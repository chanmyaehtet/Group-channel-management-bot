import os, asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = "gcm_bot"
client: AsyncIOMotorClient = None
db = None

async def connect_db(retries=3, delay=3.0):
    global client, db
    for attempt in range(1, retries + 1):
        try:
            client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000,
                                        connectTimeoutMS=8000, socketTimeoutMS=30000)
            db = client[DB_NAME]
            await client.admin.command("ping")
            await _create_indexes()
            print("✅ MongoDB connected")
            return
        except Exception as e:
            print(f"⚠️  MongoDB attempt {attempt}/{retries}: {e}")
            if attempt < retries:
                await asyncio.sleep(delay)
    raise RuntimeError("MongoDB connection failed")

async def _create_indexes():
    # groups — primary lookup
    await db.groups.create_index("group_id", unique=True)
    await db.groups.create_index("last_activity")
    # users
    await db.users.create_index("user_id", unique=True)
    await db.users.create_index("pm_active")
    # warnings — compound for fast per-group/user queries
    await db.warnings.create_index([("group_id", 1), ("user_id", 1), ("created_at", -1)])
    # blacklist — fast O(1) lookup on every message
    await db.blacklist.create_index([("type", 1), ("target_id", 1)], unique=True)
    # schedules
    await db.schedules.create_index([("group_id", 1), ("active", 1)])
    # logs — recent-first per group
    await db.logs.create_index([("group_id", 1), ("created_at", -1)])
    # anti-spam flood tracking (TTL: auto-expire after 60s)
    await db.flood_track.create_index("expires_at", expireAfterSeconds=0)
    # posts — sent announcements log
    await db.posts.create_index("admin_id")
    await db.posts.create_index("group_id")
    await db.posts.create_index([("sent_at", -1)])

async def disconnect_db():
    global client
    if client:
        client.close()

def get_db():
    if db is None:
        raise RuntimeError("DB not connected")
    return db
