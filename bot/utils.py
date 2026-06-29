import os
import time
from datetime import datetime, timezone
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import Message
from database.connection import get_db

OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "0").split(",") if x.strip()]

# Cooldown store: {user_id_command: timestamp}
_cooldowns: dict = {}
COOLDOWN_SECONDS = 2

async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def is_owner(message: Message) -> bool:
    return message.from_user.id in OWNER_IDS

async def bot_is_admin(client: Client, chat_id: int) -> bool:
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def check_cooldown(user_id: int, command: str) -> bool:
    key = f"{user_id}_{command}"
    now = time.time()
    if key in _cooldowns and now - _cooldowns[key] < COOLDOWN_SECONDS:
        return False
    _cooldowns[key] = now
    return True

async def get_target_user(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    if len(message.command) > 1:
        target = message.command[1]
        try:
            user = await client.get_users(target)
            return user.id
        except Exception:
            return None
    return None

async def log_action(client: Client, group_id: int, user_id: int, admin_id: int, action: str):
    db = get_db()
    doc = {
        "group_id": group_id,
        "user_id": user_id,
        "admin_id": admin_id,
        "action": action,
        "created_at": datetime.now(timezone.utc),
    }
    await db.moderation_logs.insert_one(doc)

    # Notify owner
    for owner_id in OWNER_IDS:
        try:
            await client.send_message(
                owner_id,
                f"📋 **Log** | Group: `{group_id}`\n"
                f"User: `{user_id}` | Admin: `{admin_id}`\n"
                f"Action: **{action}**"
            )
        except Exception:
            pass
