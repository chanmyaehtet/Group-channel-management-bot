"""
Auto-delete middleware for group command messages and bot replies.

How it works:
  1. AutoDeleteApplication.process_update() detects group command messages
     (messages that start with '/') and sets a ContextVar that holds:
       - the target chat_id
       - a list of Message objects to delete later

  2. TrackingBot.send_message() checks the ContextVar on every outgoing message.
     If the sent message's chat_id matches the tracked chat_id, it appends
     the Message to the deletion list.

  3. After the update has been fully processed, _delete_after() is scheduled
     as an asyncio task — it sleeps AUTO_DELETE_DELAY seconds then deletes
     every collected message (command + all bot replies).

     Commands in _KEEP_CMDS are NEVER auto-deleted because users need to
     read/copy from their output (e.g. schedule IDs, rules text, warnings list).

Why ContextVar?
  asyncio.ContextVar is per-Task. Because PTB processes each update inside
  a single coroutine chain (no new tasks between process_update() and the
  actual handler), the ContextVar is naturally isolated per update.
"""

import asyncio
from contextvars import ContextVar
from typing import Optional, Tuple, List

from telegram import Bot, Message, Update
from telegram.ext import Application

# Holds (chat_id, messages_list) while processing a group command, else None.
_pending: ContextVar[Optional[Tuple[int, List[Message]]]] = ContextVar(
    "_auto_delete_pending", default=None
)

# 5 minutes — gives users enough time to read bot replies before they disappear.
AUTO_DELETE_DELAY = 300

# These commands produce output the user must READ AND ACT ON (IDs, lists, etc.)
# Their messages are never auto-deleted so the user can always refer back.
_KEEP_CMDS = frozenset({
    "listschedules",
    "rules",
    "warnings",
    "id",
    "info",
    "listgroups",
    "listusers",
    "status",
    "start",
})


class TrackingBot(Bot):
    """
    Bot subclass that intercepts every send_message() call.
    If a group command update is currently being processed (ContextVar is set)
    and the destination chat matches, the sent message is queued for deletion.
    """

    async def send_message(self, chat_id, text, *args, **kwargs) -> Message:  # type: ignore[override]
        msg: Message = await super().send_message(chat_id, text, *args, **kwargs)
        state = _pending.get()
        if state is not None:
            target_chat_id, queue = state
            # Only track messages sent to the same group where the command was issued
            if msg.chat_id == target_chat_id:
                queue.append(msg)
        return msg


class AutoDeleteApplication(Application):
    """
    Application subclass that wraps process_update() to enable auto-deletion
    of group command messages and all bot replies within that update.
    """

    async def process_update(self, update: object) -> None:  # type: ignore[override]
        if not isinstance(update, Update):
            await super().process_update(update)
            return

        msg = update.message
        chat = update.effective_chat

        # Only activate for group/supergroup command messages
        is_group_command = (
            msg is not None
            and chat is not None
            and chat.type in ("group", "supergroup")
            and msg.text is not None
            and msg.text.startswith("/")
        )

        if not is_group_command:
            await super().process_update(update)
            return

        # Extract bare command name (strip leading /, bot mention, and args)
        raw_cmd = msg.text.split()[0].lstrip("/").split("@")[0].lower()

        # For "keep" commands, process normally without any auto-delete
        if raw_cmd in _KEEP_CMDS:
            await super().process_update(update)
            return

        # Seed the deletion queue with the command message itself
        to_delete: List[Message] = [msg]
        token = _pending.set((chat.id, to_delete))
        try:
            await super().process_update(update)
        finally:
            _pending.reset(token)

        # Schedule deletion — fire-and-forget task
        asyncio.create_task(_delete_after(to_delete, AUTO_DELETE_DELAY))


async def _delete_after(messages: List[Message], delay: int) -> None:
    """Sleep `delay` seconds, then silently delete every message in the list."""
    await asyncio.sleep(delay)
    for message in messages:
        try:
            await message.delete()
        except Exception:
            pass
