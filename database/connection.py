import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "gcm_bot"

client: AsyncIOMotorClient = None
db = None

async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    await db.moderation_logs.create_index([("group_id", 1), ("created_at", -1)])
    await db.warnings.create_index([("group_id", 1), ("user_id", 1), ("created_at", -1)])
    await db.group_configs.create_index([("group_id", 1)], unique=True)
    print("✅ MongoDB connected")

async def disconnect_db():
    global client
    if client:
        client.close()

def get_db():
    return db
