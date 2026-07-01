"""
Entry point — GitHub Actions polling mode.
Secrets needed: BOT_TOKEN, MONGO_URI, OWNER_IDS
"""
import os
from dotenv import load_dotenv
from telegram.ext import Application
from telegram.request import HTTPXRequest

from database.connection import connect_db, disconnect_db
from bot.handlers import (system, moderation, group_controls,
                           owner, antispam, cleaner,
                           scheduler_handler, post_handler)
from bot.handlers.scheduler_handler import load_schedules_from_db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

def build_request() -> HTTPXRequest:
    return HTTPXRequest(connect_timeout=30.0, read_timeout=30.0,
                        write_timeout=30.0, pool_timeout=30.0, http_version="1.1")

async def post_init(app: Application) -> None:
    await connect_db()
    await load_schedules_from_db(app.bot)
    me = await app.bot.get_me()
    print(f"✅ Bot running as @{me.username}")
    print("ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ — ready!")

async def post_shutdown(app: Application) -> None:
    from bot.handlers.scheduler_handler import get_scheduler
    s = get_scheduler()
    if s.running: s.shutdown(wait=False)
    await disconnect_db()

def main():
    app = (Application.builder().token(BOT_TOKEN)
           .request(build_request()).get_updates_request(build_request())
           .post_init(post_init).post_shutdown(post_shutdown).build())

    # Register handlers (order matters — antispam group=1 runs after commands)
    system.register(app)
    moderation.register(app)
    group_controls.register(app)
    owner.register(app)
    antispam.register(app)
    cleaner.register(app)
    scheduler_handler.register(app)
    post_handler.register(app)

    app.run_polling(drop_pending_updates=True, allowed_updates=["message",
        "callback_query", "chat_member", "my_chat_member"])

if __name__ == "__main__":
    main()
