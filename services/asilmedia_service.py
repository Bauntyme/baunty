"""
Asilmedia.org integratsiya xizmati.
Kinolar, seriallar, animelar va multfilmlarni qidirish,
sahifalarini tahlil qilish (parser), qismlarini (1..N) ajratish
va to'g'ridan-to'g'ri video manbalarini olish.
100% Bauntys brendi (@Bauntyfilmsbot, @BauntyFilms).
"""
import os
import re
import json
import time
import asyncio
import logging
import urllib.parse
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
import aiohttp
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from config import config, BASE_DIR
from utils.translit import get_both_scripts

logger = logging.getLogger(__name__)


@dataclass
class AsilmediaEpisode:
    """Serial yoki multfilmning alohida qismi."""
    part: int
    label: str
    url: str
    season: int = 1
    episode: int = 1
    quality: str = "1080p"
    watch_url: Optional[str] = None
    download_url: Optional[str] = None
    file_type: str = "video"
    file_size: Optional[int] = None
    duration: Optional[int] = None
    source: str = "asilmedia"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AsilmediaMovie:
    """Asilmedia filmi yoki seriali to'liq ma'lumotlari."""
    id: str
    title: str
    url: str
    orig_title: Optional[str] = None
    year: Optional[int] = None
    genres: List[str] = field(default_factory=list)
    description: Optional[str] = None
    poster: Optional[str] = None
    rating: Optional[float] = None
    duration: Optional[str] = None
    is_series: bool = False
    total_parts: int = 1
    episodes: Dict[int, AsilmediaEpisode] = field(default_factory=dict)
    video_sources: Dict[str, str] = field(default_factory=dict)
    watch_url: Optional[str] = None
    download_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["episodes"] = {str(k): v.to_dict() if hasattr(v, "to_dict") else v for k, v in self.episodes.items()}
        return d


