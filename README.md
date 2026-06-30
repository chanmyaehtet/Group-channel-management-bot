# 🤖 Group Channel Management Bot

Telegram group moderation bot — **Pyrogram + MongoDB (Motor)**

Runs on **Hugging Face Spaces (Docker Blank)** via long-polling. No web server required.

---

## 🔧 Environment Variables

Set these in Hugging Face Space → Settings → Repository secrets:

| Key | Description |
|-----|-------------|
| `BOT_TOKEN` | Telegram Bot Token from @BotFather |
| `API_ID` | Telegram API ID (my.telegram.org) |
| `API_HASH` | Telegram API Hash (my.telegram.org) |
| `MONGO_URI` | MongoDB Atlas connection string |
| `OWNER_IDS` | Comma-separated Telegram user IDs e.g. `123456,789012` |

---

## 🚀 Deploy on Hugging Face Spaces

1. Go to https://huggingface.co/new-space
2. Choose **Docker** → **Blank**
3. Connect this GitHub repo (or upload files)
4. Go to **Settings → Variables and secrets** → add all env vars above
5. Space will auto-build and run the bot ✅

---

## 📋 Commands

### Moderation (Admin only)
| Command | Action |
|---------|--------|
| `/kick` | Kick user from group |
| `/ban` | Ban user |
| `/unban` | Unban user |
| `/mute [seconds]` | Mute user |
| `/unmute` | Unmute user |
| `/warn [reason]` | Warn user (auto-ban at limit) |
| `/unwarn` | Remove latest warning |
| `/warnings` | Show user's warnings |

### Group Config (Admin only)
| Command | Action |
|---------|--------|
| `/setwelcome [msg]` | Set welcome message |
| `/setgoodbye [msg]` | Set goodbye message |
| `/setrules [text]` | Set group rules |
| `/rules` | Show rules |
| `/setwarnlimit [n]` | Set warning limit (default 3) |

### System
| Command | Response |
|---------|----------|
| `/start` | ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ |
| `/ping` | ᴘᴏɴɢ! 🏓 |

---

## 📁 Project Structure

```
├── main.py               # Entry point — starts bot with asyncio
├── requirements.txt
├── Dockerfile            # HF Spaces Docker Blank
├── bot/
│   ├── client.py         # Pyrogram client
│   ├── utils.py          # Admin checks, cooldown, logging
│   └── handlers/
│       ├── moderation.py # kick, ban, mute, warn ...
│       └── system.py     # start, ping, welcome, rules ...
└── database/
    ├── connection.py     # Motor async MongoDB client
    └── models.py         # Collection schema reference
```
