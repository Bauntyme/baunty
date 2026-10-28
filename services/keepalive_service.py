"""
Bauntys Keep-Alive & Anti-Sleep Service for Render.com.
Prevents the bot and web server from spinning down / sleeping by periodically pinging health endpoints.
"""
import os
import asyncio
import logging
from typing import List, Optional
import aiohttp
from config import config

logger = logging.getLogger("keepalive")

_keepalive_task: Optional[asyncio.Task] = None

# Default target endpoints to keep active on Render
TARGET_HEALTH_URLS: List[str] = [
    "https://baunty-cinema.onrender.com/health",
    "https://baunty-cinema.onrender.com/ping",
]

# Keep-alive headers mimicking UptimeRobot monitoring probe to pass all WAF / security middleware cleanly
KEEPALIVE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; UptimeRobot/2.0; BauntysKeepAlive/1.0; +http://www.uptimerobot.com/)",
    "Accept": "application/json, text/plain, */*",
    "Connection": "keep-alive",
}


async def ping_endpoint(session: aiohttp.ClientSession, url: str) -> bool:
    """Send a lightweight HTTP GET request to a health endpoint."""
    try:
        timeout = aiohttp.ClientTimeout(total=12.0, connect=5.0)
        async with session.get(url, headers=KEEPALIVE_HEADERS, timeout=timeout, ssl=False) as resp:
            status = resp.status
            if 200 <= status < 400:
                logger.debug(f"Keep-alive ping muvaffaqiyatli: {url} -> {status} OK")
                return True
            else:
                logger.debug(f"Keep-alive ping javobi: {url} -> {status}")
                return False
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.debug(f"Keep-alive ping xatosi ({url}): {e}")
        return False


async def _keepalive_loop(interval_seconds: int = 180) -> None:
    """
    Davriy tarzda Render healthcheck endpointlarini chaqirib,
    botning spin-down bo'lishi (o'chib qolishi)ni oldini oluvchi asinxron fon sikli.
    Render bepul tarifida 15 daqiqa (900s) harakatsizlikdan so'ng serverni uxlatadi.
    180s (3 daqiqa) oraliqdagi ping botni 24/7 faol ushlab turadi.
    """
    # Bot va web server to'liq ishga tushib olishi uchun dastlabki 10 soniya kutish
    await asyncio.sleep(10)
    logger.info("Render keep-alive (anti-sleep) monitoring xizmati ishga tushdi.")

    while True:
        try:
            urls = list(TARGET_HEALTH_URLS)
            app_url = config.webapp_url_resolved
            if app_url and app_url.startswith("https://"):
                resolved_health = f"{app_url.rstrip('/')}/health"
                if resolved_health not in urls:
                    urls.insert(0, resolved_health)

            render_ext = os.getenv("RENDER_EXTERNAL_URL", "").strip()
            if render_ext:
                if not render_ext.startswith("http://") and not render_ext.startswith("https://"):
                    render_ext = f"https://{render_ext}"
                r_health = f"{render_ext.rstrip('/')}/health"
                if r_health not in urls:
                    urls.insert(0, r_health)

            # Ichki loopback ping (event loop to'xtab qolmasligi uchun)
            local_port = getattr(config, "PORT", 8080)
            local_ping = f"http://127.0.0.1:{local_port}/ping"
            if local_ping not in urls:
                urls.append(local_ping)

            async with aiohttp.ClientSession() as session:
                for url in urls:
                    try:
                        await ping_endpoint(session, url)
                    except asyncio.CancelledError:
                        raise
                    except Exception as pe:
                        logger.debug(f"Pinger cycle error for {url}: {pe}")
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            logger.info("Keep-alive monitoring xizmati to'xtatildi.")
            break
        except Exception as ge:
            logger.warning(f"Keep-alive monitoring siklida kutilmagan xatolik: {ge}")

        await asyncio.sleep(interval_seconds)


def start_keepalive_service(interval_seconds: int = 180) -> asyncio.Task:
    """Keep-alive xizmatini ishga tushirish."""
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        return _keepalive_task
    _keepalive_task = asyncio.create_task(_keepalive_loop(interval_seconds))
    return _keepalive_task


def stop_keepalive_service() -> None:
    """Keep-alive xizmatini to'xtatish."""
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        _keepalive_task.cancel()
        _keepalive_task = None
