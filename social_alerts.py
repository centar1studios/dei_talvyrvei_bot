import os
import httpx
import asyncio
import discord
import datetime
import random
 
# ── ENV ──
DASHBOARD_URL    = os.getenv("DASHBOARD_URL", "")
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "")
GUILD_ID         = os.getenv("GUILD_ID", "")
 
TWITTER_BEARER   = os.getenv("TWITTER_BEARER_TOKEN", "")
INSTAGRAM_TOKEN  = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_UID    = os.getenv("INSTAGRAM_USER_ID", "")
 
def _headers():
    return {
        "Authorization": f"Bearer {DASHBOARD_SECRET}",
        "Content-Type": "application/json",
    }
 
# In-memory last seen IDs (backed up to D1 via API on each check)
_last_seen: dict[str, str] = {}
 
# Platform colours
COLORS = {
    "twitter":   0x1da1f2,
    "instagram": 0xe1306c,
    "tiktok":    0x010101,
    "twitch":    0x9146ff,
    "youtube":   0xff0000,
}
 
PLATFORM_LABELS = {
    "twitter":   "Twitter / X",
    "instagram": "Instagram",
    "tiktok":    "TikTok",
    "twitch":    "Twitch",
    "youtube":   "YouTube",
}
 
PLATFORM_ICONS = {
    "twitter":   "🐦",
    "instagram": "📸",
    "tiktok":    "🎵",
    "twitch":    "🟣",
    "youtube":   "📹",
}
 
 
async def fetch_alerts() -> list[dict]:
    """Fetch all enabled social alerts from the dashboard API."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{DASHBOARD_URL}/api/social-alerts",
                headers=_headers(),
                params={"guild_id": GUILD_ID},
            )
            data = resp.json()
            return [a for a in data.get("alerts", []) if a.get("enabled")]
    except Exception as e:
        print(f"[Social] Failed to fetch alerts: {e}")
        return []
 
 
async def update_last_seen(alert_id: int, post_id: str):
    """Update the last seen post ID in D1."""
    if not DASHBOARD_URL or not DASHBOARD_SECRET:
        return
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.put(
                f"{DASHBOARD_URL}/api/social-alerts",
                headers=_headers(),
                json={"id": alert_id, "last_post_id": post_id},
            )
    except Exception as e:
        print(f"[Social] Failed to update last_post_id: {e}")
 
 
def build_embed(platform: str, title: str, description: str, url: str,
                image_url: str = None, author_name: str = None,
                custom_message: str = None) -> discord.Embed:
    icon  = PLATFORM_ICONS.get(platform, "")
    label = PLATFORM_LABELS.get(platform, platform.title())
    color = COLORS.get(platform, 0xc4b0f5)
 
    embed = discord.Embed(
        title=f"{icon} {title}",
        description=(f"{custom_message}\n\n" if custom_message else "") + description,
        url=url,
        color=color,
        timestamp=datetime.datetime.utcnow(),
    )
    if author_name:
        embed.set_author(name=author_name)
    if image_url:
        embed.set_image(url=image_url)
    embed.set_footer(text=label)
    return embed
 
 
# ─────────────────────────────────────────────
# TWITTER / X
# ─────────────────────────────────────────────
 
async def check_twitter(bot: discord.Client, alert: dict):
    """Poll Twitter for new tweets from a user."""
    if not TWITTER_BEARER:
        return
 
    username = alert.get("target_username", "").lstrip("@")
    user_id  = alert.get("target_id")
    key      = f"twitter:{user_id or username}"
 
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Resolve user ID if we only have username
            if not user_id and username:
                r = await client.get(
                    f"https://api.twitter.com/2/users/by/username/{username}",
                    headers={"Authorization": f"Bearer {TWITTER_BEARER}"},
                )
                if r.status_code == 200:
                    user_id = r.json()["data"]["id"]
                else:
                    print(f"[Twitter] Could not resolve @{username}: {r.status_code}")
                    return
 
            if not user_id:
                return
 
            # Fetch latest tweets
            params = {
                "max_results": 5,
                "tweet.fields": "created_at,attachments",
                "expansions": "attachments.media_keys",
                "media.fields": "url,preview_image_url,type",
                "exclude": "retweets,replies",
            }
            if _last_seen.get(key):
                params["since_id"] = _last_seen[key]
 
            r = await client.get(
                f"https://api.twitter.com/2/users/{user_id}/tweets",
                headers={"Authorization": f"Bearer {TWITTER_BEARER}"},
                params=params,
            )
 
            if r.status_code != 200:
                print(f"[Twitter] Error {r.status_code}: {r.text[:200]}")
                return
 
            data = r.json()
            tweets = data.get("data", [])
            if not tweets:
                return
 
            # Post newest first (they come newest-first)
            for tweet in reversed(tweets):
                tweet_id = tweet["id"]
                if _last_seen.get(key) and tweet_id <= _last_seen.get(key, "0"):
                    continue
 
                channel = bot.get_channel(int(alert["discord_channel_id"]))
                if not channel:
                    continue
 
                tweet_url = f"https://twitter.com/{username}/status/{tweet_id}"
                embed = build_embed(
                    "twitter",
                    f"@{username} posted a new tweet",
                    tweet["text"],
                    tweet_url,
                    custom_message=alert.get("custom_message"),
                    author_name=f"@{username}",
                )
                await channel.send(embed=embed)
                _last_seen[key] = tweet_id
 
            await update_last_seen(alert["id"], _last_seen.get(key, ""))
 
    except Exception as e:
        print(f"[Twitter] Error checking @{username}: {e}")
 
 
# ─────────────────────────────────────────────
# INSTAGRAM
# ─────────────────────────────────────────────
 
async def check_instagram(bot: discord.Client, alert: dict):
    """Poll Instagram Graph API for new posts."""
    if not INSTAGRAM_TOKEN or not INSTAGRAM_UID:
        return
 
    key = f"instagram:{INSTAGRAM_UID}"
 
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://graph.instagram.com/{INSTAGRAM_UID}/media",
                params={
                    "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
                    "access_token": INSTAGRAM_TOKEN,
                    "limit": 5,
                }
            )
            if r.status_code != 200:
                print(f"[Instagram] Error {r.status_code}: {r.text[:200]}")
                return
 
            posts = r.json().get("data", [])
            if not posts:
                return
 
            username = alert.get("target_username", "").lstrip("@")
 
            for post in reversed(posts):
                post_id = post["id"]
                if post_id == _last_seen.get(key):
                    break
 
                channel = bot.get_channel(int(alert["discord_channel_id"]))
                if not channel:
                    continue
 
                caption   = (post.get("caption") or "")[:300]
                media_url = post.get("media_url") or post.get("thumbnail_url")
                media_type = post.get("media_type", "IMAGE")
                icon_map = {"IMAGE": "🖼️", "VIDEO": "🎬", "CAROUSEL_ALBUM": "🗂️"}
                type_label = icon_map.get(media_type, "📷")
 
                embed = build_embed(
                    "instagram",
                    f"{type_label} {username or 'New post'} on Instagram",
                    caption or "New post",
                    post.get("permalink", "https://instagram.com"),
                    image_url=media_url if alert.get("include_preview") else None,
                    custom_message=alert.get("custom_message"),
                    author_name=f"@{username}" if username else None,
                )
                await channel.send(embed=embed)
                _last_seen[key] = post_id
 
            await update_last_seen(alert["id"], _last_seen.get(key, ""))
 
    except Exception as e:
        print(f"[Instagram] Error: {e}")
 
 
# ─────────────────────────────────────────────
# TIKTOK (public RSS - unofficial, may break)
# ─────────────────────────────────────────────
 
async def check_tiktok(bot: discord.Client, alert: dict):
    """
    Attempt to detect new TikToks via public RSS feeds.
    TikTok has no official API for this. This may stop working if TikTok
    changes their site structure. Works best for accounts with public profiles.
    """
    username = alert.get("target_username", "").lstrip("@")
    key      = f"tiktok:{username}"
 
    if not username:
        return
 
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0"}) as client:
            # Try unofficial RSS endpoint
            r = await client.get(f"https://www.tiktok.com/@{username}/rss")
 
            if r.status_code != 200:
                # Fallback: check if profile page changed (rough heuristic)
                print(f"[TikTok] RSS not available for @{username} (status {r.status_code})")
                return
 
            feed = r.text
 
            # Parse latest video link from RSS
            import re
            items = re.findall(r'<item>(.*?)</item>', feed, re.DOTALL)
            if not items:
                return
 
            latest = items[0]
            link_match = re.search(r'<link>(.*?)</link>', latest)
            title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', latest)
            img_match = re.search(r'<enclosure url="([^"]+)"', latest)
 
            if not link_match:
                return
 
            link = link_match.group(1).strip()
            title = title_match.group(1).strip() if title_match else "New TikTok"
            img_url = img_match.group(1) if img_match else None
 
            # Generate a post ID from the link
            post_id = link.split("/")[-1].split("?")[0]
 
            if post_id == _last_seen.get(key):
                return
 
            channel = bot.get_channel(int(alert["discord_channel_id"]))
            if not channel:
                return
 
            embed = build_embed(
                "tiktok",
                f"🎵 @{username} posted a new TikTok",
                title,
                link,
                image_url=img_url if alert.get("include_preview") else None,
                custom_message=alert.get("custom_message"),
                author_name=f"@{username}",
            )
            await channel.send(embed=embed)
            _last_seen[key] = post_id
            await update_last_seen(alert["id"], post_id)
 
    except Exception as e:
        print(f"[TikTok] Error checking @{username}: {e}")
 
 
# ─────────────────────────────────────────────
# MAIN POLL LOOP
# ─────────────────────────────────────────────
 
async def run_social_polls(bot: discord.Client):
    """
    Background coroutine - call this from bot's on_ready.
    Polls Twitter, Instagram, and TikTok every 5 minutes.
    Twitch and YouTube are handled via Cloudflare webhooks.
    """
    await bot.wait_until_ready()
    print("[Social] Polling started")
 
    # Stagger initial checks
    await asyncio.sleep(30)
 
    while not bot.is_closed():
        try:
            alerts = await fetch_alerts()
 
            # Load last_seen from DB into memory on first run
            for alert in alerts:
                key = f"{alert['platform']}:{alert.get('target_id') or alert.get('target_username','')}"
                if key not in _last_seen and alert.get("last_post_id"):
                    _last_seen[key] = alert["last_post_id"]
 
            # Poll polling-based platforms
            for alert in alerts:
                platform = alert.get("platform")
                try:
                    if platform == "twitter":
                        await check_twitter(bot, alert)
                        await asyncio.sleep(2)  # rate limit buffer
                    elif platform == "instagram":
                        await check_instagram(bot, alert)
                        await asyncio.sleep(2)
                    elif platform == "tiktok":
                        await check_tiktok(bot, alert)
                        await asyncio.sleep(2)
                    # twitch + youtube are webhook-based - no polling needed
                except Exception as e:
                    print(f"[Social] Error in {platform} poll: {e}")
 
        except Exception as e:
            print(f"[Social] Poll loop error: {e}")
 
        # Poll every 5 minutes
        await asyncio.sleep(300)
