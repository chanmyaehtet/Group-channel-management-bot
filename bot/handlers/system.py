from datetime import datetime, timezone
from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import Application, CommandHandler, ChatMemberHandler, ContextTypes

from bot.utils import sc, is_admin, is_owner, check_cooldown, log_action
from database.connection import get_db


async def _register_group(bot, chat_id: int, title: str):
    """Upsert group into group_configs with its title so /post can list it."""
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ")


async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ᴘᴏɴɢ! 🏓")


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_cooldown(update.effective_user.id, "rules"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    db = get_db()
    config = await db.group_configs.find_one({"group_id": update.effective_chat.id})
    if not config or not config.get("rules"):
        return await update.message.reply_text(sc("No rules set for this group."))
    await update.message.reply_text(
        f"📜 *{sc('Rules')}*\n\n{config['rules']}", parse_mode="Markdown"
    )


async def setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "setrules"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
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


async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "setwelcome"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
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


async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("You need to be an admin to use this command."))
    if not check_cooldown(uid, "setgoodbye"):
        return await update.message.reply_text(sc("Please wait before using this command again."))
    if not context.args:
        return await update.message.reply_text(sc("Usage: /setgoodbye your message here"))
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


async def setwarnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        {
            "$set": {
                "warn_limit": limit,
                "updated_at": datetime.now(timezone.utc),
            },
            "$setOnInsert": {"group_id": cid, "created_at": datetime.now(timezone.utc)},
        },
        upsert=True,
    )
    await log_action(context.bot, cid, uid, uid, f"set warn limit to {limit}")
    await update.message.reply_text(sc(f"Warn limit set to {limit}."))


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

    # Also keep group title up-to-date
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


def register(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("setrules", setrules))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye))
    app.add_handler(CommandHandler("setwarnlimit", setwarnlimit))
    app.add_handler(ChatMemberHandler(handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))
