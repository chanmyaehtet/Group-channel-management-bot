from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ChatMember
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ChatMemberHandler, ContextTypes
from bot.utils import sc, is_owner, is_admin, check_cooldown
from bot.middleware import blacklist_check
from database.models import (upsert_user, upsert_group, get_group,
                               update_group_setting, add_log)

# ─── /start ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    user = update.effective_user
    await upsert_user(user.id, user.username, user.first_name, user.last_name, pm_active=True)
    bot_username = context.bot.username
    owner = is_owner(user.id)
    name = user.first_name or sc("there")

    buttons = [
        [InlineKeyboardButton("🛡️ " + sc("Moderation"), callback_data="menu_mod"),
         InlineKeyboardButton("⚠️ " + sc("Warnings"), callback_data="menu_warn")],
        [InlineKeyboardButton("🔒 " + sc("Group Control"), callback_data="menu_ctrl"),
         InlineKeyboardButton("⚙️ " + sc("Settings"), callback_data="menu_set")],
        [InlineKeyboardButton("⏰ " + sc("Scheduling"), callback_data="menu_sched"),
         InlineKeyboardButton("👤 " + sc("My Profile/ID"), callback_data="menu_id")],
        [InlineKeyboardButton("➕ " + sc("Add to Group"),
                               url=f"https://t.me/{bot_username}?startgroup=true"),
         InlineKeyboardButton("📤 " + sc("Share"),
                               url=f"https://t.me/share/url?url=https://t.me/{bot_username}")],
    ]
    if owner:
        buttons.append([InlineKeyboardButton("👑 " + sc("Owner Dashboard"), callback_data="menu_owner")])

    await update.message.reply_text(
        f"👋 *{sc('Hello')}, {sc(name)}!*\n"
        f"{sc('I am a Group Management Bot.')}\n\n"
        f"_{sc('Select a category below to see available commands.')}_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

MENUS = {
    "menu_mod": (
        "🛡️ *{mod}*\n━━━━━━━━━━━━\n"
        "`/kick` — {kick}\n`/ban` — {ban}\n`/unban` — {unban}\n"
        "`/mute [sec]` — {mute}\n`/unmute` — {unmute}\n"
        "`/purge [n]` — {purge}\n`/report` — {report}\n`/info` — {info}"
    ),
    "menu_warn": (
        "⚠️ *{warn}*\n━━━━━━━━━━━━\n"
        "`/warn [reason]` — {warn_cmd}\n`/unwarn` — {unwarn}\n"
        "`/warnings` — {warnings}\n`/setwarnlimit [n]` — {setwarnlimit}"
    ),
    "menu_ctrl": (
        "🔒 *{ctrl}*\n━━━━━━━━━━━━\n"
        "`/lock` — {lock}\n`/unlock` — {unlock}\n"
        "`/pin` — {pin}\n`/unpin` — {unpin}\n"
        "`/promote` — {promote}\n`/demote` — {demote}\n"
        "`/antispam on/off` — {antispam}\n"
        "`/antispam_links on/off` — {antispam_links}\n"
        "`/antispam_flood on/off` — {antispam_flood}\n"
        "`/autocleaner on/off` — {autocleaner}\n`/clean` — {clean}"
    ),
    "menu_set": (
        "⚙️ *{settings}*\n━━━━━━━━━━━━\n"
        "`/setwelcome <text>` — {setwelcome}\n"
        "`/setgoodbye <text>` — {setgoodbye}\n"
        "`/autowelcome on/off` — {autowelcome}\n"
        "`/autogoodbye on/off` — {autogoodbye}\n"
        "`/setrules <text>` — {setrules}\n`/rules` — {rules}\n"
        "`/post <text>` — {post}"
    ),
    "menu_sched": (
        "⏰ *{sched}*\n━━━━━━━━━━━━\n"
        "`/setschedule onetime HH:MM <text>` — {onetime}\n"
        "`/setschedule always HH:MM <text>` — {always}\n\n"
        "_{tz}_"
    ),
    "menu_id": (
        "👤 *{profile}*\n━━━━━━━━━━━━\n"
        "`/id` — {id_self}\n`/id @username` — {id_user}\n"
        "_{id_reply}_"
    ),
    "menu_owner": (
        "👑 *{owner}*\n━━━━━━━━━━━━\n"
        "`/status` — {status}\n`/ping` — {ping}\n"
        "`/listusers` — {listusers}\n`/listgroups` — {listgroups}\n"
        "`/blockuser <id>` — {blockuser}\n`/unblockuser <id>` — {unblockuser}\n"
        "`/blockgroup <id>` — {blockgroup}\n`/unblockgroup <id>` — {unblockgroup}\n"
        "`/broadcast all <text>` — {bc_all}\n"
        "`/broadcast group <id> <text>` — {bc_grp}\n"
        "`/broadcast user <id> <text>` — {bc_usr}"
    ),
}

MENU_LABELS = {
    "mod": "Moderation", "kick": "Kick a user", "ban": "Ban a user",
    "unban": "Unban a user", "mute": "Mute a user", "unmute": "Unmute a user",
    "purge": "Delete last N messages", "report": "Report user to admins",
    "info": "Get user info",
    "warn": "Warnings", "warn_cmd": "Warn a user", "unwarn": "Remove last warning",
    "warnings": "Show warnings list", "setwarnlimit": "Set auto-ban limit",
    "ctrl": "Group Control", "lock": "Lock chat", "unlock": "Unlock chat",
    "pin": "Pin replied message", "unpin": "Unpin message",
    "promote": "Promote to admin", "demote": "Demote from admin",
    "antispam": "Toggle anti-spam", "antispam_links": "Toggle link filter",
    "antispam_flood": "Toggle flood filter",
    "autocleaner": "Toggle auto-cleaner", "clean": "Manually clean deleted accounts",
    "settings": "Settings", "setwelcome": "Set welcome message",
    "setgoodbye": "Set goodbye message", "autowelcome": "Toggle auto welcome",
    "autogoodbye": "Toggle auto goodbye", "setrules": "Set group rules",
    "rules": "Show rules", "post": "Post message to group via PM",
    "sched": "Scheduling", "onetime": "Send once at specified time",
    "always": "Send daily at specified time", "tz": "All times are in Asia/Yangon timezone",
    "profile": "Profile / ID", "id_self": "Your Telegram ID",
    "id_user": "Lookup user ID", "id_reply": "Or reply to a message to get that user's ID",
    "owner": "Owner Dashboard", "status": "System status", "ping": "Speed test",
    "listusers": "Total user count", "listgroups": "All groups list",
    "blockuser": "Block a user", "unblockuser": "Unblock a user",
    "blockgroup": "Block a group", "unblockgroup": "Unblock a group",
    "bc_all": "Broadcast to everyone", "bc_grp": "Send to specific group",
    "bc_usr": "Send to specific user",
}

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data
    if key not in MENUS: return
    if key == "menu_owner" and not is_owner(query.from_user.id):
        return await query.answer(sc("Owner only!"), show_alert=True)
    labels = {k: sc(v) for k, v in MENU_LABELS.items()}
    text = MENUS[key].format(**labels)
    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ " + sc("Back"), callback_data="menu_back")]]))

async def menu_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await start.__wrapped__(update, context) if hasattr(start, "__wrapped__") else None
    # Re-trigger start
    user = query.from_user
    owner = is_owner(user.id)
    bot_username = context.bot.username
    buttons = [
        [InlineKeyboardButton("🛡️ " + sc("Moderation"), callback_data="menu_mod"),
         InlineKeyboardButton("⚠️ " + sc("Warnings"), callback_data="menu_warn")],
        [InlineKeyboardButton("🔒 " + sc("Group Control"), callback_data="menu_ctrl"),
         InlineKeyboardButton("⚙️ " + sc("Settings"), callback_data="menu_set")],
        [InlineKeyboardButton("⏰ " + sc("Scheduling"), callback_data="menu_sched"),
         InlineKeyboardButton("👤 " + sc("My Profile/ID"), callback_data="menu_id")],
        [InlineKeyboardButton("➕ " + sc("Add to Group"),
                               url=f"https://t.me/{bot_username}?startgroup=true"),
         InlineKeyboardButton("📤 " + sc("Share"),
                               url=f"https://t.me/share/url?url=https://t.me/{bot_username}")],
    ]
    if owner:
        buttons.append([InlineKeyboardButton("👑 " + sc("Owner Dashboard"), callback_data="menu_owner")])
    await query.edit_message_text(
        f"👋 *{sc('Hello')}, {sc(user.first_name or '')}!*\n"
        f"{sc('I am a Group Management Bot.')}\n\n"
        f"_{sc('Select a category below to see available commands.')}_",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

# ─── /id ──────────────────────────────────────────────────
async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    msg = update.message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        await msg.reply_text(
            f"👤 *{sc(u.first_name or 'User')}*\n"
            f"🆔 `{u.id}`"
            + (f"\n📛 @{u.username}" if u.username else ""),
            parse_mode="Markdown")
    elif context.args:
        try:
            u = await context.bot.get_chat(context.args[0])
            await msg.reply_text(
                f"👤 *{sc(u.first_name or u.title or 'User')}*\n🆔 `{u.id}`",
                parse_mode="Markdown")
        except Exception as e:
            await msg.reply_text(f"❌ {e}")
    else:
        u = msg.from_user
        chat = update.effective_chat
        await msg.reply_text(
            f"👤 *{sc(u.first_name or 'You')}*\n🆔 `{u.id}`\n"
            f"💬 {sc('Chat ID')}: `{chat.id}`"
            + (f"\n📛 @{u.username}" if u.username else ""),
            parse_mode="Markdown")

# ─── /rules /setrules ─────────────────────────────────────
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    g = await get_group(update.effective_chat.id)
    r = g.get("settings", {}).get("rules", "")
    if not r: return await update.message.reply_text(sc("No rules set for this group."))
    await update.message.reply_text(f"📜 *{sc('Rules')}*\n\n{r}", parse_mode="Markdown")

async def setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("Admins only."))
    if not context.args:
        return await update.message.reply_text(sc("Usage: /setrules <text>"))
    await update_group_setting(cid, "rules", " ".join(context.args))
    await update.message.reply_text(sc("✅ Rules updated."))

# ─── welcome / goodbye ────────────────────────────────────
async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("Admins only."))
    if not context.args:
        return await update.message.reply_text(
            sc("Usage: /setwelcome <text>\nPlaceholders: {user} {first_name} {group}"))
    await update_group_setting(cid, "welcome_message", " ".join(context.args))
    await update.message.reply_text(sc("✅ Welcome message set."))

