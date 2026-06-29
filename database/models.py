"""
MongoDB Collections Schema (reference only — no ORM, pure dicts):

moderation_logs:
  - group_id: int
  - user_id: int
  - admin_id: int
  - action: str
  - created_at: datetime (UTC)

warnings:
  - group_id: int
  - user_id: int
  - admin_id: int
  - reason: str | None
  - created_at: datetime (UTC)

group_configs:
  - group_id: int  (unique index)
  - welcome_message: str | None
  - goodbye_message: str | None
  - rules: str | None
  - warn_limit: int  (default 3)
  - created_at: datetime (UTC)
  - updated_at: datetime (UTC)
"""
