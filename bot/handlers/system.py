"""
System handlers: /start (inline menu), /ping, welcome/goodbye,
setwelcome, setgoodbye, setrules, rules.
"""

from datetime import datetime, timezone

from telegram import (
    Update, ChatMember,
    InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CallbackQueryHandler,
    ChatMemberHandler, CommandHandler, ContextTypes,
)

from bot.utils import sc, md_escape, is_admin, is_owner, check_cooldown, log_action
from database.models import get_group, update_group_setting, upsert_group


# ── /start menu ────────────────────────────────────────────────────────────────

_MENU: dict[str, str] = {
    "mod": (
        f"🛡 *{sc('Moderation Commands')}*\n\n"
        f"`/kick` — {sc('Kick a user (reply or user_id)')}\n"
        f"`/ban` — {sc('Permanently ban a user')}\n"
        f"`/unban <id>` — {sc('Unban a user')}\n"
        f"`/mute [sec]` — {sc('Mute a user')}\n"
        f"`/unmute` — {sc('Unmute a user')}\n"
        f"`/purge [n]` — {sc('Delete last N messages (max 100)')}\n"
        f"`/pin` — {sc('Pin replied message')}\n"
        f"`/unpin` — {sc('Unpin message')}\n"
        f"`/promote` — {sc('Promote user to admin')}\n"
        f"`/demote` — {sc('Remove admin rights')}\n"
        f"`/report` — {sc('Report user to admins')}"
    ),
    "warn": (
        f"⚠️ *{sc('Warning System')}*\n\n"
        f"`/warn [reason]` — {sc('Warn a user')}\n"
        f"`/unwarn` — {sc('Remove last warning')}\n"
        f"`/warnings` — {sc('View all warnings')}\n"
        f"`/setwarnlimit <n>` — {sc('Set auto-ban limit (default: 3)')}\n\n"
        f"_{sc('PM usage: /warnings <user_id> <group_id>')}_\n"
        f"_{sc('When a user reaches the warn limit they are automatically banned.')}_"
    ),
    "group": (
        f"🔒 *{sc('Group Control')}*\n\n"
        f"`/lock` — {sc('Lock chat (no messages)')}\n"
        f"`/unlock` — {sc('Unlock chat')}\n"
        f"`/setrules <text>` — {sc('Set group rules')}\n"
        f"`/rules` — {sc('Show group rules')}\n"
        f"`/setwelcome <text>` — {sc('Custom welcome message')}\n"
        f"`/setgoodbye <text>` — {sc('Custom goodbye message')}\n\n"
        f"_{sc('Placeholders: {user} {first_name} {last_name} {username} {group}')}_"
    ),
    "settings": (
        f"⚙️ *{sc('Settings & Anti-Spam')}*\n\n"
        f"`/antispam on|off` — {sc('Enable / disable anti-spam')}\n"
        f"`/antispam_links on|off` — {sc('Toggle link deletion')}\n"
        f"`/antispam_flood on|off` — {sc('Toggle flood protection')}\n"
        f"`/autocleaner on|off` — {sc('Auto-kick deleted accounts')}\n"
        f"`/clean` — {sc('Manually clean inactive accounts')}"
    ),
    "schedule": (
        f"⏰ *{sc('Scheduling')}*\n\n"
        f"`/setschedule onetime HH:MM <text>` — {sc('Send once at that time')}\n"
        f"`/setschedule always HH:MM <text>` — {sc('Send every day at that time')}\n"
        f"`/listschedules` — {sc('Show active schedules for this group')}\n"
        f"`/delschedule <id>` — {sc('Delete a schedule')}\n\n"
        f"_{sc('All times are in Asia/Yangon timezone (UTC+6:30).')}_"
    ),
    "id": (
        f"👤 *{sc('ID & Info')}*\n\n"
        f"`/id` — {sc('Your own Telegram ID + group ID')}\n"
        f"`/id @username` — {sc('Look up any username (works in PM too)')}\n"
        f"`/id` _(reply)_ — {sc('ID of replied-to user')}\n"
        f"`/info` — {sc('Full profile info & warnings (works in PM too)')}\n"
        f"`/warnings <user_id> <group_id>` — {sc('Check warnings from PM')}"
    ),
    "owner": (
        f"👑 *{sc('Owner Panel')}*\n\n"
        f"`/status` — {sc('System status (users & groups)')}\n"
        f"`/ping` — {sc('Response speed (ms)')}\n"
        f"`/listusers` — {sc('Total user count')}\n"
        f"`/listgroups` — {sc('All registered groups')}\n"
        f"`/blockuser <id>` — {sc('Block a user globally')}\n"
        f"`/unblockuser <id>` — {sc('Unblock a user')}\n"
        f"`/blockgroup <id>` — {sc('Block & leave a group')}\n"
        f"`/unblockgroup <id>` — {sc('Unblock a group')}\n"
        f"`/broadcast all <text>` — {sc('Broadcast to all users & groups')}\n"
        f"`/broadcast group <id> <text>` — {sc('Send to one group')}\n"
        f"`/broadcast user <id> <text>` — {sc('Send to one user')}\n"
        f"`/post` — {sc('Create & send an announcement (admins & owners)')}"
    ),
}

