import os
import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, ContextTypes
from telegram.request import HTTPXRequest
import httpx
import uvicorn

from database.connection import connect_db, disconnect_db
from bot.handlers import (moderation, system, broadcast, controls, posttogroup,
                           group_controls, owner, antispam, cleaner,
                           scheduler_handler, post_handler)
from bot.handlers.scheduler_handler import load_schedules_from_db
from api.routes import router as api_router

load_dotenv()

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress httpx INFO logs — they expose the bot token in URLs (security)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BOT_TOKEN  = os.getenv("BOT_TOKEN",  "").strip()
MONGO_URI  = os.getenv("MONGO_URI",  "").strip()
OWNER_IDS  = os.getenv("OWNER_IDS",  "").strip()

# Auto-detect webhook URL: explicit env var takes priority,
# then Render's auto-injected RENDER_EXTERNAL_URL
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
if not WEBHOOK_URL:
    render_ext = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if render_ext:
        WEBHOOK_URL = f"{render_ext.rstrip('/')}/webhook"

USE_WEBHOOK = bool(WEBHOOK_URL)

# Global state
ptb_app:       Application = None
bot_ready:     bool        = False
db_ready:      bool        = False
startup_error: str         = None
_keep_alive_task           = None


def build_request() -> HTTPXRequest:
    return HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        http_version="1.1",
    )


