"""Anti-spam middleware: link filter, flood filter, duplicate detection."""
import re
from datetime import datetime, timezone, timedelta
from telegram import Update, Message, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
from bot.utils import sc, is_admin, is_owner, bot_is_admin
from bot.middleware import blacklist_check
from database.models import update_group_setting, get_group, track_message

URL_RE = re.compile(r'(https?://|t\.me/|tg://|@\w{5,})', re.IGNORECASE)
FLOOD_THRESHOLD = 5  # same message N times in 10s = flood


async def _antispam_middleware(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.type == "private":
        return
    if await blacklist_check(update, ctx):
        return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if is_owner(uid) or await is_admin(ctx.bot, cid, uid):
        return
    if not await bot_is_admin(ctx.bot, cid):
        return

    g = await get_group(cid)
    s = g.get("settings", {})
    if not s.get("antispam_enabled", False):
        return

    msg: Message = update.message
    text = msg.text or msg.caption or ""

    # Link / invite filter
    if s.get("antispam_links", False) and URL_RE.search(text):
        try:
            await msg.delete()
            name = update.effective_user.username or update.effective_user.first_name
            await ctx.bot.send_message(cid, f"🚫 {sc('Link removed')} — @{name}")
        except TelegramError:
            pass
        return

    # Flood filter
    if s.get("antispam_flood", False) and text:
        count = await track_message(cid, uid, text)
        if count >= FLOOD_THRESHOLD:
            try:
                await msg.delete()
                until = datetime.now(timezone.utc) + timedelta(minutes=5)
                await ctx.bot.restrict_chat_member(
                    cid, uid,
                    ChatPermissions(can_send_messages=False),
                    until_date=until,
                )
                name = update.effective_user.username or update.effective_user.first_name
                await ctx.bot.send_message(
                    cid,
                    f"⏱️ {sc('Flood detected — muted for 5 minutes')}: @{name}",
                )
            except TelegramError:
                pass


async def antispam_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx):
        return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    val = (ctx.args[0] if ctx.args else "").lower() == "on"
    await update_group_setting(cid, "antispam_enabled", val)
    state = "ᴏɴ" if val else "ᴏꜰꜰ"
    await update.message.reply_text(
        f"🛡️ {sc('Anti-spam')}: *{state}*", parse_mode="Markdown"
    )


async def antispam_links_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx):
        return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    val = (ctx.args[0] if ctx.args else "").lower() == "on"
    await update_group_setting(cid, "antispam_links", val)
    state = "ᴏɴ" if val else "ᴏꜰꜰ"
    await update.message.reply_text(
        f"🔗 {sc('Link filter')}: *{state}*", parse_mode="Markdown"
    )


async def antispam_flood_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx):
        return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    val = (ctx.args[0] if ctx.args else "").lower() == "on"
    await update_group_setting(cid, "antispam_flood", val)
    state = "ᴏɴ" if val else "ᴏꜰꜰ"
    await update.message.reply_text(
        f"🌊 {sc('Flood filter')}: *{state}*", parse_mode="Markdown"
    )


def register(app: Application):
    app.add_handler(CommandHandler("antispam",       antispam_toggle))
    app.add_handler(CommandHandler("antispam_links", antispam_links_toggle))
    app.add_handler(CommandHandler("antispam_flood", antispam_flood_toggle))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
        _antispam_middleware,
    ), group=1)
