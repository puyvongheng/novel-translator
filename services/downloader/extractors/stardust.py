"""
StardustTV Short Drama (stardusttv.net) Extractor
"""

import re
import ssl
import urllib.request
from typing import Optional, Dict, Any
from services.downloader.extractors.base import BaseDramaExtractor


class StardustExtractor(BaseDramaExtractor):
    """Specialized extractor for StardustTV Short Drama platform."""

    def can_handle(self, url: str) -> bool:
        u = url.lower()
        return "stardusttv.net" in u or "stardust-tv" in u

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans all drama episodes, m3u8 streams, title, cover, and builds playlist entries."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Referer": "https://www.stardusttv.net/"
                }
            )
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                buf = []
                while True:
                    c = resp.read(65536)
                    if not c:
                        break
                    buf.append(c)
                html = b"".join(buf).decode('utf-8', errors='ignore')

            # Series Title
            series_title = "Short Drama"
            t_m = re.search(r'Episode\s*\d+-(.*?)\s*StardustTV', html, re.IGNORECASE)
            if t_m:
                series_title = t_m.group(1).strip()
            elif "<title>" in html:
                title_tag = re.search(r'<title>(.*?)</title>', html)
                if title_tag:
                    series_title = title_tag.group(1).split("-")[0].strip()

            # Series ID
            id_m = re.search(r'-(\d+)(?:[/?#]|$)', url)
            series_id = id_m.group(1) if id_m else "23560"

            # Cover
            cover = ""
            cover_m = re.search(r'https://[^\s"\'<>]+\.stardust-tv\.com/prod/\d+/1/thumbnail_[a-zA-Z0-9_-]+\.jpg', html)
            if cover_m:
                cover = cover_m.group(0)

            # All episodes m3u8 streams
            pattern = re.compile(r'(https?://[a-zA-Z0-9_.-]*stardust-tv\.com/prod/\d+/(\d+)/[a-zA-Z0-9_-]+\.m3u8)')
            entries = []
            seen = set()
            for m3u8_url, ep_num_str in pattern.findall(html):
                ep_num = int(ep_num_str)
                if ep_num not in seen:
                    seen.add(ep_num)
                    thumb_url = f"https://v.stardust-tv.com/prod/{series_id}/{ep_num}/thumbnail.jpg"
                    spec_thumb = re.search(r'(https://v\.stardust-tv\.com/prod/' + str(series_id) + r'/' + str(ep_num) + r'/thumbnail_[a-zA-Z0-9_-]+\.jpg)', html)
                    if spec_thumb:
                        thumb_url = spec_thumb.group(1)
                    elif cover:
                        thumb_url = cover

                    ep_title = f"{series_title} - Episode {ep_num:02d}"
                    slug_title = series_title.lower().replace(" ", "-")
                    entries.append({
                        "id": f"{series_id}_{ep_num}",
                        "ep_num": ep_num,
                        "title": ep_title,
                        "url": m3u8_url,
                        "webpage_url": f"https://www.stardusttv.net/episodes/{ep_num:02d}-{slug_title}-{series_id}",
                        "duration": 90,
                        "thumbnail": thumb_url
                    })

            entries.sort(key=lambda x: x["ep_num"])

            formats = [
                {"format_id": "1080p", "ext": "mp4", "resolution": "1080x1920", "format": "1080P HD (Native StardustTV Stream)", "url": entries[0]["url"] if entries else ""}
            ]

            return {
                "_type": "playlist",
                "id": series_id,
                "title": f"🎬 {series_title} (StardustTV)",
                "uploader": "StardustTV Short Drama",
                "thumbnail": cover,
                "description": f"StardustTV Series: {series_title}",
                "entries": entries,
                "formats": formats,
                "is_stardust": True
            }
        except Exception as e:
            self.log(f"⚠️ [StardustTV] Scan failed: {e}")
            return None

