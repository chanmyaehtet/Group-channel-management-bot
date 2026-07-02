import asyncio
from telegram import Update, ChatMember, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import BadRequest, TelegramError

from bot.utils import sc, is_admin, is_owner, bot_is_admin, check_cooldown, get_target_user_id, log_action
from database.connection import get_db
from database.models import update_group_setting, count_warnings

_ALL_PERMISSIONS = ChatPermissions(
    can_send_messages=True, can_send_polls=True,
    can_send_other_messages=True, can_add_web_page_previews=True,
    can_change_info=False, can_invite_users=True, can_pin_messages=False,
)
_NO_PERMISSIONS = ChatPermissions(
    can_send_messages=False, can_send_polls=False,
    can_send_other_messages=False, can_add_web_page_previews=False,
    can_change_info=False, can_invite_users=False, can_pin_messages=False,
)


def _group_only_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            sc("Add me to a group") + " ➕",
            url=f"https://t.me/{bot_username}?startgroup=true"
        )
    ]])


async def lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to lock the chat."))
    try:
        await context.bot.set_chat_permissions(cid, _NO_PERMISSIONS)
        await update_group_setting(cid, "locked", True)
        await log_action(context.bot, cid, uid, uid, "locked the chat")
        await update.message.reply_text("🔒 " + sc("Chat locked. Only admins can send messages."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to unlock the chat."))
    try:
        await context.bot.set_chat_permissions(cid, _ALL_PERMISSIONS)
        await update_group_setting(cid, "locked", False)
        await log_action(context.bot, cid, uid, uid, "unlocked the chat")
        await update.message.reply_text("🔓 " + sc("Chat unlocked. Members can send messages again."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to pin messages."))
    if not update.message.reply_to_message:
        return await update.message.reply_text(sc("Reply to a message to pin it."))
    try:
        await context.bot.pin_chat_message(cid, update.message.reply_to_message.message_id, disable_notification=False)
        await log_action(context.bot, cid, uid, uid, "pinned a message")
        await update.message.reply_text("📌 " + sc("Message pinned."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to unpin messages."))
    try:
        if update.message.reply_to_message:
            await context.bot.unpin_chat_message(cid, update.message.reply_to_message.message_id)
        else:
            await context.bot.unpin_chat_message(cid)
        await log_action(context.bot, cid, uid, uid, "unpinned a message")
        await update.message.reply_text("📌 " + sc("Message unpinned."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to promote members."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    title = " ".join(context.args[1:]) if context.args and len(context.args) > 1 else ""
    try:
        await context.bot.promote_chat_member(
            cid, target,
            can_manage_chat=True, can_delete_messages=True,
            can_restrict_members=True, can_invite_users=True, can_pin_messages=True,
        )
        if title:
            await context.bot.set_chat_administrator_custom_title(cid, target, title)
        await log_action(context.bot, cid, target, uid, f"promoted" + (f" as '{title}'" if title else ""))
        suffix = f" ({sc('title')}: {title})" if title else ""
        await update.message.reply_text("⭐ " + sc("User promoted to admin.") + suffix)
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to demote admins."))
    target = await get_target_user_id(update, context)
    if not target:
        return await update.message.reply_text(sc("Reply to a message or provide a user ID."))
    try:
        await context.bot.promote_chat_member(
            cid, target,
            can_manage_chat=False, can_delete_messages=False,
            can_restrict_members=False, can_invite_users=False, can_pin_messages=False,
        )
        await log_action(context.bot, cid, target, uid, "demoted from admin")
        await update.message.reply_text("🔽 " + sc("User demoted from admin."))
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    if not check_cooldown(update.effective_user.id, "info"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    cid = update.effective_chat.id
    target = await get_target_user_id(update, context)
    if not target:
        target = update.effective_user.id
    try:
        user = await context.bot.get_chat(target)
        member = await context.bot.get_chat_member(cid, target)
        warn_count = await count_warnings(cid, target)
        status_map = {
            ChatMember.OWNER:         sc("Owner"),
            ChatMember.ADMINISTRATOR: sc("Admin"),
            ChatMember.MEMBER:        sc("Member"),
            ChatMember.RESTRICTED:    sc("Restricted"),
            ChatMember.LEFT:          sc("Left"),
            ChatMember.BANNED:        sc("Banned"),
        }
        status = status_map.get(member.status, sc("Unknown"))
        uname  = f"@{user.username}" if user.username else sc("None")
        name   = sc((user.first_name or "") + (" " + user.last_name if user.last_name else "")).strip()
        text = (
            f"👤 *{sc('User Info')}*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"🆔 *{sc('ID')}:* `{user.id}`\n"
            f"👤 *{sc('Name')}:* {name}\n"
            f"📛 *{sc('Username')}:* {uname}\n"
            f"🔰 *{sc('Status')}:* {status}\n"
            f"⚠️ *{sc('Warnings')}:* {warn_count}\n"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    if not check_cooldown(update.effective_user.id, "report"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    cid = update.effective_chat.id
    reporter = update.effective_user
    reason = " ".join(context.args) if context.args else sc("No reason given")
    if not update.message.reply_to_message:
        return await update.message.reply_text(sc("Reply to a message to report it."))
    reported_user = update.message.reply_to_message.from_user
    try:
        admins = await context.bot.get_chat_administrators(cid)
        admin_mentions = " ".join(
            f"[{sc(a.user.first_name)}](tg://user?id={a.user.id})"
            for a in admins if not a.user.is_bot
        )
        reporter_link = f"[{sc(reporter.first_name)}](tg://user?id={reporter.id})"
        reported_name = reported_user.first_name if reported_user else "?"
        reported_link = f"[{sc(reported_name)}](tg://user?id={reported_user.id if reported_user else 0})"
        text = (
            f"🚨 *{sc('Report')}*\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"👤 *{sc('Reported by')}:* {reporter_link}\n"
            f"🎯 *{sc('Reported user')}:* {reported_link}\n"
            f"📝 *{sc('Reason')}:* {sc(reason)}\n\n"
            f"📣 {sc('Admins')}: {admin_mentions}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
        await log_action(context.bot, cid, reported_user.id if reported_user else 0, reporter.id, f"reported: {reason}")
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("This command only works in groups."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not await bot_is_admin(context.bot, cid):
        return await update.message.reply_text(sc("I need admin rights to delete messages."))
    count = 10
    if context.args:
        try:
            count = max(1, min(int(context.args[0]), 100))
        except ValueError:
            pass
    start_msg_id = update.message.message_id
    ids_to_delete = list(range(start_msg_id, start_msg_id - count - 1, -1))
    deleted = 0
    try:
        for chunk in [ids_to_delete[i:i+100] for i in range(0, len(ids_to_delete), 100)]:
            try:
                await context.bot.delete_messages(cid, chunk)
                deleted += len(chunk)
            except Exception:
                for mid in chunk:
                    try:
                        await context.bot.delete_message(cid, mid)
                        deleted += 1
                    except Exception:
                        pass
        await log_action(context.bot, cid, uid, uid, f"purged ~{deleted} messages")
        confirm = await context.bot.send_message(cid, "🗑️ " + sc(f"Purged {deleted} messages."))
        await asyncio.sleep(3)
        await confirm.delete()
    except (BadRequest, TelegramError) as e:
        await update.message.reply_text(f"{sc('Error')}: {e.message}")


async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show Telegram ID of self, a replied-to user, or a username lookup."""
    if not check_cooldown(update.effective_user.id, "id"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    target = await get_target_user_id(update, context)
    chat   = update.effective_chat
    if target and target != update.effective_user.id:
        try:
            user = await context.bot.get_chat(target)
            name  = sc((user.first_name or "") + (" " + user.last_name if user.last_name else "")).strip()
            uname = f"@{user.username}" if user.username else sc("No username")
            await update.message.reply_text(
                f"👤 *{name}*\n🆔 `{target}`\n📛 {uname}",
                parse_mode="Markdown"
            )
        except Exception:
            await update.message.reply_text(f"🆔 `{target}`", parse_mode="Markdown")
    else:
        user  = update.effective_user
        name  = sc((user.first_name or "") + (" " + user.last_name if user.last_name else "")).strip()
        uname = f"@{user.username}" if user.username else sc("No username")
        lines = [f"👤 *{name}*\n🆔 `{user.id}`\n📛 {uname}"]
        if chat.type != "private":
            gname = sc(chat.title or "Group")
            lines.append(f"\n👥 *{gname}*\n🆔 `{chat.id}`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def register(app: Application):
    app.add_handler(CommandHandler("lock",    lock))
    app.add_handler(CommandHandler("unlock",  unlock))
    app.add_handler(CommandHandler("pin",     pin))
    app.add_handler(CommandHandler("unpin",   unpin))
    app.add_handler(CommandHandler("promote", promote))
    app.add_handler(CommandHandler("demote",  demote))
    app.add_handler(CommandHandler("info",    info))
    app.add_handler(CommandHandler("report",  report))
    app.add_handler(CommandHandler("purge",   purge))
    app.add_handler(CommandHandler("id",      id_cmd))
