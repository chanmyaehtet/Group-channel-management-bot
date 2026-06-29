from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message, ChatMemberUpdated

from bot.client import bot
from bot.utils import is_admin, is_owner, check_cooldown, log_action
from database.connection import get_db

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)

START_TEXT = "ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ"


@bot.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    await message.reply(START_TEXT)


@bot.on_message(filters.command("ping"))
async def ping(client: Client, message: Message):
    await message.reply("ᴘᴏɴɢ! 🏓")


@bot.on_message(filters.command("rules") & filters.group)
async def rules(client: Client, message: Message):
    if not await check_cooldown(message.from_user.id, "rules"):
        return await message.reply(sc("Please wait before using this command again."))
    db = get_db()
    config = await db.group_configs.find_one({"group_id": message.chat.id})
    if not config or not config.get("rules"):
        return await message.reply(sc("No rules set for this group."))
    await message.reply(f"📜 **{sc('Rules')}**\n\n{config['rules']}")


@bot.on_message(filters.command("setrules") & filters.group)
async def set_rules(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "setrules"):
        return await message.reply(sc("Please wait before using this command again."))
    if len(message.command) < 2:
        return await message.reply(sc("Please provide the rules text."))

    rules_text = " ".join(message.command[1:])
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": message.chat.id},
        {"$set": {"rules": rules_text, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": message.chat.id, "warn_limit": 3, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(client, message.chat.id, message.from_user.id, message.from_user.id, "set rules")
    await message.reply(sc("Rules set successfully."))


@bot.on_message(filters.command("setwelcome") & filters.group)
async def set_welcome(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "setwelcome"):
        return await message.reply(sc("Please wait before using this command again."))
    if len(message.command) < 2:
        return await message.reply(
            sc("Please provide a welcome message. Placeholders:") +
            "\n{user} {first_name} {last_name} {username} {group}"
        )

    welcome = " ".join(message.command[1:])
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": message.chat.id},
        {"$set": {"welcome_message": welcome, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": message.chat.id, "warn_limit": 3, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(client, message.chat.id, message.from_user.id, message.from_user.id, "set welcome message")
    await message.reply(sc("Welcome message set successfully."))


@bot.on_message(filters.command("setgoodbye") & filters.group)
async def set_goodbye(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "setgoodbye"):
        return await message.reply(sc("Please wait before using this command again."))
    if len(message.command) < 2:
        return await message.reply(
            sc("Please provide a goodbye message. Placeholders:") +
            "\n{user} {first_name} {last_name} {username} {group}"
        )

    goodbye = " ".join(message.command[1:])
    db = get_db()
    await db.group_configs.update_one(
        {"group_id": message.chat.id},
        {"$set": {"goodbye_message": goodbye, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": message.chat.id, "warn_limit": 3, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(client, message.chat.id, message.from_user.id, message.from_user.id, "set goodbye message")
    await message.reply(sc("Goodbye message set successfully."))


@bot.on_message(filters.command("setwarnlimit") & filters.group)
async def set_warn_limit(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "setwarnlimit"):
        return await message.reply(sc("Please wait before using this command again."))
    if len(message.command) < 2:
        return await message.reply(sc("Usage: /setwarnlimit [number]"))

    try:
        limit = int(message.command[1])
        if limit < 1:
            raise ValueError
    except ValueError:
        return await message.reply(sc("Please provide a valid number (minimum 1)."))

    db = get_db()
    await db.group_configs.update_one(
        {"group_id": message.chat.id},
        {"$set": {"warn_limit": limit, "updated_at": datetime.now(timezone.utc)},
         "$setOnInsert": {"group_id": message.chat.id, "created_at": datetime.now(timezone.utc)}},
        upsert=True
    )
    await log_action(client, message.chat.id, message.from_user.id, message.from_user.id, f"set warn limit to {limit}")
    await message.reply(sc(f"Warn limit set to {limit}."))


@bot.on_chat_member_updated()
async def handle_member_update(client: Client, chat_member: ChatMemberUpdated):
    if not chat_member.chat.type.name.upper().startswith(("SUPER", "GROUP")):
        return

    old = chat_member.old_chat_member.status if chat_member.old_chat_member else None
    new = chat_member.new_chat_member.status if chat_member.new_chat_member else None

    joined = (old in (None, ChatMemberStatus.LEFT, ChatMemberStatus.BANNED)) and \
              (new in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER))
    left = (old in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)) and \
           (new in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED))

    db = get_db()
    config = await db.group_configs.find_one({"group_id": chat_member.chat.id})

    def fmt(template, user):
        return template.format(
            user=user.mention,
            first_name=user.first_name,
            last_name=user.last_name or "",
            username=f"@{user.username}" if user.username else "",
            group=chat_member.chat.title,
        )

    try:
        if joined:
            user = chat_member.new_chat_member.user
            msg = fmt(
                (config.get("welcome_message") if config and config.get("welcome_message")
                 else "ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴛʜᴇ ɢʀᴏᴜᴘ, {user}!"),
                user
            )
            await client.send_message(chat_member.chat.id, msg)
            await log_action(client, chat_member.chat.id, user.id, 0, "joined the group")

        elif left:
            user = chat_member.old_chat_member.user
            action = "was banned" if new == ChatMemberStatus.BANNED else "left the group"
            msg = fmt(
                (config.get("goodbye_message") if config and config.get("goodbye_message")
                 else "ɢᴏᴏᴅʙʏᴇ, {user}!"),
                user
            )
            await client.send_message(chat_member.chat.id, msg)
            await log_action(client, chat_member.chat.id, user.id, 0, action)
    except Exception as e:
        print(f"Member update error: {e}")
