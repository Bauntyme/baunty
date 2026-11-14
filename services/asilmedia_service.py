"""
Asilmedia.org integratsiya xizmati.
Kinolar, seriallar, animelar va multfilmlarni qidirish,
va to'g'ridan-to'g'ri video manbalarini olish.
100% Bauntys brendi (@BauntyCinemabot, @BauntyFilms).
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
    quality_urls: Dict[str, str] = field(default_factory=dict)
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
    amh_id: Optional[str] = None
    amh_n: Optional[str] = None

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
    DEFAULT_TIMEOUT = 6

    def __init__(self):
        self._cache_dir = BASE_DIR / "data" / "asilmedia_cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._search_cache: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
        self._details_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def _get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        ref = referer or f"{self.BASE_URL}/"
        if ref == self.BASE_URL:
            ref = f"{self.BASE_URL}/"
        return {
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "uz,ru;q=0.9,en;q=0.8",
            "Referer": ref,
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

        # 5. Fallback raqam (360p/480p/720p/1080p kabi sifat belgilarini chiqarib tashlab)
        label_no_q = re.sub(r"\b(?:360|480|720|1080|2160)p\b|\b4k\b", "", label, flags=re.I)
        m_any = re.search(r"\b(\d+)\b", label_no_q)
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

            inferred_parts = 1
            if is_series:
                m_ep = re.search(r"(\d+)\s*[- ]*\s*(?:qism|seriya)", f"{raw_t} {desc}", re.I)
                if m_ep and 1 <= int(m_ep.group(1)) <= 500:
                    inferred_parts = int(m_ep.group(1))
                else:
                    inferred_parts = 2
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
                "total_parts": inferred_parts,
                "views": 2500,
            })

        async with aiohttp.ClientSession(headers=self._get_headers()) as session:
            # Asilmedia ochiq sahifalari (sayt.php, /page/{p}/, /tarjima-kinolar/page/{p}/, /seriallar/page/{p}/)
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

    @staticmethod
    def is_html_wrapper_url(url: Optional[str]) -> bool:
        """URL video oqimi emas, HTML sahifa yoki watch/download wrapper ekanligini tekshirish."""
        if not url:
            return False
        low = str(url).strip().lower()
        if not low:
            return False
        if "sslip.io" in low or "sayt.php" in low:
            return True
        if re.search(r"server\.asilmedia\.org/(?:watch|download|embed)", low):
            return True
        if re.search(r"\.html?(?:$|[?#])", low):
            return True
        return False

    @staticmethod
    @staticmethod
    def strip_fayllar_token(url: Optional[str]) -> str:
        """Fayllar CDN URL dan token va expires parametrlarini olib tashlash."""
        if not url:
            return ""
        s = str(url).strip()
        parsed = urllib.parse.urlparse(s)
        if not parsed.query:
            return s
        qs_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in qs_pairs if k.lower() not in ("token", "expires", "st", "e")]
        new_query = urllib.parse.urlencode(filtered)
        return urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

    @staticmethod
    def is_token_expired(url: Optional[str]) -> bool:
        """Havoladagi token muddati (expires) o'tganligini tekshirish."""
        if not url:
            return False
        parsed = urllib.parse.urlparse(str(url))
        qs = dict(urllib.parse.parse_qsl(parsed.query))
        expires = qs.get("expires") or qs.get("e")
        if expires and str(expires).isdigit():
            import time
            return int(expires) <= int(time.time()) + 30
        return False

    @staticmethod
    def needs_fayllar_sign(url: Optional[str], force: bool = False) -> bool:
        """am:<id>:<hash> yoki tokensiz/muddati o'tgan fayllar havolasi imzolashga muhtojligini aniqlash."""
        if not url:
            return False
        s = str(url).strip()
        if re.match(r"^am:\d+:", s, re.I):
            return True
        low = s.lower()
        is_fayllar = ("fayllar.com" in low or "fayllar1.ru" in low or "fayllar" in low)
        if not is_fayllar:
            return False
        if force:
            return True
        if "token=" not in low:
            return True
        if AsilmediaService.is_token_expired(s):
            return True
        return False

    @staticmethod
    def extract_amh_params(html: str) -> Tuple[Optional[str], Optional[str]]:
        """HTML sahifadagi <i id='amh' data-id='...' data-n='...'> parametrlarini ajratish."""
        if not html:
            return None, None
        m_tag = re.search(r"<(?:i|span|div|b)\b[^>]*\bid=[\"']amh[\"'][^>]*>", html, re.I)
        if not m_tag:
            return None, None
        tag_str = m_tag.group(0)
        m_id = re.search(r"\bdata-id=[\"']([^\"']+)[\"']", tag_str, re.I)
        m_n = re.search(r"\bdata-n=[\"']([^\"']+)[\"']", tag_str, re.I)
        amh_id = m_id.group(1).strip() if m_id else None
        amh_n = m_n.group(1).strip() if m_n else None
        return amh_id, amh_n

    async def sign_fayllar_urls(
        self,
        urls: List[str],
        amh_id: Optional[Union[str, int]] = None,
        amh_n: Optional[str] = None,
        force: bool = False,
    ) -> Dict[str, str]:
        """am:<id>:<hash> va tokensiz fayllar havolalarini Asilmedia tokeni bilan imzolash."""
        if not urls:
            return {}
        seen: set[str] = set()
        sign_candidates: List[str] = []
        raw_to_cand: Dict[str, str] = {}
        for u in urls:
            su = str(u or "").strip()
            if not su:
                continue
            cand = self.strip_fayllar_token(su) if "token=" in su.lower() else su
            raw_to_cand[su] = cand
            if cand in seen:
                continue
            if force or self.needs_fayllar_sign(su, force=force):
                seen.add(cand)
                sign_candidates.append(cand)
        if not sign_candidates:
            return {}

        resolved_id = str(amh_id).strip() if amh_id is not None else None
        if not resolved_id:
            for su in sign_candidates:
                m_am = re.match(r"^am:(\d+):", su, re.I)
                if m_am:
                    resolved_id = m_am.group(1)
                    break

        signed_map: Dict[str, str] = {}
        # Asilmedia fayllar-sign.php ~25 tadan ko'p URL yuborilganda bo'sh JSON qaytaradi;
        # 18 talik paket barcha qismlar (jumladan 100+ qismli seriallar) uchun ishonchli ishlaydi.
        batch_size = 18
        async with aiohttp.ClientSession(headers=self._get_headers(referer=self.BASE_URL)) as session:
            for i in range(0, len(sign_candidates), batch_size):
                chunk = sign_candidates[i:i + batch_size]
                qs_parts = [f"u[]={urllib.parse.quote(u, safe='')}" for u in chunk]
                if resolved_id:
                    qs_parts.append(f"id={urllib.parse.quote(resolved_id, safe='')}")
                if amh_n:
                    qs_parts.append(f"n={urllib.parse.quote(str(amh_n), safe='')}")
                qs = "&".join(qs_parts)

                for mirror in self.MIRRORS:
                    sign_url = f"{mirror}/fayllar-sign.php?{qs}"
                    req_headers = {"Referer": f"{mirror}/"}
                    try:
                        async with session.get(sign_url, headers=req_headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                            if resp.status == 200:
                                data = await resp.json(content_type=None)
                                if isinstance(data, dict) and data:
                                    for k, v in data.items():
                                        sv = str(v or "").strip()
                                        if sv.startswith("http") and not self.is_html_wrapper_url(sv) and not sv.startswith("am:"):
                                            signed_map[str(k)] = sv
                                    # Map original raw URLs back to signed URLs
                                    for r_u, c_u in raw_to_cand.items():
                                        if c_u in signed_map:
                                            signed_map[r_u] = signed_map[c_u]
                                    if any(u in signed_map for u in chunk):
                                        break
                    except Exception as e:
                        logger.debug(f"fayllar-sign error ({mirror}): {e}")
        return signed_map

    async def resolve_stream_url(
        self,
        raw_url: str,
        news_id: Optional[Union[str, int]] = None,
        amh_id: Optional[str] = None,
        amh_n: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[str]:
        """am:... yoki tokensiz/eskirgan fayllar havolasini bevosita imzolangan MP4 CDN URL ga aylantirish."""
        raw = str(raw_url or "").strip()
        if not raw or self.is_html_wrapper_url(raw):
            return None

        nid = str(news_id).strip() if news_id is not None else None
        if not nid:
            m_am = re.match(r"^am:(\d+):", raw, re.I)
            if m_am:
                nid = m_am.group(1)

        needs_sign = force_refresh or self.needs_fayllar_sign(raw, force=force_refresh)
        if needs_sign:
            if (not amh_id or not amh_n) and nid:
                # Keshdan amh_id / amh_n bor-yo'qligini tekshirish
                clean_nid = re.search(r"(\d+)", nid)
                nid_num = clean_nid.group(1) if clean_nid else None
                if nid_num:
                    for _, cached_dict in self._details_cache.values():
                        if isinstance(cached_dict, dict) and str(cached_dict.get("id")) == nid_num:
                            amh_id = amh_id or cached_dict.get("amh_id")
                            amh_n = amh_n or cached_dict.get("amh_n")
                            if amh_id and amh_n:
                                break
                if (not amh_id or not amh_n) and nid_num:
                    page_candidates: List[str] = []
                    for m in self.MIRRORS:
                        page_candidates.append(f"{m}/{nid_num}-kino.html")
                        page_candidates.append(f"{m}/bot/sayt.php?id={nid_num}&k=hamkor")
                    async with aiohttp.ClientSession(headers=self._get_headers(referer=self.BASE_URL)) as session:
                        for purl in page_candidates:
                            try:
                                async with session.get(purl, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                                    if resp.status == 200:
                                        html = await resp.text()
                                        f_id, f_n = self.extract_amh_params(html)
                                        if f_id or f_n:
                                            amh_id = amh_id or f_id
                                            amh_n = amh_n or f_n
                                            break
                            except Exception as e:
                                logger.debug(f"resolve_stream_url HTML fetch error ({purl}): {e}")

            clean_raw = self.strip_fayllar_token(raw) if "token=" in raw.lower() else raw
            if force_refresh:
                try:
                    signed_map = await self.sign_fayllar_urls([clean_raw], amh_id=amh_id or nid, amh_n=amh_n, force=True)
                except TypeError:
                    signed_map = await self.sign_fayllar_urls([clean_raw], amh_id=amh_id or nid, amh_n=amh_n)
            else:
                signed_map = await self.sign_fayllar_urls([clean_raw], amh_id=amh_id or nid, amh_n=amh_n)
            resolved = signed_map.get(clean_raw) or signed_map.get(raw)
            if resolved and resolved.startswith("http") and not self.is_html_wrapper_url(resolved) and not resolved.startswith("am:"):
                return resolved
            return None

        if raw.startswith("http") and not self.is_html_wrapper_url(raw):
            return raw
        return None

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

        async with aiohttp.ClientSession(headers=self._get_headers(referer=self.BASE_URL)) as session:
            for u in urls_to_try:
                try:
                    req_timeout = 5 if "sayt.php" in u else self.DEFAULT_TIMEOUT
                    async with session.get(u, timeout=aiohttp.ClientTimeout(total=req_timeout)) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            movie = self.extract_sources_from_html(html, page_url=u)
                            if movie:
                                # Barcha noyob am:... va tokensiz fayllar havolalarini amh_id / amh_n bilan imzolash
                                unsigned_list: List[str] = []
                                _seen_u: set[str] = set()
                                for qurl in movie.video_sources.values():
                                    if self.needs_fayllar_sign(qurl) and qurl not in _seen_u:
                                        _seen_u.add(qurl)
                                        unsigned_list.append(qurl)
                                for ep in movie.episodes.values():
                                    for cand_u in [ep.url, ep.download_url] + list(ep.quality_urls.values()):
                                        if cand_u and self.needs_fayllar_sign(cand_u) and cand_u not in _seen_u:
                                            _seen_u.add(cand_u)
                                            unsigned_list.append(cand_u)

                                if unsigned_list:
                                    sign_id = movie.amh_id or extracted_id or movie.id
                                    # Katta seriallarda (100+ qism) barcha havolalarni birdan imzolash sahifani
                                    # sekinlashtirmasligi uchun dastlabki 24 tasini oldindan imzolaymiz; qolganlari
                                    # kerakli qism bosilganda amh_id/amh_n orqali lahzada imzolanadi.
                                    upfront_list = unsigned_list[:24] if len(unsigned_list) > 24 else unsigned_list
                                    signed_map = await self.sign_fayllar_urls(
                                        upfront_list,
                                        amh_id=sign_id,
                                        amh_n=movie.amh_n,
                                    )
                                    if signed_map:
                                        for qk, qurl in list(movie.video_sources.items()):
                                            if qurl in signed_map:
                                                movie.video_sources[qk] = signed_map[qurl]
                                        for ep in movie.episodes.values():
                                            for qk, qurl in list(ep.quality_urls.items()):
                                                if qurl in signed_map:
                                                    ep.quality_urls[qk] = signed_map[qurl]
                                            if ep.url in signed_map:
                                                ep.url = signed_map[ep.url]
                                            if ep.download_url in signed_map:
                                                ep.download_url = signed_map[ep.download_url]
                                            if (not ep.url or ep.url.startswith("am:")) and ep.quality_urls:
                                                best_ep_q = next(
                                                    (q for q in ["1080p", "720p", "480p", "4K", "360p"] if q in ep.quality_urls and not str(ep.quality_urls[q]).startswith("am:")),
                                                    next(iter(ep.quality_urls), None),
                                                )
                                                if best_ep_q:
                                                    ep.quality = best_ep_q
                                                    ep.url = ep.quality_urls[best_ep_q]
                                                    ep.download_url = ep.quality_urls[best_ep_q]
                                        if movie.download_url and movie.download_url in signed_map:
                                            movie.download_url = signed_map[movie.download_url]
                                        if not movie.download_url or str(movie.download_url).startswith("am:"):
                                            movie.download_url = None
                                            for qk in ["1080p", "720p", "480p", "primary"]:
                                                cand_d = movie.video_sources.get(qk)
                                                if cand_d and not self.is_html_wrapper_url(cand_d) and not str(cand_d).startswith("am:"):
                                                    movie.download_url = cand_d
                                                    break
                                        if (not movie.download_url or str(movie.download_url).startswith("am:")) and 1 in movie.episodes:
                                            ep1_dl = movie.episodes[1].download_url
                                            if ep1_dl and not str(ep1_dl).startswith("am:"):
                                                movie.download_url = ep1_dl

                                # Telegram kanaldagi oqim va davomiylik ma'lumotlari bilan boyitish
                                target_mid = extracted_id or movie.id
                                tg_info = await self.get_telegram_media_info(target_mid)
                                if tg_info and isinstance(tg_info, dict) and isinstance(tg_info.get("fields"), list):
                                    for fld in tg_info["fields"]:
                                        q = fld.get("quality", "1080p")
                                        w = fld.get("watch")
                                        d_url = fld.get("download_joined") or fld.get("download")
                                        if w:
                                            if not movie.watch_url:
                                                movie.watch_url = w
                                            if 1 in movie.episodes and not movie.episodes[1].watch_url:
                                                movie.episodes[1].watch_url = w
                                        if d_url and not self.is_html_wrapper_url(d_url):
                                            if not movie.video_sources.get(q):
                                                movie.video_sources[q] = d_url
                                            if not movie.download_url:
                                                movie.download_url = d_url
                                            if 1 in movie.episodes and not movie.episodes[1].download_url:
                                                movie.episodes[1].download_url = d_url
                                        dur = fld.get("total_duration")
                                        if dur:
                                            movie.duration = f"{dur // 60} daqiqa"
                                            if 1 in movie.episodes:
                                                movie.episodes[1].duration = dur

                                self._details_cache[cache_key] = (now, movie.to_dict())
                                return movie
                except Exception as e:
                    err_desc = f"{type(e).__name__}: {e}".strip(": ")
                    logger.warning(f"Asilmedia get_movie_details error for '{u}': {err_desc}")

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

        # 3. Video oqimlarini qazib olish (Multi-tier parser + sifat bo'yicha qism deduplikatsiyasi)
        amh_id, amh_n = self.extract_amh_params(html)
        if not amh_id and movie_id.isdigit():
            amh_id = movie_id

        quality_rank = {"360p": 0, "480p": 1, "720p": 2, "1080p": 3, "4K": 4}
        ep_groups: Dict[Tuple[int, int], AsilmediaEpisode] = {}
        video_sources: Dict[str, str] = {}
        top_watch_url: Optional[str] = None
        is_series = False

        def _detect_quality(text: str, default_q: str = "1080p") -> str:
            low = (text or "").lower()
            if "2160p" in low or "4k" in low:
                return "4K"
            if "1080p" in low:
                return "1080p"
            if "720p" in low:
                return "720p"
            if "480p" in low:
                return "480p"
            if "360p" in low:
                return "360p"
            return default_q

        def _pick_best_stream(q_urls: Dict[str, str]) -> Tuple[str, str]:
            best_q, best_u, best_score = "1080p", "", -1
            for qk, qu in q_urls.items():
                score = quality_rank.get(qk, 1)
                if score > best_score:
                    best_q, best_u, best_score = qk, qu, score
            return best_q, best_u

        def _register_episode(
            season: int,
            ep_num: int,
            quality: str,
            label: str,
            stream_url: str,
        ) -> None:
            s_u = (stream_url or "").strip()
            if not s_u:
                return
            key = (int(season), int(ep_num))
            if key not in ep_groups:
                ep_groups[key] = AsilmediaEpisode(
                    part=int(ep_num),
                    label=label or f"{ep_num}-qism",
                    url="",
                    season=int(season),
                    episode=int(ep_num),
                    quality=quality,
                    watch_url=None,
                    download_url="",
                    quality_urls={},
                )
            ep = ep_groups[key]
            if self.is_html_wrapper_url(s_u):
                if not ep.watch_url:
                    ep.watch_url = s_u
                return

            # Haqiqiy oqim URL: sifat bo'yicha saqlash va eng yaxshi oqimni tanlash
            existing_q_u = ep.quality_urls.get(quality)
            if not existing_q_u or ("token=" in s_u and "token=" not in existing_q_u):
                ep.quality_urls[quality] = s_u
            best_q, best_u = _pick_best_stream(ep.quality_urls)
            if best_u:
                ep.quality = best_q
                ep.url = best_u
                ep.download_url = best_u
                if label:
                    clean_lbl = re.sub(r"\s*\b(?:360|480|720|1080|2160)p\b", "", label, flags=re.I).strip()
                    ep.label = clean_lbl or label

        def _set_movie_source(q_name: str, src_url: str) -> None:
            nonlocal top_watch_url
            s_u = (src_url or "").strip()
            if not s_u:
                return
            if self.is_html_wrapper_url(s_u):
                if not top_watch_url:
                    top_watch_url = s_u
                return
            video_sources[q_name] = s_u
            best_q, best_u = _pick_best_stream(
                {k: v for k, v in video_sources.items() if k in quality_rank}
            )
            if best_u:
                video_sources["primary"] = best_u

        # Tier 1: id="tg-data" (Telegram stream/download serveri havolalari)
        tg_data_el = soup.find(id="tg-data") if soup else None
        if tg_data_el:
            tg_lines = tg_data_el.get_text().strip().split("\n")
            for line in tg_lines:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                parts = line.split("=", 2)
                if len(parts) == 3:
                    slot_name, label_str, stream_url = parts[0].strip(), parts[1].strip(), parts[2].strip()
                elif len(parts) == 2:
                    slot_name, stream_url = parts[0].strip(), parts[1].strip()
                    label_str = slot_name
                else:
                    continue

                if slot_name.startswith("serialpart"):
                    is_series = True
                    s_idx_m = re.search(r"serialpart(\d+)", slot_name)
                    fallback_idx = int(s_idx_m.group(1)) if s_idx_m else len(ep_groups) + 1
                    season, ep_num, q_val = self.parse_episode_label(label_str, fallback_index=fallback_idx)
                    _register_episode(season, ep_num, q_val, label_str, stream_url)

                elif slot_name.startswith("kino_url"):
                    is_quality_only = bool(re.match(r"^(?:360p|480p|720p|1080p|2160p|4k)(?:\s*[/|]?\s*hd)?$", label_str.strip(), re.I))
                    m_multi = None if is_quality_only else re.search(r"(?:qism\s*[-_]?\s*(\d+)|(\d+)\s*[-_]?\s*qism|[-_\s](\d+)\s*(?:/|qism|hd|$))", label_str, re.I)
                    if m_multi:
                        is_series = True
                        part_hint = int(next(g for g in m_multi.groups() if g))
                        season, ep_num, q_val = self.parse_episode_label(label_str, fallback_index=part_hint)
                        _register_episode(season, ep_num, q_val, label_str, stream_url)
                    else:
                        q_name = _detect_quality(label_str, default_q="480p")
                        _set_movie_source(q_name, stream_url)

        # Tier 2: id="episodes-raw-data" va id="serial-dl-data" (Direct MP4 / am:... CDN fayllar)
        for section_id in ["episodes-raw-data", "serial-dl-data"]:
            sec_el = soup.find(id=section_id) if soup else None
            if sec_el:
                is_series = True
                links = sec_el.find_all("a", href=True)
                for idx, a_tag in enumerate(links, start=1):
                    href = a_tag["href"].strip()
                    lbl = a_tag.get("data-label", "").strip() or a_tag.get_text(strip=True) or f"{idx}-qism"
                    season, ep_num, q_val = self.parse_episode_label(lbl, fallback_index=idx)
                    _register_episode(season, ep_num, q_val, lbl, href)

        # Tier 3: Player tabs (data-url), iframe yoki video teglari
        if soup:
            for btn in soup.find_all(attrs={"data-url": True}):
                d_url = btn.get("data-url", "").strip()
                if not d_url:
                    continue
                d_name = (btn.get("data-name") or btn.get_text(" ", strip=True) or "").strip()
                has_part_marker = bool(re.search(
                    r"(?:\d+\s*[-_]?\s*qism|qism\s*[-_]?\s*\d+|taksi\s*[-_]?\s*\d+|\b(?:part|ep|seriya)\s*[-_]?\s*\d+)",
                    d_name,
                    re.I,
                ))
                if has_part_marker:
                    is_series = True
                    season, ep_num, q_val = self.parse_episode_label(d_name, fallback_index=len(ep_groups) + 1)
                    _register_episode(season, ep_num, q_val, d_name, d_url)
                else:
                    q_name = _detect_quality(f"{d_name} {d_url}", default_q="480p")
                    _set_movie_source(q_name, d_url)

            for ifr in soup.find_all("iframe"):
                src = ifr.get("data-player-src") or ifr.get("src") or ifr.get("data-src")
                if src:
                    src = src.strip()
                    if self.is_html_wrapper_url(src):
                        if not top_watch_url and "server.asilmedia.org" in src.lower():
                            top_watch_url = src
                    elif "fayllar" in src.lower() or src.lower().endswith(".mp4") or src.startswith("am:"):
                        q_name = _detect_quality(src, default_q="1080p")
                        _set_movie_source(q_name, src)

        # Regex fallback: agar soup topilmagan yoki tabs aniqlanmagan bo'lsa
        if not video_sources and not ep_groups:
            for m in re.finditer(r'data-url=["\']((?:https?://|am:)[^"\']+)["\']', html):
                d_url = m.group(1).strip()
                q_name = _detect_quality(d_url, default_q="480p")
                _set_movie_source(q_name, d_url)

        # Tier 4: Script teglari ichidan direct mp4 oqimlarni qidirish
        if not ep_groups and not video_sources and soup:
            for sc in soup.find_all("script"):
                sc_text = sc.string or sc.get_text() or ""
                if not sc_text:
                    continue
                for f_url in re.findall(r'https?://[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?', sc_text):
                    if not self.is_html_wrapper_url(f_url):
                        q_name = _detect_quality(f_url, default_q="1080p")
                        _set_movie_source(q_name, f_url)

        # Guruhlangan qismlarni (season, episode) bo'yicha tartiblash va 1..N raqamlash
        episodes: Dict[int, AsilmediaEpisode] = {}
        for seq_idx, key in enumerate(sorted(ep_groups.keys()), start=1):
            ep = ep_groups[key]
            ep.part = seq_idx
            if not ep.label:
                ep.label = f"{seq_idx}-qism"
            episodes[seq_idx] = ep

        # Agar na episodes, na video_sources, na top_watch_url bo'lsa - kino emas
        if not episodes and not video_sources and not top_watch_url:
            return None
        if re.search(r"asilmedia\s*[-—–]\s*(?:kinolar|bosh)", raw_title, re.I) and not episodes:
            return None

        # Agar serial bo'lmasa va bitta video manbasi bo'lsa, 1-qism sifatida shakllantiramiz
        if not episodes and video_sources:
            best_q, best_url = _pick_best_stream(
                {k: v for k, v in video_sources.items() if k in quality_rank}
            )
            if not best_url:
                best_url = video_sources.get("primary") or next(iter(video_sources.values()), "")
            q_map = {
                k: v for k, v in video_sources.items()
                if k in quality_rank and not self.is_html_wrapper_url(v)
            }
            episodes[1] = AsilmediaEpisode(
                part=1,
                label="To'liq film",
                url=best_url,
                season=1,
                episode=1,
                quality=best_q if best_q in quality_rank else "1080p",
                watch_url=top_watch_url,
                download_url=best_url,
                quality_urls=q_map,
            )

        if not top_watch_url and 1 in episodes:
            top_watch_url = episodes[1].watch_url
        best_dl = None
        if 1 in episodes and episodes[1].download_url and not self.is_html_wrapper_url(episodes[1].download_url):
            best_dl = episodes[1].download_url

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
            watch_url=top_watch_url,
            download_url=best_dl,
            amh_id=amh_id,
            amh_n=amh_n,
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
        from difflib import SequenceMatcher
        generic_noise = {
            "kino", "film", "serial", "multfilm", "anime", "qism", "qismlar",
            "barcha", "fasl", "uzbek", "tilida", "tarjima", "hd", "fhd", "uhd",
            "test", "premyera", "yangi", "part", "season", "episode",
        }
        q_lower = clean_q.lower()
        q_words = [w for w in re.findall(r"[a-z0-9а-яёғқўҳ]+", q_lower) if w not in generic_noise and len(w) >= 2]
        if not q_words:
            q_words = re.findall(r"[a-z0-9а-яёғқўҳ]+", q_lower)

        def score_candidate(cand: Dict[str, Any]) -> int:
            score = 0
            title_relevance = 0
            c_title = cand["title"].lower()
            raw_t = cand.get("raw_title", "").lower()
            c_id = str(cand.get("id"))

            # Kanonik franshizalar uchun to'g'ridan-to'g'ri prioritet
            if ("taksi" in q_lower or "taxi" in q_lower) and c_id == "9165":
                title_relevance += 300
            elif "titan" in q_lower and c_id in ("16913", "14075"):
                title_relevance += 300
            elif ("forsaj" in q_lower or "fast" in q_lower) and c_id in ("14902", "13087", "8563"):
                title_relevance += 250
            elif "chuqur" in q_lower and ("cukur" in raw_t or "serial" in raw_t or cand.get("is_series")):
                title_relevance += 200

            if c_title == q_lower:
                title_relevance += 150
            elif len(q_lower) >= 3 and (c_title.startswith(q_lower) or raw_t.startswith(q_lower)):
                title_relevance += 80
            elif len(q_lower) >= 3 and len(c_title) >= 3 and (q_lower in c_title or c_title in q_lower):
                title_relevance += 50

            c_tokens = set(re.findall(r"[a-z0-9а-яёғқўҳ]+", f"{c_title} {raw_t}"))
            matched_words = [
                w for w in q_words
                if w in c_tokens or (len(w) >= 4 and any(ct.startswith(w) or w.startswith(ct) for ct in c_tokens))
            ]
            segments = [s.strip() for s in re.split(r"[/|()]+", c_title) if len(s.strip()) >= 2] or [c_title]
            best_sim = max(
                (SequenceMatcher(None, re.sub(r"[^a-z0-9а-яёғқўҳ ]+", "", q_lower).strip(),
                                 re.sub(r"[^a-z0-9а-яёғқўҳ ]+", "", seg).strip()).ratio()
                 for seg in segments),
                default=0.0,
            )

            # Mutlaqo aloqasiz kino qaytmasligi uchun (masalan, "Faylsiz Test Kino" -> "Alfa test")
            if title_relevance == 0:
                if not matched_words:
                    return -1
                if len(matched_words) < len(q_words) and best_sim < 0.6:
                    return -1
                title_relevance = int(best_sim * 40) + len(matched_words) * 15

            score += title_relevance

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

        relevant_candidates = [c for c in candidates if score_candidate(c) > 0]
        if not relevant_candidates:
            return None

        relevant_candidates.sort(key=score_candidate, reverse=True)

        # Yuqori ball to'plagan dastlabki nomzodlardan mosini ko'rib chiqish
        best_candidate_movie = None
        for cand in relevant_candidates[:6]:
            movie_det = await self.get_movie_details(cand["url"])
            if movie_det:
                if (is_series or target_parts > 1):
                    if movie_det.total_parts >= target_parts:
                        return movie_det
                    if best_candidate_movie is None or movie_det.total_parts > best_candidate_movie.total_parts:
                        best_candidate_movie = movie_det
                else:
                    return movie_det

        return best_candidate_movie

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
            target_url = str(url or "").strip()
            if self.is_html_wrapper_url(target_url):
                logger.warning(f"HTML/watch sahifa video sifatida yuklanmaydi: {target_url}")
                return None

            if self.needs_fayllar_sign(target_url):
                resolved = await self.resolve_stream_url(target_url)
                if not resolved:
                    logger.warning(f"Asilmedia oqim URL imzolanmadi: {target_url}")
                    return None
                target_url = resolved

            if self.is_html_wrapper_url(target_url) or not target_url.startswith("http"):
                logger.warning(f"Yaroqsiz video URL rad etildi: {target_url}")
                return None

            encoded_url = urllib.parse.quote(target_url, safe=":/%?=&-._~")
            headers = self._get_headers(referer=self.BASE_URL)
            valid_header = False

            async with aiohttp.ClientSession(headers=headers) as session:
                client_timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=30)
                async with session.get(encoded_url, timeout=client_timeout) as resp:
                    if resp.status in (410, 403):
                        logger.warning(f"Video yuklashda HTTP {resp.status} (token eskirgan): {encoded_url}, qayta imzolanmoqda...")
                        clean_url = self.strip_fayllar_token(target_url)
                        re_signed = await self.resolve_stream_url(clean_url, force_refresh=True)
                        if re_signed and re_signed != target_url:
                            logger.info(f"Yangi imzolangan URL olindi: {re_signed}, qayta yuklanmoqda...")
                            return await self.download_video_stream(
                                url=re_signed,
                                destination_path=destination_path,
                                max_bytes=max_bytes,
                                timeout=timeout
                            )
                        logger.warning(f"Qayta imzolash muvaffaqiyatsiz bo'ldi HTTP {resp.status}")
                        return None
                    elif resp.status not in (200, 206):
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
                    if valid_header and temp_file.stat().st_size >= 512 * 1024:
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
                    quality_urls=dict(v.get("quality_urls") or {}),
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
            amh_id=d.get("amh_id"),
            amh_n=d.get("amh_n"),
        )


# Singleton nusxa
asilmedia_service = AsilmediaService()
strip_fayllar_token = AsilmediaService.strip_fayllar_token
needs_fayllar_sign = AsilmediaService.needs_fayllar_sign
