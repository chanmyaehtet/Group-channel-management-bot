"""
/post — Multi-step post creation wizard.

Access:
  - Bot OWNER: can post to ANY registered group.
  - Group ADMIN: can post ONLY to groups where they are an admin.
  - Regular users: not allowed.

Flow:
  /post  (PM or group)
    └── TYPING_MESSAGE   ← user types the post text
        └── CONFIRM_MESSAGE  ← ✅ Confirm / ❌ Cancel
            └── BUTTON_CHOICE  ← ➕ Add Button / ⏭️ Skip
                │
                ├── Skip ──────────────────────────────┐
                └── ➕ Add Button                       │
                    └── BUTTON_1_NAME                   │
                        └── BUTTON_1_URL                │
                            └── BUTTON_2_CHOICE         │
                                │                       │
                                ├── Skip ───────────────┤
                                └── ➕ Add 2nd Button   │
                                    └── BUTTON_2_NAME   │
                                        └── BUTTON_2_URL│
                                                        ▼
                                               SELECT_GROUP
                                                   └── FINAL_CONFIRM
                                                       └── ✅ Send → END

• /cancel ends conversation at any step
• 5 minutes of inactivity → auto-cancel
• Sent posts are persisted to the `posts` MongoDB collection
"""

from datetime import datetime, timezone

from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import TelegramError

from bot.utils import sc, is_owner, is_admin
from database.connection import get_db
from database.models import get_all_groups

# ── State constants ────────────────────────────────────────────────────────────
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


# ── Internal helpers ───────────────────────────────────────────────────────────

def _normalise_url(raw: str) -> str:
    """Turn @username or bare domain into a full https URL."""
    raw = raw.strip()
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if not raw.startswith(("http://", "https://")):
        return f"https://{raw}"
    return raw


