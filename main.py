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
from bot.handlers import moderation, system, broadcast, controls, posttogroup
from api.routes import router as api_router

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
OWNER_IDS = os.getenv("OWNER_IDS", "").strip()

# Auto-detect webhook URL: explicit env var takes priority,
# then Render's auto-injected RENDER_EXTERNAL_URL
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
if not WEBHOOK_URL:
    render_ext = os.getenv("RENDER_EXTERNAL_URL", "").strip()
    if render_ext:
        WEBHOOK_URL = f"{render_ext.rstrip('/')}/webhook"

USE_WEBHOOK = bool(WEBHOOK_URL)

# Global state
ptb_app: Application = None
bot_ready: bool = False
db_ready: bool = False
startup_error: str = None


def build_request() -> HTTPXRequest:
    return HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0,
        http_version="1.1",
    )


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

        moderation.register(ptb_app)
        system.register(ptb_app)
        broadcast.register(ptb_app)
        controls.register(ptb_app)
        posttogroup.register(ptb_app)

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
            print(f"⚠️  No WEBHOOK_URL — bot running as @{me.username} but won't receive updates.")
            print("   Set WEBHOOK_URL or RENDER_EXTERNAL_URL env var to enable webhook.")

        bot_ready = True
        startup_error = None
        print("✅ Bot fully initialized and ready!")

    except Exception as e:
        startup_error = f"Bot initialization failed: {e}"
        print(f"❌ {startup_error}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start HTTP server immediately — init bot/DB in background
    asyncio.create_task(init_bot_and_db())
    yield
    # Shutdown
    global ptb_app
    try:
        if ptb_app and bot_ready:
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
    """Uptime Robot health check — always 200. Accepts both GET and HEAD requests."""
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


@web_app.post("/webhook")
async def telegram_webhook(request: Request):
    if not bot_ready or ptb_app is None:
        return Response(
            content='{"error":"bot not ready"}',
            media_type="application/json",
            status_code=503,
        )
    try:
        data = await request.json()
        update = Update.de_json(data, ptb_app.bot)
        await ptb_app.process_update(update)
    except Exception as e:
        print(f"Webhook error: {e}")
    return Response(status_code=200)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    print(f"Starting server on port {port}")
    print(f"Webhook mode: {USE_WEBHOOK}")
    print(f"Webhook URL: {WEBHOOK_URL or 'not set'}")
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="info")
