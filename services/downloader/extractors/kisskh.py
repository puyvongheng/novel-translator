"""
KissKH Asian Drama (kisskh.do / kisskh.me / kisskh.co) Extractor
"""

import re
import ssl
import json
import urllib.request
from typing import Optional, Dict, Any, Callable
from services.downloader.extractors.base import BaseDramaExtractor


class KissKHExtractor(BaseDramaExtractor):
    """Specialized extractor for KissKH Asian Drama streaming platform."""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, silent_resolver: Optional[Callable[[str], str]] = None):
        super().__init__(log_callback)
        self.silent_resolver = silent_resolver

    def can_handle(self, url: str) -> bool:
        return "kisskh." in url.lower()

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans drama episodes, metadata, cover, and resolves direct m3u8 streams."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            # 1. Parse drama id & episode id
            id_m = re.search(r'[?&]id=(\d+)', url)
            drama_id = id_m.group(1) if id_m else ""
            ep_m = re.search(r'[?&]ep=(\d+)', url)
            target_ep_id = int(ep_m.group(1)) if ep_m else 0

            num_m = re.search(r'Episode-(\d+)', url, re.IGNORECASE)
            target_ep_num = int(num_m.group(1)) if num_m else 1

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://kisskh.do/"
            }

            slug = ""
            title_match = re.search(r'/Drama/([^/?#]+)', url)
            if title_match:
                slug = title_match.group(1).replace("-", " ")

            # Auto-resolve drama_id via Search API if not present in query string
            if not drama_id and slug:
                search_url = f"https://kisskh.do/api/DramaList/Search?q={urllib.request.quote(slug)}&type=0"
                try:
                    req_s = urllib.request.Request(search_url, headers=headers)
                    with urllib.request.urlopen(req_s, context=ctx, timeout=10) as r_s:
                        res_s = json.loads(r_s.read().decode('utf-8'))
                        if res_s and isinstance(res_s, list):
                            for item in res_s:
                                if slug.lower() in item.get("title", "").lower() or item.get("title", "").lower() in slug.lower():
                                    drama_id = str(item.get("id"))
                                    break
                            if not drama_id and len(res_s) > 0:
                                drama_id = str(res_s[0].get("id"))
                except Exception as e:
                    self.log(f"⚠️ [KissKH Search] Auto-resolve drama ID error: {e}")

            # 2. Fetch Drama Metadata
            drama_title = slug or "Asian Drama"
            cover = ""
            desc = ""
            episodes_raw = []

            if drama_id:
                api_drama = f"https://kisskh.do/api/DramaList/Drama/{drama_id}"
                req = urllib.request.Request(api_drama, headers=headers)
                try:
                    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                        drama_data = json.loads(r.read().decode('utf-8', errors='ignore'))
                        drama_title = drama_data.get("title") or drama_data.get("drama_name") or drama_title
                        cover = drama_data.get("thumbnail") or ""
                        desc = drama_data.get("description") or ""
                        episodes_raw = drama_data.get("episodes") or []
                except Exception as e:
                    self.log(f"⚠️ [KissKH API] Metadata fetch error: {e}")

            if drama_title == "Asian Drama":
                title_match = re.search(r'/Drama/([^/?#]+)', url)
                if title_match:
                    drama_title = title_match.group(1).replace("-", " ")

            # 3. Build episode entries & determine target page URL
            entries = []
            target_idx = 0
            target_page_url = url
            slug_title = re.sub(r'[^a-zA-Z0-9]+', '-', drama_title).strip('-')

            if episodes_raw:
                episodes_raw.sort(key=lambda x: float(x.get("number", 0) or 0))
                for idx, ep_obj in enumerate(episodes_raw):
                    ep_id = ep_obj.get("id")
                    ep_num = int(float(ep_obj.get("number", idx + 1) or (idx + 1)))
                    ep_title = f"{drama_title} - Episode {ep_num:02d}"
                    ep_page_url = f"https://kisskh.do/Drama/{slug_title}/Episode-{ep_num}?id={drama_id}&ep={ep_id}"

                    is_target = (target_ep_id and ep_id == target_ep_id) or (not target_ep_id and ep_num == target_ep_num)
                    if is_target:
                        target_idx = idx
                        target_page_url = ep_page_url

                    entries.append({
                        "id": str(ep_id),
                        "ep_num": ep_num,
                        "title": ep_title,
                        "url": "",  # Populated after resolution
                        "webpage_url": ep_page_url,
                        "duration": 3600,
                        "thumbnail": cover,
                        "is_kisskh": True
                    })

                if not target_page_url and entries:
                    target_page_url = entries[0]["webpage_url"]
            else:
                entries.append({
                    "id": str(target_ep_id or "1"),
                    "ep_num": target_ep_num,
                    "title": f"{drama_title} - Episode {target_ep_num:02d}",
                    "url": "",
                    "webpage_url": url,
                    "duration": 3600,
                    "thumbnail": cover,
                    "is_kisskh": True
                })

            # 4. Resolve target episode stream silently if resolver provided
            stream_url = ""
            if self.silent_resolver and target_page_url:
                self.log(f"⚡ [KissKH] Resolving stream for Episode {target_ep_num}...")
                stream_url = self.silent_resolver(target_page_url)
                if stream_url:
                    self.log(f"✅ [KissKH] Stream Ready: {stream_url[:75]}...")
                    if target_idx < len(entries):
                        entries[target_idx]["url"] = stream_url

            formats = [
                {
                    "format_id": "1080p",
                    "ext": "mp4",
                    "height": 1080,
                    "resolution": "1920x1080",
                    "format": "1080P HD (Native KissKH HLS Stream)",
                    "url": stream_url or (entries[0]["url"] if entries else ""),
                    "vcodec": "avc1",
                    "acodec": "mp4a"
                }
            ]

            return {
                "_type": "playlist",
                "id": drama_id or "kisskh",
                "title": f"🎬 {drama_title} (KissKH)",
                "uploader": "KissKH Asian Drama",
                "thumbnail": cover,
                "description": desc or f"KissKH Drama: {drama_title}",
                "entries": entries,
                "formats": formats,
                "target_index": target_idx,
                "is_kisskh": True
            }
        except Exception as e:
            self.log(f"⚠️ [KissKH] Scan failed: {e}")
            return None

