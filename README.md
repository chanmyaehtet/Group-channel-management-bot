# 🤖 Group Channel Management Bot

Telegram group moderation bot built with **Pyrogram** + **MongoDB** (Motor) + **FastAPI**.

## Environment Variables (Render)

| Key | Description |
|-----|-------------|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash from my.telegram.org |
| `MONGO_URI` | MongoDB connection string |
| `OWNER_IDS` | Comma-separated Telegram user IDs (e.g. `123456,789012`) |
| `API_TOKEN` | Optional: secret token for REST API access |

## Commands

### Moderation (Admin only)
- `/kick` — Kick user
- `/ban` — Ban user
- `/unban` — Unban user
- `/mute [seconds]` — Mute user
- `/unmute` — Unmute user
- `/warn [reason]` — Warn user (auto-ban at warn limit)
- `/unwarn` — Remove latest warning
- `/warnings` — View user warnings

### Group Config (Admin only)
- `/setwelcome [msg]` — Set welcome message
- `/setgoodbye [msg]` — Set goodbye message
- `/setrules [text]` — Set group rules
- `/rules` — Show group rules
- `/setwarnlimit [n]` — Set warning limit (default: 3)

### System
- `/start` — ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ
- `/ping` — ᴘᴏɴɢ! 🏓

## REST API Endpoints

All endpoints require `X-API-Token` header (if `API_TOKEN` env is set).

- `GET /api/health`
- `GET /api/logs?group_id=&user_id=&action=`
- `GET /api/warns/{user_id}`
- `GET /api/groups`
- `GET /api/stats`

## Deploy on Render

1. Connect this GitHub repo to Render
2. Set all environment variables listed above
3. Deploy — Render will auto-build and run
4. Copy the `https://....onrender.com` URL → add to UptimeRobot (HTTP monitor, every 5 min)
