"""
Bilibili Bangumi & Short Drama Extractor for Downloader Service
"""

import os
import re
import ssl
import json
import urllib.request
from typing import Optional, Dict, Any, List
from services.downloader.extractors.base import BaseDramaExtractor
from services.downloader.bypass import BypassEngine


class BilibiliBangumiExtractor(BaseDramaExtractor):
    """
    Specialized extractor for Bilibili Bangumi, Anime, and Short Dramas.
    Supports season/episode listing, multi-episode batching, and regional bypass.
    """

    def can_handle(self, url: str) -> bool:
        u = (url or "").lower()
        is_bili = "bilibili.com" in u or "b23.tv" in u
        has_ep_ss = bool(re.search(r'/(?:ep|ss)\d+', u)) or "bangumi" in u
        is_regular_video = bool(re.search(r'/video/(?:bv|av)', u))
        return is_bili and (has_ep_ss or not is_regular_video and "bangumi" in u)

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans all episodes, series title, cover, duration, and bvid/cid mappings."""
        try:
            ep_m = re.search(r'ep(\d+)', url)
            ss_m = re.search(r'ss(\d+)', url)

            if ep_m:
                api_url = f"https://api.bilibili.com/pgc/view/web/season?ep_id={ep_m.group(1)}"
            elif ss_m:
                api_url = f"https://api.bilibili.com/pgc/view/web/season?season_id={ss_m.group(1)}"
            else:
                return None

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Accept": "application/json, text/plain, */*"
            }
            # Attach GeoBypass headers
            headers.update(BypassEngine.get_geo_bypass_headers("CN"))

            req = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            if data.get("code") != 0:
                err_msg = data.get("message") or f"Code {data.get('code')}"
                self.log(f"⚠️ [Bilibili] API returned non-zero code: {err_msg}")
                return None

            res = data.get("result", {})
            title = res.get("title") or res.get("series_title") or "Bilibili Drama"
            cover = res.get("cover") or ""
            desc = res.get("evaluate") or ""
            eps = res.get("episodes", [])
            if not eps:
                return None

            entries = []
            target_idx = 0
            cur_ep_str = ep_m.group(1) if ep_m else ""

            for idx, ep in enumerate(eps):
                dur = float(ep.get("duration", 0) or 0) / 1000.0
                lt = ep.get("long_title") or ""
                ep_id_str = str(ep.get("id") or ep.get("ep_id") or "")
                if cur_ep_str and ep_id_str == cur_ep_str:
                    target_idx = idx

                entries.append({
                    "id": ep_id_str,
                    "title": f"第{idx+1}集 {lt}".strip(),
                    "url": f"https://www.bilibili.com/bangumi/play/ep{ep_id_str}",
                    "webpage_url": f"https://www.bilibili.com/bangumi/play/ep{ep_id_str}",
                    "duration": dur,
                    "thumbnail": ep.get("cover") or cover,
                    "bvid": ep.get("bvid"),
                    "cid": ep.get("cid"),
                    "is_bilibili_bangumi": True
                })

            tags = ["Bilibili", "短剧", "国创"]
            type_name = res.get("type_name")
            if type_name:
                tags.append(type_name)

            formats = [
                {"format_id": "1080p", "ext": "mp4", "resolution": "1920x1080", "format_note": "Full HD 1080p", "height": 1080, "vcodec": "avc1", "acodec": "mp4a"},
                {"format_id": "720p", "ext": "mp4", "resolution": "1280x720", "format_note": "HD 720p", "height": 720, "vcodec": "avc1", "acodec": "mp4a"},
                {"format_id": "480p", "ext": "mp4", "resolution": "854x480", "format_note": "SD 480p", "height": 480, "vcodec": "avc1", "acodec": "mp4a"}
            ]

            return {
                "_type": "playlist",
                "id": str(res.get("season_id") or (ep_m and ep_m.group(1))),
                "title": f"🎬 {title} (Bilibili)",
                "uploader": "Bilibili (哔哩哔哩)",
                "description": desc,
                "thumbnail": cover,
                "tags": tags,
                "entries": entries,
                "formats": formats,
                "target_index": target_idx,
                "is_bilibili_bangumi": True
            }
        except Exception as e:
            self.log(f"⚠️ [Bilibili Bangumi] Scan failed: {e}")
            return None

