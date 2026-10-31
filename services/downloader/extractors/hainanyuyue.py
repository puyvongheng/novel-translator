"""
Hainan Yuyue Short Drama (海南愉悦短剧 - hainanyuyue.com / kylin.hainanyuyue.com) Extractor
"""

import re
import ssl
import json
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any
from services.downloader.extractors.base import BaseDramaExtractor


class HainanYuyueExtractor(BaseDramaExtractor):
    """Specialized extractor for Hainan Yuyue Short Drama platform."""

    def can_handle(self, url: str) -> bool:
        u = url.lower()
        return "hainanyuyue.com" in u or "kylin.hainanyuyue.com" in u

    def fetch_play_url(self, ch_id: str, video_id: str, enc_did: str, uid: str) -> str:
        """Fetches direct video stream URL for a Hainan Yuyue episode."""
        if not ch_id:
            return ""
        try:
            scheme = json.dumps({
                'video_series_id': '',
                'vs_id_type': '1',
                'source': '8',
                'module_name': 'share',
                'vid': ch_id,
                'share_toast_vid': ch_id,
                'share_ab_group': 2,
                'video_id': video_id
            })
            zlink = f'https://kylin.hainanyuyue.com/LoRoS?schemeParams={urllib.parse.quote(scheme)}'
            params = {
                'encrypt_did': enc_did,
                'uid': uid,
                'zlink': zlink,
                'share_type': '4',
                'landing_source': 'share'
            }
            ep_url = f'https://hainanyuyue.com/share/video-animation-share?{urllib.parse.urlencode(params)}'
            req = urllib.request.Request(
                ep_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
            )
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
                ep_html = r.read().decode('utf-8', errors='ignore')
            m = re.search(r'window\._ROUTER_DATA\s*=\s*(\{.*)', ep_html)
            if m:
                d = json.JSONDecoder().raw_decode(m.group(1))[0]
                for _, lv in d.get("loaderData", {}).items():
                    if isinstance(lv, dict) and "pageData" in lv:
                        return lv["pageData"].get("series_data", {}).get("play_url", "")
        except Exception as e:
            self.log(f"⚠️ [Hainan Yuyue] Failed to fetch episode {ch_id}: {e}")
        return ""

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        """Scans drama episodes, metadata, cover, and builds direct video stream entries."""
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}
            )
            with urllib.request.urlopen(req, context=ctx, timeout=12) as resp:
                final_url = resp.geturl()
                html = resp.read().decode('utf-8', errors='ignore')

            router_m = re.search(r'window\._ROUTER_DATA\s*=\s*(\{.*)', html)
            if not router_m:
                return None

            data = json.JSONDecoder().raw_decode(router_m.group(1))[0]
            loader = data.get("loaderData", {})
            page_data = None
            parent_v = {}
            for k, v in loader.items():
                if isinstance(v, dict) and "pageData" in v:
                    page_data = v["pageData"]
                    parent_v = v
                    break

            if not page_data:
                return None

            series = page_data.get("series_data", {})
            title = series.get("title") or "Hainan Yuyue Short Drama"
            desc = series.get("series_intro") or ""
            cover = series.get("series_cover") or ""
            tags = series.get("category_list") or ([series.get("category")] if series.get("category") else ["短剧", "海南愉悦", "720P HD"])
            chapter_ids = page_data.get("chapter_ids") or []
            used_ch_id = str(page_data.get("used_chapter_id") or "")
            first_play_url = series.get("play_url") or ""

            # Base context params for fetching other chapters
            params_d = parent_v.get("params") or {}
            link_params = parent_v.get("linkParams") or {}
            enc_did = params_d.get("encrypt_did", "")
            uid = link_params.get("uid", "")
            video_id = params_d.get("video_id", "")

            # Fallback to query params from final_url if empty
            if not enc_did or not uid or not video_id:
                parsed = urllib.parse.urlparse(final_url)
                qs = urllib.parse.parse_qs(parsed.query)
                enc_did = enc_did or qs.get("encrypt_did", [""])[0]
                uid = uid or qs.get("uid", [""])[0]
                if not video_id:
                    zlink = qs.get("zlink", [""])[0]
                    sm = re.search(r'video_id(?:%22%3A%22|":"|\s*:\s*")(\d+)', zlink)
                    if sm:
                        video_id = sm.group(1)

            target_idx = 0
            episodes = []
            if chapter_ids:
                for idx, ch_id in enumerate(chapter_ids):
                    ep_num = idx + 1
                    is_cur = (ch_id == used_ch_id) or (idx == 0 and not used_ch_id)
                    if is_cur:
                        target_idx = idx

                    ep_url = first_play_url if is_cur else ""
                    episodes.append({
                        "id": ch_id,
                        "ch_id": ch_id,
                        "ep_num": ep_num,
                        "title": f"{title} 第{ep_num}集",
                        "url": ep_url,
                        "webpage_url": final_url,
                        "duration": 90,
                        "thumbnail": cover,
                        "is_hainanyuyue": True,
                        "video_id": video_id,
                        "enc_did": enc_did,
                        "uid": uid
                    })
            else:
                episodes.append({
                    "id": used_ch_id or "1",
                    "ch_id": used_ch_id,
                    "ep_num": 1,
                    "title": f"{title} 第1集",
                    "url": first_play_url,
                    "webpage_url": final_url,
                    "duration": 90,
                    "thumbnail": cover,
                    "is_hainanyuyue": True,
                    "video_id": video_id,
                    "enc_did": enc_did,
                    "uid": uid
                })

            formats = [
                {"format_id": "720p", "ext": "mp4", "resolution": "1280x720", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "format": "720P HD (Hainan Yuyue MP4 Direct)", "url": first_play_url}
            ]

            return {
                "_type": "playlist",
                "id": video_id or "hainanyuyue",
                "title": f"🎬 {title} (海南愉悦)",
                "uploader": "海南愉悦 (Hainan Yuyue)",
                "thumbnail": cover,
                "description": desc or f"海南愉悦短剧: {title}",
                "tags": tags,
                "entries": episodes,
                "formats": formats,
                "target_index": target_idx,
                "is_hainanyuyue": True
            }
        except Exception as e:
            self.log(f"⚠️ [Hainan Yuyue] Extractor failed: {e}")
            return None

