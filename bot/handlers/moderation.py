"""
Moderation commands: /kick /ban /unban /mute /unmute /warn /unwarn /warnings /setwarnlimit

Group commands: kick, ban, unban, mute, unmute, warn, setwarnlimit
PM + Group commands: unwarn, warnings (with user_id arg in PM)
"""
from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import BadRequest, TelegramError
from bot.utils import sc, md_escape, is_admin, is_owner, bot_is_admin, check_cooldown, resolve_target
from bot.middleware import blacklist_check
from database.models import (add_warning, remove_last_warning, count_warnings,
                               get_warnings, clear_warnings, get_group, add_log,
                               update_group_setting)


# ── Guards ─────────────────────────────────────────────────────────────────────

def _group_guard(func):
    """Requires group chat + cooldown + blacklist check."""
    async def wrapper(update: Update, ctx):
        if await blacklist_check(update, ctx): return
        if update.effective_chat.type == "private":
            return await update.message.reply_text(
                sc("This command only works in a group chat.")
            )
        uid = update.effective_user.id
        if not check_cooldown(uid, func.__name__): return
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper


async def _require_admin(update, ctx):
    uid, cid = update.effective_user.id, update.effective_chat.id
    if is_owner(uid): return True
    if await is_admin(ctx.bot, cid, uid): return True
    await update.message.reply_text(sc("You need to be an admin to use this command."))
    return False


async def _require_bot_admin(update, ctx):
    if await bot_is_admin(ctx.bot, update.effective_chat.id): return True
    await update.message.reply_text(sc("I need admin rights to do that."))
    return False


# ── /kick ──────────────────────────────────────────────────────────────────────

