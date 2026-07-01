from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest, TelegramError

from bot.utils import sc
from database.models import get_all_groups

# ── States ──────────────────────────────────────────────────────────────────
(
    WAITING_TEXT,
    CONFIRM_TEXT,
    CHOOSE_BTN,
    BTN1_NAME,
    BTN1_URL,
    CHOOSE_BTN2,
    BTN2_NAME,
    BTN2_URL,
    SELECT_GROUP,
) = range(9)


# ── Helpers ──────────────────────────────────────────────────────────────────
def _url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if not raw.startswith(("http://", "https://")):
        return f"https://{raw}"
    return raw


async def _show_group_select(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, is_query: bool
) -> int:
    groups = await get_all_groups()
    if not groups:
        msg = "❌ " + sc("No groups found. Add me to a group first.")
        if is_query:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        context.user_data.clear()
        return ConversationHandler.END

    buttons = []
    for g in groups:
        gid = g["group_id"]
        title = sc((g.get("title") or str(gid))[:30])
        buttons.append([InlineKeyboardButton(title, callback_data=f"ptg:grp:{gid}")])

    buttons.append([InlineKeyboardButton("❌ " + sc("Cancel"), callback_data="ptg:cancel_send")])
    keyboard = InlineKeyboardMarkup(buttons)
    text = f"📍 *{sc('Select group to post to')}:*"

    if is_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    return SELECT_GROUP


# ── Handlers ──────────────────────────────────────────────────────────────────
async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return await update.message.reply_text(
            sc("Use /post in PM (private chat with the bot).")
        )
    context.user_data.clear()
    await update.message.reply_text(
        f"📝 *{sc('Create a Post')}*\n\n"
        f"{sc('Type your post message below.')}\n"
        f"_{sc('Send /cancel to abort at any time.')}_",
        parse_mode="Markdown",
    )
    return WAITING_TEXT


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["post_text"] = update.message.text
    preview = update.message.text[:400] + ("…" if len(update.message.text) > 400 else "")
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ " + sc("Confirm"), callback_data="ptg:confirm"),
        InlineKeyboardButton("❌ " + sc("Cancel"),  callback_data="ptg:cancel"),
    ]])
    await update.message.reply_text(
        f"📋 *{sc('Post Preview')}:*\n\n{preview}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return CONFIRM_TEXT


async def confirm_text_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "ptg:cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ " + sc("Post cancelled."))
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ " + sc("Add Button"), callback_data="ptg:add_btn"),
        InlineKeyboardButton("⏭️ " + sc("Skip"),       callback_data="ptg:skip_btn"),
    ]])
    await query.edit_message_text(
        f"🔘 *{sc('Add Buttons?')}*\n\n"
        f"{sc('You can attach up to 2 custom buttons to your post.')}\n"
        f"{sc('Each button needs a name and a URL or @username.')}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return CHOOSE_BTN


async def choose_btn_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "ptg:skip_btn":
        return await _show_group_select(update, context, is_query=True)
    await query.edit_message_text(
        f"🏷️ *{sc('Button 1 — Name')}*\n\n"
        f"{sc('Type the button label (e.g. Contact Admin, Join Link):')}\n"
        f"_{sc('Send /cancel to abort.')}_",
        parse_mode="Markdown",
    )
    return BTN1_NAME


async def receive_btn1_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["btn1_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"🔗 *{sc('Button 1 — URL')}*\n\n"
        f"{sc('Enter the URL or @username for this button:')}\n"
        f"_{sc('Example: https://t.me/admin or @admin')}_",
        parse_mode="Markdown",
    )
    return BTN1_URL


async def receive_btn1_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["btn1_url"] = _url(update.message.text)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ " + sc("Add 2nd Button"), callback_data="ptg:add_btn2"),
        InlineKeyboardButton("⏭️ " + sc("Skip"),           callback_data="ptg:skip_btn2"),
    ]])
    await update.message.reply_text(
        f"✅ *{sc('Button 1 saved!')}*\n\n"
        f"{sc('Do you want to add a second button?')}",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    return CHOOSE_BTN2


async def choose_btn2_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "ptg:skip_btn2":
        return await _show_group_select(update, context, is_query=True)
    await query.edit_message_text(
        f"🏷️ *{sc('Button 2 — Name')}*\n\n"
        f"{sc('Type the label for button 2:')}\n"
        f"_{sc('Send /cancel to abort.')}_",
        parse_mode="Markdown",
    )
    return BTN2_NAME


async def receive_btn2_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["btn2_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"🔗 *{sc('Button 2 — URL')}*\n\n"
        f"{sc('Enter the URL or @username for button 2:')}\n"
        f"_{sc('Example: https://example.com or @username')}_",
        parse_mode="Markdown",
    )
    return BTN2_URL


async def receive_btn2_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["btn2_url"] = _url(update.message.text)
    return await _show_group_select(update, context, is_query=False)


async def select_group_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ptg:cancel_send":
        context.user_data.clear()
        await query.edit_message_text("❌ " + sc("Post cancelled."))
        return ConversationHandler.END

    gid = int(query.data.split(":")[-1])
    context.user_data["target_gid"] = gid

    post_text = context.user_data.get("post_text", "")
    btn1_name = context.user_data.get("btn1_name")
    btn1_url  = context.user_data.get("btn1_url")
    btn2_name = context.user_data.get("btn2_name")
    btn2_url  = context.user_data.get("btn2_url")

    try:
        chat = await context.bot.get_chat(gid)
        group_name = sc(chat.title or str(gid))
    except Exception:
        group_name = sc(str(gid))

    btn_preview = ""
    if btn1_name:
        btn_preview += f"\n🔘 {sc('Button 1')}: *{sc(btn1_name)}* → `{btn1_url}`"
    if btn2_name:
        btn_preview += f"\n🔘 {sc('Button 2')}: *{sc(btn2_name)}* → `{btn2_url}`"

    preview = post_text[:300] + ("…" if len(post_text) > 300 else "")
    confirm_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ " + sc("Confirm to Send"), callback_data=f"ptg:send:{gid}"),
        InlineKeyboardButton("❌ " + sc("Cancel"),          callback_data="ptg:cancel_send"),
    ]])

    await query.edit_message_text(
        f"📋 *{sc('Final Preview')}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📍 *{sc('Group')}:* {group_name}\n\n"
        f"📝 *{sc('Message')}:*\n{preview}"
        + btn_preview
        + f"\n━━━━━━━━━━━━━━━━\n"
        f"*{sc('Send this post?')}*",
        parse_mode="Markdown",
        reply_markup=confirm_keyboard,
    )
    return SELECT_GROUP


