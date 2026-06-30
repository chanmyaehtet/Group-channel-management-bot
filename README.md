---
title: My Telegram Bot
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 🤖 Group Channel Management Bot

Telegram group moderation bot — **python-telegram-bot v21 + MongoDB (Motor)**

## 🔧 Required Secrets (HF Space → Settings → Variables and secrets)

| Secret | Value |
|--------|-------|
| `BOT_TOKEN` | Token from @BotFather |
| `MONGO_URI` | MongoDB Atlas connection string |
| `OWNER_IDS` | Your Telegram numeric user ID (e.g. `123456789`) |

> ✅ No API_ID or API_HASH needed!

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | ᴛʏᴘᴇ ꜱᴏᴍᴇᴛʜɪɴɢ ᴛᴏ ꜱᴛᴀʀᴛ |
| `/ping` | ᴘᴏɴɢ! 🏓 |
| `/kick` | Kick user |
| `/ban` | Ban user |
| `/unban` | Unban user |
| `/mute [sec]` | Mute user |
| `/unmute` | Unmute user |
| `/warn [reason]` | Warn user |
| `/unwarn` | Remove last warning |
| `/warnings` | Show warnings |
| `/setwelcome` | Set welcome message |
| `/setgoodbye` | Set goodbye message |
| `/setrules` | Set group rules |
| `/rules` | Show rules |
| `/setwarnlimit` | Set auto-ban limit |
| `/broadcast all <msg>` | Send to all groups (owner only) |
| `/broadcast <id> <msg>` | Send to specific group (owner only) |
