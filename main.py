import os
import sys
import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application
from telegram.request import HTTPXRequest
import uvicorn

from database.connection import connect_db, disconnect_db
from bot.handlers import moderation, system, broadcast, post

load_dotenv()

# Suppress httpx INFO logs — prevents bot token from appearing in Render logs
logging.getLogger("httpx").setLevel(logging.WARNING)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN secret is missing.")

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
USE_WEBHOOK = bool(WEBHOOK_URL)

# Render sets this automatically; used for keep-alive self-ping
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").strip()

PORT = int(os.getenv("PORT", 8000))

ptb_app: Application = None
_keep_alive_task: asyncio.Task = None


def log(msg: str):
    print(msg, flush=True)


def build_request() -> HTTPXRequest:
    return HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        http_version="1.1",
    )


async def _keep_alive_loop():
    """Ping own health endpoint every 14 min to prevent Render free-tier sleep.
    Uses RENDER_EXTERNAL_URL (auto-set by Render) if available, else localhost:{PORT}.
    """
    await asyncio.sleep(30)  # wait for server to be fully ready
    ping_url = f"{RENDER_EXTERNAL_URL}/ping" if RENDER_EXTERNAL_URL else f"http://localhost:{PORT}/ping"
    log(f"🏓 Keep-alive target: {ping_url}")
    while True:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(ping_url)
                log(f"🏓 Keep-alive ping: {r.status_code}")
        except Exception as e:
            log(f"⚠️  Keep-alive ping failed: {e}")
        await asyncio.sleep(14 * 60)  # 14 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ptb_app, _keep_alive_task

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
    post.register(ptb_app)

    await ptb_app.initialize()
    await ptb_app.start()

    me = await ptb_app.bot.get_me()

    if USE_WEBHOOK:
        await ptb_app.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
        info = await ptb_app.bot.get_webhook_info()
        log(f"✅ Bot: @{me.username}")
        log(f"✅ Webhook set: {WEBHOOK_URL}")
        log(f"✅ Pending updates: {info.pending_update_count}")
        if info.last_error_message:
            log(f"⚠️  Last webhook error: {info.last_error_message}")
            log(f"⚠️  Last error date: {info.last_error_date}")
        _keep_alive_task = asyncio.create_task(_keep_alive_loop())
        log("🏓 Keep-alive task started (ping every 14 min)")
    else:
        log(f"✅ Bot: @{me.username}")
        log("⚠️  WARNING: WEBHOOK_URL is not set!")
        log("⚠️  Bot is running but CANNOT receive messages.")
        log("⚠️  Fix: Set WEBHOOK_URL=https://<your-render-url>/webhook")

    log("ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ — ready!")

    yield

    if _keep_alive_task:
        _keep_alive_task.cancel()
    try:
        # Do NOT delete_webhook() here — Render free tier shuts down on idle,
        # and deleting the webhook creates a dead cycle where Telegram has no
        # URL to call, so the service never wakes up again.
        await ptb_app.stop()
        await ptb_app.shutdown()
    except Exception:
        pass
    await disconnect_db()
    log("Bot stopped.")


web_app = FastAPI(lifespan=lifespan, title="Group Management Bot")


@web_app.get("/")
async def health_check():
    return {"status": "✅ running", "message": "ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ"}


@web_app.get("/ping")
@web_app.head("/ping")
async def ping():
    """Health check endpoint — used by keep-alive loop and Render."""
    return {"ok": True}


@web_app.get("/winfo")
async def webhook_info():
    """Live webhook status — open in browser to verify Telegram webhook is healthy."""
    if ptb_app is None:
        return {"error": "Bot not initialized yet"}
    try:
        info = await ptb_app.bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_message": info.last_error_message,
            "last_error_date": str(info.last_error_date) if info.last_error_date else None,
            "max_connections": info.max_connections,
            "allowed_updates": list(info.allowed_updates) if info.allowed_updates else [],
        }
    except Exception as e:
        return {"error": str(e)}


@web_app.post("/webhook")
async def telegram_webhook(request: Request):
    if ptb_app is None:
        return Response(status_code=503)
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        update_type = "unknown"
        if update.message:
            update_type = f"message({update.message.text or update.message.content_type})"
        elif update.callback_query:
            update_type = f"callback({update.callback_query.data})"
        elif update.my_chat_member:
            update_type = "my_chat_member"
        log(f"📨 Update #{update.update_id} → {update_type}")
        await ptb_app.process_update(update)
    except Exception as e:
        log(f"Webhook error: {e}")
    return Response(status_code=200)


if __name__ == "__main__":
    uvicorn.run(web_app, host="0.0.0.0", port=PORT, log_level="info")
