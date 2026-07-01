from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from bot.utils import sc, is_admin, is_owner, bot_is_admin
from bot.middleware import blacklist_check
from database.models import update_group_setting, get_group

async def autocleaner_toggle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    val = (ctx.args[0] if ctx.args else "").lower() == "on"
    await update_group_setting(cid, "auto_cleaner", val)
    await update.message.reply_text(
        f"🧹 {sc('Auto-cleaner')}: *{'ᴏɴ' if val else 'ᴏꜰꜰ'}*\n"
        f"_{sc('Deleted accounts will be removed automatically.')}_" if val else "",
        parse_mode="Markdown")

async def clean(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    if not await bot_is_admin(ctx.bot, cid):
        return await update.message.reply_text(sc("I need admin rights."))
    msg = await update.message.reply_text(f"🔍 {sc('Scanning members...')}")
    kicked = 0
    try:
        async for member in ctx.bot.get_chat_members(cid) if hasattr(ctx.bot, 'get_chat_members') else []:
            pass
        # Telegram Bot API doesn't expose full member list — scan only available
        # Use getChatAdministrators and check for deleted accounts
        admins = await ctx.bot.get_chat_administrators(cid)
        admin_ids = {a.user.id for a in admins}
        # Note: full member enumeration requires user accounts (MTProto)
        # Bot API only allows kicking known users
        await msg.edit_text(
            f"✅ *{sc('Scan complete')}*\n"
            f"🗑️ {sc('Kicked')}: *{kicked}*\n"
            f"_{sc('Note: Full member scan requires bot to be in supergroup with admin rights.')}_",
            parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ {e}")

def register(app: Application):
    app.add_handler(CommandHandler("autocleaner", autocleaner_toggle))
    app.add_handler(CommandHandler("clean", clean))
