"""
Universal Social Media & Image Extractor for Downloader Service
Supports Telegram, Pinterest, Pngtree, Facebook Stories/Photos, and Instagram
"""

import os
import re
import ssl
import json
import urllib.request
from typing import Optional, Dict, Any, Callable
from services.downloader.extractors.base import BaseDramaExtractor

try:
    from curl_cffi import requests as cffi_requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False


class UniversalSocialExtractor(BaseDramaExtractor):
    """
    Unified Extractor for Telegram, Pinterest, Pngtree, Facebook Stories/Photos, and Instagram.
    Extracts direct HD video streams and original pristine images/PNGs.
    """

    def can_handle(self, url: str) -> bool:
        u = (url or "").lower()
        return any(d in u for d in [
            "t.me/", "telegram.me/", "pinterest.com", "pin.it",
            "pngtree.com", "facebook.com", "fb.watch", "instagram.com"
        ])

    def _fetch_html(self, url: str, cookie_file: str = "") -> str:
        """Fetches page content with browser impersonation and Netscape cookie support."""
        cookie_header = ""
        if cookie_file and os.path.exists(cookie_file):
            try:
                cookies = []
                with open(cookie_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            parts = line.split("\t")
                            if len(parts) >= 7:
                                cookies.append(f"{parts[5]}={parts[6]}")
                if cookies:
                    cookie_header = "; ".join(cookies)
            except Exception:
                pass

        if CURL_CFFI_AVAILABLE:
            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                }
                if cookie_header:
                    headers["Cookie"] = cookie_header
                r = cffi_requests.get(url, headers=headers, impersonate="chrome124", allow_redirects=True, timeout=12)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            }
            if cookie_header:
                headers["Cookie"] = cookie_header
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def extract_series(self, url: str, cookie_file: str = "") -> Optional[Dict[str, Any]]:
        u = (url or "").strip()
        u_lower = u.lower()

        # ── 1. TELEGRAM (t.me/... or telegram.me/...) ──
        if "t.me/" in u_lower or "telegram.me/" in u_lower:
            return self._extract_telegram(u, cookie_file)

        # ── 2. PINTEREST (pinterest.com or pin.it) ──
        elif "pinterest.com" in u_lower or "pin.it" in u_lower:
            return self._extract_pinterest(u, cookie_file)

        # ── 3. PNGTREE (pngtree.com) ──
        elif "pngtree.com" in u_lower:
            return self._extract_pngtree(u, cookie_file)

        # ── 4. FACEBOOK STORIES, PHOTOS, SHARE REDIRECTS ──
        elif "facebook.com" in u_lower or "fb.watch" in u_lower:
            return self._extract_facebook(u, cookie_file)

        # ── 5. INSTAGRAM REELS, POSTS, STORIES ──
        elif "instagram.com" in u_lower:
            return self._extract_instagram(u, cookie_file)

        return None

    def _extract_telegram(self, url: str, cookie_file: str) -> Optional[Dict[str, Any]]:
        """Extracts media from public Telegram message embeds (video, photo, text)."""
        self.log(f"✈️ [Telegram] កំពុងស្កែនសារ និងមេឌៀ (Scanning Telegram Media)...")
        # Ensure embed=1 parameter for widget embed
        embed_url = url if "embed=1" in url else (url.split("?")[0] + "?embed=1")
        html = self._fetch_html(embed_url, cookie_file)

        # Extract Channel / User Name
        author_m = re.search(r'<div class="tgme_widget_message_owner_name">.*?<span[^>]*>(.*?)</span>', html, re.DOTALL)
        author = author_m.group(1).strip() if author_m else "Telegram Channel"

        # Extract Text
        text_m = re.search(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        raw_text = re.sub(r'<[^>]+>', ' ', text_m.group(1)).strip() if text_m else ""
        short_title = raw_text[:60] if raw_text else f"Telegram Media from {author}"

        # 1. Check for Video
        vid_m = re.search(r'<video[^>]+src="([^"]+)"', html)
        video_url = vid_m.group(1).replace("&amp;", "&") if vid_m else ""

        # 2. Check for Photos
        imgs = re.findall(r"background-image:url\('([^']+)'\)", html)
        img_url = imgs[0] if imgs else ""

        if not video_url and not img_url:
            # Fallback check for single img tags
            img_tag_m = re.search(r'<img[^>]+src="([^"]+)"', html)
            if img_tag_m and "cdn" in img_tag_m.group(1):
                img_url = img_tag_m.group(1)

        if not video_url and not img_url:
            self.log("ℹ️ [Telegram] មិនមានឯកសារ Video ឬ Image នៅក្នុង Link នេះទេ (ប្រហែលជាសារអក្សរសុទ្ធ ឬ Channel Private)!")
            return None

        # Build Format Entries
        formats = []
        is_video = bool(video_url)
        media_url = video_url if is_video else img_url
        ext = "mp4" if is_video else ("jpg" if ".jpg" in img_url.lower() else "png")

        formats.append({
            "format_id": "hd" if is_video else "original",
            "ext": ext,
            "resolution": "1920x1080" if is_video else "Original High-Res",
            "format": f"Telegram {'Video (MP4)' if is_video else 'Original Photo'}",
            "url": media_url,
            "vcodec": "avc1" if is_video else None,
            "acodec": "mp4a" if is_video else None
        })

        self.log(f"✅ [Telegram] រកឃើញ {'វីដេអូ HD' if is_video else 'រូបភាពច្បាស់ HD'} ពី '{author}'!")

        return {
            "_type": "video" if is_video else "image",
            "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
            "title": f"🎬 {author} - {short_title}" if is_video else f"🖼️ {author} - {short_title}",
            "uploader": author,
            "thumbnail": img_url or video_url,
            "description": raw_text,
            "formats": formats,
            "url": media_url,
            "is_image": not is_video,
            "is_telegram": True
        }

    def _extract_pinterest(self, url: str, cookie_file: str) -> Optional[Dict[str, Any]]:
        """Extracts original lossless image or video from Pinterest pins."""
        self.log(f"📌 [Pinterest] កំពុងស្កែនរូបភាព HD / វីដេអូ (Scanning Pinterest Media)...")
        # Follow pin.it redirects if necessary
        real_url = url
        if "pin.it" in url and CURL_CFFI_AVAILABLE:
            try:
                r = cffi_requests.get(url, impersonate="chrome124", allow_redirects=True, timeout=8)
                real_url = r.url
            except Exception:
                pass

        html = self._fetch_html(real_url, cookie_file)

        # Extract Title from <title> tag as fallback
        title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_m.group(1).split("|")[0].split("on Pinterest")[0].strip() if title_m else "Pinterest Pin"

        best_img = ""
        video_url = ""

        # 1. Check Schema.org JSON-LD for exact pin headline, original image, and video
        for s in re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                d = json.loads(s)
                if isinstance(d, dict):
                    cand_title = d.get("headline") or d.get("name")
                    if cand_title and cand_title != "Pinterest":
                        title = cand_title.strip()
                    if d.get("contentUrl") and (".mp4" in d["contentUrl"] or "v.pinimg.com" in d["contentUrl"]):
                        video_url = d["contentUrl"]
                    cand_img = d.get("image")
                    if isinstance(cand_img, str) and "pinimg.com" in cand_img:
                        best_img = cand_img.replace("/736x/", "/originals/").replace("/474x/", "/originals/")
                    elif isinstance(cand_img, dict) and cand_img.get("url"):
                        best_img = cand_img["url"].replace("/736x/", "/originals/").replace("/474x/", "/originals/")
            except Exception:
                pass

        # 2. Check for Video (v.pinimg.com or 720p.mp4)
        if not video_url:
            vids = re.findall(r'https://v\.pinimg\.com/[^\s"\'<>]+\.mp4', html)
            if not vids:
                vids = re.findall(r'<meta[^>]*property=["\']og:video["\'][^>]*content=["\']([^"\']+)["\']', html)
            video_url = vids[0] if vids else ""

        # 3. Check for Highest-Resolution Image if not found in JSON-LD
        if not best_img:
            og_imgs = re.findall(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
            if og_imgs:
                best_img = og_imgs[0].replace("/736x/", "/originals/").replace("/474x/", "/originals/")
            else:
                pin_imgs = re.findall(r'https://i\.pinimg\.com/[^\s"\'<>]+\.(?:jpg|png|webp)', html)
                for img in pin_imgs:
                    if "/originals/" in img:
                        best_img = img
                        break
                if not best_img:
                    for img in pin_imgs:
                        if "/736x/" in img:
                            best_img = img.replace("/736x/", "/originals/")
                            break
                if not best_img and pin_imgs:
                    best_img = pin_imgs[0]

        is_video = bool(video_url)
        media_url = video_url if is_video else best_img

        if not media_url:
            self.log("⚠️ [Pinterest] មិនទាន់ទទួលបាន Media URL ដោយផ្ទាល់ទេ!")
            return None

        ext = "mp4" if is_video else ("png" if ".png" in best_img.lower() else "jpg")
        formats = [{
            "format_id": "hd" if is_video else "original",
            "ext": ext,
            "resolution": "1080p" if is_video else "Lossless Original HD",
            "format": f"Pinterest {'Video (MP4)' if is_video else 'Original Lossless Image'}",
            "url": media_url
        }]

        self.log(f"✅ [Pinterest] រកឃើញ {'វីដេអូ HD' if is_video else 'រូបភាពច្បាស់ Lossless Original'}!")

        return {
            "_type": "video" if is_video else "image",
            "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
            "title": f"🎬 {title} (Pinterest)" if is_video else f"🖼️ {title} (Pinterest)",
            "uploader": "Pinterest",
            "thumbnail": best_img or video_url,
            "formats": formats,
            "url": media_url,
            "is_image": not is_video,
            "is_pinterest": True
        }

    def _extract_pngtree(self, url: str, cookie_file: str) -> Optional[Dict[str, Any]]:
        """Extracts transparent PNG graphic and high-res vector art from Pngtree."""
        self.log(f"🌲 [Pngtree] កំពុងស្កែនរូបភាព Transparent PNG (Scanning Pngtree Graphic)...")
        html = self._fetch_html(url, cookie_file)

        title_m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE)
        title = title_m.group(1).split("|")[0].split("PNG")[0].strip() if title_m else "Pngtree Graphic"

        # Search for high-res PNG CDN urls (png.pngtree.com or img.pngtree.com)
        imgs = re.findall(r'https?://(?:png|img)\.pngtree\.com/[^\s"\'<>]+\.(?:png|jpg|webp)', html)
        best_png = ""
        for img in imgs:
            if "png-clipart" in img or "element" in img or "background" in img:
                best_png = img
                break
        if not best_png and imgs:
            best_png = imgs[0]

        if not best_png:
            self.log("🔒 [Pngtree Notice] ទំព័រ Pngtree នេះត្រូវការ Cloudflare Captcha Clearance!")
            self.log("💡 សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីបើកទំព័រនេះ នោះប្រព័ន្ធនឹងចាប់យកឯកសារ Transparent PNG ស្វ័យប្រវត្តិ!")
            return None

        self.log(f"✅ [Pngtree] រកឃើញរូបភាព Transparent PNG គុណភាពខ្ពស់!")

        return {
            "_type": "image",
            "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
            "title": f"🖼️ {title} (Pngtree PNG)",
            "uploader": "Pngtree",
            "thumbnail": best_png,
            "formats": [{
                "format_id": "original",
                "ext": "png",
                "resolution": "Original PNG (Transparent)",
                "format": "Pngtree Transparent PNG",
                "url": best_png
            }],
            "url": best_png,
            "is_image": True,
            "is_pngtree": True
        }

    def _extract_facebook(self, url: str, cookie_file: str) -> Optional[Dict[str, Any]]:
        """Handles Facebook Stories, Photos, Profiles, and Share redirect links."""
        u_lower = url.lower()
        is_story = "/stories/" in u_lower
        is_photos = "/photos" in u_lower or "/photo.php" in u_lower

        if is_story:
            self.log(f"📖 [Facebook Stories] កំពុងស្កែន Story Facebook (Scanning FB Story)...")
        elif is_photos:
            self.log(f"🖼️ [Facebook Photos] កំពុងស្កែនរូបភាព Facebook (Scanning FB Photos)...")
        else:
            self.log(f"🌐 [Facebook Post] កំពុងដោះស្រាយ Link និងទិន្នន័យ Facebook...")

        # If share redirect link (e.g. /share/p/...)
        resolved_url = url
        if "/share/" in u_lower and CURL_CFFI_AVAILABLE:
            try:
                r = cffi_requests.get(url, impersonate="chrome124", allow_redirects=True, timeout=8)
                if r.url and "/share/" not in r.url:
                    resolved_url = r.url
                    self.log(f"🔗 [Facebook] Expanded Share Link: {resolved_url[:65]}...")
            except Exception:
                pass

        html = self._fetch_html(resolved_url, cookie_file)

        # Check for Video
        vids = re.findall(r'"playable_url_quality_hd":"([^"]+)"', html) or re.findall(r'"playable_url":"([^"]+)"', html)
        video_url = vids[0].replace(r"\/", "/") if vids else ""
        if not video_url:
            og_vids = re.findall(r'<meta[^>]*property=["\']og:video[^"\']*["\'][^>]*content=["\']([^"\']+)["\']', html)
            if og_vids:
                video_url = og_vids[0]

        # Check for Photos
        fbcdn_imgs = re.findall(r'https://scontent[^\s"\'<>]+\.(?:jpg|png|webp)[^\s"\'<>]*', html)
        best_img = fbcdn_imgs[0] if fbcdn_imgs else ""
        if not best_img:
            og_imgs = re.findall(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
            if og_imgs:
                best_img = og_imgs[0]

        is_video = bool(video_url)
        media_url = video_url if is_video else best_img

        if media_url:
            self.log(f"✅ [Facebook] រកឃើញ {'វីដេអូ HD' if is_video else 'រូបភាព HD'} ដោយជោគជ័យ!")
            ext = "mp4" if is_video else "jpg"
            return {
                "_type": "video" if is_video else "image",
                "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
                "title": f"🎬 Facebook {'Story Video' if is_story else 'Video'}" if is_video else f"🖼️ Facebook {'Story Photo' if is_story else 'Photo'}",
                "uploader": "Facebook",
                "thumbnail": best_img or video_url,
                "formats": [{
                    "format_id": "hd" if is_video else "original",
                    "ext": ext,
                    "resolution": "1080p" if is_video else "High-Res Photo",
                    "format": f"Facebook {'HD Video' if is_video else 'HD Image'}",
                    "url": media_url
                }],
                "url": media_url,
                "is_image": not is_video,
                "is_facebook": True
            }

        # If not extracted directly (due to Facebook Login Wall for Stories/Private Posts)
        self.log("🔒 [Facebook Notice] Facebook Stories, Private Posts & Photos ត្រូវបានការពារដោយ Login Wall របស់ Facebook!")
        self.log("💡 វិធីទាញយកងាយស្រួលបំផុត ១០០% ជោគជ័យ៖")
        self.log("   👉 សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ខាងលើ ដើម្បីបើកមើល Story ឬរូបភាពក្នុង Facebook!")
        self.log("   👉 ប្រព័ន្ធ Built-in Browser នឹងចាប់យកឯកសាររូបភាព (HD Image) និងវីដេអូ Story (.mp4) ស្វ័យប្រវត្តិភ្លាមៗ!")
        return None

    def _extract_instagram(self, url: str, cookie_file: str) -> Optional[Dict[str, Any]]:
        """Handles Instagram Reels, Posts, and Stories."""
        self.log(f"📸 [Instagram] កំពុងស្កែន Reels / Story / Post (Scanning Instagram)...")
        html = self._fetch_html(url, cookie_file)

        # Check for video
        vids = re.findall(r'"video_url":"([^"]+)"', html) or re.findall(r'<meta[^>]*property=["\']og:video["\'][^>]*content=["\']([^"\']+)["\']', html)
        video_url = vids[0].replace(r"\u0026", "&").replace(r"\/", "/") if vids else ""

        # Check for photo
        imgs = re.findall(r'"display_url":"([^"]+)"', html) or re.findall(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
        img_url = imgs[0].replace(r"\u0026", "&").replace(r"\/", "/") if imgs else ""

        is_video = bool(video_url)
        media_url = video_url if is_video else img_url

        if media_url:
            self.log(f"✅ [Instagram] រកឃើញ {'វីដេអូ Reel HD' if is_video else 'រូបភាព HD'} ដោយជោគជ័យ!")
            ext = "mp4" if is_video else "jpg"
            return {
                "_type": "video" if is_video else "image",
                "id": re.sub(r'[^a-zA-Z0-9_-]', '_', url),
                "title": f"🎬 Instagram {'Reel/Video' if is_video else 'Photo'}",
                "uploader": "Instagram",
                "thumbnail": img_url or video_url,
                "formats": [{
                    "format_id": "hd" if is_video else "original",
                    "ext": ext,
                    "resolution": "1080p" if is_video else "High-Res Photo",
                    "format": f"Instagram {'HD Video' if is_video else 'HD Photo'}",
                    "url": media_url
                }],
                "url": media_url,
                "is_image": not is_video,
                "is_instagram": True
            }

        self.log("🔒 [Instagram Notice] Instagram តម្រូវឱ្យមាន Login ដើម្បីមើល Reels/Stories!")
        self.log("💡 សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីបើកមើល នោះប្រព័ន្ធនឹងចាប់យក Stream (.mp4/Image) ស្វ័យប្រវត្តិ!")
        return None