_BACK_ROW = [[InlineKeyboardButton(f"« {sc('Back')}", callback_data="menu:back")]]


def _main_keyboard(owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(f"🛡 {sc('Moderation')}",    callback_data="menu:mod"),
            InlineKeyboardButton(f"⚠️ {sc('Warnings')}",      callback_data="menu:warn"),
        ],
        [
            InlineKeyboardButton(f"🔒 {sc('Group Control')}",  callback_data="menu:group"),
            InlineKeyboardButton(f"⚙️ {sc('Settings')}",      callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton(f"⏰ {sc('Scheduling')}",    callback_data="menu:schedule"),
            InlineKeyboardButton(f"👤 {sc('ID & Info')}",     callback_data="menu:id"),
        ],
    ]
    if owner:
        rows.append([InlineKeyboardButton(f"👑 {sc('Owner Panel')}", callback_data="menu:owner")])
    return InlineKeyboardMarkup(rows)


def _welcome_text(first_name: str) -> str:
    # BUG FIX: escape Markdown special chars from user-supplied name
    name = md_escape(first_name)
    return (
        f"👋 *{sc('Hello')}, {name}!*\n\n"
        f"{sc('I am your Group Management Bot.')}\n"
        f"{sc('Choose a category below to see available commands.')}"
    )


# ── /start ─────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    if chat.type != "private":
        await update.message.reply_text(
            f"👋 {sc('Hi')} {md_escape(user.first_name)}! "
            f"{sc('DM me to see all available commands.')}",
        )
        return
    owner = is_owner(user.id)
    await update.message.reply_text(
        _welcome_text(user.first_name),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(owner),
    )


# ── Inline menu callbacks ──────────────────────────────────────────────────────

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user  = query.from_user
    parts = query.data.split(":", 1)
    if len(parts) < 2:
        return
    key   = parts[1]
    owner = is_owner(user.id)

    if key == "back":
        await query.edit_message_text(
            _welcome_text(user.first_name),
            parse_mode="Markdown",
            reply_markup=_main_keyboard(owner),
        )
        return

    if key == "owner" and not owner:
        await query.answer(f"⛔ {sc('Owner only.')}", show_alert=True)
        return

    text = _MENU.get(key)
    if not text:
        return

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(_BACK_ROW),
    )


# ── /rules ─────────────────────────────────────────────────────────────────────

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_cooldown(update.effective_user.id, "rules"):
        return await update.message.reply_text(
            sc("Please wait before using this command again.")
        )
    # Allow /rules in PM if the user provides a group_id: /rules <group_id>
    if update.effective_chat.type == "private":
        if not context.args:
            return await update.message.reply_text(
                f"*{sc('PM Usage')}:* `/rules <group_id>`\n"
                f"_{sc('Or use this command inside the group directly.')}_",
                parse_mode="Markdown"
            )
        try:
            cid = int(context.args[0])
        except ValueError:
            return await update.message.reply_text(sc("Provide a numeric group_id."))
    else:
        cid = update.effective_chat.id

    group = await get_group(cid)
    rules_text = group.get("settings", {}).get("rules", "")
    if not rules_text:
        return await update.message.reply_text(sc("No rules set for this group."))
    await update.message.reply_text(
        f"📜 *{sc('Rules')}*\n\n{rules_text}", parse_mode="Markdown"
    )


# ── /setrules ──────────────────────────────────────────────────────────────────

