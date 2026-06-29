import asyncio
from datetime import datetime, timezone
from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from pyrogram.errors import UserAdminInvalid, ChatAdminRequired, FloodWait

from bot.client import bot
from bot.utils import is_admin, is_owner, bot_is_admin, check_cooldown, get_target_user, log_action
from database.connection import get_db

SMALL_CAPS = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def sc(text: str) -> str:
    return text.translate(SMALL_CAPS)


@bot.on_message(filters.command("kick") & filters.group)
async def kick(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "kick"):
        return await message.reply(sc("Please wait before using this command again."))
    if not await bot_is_admin(client, message.chat.id):
        return await message.reply(sc("I need admin rights."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    try:
        target = await client.get_chat_member(message.chat.id, user_id)
        if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply(sc("Cannot kick an admin."))
        await client.ban_chat_member(message.chat.id, user_id)
        await client.unban_chat_member(message.chat.id, user_id)
        await log_action(client, message.chat.id, user_id, message.from_user.id, "kick")
        await message.reply(sc("User kicked."))
    except (UserAdminInvalid, ChatAdminRequired):
        await message.reply(sc("I need admin rights to perform this action."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("ban") & filters.group)
async def ban(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "ban"):
        return await message.reply(sc("Please wait before using this command again."))
    if not await bot_is_admin(client, message.chat.id):
        return await message.reply(sc("I need admin rights."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    try:
        target = await client.get_chat_member(message.chat.id, user_id)
        if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply(sc("Cannot ban an admin."))
        await client.ban_chat_member(message.chat.id, user_id)
        if message.reply_to_message:
            await message.reply_to_message.delete()
        await log_action(client, message.chat.id, user_id, message.from_user.id, "ban")
        await message.reply(sc("User banned."))
    except (UserAdminInvalid, ChatAdminRequired):
        await message.reply(sc("I need admin rights to perform this action."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("unban") & filters.group)
async def unban(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "unban"):
        return await message.reply(sc("Please wait before using this command again."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    try:
        await client.unban_chat_member(message.chat.id, user_id)
        await log_action(client, message.chat.id, user_id, message.from_user.id, "unban")
        await message.reply(sc("User unbanned."))
    except (UserAdminInvalid, ChatAdminRequired):
        await message.reply(sc("I need admin rights to perform this action."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("mute") & filters.group)
async def mute(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "mute"):
        return await message.reply(sc("Please wait before using this command again."))
    if not await bot_is_admin(client, message.chat.id):
        return await message.reply(sc("I need admin rights."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    duration = None
    cmd = message.command
    offset = 2 if len(cmd) > 1 and not cmd[1].startswith("@") else 1
    if len(cmd) > offset:
        try:
            duration = int(cmd[offset])
        except ValueError:
            pass

    try:
        target = await client.get_chat_member(message.chat.id, user_id)
        if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply(sc("Cannot mute an admin."))

        from pyrogram.types import ChatPermissions
        until = None
        if duration:
            from datetime import timedelta
            until = datetime.now(timezone.utc) + timedelta(seconds=duration)

        await client.restrict_chat_member(
            message.chat.id, user_id,
            ChatPermissions(can_send_messages=False),
            until_date=until
        )
        dur_text = f" {sc('for')} {duration}s" if duration else ""
        await log_action(client, message.chat.id, user_id, message.from_user.id, f"mute{dur_text}")
        await message.reply(sc(f"User muted{dur_text}."))
    except (UserAdminInvalid, ChatAdminRequired):
        await message.reply(sc("I need admin rights to perform this action."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("unmute") & filters.group)
async def unmute(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "unmute"):
        return await message.reply(sc("Please wait before using this command again."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    try:
        from pyrogram.types import ChatPermissions
        await client.restrict_chat_member(
            message.chat.id, user_id,
            ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        )
        await log_action(client, message.chat.id, user_id, message.from_user.id, "unmute")
        await message.reply(sc("User unmuted."))
    except (UserAdminInvalid, ChatAdminRequired):
        await message.reply(sc("I need admin rights to perform this action."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("warn") & filters.group)
async def warn(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "warn"):
        return await message.reply(sc("Please wait before using this command again."))
    if not await bot_is_admin(client, message.chat.id):
        return await message.reply(sc("I need admin rights."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    reason = None
    if len(message.command) > 2:
        reason = " ".join(message.command[2:])

    try:
        target = await client.get_chat_member(message.chat.id, user_id)
        if target.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return await message.reply(sc("Cannot warn an admin."))

        db = get_db()
        # Get warn limit from group config
        config = await db.group_configs.find_one({"group_id": message.chat.id})
        warn_limit = config.get("warn_limit", 3) if config else 3

        # Add warning
        await db.warnings.insert_one({
            "group_id": message.chat.id,
            "user_id": user_id,
            "admin_id": message.from_user.id,
            "reason": reason,
            "created_at": datetime.now(timezone.utc),
        })

        # Count warnings
        count = await db.warnings.count_documents({"group_id": message.chat.id, "user_id": user_id})
        await log_action(client, message.chat.id, user_id, message.from_user.id,
                         f"warn ({count}/{warn_limit})" + (f": {reason}" if reason else ""))

        if count >= warn_limit:
            await client.ban_chat_member(message.chat.id, user_id)
            await log_action(client, message.chat.id, user_id, message.from_user.id,
                             f"auto-ban after {count} warnings")
            return await message.reply(
                sc(f"User has reached {count}/{warn_limit} warnings and has been banned.")
            )

        await message.reply(
            sc(f"User warned ({count}/{warn_limit}).") + (f" {sc('Reason')}: {reason}" if reason else "")
        )
    except (UserAdminInvalid, ChatAdminRequired):
        await message.reply(sc("I need admin rights to perform this action."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("unwarn") & filters.group)
async def unwarn(client: Client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id) and not await is_owner(message):
        return await message.reply(sc("You need to be an admin to use this command."))
    if not await check_cooldown(message.from_user.id, "unwarn"):
        return await message.reply(sc("Please wait before using this command again."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    try:
        db = get_db()
        latest = await db.warnings.find_one(
            {"group_id": message.chat.id, "user_id": user_id},
            sort=[("created_at", -1)]
        )
        if not latest:
            return await message.reply(sc("This user has no warnings to remove."))

        await db.warnings.delete_one({"_id": latest["_id"]})
        count = await db.warnings.count_documents({"group_id": message.chat.id, "user_id": user_id})
        await log_action(client, message.chat.id, user_id, message.from_user.id,
                         f"unwarn (remaining: {count})")
        await message.reply(sc(f"Warning removed. User now has {count} warnings."))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")


@bot.on_message(filters.command("warnings") & filters.group)
async def warnings_cmd(client: Client, message: Message):
    if not await check_cooldown(message.from_user.id, "warnings"):
        return await message.reply(sc("Please wait before using this command again."))

    user_id = await get_target_user(client, message)
    if not user_id:
        return await message.reply(sc("Please reply to a message or provide a username."))

    try:
        db = get_db()
        config = await db.group_configs.find_one({"group_id": message.chat.id})
        warn_limit = config.get("warn_limit", 3) if config else 3

        cursor = db.warnings.find(
            {"group_id": message.chat.id, "user_id": user_id}
        ).sort("created_at", -1)
        all_warns = await cursor.to_list(length=None)

        if not all_warns:
            return await message.reply(sc("This user has no warnings."))

        user = await client.get_users(user_id)
        text = f"**{sc('Warnings for')} {user.first_name}** ({len(all_warns)}/{warn_limit}):\n\n"
        for i, w in enumerate(all_warns, 1):
            admin = await client.get_users(w["admin_id"])
            t = w["created_at"].strftime("%Y-%m-%d %H:%M")
            r = f": {w['reason']}" if w.get("reason") else ""
            text += f"{i}. {sc('By')} {admin.first_name} {sc('on')} {t}{r}\n"

        await message.reply(text)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await message.reply(f"{sc('Error')}: {e}")