async def confirm_send_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "ptg:cancel_send":
        context.user_data.clear()
        await query.edit_message_text("❌ " + sc("Post cancelled."))
        return ConversationHandler.END

    gid = int(query.data.split(":")[-1])
    post_text = context.user_data.get("post_text", "")
    btn1_name = context.user_data.get("btn1_name")
    btn1_url  = context.user_data.get("btn1_url")
    btn2_name = context.user_data.get("btn2_name")
    btn2_url  = context.user_data.get("btn2_url")

    btn_rows = []
    if btn1_name and btn1_url:
        row = [InlineKeyboardButton(btn1_name, url=btn1_url)]
        if btn2_name and btn2_url:
            row.append(InlineKeyboardButton(btn2_name, url=btn2_url))
        btn_rows.append(row)

    post_keyboard = InlineKeyboardMarkup(btn_rows) if btn_rows else None

    try:
        chat = await context.bot.get_chat(gid)
        group_name = sc(chat.title or str(gid))
        await context.bot.send_message(
            gid,
            f"📢 *{sc('Announcement')}*\n\n{post_text}",
            parse_mode="Markdown",
            reply_markup=post_keyboard,
        )
        context.user_data.clear()
        await query.edit_message_text(
            f"✅ *{sc('Posted successfully!')}*\n"
            f"📍 {sc('Group')}: *{group_name}*",
            parse_mode="Markdown",
        )
    except (BadRequest, TelegramError) as e:
        await query.edit_message_text(
            f"❌ *{sc('Failed to post')}*: `{e}`",
            parse_mode="Markdown",
        )
    return ConversationHandler.END


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ " + sc("Post cancelled."))
    return ConversationHandler.END


# ── Registration ──────────────────────────────────────────────────────────────
def register(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            WAITING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text)
            ],
            CONFIRM_TEXT: [
                CallbackQueryHandler(confirm_text_cb, pattern=r"^ptg:(confirm|cancel)$")
            ],
            CHOOSE_BTN: [
                CallbackQueryHandler(choose_btn_cb, pattern=r"^ptg:(add_btn|skip_btn)$")
            ],
            BTN1_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn1_name)
            ],
            BTN1_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn1_url)
            ],
            CHOOSE_BTN2: [
                CallbackQueryHandler(choose_btn2_cb, pattern=r"^ptg:(add_btn2|skip_btn2)$")
            ],
            BTN2_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn2_name)
            ],
            BTN2_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn2_url)
            ],
            SELECT_GROUP: [
                CallbackQueryHandler(select_group_cb,  pattern=r"^ptg:grp:"),
                CallbackQueryHandler(confirm_send_cb,  pattern=r"^ptg:send:"),
                CallbackQueryHandler(confirm_send_cb,  pattern=r"^ptg:cancel_send$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        per_user=True,
        per_chat=True,
        conversation_timeout=300,
    )
    app.add_handler(conv)
