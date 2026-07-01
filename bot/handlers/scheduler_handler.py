"""Scheduling system — Yangon timezone (Asia/Yangon = UTC+6:30)."""
import pytz
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from bot.utils import sc, is_admin, is_owner
from bot.middleware import blacklist_check
from database.models import (add_schedule, get_active_schedules,
                               deactivate_schedule, mark_schedule_ran)

YANGON_TZ = pytz.timezone("Asia/Yangon")
_scheduler: AsyncIOScheduler = None
_bot: Bot = None

def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone=YANGON_TZ)
    return _scheduler

async def _fire_schedule(group_id: int, text: str, stype: str, schedule_id: str):
    global _bot
    if _bot is None: return
    try:
        await _bot.send_message(group_id, text)
        await mark_schedule_ran(schedule_id)
        if stype == "onetime":
            await deactivate_schedule(schedule_id)
            get_scheduler().remove_job(schedule_id)
    except Exception as e:
        print(f"Schedule fire error [{schedule_id}]: {e}")

async def load_schedules_from_db(bot: Bot):
    global _bot
    _bot = bot
    scheduler = get_scheduler()
    schedules = await get_active_schedules()
    for s in schedules:
        sid = str(s["_id"])
        time_parts = s["time"].split(":")
        h, m = int(time_parts[0]), int(time_parts[1])
        if s["type"] == "onetime":
            now = datetime.now(YANGON_TZ)
            fire_time = YANGON_TZ.localize(datetime(now.year, now.month, now.day, h, m))
            if fire_time <= now: continue  # already past
            trigger = CronTrigger(hour=h, minute=m, timezone=YANGON_TZ, end_date=fire_time)
        else:
            trigger = CronTrigger(hour=h, minute=m, timezone=YANGON_TZ)
        scheduler.add_job(_fire_schedule, trigger=trigger, id=sid,
                          kwargs={"group_id": s["group_id"], "text": s["text"],
                                  "stype": s["type"], "schedule_id": sid},
                          replace_existing=True)
    if not scheduler.running:
        scheduler.start()
    print(f"✅ Scheduler started — {len(schedules)} job(s) loaded")

async def setschedule(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await blacklist_check(update, ctx): return
    uid, cid = update.effective_user.id, update.effective_chat.id
    if update.effective_chat.type == "private":
        return await update.message.reply_text(sc("Use in a group."))
    if not is_owner(uid) and not await is_admin(ctx.bot, cid, uid):
        return await update.message.reply_text(sc("Admins only."))
    if not ctx.args or len(ctx.args) < 3:
        return await update.message.reply_text(
            f"*{sc('Usage')}:*\n"
            f"`/setschedule onetime HH:MM <text>`\n"
            f"`/setschedule always HH:MM <text>`\n\n"
            f"_{sc('Times are in Asia/Yangon timezone (UTC+6:30)')}_",
            parse_mode="Markdown")
    stype = ctx.args[0].lower()
    if stype not in ("onetime", "always"):
        return await update.message.reply_text(sc("Type must be 'onetime' or 'always'."))
    time_str = ctx.args[1]
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59): raise ValueError
    except:
        return await update.message.reply_text(sc("Invalid time. Use HH:MM format (e.g. 08:00)."))
    text = " ".join(ctx.args[2:])
    if not text: return await update.message.reply_text(sc("Please provide message text."))

    sid = await add_schedule(cid, uid, stype, time_str, text)
    trigger = (CronTrigger(hour=h, minute=m, timezone=YANGON_TZ) if stype == "always"
               else CronTrigger(hour=h, minute=m, timezone=YANGON_TZ,
                                end_date=datetime(2099, 12, 31, tzinfo=YANGON_TZ)))
    get_scheduler().add_job(_fire_schedule, trigger=trigger, id=sid,
                             kwargs={"group_id": cid, "text": text,
                                     "stype": stype, "schedule_id": sid},
                             replace_existing=True)
    await update.message.reply_text(
        f"⏰ *{sc('Schedule set')}*\n"
        f"🕐 {sc('Time')}: *{time_str}* (Yangon)\n"
        f"🔁 {sc('Type')}: *{sc(stype)}*\n"
        f"📝 {sc('Message')}: {text}",
        parse_mode="Markdown")

def register(app: Application):
    app.add_handler(CommandHandler("setschedule", setschedule))
