from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import BadRequest, TelegramError
from bot.utils import sc, is_admin, is_owner, bot_is_admin, check_cooldown, resolve_target
from bot.middleware import blacklist_check
from database.models import (add_warning, remove_last_warning, count_warnings,
                               get_warnings, clear_warnings, get_group, add_log)

def _guard(func):
    async def wrapper(update: Update, ctx):
        if await blacklist_check(update, ctx): return
        uid, cid = update.effective_user.id, update.effective_chat.id
        if update.effective_chat.type == "private":
            return await update.message.reply_text(sc("Use this command in a group."))
        if not check_cooldown(uid, func.__name__): return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper

async def _require_admin(update, ctx):
    uid, cid = update.effective_user.id, update.effective_chat.id
    if is_owner(uid): return True
    if await is_admin(ctx.bot, cid, uid): return True
    await update.message.reply_text(sc("You need to be an admin."))
    return False

async def _require_bot_admin(update, ctx):
    if await bot_is_admin(ctx.bot, update.effective_chat.id): return True
    await update.message.reply_text(sc("I need admin rights to do that."))
    return False

@_guard
async def kick(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    cid = update.effective_chat.id
    try:
        m = await ctx.bot.get_chat_member(cid, tid)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot kick an admin."))
        await ctx.bot.ban_chat_member(cid, tid)
        await ctx.bot.unban_chat_member(cid, tid)
        await add_log(cid, tid, update.effective_user.id, "kick")
        await update.message.reply_text(f"👢 {sc('User kicked.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def ban(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    cid = update.effective_chat.id
    try:
        m = await ctx.bot.get_chat_member(cid, tid)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot ban an admin."))
        await ctx.bot.ban_chat_member(cid, tid)
        if update.message.reply_to_message:
            try: await update.message.reply_to_message.delete()
            except: pass
        await add_log(cid, tid, update.effective_user.id, "ban")
        await update.message.reply_text(f"🔨 {sc('User banned.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def unban(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    try:
        await ctx.bot.unban_chat_member(update.effective_chat.id, tid, only_if_banned=True)
        await add_log(update.effective_chat.id, tid, update.effective_user.id, "unban")
        await update.message.reply_text(f"✅ {sc('User unbanned.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def mute(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    cid = update.effective_chat.id
    duration = None
    if ctx.args and len(ctx.args) > 1:
        try: duration = int(ctx.args[1])
        except: pass
    try:
        m = await ctx.bot.get_chat_member(cid, tid)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot mute an admin."))
        until = None
        if duration:
            from datetime import datetime, timezone, timedelta
            until = datetime.now(timezone.utc) + timedelta(seconds=duration)
        await ctx.bot.restrict_chat_member(cid, tid, ChatPermissions(can_send_messages=False), until_date=until)
        dur_txt = f" {sc('for')} {duration}s" if duration else ""
        await add_log(cid, tid, update.effective_user.id, "mute", {"duration": duration})
        await update.message.reply_text(f"🔇 {sc('User muted')}{dur_txt}.")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def unmute(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    try:
        await ctx.bot.restrict_chat_member(update.effective_chat.id, tid,
            ChatPermissions(can_send_messages=True, can_send_polls=True,
                            can_send_other_messages=True, can_add_web_page_previews=True,
                            can_invite_users=True))
        await add_log(update.effective_chat.id, tid, update.effective_user.id, "unmute")
        await update.message.reply_text(f"🔊 {sc('User unmuted.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def warn(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    cid = update.effective_chat.id
    reason = " ".join(ctx.args[1:]) if ctx.args and len(ctx.args) > 1 else None
    try:
        m = await ctx.bot.get_chat_member(cid, tid)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot warn an admin."))
        g = await get_group(cid)
        limit = g.get("settings", {}).get("warn_limit", 3)
        count = await add_warning(cid, tid, update.effective_user.id, reason)
        await add_log(cid, tid, update.effective_user.id, "warn", {"reason": reason, "count": count})
        if count >= limit:
            await ctx.bot.ban_chat_member(cid, tid)
            await clear_warnings(cid, tid)
            await add_log(cid, tid, update.effective_user.id, "auto-ban")
            return await update.message.reply_text(
                f"🔨 {sc('User reached')} {count}/{limit} {sc('warnings — auto-banned.')}")
        r_txt = f"\n📝 {sc('Reason')}: {reason}" if reason else ""
        await update.message.reply_text(f"⚠️ {sc('Warning')} {count}/{limit}{r_txt}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def unwarn(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    ok = await remove_last_warning(update.effective_chat.id, tid)
    remaining = await count_warnings(update.effective_chat.id, tid)
    if ok: await update.message.reply_text(f"✅ {sc('Warning removed. Remaining:')} {remaining}")
    else:  await update.message.reply_text(sc("No warnings to remove."))

@_guard
async def warnings_cmd(update: Update, ctx):
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    cid = update.effective_chat.id
    g = await get_group(cid)
    limit = g.get("settings", {}).get("warn_limit", 3)
    warns = await get_warnings(cid, tid)
    if not warns: return await update.message.reply_text(sc("No warnings for this user."))
    try: u = await ctx.bot.get_chat(tid); name = sc(u.first_name or str(tid))
    except: name = str(tid)
    lines = [f"⚠️ *{sc('Warnings for')} {name}* ({len(warns)}/{limit})\n━━━━━━━━━━━━"]
    for i, w in enumerate(warns, 1):
        t = w["created_at"].strftime("%Y-%m-%d")
        r = f": {w['reason']}" if w.get("reason") else ""
        lines.append(f"{i}. {t}{r}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@_guard
async def setwarnlimit(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not ctx.args:
        return await update.message.reply_text(sc("Usage: /setwarnlimit <number>"))
    try: limit = int(ctx.args[0])
    except: return await update.message.reply_text(sc("Provide a valid number."))
    if limit < 1: return await update.message.reply_text(sc("Minimum is 1."))
    from database.models import update_group_setting
    await update_group_setting(update.effective_chat.id, "warn_limit", limit)
    await update.message.reply_text(f"✅ {sc('Warn limit set to')} {limit}.")

def register(app: Application):
    for cmd, func in [
        ("kick",         kick),
        ("ban",          ban),
        ("unban",        unban),
        ("mute",         mute),
        ("unmute",       unmute),
        ("warn",         warn),
        ("unwarn",       unwarn),
        ("warnings",     warnings_cmd),
        ("setwarnlimit", setwarnlimit),
    ]:
        app.add_handler(CommandHandler(cmd, func))
