import os, time
from telegram import Bot, ChatMember
from telegram.ext import ContextTypes
from telegram import Update

OWNER_IDS = [int(x.strip()) for x in os.getenv("OWNER_IDS","").split(",") if x.strip().isdigit()]

SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
)
def sc(text: str) -> str: return text.translate(SC)

def md_escape(text: str) -> str:
    """Escape Markdown v1 special characters in user-supplied strings.
    Prevents parse_entities errors when names contain *, _, `, [ characters."""
    if not text:
        return ""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text

def is_owner(user_id: int) -> bool: return user_id in OWNER_IDS

async def is_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except: return False

async def bot_is_admin(bot: Bot, chat_id: int) -> bool:
    try:
        me = await bot.get_me()
        m = await bot.get_chat_member(chat_id, me.id)
        return m.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    except: return False

_cooldowns: dict = {}
def check_cooldown(user_id: int, cmd: str, secs: float = 2.0) -> bool:
    key = f"{user_id}_{cmd}"; now = time.time()
    if key in _cooldowns and now - _cooldowns[key] < secs: return False
    _cooldowns[key] = now; return True

async def resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns (user_id, user_obj_or_None). Checks reply, then args."""
    msg = update.message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        return u.id, u
    if context.args:
        raw = context.args[0]
        try: return int(raw), None
        except ValueError:
            try:
                lookup = raw if raw.startswith("@") else f"@{raw}"
                u = await context.bot.get_chat(lookup)
                return u.id, u
            except: pass
    return None, None

async def get_target_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns user_id only (or None). Used by controls.py handlers."""
    msg = update.message
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user.id
    if context.args:
        raw = context.args[0]
        try: return int(raw)
        except ValueError:
            try:
                lookup = raw if raw.startswith("@") else f"@{raw}"
                u = await context.bot.get_chat(lookup)
                return u.id
            except: pass
    return None

async def log_action(bot: Bot, chat_id: int, user_id: int, admin_id: int, action: str) -> None:
    """Write a moderation action to the audit log."""
    try:
        from database.models import add_log
        await add_log(chat_id, user_id, admin_id, action)
    except Exception as e:
        print(f"log_action error: {e}")

def fmt_user(user) -> str:
    if user is None: return sc("Unknown")
    name = user.first_name or ""
    if user.username: return f"@{user.username}"
    return sc(name)
