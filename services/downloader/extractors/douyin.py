"""
Douyin & TikTok Video Extractor for Downloader Service
Extracts video metadata, author, audio, and bypasses watermarks.
"""

import os
import re
import ssl
import json
import urllib.request
from typing import Optional, Dict, Any
from services.downloader.extractors.base import BaseDramaExtractor
from services.downloader.bypass import BypassEngine


class DouyinExtractor(BaseDramaExtractor):
    """Specialized extractor for Douyin (抖音) with watermark removal."""

    def can_handle(self, url: str) -> bool:
        u = (url or "").lower()
        return any(d in u for d in ["douyin.com", "iesdouyin.com", "v.douyin.com"])

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Extracts Douyin video info and direct watermark-free MP4 stream link."""
        try:
            # 1. Resolve short share redirect if needed (v.douyin.com)
            final_url = url
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
                }
            )
            try:
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
                resp = opener.open(req, timeout=10)
                final_url = resp.geturl()
            except Exception:
                pass

            # 2. Extract item ID (modal_id or video/xxx)
            item_id = ""
            m_modal = re.search(r'modal_id=(\d+)', final_url)
            if m_modal:
                item_id = m_modal.group(1)
            else:
                m_vid = re.search(r'video/(\d+)', final_url)
                if m_vid:
                    item_id = m_vid.group(1)

            if not item_id:
                return None

            # 3. Query Douyin Web API
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={item_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15",
                "Referer": "https://www.douyin.com/"
            }
            headers.update(BypassEngine.get_geo_bypass_headers("CN"))

            req_api = urllib.request.Request(api_url, headers=headers)
            with urllib.request.urlopen(req_api, context=ctx, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8", errors="ignore"))

            item_list = data.get("item_list", [])
            if not item_list:
                return None

            item = item_list[0]
            desc = item.get("desc", "Douyin Video")
            author = item.get("author", {}).get("nickname", "Douyin Creator")
            video_data = item.get("video", {})
            play_addr = video_data.get("play_addr", {}).get("url_list", [])

            raw_stream = play_addr[0] if play_addr else ""
            # Watermark Bypass: replace playwm with play
            clean_stream = BypassEngine.clean_douyin_watermark(raw_stream)

            cover_list = video_data.get("cover", {}).get("url_list", [])
            cover = cover_list[0] if cover_list else ""
            dur = float(item.get("duration", 0) or 0) / 1000.0

            formats = [
                {
                    "format_id": "1080p",
                    "ext": "mp4",
                    "resolution": "1080x1920",
                    "format_note": "No Watermark HD MP4",
                    "url": clean_stream,
                    "height": 1080,
                    "vcodec": "avc1",
                    "acodec": "mp4a"
                }
            ]

            return {
                "_type": "video",
                "id": item_id,
                "title": f"🎬 {desc[:80]} (Douyin)",
                "uploader": author,
                "description": desc,
                "thumbnail": cover,
                "duration": dur,
                "tags": ["Douyin", "Short Video", "No Watermark"],
                "formats": formats,
                "url": clean_stream,
                "is_douyin": True
            }
        except Exception as e:
            self.log(f"⚠️ [Douyin] Extraction failed: {e}")
            return None

