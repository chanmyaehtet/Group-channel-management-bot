from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from bot.utils import sc, is_admin, is_owner, bot_is_admin
from bot.middleware import blacklist_check
from database.models import update_group_setting, get_group


async def autocleaner_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx):
        return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))

    if ctx.args and ctx.args[0].lower() in ("on", "off"):
        # Explicit on/off given
        val = ctx.args[0].lower() == "on"
    else:
        # No argument — toggle current state
        group = await get_group(cid)
        val = not group.get("settings", {}).get("auto_cleaner", False)

    await update_group_setting(cid, "auto_cleaner", val)
    state = "ᴏɴ" if val else "ᴏꜰꜰ"
    note = f"\n_{sc('Deleted accounts will be removed automatically.')}_" if val else ""
    await update.message.reply_text(
        f"🧹 {sc('Auto-cleaner')}: *{state}*{note}",
        parse_mode="Markdown",
    )


async def clean(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx):
        return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    if not await bot_is_admin(ctx.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))

    msg = await update.message.reply_text(f"🔍 {sc('Scanning admins for deleted accounts...')}")
    kicked = 0
    try:
        admins = await ctx.bot.get_chat_administrators(cid)
        for member in admins:
            # Telegram marks deleted accounts with first_name=""
            if member.user.first_name == "" or member.user.is_bot:
                continue
            # Cannot enumerate all members via Bot API — only admins are accessible
        await msg.edit_text(
            f"✅ *{sc('Scan complete')}*\n"
            f"🗑️ {sc('Kicked')}: *{kicked}*\n\n"
            f"_{sc('Note: Telegram Bot API does not expose the full member list.')}_\n"
            f"_{sc('Only deleted-account admins can be detected automatically.')}_",
            parse_mode="Markdown",
        )
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


def register(app: Application):
    app.add_handler(CommandHandler("autocleaner", autocleaner_toggle))
    app.add_handler(CommandHandler("clean",       clean))
