import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bot.utils import sc, is_owner
from database.connection import get_db


def _validate_group_id(target: str):
    """
    Returns (group_id, error_message).
    Valid Telegram group/channel IDs are negative integers.
    Supergroup/channel IDs start with -100.
    """
    try:
        gid = int(target)
    except ValueError:
        return None, (
            f"❌ *{sc('Invalid format')}*\n\n"
            f"{sc('Group ID must be a number.')}\n"
            f"{sc('Example')}: `/broadcast -1001234567890 Hello`"
        )
    if gid > 0:
        return None, (
            f"❌ *{sc('Invalid Group ID')}*: `{gid}`\n\n"
            f"⚠️ {sc('Positive numbers are user IDs, not group IDs.')}\n\n"
            f"💡 *{sc('Hint')}:*\n"
            f"• {sc('Group/supergroup IDs are')} *{sc('negative')}* {sc('numbers')}\n"
            f"• {sc('Supergroup format')}: `-100xxxxxxxxxx`\n"
            f"• {sc('Basic group format')}: `-xxxxxxx`\n\n"
            f"{sc('Use')} `/broadcast all` {sc('to send to all registered groups.')}"
        )
    return gid, None


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
            f"`/broadcast -1001234567890 ʜᴇʟʟᴏ`\n\n"
            f"💡 *{sc('Note')}:* {sc('Group IDs must be negative numbers (e.g. -1001234567890)')}",
            parse_mode="Markdown",
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
            parse_mode="Markdown",
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
            parse_mode="Markdown",
        )

    else:
        group_id, error = _validate_group_id(target)
        if error:
            return await update.message.reply_text(error, parse_mode="Markdown")

        try:
            await context.bot.send_message(group_id, text)
            await db.moderation_logs.insert_one({
                "group_id": group_id, "user_id": 0, "admin_id": uid,
                "action": "broadcast single",
                "created_at": datetime.now(timezone.utc),
            })
            await update.message.reply_text(
                f"✅ *{sc('Message Sent')}*\n"
                f"📍 {sc('Group ID')}: `{group_id}`",
                parse_mode="Markdown",
            )
        except Exception as e:
            err_str = str(e).lower()
            hint = ""
            if "chat not found" in err_str:
                hint = (
                    f"\n\n💡 *{sc('Possible reasons')}:*\n"
                    f"• {sc('Bot is not a member of this group')}\n"
                    f"• {sc('Group ID is incorrect')}\n"
                    f"• {sc('Group was deleted or is private')}"
                )
            elif "bot was kicked" in err_str or "forbidden" in err_str:
                hint = f"\n\n💡 {sc('The bot was removed from this group.')}"
            await update.message.reply_text(
                f"❌ *{sc('Failed')}*: `{e}`{hint}",
                parse_mode="Markdown",
            )


def register(app: Application):
    app.add_handler(CommandHandler("broadcast", broadcast))
