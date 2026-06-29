import os
import importlib
from pyrogram import Client
from dotenv import load_dotenv
from database.connection import connect_db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

bot = Client(
    "gcm_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

async def start_bot():
    await connect_db()
    # Import handlers to register them
    importlib.import_module("bot.handlers.moderation")
    importlib.import_module("bot.handlers.system")
    await bot.start()
    me = await bot.get_me()
    print(f"✅ Bot started as @{me.username}")
