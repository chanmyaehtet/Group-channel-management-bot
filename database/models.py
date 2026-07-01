"""
Clean data-access layer — all MongoDB operations go through here.
Handlers never touch raw pymongo/motor directly.
"""
from datetime import datetime, timezone
from typing import Optional
from .connection import get_db

def _now():
    return datetime.now(timezone.utc)

# ─── GROUPS ───────────────────────────────────────────────
async def get_group(group_id: int) -> dict:
    db = get_db()
    return await db.groups.find_one({"group_id": group_id}) or {}

async def upsert_group(group_id: int, title: str = None) -> None:
    db = get_db()
    update = {"$set": {"last_activity": _now()},
               "$setOnInsert": {"group_id": group_id, "title": title,
                                "added_at": _now(), "settings": _default_settings()}}
    if title:
        update["$set"]["title"] = title
    await db.groups.update_one({"group_id": group_id}, update, upsert=True)

async def update_group_setting(group_id: int, key: str, value) -> None:
    db = get_db()
    await db.groups.update_one({"group_id": group_id},
        {"$set": {f"settings.{key}": value, "last_activity": _now()}}, upsert=True)

async def get_all_groups() -> list:
    db = get_db()
    return await db.groups.find({}, {"group_id": 1, "title": 1}).to_list(None)

def _default_settings() -> dict:
    return {
        "welcome_message": "", "goodbye_message": "",
        "auto_welcome": True, "auto_goodbye": True,
        "rules": "", "warn_limit": 3,
        "antispam_enabled": False, "antispam_links": False, "antispam_flood": False,
        "auto_cleaner": False, "locked": False,
    }

# ─── USERS ────────────────────────────────────────────────
async def upsert_user(user_id: int, username: str = None,
                      first_name: str = None, last_name: str = None,
                      pm_active: bool = None) -> None:
    db = get_db()
    set_fields = {"last_seen": _now()}
    if username is not None:  set_fields["username"]   = username
    if first_name is not None: set_fields["first_name"] = first_name
    if last_name is not None:  set_fields["last_name"]  = last_name
    if pm_active is not None:  set_fields["pm_active"]  = pm_active
    await db.users.update_one({"user_id": user_id},
        {"$set": set_fields,
         "$setOnInsert": {"user_id": user_id, "first_seen": _now(), "pm_active": False}},
        upsert=True)

async def get_all_pm_users() -> list:
    db = get_db()
    return await db.users.find({"pm_active": True}, {"user_id": 1}).to_list(None)

async def count_users() -> int:
    return await get_db().users.count_documents({})

async def count_groups() -> int:
    return await get_db().groups.count_documents({})

# ─── WARNINGS ─────────────────────────────────────────────
async def add_warning(group_id: int, user_id: int, admin_id: int, reason: str = None) -> int:
    db = get_db()
    await db.warnings.insert_one({"group_id": group_id, "user_id": user_id,
                                   "admin_id": admin_id, "reason": reason, "created_at": _now()})
    return await db.warnings.count_documents({"group_id": group_id, "user_id": user_id})

async def remove_last_warning(group_id: int, user_id: int) -> bool:
    db = get_db()
    doc = await db.warnings.find_one({"group_id": group_id, "user_id": user_id},
                                      sort=[("created_at", -1)])
    if not doc: return False
    await db.warnings.delete_one({"_id": doc["_id"]})
    return True

async def count_warnings(group_id: int, user_id: int) -> int:
    return await get_db().warnings.count_documents({"group_id": group_id, "user_id": user_id})

async def get_warnings(group_id: int, user_id: int) -> list:
    db = get_db()
    return await db.warnings.find({"group_id": group_id, "user_id": user_id})\
                             .sort("created_at", -1).to_list(None)

async def clear_warnings(group_id: int, user_id: int) -> None:
    await get_db().warnings.delete_many({"group_id": group_id, "user_id": user_id})

# ─── BLACKLIST ────────────────────────────────────────────
async def block(target_type: str, target_id: int, by: int) -> None:
    db = get_db()
    await db.blacklist.update_one({"type": target_type, "target_id": target_id},
        {"$set": {"blocked_by": by, "blocked_at": _now()}}, upsert=True)

async def unblock(target_type: str, target_id: int) -> bool:
    r = await get_db().blacklist.delete_one({"type": target_type, "target_id": target_id})
    return r.deleted_count > 0

async def is_blocked(target_type: str, target_id: int) -> bool:
    doc = await get_db().blacklist.find_one({"type": target_type, "target_id": target_id})
    return doc is not None

# ─── SCHEDULES ────────────────────────────────────────────
async def add_schedule(group_id: int, admin_id: int,
                        stype: str, time_str: str, text: str) -> str:
    db = get_db()
    doc = {"group_id": group_id, "admin_id": admin_id, "type": stype,
           "time": time_str, "text": text, "active": True,
           "created_at": _now(), "last_run": None}
    result = await db.schedules.insert_one(doc)
    return str(result.inserted_id)

async def get_active_schedules() -> list:
    db = get_db()
    return await db.schedules.find({"active": True}).to_list(None)

async def deactivate_schedule(schedule_id) -> None:
    from bson import ObjectId
    await get_db().schedules.update_one({"_id": ObjectId(schedule_id)},
                                         {"$set": {"active": False}})

async def mark_schedule_ran(schedule_id) -> None:
    from bson import ObjectId
    await get_db().schedules.update_one({"_id": ObjectId(schedule_id)},
                                         {"$set": {"last_run": _now()}})

# ─── LOGS ─────────────────────────────────────────────────
async def add_log(group_id: int, user_id: int, admin_id: int,
                   action: str, details: dict = None) -> None:
    await get_db().logs.insert_one({"group_id": group_id, "user_id": user_id,
                                     "admin_id": admin_id, "action": action,
                                     "details": details or {}, "created_at": _now()})

# ─── FLOOD TRACKING (anti-spam) ───────────────────────────
async def track_message(group_id: int, user_id: int, text: str) -> int:
    """Returns count of identical messages in last 10s."""
    from datetime import timedelta
    db = get_db()
    now = _now()
    window = now - timedelta(seconds=10)
    key = f"{group_id}:{user_id}:{hash(text)}"
    expires = now + timedelta(seconds=60)
    await db.flood_track.update_one({"key": key},
        {"$inc": {"count": 1}, "$set": {"expires_at": expires},
         "$setOnInsert": {"key": key, "created_at": now}}, upsert=True)
    doc = await db.flood_track.find_one({"key": key})
    return doc.get("count", 1) if doc else 1
