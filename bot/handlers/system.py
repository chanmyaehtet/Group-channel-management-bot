"""
System handlers: /start (inline menu), /ping, welcome/goodbye, setwelcome,
setgoodbye, setrules, rules, setwarnlimit.
"""

from datetime import datetime, timezone

from telegram import (
    Update,
    ChatMember,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
)

from bot.utils import sc, is_admin, is_owner, check_cooldown, log_action
from database.connection import get_db


# ── /start menu content ────────────────────────────────────────────────────────

_MENU: dict[str, str] = {
    "mod": (
        f"🛡 *{sc('Moderation Commands')}*\n\n"
        f"`/kick` — {sc('Kick a user (reply or user_id)')}\n"
        f"`/ban` — {sc('Permanently ban a user')}\n"
        f"`/unban <id>` — {sc('Unban a user')}\n"
        f"`/mute [sec]` — {sc('Mute a user')}\n"
        f"`/unmute` — {sc('Unmute a user')}\n"
        f"`/purge [n]` — {sc('Delete last N messages')}\n"
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
        f"`/listschedules` — {sc('Show active schedules')}\n"
        f"`/delschedule <id>` — {sc('Delete a schedule')}"
    ),
    "id": (
        f"👤 *{sc('ID & Info')}*\n\n"
        f"`/id` — {sc('Your own Telegram ID')}\n"
        f"`/id @username` — {sc('Look up any username')}\n"
        f"`/id` _(reply)_ — {sc('ID of replied-to user')}\n"
        f"`/info` — {sc('Full profile info')}"
    ),
    "owner": (
        f"👑 *{sc('Owner Panel')}*\n\n"
        f"`/status` — {sc('System status')}\n"
        f"`/ping` — {sc('Response speed')}\n"
        f"`/users` — {sc('Total user count')}\n"
        f"`/groups` — {sc('Total group count')}\n"
        f"`/blockuser <id>` — {sc('Block a user')}\n"
        f"`/unblockuser <id>` — {sc('Unblock a user')}\n"
        f"`/blockgroup <id>` — {sc('Block a group')}\n"
        f"`/unblockgroup <id>` — {sc('Unblock a group')}\n"
        f"`/broadcast all <text>` — {sc('Broadcast to all users')}\n"
        f"`/broadcast <group_id> <text>` — {sc('Broadcast to one group')}\n"
        f"`/post` — {sc('Create & send an announcement')}"
    ),
}

_BACK_ROW = [[InlineKeyboardButton(f"« {sc('Back')}", callback_data="menu:back")]]


def _main_keyboard(owner: bool) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(f"🛡 {sc('Moderation')}",   callback_data="menu:mod"),
            InlineKeyboardButton(f"⚠️ {sc('Warnings')}",     callback_data="menu:warn"),
        ],
        [
            InlineKeyboardButton(f"🔒 {sc('Group Control')}", callback_data="menu:group"),
            InlineKeyboardButton(f"⚙️ {sc('Settings')}",     callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton(f"⏰ {sc('Scheduling')}",   callback_data="menu:schedule"),
            InlineKeyboardButton(f"👤 {sc('ID & Info')}",    callback_data="menu:id"),
        ],
    ]
    if owner:
        rows.append([InlineKeyboardButton(f"👑 {sc('Owner Panel')}", callback_data="menu:owner")])
    return InlineKeyboardMarkup(rows)


