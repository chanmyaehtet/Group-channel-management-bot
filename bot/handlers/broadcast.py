import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.utils import sc, is_owner
from database.connection import get_db


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_owner(uid):
        return await update.message.reply_text(sc("This command is only for bot owners."))
    args = context.args
    if not args or len(args) < 2:
        return await update.message.reply_text(
            f"*{sc('Usage')}:*\n"
            f"`/broadcast all <message>` — {sc('Send to ALL groups')}\n"
            f"`/broadcast <group_id> <message>` — {sc('Send to a specific group')}\n\n"
            f"*{sc('Example')}:*\n"
            f"`/broadcast all ꜱᴇʀᴠᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ᴛᴏɴɪɢʜᴛ`\n"
            f"`/broadcast -1001234567890 ʜᴇʟʟᴏ`",
            parse_mode="Markdown"
        )
    target = args[0]
    text = " ".join(args[1:])
    db = get_db()

    if target.lower() == "all":
        configs = await db.group_configs.find({}, {"group_id": 1}).to_list(length=None)
        group_ids = [c["group_id"] for c in configs]
        if not group_ids:
            return await update.message.reply_text(sc("No groups found in database."))
        status_msg = await update.message.reply_text(
            f"📡 {sc('Broadcasting to')} *{len(group_ids)}* {sc('groups')}...",
            parse_mode="Markdown"
        )
        success, failed = 0, 0
        for gid in group_ids:
            try:
                await context.bot.send_message(gid, text)
                success += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                failed += 1
                print(f"Broadcast failed {gid}: {e}")
        await db.moderation_logs.insert_one({
            "group_id": 0, "user_id": 0, "admin_id": uid,
            "action": f"broadcast all ({success} ok, {failed} failed)",
            "created_at": datetime.now(timezone.utc),
        })
        await status_msg.edit_text(
            f"✅ *{sc('Broadcast Complete')}*\n"
            f"━━━━━━━━━━━━\n"
            f"📨 {sc('Sent')}: *{success}*\n"
            f"❌ {sc('Failed')}: *{failed}*\n"
            f"📋 {sc('Total')}: *{len(group_ids)}*",
            parse_mode="Markdown"
        )
    else:
        try:
            group_id = int(target)
        except ValueError:
            return await update.message.reply_text(
                sc("Invalid group ID. Use a number or 'all'.")
            )
        try:
            await context.bot.send_message(group_id, text)
            await db.moderation_logs.insert_one({
                "group_id": group_id, "user_id": 0, "admin_id": uid,
                "action": "broadcast single", "created_at": datetime.now(timezone.utc),
            })
            await update.message.reply_text(
                f"✅ *{sc('Message Sent')}*\n"
                f"📍 {sc('Group ID')}: `{group_id}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(
                f"❌ *{sc('Failed')}*: `{e}`", parse_mode="Markdown"
            )


def register(app: Application):
    app.add_handler(CommandHandler("broadcast", broadcast))
