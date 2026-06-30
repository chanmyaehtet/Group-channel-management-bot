import asyncio
from datetime import datetime, timezone
from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import BadRequest, TelegramError

from bot.utils import sc, is_admin, is_owner, bot_is_admin, check_cooldown, get_target_user_id, log_action
from database.connection import get_db


async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "kick"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        m = await context.bot.get_chat_member(cid, target)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot kick an admin."))
        await context.bot.ban_chat_member(cid, target)
        await context.bot.unban_chat_member(cid, target)
        await log_action(context.bot, cid, target, uid, "kick")
        await update.message.reply_text(sc("User kicked."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "ban"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        m = await context.bot.get_chat_member(cid, target)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot ban an admin."))
        await context.bot.ban_chat_member(cid, target)
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await log_action(context.bot, cid, target, uid, "ban")
        await update.message.reply_text(sc("User banned."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "unban"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        await context.bot.unban_chat_member(cid, target, only_if_banned=True)
        await log_action(context.bot, cid, target, uid, "unban")
        await update.message.reply_text(sc("User unbanned."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "mute"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    duration = None
    if context.args and len(context.args) > 1:
        try:
            duration = int(context.args[1])
        except ValueError:
            pass
    try:
        m = await context.bot.get_chat_member(cid, target)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot mute an admin."))
        until = None
        if duration:
            from datetime import timedelta
            until = datetime.now(timezone.utc) + timedelta(seconds=duration)
        await context.bot.restrict_chat_member(
            cid, target,
            ChatPermissions(can_send_messages=False),
            until_date=until
        )
        dur_text = f" {sc('for')} {duration}s" if duration else ""
        await log_action(context.bot, cid, target, uid, f"mute{dur_text}")
        await update.message.reply_text(sc(f"User muted{dur_text}."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "unmute"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        await context.bot.restrict_chat_member(
            cid, target,
            ChatPermissions(
                can_send_messages=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
            )
        )
        await log_action(context.bot, cid, target, uid, "unmute")
        await update.message.reply_text(sc("User unmuted."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "warn"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    reason = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else None
    try:
        m = await context.bot.get_chat_member(cid, target)
        if m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            return await update.message.reply_text(sc("Cannot warn an admin."))
        db = get_db()
        config = await db.group_configs.find_one({"group_id": cid})
        warn_limit = config.get("warn_limit", 3) if config else 3
        await db.warnings.insert_one({
            "group_id": cid, "user_id": target, "admin_id": uid,
            "reason": reason, "created_at": datetime.now(timezone.utc),
        })
        count = await db.warnings.count_documents({"group_id": cid, "user_id": target})
        await log_action(context.bot, cid, target, uid,
                         f"warn ({count}/{warn_limit})" + (f": {reason}" if reason else ""))
        if count >= warn_limit:
            await context.bot.ban_chat_member(cid, target)
            await log_action(context.bot, cid, target, uid, f"auto-ban after {count} warnings")
            return await update.message.reply_text(
                sc(f"User reached {count}/{warn_limit} warnings and has been banned.")
            )
        await update.message.reply_text(
            sc(f"User warned ({count}/{warn_limit}).") +
            (f" {sc('Reason')}: {reason}" if reason else "")
        )
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "unwarn"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        db = get_db()
        latest = await db.warnings.find_one(
            {"group_id": cid, "user_id": target}, sort=[("created_at", -1)]
        )
        if not latest:
            return await update.message.reply_text(sc("This user has no warnings to remove."))
        await db.warnings.delete_one({"_id": latest["_id"]})
        count = await db.warnings.count_documents({"group_id": cid, "user_id": target})
        await log_action(context.bot, cid, target, uid, f"unwarn (remaining: {count})")
        await update.message.reply_text(sc(f"Warning removed. User now has {count} warnings."))
    except Exception as e:
        await update.message.reply_text(f"{sc('Error')}: {e}")


async def warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not check_cooldown(update.effective_user.id, "warnings"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        db = get_db()
        config = await db.group_configs.find_one({"group_id": cid})
        warn_limit = config.get("warn_limit", 3) if config else 3
        all_warns = await db.warnings.find(
            {"group_id": cid, "user_id": target}
        ).sort("created_at", -1).to_list(length=None)
        if not all_warns:
            return await update.message.reply_text(sc("This user has no warnings."))
        try:
            user = await context.bot.get_chat(target)
            name = user.first_name or str(target)
        except Exception:
            name = str(target)
        text = f"*{sc('Warnings for')} {name}* ({len(all_warns)}/{warn_limit}):\n\n"
        for i, w in enumerate(all_warns, 1):
            try:
                admin = await context.bot.get_chat(w["admin_id"])
                aname = admin.first_name
            except Exception:
                aname = str(w["admin_id"])
            t = w["created_at"].strftime("%Y-%m-%d %H:%M")
            r = f": {w['reason']}" if w.get("reason") else ""
            text += f"{i}. {sc('By')} {aname} {sc('on')} {t}{r}\n"
        await update.message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"{sc('Error')}: {e}")


def register(app: Application):
    app.add_handler(CommandHandler("kick", kick))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CommandHandler("warn", warn))
    app.add_handler(CommandHandler("unwarn", unwarn))
    app.add_handler(CommandHandler("warnings", warnings))
