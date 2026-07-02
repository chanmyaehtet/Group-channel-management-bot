# BUG-11: This file is DEAD CODE — it is never imported or registered in main.py.
# The commands defined here (lock, unlock, pin, unpin, promote, demote) are fully
# handled by bot/handlers/controls.py which IS registered.
# This file is kept for reference only. Do NOT register it — it would cause duplicate
# command conflicts with controls.py.
from telegram import Update, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from bot.utils import sc, is_admin, is_owner, bot_is_admin, check_cooldown, resolve_target
from bot.middleware import blacklist_check
from database.models import update_group_setting, add_log

def _guard(func):
    async def wrapper(update: Update, ctx):
        if await blacklist_check(update, ctx): return
        if update.effective_chat.type == "private":
            return await update.message.reply_text(sc("Use this command in a group."))
        if not check_cooldown(update.effective_user.id, func.__name__): return
        uid, cid = update.effective_user.id, update.effective_chat.id
        if not await is_admin(ctx.bot, cid, uid) and not is_owner(uid):
            return await update.message.reply_text(sc("Admins only."))
        return await func(update, ctx)
    wrapper.__name__ = func.__name__
    return wrapper

@_guard
async def lock(update: Update, ctx):
    cid = update.effective_chat.id
    if not await bot_is_admin(ctx.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    try:
        await ctx.bot.set_chat_permissions(cid, ChatPermissions(can_send_messages=False))
        await update_group_setting(cid, "locked", True)
        await add_log(cid, 0, update.effective_user.id, "lock")
        await update.message.reply_text(f"🔒 {sc('Chat locked. Only admins can send messages.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def unlock(update: Update, ctx):
    cid = update.effective_chat.id
    if not await bot_is_admin(ctx.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    try:
        await ctx.bot.set_chat_permissions(cid, ChatPermissions(
            can_send_messages=True, can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True, can_invite_users=True))
        await update_group_setting(cid, "locked", False)
        await add_log(cid, 0, update.effective_user.id, "unlock")
        await update.message.reply_text(f"🔓 {sc('Chat unlocked.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def pin(update: Update, ctx):
    if not update.message.reply_to_message:
        return await update.message.reply_text(sc("Reply to a message to pin it."))
    if not await bot_is_admin(ctx.bot, update.effective_chat.id):
        return await update.message.reply_text(sc("I need admin rights."))
    try:
        await ctx.bot.pin_chat_message(update.effective_chat.id,
                                        update.message.reply_to_message.message_id, disable_notification=False)
        await update.message.reply_text(f"📌 {sc('Message pinned.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def unpin(update: Update, ctx):
    if not await bot_is_admin(ctx.bot, update.effective_chat.id):
        return await update.message.reply_text(sc("I need admin rights."))
    try:
        await ctx.bot.unpin_chat_message(update.effective_chat.id)
        await update.message.reply_text(f"📌 {sc('Message unpinned.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def promote(update: Update, ctx):
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    if not await bot_is_admin(ctx.bot, update.effective_chat.id):
        return await update.message.reply_text(sc("I need admin rights."))
    try:
        await ctx.bot.promote_chat_member(update.effective_chat.id, tid,
            can_delete_messages=True, can_restrict_members=True,
            can_pin_messages=True, can_manage_chat=True)
        await add_log(update.effective_chat.id, tid, update.effective_user.id, "promote")
        await update.message.reply_text(f"⬆️ {sc('User promoted to admin.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

@_guard
async def demote(update: Update, ctx):
    tid, _ = await resolve_target(update, ctx)
    if not tid: return await update.message.reply_text(sc("Reply or provide user ID."))
    if not await bot_is_admin(ctx.bot, update.effective_chat.id):
        return await update.message.reply_text(sc("I need admin rights."))
    try:
        await ctx.bot.promote_chat_member(update.effective_chat.id, tid,
            can_delete_messages=False, can_restrict_members=False,
            can_pin_messages=False, can_manage_chat=False)
        await add_log(update.effective_chat.id, tid, update.effective_user.id, "demote")
        await update.message.reply_text(f"⬇️ {sc('User demoted.')}")
    except TelegramError as e: await update.message.reply_text(f"❌ {e.message}")

def register(app: Application):
    for cmd, func in [("lock", lock), ("unlock", unlock), ("pin", pin),
                      ("unpin", unpin), ("promote", promote), ("demote", demote)]:
        app.add_handler(CommandHandler(cmd, func))
