"""
Bauntys Production Telemetry va Database Flow Service
=====================================================
1. Real-time Neon PostgreSQL / SQLite Database Health Check & Latency Benchmark.
2. Live Row Counts: users, movies, downloads, expenses, calories, mafia_games.
3. In-memory Rolling Ring Buffer (last 200 requests across aiohttp web server).
4. Live Traffic Stats: RPM (Requests Per Minute), Success Rate %, Average/P95 Latency ms, Error Counters.
5. System Telemetry: Memory RSS (MB), Server Uptime, Python runtime, Platform info.
"""
import os
import sys
import time
import math
import logging
from collections import deque, defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import text, select, func
from config import config
from database.session import get_session, engine
from database.models import (
    User,
    Movie,
    DownloadLog,
    Expense,
    CalorieLogItem,
    MafiaGameRecord,
    utc_now,
)

logger = logging.getLogger("telemetry")


def get_process_memory_mb() -> float:
    """Jarayon xotira sarfini (RSS) aniqlash (Windows va Linux/Render uchun mos)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                wintypes.DWORD,
            ]
            ctypes.windll.psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / (1024 * 1024), 2)
        else:
            # Linux (Render.com)
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            parts = line.split()
                            return round(float(parts[1]) / 1024, 2)
            except Exception:
                pass
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == "darwin":
                return round(usage / (1024 * 1024), 2)
            return round(usage / 1024, 2)
    except Exception:
        pass
    return 0.0


def format_uptime_string(seconds: float) -> str:
    """Sekundlarni 'Xd Xh Xm Xs' formatiga o'tkazish."""
    s = int(seconds)
    days = s // 86400
    hours = (s % 86400) // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m {secs}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def mask_database_url(url_str: str) -> str:
    """Parol va maxfiy ma'lumotlarni yashirgan holda DB URL ni qaytarish."""
    if not url_str:
        return "N/A"
    try:
        if "@" in url_str and "://" in url_str:
            proto, rest = url_str.split("://", 1)
            auth, host_part = rest.split("@", 1)
            user = auth.split(":", 1)[0] if ":" in auth else auth
            return f"{proto}://{user}:******@{host_part}"
        return url_str
    except Exception:
        return "configured"


