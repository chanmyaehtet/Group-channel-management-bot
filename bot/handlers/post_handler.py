"""Allow admins to post a message to their group from PM."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from bot.utils import sc, is_owner
from bot.middleware import blacklist_check
from database.models import get_all_groups

async def post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx): return
    if update.effective_chat.type != "private":
        return await update.message.reply_text(sc("Use /post in PM with the bot."))
    if not ctx.args:
        return await update.message.reply_text(
            f"*{sc('Usage')}:* `/post <your message>`\n"
            f"_{sc('Then select which group to send it to.')}_",
            parse_mode="Markdown")
    text = " ".join(ctx.args)
    ctx.user_data["post_text"] = text
    groups = await get_all_groups()
    if not groups:
        return await update.message.reply_text(sc("No groups found. Add me to a group first."))
    buttons = []
    for g in groups[:20]:
        title = g.get("title") or str(g["group_id"])
        buttons.append([InlineKeyboardButton(
            sc(title[:40]), callback_data=f"post_{g['group_id']}")])
    buttons.append([InlineKeyboardButton("❌ " + sc("Cancel"), callback_data="post_cancel")])
    await update.message.reply_text(
        f"📤 *{sc('Select group to post to')}:*\n\n`{text}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons))

async def post_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "post_cancel":
        ctx.user_data.pop("post_text", None)
        return await query.edit_message_text(sc("Cancelled."))
    gid = int(query.data.replace("post_", ""))
    text = ctx.user_data.get("post_text", "")
    if not text:
        return await query.edit_message_text(sc("No message text found. Use /post again."))
    try:
        await ctx.bot.send_message(gid, text)
        await query.edit_message_text(f"✅ {sc('Message sent to group')} `{gid}`", parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"❌ {e}")
    ctx.user_data.pop("post_text", None)

def register(app: Application):
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CallbackQueryHandler(post_callback, pattern=r"^post_"))