@_group_guard
async def kick(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid:
        return await update.message.reply_text(
            sc("Reply to a message or provide a user ID / @username.")
        )
    cid = update.effective_chat.id
    try:
        m = await ctx.bot.get_chat_member(cid, tid)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot kick an admin."))
        await ctx.bot.ban_chat_member(cid, tid)
        await ctx.bot.unban_chat_member(cid, tid)
        await add_log(cid, tid, update.effective_user.id, "kick")
        await update.message.reply_text(f"👢 {sc('User kicked.')}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e.message}")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


# ── /ban ───────────────────────────────────────────────────────────────────────

@_group_guard
async def ban(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid:
        return await update.message.reply_text(
            sc("Reply to a message or provide a user ID / @username.")
        )
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
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e.message}")


# ── /unban ─────────────────────────────────────────────────────────────────────

@_group_guard
async def unban(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    # BUG-09 FIX: bot needs admin rights to unban members
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid:
        return await update.message.reply_text(sc("Reply or provide user ID / @username."))
    try:
        await ctx.bot.unban_chat_member(update.effective_chat.id, tid, only_if_banned=True)
        await add_log(update.effective_chat.id, tid, update.effective_user.id, "unban")
        await update.message.reply_text(f"✅ {sc('User unbanned.')}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e.message}")


# ── /mute ──────────────────────────────────────────────────────────────────────

@_group_guard
async def mute(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid:
        return await update.message.reply_text(sc("Reply or provide user ID / @username."))
    cid = update.effective_chat.id
    # Duration arg index depends on whether target was reply (arg[0]) or explicit (arg[1])
    _dur_idx = 0 if update.message.reply_to_message else 1
    duration = None
    if ctx.args and len(ctx.args) > _dur_idx:
        try: duration = int(ctx.args[_dur_idx])
        except: pass
    try:
        m = await ctx.bot.get_chat_member(cid, tid)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot mute an admin."))
        until = None
        if duration:
            from datetime import datetime, timezone, timedelta
            until = datetime.now(timezone.utc) + timedelta(seconds=duration)
        await ctx.bot.restrict_chat_member(
            cid, tid, ChatPermissions(can_send_messages=False), until_date=until
        )
        dur_txt = f" {sc('for')} {duration}s" if duration else ""
        await add_log(cid, tid, update.effective_user.id, "mute", {"duration": duration})
        await update.message.reply_text(f"🔇 {sc('User muted')}{dur_txt}.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e.message}")


# ── /unmute ────────────────────────────────────────────────────────────────────

@_group_guard
async def unmute(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid:
        return await update.message.reply_text(sc("Reply or provide user ID / @username."))
    try:
        await ctx.bot.restrict_chat_member(
            update.effective_chat.id, tid,
            ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True,
            )
        )
        await add_log(update.effective_chat.id, tid, update.effective_user.id, "unmute")
        await update.message.reply_text(f"🔊 {sc('User unmuted.')}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e.message}")


# ── /warn ──────────────────────────────────────────────────────────────────────

@_group_guard
async def warn(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not await _require_bot_admin(update, ctx): return
    tid, _ = await resolve_target(update, ctx)
    if not tid:
        return await update.message.reply_text(sc("Reply or provide user ID / @username."))
    cid = update.effective_chat.id
    _r_start = 0 if update.message.reply_to_message else 1
    reason = " ".join(ctx.args[_r_start:]) if ctx.args and len(ctx.args) > _r_start else None
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
                f"🔨 {sc('User reached')} {count}/{limit} {sc('warnings — auto-banned.')}"
            )
        r_txt = f"\n📝 {sc('Reason')}: {md_escape(reason)}" if reason else ""
        await update.message.reply_text(f"⚠️ {sc('Warning')} {count}/{limit}{r_txt}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ {e.message}")


# ── /unwarn — works in group AND PM ───────────────────────────────────────────
# PM usage: /unwarn <user_id> <group_id>

async def unwarn(update: Update, ctx):
    if await blacklist_check(update, ctx): return
    uid = update.effective_user.id
    # BUG-13 FIX: add rate limiting — this command works in PM too so _group_guard can't be used
    if not check_cooldown(uid, "unwarn"):
        return await update.message.reply_text(sc("Please wait before using this command again."))

    if update.effective_chat.type == "private":
        # PM: /unwarn <user_id> <group_id>
        if not ctx.args or len(ctx.args) < 2:
            return await update.message.reply_text(
                f"*{sc('PM Usage')}:* `/unwarn <user_id> <group_id>`",
                parse_mode="Markdown"
            )
        try:
            tid  = int(ctx.args[0])
            cid  = int(ctx.args[1])
        except ValueError:
            return await update.message.reply_text(sc("Provide numeric user_id and group_id."))
        if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
            return await update.message.reply_text(sc("You need to be an admin of that group."))
    else:
        cid = update.effective_chat.id
        if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
            return await update.message.reply_text(sc("You need to be an admin."))
        tid, _ = await resolve_target(update, ctx)
        if not tid:
            return await update.message.reply_text(sc("Reply or provide user ID."))

    ok = await remove_last_warning(cid, tid)
    remaining = await count_warnings(cid, tid)
    if ok:
        await update.message.reply_text(
            f"✅ {sc('Warning removed.')} {sc('Remaining:')} {remaining}"
        )
    else:
        await update.message.reply_text(sc("No warnings to remove."))


# ── /warnings — works in group AND PM ─────────────────────────────────────────
# PM usage: /warnings <user_id> <group_id>

async def warnings_cmd(update: Update, ctx):
    if await blacklist_check(update, ctx): return
    uid = update.effective_user.id
    # BUG-13 FIX: add rate limiting — this command works in PM too so _group_guard can't be used
    if not check_cooldown(uid, "warnings"):
        return await update.message.reply_text(sc("Please wait before using this command again."))

    if update.effective_chat.type == "private":
        # PM: /warnings <user_id> <group_id>
        if not ctx.args or len(ctx.args) < 2:
            return await update.message.reply_text(
                f"*{sc('PM Usage')}:* `/warnings <user_id> <group_id>`\n"
                f"_{sc('Or use this command inside the group directly.')}_",
                parse_mode="Markdown"
            )
        try:
            tid = int(ctx.args[0])
            cid = int(ctx.args[1])
        except ValueError:
            return await update.message.reply_text(sc("Provide numeric user_id and group_id."))
        if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
            return await update.message.reply_text(sc("You need to be an admin of that group."))
    else:
        cid = update.effective_chat.id
        tid, _ = await resolve_target(update, ctx)
        if not tid:
            return await update.message.reply_text(sc("Reply or provide user ID."))

    g = await get_group(cid)
    limit = g.get("settings", {}).get("warn_limit", 3)
    warns = await get_warnings(cid, tid)
    if not warns:
        return await update.message.reply_text(sc("No warnings for this user."))

    try:
        u = await ctx.bot.get_chat(tid)
        # BUG FIX: escape special Markdown chars in user's name
        raw_name = u.first_name or str(tid)
        name = md_escape(sc(raw_name))
    except:
        name = str(tid)

    lines = [f"⚠️ *{sc('Warnings for')} {name}* ({len(warns)}/{limit})\n━━━━━━━━━━━━"]
    for i, w in enumerate(warns, 1):
        t = w["created_at"].strftime("%Y-%m-%d")
        # BUG FIX: escape reason text too
        r = f": {md_escape(w['reason'])}" if w.get("reason") else ""
        lines.append(f"{i}. {t}{r}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── /setwarnlimit ──────────────────────────────────────────────────────────────

@_group_guard
async def setwarnlimit(update: Update, ctx):
    if not await _require_admin(update, ctx): return
    if not ctx.args:
        return await update.message.reply_text(sc("Usage: /setwarnlimit <number>"))
    try:
        limit = int(ctx.args[0])
    except:
        return await update.message.reply_text(sc("Provide a valid number."))
    if limit < 1:
        return await update.message.reply_text(sc("Minimum is 1."))
    await update_group_setting(update.effective_chat.id, "warn_limit", limit)
    await update.message.reply_text(f"✅ {sc('Warn limit set to')} {limit}.")


# ── Registration ───────────────────────────────────────────────────────────────

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
