from datetime import datetime, timezone
from telegram import Update, ChatMember, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes

from bot.utils import sc, is_admin, is_owner, check_cooldown, log_action
from database.connection import get_db


def _group_only_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            sc("Add me to a group") + " ➕",
            url=f"https://t.me/{bot_username}?startgroup=true"
        )
    ]])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = sc(user.first_name or "Admin")
    bot_username = context.bot.username

    text = (
        f"👋 *{sc('Hello')}, {name}!*\n"
        f"{sc('I am a Group Management Bot — add me to your group and make me admin.')}\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🛡️ *{sc('Moderation')}*\n"
        f"`/kick` — {sc('Kick a user')}\n"
        f"`/ban` — {sc('Ban a user')}\n"
        f"`/unban` — {sc('Unban a user')}\n"
        f"`/mute [sec]` — {sc('Mute a user')}\n"
        f"`/unmute` — {sc('Unmute a user')}\n\n"
        f"⚠️ *{sc('Warnings')}*\n"
        f"`/warn [reason]` — {sc('Warn a user')}\n"
        f"`/unwarn` — {sc('Remove last warning')}\n"
        f"`/warnings` — {sc('Show warning list')}\n"
        f"`/setwarnlimit [n]` — {sc('Set auto-ban limit')}\n\n"
        f"🔒 *{sc('Group Controls')}* _{sc('admin only')}_\n"
        f"`/lock` — {sc('Lock chat (mute all members)')}\n"
        f"`/unlock` — {sc('Unlock chat')}\n"
        f"`/pin` — {sc('Pin replied message')}\n"
        f"`/unpin` — {sc('Unpin message')}\n"
        f"`/promote` — {sc('Promote user to admin')}\n"
        f"`/demote` — {sc('Demote user from admin')}\n"
        f"`/purge [n]` — {sc('Delete last N messages')}\n"
        f"`/info` — {sc('Get user information')}\n"
        f"`/report` — {sc('Report user to admins')}\n\n"
        f"⚙️ *{sc('Group Settings')}* _{sc('admin only')}_\n"
        f"`/setwelcome` — {sc('Set welcome message')}\n"
        f"`/setgoodbye` — {sc('Set goodbye message')}\n"
        f"`/setrules` — {sc('Set group rules')}\n"
        f"`/rules` — {sc('Show group rules')}\n\n"
        f"📤 *{sc('Post to Group from PM')}*\n"
        f"`/post <text>` — {sc('Send a message to your group via PM')}\n\n"
        f"📡 *{sc('Broadcast')}* _{sc('owner only')}_\n"
        f"`/broadcast all <text>`\n"
        f"`/broadcast <group_id> <text>`\n\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🏓 `/ping` — {sc('Check bot status')}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                sc("Add me to group") + " ➕",
                url=f"https://t.me/{bot_username}?startgroup=true"
            ),
            InlineKeyboardButton(
                sc("Share bot") + " 📤",
                url=f"https://t.me/share/url?url=https://t.me/{bot_username}&text=Great+group+management+bot!"
            ),
        ]
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(sc("Pong!") + " 🏓")


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("Use this command in your group."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    if not check_cooldown(update.effective_user.id, "rules"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    db = get_db()
    config = await db.group_configs.find_one({"group_id": update.effective_chat.id})
    if not config or not config.get("rules"):
        return await update.message.reply_text(sc("No rules set for this group."))
    await update.message.reply_text(f"📜 *{sc('Rules')}*\n\n{config['rules']}", parse_mode="Markdown")


async def setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("Use this command in your group."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "setrules"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not context.args:
        return await update.message.reply_text(sc("Please provide the rules text."))
    rules_text = " ".join(context.args)
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {"$set": {"rules": rules_text, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": cid, "warn_limit": 3, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(context.bot, cid, uid, uid, "set rules")
    await update.message.reply_text(sc("Rules set successfully."))


async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("Use this command in your group."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "setwelcome"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not context.args:
        return await update.message.reply_text(
            sc("Usage: /setwelcome your message here\n"
               "Placeholders: {user} {first_name} {last_name} {username} {group}")
        )
    msg = " ".join(context.args)
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {"$set": {"welcome_message": msg, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": cid, "warn_limit": 3, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(context.bot, cid, uid, uid, "set welcome message")
    await update.message.reply_text(sc("Welcome message set successfully."))


async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("Use this command in your group."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "setgoodbye"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not context.args:
        return await update.message.reply_text(sc("Usage: /setgoodbye your message here"))
    msg = " ".join(context.args)
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {"$set": {"goodbye_message": msg, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": cid, "warn_limit": 3, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(context.bot, cid, uid, uid, "set goodbye message")
    await update.message.reply_text(sc("Goodbye message set successfully."))


async def setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return await update.message.reply_text(
            sc("Use this command in your group."),
            reply_markup=_group_only_keyboard(context.bot.username)
        )
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not context.args:
        return await update.message.reply_text(sc("Usage: /setwarnlimit [number]"))
    try:
        limit = int(context.args[0])
        if limit < 1:
            raise ValueError
    except ValueError:
        return await update.message.reply_text(sc("Please provide a valid number (minimum 1)."))
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": cid},
        {"$set": {"warn_limit": limit, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": cid, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(context.bot, cid, uid, uid, f"set warn limit to {limit}")
    await update.message.reply_text(sc(f"Warn limit set to {limit}."))


async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                config.get("welcome_message", "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!") if config else
                "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!",
                user
            )
            await context.bot.send_message(result.chat.id, msg)
            await log_action(context.bot, result.chat.id, user.id, 0, "joined the group")
        elif left:
            user = result.old_chat_member.user
            action = "was banned" if new_status == ChatMember.BANNED else "left the group"
            msg = fmt(
                config.get("goodbye_message", "ɢᴏᴏᴅʙʏᴇ, {user}!") if config else
                "ɢᴏᴏᴅʙʏᴇ, {user}!",
                user
            )
            await context.bot.send_message(result.chat.id, msg)
            await log_action(context.bot, result.chat.id, user.id, 0, action)
    except Exception as e:
        print(f"Member update error: {e}")


def register(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("setrules", setrules))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye))
    app.add_handler(CommandHandler("setwarnlimit", setwarnlimit))
    app.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))
