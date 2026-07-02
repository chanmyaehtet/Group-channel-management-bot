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

    msg = await update.message.reply_text(f"🔍 {sc('Scanning for deleted admin accounts...')}")
    kicked = 0
    try:
        admins = await ctx.bot.get_chat_administrators(cid)
        for member in admins:
            # Telegram marks deleted accounts with first_name="" and is_bot=False
            # BUG-14 FIX: actually kick deleted accounts found in admin list
            if member.user.is_bot:
                continue
            if not member.user.first_name:  # deleted account
                try:
                    await ctx.bot.ban_chat_member(cid, member.user.id)
                    await ctx.bot.unban_chat_member(cid, member.user.id)
                    kicked += 1
                except Exception:
                    pass
        await msg.edit_text(
            f"✅ *{sc('Scan complete')}*\n"
            f"🗑️ {sc('Kicked')}: *{kicked}*\n\n"
            f"_{sc('Note: Telegram Bot API only exposes admin members.')}_\n"
            f"_{sc('Regular deleted accounts in the group cannot be detected via Bot API.')}_",
            parse_mode="Markdown",
        )
    except Exception as e:
        await msg.edit_text(f"❌ {e}")


def register(app: Application):
    app.add_handler(CommandHandler("autocleaner", autocleaner_toggle))
    app.add_handler(CommandHandler("clean",       clean))