class TelemetryService:
    """
    Server va ma'lumotlar bazasi telemetriya boshqaruv xizmati.
    """

    def __init__(self, max_buffer_size: int = 200):
        self.max_buffer_size = max_buffer_size
        self._start_time = time.time()
        self._boot_time_iso = datetime.now(timezone.utc).isoformat()
        self._request_counter = 0

        # Ring buffer for recent requests
        self._recent_requests: deque = deque(maxlen=max_buffer_size)

        # Sliding window for RPM calculation (timestamps of requests within last 60 seconds)
        self._rpm_window: deque = deque(maxlen=2000)

        # Recent latencies for rolling average and p95
        self._recent_latencies: deque = deque(maxlen=200)

        # Global counters
        self._total_requests = 0
        self._errors_4xx = 0
        self._errors_5xx = 0
        self._success_2xx = 0
        self._redirect_3xx = 0

        # Endpoint distribution
        self._endpoint_counts: Dict[str, int] = defaultdict(int)

        # Cached last DB snapshot for resilience
        self._last_db_snapshot: Optional[Dict[str, Any]] = None
        self._last_db_check_ts: float = 0.0

    @property
    def start_time(self) -> float:
        return self._start_time

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._start_time

    def record_request(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        client_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Kelib tushgan HTTP so'rovni xotiradagi ring bufferga yozib qo'yish."""
        now = time.time()
        self._total_requests += 1
        self._request_counter += 1

        # Classify status
        if 200 <= status < 300:
            self._success_2xx += 1
        elif 300 <= status < 400:
            self._redirect_3xx += 1
        elif 400 <= status < 500:
            self._errors_4xx += 1
        elif status >= 500:
            self._errors_5xx += 1

        # RPM sliding window
        self._rpm_window.append(now)

        # Latencies
        self._recent_latencies.append(duration_ms)

        # Top endpoints count (limit path length and strip query for clean grouping)
        clean_path = path.split("?")[0] if path else "/"
        if len(self._endpoint_counts) < 500:
            self._endpoint_counts[clean_path] += 1
        elif clean_path in self._endpoint_counts:
            self._endpoint_counts[clean_path] += 1

        # Record item
        dt_now = datetime.now(timezone.utc)
        record = {
            "id": self._request_counter,
            "timestamp": dt_now.isoformat(),
            "time_str": dt_now.strftime("%H:%M:%S"),
            "method": method.upper() if method else "GET",
            "path": path[:128] if path else "/",
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip or "127.0.0.1",
            "user_agent": (user_agent[:100] + "...") if user_agent and len(user_agent) > 100 else (user_agent or "-"),
            "is_error": status >= 400,
        }

        self._recent_requests.appendleft(record)

    def clear_buffer(self) -> None:
        """Admin tomonidan so'rovlar buferini tozalash."""
        self._recent_requests.clear()
        self._recent_latencies.clear()

    def get_traffic_stats(self) -> Dict[str, Any]:
        """Trafik va so'rovlar oqimi statistikasini hisoblash."""
        now = time.time()
        cutoff_60s = now - 60.0

        # Prune old RPM entries
        while self._rpm_window and self._rpm_window[0] < cutoff_60s:
            self._rpm_window.popleft()
        rpm = len(self._rpm_window)

        # Latency calculations
        if self._recent_latencies:
            lat_list = list(self._recent_latencies)
            avg_lat = round(sum(lat_list) / len(lat_list), 2)
            sorted_lat = sorted(lat_list)
            p95_idx = min(len(sorted_lat) - 1, int(math.ceil(len(sorted_lat) * 0.95)) - 1)
            p95_lat = round(sorted_lat[p95_idx], 2)
            min_lat = round(sorted_lat[0], 2)
            max_lat = round(sorted_lat[-1], 2)
        else:
            avg_lat = 0.0
            p95_lat = 0.0
            min_lat = 0.0
            max_lat = 0.0

        # Success rate
        total = self._total_requests
        if total > 0:
            success_count = self._success_2xx + self._redirect_3xx
            success_rate = round((success_count / total) * 100, 2)
        else:
            success_rate = 100.0

        # Top endpoints sorted
        top_eps = sorted(
            [{"path": k, "count": v} for k, v in self._endpoint_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:8]

        return {
            "total_requests": self._total_requests,
            "rpm": rpm,
            "success_rate": success_rate,
            "avg_latency_ms": avg_lat,
            "p95_latency_ms": p95_lat,
            "min_latency_ms": min_lat,
            "max_latency_ms": max_lat,
            "errors_4xx": self._errors_4xx,
            "errors_5xx": self._errors_5xx,
            "status_distribution": {
                "2xx": self._success_2xx,
                "3xx": self._redirect_3xx,
                "4xx": self._errors_4xx,
                "5xx": self._errors_5xx,
            },
            "top_endpoints": top_eps,
        }

    def get_system_stats(self) -> Dict[str, Any]:
        """Tizim resurslari va server holatini olish."""
        uptime_sec = self.uptime_seconds
        mem_mb = get_process_memory_mb()
        import platform

        return {
            "name": "Bauntys Cinema Ecosystem Flow Monitor",
            "bot_username": f"@{config.BOT_USERNAME.lstrip('@')}",
            "channel_username": config.CHANNEL_USERNAME,
            "uptime_seconds": int(uptime_sec),
            "uptime_str": format_uptime_string(uptime_sec),
            "boot_time": self._boot_time_iso,
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "memory_mb": mem_mb,
            "port": config.PORT,
            "host": config.HOST,
            "webapp_url": config.webapp_url_resolved,
        }

    async def check_database_health(self) -> Dict[str, Any]:
        """
        Neon PostgreSQL / SQLite ma'lumotlar bazasi bilan real-vaqtdagi ulanishni tekshirish,
        ping kechikishini (ms) o'lchash va 6 ta asosiy jadvaldagi yozuvlar sonini hisoblash.
        """
        raw_db_url = config.db_url
        is_neon = "neon.tech" in raw_db_url
        is_postgres = "postgres" in raw_db_url
        engine_type = "Neon PostgreSQL" if is_neon else ("PostgreSQL" if is_postgres else "SQLite (WAL)")

        pool_class = engine.pool.__class__.__name__
        pool_status = f"{pool_class} (Serverless Cloud Pool)" if "Null" in pool_class else f"{pool_class} (Active)"

        t0 = time.perf_counter()
        ping_ms = -1.0
        status_str = "OFFLINE"
        db_error: Optional[str] = None
        table_counts = {
            "users": 0,
            "movies": 0,
            "downloads": 0,
            "expenses": 0,
            "calories": 0,
            "mafia_games": 0,
            "total_records": 0,
        }

        try:
            async with get_session() as session:
                # 1. Tezkor ping test (SELECT 1)
                await session.execute(text("SELECT 1"))
                ping_ms = round((time.perf_counter() - t0) * 1000, 2)
                status_str = "ONLINE"

                now = time.time()
                should_recount = (now - self._last_db_check_ts > 3.0) or (not self._last_db_snapshot) or ("table_counts" not in self._last_db_snapshot)

                if should_recount:
                    # 2. 6 ta asosiy jadvaldagi yozuvlar sonini olish (xavfsiz alohida tekshiruv bilan)
                    targets = [
                        ("users", User),
                        ("movies", Movie),
                        ("downloads", DownloadLog),
                        ("expenses", Expense),
                        ("calories", CalorieLogItem),
                        ("mafia_games", MafiaGameRecord),
                    ]

                    total_sum = 0
                    for tbl_key, model in targets:
                        try:
                            res = await session.execute(select(func.count()).select_from(model))
                            c = res.scalar() or 0
                            table_counts[tbl_key] = int(c)
                            total_sum += int(c)
                        except Exception as te:
                            logger.debug(f"{tbl_key} jadvalini hisoblashda xatolik: {te}")
                            table_counts[tbl_key] = 0

                    table_counts["total_records"] = total_sum
                else:
                    table_counts = self._last_db_snapshot["table_counts"]

        except Exception as e:
            db_error = str(e)
            if ping_ms >= 0:
                status_str = "DEGRADED"
            else:
                status_str = "OFFLINE"
                ping_ms = -1.0
            logger.warning(f"Ma'lumotlar bazasi telemetriya tekshiruvida xatolik: {e}")
            # Agar oldingi ma'lumotlar mavjud bo'lsa, xotiradagi oxirgi counts ni saqlab turamiz
            if self._last_db_snapshot and "table_counts" in self._last_db_snapshot:
                table_counts = self._last_db_snapshot["table_counts"]

        snapshot = {
            "status": status_str,
            "engine": engine_type,
            "db_url_masked": mask_database_url(raw_db_url),
            "ping_ms": ping_ms,
            "pool_status": pool_status,
            "table_counts": table_counts,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "error": db_error,
        }

        self._last_db_snapshot = snapshot
        self._last_db_check_ts = time.time()
        return snapshot

    async def get_full_telemetry(self) -> Dict[str, Any]:
        """Tizim, ma'lumotlar bazasi va trafik oqimi bo'yicha to'liq telemetriya ob'ekti."""
        system_data = self.get_system_stats()
        traffic_data = self.get_traffic_stats()
        database_data = await self.check_database_health()

        return {
            "ok": True,
            "server": system_data,
            "database": database_data,
            "traffic": traffic_data,
            "recent_requests": list(self._recent_requests),
            "timestamp": time.time(),
        }


# Global singleton nusxa
telemetry_service = TelemetryService(max_buffer_size=200)