async def setgoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("Admins only."))
    if not context.args:
        return await update.message.reply_text(sc("Usage: /setgoodbye <text>"))
    await update_group_setting(cid, "goodbye_message", " ".join(context.args))
    await update.message.reply_text(sc("✅ Goodbye message set."))

async def autowelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("Admins only."))
    arg = (context.args[0] if context.args else "").lower()
    val = arg == "on"
    await update_group_setting(cid, "auto_welcome", val)
    await update.message.reply_text(f"✅ {sc('Auto-welcome')}: *{'ᴏɴ' if val else 'ᴏꜰꜰ'}*", parse_mode="Markdown")

async def autogoodbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, context): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if not await is_admin(context.bot, cid, uid) and not is_owner(uid):
        return await update.message.reply_text(sc("Admins only."))
    arg = (context.args[0] if context.args else "").lower()
    val = arg == "on"
    await update_group_setting(cid, "auto_goodbye", val)
    await update.message.reply_text(f"✅ {sc('Auto-goodbye')}: *{'ᴏɴ' if val else 'ᴏꜰꜰ'}*", parse_mode="Markdown")

# ─── Member join/leave ────────────────────────────────────
DEFAULT_WELCOME = "🎉 {sc_welcome} *{user}* {sc_to} *{group}*!"
DEFAULT_GOODBYE = "👋 *{user}* {sc_left} *{group}*."

