"""
KH Diamond Movie & Drama Series Extractor for Downloader Service
Supports episode listing, metadata parsing, cover art, and stream extraction for khdiamond.net
"""

import os
import re
import ssl
import html as html_lib
import urllib.request
from typing import Optional, Dict, Any, Callable
from services.downloader.extractors.base import BaseDramaExtractor


def _parse_duration_to_sec(dur_str: str) -> int:
    """Parses '0:21:21' or '21:21' into total seconds."""
    parts = (dur_str or "").strip().split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        pass
    return 0


class KHDiamondExtractor(BaseDramaExtractor):
    """Specialized extractor for KH Diamond movies and dubbed Asian series/anime."""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None, silent_resolver: Optional[Callable[[str], str]] = None):
        super().__init__(log_callback)
        self.silent_resolver = silent_resolver

    def can_handle(self, url: str) -> bool:
        return "khdiamond.net" in (url or "").lower()

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans KH Diamond series or single episode/movie details and streaming endpoints."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://khdiamond.net/"
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
                html_text = resp.read().decode("utf-8", errors="ignore")

            title_m = re.search(r'<title>(.*?)</title>', html_text, re.IGNORECASE)
            raw_title = title_m.group(1).split("–")[0].split("-")[0].strip() if title_m else "KH Diamond"
            raw_title = html_lib.unescape(raw_title).strip()

            poster_m = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"]([^\'"]+)[\'"]', html_text, re.IGNORECASE)
            poster = poster_m.group(1).strip() if poster_m else ""

            # Check if this page contains multiple episodes (TV Series)
            entries = []
            
            # Pattern 1: Video Card Grid (e.g. /tvshows/...)
            card_pattern = re.compile(
                r'<div class="video-card">.*?<a[^>]+href="([^"]+)".*?<img[^>]+src="([^"]+)".*?<span class="duration">\s*([^<]+)</span>.*?<div class="title">\s*([^<]+)</div>.*?<div class="meta">.*?<span[^>]*>([^<]+)</span>',
                re.DOTALL
            )
            matches = card_pattern.findall(html_text)

            # Pattern 2: List Items (e.g. <li class='mark-...'>)
            if not matches:
                li_pattern = re.compile(
                    r"<li[^>]*class=['\"][^'\"]*mark-[^'\"]*['\"][^>]*>.*?<a href='([^']+)'[^>]*class='imagen'.*?<div class='sm-ep-runtime'>\s*([^<]+)</div>.*?<img src='([^']+)'.*?<div class='numerando'>([^<]+)</div>.*?<div class='episodiotitle'><a[^>]*>([^<]+)</a>",
                    re.DOTALL
                )
                li_matches = li_pattern.findall(html_text)
                for ep_href, ep_dur, ep_thumb, ep_num, ep_t in li_matches:
                    matches.append((ep_href, ep_thumb, ep_dur, ep_t, ep_num))

            for idx, (ep_href, ep_thumb, ep_dur, ep_t, ep_meta) in enumerate(matches, 1):
                clean_t = html_lib.unescape(ep_t).strip()
                clean_meta = html_lib.unescape(ep_meta).strip()
                dur_sec = _parse_duration_to_sec(ep_dur)

                # Format clean episode display title
                full_ep_title = f"{clean_meta} - {clean_t}" if clean_meta else clean_t

                entries.append({
                    "id": f"khdiamond_ep_{idx}",
                    "title": full_ep_title,
                    "url": ep_href,
                    "webpage_url": ep_href,
                    "duration": dur_sec,
                    "thumbnail": ep_thumb or poster,
                    "is_khdiamond": True
                })

            if len(entries) > 1 or (entries and "/tvshows/" in url.lower()):
                self.log(f"✅ [KH Diamond] ស្កែនឃើញរឿងភាគ: '{raw_title}' (សរុប {len(entries)} ភាគ)")
                
                # Sample formats for playlist table
                sample_formats = [
                    {
                        "format_id": "1080p",
                        "ext": "mp4",
                        "resolution": "1920x1080",
                        "format": "1080P FHD (KH Diamond Stream)",
                        "url": entries[0]["url"],
                        "height": 1080,
                        "vcodec": "avc1",
                        "acodec": "mp4a"
                    },
                    {
                        "format_id": "720p",
                        "ext": "mp4",
                        "resolution": "1280x720",
                        "format": "720P HD (KH Diamond Standard)",
                        "url": entries[0]["url"],
                        "height": 720,
                        "vcodec": "avc1",
                        "acodec": "mp4a"
                    }
                ]

                return {
                    "_type": "playlist",
                    "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
                    "title": f"🎬 {raw_title} (KH Diamond) ({len(entries)} Videos)",
                    "uploader": "KH Diamond (Cambodia)",
                    "thumbnail": poster,
                    "formats": sample_formats,
                    "entries": entries,
                    "is_khdiamond": True
                }

            # Single Movie or Single Episode
            m3u8_m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html_text)
            stream_url = m3u8_m.group(1) if m3u8_m else ""

            if not stream_url and self.silent_resolver:
                self.log(f"⚡ [KH Diamond] កំពុងដោះសោ Stream វីដេអូស្វ័យប្រវត្តិ...")
                stream_url = self.silent_resolver(url)
                if stream_url:
                    self.log(f"✅ [KH Diamond] Stream Ready: {stream_url[:75]}...")

            formats = [
                {
                    "format_id": "1080p",
                    "ext": "mp4",
                    "resolution": "1920x1080",
                    "format_note": "HLS Stream (KH Diamond)",
                    "url": stream_url or url,
                    "height": 1080,
                    "vcodec": "avc1",
                    "acodec": "mp4a"
                }
            ]

            entry = {
                "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
                "title": f"🎬 {raw_title} (KH Diamond)",
                "url": stream_url or url,
                "webpage_url": url,
                "thumbnail": poster,
                "is_khdiamond": True
            }

            return {
                "_type": "video",
                "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
                "title": f"🎬 {raw_title} (KH Diamond)",
                "uploader": "KH Diamond (Cambodia)",
                "thumbnail": poster,
                "tags": ["KH Diamond", "Khmer Dubbed", "Movie"],
                "formats": formats,
                "url": stream_url or "",
                "entries": [entry],
                "is_khdiamond": True
            }
        except Exception as e:
            self.log(f"⚠️ [KH Diamond] Extraction error: {e}")
            return None
