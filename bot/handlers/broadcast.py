"""
broadcast.py — kept for reference only.

BUG FIX: /broadcast duplicate handler removed.
owner.py already registers /broadcast with a more complete implementation
(supports all / group / user targeting). Registering it twice caused
the second handler to shadow or double-fire depending on PTB handler groups.

This module no longer registers any command handler.
"""
from telegram.ext import Application


def register(app: Application):
    # No handlers registered here — /broadcast is handled by owner.py
    pass
