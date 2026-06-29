import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from database.connection import get_db

router = APIRouter(prefix="/api")

API_TOKEN = os.getenv("API_TOKEN", "")
api_key_header = APIKeyHeader(name="X-API-Token", auto_error=False)


def verify_token(token: str = Security(api_key_header)):
    if API_TOKEN and token != API_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid API token")
    return token


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@router.get("/logs")
async def get_logs(
    skip: int = 0, limit: int = 100,
    group_id: Optional[int] = None,
    user_id: Optional[int] = None,
    admin_id: Optional[int] = None,
    action: Optional[str] = None,
    token: str = Security(verify_token),
):
    db = get_db()
    query: Dict[str, Any] = {}
    if group_id: query["group_id"] = group_id
    if user_id: query["user_id"] = user_id
    if admin_id: query["admin_id"] = admin_id
    if action: query["action"] = {"$regex": action, "$options": "i"}

    cursor = db.moderation_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    logs = await cursor.to_list(length=limit)
    for log in logs:
        if isinstance(log.get("created_at"), datetime):
            log["created_at"] = log["created_at"].isoformat()
    return logs


@router.get("/warns/{user_id}")
async def get_user_warnings(
    user_id: int,
    group_id: Optional[int] = None,
    token: str = Security(verify_token),
):
    db = get_db()
    query: Dict[str, Any] = {"user_id": user_id}
    if group_id: query["group_id"] = group_id
    cursor = db.warnings.find(query, {"_id": 0}).sort("created_at", -1)
    warns = await cursor.to_list(length=None)
    for w in warns:
        if isinstance(w.get("created_at"), datetime):
            w["created_at"] = w["created_at"].isoformat()
    return warns


@router.get("/groups")
async def get_groups(
    skip: int = 0, limit: int = 100,
    token: str = Security(verify_token),
):
    db = get_db()
    cursor = db.group_configs.find({}, {"_id": 0}).skip(skip).limit(limit)
    groups = await cursor.to_list(length=limit)
    for g in groups:
        for key in ("created_at", "updated_at"):
            if isinstance(g.get(key), datetime):
                g[key] = g[key].isoformat()
    return groups


@router.get("/stats")
async def get_stats(token: str = Security(verify_token)):
    db = get_db()
    total_groups = await db.group_configs.count_documents({})
    total_warnings = await db.warnings.count_documents({})
    total_actions = await db.moderation_logs.count_documents({})

    # Unique users
    unique_users = await db.moderation_logs.distinct("user_id")
    total_users = len(unique_users)

    # Actions by type (aggregate)
    pipeline_actions = [{"$group": {"_id": "$action", "count": {"$sum": 1}}}]
    actions_by_type = {
        doc["_id"]: doc["count"]
        async for doc in db.moderation_logs.aggregate(pipeline_actions)
    }

    # Most active groups
    pipeline_groups = [
        {"$group": {"_id": "$group_id", "action_count": {"$sum": 1}}},
        {"$sort": {"action_count": -1}},
        {"$limit": 5},
    ]
    most_active_groups = [
        {"group_id": doc["_id"], "action_count": doc["action_count"]}
        async for doc in db.moderation_logs.aggregate(pipeline_groups)
    ]

    # Most warned users
    pipeline_warned = [
        {"$group": {"_id": "$user_id", "warning_count": {"$sum": 1}}},
        {"$sort": {"warning_count": -1}},
        {"$limit": 5},
    ]
    most_warned_users = [
        {"user_id": doc["_id"], "warning_count": doc["warning_count"]}
        async for doc in db.warnings.aggregate(pipeline_warned)
    ]

    return {
        "total_groups": total_groups,
        "total_users": total_users,
        "total_warnings": total_warnings,
        "total_actions": total_actions,
        "actions_by_type": actions_by_type,
        "most_active_groups": most_active_groups,
        "most_warned_users": most_warned_users,
    }
