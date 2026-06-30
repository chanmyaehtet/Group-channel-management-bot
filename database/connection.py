import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "gcm_bot"

client: AsyncIOMotorClient = None
db = None


async def connect_db(retries: int = 3, delay: float = 3.0):
    global client, db
    for attempt in range(1, retries + 1):
        try:
            client = AsyncIOMotorClient(
                MONGO_URI,
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=8000,
                socketTimeoutMS=30000,
            )
            db = client[DB_NAME]
            # Verify connection is alive
            await client.admin.command("ping")
            # Create indexes
            await db.moderation_logs.create_index([("group_id", 1), ("created_at", -1)])
            await db.warnings.create_index([("group_id", 1), ("user_id", 1), ("created_at", -1)])
            await db.group_configs.create_index([("group_id", 1)], unique=True)
            print(f"✅ MongoDB connected (attempt {attempt})")
            return
        except Exception as e:
            print(f"⚠️  MongoDB attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError(f"MongoDB connection failed after {retries} attempts")


async def disconnect_db():
    global client
    if client:
        client.close()
        print("MongoDB disconnected.")


def get_db():
    if db is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return db
