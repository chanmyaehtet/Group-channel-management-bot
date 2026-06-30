import os
import asyncio
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application
from telegram.request import HTTPXRequest
import uvicorn

from database.connection import connect_db, disconnect_db
from bot.handlers import moderation, system, broadcast
from api.routes import router as api_router

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN secret is missing.")

# Auto-detect webhook URL from Render environment if not explicitly set
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
if not WEBHOOK_URL:
    render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if render_url:
        WEBHOOK_URL = f"{render_url}/webhook"

USE_WEBHOOK = bool(WEBHOOK_URL)

ptb_app: Application = None


def build_request() -> HTTPXRequest:
    return HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        http_version="1.1",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app

    await connect_db()

    ptb_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(build_request())
        .get_updates_request(build_request())
        .build()
    )

    moderation.register(ptb_app)
    system.register(ptb_app)
    broadcast.register(ptb_app)

    await ptb_app.initialize()
    await ptb_app.start()

    if USE_WEBHOOK:
        await ptb_app.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        me = await ptb_app.bot.get_me()
        print(f"✅ Webhook set: {WEBHOOK_URL}")
        print(f"✅ Bot running as @{me.username}")
    else:
        me = await ptb_app.bot.get_me()
        print(f"✅ Bot running as @{me.username} (no webhook — updates via polling only)")
        print("⚠️  Set WEBHOOK_URL env var for webhook mode on Render.")

    print("ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ — ready!")

    yield

    try:
        if USE_WEBHOOK:
            await ptb_app.bot.delete_webhook()
        await ptb_app.stop()
        await ptb_app.shutdown()
    except Exception:
        pass
    await disconnect_db()
    print("Bot stopped.")


web_app = FastAPI(lifespan=lifespan, title="Group Management Bot")

# Mount REST API routes
web_app.include_router(api_router)


@web_app.get("/")
async def health_check():
    return {"status": "ok", "bot": "running", "webhook": USE_WEBHOOK}


@web_app.get("/ping")
async def ping():
    """Uptime Robot ping endpoint — always returns 200 OK."""
    return "pong"


@web_app.post("/webhook")
async def telegram_webhook(request: Request):
    if ptb_app is None:
        return Response(status_code=503)
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        print(f"Webhook error: {e}")
    return Response(status_code=200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")
