import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from dotenv import load_dotenv

from bot.client import start_bot, bot
from api.routes import router as api_router
from database.connection import disconnect_db

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_bot()
    yield
    await bot.stop()
    await disconnect_db()


app = FastAPI(title="GCM Bot API", lifespan=lifespan)
app.include_router(api_router)


@app.get("/")
async def root():
    return {"status": "running", "message": "ɢᴄᴍ ʙᴏᴛ ɪs ᴀᴄᴛɪᴠᴇ 🤖"}
