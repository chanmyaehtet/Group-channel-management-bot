import os
import time
from datetime import datetime, timezone
from telegram import Update, Bot, ChatMember
from telegram.ext import ContextTypes
from database.connection import get_db

OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS", "0").split(",") if x.strip().isdigit()]
_cooldowns: dict = {}
COOLDOWN_SECONDS = 2

SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)

def sc(text: str) -> str:
    return text.translate(SC)

def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS

async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False

async def bot_is_admin(bot: Bot, chat_id: int) -> bool:
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat_id, me.id)
        return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except Exception:
        return False

def check_cooldown(user_id: int, command: str) -> bool:
    key = f"{user_id}_{command}"
    now = time.time()
    if key in _cooldowns and now - _cooldowns[key] < COOLDOWN_SECONDS:
        return False
    _cooldowns[key] = now
    return True

async def get_target_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user.id
    if context.args:
        target = context.args[0]
        try:
            return int(target)
        except ValueError:
            try:
                user = await context.bot.get_chat(target)
                return user.id
            except Exception:
                return None
    return None

async def log_action(bot: Bot, group_id: int, user_id: int, admin_id: int, action: str):
    db = get_db()
    await db.moderation_logs.insert_one({
        "group_id": group_id,
        "user_id": user_id,
        "admin_id": admin_id,
        "action": action,
        "created_at": datetime.now(timezone.utc),
    })
    for owner_id in OWNER_IDS:
        try:
            await bot.send_message(
                owner_id,
                f"📋 **Log** | Group: `{group_id}`\n"
                f"User: `{user_id}` | Admin: `{admin_id}`\n"
                f"Action: **{action}**",
                parse_mode="Markdown"
            )
        except Exception:
            pass
