"""
Polling mode — for GitHub Actions hosting.
No webhook, no PORT, no SPACE_HOST needed.
Just BOT_TOKEN + MONGO_URI + OWNER_IDS.
"""
import os
from dotenv import load_dotenv
from telegram.ext import Application
from telegram.request import HTTPXRequest

from database.connection import connect_db, disconnect_db
from bot.handlers import moderation, system, broadcast, post

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")


def build_request() -> HTTPXRequest:
    return HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        http_version="1.1",
    )


async def post_init(app: Application) -> None:
    await connect_db()
    me = await app.bot.get_me()
    print(f"✅ MongoDB connected")
    print(f"✅ Bot running as @{me.username}")
    print("ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ — polling mode, ready!")


async def post_shutdown(app: Application) -> None:
    await disconnect_db()
    print("Bot stopped.")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(build_request())
        .get_updates_request(build_request())
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    moderation.register(app)
    system.register(app)
    broadcast.register(app)
    post.register(app)

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
