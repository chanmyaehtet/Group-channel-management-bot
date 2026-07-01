from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters,
)
from telegram.error import TelegramError

from bot.utils import sc, is_owner, is_admin
from database.connection import get_db

(
    TYPING_MESSAGE,
    CONFIRM_MESSAGE,
    BUTTON_CHOICE,
    BUTTON_1_NAME,
    BUTTON_1_URL,
    BUTTON_2_CHOICE,
    BUTTON_2_NAME,
    BUTTON_2_URL,
    SELECT_GROUP,
    FINAL_CONFIRM,
) = range(10)

TIMEOUT = 300  # 5 minutes


async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not is_owner(uid) and not await is_admin(context.bot, cid, uid):
        await update.message.reply_text(sc("This command is only for admins and owners."))
        return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        f"📝 *{sc('Create a Post')}*\n\n"
        f"{sc('Type your post message below.')}\n\n"
        f"_{sc('Send /cancel to stop at any time.')}_",
        parse_mode="Markdown",
    )
    return TYPING_MESSAGE


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["message"] = update.message.text
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data="post_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="post_cancel"),
        ]
    ])
    await update.message.reply_text(
        f"📋 *{sc('Post Preview')}*:\n\n{update.message.text}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return CONFIRM_MESSAGE


async def confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "post_cancel":
        await query.edit_message_text(sc("Post cancelled."))
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Button", callback_data="add_btn"),
            InlineKeyboardButton("⏭️ Skip", callback_data="skip_btn"),
        ]
    ])
    await query.edit_message_text(
        f"🔘 *{sc('Add Buttons')}?*\n\n"
        f"{sc('You can add up to 2 buttons below your post.')}\n"
        f"{sc('Each button needs a label and a URL or @username.')}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return BUTTON_CHOICE


async def button_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "skip_btn":
        context.user_data["buttons"] = []
        await query.edit_message_text(f"⏭️ {sc('No buttons. Selecting group...')}")
        return await _show_group_selection(query.message, context, edit=True)

    await query.edit_message_text(
        f"🏷 *{sc('Button 1 — Name')}*\n\n"
        f"{sc('Type the button label (e.g. Contact Admin)')}",
        parse_mode="Markdown",
    )
    return BUTTON_1_NAME


async def receive_btn1_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["btn1_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"🔗 *{sc('Button 1 — URL')}*\n\n"
        f"{sc('Enter a URL (https://...) or @username')}",
        parse_mode="Markdown",
    )
    return BUTTON_1_URL


async def receive_btn1_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if url.startswith("@"):
        url = f"https://t.me/{url[1:]}"
    elif not url.startswith("http"):
        url = f"https://t.me/{url}"
    context.user_data["btn1_url"] = url

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add 2nd Button", callback_data="add_btn2"),
            InlineKeyboardButton("⏭️ Skip", callback_data="skip_btn2"),
        ]
    ])
    await update.message.reply_text(
        f"✅ *{sc('Button 1 saved!')}*\n\n"
        f"🏷 `{context.user_data['btn1_name']}` → `{url}`",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return BUTTON_2_CHOICE


async def btn2_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "skip_btn2":
        context.user_data["buttons"] = [
            (context.user_data["btn1_name"], context.user_data["btn1_url"])
        ]
        await query.edit_message_text(f"⏭️ {sc('1 button added. Selecting group...')}")
        return await _show_group_selection(query.message, context, edit=True)

    await query.edit_message_text(
        f"🏷 *{sc('Button 2 — Name')}*\n\n"
        f"{sc('Type the button label (e.g. Website)')}",
        parse_mode="Markdown",
    )
    return BUTTON_2_NAME


async def receive_btn2_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["btn2_name"] = update.message.text.strip()
    await update.message.reply_text(
        f"🔗 *{sc('Button 2 — URL')}*\n\n"
        f"{sc('Enter a URL (https://...) or @username')}",
        parse_mode="Markdown",
    )
    return BUTTON_2_URL


async def receive_btn2_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if url.startswith("@"):
        url = f"https://t.me/{url[1:]}"
    elif not url.startswith("http"):
        url = f"https://t.me/{url}"
    context.user_data["btn2_url"] = url
    context.user_data["buttons"] = [
        (context.user_data["btn1_name"], context.user_data["btn1_url"]),
        (context.user_data["btn2_name"], url),
    ]
    await update.message.reply_text(
        f"✅ *{sc('Button 2 saved!')}*\n\n"
        f"🏷 `{context.user_data['btn2_name']}` → `{url}`\n\n"
        f"{sc('Selecting group...')}",
        parse_mode="Markdown",
    )
    return await _show_group_selection(update.message, context, edit=False)


async def _show_group_selection(message, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    db = get_db()
    configs = await db.group_configs.find({}, {"group_id": 1, "title": 1}).to_list(length=None)

    if not configs:
        text = (
            f"❌ *{sc('No groups found')}*\n\n"
            f"{sc('Add the bot to a group and use /setwelcome or /setrules there first.')}"
        )
        if edit:
            await message.edit_text(text, parse_mode="Markdown")
        else:
            await message.reply_text(text, parse_mode="Markdown")
        context.user_data.clear()
        return ConversationHandler.END

    buttons = []
    for cfg in configs:
        gid = cfg["group_id"]
        title = cfg.get("title") or str(gid)
        buttons.append([InlineKeyboardButton(title, callback_data=f"grp_{gid}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="post_cancel_grp")])

    keyboard = InlineKeyboardMarkup(buttons)
    text = f"📍 *{sc('Select group to post to')}:*"
    if edit:
        await message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return SELECT_GROUP


async def select_group_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "post_cancel_grp":
        await query.edit_message_text(sc("Post cancelled."))
        context.user_data.clear()
        return ConversationHandler.END

    group_id = int(query.data.replace("grp_", ""))
    context.user_data["group_id"] = group_id

    try:
        chat = await context.bot.get_chat(group_id)
        group_title = chat.title or str(group_id)
    except Exception:
        group_title = str(group_id)
    context.user_data["group_title"] = group_title

    msg_text = context.user_data["message"]
    buttons = context.user_data.get("buttons", [])
    btn_lines = ""
    for name, url in buttons:
        btn_lines += f"\n🔘 `{name}` → `{url}`"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm to Send", callback_data="final_confirm"),
            InlineKeyboardButton("❌ Cancel", callback_data="final_cancel"),
        ]
    ])
    await query.edit_message_text(
        f"📋 *{sc('Final Preview')}*\n"
        f"━━━━━━━━━━━━\n"
        f"📍 *{sc('Group')}*: {group_title}\n"
        f"📝 *{sc('Message')}*:\n{msg_text}"
        + (f"\n{btn_lines}" if btn_lines else "") +
        f"\n━━━━━━━━━━━━",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return FINAL_CONFIRM


async def final_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "final_cancel":
        await query.edit_message_text(sc("Post cancelled."))
        context.user_data.clear()
        return ConversationHandler.END

    group_id = context.user_data["group_id"]
    msg_text = context.user_data["message"]
    buttons = context.user_data.get("buttons", [])
    group_title = context.user_data.get("group_title", str(group_id))

    post_keyboard = None
    if buttons:
        row = [InlineKeyboardButton(name, url=url) for name, url in buttons]
        post_keyboard = InlineKeyboardMarkup([row])

    try:
        await context.bot.send_message(
            group_id,
            f"📢 *{sc('Announcement')}*\n\n{msg_text}",
            reply_markup=post_keyboard,
            parse_mode="Markdown",
        )
        db = get_db()
        await db.moderation_logs.insert_one({
            "group_id": group_id,
            "user_id": 0,
            "admin_id": update.effective_user.id,
            "action": f"post sent ({len(buttons)} buttons)",
            "created_at": datetime.now(timezone.utc),
        })
        await query.edit_message_text(
            f"✅ *{sc('Post Sent!')}*\n📍 {sc('Group')}: {group_title}",
            parse_mode="Markdown",
        )
    except TelegramError as e:
        await query.edit_message_text(
            f"❌ *{sc('Failed to send')}*: `{e}`",
            parse_mode="Markdown",
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(sc("Post creation cancelled."))
    else:
        await update.message.reply_text(sc("Post creation cancelled."))
    return ConversationHandler.END


def register(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            TYPING_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message)
            ],
            CONFIRM_MESSAGE: [
                CallbackQueryHandler(confirm_cb, pattern="^post_(confirm|cancel)$")
            ],
            BUTTON_CHOICE: [
                CallbackQueryHandler(button_choice_cb, pattern="^(add_btn|skip_btn)$")
            ],
            BUTTON_1_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn1_name)
            ],
            BUTTON_1_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn1_url)
            ],
            BUTTON_2_CHOICE: [
                CallbackQueryHandler(btn2_choice_cb, pattern="^(add_btn2|skip_btn2)$")
            ],
            BUTTON_2_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn2_name)
            ],
            BUTTON_2_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn2_url)
            ],
            SELECT_GROUP: [
                CallbackQueryHandler(select_group_cb, pattern="^(grp_-?\\d+|post_cancel_grp)$")
            ],
            FINAL_CONFIRM: [
                CallbackQueryHandler(final_confirm_cb, pattern="^(final_confirm|final_cancel)$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_post)],
        conversation_timeout=TIMEOUT,
        allow_reentry=True,
    )
    app.add_handler(conv)
