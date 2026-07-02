import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import RetryAfter
from bot.utils import sc, is_owner, fmt_user
from bot.middleware import blacklist_check
from database.models import (block, unblock, count_users, count_groups,
                               get_all_groups, get_all_pm_users, add_log)

def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_owner(update.effective_user.id):
            return
        if await blacklist_check(update, context): return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

@owner_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = await count_users()
    groups = await count_groups()
    await update.message.reply_text(
        f"⚙️ *{sc('System Status')}*\n"
        f"━━━━━━━━━━━━\n"
        f"👤 {sc('Users')}: *{users}*\n"
        f"👥 {sc('Groups')}: *{groups}*\n"
        f"🟢 {sc('Status')}: *{sc('Online')}*",
        parse_mode="Markdown"
    )

@owner_only
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import time; s = time.time()
    msg = await update.message.reply_text("🏓")
    ms = int((time.time() - s) * 1000)
    await msg.edit_text(f"🏓 *{sc('Pong')}!* `{ms}ms`", parse_mode="Markdown")

@owner_only
async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = await count_users()
    await update.message.reply_text(f"👤 {sc('Total users')}: *{n}*", parse_mode="Markdown")

@owner_only
async def listgroups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    groups = await get_all_groups()
    if not groups:
        return await update.message.reply_text(sc("No groups yet."))
    lines = [f"👥 *{sc('Groups')}* ({len(groups)})\n━━━━━━━━━━━━"]
    for g in groups[:30]:
        title = sc(g.get("title") or "Unknown")
        lines.append(f"`{g['group_id']}` — {title}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

@owner_only
async def blockuser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(sc("Usage: /blockuser <user_id>"))
    try: uid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(sc("Provide a numeric user ID."))
    await block("user", uid, update.effective_user.id)
    await update.message.reply_text(f"🚫 {sc('User')} `{uid}` {sc('blocked.')}", parse_mode="Markdown")

@owner_only
async def unblockuser_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(sc("Usage: /unblockuser <user_id>"))
    try: uid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(sc("Provide a numeric user ID."))
    ok = await unblock("user", uid)
    status_text = sc("Unblocked.") if ok else sc("User was not blocked.")
    await update.message.reply_text(f"✅ {status_text}")

@owner_only
async def blockgroup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(sc("Usage: /blockgroup <group_id>"))
    try: gid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(sc("Provide a numeric group ID."))
    await block("group", gid, update.effective_user.id)
    try: await context.bot.leave_chat(gid)
    except Exception: pass
    await update.message.reply_text(f"🚫 {sc('Group')} `{gid}` {sc('blocked and left.')}", parse_mode="Markdown")

@owner_only
async def unblockgroup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text(sc("Usage: /unblockgroup <group_id>"))
    try: gid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text(sc("Provide a numeric group ID."))
    ok = await unblock("group", gid)
    status_text = sc("Unblocked.") if ok else sc("Group was not blocked.")
    await update.message.reply_text(f"✅ {status_text}")

@owner_only
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args or len(args) < 2:
        return await update.message.reply_text(
            f"*{sc('Usage')}:*\n"
            f"`/broadcast all <text>`\n"
            f"`/broadcast group <group_id> <text>`\n"
            f"`/broadcast user <user_id> <text>`", parse_mode="Markdown")
    target = args[0].lower()
    if target == "all":
        text = " ".join(args[1:])
        groups = await get_all_groups()
        pm_users = await get_all_pm_users()
        targets = [g["group_id"] for g in groups] + [u["user_id"] for u in pm_users]
        msg = await update.message.reply_text(f"📡 {sc('Broadcasting to')} *{len(targets)}*...", parse_mode="Markdown")
        ok = fail = 0
        for tid in targets:
            # BUG-10 FIX: handle Telegram RetryAfter with proper backoff instead of failing
            try:
                await context.bot.send_message(tid, text)
                ok += 1
                await asyncio.sleep(0.05)
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                try:
                    await context.bot.send_message(tid, text)
                    ok += 1
                except Exception:
                    fail += 1
            except Exception:
                fail += 1
        await msg.edit_text(f"✅ *{sc('Done')}*\n📨 {sc('Sent')}: *{ok}* | ❌ {sc('Failed')}: *{fail}*", parse_mode="Markdown")
    elif target == "group" and len(args) >= 3:
        try: gid = int(args[1])
        except ValueError:
            return await update.message.reply_text(sc("Invalid group ID."))
        text = " ".join(args[2:])
        try:
            await context.bot.send_message(gid, text)
            await update.message.reply_text(f"✅ {sc('Sent to group')} `{gid}`", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ `{e}`", parse_mode="Markdown")
    elif target == "user" and len(args) >= 3:
        try: uid = int(args[1])
        except ValueError:
            return await update.message.reply_text(sc("Invalid user ID."))
        text = " ".join(args[2:])
        try:
            await context.bot.send_message(uid, text)
            await update.message.reply_text(f"✅ {sc('Sent to user')} `{uid}`", parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text(f"❌ `{e}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(sc("Invalid syntax. Use: /broadcast all/group/user ..."))

def register(app: Application):
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ping", ping))
    app.add_handler(CommandHandler("listusers", listusers))
    app.add_handler(CommandHandler("listgroups", listgroups))
    app.add_handler(CommandHandler("blockuser", blockuser_cmd))
    app.add_handler(CommandHandler("unblockuser", unblockuser_cmd))
    app.add_handler(CommandHandler("blockgroup", blockgroup_cmd))
    app.add_handler(CommandHandler("unblockgroup", unblockgroup_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