async def ptb_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log ALL handler exceptions so they appear in Render logs instead of being silently dropped."""
    err = context.error
    print(f"❌ PTB HANDLER ERROR — update={update!r} error={err!r}")
    traceback.print_exception(type(err), err, err.__traceback__)
    logger.error("Unhandled PTB exception", exc_info=err)


async def _keep_alive_loop():
    """Ping /ping every 14 minutes to prevent Render free-tier spin-down.
    Render sleeps instances after ~15 min inactivity; this keeps us awake.
    """
    await asyncio.sleep(30)  # small initial delay so server is fully ready
    port = int(os.getenv("PORT", 8000))
    url  = f"http://localhost:{port}/ping"
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get(url)
            print("🏓 Keep-alive ping sent")
        except Exception as e:
            print(f"⚠️  Keep-alive ping failed: {e}")
        await asyncio.sleep(14 * 60)   # 14 minutes


async def init_bot_and_db():
    """Initialize DB and bot in the background — does NOT crash the HTTP server on failure."""
    global ptb_app, bot_ready, db_ready, startup_error

    # Step 1: MongoDB
    if not MONGO_URI:
        startup_error = "MONGO_URI env var is missing"
        print(f"❌ {startup_error}")
        return
    try:
        await connect_db()
        db_ready = True
        print("✅ MongoDB connected")
    except Exception as e:
        startup_error = f"MongoDB connection failed: {e}"
        print(f"❌ {startup_error}")
        return

    # Step 2: Telegram bot
    if not BOT_TOKEN:
        startup_error = "BOT_TOKEN env var is missing"
        print(f"❌ {startup_error}")
        return
    try:
        ptb_app = (
            Application.builder()
            .token(BOT_TOKEN)
            .request(build_request())
            .get_updates_request(build_request())
            .build()
        )

        # ── Error handler: makes ALL handler exceptions visible in logs ──
        ptb_app.add_error_handler(ptb_error_handler)

        # Register ALL handlers
        system.register(ptb_app)
        moderation.register(ptb_app)
        broadcast.register(ptb_app)
        controls.register(ptb_app)
        group_controls.register(ptb_app)
        owner.register(ptb_app)
        antispam.register(ptb_app)
        cleaner.register(ptb_app)
        scheduler_handler.register(ptb_app)
        post_handler.register(ptb_app)
        posttogroup.register(ptb_app)

        await ptb_app.initialize()
        await ptb_app.start()

        # Load scheduled jobs from DB
        await load_schedules_from_db(ptb_app.bot)

        if USE_WEBHOOK:
            await ptb_app.bot.set_webhook(
                url=WEBHOOK_URL,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            me = await ptb_app.bot.get_me()
            print(f"✅ Webhook set: {WEBHOOK_URL}")
            print(f"✅ Bot running as @{me.username}")

            # Immediately verify webhook was accepted by Telegram
            winfo = await ptb_app.bot.get_webhook_info()
            print(f"📡 Telegram webhook URL  : {winfo.url}")
            print(f"📡 Pending updates       : {winfo.pending_update_count}")
            if winfo.last_error_message:
                print(f"⚠️  Telegram webhook error: {winfo.last_error_message} "
                      f"(at {winfo.last_error_date})")
        else:
            me = await ptb_app.bot.get_me()
            print(f"⚠️  No WEBHOOK_URL — bot running as @{me.username} (webhook not active).")
            print("   Set WEBHOOK_URL or RENDER_EXTERNAL_URL env var to enable webhook.")

        bot_ready = True
        startup_error = None
        print("✅ Bot fully initialized and ready!")

    except Exception as e:
        startup_error = f"Bot initialization failed: {e}"
        print(f"❌ {startup_error}")
        traceback.print_exc()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _keep_alive_task
    # Start HTTP server immediately — init bot/DB and keep-alive in background
    asyncio.create_task(init_bot_and_db())
    _keep_alive_task = asyncio.create_task(_keep_alive_loop())
    yield
    # Shutdown
    global ptb_app
    if _keep_alive_task:
        _keep_alive_task.cancel()
    try:
        if ptb_app and bot_ready:
            from bot.handlers.scheduler_handler import get_scheduler
            sched = get_scheduler()
            if sched.running:
                sched.shutdown(wait=False)
            if USE_WEBHOOK:
                await ptb_app.bot.delete_webhook()
            await ptb_app.stop()
            await ptb_app.shutdown()
    except Exception:
        pass
    try:
        await disconnect_db()
    except Exception:
        pass
    print("Bot stopped.")


web_app = FastAPI(lifespan=lifespan, title="Group Management Bot")
web_app.include_router(api_router)


@web_app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "status": "running",
        "bot_ready": bot_ready,
        "db_ready": db_ready,
        "webhook_mode": USE_WEBHOOK,
        "webhook_url": WEBHOOK_URL or None,
        "error": startup_error,
    }


@web_app.api_route("/ping", methods=["GET", "HEAD"])
async def ping():
    """Keep-alive health check — always 200."""
    return Response(content="pong", media_type="text/plain", status_code=200)


@web_app.get("/health")
async def health():
    """Detailed component health."""
    return {
        "http": "ok",
        "bot": "ready" if bot_ready else "initializing",
        "db": "ready" if db_ready else "initializing",
        "webhook": WEBHOOK_URL if USE_WEBHOOK else "disabled",
        "error": startup_error,
    }


@web_app.get("/winfo")
async def winfo():
    """Return live Telegram getWebhookInfo — useful for diagnosing webhook problems."""
    if not bot_ready or ptb_app is None:
        return {"error": "bot not ready yet"}
    try:
        info = await ptb_app.bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": str(info.last_error_date) if info.last_error_date else None,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
            "allowed_updates": list(info.allowed_updates) if info.allowed_updates else [],
        }
    except Exception as e:
        return {"error": str(e)}


@web_app.post("/webhook")
async def telegram_webhook(request: Request):
    if not bot_ready or ptb_app is None:
        logger.warning("Webhook hit but bot not ready yet — returning 503")
        return Response(
            content='{"error":"bot not ready"}',
            media_type="application/json",
            status_code=503,
        )
    try:
        data = await request.json()
        update_id   = data.get("update_id", "?")
        update_type = next((k for k in data if k != "update_id"), "unknown")
        # Use logger (stderr, always unbuffered) so this ALWAYS appears in Render logs
        logger.info("📨 Webhook update #%s type=%s", update_id, update_type)
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        logger.error("❌ Webhook processing error: %s", e, exc_info=True)
    return Response(status_code=200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}")
    print(f"Webhook mode: {USE_WEBHOOK}")
    print(f"Webhook URL:  {WEBHOOK_URL or 'not set'}")
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")
