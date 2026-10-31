"""
SabayFlix Movie & Series Extractor for Downloader Service
Supports metadata parsing, cover artwork, episode listings, and stream extraction for sabayflix.net
"""

import os
import re
import ssl
import json
import urllib.request
from typing import Optional, Dict, Any, Callable
from services.downloader.extractors.base import BaseDramaExtractor


class SabayflixExtractor(BaseDramaExtractor):
    """Specialized extractor for SabayFlix Cambodian movies and series streaming platform."""

    API_BASE = "https://api-v2.sf-api.net/api/v1"

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, silent_resolver: Optional[Callable[[str], str]] = None):
        super().__init__(log_callback)
        self.silent_resolver = silent_resolver

    def can_handle(self, url: str) -> bool:
        return "sabayflix.net" in (url or "").lower()

    def _extract_access_token_from_cookie(self, cookie_file: str = "") -> str:
        """Extracts accessToken from cookiefile or Netscape cookies text if present."""
        if not cookie_file or not os.path.exists(cookie_file):
            return ""
        try:
            with open(cookie_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for line in content.splitlines():
                if "accessToken" in line or "token" in line:
                    parts = line.strip().split("\t")
                    if len(parts) >= 7 and "token" in parts[5].lower():
                        return parts[6].strip()
            # Also check if cookie file is raw json
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    return data.get("accessToken") or data.get("token") or ""
            except Exception:
                pass
        except Exception:
            pass
        return ""

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans SabayFlix movie/series metadata, cover, duration, and stream."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # 1. Extract film hash from URL (e.g. /movie/aCPST9k5o1sM or /series/...)
            hash_m = re.search(r'/(?:movie|film|series|watch)/([a-zA-Z0-9_\-]+)', url)
            film_hash = hash_m.group(1) if hash_m else ""

            if not film_hash:
                # Fallback: check query string
                q_m = re.search(r'[?&](?:hash|id)=([a-zA-Z0-9_\-]+)', url)
                film_hash = q_m.group(1) if q_m else ""

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Origin": "https://www.sabayflix.net",
                "Referer": "https://www.sabayflix.net/"
            }

            token = self._extract_access_token_from_cookie(cookie_file)
            if token:
                headers["Authorization"] = f"Bearer {token}"

            # 2. Fetch film metadata from SabayFlix API
            film_data = {}
            if film_hash:
                api_url = f"{self.API_BASE}/film?hash={film_hash}"
                try:
                    req = urllib.request.Request(api_url, headers=headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
                        film_data = json.loads(r.read().decode('utf-8', errors='ignore'))
                except Exception as e:
                    self.log(f"⚠️ [SabayFlix API] Error fetching film metadata: {e}")

            title = film_data.get("title") or "SabayFlix Movie"
            desc = film_data.get("description") or ""
            cover = film_data.get("cover_url") or film_data.get("poster_url") or ""
            poster = film_data.get("poster_url") or cover
            duration_mins = film_data.get("duration") or 90
            duration_sec = int(duration_mins) * 60
            year = film_data.get("year") or 2026
            f_type = film_data.get("type") or "movie"
            category_name = film_data.get("inCategory", {}).get("name", "")
            if "||" in category_name:
                category_name = category_name.split("||")[0].strip()

            subscription = film_data.get("subscription") or "free"

            # 3. Attempt direct stream resolution
            stream_url = ""
            if film_hash:
                stream_api = f"{self.API_BASE}/stream?film_hash={film_hash}&type={f_type}"
                try:
                    req_s = urllib.request.Request(stream_api, headers=headers)
                    with urllib.request.urlopen(req_s, context=ctx, timeout=10) as r_s:
                        s_data = json.loads(r_s.read().decode('utf-8', errors='ignore'))
                        if isinstance(s_data, str) and (s_data.startswith("http") or ".m3u8" in s_data):
                            stream_url = s_data
                        elif isinstance(s_data, dict):
                            stream_url = s_data.get("stream") or s_data.get("url") or s_data.get("src") or ""
                except urllib.error.HTTPError as h_err:
                    if h_err.code == 401:
                        self.log("🔒 [SabayFlix Notice] រឿងនេះតម្រូវឱ្យមាន Login/គណនី SabayFlix (Member Only)!")
                        self.log("💡 [Sniffer Notice] សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បី Login រួចប្រព័ន្ធនឹងចាប់យក Stream (.m3u8) ស្វ័យប្រវត្តិ!")
                    else:
                        self.log(f"⚠️ [SabayFlix Stream API] HTTP {h_err.code}")
                except Exception as e:
                    self.log(f"⚠️ [SabayFlix Stream API] {e}")

            # 4. If resolver provided and no stream yet
            if not stream_url and self.silent_resolver:
                self.log(f"⚡ [SabayFlix] កំពុងដោះសោ Stream វីដេអូស្វ័យប្រវត្តិ...")
                stream_url = self.silent_resolver(url)
                if stream_url:
                    self.log(f"✅ [SabayFlix] Stream Ready: {stream_url[:75]}...")

            # 5. Build entry & formats
            tags = ["SabayFlix", "Khmer Movie"]
            if category_name:
                tags.append(category_name)
            if year:
                tags.append(str(year))

            formats = [
                {
                    "format_id": "1080p",
                    "ext": "mp4",
                    "resolution": "1920x1080",
                    "format": "1080P FHD (SabayFlix Native Stream)",
                    "url": stream_url or url,
                    "height": 1080,
                    "vcodec": "avc1",
                    "acodec": "mp4a"
                },
                {
                    "format_id": "720p",
                    "ext": "mp4",
                    "resolution": "1280x720",
                    "format": "720P HD (SabayFlix Standard Stream)",
                    "url": stream_url or url,
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "mp4a"
                }
            ]

            entry = {
                "id": film_hash or "sabayflix_movie",
                "title": f"🎬 {title} (SabayFlix)",
                "url": stream_url or "",
                "webpage_url": url,
                "duration": duration_sec,
                "thumbnail": cover or poster,
                "is_sabayflix": True
            }

            return {
                "_type": "video",
                "id": film_hash or "sabayflix_movie",
                "title": f"🎬 {title} (SabayFlix)",
                "uploader": "SabayFlix (Cambodia)",
                "thumbnail": cover or poster,
                "description": desc or f"SabayFlix: {title}",
                "duration": duration_sec,
                "tags": tags,
                "formats": formats,
                "url": stream_url or "",
                "entries": [entry],
                "is_sabayflix": True
            }
        except Exception as e:
            self.log(f"⚠️ [SabayFlix] Extraction failed: {e}")
            return None
