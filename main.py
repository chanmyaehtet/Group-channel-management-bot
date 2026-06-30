import os
import asyncio
import importlib

from pyrogram import idle
from dotenv import load_dotenv

from bot.client import bot
from database.connection import connect_db, disconnect_db

load_dotenv()


async def main():
    await connect_db()

    # Register all handlers
    importlib.import_module("bot.handlers.moderation")
    importlib.import_module("bot.handlers.system")

    await bot.start()
    me = await bot.get_me()
    print(f"✅ Bot started as @{me.username}")
    print("ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ — bot is running...")

    await idle()  # Keep bot alive until interrupted

    await bot.stop()
    await disconnect_db()
    print("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
