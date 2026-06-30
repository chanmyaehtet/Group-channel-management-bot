from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest, TelegramError

from bot.utils import sc, is_owner
from database.connection import get_db


async def post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return await update.message.reply_text(sc("Use /post in PM (private chat) with the bot."))
    if not context.args:
        return await update.message.reply_text(
            f"📤 *{sc('Usage')}*\n"
            f"`/post {sc('your message here')}`\n\n"
            f"{sc('I will show you a list of groups to send it to.')}",
            parse_mode="Markdown"
        )
    text = " ".join(context.args)
    uid = update.effective_user.id
    db = get_db()

    configs = await db.group_configs.find({}, {"group_id": 1}).to_list(length=None)
    if not configs:
        return await update.message.reply_text(sc("No groups found. Add me to a group first."))

    buttons = []
    for cfg in configs:
        gid = cfg["group_id"]
        try:
            chat = await context.bot.get_chat(gid)
            title = chat.title or str(gid)
        except Exception:
            title = str(gid)
        callback_data = f"postgroup:{gid}:{uid}"
        buttons.append([InlineKeyboardButton(sc(title[:30]), callback_data=callback_data)])

    buttons.append([InlineKeyboardButton("❌ " + sc("Cancel"), callback_data=f"postgroup:cancel:{uid}")])
    keyboard = InlineKeyboardMarkup(buttons)

    context.user_data["pending_post_text"] = text

    await update.message.reply_text(
        f"📤 *{sc('Select a group to post to')}:*\n\n"
        f"```\n{text[:200]}{'...' if len(text) > 200 else ''}\n```",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


async def post_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("postgroup:"):
        return

    parts = data.split(":", 2)
    if len(parts) < 3:
        return

    _, target, owner_uid = parts

    if str(query.from_user.id) != owner_uid:
        return await query.answer(sc("This is not your action."), show_alert=True)

    if target == "cancel":
        context.user_data.pop("pending_post_text", None)
        await query.edit_message_text("❌ " + sc("Post cancelled."))
        return

    text = context.user_data.get("pending_post_text")
    if not text:
        return await query.edit_message_text(sc("No message found. Please use /post again."))

    try:
        group_id = int(target)
        chat = await context.bot.get_chat(group_id)
        group_name = sc(chat.title or str(group_id))

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👍 " + sc("Like"), callback_data=f"react:like:{group_id}"),
                InlineKeyboardButton("👎 " + sc("Dislike"), callback_data=f"react:dislike:{group_id}"),
            ],
            [
                InlineKeyboardButton("💬 " + sc("Comment in group"), url=f"https://t.me/{chat.username}" if chat.username else f"tg://openmessage?chat_id={group_id}"),
            ]
        ])

        await context.bot.send_message(
            group_id,
            f"📢 *{sc('Announcement')}*\n\n{text}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )

        context.user_data.pop("pending_post_text", None)
        await query.edit_message_text(
            f"✅ *{sc('Posted successfully!')}*\n"
            f"📍 {sc('Group')}: *{group_name}*",
            parse_mode="Markdown"
        )
    except (BadRequest, TelegramError) as e:
        await query.edit_message_text(f"❌ *{sc('Failed to post')}*: `{e}`", parse_mode="Markdown")
    except ValueError:
        await query.edit_message_text(sc("Invalid group ID."))


async def react_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(sc("Thanks for your reaction!"), show_alert=False)


def register(app: Application):
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CallbackQueryHandler(post_callback, pattern=r"^postgroup:"))
    app.add_handler(CallbackQueryHandler(react_callback, pattern=r"^react:"))