async def setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("Use this command inside the group.")
        )
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(
            sc("You need to be an admin to use this command.")
        )
    if not check_cooldown(uid, "setrules"):
        return await update.message.reply_text(
            sc("Please wait before using this command again.")
        )
    if not context.args:
        return await update.message.reply_text(sc("Please provide the rules text."))
    rules_text = " ".join(context.args)
    await update_group_setting(cid, "rules", rules_text)
    await log_action(context.bot, cid, uid, uid, "set rules")
    await update.message.reply_text(sc("Rules set successfully."))


# ── /setwelcome ────────────────────────────────────────────────────────────────

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use this command inside the group."))
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(
            sc("You need to be an admin to use this command.")
        )
    if not check_cooldown(uid, "setwelcome"):
        return await update.message.reply_text(
            sc("Please wait before using this command again.")
        )
    if not context.args:
        return await update.message.reply_text(
            sc(
                "Usage: /setwelcome your message here\n"
                "Placeholders: {user} {first_name} {last_name} {username} {group}"
            )
        )
    msg = " ".join(context.args)
    await update_group_setting(cid, "welcome_message", msg)
    await log_action(context.bot, cid, uid, uid, "set welcome message")
    await update.message.reply_text(sc("Welcome message set successfully."))


# ── /setgoodbye ────────────────────────────────────────────────────────────────

async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use this command inside the group."))
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(
            sc("You need to be an admin to use this command.")
        )
    if not check_cooldown(uid, "setgoodbye"):
        return await update.message.reply_text(
            sc("Please wait before using this command again.")
        )
    if not context.args:
        return await update.message.reply_text(
            sc("Usage: /setgoodbye your message here")
        )
    msg = " ".join(context.args)
    await update_group_setting(cid, "goodbye_message", msg)
    await log_action(context.bot, cid, uid, uid, "set goodbye message")
    await update.message.reply_text(sc("Goodbye message set successfully."))


# ── Bot join / leave tracking ──────────────────────────────────────────────────

async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires when the BOT itself is added to / removed from a group."""
    result = update.my_chat_member
    if not result:
        return
    new_status = result.new_chat_member.status
    chat = result.chat

    if new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR):
        title = chat.title or str(chat.id)
        await upsert_group(chat.id, title)
        print(f"Bot added to group: {title} ({chat.id})")
    elif new_status in (ChatMember.LEFT, ChatMember.BANNED):
        print(f"Bot removed from group: {chat.id}")


async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires when other members join / leave a group."""
    result = update.chat_member
    if not result:
        return
    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    joined = (
        old_status in (ChatMember.LEFT, ChatMember.BANNED)
        and new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    )
    left = (
        old_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER)
        and new_status in (ChatMember.LEFT, ChatMember.BANNED)
    )

    # Always keep group title up-to-date
    if result.chat.title:
        await upsert_group(result.chat.id, result.chat.title)

    group    = await get_group(result.chat.id)
    settings = group.get("settings", {})

    def fmt(template: str, user) -> str:
        try:
            return template.format(
                user=f"@{user.username}" if user.username else user.first_name,
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                username=f"@{user.username}" if user.username else "",
                group=result.chat.title or "",
            )
        except (KeyError, IndexError):
            return template

    try:
        if joined:
            user = result.new_chat_member.user
            template = settings.get(
                "welcome_message",
                "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!"
            ) or "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!"
            await context.bot.send_message(result.chat.id, fmt(template, user))
            await log_action(context.bot, result.chat.id, user.id, 0, "joined the group")
        elif left:
            user   = result.old_chat_member.user
            action = "was banned" if new_status == ChatMember.BANNED else "left the group"
            template = settings.get(
                "goodbye_message",
                "ɢᴏᴏᴅʙʏᴇ, {user}!"
            ) or "ɢᴏᴏᴅʙʏᴇ, {user}!"
            await context.bot.send_message(result.chat.id, fmt(template, user))
            await log_action(context.bot, result.chat.id, user.id, 0, action)
    except Exception as e:
        print(f"Member update error: {e}")


# ── Registration ───────────────────────────────────────────────────────────────

def register(app: Application):
    app.add_handler(CommandHandler("start",      start))
    app.add_handler(CommandHandler("rules",      rules))
    app.add_handler(CommandHandler("setrules",   setrules))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    app.add_handler(
        ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_handler(
        ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER)
    )