async def _nudge(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Remind the user to tap a button instead of typing."""
    await update.message.reply_text(
        "👆 " + sc("Please use the buttons above, or send /cancel to exit.")
    )


async def _get_accessible_groups(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> list:
    """
    Owner  → all registered groups.
    Admin  → only groups where user is an admin.
    Others → empty list (blocked at entry).
    """
    groups = await get_all_groups()
    if is_owner(user_id):
        return groups

    accessible = []
    for g in groups:
        try:
            member = await context.bot.get_chat_member(g["group_id"], user_id)
            if member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
                accessible.append(g)
        except Exception:
            pass
    return accessible


async def _show_group_select(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Render the group-selection keyboard filtered by user's admin status."""
    user_id = update.effective_user.id
    groups  = await _get_accessible_groups(context, user_id)

    if not groups:
        text = (
            f"❌ *{sc('No accessible groups found')}*\n\n"
            f"{sc('You need to be an admin in at least one group that has this bot.')}\n"
            f"{sc('Add the bot to your group as admin, then try /post again.')}"
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await update.message.reply_text(text, parse_mode="Markdown")
        context.user_data.clear()
        return ConversationHandler.END

    rows = [
        [InlineKeyboardButton(
            sc((g.get("title") or str(g["group_id"]))[:35]),
            callback_data=f"post_grp:{g['group_id']}"
        )]
        for g in groups
    ]
    rows.append([InlineKeyboardButton("❌ " + sc("Cancel"), callback_data="post_cancel_grp")])
    keyboard = InlineKeyboardMarkup(rows)
    text = f"📍 *{sc('Select group to post to')}:*"

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)

    return SELECT_GROUP


# ── Step 1: Entry (/post) ──────────────────────────────────────────────────────

async def post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Entry point — available in PM or group.
    Allowed: bot owners + group admins.
    Rejected: regular users.
    """
    user_id = update.effective_user.id

    # Check access: owner or admin of at least one group
    if not is_owner(user_id):
        # Quick pre-check before starting the wizard
        groups = await get_all_groups()
        has_access = False
        for g in groups:
            try:
                member = await context.bot.get_chat_member(g["group_id"], user_id)
                if member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
                    has_access = True
                    break
            except Exception:
                pass
        if not has_access:
            await update.message.reply_text(
                f"⛔ *{sc('Access Denied')}*\n\n"
                f"{sc('Only bot owners and group admins can create posts.')}\n"
                f"{sc('You must be an admin in at least one group that has this bot.')}",
                parse_mode="Markdown"
            )
            return ConversationHandler.END

    context.user_data.clear()
    await update.message.reply_text(
        f"📝 *{sc('Create a Post')}*\n\n"
        f"{sc('Type your post message below.')}\n\n"
        f"_{sc('Send /cancel to stop at any time.')}_",
        parse_mode="Markdown",
    )
    return TYPING_MESSAGE


# ── Step 2: Receive post text ──────────────────────────────────────────────────

async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["message"] = update.message.text

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ " + sc("Confirm"), callback_data="post_confirm"),
        InlineKeyboardButton("❌ " + sc("Cancel"),  callback_data="post_cancel"),
    ]])
    await update.message.reply_text(
        f"📋 *{sc('Post Preview')}:*\n\n{update.message.text}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return CONFIRM_MESSAGE


# ── Step 3: Confirm text → ask about buttons ───────────────────────────────────

async def confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "post_cancel":
        await query.edit_message_text(sc("Post cancelled."))
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ " + sc("Add Button"), callback_data="add_btn"),
        InlineKeyboardButton("⏭️ " + sc("Skip"),       callback_data="skip_btn"),
    ]])
    await query.edit_message_text(
        f"🔘 *{sc('Add Buttons?')}*\n\n"
        f"{sc('You can attach up to 2 buttons to your post.')}\n"
        f"{sc('Each button needs a label and a URL or @username.')}",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return BUTTON_CHOICE


# ── Step 4a: Button 1 — name ───────────────────────────────────────────────────

async def button_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "skip_btn":
        context.user_data["buttons"] = []
        return await _show_group_select(update, context)

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
        f"{sc('Enter a URL or @username')}\n"
        f"_{sc('e.g. https://t.me/admin or @admin')}_",
        parse_mode="Markdown",
    )
    return BUTTON_1_URL


async def receive_btn1_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = _normalise_url(update.message.text)
    context.user_data["btn1_url"] = url

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ " + sc("Add 2nd Button"), callback_data="add_btn2"),
        InlineKeyboardButton("⏭️ " + sc("Skip"),           callback_data="skip_btn2"),
    ]])
    await update.message.reply_text(
        f"✅ *{sc('Button 1 saved!')}*\n\n"
        f"🏷 `{context.user_data['btn1_name']}` → `{url}`",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return BUTTON_2_CHOICE


# ── Step 4b: Button 2 ─────────────────────────────────────────────────────────

async def btn2_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "skip_btn2":
        context.user_data["buttons"] = [
            {"label": context.user_data["btn1_name"],
             "url":   context.user_data["btn1_url"]}
        ]
        return await _show_group_select(update, context)

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
        f"{sc('Enter a URL or @username')}",
        parse_mode="Markdown",
    )
    return BUTTON_2_URL


async def receive_btn2_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = _normalise_url(update.message.text)
    context.user_data["buttons"] = [
        {"label": context.user_data["btn1_name"], "url": context.user_data["btn1_url"]},
        {"label": context.user_data["btn2_name"], "url": url},
    ]
    await update.message.reply_text(
        f"✅ *{sc('Button 2 saved!')}*\n\n"
        f"🏷 `{context.user_data['btn2_name']}` → `{url}`",
        parse_mode="Markdown",
    )
    return await _show_group_select(update, context)


# ── Step 5: Group selected → final preview ─────────────────────────────────────

async def select_group_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "post_cancel_grp":
        await query.edit_message_text(sc("Post cancelled."))
        context.user_data.clear()
        return ConversationHandler.END

    group_id = int(query.data.split(":")[1])

    # Re-verify admin access for non-owners (security check)
    user_id = update.effective_user.id
    if not is_owner(user_id):
        try:
            member = await context.bot.get_chat_member(group_id, user_id)
            if member.status not in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
                await query.edit_message_text(
                    f"⛔ {sc('You are no longer an admin in that group.')}"
                )
                context.user_data.clear()
                return ConversationHandler.END
        except Exception:
            await query.edit_message_text(
                f"⛔ {sc('Could not verify your admin status. Please try again.')}"
            )
            context.user_data.clear()
            return ConversationHandler.END

    context.user_data["group_id"] = group_id

    try:
        chat = await context.bot.get_chat(group_id)
        group_title = chat.title or str(group_id)
    except Exception:
        group_title = str(group_id)
    context.user_data["group_title"] = group_title

    msg_text  = context.user_data["message"]
    buttons   = context.user_data.get("buttons", [])
    btn_lines = "".join(
        f"\n🔘 {sc('Button')} {i+1}: `{b['label']}` → `{b['url']}`"
        for i, b in enumerate(buttons)
    )

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ " + sc("Confirm to Send"), callback_data="final_confirm"),
        InlineKeyboardButton("❌ " + sc("Cancel"),          callback_data="final_cancel"),
    ]])
    await query.edit_message_text(
        f"📋 *{sc('Final Preview')}*\n"
        f"━━━━━━━━━━━━\n"
        f"📍 *{sc('Group')}*: {group_title}\n"
        f"📝 *{sc('Message')}*:\n{msg_text}"
        + (f"\n{btn_lines}" if btn_lines else "")
        + "\n━━━━━━━━━━━━",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return FINAL_CONFIRM


# ── Step 6: Send post ──────────────────────────────────────────────────────────

async def final_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "final_cancel":
        await query.edit_message_text(sc("Post cancelled."))
        context.user_data.clear()
        return ConversationHandler.END

    group_id    = context.user_data["group_id"]
    group_title = context.user_data.get("group_title", str(group_id))
    msg_text    = context.user_data["message"]
    buttons     = context.user_data.get("buttons", [])

    post_keyboard = None
    if buttons:
        post_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(b["label"], url=b["url"])]
            for b in buttons
        ])

    try:
        sent = await context.bot.send_message(
            group_id,
            f"📢 *{sc('Announcement')}*\n\n{msg_text}",
            reply_markup=post_keyboard,
            parse_mode="Markdown",
        )
        try:
            db = get_db()
            await db.posts.insert_one({
                "admin_id":    update.effective_user.id,
                "group_id":    group_id,
                "group_title": group_title,
                "message_id":  sent.message_id,
                "text":        msg_text,
                "buttons":     buttons,
                "sent_at":     datetime.now(timezone.utc),
            })
        except Exception:
            pass
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


# ── Fallbacks & timeout ────────────────────────────────────────────────────────

async def cancel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(sc("Post creation cancelled."))
    else:
        await update.message.reply_text(sc("Post creation cancelled."))
    return ConversationHandler.END


async def _timeout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                update.effective_chat.id,
                "⏰ " + sc("Post creation timed out (5 min). Use /post to start again."),
            )
    except Exception:
        pass
    return ConversationHandler.END


# ── Registration ───────────────────────────────────────────────────────────────

def register(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("post", post_start)],
        states={
            TYPING_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_message),
            ],
            CONFIRM_MESSAGE: [
                CallbackQueryHandler(confirm_cb, pattern=r"^post_(confirm|cancel)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _nudge),
            ],
            BUTTON_CHOICE: [
                CallbackQueryHandler(button_choice_cb, pattern=r"^(add_btn|skip_btn)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _nudge),
            ],
            BUTTON_1_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn1_name),
            ],
            BUTTON_1_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn1_url),
            ],
            BUTTON_2_CHOICE: [
                CallbackQueryHandler(btn2_choice_cb, pattern=r"^(add_btn2|skip_btn2)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _nudge),
            ],
            BUTTON_2_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn2_name),
            ],
            BUTTON_2_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_btn2_url),
            ],
            SELECT_GROUP: [
                CallbackQueryHandler(
                    select_group_cb,
                    pattern=r"^(post_grp:-?\d+|post_cancel_grp)$"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _nudge),
            ],
            FINAL_CONFIRM: [
                CallbackQueryHandler(
                    final_confirm_cb,
                    pattern=r"^(final_confirm|final_cancel)$"
                ),
                MessageHandler(filters.TEXT & ~filters.COMMAND, _nudge),
            ],
            ConversationHandler.TIMEOUT: [
                MessageHandler(filters.ALL, _timeout_handler),
                CallbackQueryHandler(_timeout_handler),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_post)],
        conversation_timeout=TIMEOUT,
        per_user=True,
        per_chat=False,
        allow_reentry=True,
    )
    app.add_handler(conv)