def _md_safe(text: str) -> str:
    """Escape Markdown v1 special chars in user-supplied strings."""
    for ch in ("*", "_", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _welcome_text(first_name: str) -> str:
    name = _md_safe(first_name)
    return (
        f"👋 *{sc('Hello')}, {name}!*\n\n"
        f"{sc('I am your Group Management Bot.')}\n"
        f"{sc('Choose a category below to see available commands.')}"
    )


# ── /start ─────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # In a group just show a short notice
    if chat.type != "private":
        await update.message.reply_text(
            f"👋 {sc('Hi')} {user.first_name}! "
            f"{sc('DM me to see all available commands.')}",
        )
        return

    owner = is_owner(user.id)
    await update.message.reply_text(
        _welcome_text(user.first_name),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(owner),
    )


# ── Menu callbacks ─────────────────────────────────────────────────────────────

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user  = query.from_user
    key   = query.data.split(":")[1]   # e.g. "mod", "warn", "back"
    owner = is_owner(user.id)

    if key == "back":
        await query.edit_message_text(
            _welcome_text(user.first_name),
            parse_mode="Markdown",
            reply_markup=_main_keyboard(owner),
        )
        return

    # Owner-gate
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


# ── /ping ──────────────────────────────────────────────────────────────────────

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🏓 {sc('Pong!')}")


# ── /rules ─────────────────────────────────────────────────────────────────────

async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_cooldown(update.effective_user.id, "rules"):
        return await update.message.reply_text(
            sc("Please wait before using this command again.")
        )
    db = get_db()
    config = await db.group_configs.find_one({"group_id": update.effective_chat.id})
    if not config or not config.get("rules"):
        return await update.message.reply_text(sc("No rules set for this group."))
    await update.message.reply_text(
        f"📜 *{sc('Rules')}*\n\n{config['rules']}", parse_mode="Markdown"
    )


# ── /setrules ──────────────────────────────────────────────────────────────────

async def setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
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
    title = update.effective_chat.title or str(cid)
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {
            "$set": {
                "rules": rules_text,
                "title": title,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "group_id": cid,
                "warn_limit": 3,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    await log_action(context.bot, cid, uid, uid, "set rules")
    await update.message.reply_text(sc("Rules set successfully."))


# ── /setwelcome ────────────────────────────────────────────────────────────────

async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
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
    title = update.effective_chat.title or str(cid)
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {
            "$set": {
                "welcome_message": msg,
                "title": title,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "group_id": cid,
                "warn_limit": 3,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    await log_action(context.bot, cid, uid, uid, "set welcome message")
    await update.message.reply_text(sc("Welcome message set successfully."))


# ── /setgoodbye ────────────────────────────────────────────────────────────────

async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
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
    title = update.effective_chat.title or str(cid)
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {
            "$set": {
                "goodbye_message": msg,
                "title": title,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "group_id": cid,
                "warn_limit": 3,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    await log_action(context.bot, cid, uid, uid, "set goodbye message")
    await update.message.reply_text(sc("Goodbye message set successfully."))


# ── /setwarnlimit ──────────────────────────────────────────────────────────────

async def setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(
            sc("You need to be an admin to use this command.")
        )
    if not context.args:
        return await update.message.reply_text(sc("Usage: /setwarnlimit [number]"))
    try:
        limit = int(context.args[0])
        if limit < 1:
            raise ValueError
    except ValueError:
        return await update.message.reply_text(
            sc("Please provide a valid number (minimum 1).")
        )
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {
            "$set": {
                "warn_limit": limit,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "group_id": cid,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )
    await log_action(context.bot, cid, uid, uid, f"set warn limit to {limit}")
    await update.message.reply_text(sc(f"Warn limit set to {limit}."))


# ── Bot join / leave tracking ──────────────────────────────────────────────────

async def _register_group(bot, chat_id: int, title: str):
    """Upsert group into group_configs so /post can list it."""
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": chat_id},
        {
            "$set": {"title": title, "updated_at": datetime.now(timezone.utc)},
            "$setOnInsert": {
                "group_id": chat_id,
                "warn_limit": 3,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )


async def handle_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires when the BOT itself is added to / removed from a group."""
    result = update.my_chat_member
    if not result:
        return
    new_status = result.new_chat_member.status
    chat = result.chat

    if new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR):
        title = chat.title or str(chat.id)
        await _register_group(context.bot, chat.id, title)
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

    joined = old_status in (ChatMember.LEFT, ChatMember.BANNED) and \
        new_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    left = old_status in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER) and \
        new_status in (ChatMember.LEFT, ChatMember.BANNED)

    db = get_db()
    config = await db.group_configs.find_one({"group_id": result.chat.id})

    if result.chat.title:
        await _register_group(context.bot, result.chat.id, result.chat.title)

    def fmt(template: str, user) -> str:
        return template.format(
            user=f"@{user.username}" if user.username else user.first_name,
            first_name=user.first_name,
            last_name=user.last_name or "",
            username=f"@{user.username}" if user.username else "",
            group=result.chat.title,
        )

    try:
        if joined:
            user = result.new_chat_member.user
            msg = fmt(
                config.get("welcome_message", "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!")
                if config else "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!",
                user,
            )
            await context.bot.send_message(result.chat.id, msg)
            await log_action(context.bot, result.chat.id, user.id, 0, "joined the group")
        elif left:
            user = result.old_chat_member.user
            action = "was banned" if new_status == ChatMember.BANNED else "left the group"
            msg = fmt(
                config.get("goodbye_message", "ɢᴏᴏᴅʙʏᴇ, {user}!")
                if config else "ɢᴏᴏᴅʙʏᴇ, {user}!",
                user,
            )
            await context.bot.send_message(result.chat.id, msg)
            await log_action(context.bot, result.chat.id, user.id, 0, action)
    except Exception as e:
        print(f"Member update error: {e}")


# ── Registration ───────────────────────────────────────────────────────────────

def register(app: Application):
    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("ping",         ping))
    app.add_handler(CommandHandler("rules",        rules))
    app.add_handler(CommandHandler("setrules",     setrules))
    app.add_handler(CommandHandler("setwelcome",   setwelcome))
    app.add_handler(CommandHandler("setgoodbye",   setgoodbye))
    app.add_handler(CommandHandler("setwarnlimit", setwarnlimit))
    # Inline menu callbacks (pattern: "menu:<key>")
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:"))
    app.add_handler(
        ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    app.add_handler(
        ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER)
    )
