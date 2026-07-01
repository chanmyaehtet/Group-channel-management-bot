"""Blacklist middleware — checked before every command/message."""
from telegram import Update
from telegram.ext import ContextTypes
from database.models import is_blocked

async def blacklist_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Returns True if request should be ignored (blocked)."""
    uid = update.effective_user.id if update.effective_user else None
    cid = update.effective_chat.id if update.effective_chat else None
    if uid and await is_blocked("user", uid): return True
    if cid and cid < 0 and await is_blocked("group", cid): return True
    return False