class AsilmediaService:
    """Asilmedia.org bilan to'liq avtomatlashtirilgan ishlash xizmati."""

    BASE_URL = "https://asilmedia.org"
    MIRRORS = ["https://asilmedia.org", "https://asilmedia.net"]
    STREAM_SERVER_URL = "https://server.asilmedia.org"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    DEFAULT_TIMEOUT = 10

    def __init__(self):
        self._cache_dir = BASE_DIR / "data" / "asilmedia_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._search_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._details_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def _get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
            "Referer": referer or self.BASE_URL,
        }

    @staticmethod
    def clean_title(title: str) -> str:
        """Sarlavhadagi ortiqcha texnik so'zlarni tozalash."""
        if not title:
            return ""
        # Ortiqcha reklama va format yozuvlarini olib tashlash
        patterns = [
            r"O['`ʻʼ]zbek\s+tilida",
            r"Uzbek\s+tilida",
            r"O['`ʻʼ]zbekcha\s+tarjima",
            r"tarjima\s+kino",
            r"tas-ix\s+skachat",
            r"Full\s+HD",
            r"HD",
            r"skachat",
            r"download",
            r"Barcha\s+qismlar(?:i)?",
            r"seriali",
            r"filmi",
            r"premyera",
        ]
        res = title
        for p in patterns:
            res = re.sub(p, "", res, flags=re.IGNORECASE)
        # Ortiqcha probellar va chiziqchalarni tozalash
        res = re.sub(r"[\s\-_/|]+$", "", res)
        res = re.sub(r"^[\s\-_/|]+", "", res)
        res = re.sub(r"\s{2,}", " ", res).strip()
        return res or title.strip()

    @staticmethod
    def parse_episode_label(label: str, fallback_index: int = 1) -> Tuple[int, int, str]:
        """
        Qism sarlavhasidan (fasl, qism, sifat) ni ajratish.
        Masalan:
        - "1-fasl 1-qism 1080p" -> (1, 1, "1080p")
        - "4-fasl 5-qism 480p"  -> (4, 5, "480p")
        - "720p Taksi-2 / HD"   -> (1, 2, "720p")
        - "12-qism Full HD"     -> (1, 12, "1080p")
        """
        quality = "1080p"
        if "480p" in label.lower():
            quality = "480p"
        elif "720p" in label.lower():
            quality = "720p"
        elif "1080p" in label.lower():
            quality = "1080p"
        elif "2160p" in label.lower() or "4k" in label.lower():
            quality = "4K"

        # 1. "1-fasl 2-qism"
        m_fp = re.search(r"(\d+)\s*[-_]?\s*fasl\s*(\d+)\s*[-_]?\s*qism", label, re.I)
        if m_fp:
            return int(m_fp.group(1)), int(m_fp.group(2)), quality

        # 2. "Taksi-2" yoki "Taksi 3"
        m_taksi = re.search(r"taksi\s*[-_]?\s*(\d+)", label, re.I)
        if m_taksi:
            return 1, int(m_taksi.group(1)), quality

        # 3. "5-qism" yoki "qism 5"
        m_q = re.search(r"(\d+)\s*[-_]?\s*qism", label, re.I)
        if m_q:
            return 1, int(m_q.group(1)), quality

        m_q2 = re.search(r"qism\s*[-_]?\s*(\d+)", label, re.I)
        if m_q2:
            return 1, int(m_q2.group(1)), quality

        # 4. "Part 3" yoki "Ep 4"
        m_part = re.search(r"\b(?:part|ep|seriya)\s*[-_]?\s*(\d+)\b", label, re.I)
        if m_part:
            return 1, int(m_part.group(1)), quality

        # 5. Fallback raqam
        m_any = re.search(r"\b(\d+)\b", label)
        if m_any:
            val = int(m_any.group(1))
            if 1 <= val <= 2000:
                return 1, val, quality

        return 1, fallback_index, quality

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Asilmedia.org qidiruv tizimidan kinolarni topish.
        Lotin va Kirill tillarini qo'llab-quvvatlaydi.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        # Keshni tekshirish (15 daqiqa)
        cache_key = clean_q.lower()
        now = time.time()
        if cache_key in self._search_cache:
            ts, cached_res = self._search_cache[cache_key]
            if now - ts < 900:
                return cached_res[:limit]

        results: List[Dict[str, Any]] = []
        queries_to_try = list(get_both_scripts(clean_q))
        if clean_q not in queries_to_try:
            queries_to_try.insert(0, clean_q)

        async with aiohttp.ClientSession(headers=self._get_headers()) as session:
            for q in queries_to_try:
                for base_url in self.MIRRORS:
                    try:
                        # DLE qidiruv parametri: do=search&subaction=search&story=...
                        search_url = f"{base_url}/"
                        params = {"do": "search", "subaction": "search", "story": q}
                        async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)) as resp:
                            if resp.status == 200:
                                html = await resp.text()
                                parsed = self._parse_search_results(html)
                                for item in parsed:
                                    if not any(x["url"] == item["url"] for x in results):
                                        results.append(item)
                                if results:
                                    break
                    except Exception as e:
                        logger.debug(f"Asilmedia search error on {base_url} for '{q}': {e}")

                # Agar GET da topilmasa, POST orqali ham urinib ko'rish
                if not results:
                    for base_url in self.MIRRORS:
                        try:
                            search_url = f"{base_url}/"
                            params = {"do": "search", "subaction": "search", "story": q}
                            async with session.post(search_url, data=params, timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)) as resp:
                                if resp.status == 200:
                                    html = await resp.text()
                                    parsed = self._parse_search_results(html)
                                    for item in parsed:
                                        if not any(x["url"] == item["url"] for x in results):
                                            results.append(item)
                                    if results:
                                        break
                        except Exception as e:
                            logger.debug(f"Asilmedia POST search error on {base_url} for '{q}': {e}")

        # Keshga saqlash
        self._search_cache[cache_key] = (now, results)
        return results[:limit]

    def _parse_search_results(self, html: str) -> List[Dict[str, Any]]:
        """Qidiruv natijalari HTML sahifasini tahlil qilish."""
        soup = BeautifulSoup(html, "html.parser")
        items: List[Dict[str, Any]] = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            # Asilmedia kino sahifalari formati: /{id}-{slug}.html
            m = re.search(r"/(\d+)-([^/]+)\.html", href, re.I)
            if not m:
                continue

            full_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            movie_id = m.group(1)
            title_elem = a.find(class_=re.compile(r"title", re.I)) or a.find(attrs={"itemprop": "name"})
            if title_elem:
                raw_title = title_elem.get_text(strip=True)
            else:
                raw_title = a.get("title") or a.get("aria-label") or ""
            if not raw_title:
                img = a.find("img")
                if img:
                    raw_title = img.get("alt", "")
            if not raw_title:
                raw_title = a.get_text(strip=True) or ""

            # Sarlavhani tozalash
            title = self.clean_title(raw_title)
            if not title:
                continue

            # Poster
            poster_url = None
            parent_card = a.find_parent(class_=re.compile(r"card|movie|item|short", re.I)) or a
            img_tag = parent_card.find("img")
            if img_tag:
                p_src = img_tag.get("src") or img_tag.get("data-src")
                if p_src:
                    poster_url = p_src if p_src.startswith("http") else f"{self.BASE_URL}{p_src}"

            # Yil
            year = None
            y_match = re.search(r"\b(19\d{2}|20\d{2})\b", raw_title)
            if y_match:
                year = int(y_match.group(1))

            # Serial yoki ko'p qismli ekanligi belgisi
            is_series = bool(
                re.search(r"serial|fasl|qism|barcha|qismlar|\b\d+[\s\-]+\d+", f"{raw_title} {href}", re.I)
                or "serial" in href.lower()
                or "barcha-qismlar" in href.lower()
            )

            items.append({
                "id": movie_id,
                "title": title,
                "raw_title": raw_title,
                "url": full_url,
                "year": year,
                "poster": poster_url,
                "is_series": is_series,
            })

        return items

    async def fetch_catalog_batch(self, pages: int = 5) -> List[Dict[str, Any]]:
        """
        Asilmedia ochiq API va katalog sahifalaridan (sayt.php, /page/{p}/, /api/asil/*)
        o'nlab/yuzlab mashhur va yangi kinolarni avtomatik ravishda yig'ib qaytaruvchi
        samarali batch-sinxronizator.
        """
        items: List[Dict[str, Any]] = []
        seen_ids = set()

        def add_item(iid, title, raw_t="", url="", year=None, poster="", is_series=False, genres=None, desc=""):
            s_id = str(iid).strip()
            if not s_id or s_id in seen_ids:
                return
            seen_ids.add(s_id)
            clean_t = self.clean_title(title)
            if not clean_t:
                return
            genres_list = genres or []
            if isinstance(genres_list, str):
                genres_list = [g.strip() for g in genres_list.split(",") if g.strip()]
            y_val = year
            if not y_val and raw_t:
                y_m = re.search(r"\b(19\d{2}|20\d{2})\b", raw_t)
                if y_m:
                    y_val = int(y_m.group(1))

            items.append({
                "id": s_id,
                "title": clean_t,
                "raw_title": raw_t or clean_t,
                "url": url or f"{self.BASE_URL}/{s_id}-kino.html",
                "year": y_val,
                "poster": poster,
                "is_series": is_series,
                "genres": genres_list,
                "description": desc,
                "total_parts": 10 if is_series else 1,
                "views": 2500,
            })

        async with aiohttp.ClientSession(headers=self._get_headers()) as session:
            # 1. Upstream /api/asil/home (pop, film, serial)
            try:
                async with session.get("https://161-97-96-58.sslip.io/api/asil/home", timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                    if resp.status == 200:
                        h_data = await resp.json()
                        if isinstance(h_data, dict):
                            for sec in ["pop", "film", "serial"]:
                                for it in h_data.get(sec, []):
                                    iid = it.get("id")
                                    if iid:
                                        add_item(
                                            iid=iid,
                                            title=it.get("t", ""),
                                            poster=it.get("p", ""),
                                            year=it.get("y"),
                                            genres=it.get("g", []),
                                            is_series=(it.get("type") == "serial") or (sec == "serial"),
                                            desc=it.get("desc", ""),
                                        )
            except Exception as e:
                logger.debug(f"fetch_catalog_batch upstream home error: {e}")

            # 2. Upstream /api/asil/list?page=1..pages
            for p in range(1, max(2, pages + 1)):
                try:
                    async with session.get(f"https://161-97-96-58.sslip.io/api/asil/list?page={p}", timeout=aiohttp.ClientTimeout(total=1.8, connect=1.0)) as resp:
                        if resp.status == 200:
                            l_data = await resp.json()
                            if isinstance(l_data, dict) and isinstance(l_data.get("items"), list):
                                for it in l_data.get("items", []):
                                    iid = it.get("id")
                                    if iid:
                                        add_item(
                                            iid=iid,
                                            title=it.get("t", ""),
                                            poster=it.get("p", ""),
                                            year=it.get("y"),
                                            genres=it.get("g", []),
                                            is_series=(it.get("type") == "serial"),
                                            desc=it.get("desc", ""),
                                        )
                except Exception as e:
                    logger.debug(f"fetch_catalog_batch upstream list page {p} error: {e}")

            # 3. Asilmedia ochiq sahifalari (sayt.php, /page/{p}/, /tarjima-kinolar/page/{p}/, /seriallar/page/{p}/)
            direct_urls = []
            for p in range(1, pages + 1):
                p_suffix = f"/page/{p}/" if p > 1 else "/"
                for m in self.MIRRORS:
                    direct_urls.append(f"{m}{p_suffix}")
                    direct_urls.append(f"{m}/tarjima-kinolar{p_suffix}")
                    direct_urls.append(f"{m}/seriallar{p_suffix}")
            for m in self.MIRRORS:
                direct_urls.append(f"{m}/sayt.php")

            for u in direct_urls[:min(len(direct_urls), pages * 3 + 2)]:
                try:
                    async with session.get(u, timeout=aiohttp.ClientTimeout(total=3.5)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            parsed = self._parse_search_results(html)
                            for pit in parsed:
                                add_item(
                                    iid=pit["id"],
                                    title=pit["title"],
                                    raw_t=pit.get("raw_title", ""),
                                    url=pit.get("url", ""),
                                    year=pit.get("year"),
                                    poster=pit.get("poster", ""),
                                    is_series=pit.get("is_series", False),
                                )
                except Exception as e:
                    logger.debug(f"fetch_catalog_batch scraping {u} error: {e}")

        return items

    async def sign_fayllar_urls(self, urls: List[str]) -> Dict[str, str]:
        """Fayllar.com video havolalarini Asilmedia tokeni bilan imzolash."""
        if not urls:
            return {}
        fayllar_urls = [u for u in urls if "fayllar" in str(u) and "token=" not in str(u)]
        if not fayllar_urls:
            return {}
        qs = "&".join(f"u[]={urllib.parse.quote(str(u))}" for u in fayllar_urls)
        sign_url = f"{self.BASE_URL}/fayllar-sign.php?{qs}"
        try:
            async with aiohttp.ClientSession(headers=self._get_headers(referer=self.BASE_URL)) as session:
                async with session.get(sign_url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.debug(f"fayllar-sign error: {e}")
        return {}

    async def get_telegram_media_info(self, news_id: Union[str, int]) -> Optional[Dict[str, Any]]:
        """d.asilmedia.org orqali kinoning Telegram kanaldagi oqim va post ma'lumotlarini olish."""
        try:
            clean_id = re.search(r"(\d+)", str(news_id))
            if not clean_id:
                return None
            url = f"https://d.asilmedia.org/api/videos/by-news/{clean_id.group(1)}"
            async with aiohttp.ClientSession(headers=self._get_headers(referer=self.BASE_URL)) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.debug(f"get_telegram_media_info error: {e}")
        return None

    async def get_movie_details(self, url_or_id: str) -> Optional[AsilmediaMovie]:
        """
        Kino/serial sahifasini to'liq yuklash va barcha qismlari, video oqimlarini ajratish.
        """
        target_url = url_or_id
        extracted_id = None
        id_match = re.search(r"(\d+)", str(url_or_id))
        if id_match:
            extracted_id = id_match.group(1)

        if not str(target_url).startswith("http"):
            # ID berilgan bo'lsa
            target_url = f"{self.BASE_URL}/{target_url}-kino.html"

        cache_key = target_url.lower()
        now = time.time()
        if cache_key in self._details_cache:
            ts, cached_dict = self._details_cache[cache_key]
            if now - ts < 1800:
                # Keshdan tiklash
                return self._dict_to_movie(cached_dict)

        urls_to_try = []
        if extracted_id:
            # Bot sayt.php oynasi to'g'ridan-to'g'ri toza HTML va barcha video ma'lumotlarni beradi
            urls_to_try.append(f"{self.BASE_URL}/bot/sayt.php?id={extracted_id}&k=hamkor")
        urls_to_try.append(target_url)
        for m in self.MIRRORS:
            alt = re.sub(r"^https?://[^/]+", m, target_url)
            if alt not in urls_to_try:
                urls_to_try.append(alt)

        for u in urls_to_try:
            try:
                async with aiohttp.ClientSession(headers=self._get_headers(referer=self.BASE_URL)) as session:
                    async with session.get(u, timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            movie = self.extract_sources_from_html(html, page_url=u)
                            if movie:
                                # Fayllar.com havolalarini avtomatik imzolash
                                unsigned_list = []
                                for qk, qurl in movie.video_sources.items():
                                    if "fayllar" in str(qurl) and "token=" not in str(qurl):
                                        unsigned_list.append(qurl)
                                for ep in movie.episodes.values():
                                    if "fayllar" in str(ep.url) and "token=" not in str(ep.url):
                                        unsigned_list.append(ep.url)

                                if unsigned_list:
                                    signed_map = await self.sign_fayllar_urls(unsigned_list)
                                    if signed_map:
                                        for qk, qurl in list(movie.video_sources.items()):
                                            if qurl in signed_map:
                                                movie.video_sources[qk] = signed_map[qurl]
                                        for ep in movie.episodes.values():
                                            if ep.url in signed_map:
                                                signed_val = signed_map[ep.url]
                                                ep.url = signed_val
                                                ep.download_url = signed_val

                                # Telegram kanaldagi oqim va davomiylik ma'lumotlari bilan boyitish
                                target_mid = extracted_id or movie.id
                                tg_info = await self.get_telegram_media_info(target_mid)
                                if tg_info and isinstance(tg_info, dict) and isinstance(tg_info.get("fields"), list):
                                    for fld in tg_info["fields"]:
                                        q = fld.get("quality", "1080p")
                                        w = fld.get("watch")
                                        d_url = fld.get("download_joined") or fld.get("download") or w
                                        if w:
                                            movie.video_sources[f"tg_{q}"] = w
                                            if not movie.video_sources.get(q):
                                                movie.video_sources[q] = w
                                            if not movie.watch_url:
                                                movie.watch_url = w
                                            if not movie.download_url:
                                                movie.download_url = d_url
                                        dur = fld.get("total_duration")
                                        if dur:
                                            movie.duration = f"{dur // 60} daqiqa"
                                            if 1 in movie.episodes:
                                                movie.episodes[1].duration = dur
                                                if w:
                                                    movie.episodes[1].watch_url = w
                                                    movie.episodes[1].download_url = d_url

                                self._details_cache[cache_key] = (now, movie.to_dict())
                                return movie
            except Exception as e:
                logger.warning(f"Asilmedia get_movie_details error for '{u}': {e}")

        return None

    def extract_sources_from_html(self, html: str, page_url: str = "") -> Optional[AsilmediaMovie]:
        """HTML sahifasidan barcha video oqimlari va qismlarni chiqarib olish."""
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser") if BeautifulSoup else None

        # 1. Asosiy ID va sarlavha
        m_id = re.search(r"/(\d+)-", page_url)
        if not m_id:
            m_id = re.search(r"[?&]id=(\d+)", page_url)
        if not m_id:
            m_id = re.search(r"(\d{3,6})", page_url)
        movie_id = m_id.group(1) if m_id else str(int(time.time()))

        raw_title = ""
        if soup:
            title_el = soup.find("h1") or soup.find("title")
            if title_el:
                raw_title = title_el.get_text(strip=True)
        if not raw_title:
            t_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            raw_title = t_m.group(1).split("|")[0].strip() if t_m else f"Kino #{movie_id}"
        clean_t = self.clean_title(raw_title)

        # 2. Tavsif, Janr, Yil
        desc = ""
        desc_el = soup.find(class_=re.compile(r"fs-description|description|story", re.I))
        if desc_el:
            desc = desc_el.get_text(strip=True)

        genres = []
        for g_a in soup.find_all("a", href=re.compile(r"xfsearch/genre", re.I)):
            g_text = g_a.get_text(strip=True)
            # "Detektiv (детектив)" -> "Detektiv"
            g_clean = g_text.split("(")[0].strip()
            if g_clean and g_clean not in genres:
                genres.append(g_clean)

        year = None
        y_a = soup.find("a", href=re.compile(r"xfsearch/year", re.I))
        if y_a and y_a.get_text(strip=True).isdigit():
            year = int(y_a.get_text(strip=True))
        else:
            y_m = re.search(r"\b(19\d{2}|20\d{2})\b", raw_title)
            if y_m:
                year = int(y_m.group(1))

        poster = None
        poster_img = soup.find(class_=re.compile(r"fs-poster|poster", re.I))
        if poster_img:
            if poster_img.name == "img":
                poster = poster_img.get("src")
            else:
                p_in = poster_img.find("img")
                if p_in:
                    poster = p_in.get("src")
        if not poster:
            og_img = soup.find("meta", property="og:image")
            if og_img:
                poster = og_img.get("content")

        if poster and not poster.startswith("http"):
            poster = f"{self.BASE_URL}{poster}"

        # 3. Video oqimlarini qazib olish (Multi-tier parser)
        episodes: Dict[int, AsilmediaEpisode] = {}
        video_sources: Dict[str, str] = {}
        is_series = False

        # Tier 1: id="tg-data" (Telegram stream/download serveri havolalari)
        tg_data_el = soup.find(id="tg-data")
        if tg_data_el:
            tg_lines = tg_data_el.get_text().strip().split("\n")
            for line in tg_lines:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                parts = line.split("=", 2)
                if len(parts) == 3:
                    # Masalan: serialpart1=1-fasl 1-qism 1080p=https://server.asilmedia.org/watch/...
                    slot_name, label_str, stream_url = parts[0].strip(), parts[1].strip(), parts[2].strip()
                elif len(parts) == 2:
                    slot_name, stream_url = parts[0].strip(), parts[1].strip()
                    label_str = slot_name
                else:
                    continue

                # serialpart yoki kino_url ni ajratish
                if slot_name.startswith("serialpart"):
                    is_series = True
                    # serialpart1 -> 1
                    s_idx_m = re.search(r"serialpart(\d+)", slot_name)
                    fallback_idx = int(s_idx_m.group(1)) if s_idx_m else len(episodes) + 1

                    season, ep_num, q_val = self.parse_episode_label(label_str, fallback_index=fallback_idx)
                    # Ketma-ket qism raqami sifatida fallback_idx yoki ep_num ni ishlatamiz
                    part_num = fallback_idx if fallback_idx > 0 else ep_num

                    watch_u = stream_url
                    down_u = stream_url.replace("/watch/", "/download/") if "/watch/" in stream_url else stream_url
                    ep = AsilmediaEpisode(
                        part=part_num,
                        label=label_str,
                        url=down_u,
                        season=season,
                        episode=ep_num,
                        quality=q_val,
                        watch_url=watch_u,
                        download_url=down_u,
                    )
                    # Agar bu qism avval saqlangan bo'lsa va yangisi yuqoriroq sifatda bo'lsa yangilaymiz
                    if part_num not in episodes or q_val == "1080p":
                        episodes[part_num] = ep

                elif slot_name.startswith("kino_url"):
                    # Masalan: kino_url1=480p=https://... yoki kino_url1=720p Taksi-1 / HD=https://...
                    # Agar label ichida qism raqami bo'lsa (masalan Taksi-1, Taksi-2)
                    m_multi = re.search(r"[-_\s](\d+)\s*(?:/|qism|hd|$)", label_str, re.I)
                    if m_multi:
                        is_series = True
                        part_num = int(m_multi.group(1))
                        season, ep_num, q_val = self.parse_episode_label(label_str, fallback_index=part_num)
                        watch_u = stream_url
                        down_u = stream_url.replace("/watch/", "/download/") if "/watch/" in stream_url else stream_url
                        episodes[part_num] = AsilmediaEpisode(
                            part=part_num,
                            label=label_str,
                            url=down_u,
                            season=season,
                            episode=ep_num,
                            quality=q_val,
                            watch_url=watch_u,
                            download_url=down_u,
                        )
                    else:
                        # Bir qismli kino uchun sifat bo'yicha manba
                        q_name = "1080p" if "1080p" in label_str else ("720p" if "720p" in label_str else "480p")
                        video_sources[q_name] = stream_url

        # Tier 2: id="episodes-raw-data" va id="serial-dl-data" (Direct MP4 / CDN fayllar)
        for section_id in ["episodes-raw-data", "serial-dl-data"]:
            sec_el = soup.find(id=section_id)
            if sec_el:
                is_series = True
                links = sec_el.find_all("a", href=True)
                for idx, a_tag in enumerate(links, start=1):
                    href = a_tag["href"].strip()
                    lbl = a_tag.get("data-label", "").strip() or a_tag.get_text(strip=True) or f"{idx}-qism"
                    season, ep_num, q_val = self.parse_episode_label(lbl, fallback_index=idx)
                    part_num = idx

                    if part_num not in episodes:
                        episodes[part_num] = AsilmediaEpisode(
                            part=part_num,
                            label=lbl,
                            url=href,
                            season=season,
                            episode=ep_num,
                            quality=q_val,
                            watch_url=href,
                            download_url=href,
                        )
                    else:
                        # Agar avvalgi manbaga direct MP4 qo'shish kerak bo'lsa
                        if href.endswith(".mp4") and q_val in ["1080p", "720p"]:
                            episodes[part_num].url = href

        # Tier 3: Player tabs (data-url), iframe yoki video teglari
        if soup:
            for btn in soup.find_all(attrs={"data-url": True}):
                d_url = btn.get("data-url", "").strip()
                d_name = btn.get("data-name", "").strip()
                q_name = "1080p" if "1080p" in f"{d_url} {d_name}" else ("720p" if "720p" in f"{d_url} {d_name}" else "480p")
                if d_url:
                    video_sources[q_name] = d_url
                    if "primary" not in video_sources or q_name == "1080p":
                        video_sources["primary"] = d_url

            for ifr in soup.find_all("iframe"):
                src = ifr.get("data-player-src") or ifr.get("src") or ifr.get("data-src")
                if src:
                    src = src.strip()
                    if "primary" not in video_sources and ("fayllar.com" in src or src.endswith(".mp4") or "server.asilmedia.org" in src):
                        video_sources["primary"] = src
                        if "1080p" not in video_sources:
                            video_sources["1080p"] = src

        # Regex fallback: agar soup topilmagan yoki tabs aniqlanmagan bo'lsa
        if not video_sources:
            for m in re.finditer(r'data-url=["\'](https?://[^"\']+)["\']', html):
                d_url = m.group(1).strip()
                q_name = "1080p" if "1080p" in d_url else ("720p" if "720p" in d_url else "480p")
                video_sources[q_name] = d_url
                if "primary" not in video_sources or q_name == "1080p":
                    video_sources["primary"] = d_url

        # Tier 4: Script teglari ichidan server.asilmedia.org yoki direct mp4 oqimlarni qidirish
        if not episodes and not video_sources and soup:
            for sc in soup.find_all("script"):
                sc_text = sc.string or sc.get_text() or ""
                if not sc_text:
                    continue
                found_urls = re.findall(r'https?://server\.asilmedia\.org/(?:watch|download)/\d+/\d+', sc_text)
                if not found_urls:
                    found_urls = re.findall(r'https?://[^\s"\'<>]+\.mp4', sc_text)
                for f_url in found_urls:
                    if "primary" not in video_sources:
                        video_sources["primary"] = f_url
                    if "1080p" not in video_sources:
                        video_sources["1080p"] = f_url

        # Agar na episodes, na video_sources bo'lsa yoki Asilmedia umumiy bosh sahifasi bo'lsa - kino emas
        if not episodes and not video_sources:
            return None
        if re.search(r"asilmedia\s*[-—–]\s*(?:kinolar|bosh)", raw_title, re.I) and not episodes:
            return None

        # Agar serial bo'lmasa va bitta video manbasi bo'lsa, 1-qism sifatida shakllantiramiz
        if not episodes and video_sources:
            best_url = video_sources.get("1080p") or video_sources.get("720p") or video_sources.get("primary") or list(video_sources.values())[0]
            episodes[1] = AsilmediaEpisode(
                part=1,
                label="To'liq film",
                url=best_url,
                season=1,
                episode=1,
                quality="1080p",
                watch_url=best_url,
                download_url=best_url,
            )

        total_parts = len(episodes) if episodes else 1

        return AsilmediaMovie(
            id=movie_id,
            title=clean_t,
            url=page_url,
            orig_title=raw_title,
            year=year,
            genres=genres,
            description=desc,
            poster=poster,
            is_series=is_series or total_parts > 1,
            total_parts=total_parts,
            episodes=episodes,
            video_sources=video_sources,
        )

    async def find_best_match(
        self,
        title: str,
        year: Optional[int] = None,
        is_series: Optional[bool] = None,
        target_parts: int = 1
    ) -> Optional[AsilmediaMovie]:
        """
        Kino yoki serial nomi bo'yicha Asilmediadan eng to'g'ri keluvchi kartochkani topish
        va uning barcha qismlarini yuklab qaytarish.
        """
        clean_q = self.clean_title(title)
        candidates = await self.search(clean_q, limit=8)

        # Agar ko'p qismli kino yoki serial qidirilayotgan bo'lsa, "barcha qismlar" so'rovi bilan ham qidirish
        if is_series or target_parts > 1:
            more_cands = await self.search(f"{clean_q} barcha qismlar", limit=6)
            for mc in more_cands:
                if not any(c["url"] == mc["url"] for c in candidates):
                    candidates.append(mc)

        if not candidates:
            # Agar birinchi qidiruvda chiqmasa, sarlavhadan birinchi 1-2 so'zni olib qidirish
            words = clean_q.split()
            if len(words) > 1:
                candidates = await self.search(" ".join(words[:2]), limit=8)

        if not candidates:
            return None

        # Eng yaxshi moslikni aniqlash (scoring)
        def score_candidate(cand: Dict[str, Any]) -> int:
            score = 0
            c_title = cand["title"].lower()
            q_lower = clean_q.lower()
            raw_t = cand.get("raw_title", "").lower()
            c_id = str(cand.get("id"))

            # Kanonik franshizalar uchun to'g'ridan-to'g'ri prioritet
            if ("taksi" in q_lower or "taxi" in q_lower) and c_id == "9165":
                score += 300
            elif "titan" in q_lower and c_id in ("16913", "14075"):
                score += 300
            elif ("forsaj" in q_lower or "fast" in q_lower) and c_id in ("14902", "13087", "8563"):
                score += 250
            elif "chuqur" in q_lower and ("cukur" in raw_t or "serial" in raw_t or cand.get("is_series")):
                score += 200

            if c_title == q_lower:
                score += 150
            elif c_title.startswith(q_lower) or raw_t.startswith(q_lower):
                score += 80
            elif q_lower in c_title or c_title in q_lower:
                score += 50

            # Ko'p qismli serial yoki kolleksiya talab qilinganda
            if (is_series or target_parts > 1):
                if cand.get("is_series") or "barcha qismlar" in raw_t or "serial" in raw_t:
                    score += 120
                if "barcha-qismlar" in cand["url"].lower():
                    score += 60
                if any(str(p) in cand["title"] for p in range(1, target_parts + 1)):
                    score += 30
            elif is_series is False:
                if not cand.get("is_series") and "barcha qismlar" not in raw_t:
                    score += 20

            # Yil mosligi
            if year and cand.get("year"):
                if cand["year"] == year:
                    score += 30
                elif abs(cand["year"] - year) <= 1:
                    score += 15

            return score

        candidates.sort(key=score_candidate, reverse=True)

        # Yuqori ball to'plagan dastlabki nomzodlardan mosini ko'rib chiqish
        best_candidate_movie = None
        for cand in candidates[:6]:
            movie_det = await self.get_movie_details(cand["url"])
            if movie_det:
                if (is_series or target_parts > 1):
                    if movie_det.total_parts >= target_parts:
                        return movie_det
                    if best_candidate_movie is None or movie_det.total_parts > best_candidate_movie.total_parts:
                        best_candidate_movie = movie_det
                else:
                    return movie_det

        if best_candidate_movie:
            return best_candidate_movie

        return await self.get_movie_details(candidates[0]["url"])

    @staticmethod
    def is_valid_video_header(data: bytes) -> bool:
        """Video oqimi boshidagi baytlarni (magic bytes) tekshirish."""
        if not data or len(data) < 16:
            return False
        # HTML yoki matnni darhol rad etish
        lower_prefix = data[:256].lower()
        if (
            b"<!doctype" in lower_prefix
            or b"<html" in lower_prefix
            or b"<head" in lower_prefix
            or b"<body" in lower_prefix
            or b"var " in lower_prefix
            or b"/*" in lower_prefix
        ):
            return False

        # MP4/MOV: 'ftyp' dastlabki 32 bayt ichida
        if b"ftyp" in data[:32]:
            return True
        # MKV / WebM
        if data.startswith(b"\x1a\x45\xdf\xa3"):
            return True
        # AVI (RIFF ... AVI)
        if data.startswith(b"RIFF") and b"AVI" in data[:16]:
            return True
        # FLV
        if data.startswith(b"FLV"):
            return True
        # MPEG-TS (0x47 sinxronizatsiya bayti)
        if data[0] == 0x47:
            return True
        # MP4 header / moov / mdat
        if b"moov" in data[:64] or b"mdat" in data[:64]:
            return True
        # Umumiy binar oqim (agar HTML belgilaridan xoli bo'lsa)
        if not any(c in data[:64] for c in b"<>{}()"):
            return True
        return False

    async def download_video_stream(
        self,
        url: str,
        destination_path: Path,
        max_bytes: int = 2048 * 1024 * 1024,
        timeout: int = 180
    ) -> Optional[Path]:
        """
        Asilmedia video faylini xavfsiz holda serverga to'liq yuklab olish (chunk streaming).
        2GB gacha bo'lgan barcha to'liq kinolar va serial qismlarini to'liq hajmda yuklaydi.
        HTML sahifalar yoki xato javoblar yuklanmaydi va rad etiladi.
        """
        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            target_url = url
            if "fayllar" in target_url and "token=" not in target_url:
                try:
                    signed_map = await self.sign_fayllar_urls([target_url])
                    if target_url in signed_map:
                        target_url = signed_map[target_url]
                except Exception as se:
                    logger.debug(f"Auto-sign fayllar url error: {se}")

            encoded_url = urllib.parse.quote(target_url, safe=":/%?=&-._~")
            headers = self._get_headers(referer=self.BASE_URL)

            async with aiohttp.ClientSession(headers=headers) as session:
                client_timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=30)
                async with session.get(encoded_url, timeout=client_timeout) as resp:
                    if resp.status not in (200, 206):
                        logger.warning(f"Video yuklashda HTTP {resp.status}: {encoded_url}")
                        return None

                    content_type = (resp.headers.get("Content-Type") or "").lower()
                    if any(t in content_type for t in ["text/html", "text/plain", "application/json", "application/xml"]):
                        logger.warning(f"Yuklash manzili video emas ({content_type}): {encoded_url}")
                        return None

                    content_length = resp.headers.get("Content-Length")
                    cl_num = int(content_length) if content_length and content_length.isdigit() else None
                    if cl_num and cl_num > max_bytes:
                        logger.warning(f"Video hajmi {cl_num} bayt xavfsiz limitdan ({max_bytes}) katta, yuklash to'xtatildi.")
                        return None
                    elif cl_num:
                        logger.info(f"Video to'liq yuklab olinmoqda: {cl_num} bayt ({cl_num // (1024*1024)} MB)...")

                    downloaded = 0
                    temp_file = destination_path.with_suffix(".tmp")
                    first_chunk = True
                    valid_header = False

                    with open(temp_file, "wb") as f:
                        async for chunk in resp.content.iter_chunked(64 * 1024):
                            if not chunk:
                                break
                            if first_chunk:
                                first_chunk = False
                                if not self.is_valid_video_header(chunk):
                                    logger.warning(f"Video boshlang'ich baytlari yaroqsiz (HTML yoki matn): {encoded_url}")
                                    break
                                valid_header = True
                            f.write(chunk)
                            downloaded += len(chunk)
                            if downloaded >= max_bytes:
                                break

                    # Haqiqiy video kamida 1KB bo'lishi kerak
                    min_valid_size = 1024
                    if downloaded >= min_valid_size and valid_header:
                        if temp_file.exists():
                            if destination_path.exists():
                                destination_path.unlink()
                            temp_file.rename(destination_path)
                            logger.info(f"Video muvaffaqiyatli saqlandi ({downloaded} bayt): {destination_path}")
                            return destination_path
                    else:
                        if temp_file.exists():
                            temp_file.unlink()
                        if downloaded > 0:
                            logger.warning(f"Fayl hajmi video uchun juda kichik ({downloaded} bayt): {destination_path.name}")
        except Exception as e:
            logger.warning(f"download_video_stream error for '{url}': {e}")
            temp_file = destination_path.with_suffix(".tmp")
            if temp_file.exists():
                try:
                    if temp_file.stat().st_size >= 512 * 1024:
                        if destination_path.exists():
                            destination_path.unlink()
                        temp_file.rename(destination_path)
                        logger.info(f"Qisman yuklangan video saqlandi ({destination_path.stat().st_size} bayt): {destination_path}")
                        return destination_path
                    else:
                        temp_file.unlink()
                except Exception:
                    pass

        return None

    def _dict_to_movie(self, d: Dict[str, Any]) -> AsilmediaMovie:
        """Keshdagi dict dan AsilmediaMovie obyektini tiklash."""
        eps: Dict[int, AsilmediaEpisode] = {}
        for k, v in d.get("episodes", {}).items():
            if isinstance(v, dict):
                eps[int(k)] = AsilmediaEpisode(
                    part=int(v.get("part", k)),
                    label=v.get("label", f"{k}-qism"),
                    url=v.get("url", ""),
                    season=int(v.get("season", 1)),
                    episode=int(v.get("episode", k)),
                    quality=v.get("quality", "1080p"),
                    watch_url=v.get("watch_url"),
                    download_url=v.get("download_url"),
                    file_type=v.get("file_type", "video"),
                    file_size=v.get("file_size"),
                    duration=v.get("duration"),
                    source=v.get("source", "asilmedia"),
                )
        return AsilmediaMovie(
            id=str(d.get("id")),
            title=d.get("title", ""),
            url=d.get("url", ""),
            orig_title=d.get("orig_title"),
            year=d.get("year"),
            genres=d.get("genres", []),
            description=d.get("description"),
            poster=d.get("poster"),
            rating=d.get("rating"),
            duration=d.get("duration"),
            is_series=bool(d.get("is_series")),
            total_parts=int(d.get("total_parts", 1)),
            episodes=eps,
            video_sources=d.get("video_sources", {}),
            watch_url=d.get("watch_url"),
            download_url=d.get("download_url"),
        )


# Singleton nusxa
asilmedia_service = AsilmediaService()