async def on_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result: return
    old, new = result.old_chat_member.status, result.new_chat_member.status
    joined = old in (ChatMember.LEFT, ChatMember.BANNED) and \
             new in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER)
    left = old in (ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER) and \
           new in (ChatMember.LEFT, ChatMember.BANNED)
    if not joined and not left: return

    cid = result.chat.id
    g = await get_group(cid)
    settings = g.get("settings", {})

    def _fmt(tpl: str, user) -> str:
        return tpl.format(
            user=f"@{user.username}" if user.username else (user.first_name or ""),
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            username=f"@{user.username}" if user.username else "",
            group=result.chat.title or "",
        )

    if joined:
        await upsert_group(cid, result.chat.title)
        if not settings.get("auto_welcome", True): return
        user = result.new_chat_member.user
        tpl = settings.get("welcome_message") or \
              f"🎉 {sc('Welcome')} *{{user}}* {sc('to')} *{{group}}*!"
        try: await context.bot.send_message(cid, _fmt(tpl, user), parse_mode="Markdown")
        except: pass
    elif left:
        if not settings.get("auto_goodbye", True): return
        user = result.old_chat_member.user
        tpl = settings.get("goodbye_message") or \
              f"👋 *{{user}}* {sc('has left')} *{{group}}*."
        try: await context.bot.send_message(cid, _fmt(tpl, user), parse_mode="Markdown")
        except: pass

def register(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("rules", rules))
    app.add_handler(CommandHandler("setrules", setrules))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("setgoodbye", setgoodbye))
    app.add_handler(CommandHandler("autowelcome", autowelcome))
    app.add_handler(CommandHandler("autogoodbye", autogoodbye))
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_(?!back)"))
    app.add_handler(CallbackQueryHandler(menu_back, pattern="^menu_back$"))
    app.add_handler(ChatMemberHandler(on_member_update, ChatMemberHandler.CHAT_MEMBER))
