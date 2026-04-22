import os
import httpx
import asyncio
 
DASHBOARD_URL    = os.getenv("DASHBOARD_URL", "")
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "")
GUILD_ID         = os.getenv("GUILD_ID", "")
 
def _headers():
    return {
        "Authorization": f"Bearer {DASHBOARD_SECRET}",
        "Content-Type": "application/json",
    }
 
async def post_mod_log(action: str, moderator: str, target: str = None, reason: str = None):
    """Call this whenever a mod action happens."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/logs",
                headers=_headers(),
                json={
                    "guild_id":  GUILD_ID,
                    "action":    action,
                    "moderator": moderator,
                    "target":    target,
                    "reason":    reason,
                }
            )
    except Exception as e:
        print(f"[API] Failed to post mod log: {e}")
 
 
async def post_warning(user_id: str, username: str, reason: str, moderator: str):
    """Call this when a warning is issued."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/warnings",
                headers=_headers(),
                json={
                    "guild_id":  GUILD_ID,
                    "user_id":   user_id,
                    "username":  username,
                    "reason":    reason,
                    "moderator": moderator,
                }
            )
    except Exception as e:
        print(f"[API] Failed to post warning: {e}")
 
 
async def post_birthday(user_id: str, username: str, month: int, day: int):
    """Call this when someone registers their birthday."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/birthdays",
                headers=_headers(),
                json={
                    "guild_id": GUILD_ID,
                    "user_id":  user_id,
                    "username": username,
                    "month":    month,
                    "day":      day,
                }
            )
    except Exception as e:
        print(f"[API] Failed to post birthday: {e}")
 
 
async def post_reaction_role(message_id: str, emoji: str, role_id: str, role_name: str = None):
    """Call this when a reaction role is added via /reactionrole."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/reaction-roles",
                headers=_headers(),
                json={
                    "guild_id":   GUILD_ID,
                    "message_id": message_id,
                    "emoji":      emoji,
                    "role_id":    role_id,
                    "role_name":  role_name,
                }
            )
    except Exception as e:
        print(f"[API] Failed to post reaction role: {e}")
 
 
async def update_stats(member_count: int, messages_today: int = 0):
    """Call this periodically to update server stats."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/stats",
                headers=_headers(),
                json={
                    "guild_id":       GUILD_ID,
                    "member_count":   member_count,
                    "messages_today": messages_today,
                }
            )
    except Exception as e:
        print(f"[API] Failed to update stats: {e}")
