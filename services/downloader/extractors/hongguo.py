"""
Hongguo Short Drama (红果短剧 - hongguoduanju.com) Extractor
"""

import os
import re
import ssl
import json
import urllib.request
from typing import Optional, Dict, Any, Callable
from services.downloader.extractors.base import BaseDramaExtractor


class HongguoExtractor(BaseDramaExtractor):
    """Specialized extractor for Hongguo Short Drama & Series."""

    def can_handle(self, url: str) -> bool:
        return any(d in url.lower() for d in ["hongguoduanju.com", "novelquickapp.com"])

    @staticmethod
    def load_cookies_str_from_file(cookie_file: str, domain: str = "") -> str:
        """Parses Netscape cookie file and formats as standard Cookie request header."""
        if not cookie_file or not os.path.exists(cookie_file):
            return ""
        cookies = []
        try:
            with open(cookie_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        d, _, _, _, _, k, v = parts[:7]
                        if not domain or domain in d.lower():
                            cookies.append(f"{k}={v}")
            return "; ".join(cookies)
        except Exception:
            return ""

    def fetch_play_info(self, series_id: str, item_id: str, cookie_file: str = "", return_err: bool = False):
        """Fetches HD video and audio stream URLs and CENC decryption keys from Hongguo backend."""
        api_url = f"https://hongguoduanju.com/api/drama/item/v1?series_id={series_id}&item_id={item_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": "https://hongguoduanju.com/",
            "Accept": "application/json, text/plain, */*"
        }

        cookie_str = self.load_cookies_str_from_file(cookie_file, domain="hongguo")
        if cookie_str:
            headers["Cookie"] = cookie_str

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                if data.get("code") == 0:
                    v_data = data.get("data", {}).get("video_data", {})
                    # Prefer 720p HD > 480p > 360p
                    p_list = v_data.get("play_url_list", [])
                    best_stream = None
                    for p in p_list:
                        if p.get("definition") == "720p":
                            best_stream = p
                            break
                    if not best_stream and p_list:
                        best_stream = p_list[-1]

                    res = {
                        "main_url": best_stream.get("main_url") if best_stream else "",
                        "definition": best_stream.get("definition") if best_stream else "360p",
                        "audio": v_data.get("audio_data", {}),
                        "player_access_key": best_stream.get("player_access_key") if best_stream else "",
                        "duration": float(v_data.get("duration", 0) or 0)
                    }
                    return (res, "") if return_err else res
                else:
                    err_msg = data.get("message") or f"Code {data.get('code')}"
                    return ({}, err_msg) if return_err else {}
        except Exception as e:
            return ({}, str(e)) if return_err else {}

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans all drama episodes, title, cover, and builds direct video stream entries."""
        try:
            if "novelquickapp.com" in url:
                m_sid = re.search(r'(?:video_)?series_id=(\d+)', url)
                if not m_sid:
                    try:
                        req_r = urllib.request.Request(url, headers={
                            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
                        })
                        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
                        resp_r = opener.open(req_r, timeout=8)
                        m_sid = re.search(r'(?:video_)?series_id=(\d+)', resp_r.geturl())
                    except Exception:
                        pass
                if m_sid:
                    url = f"https://hongguoduanju.com/player/{m_sid.group(1)}"

            ids = re.findall(r'/(\d{10,25})', url)
            if not ids:
                s_m = re.search(r'(?:video_)?series_id=(\d+)', url)
                if s_m:
                    ids = [s_m.group(1)]
            if not ids:
                return None
            series_id = ids[0]
            target_vid = ids[1] if len(ids) > 1 else ""

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Referer": "https://hongguoduanju.com/"
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

            # Extract Title, Description, and Episode 1 Duration from JSON-LD Schema
            title = "Hongguo Short Drama"
            desc = ""
            cover = ""
            tags = []
            ep1_duration = 0
            schemas = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html, re.DOTALL)
            for s in schemas:
                try:
                    s_data = json.loads(s.strip())
                    if isinstance(s_data, dict):
                        if s_data.get("@type") == "TVEpisode" or "partOfSeries" in s_data:
                            series_info = s_data.get("partOfSeries", {})
                            if isinstance(series_info, dict) and series_info.get("name"):
                                title = series_info.get("name")
                            desc = s_data.get("description") or desc
                            img = s_data.get("image")
                            if isinstance(img, list) and img:
                                cover = img[0]
                            elif isinstance(img, str):
                                cover = img

                            dur_str = s_data.get("timeRequired") or s_data.get("duration") or ""
                            if dur_str:
                                m = re.search(r'PT(?:(\d+)M)?(?:(\d+)S)?', dur_str)
                                if m:
                                    mins = int(m.group(1) or 0)
                                    secs = int(m.group(2) or 0)
                                    ep1_duration = mins * 60 + secs
                except Exception:
                    pass

            if title == "Hongguo Short Drama":
                m_title = re.search(r'<title>(.*?)</title>', html)
                if m_title:
                    title = m_title.group(1).split("-")[0].split("_")[0].strip()

            # Extract Category Tags
            tag_matches = re.findall(r'<div[^>]*class=[\'"][^\'"]*video-tag[^\'"]*[\'"][^>]*>(.*?)</div>', html, re.DOTALL)
            for tm in tag_matches:
                clean_t = re.sub(r'<[^>]+>', '', tm).strip()
                if clean_t and clean_t not in tags:
                    tags.append(clean_t)
            if not tags:
                kw_m = re.search(r'<meta[^>]*name=[\'"]keywords[\'"][^>]*content=[\'"](.*?)[\'"]', html, re.IGNORECASE)
                if kw_m:
                    tags = [k.strip() for k in kw_m.group(1).split(",") if k.strip()][:4]

            # Extract Cover Image fallback
            if not cover:
                og_img = re.search(r'<meta[^>]*property=[\'"]og:image[\'"][^>]*content=[\'"](.*?)[\'"]', html)
                if og_img:
                    cover = og_img.group(1)
                else:
                    m_cover = re.search(r'(https://[^\s"\'<>]+\.pstatp\.com/origin/[a-zA-Z0-9_-]+)', html)
                    if m_cover:
                        cover = m_cover.group(1)

            # Extract All Episode IDs
            raw_vids = re.findall(rf'/{series_id}/(\d{{15,25}})', html)
            seen = set()
            clean_vids = []
            for v in raw_vids:
                if v not in seen:
                    seen.add(v)
                    clean_vids.append(v)

            if not clean_vids and target_vid:
                clean_vids = [target_vid]

            # Build Episode Entries
            entries = []
            target_idx = 0
            for idx, vid in enumerate(clean_vids):
                ep_num = idx + 1
                if vid == target_vid:
                    target_idx = idx

                ep_title = f"{title} 第{ep_num}集"
                dur = float(ep1_duration) if (idx == 0 and ep1_duration > 0) else 0.0

                entries.append({
                    "id": vid,
                    "series_id": series_id,
                    "ep_num": ep_num,
                    "title": ep_title,
                    "url": f"https://hongguoduanju.com/video/{series_id}/{vid}",
                    "webpage_url": f"https://hongguoduanju.com/video/{series_id}/{vid}",
                    "duration": dur,
                    "thumbnail": cover,
                    "is_hongguo": True
                })

            formats = [
                {"format_id": "720p", "ext": "mp4", "resolution": "720x1280", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "format": "720P HD (Decrypted Full HD)", "url": entries[0]["url"] if entries else ""}
            ]

            return {
                "_type": "playlist",
                "id": series_id,
                "title": f"🎬 {title} (红果短剧)",
                "uploader": "红果短剧 (Hongguo)",
                "thumbnail": cover,
                "description": desc or f"红果短剧短剧: {title}",
                "tags": tags,
                "entries": entries,
                "formats": formats,
                "target_index": target_idx,
                "is_hongguo": True
            }
        except Exception as e:
            self.log(f"⚠️ [Hongguo] Extractor failed: {e}")
            return None

