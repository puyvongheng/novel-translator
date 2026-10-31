"""
Shared Utilities and Helper Functions for Downloader Service
"""

import os
import re
import shutil
import urllib.request
from typing import Optional


def get_ffmpeg_binary_path() -> Optional[str]:
    """Finds or detects static FFmpeg binary (imageio-ffmpeg, system PATH, or local bin)."""
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.isfile(p):
            return os.path.abspath(p)
    except Exception:
        pass

    w = shutil.which("ffmpeg")
    if w:
        return os.path.abspath(w)

    for cand in [
        os.path.abspath("ffmpeg.exe"),
        os.path.abspath("bin/ffmpeg.exe"),
        os.path.abspath("ffmpeg/bin/ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"
    ]:
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def strip_ansi(text: str) -> str:
    """Removes ANSI color and formatting codes from text or error messages."""
    if not text:
        return ""
    return re.sub(r'(?:\x1b\[|\033\[|\[)[0-9;]*[a-zA-Z]', '', text).strip()


def normalize_video_url(raw_input: str) -> str:
    """
    Cleans, extracts and normalizes video URLs from messy user input or share text:
    - Extracts HTTP/HTTPS URL from messy share text (e.g. Douyin / TikTok share descriptions)
    - Normalizes Douyin modal_id URLs:
      https://www.douyin.com/jingxuan?modal_id=7693807499467640114 -> https://www.douyin.com/video/7693807499467640114
    - Normalizes TikTok modal_id URLs
    - Normalizes Bilibili, Sabayflix, KH Diamond, Hongguo, StardustTV, Mango TV, KissKH, YouTube
    """
    if not raw_input:
        return ""
    
    text = str(raw_input).strip()
    url_match = re.search(r'https?://[^\s<>"\']+', text)
    if url_match:
        url = url_match.group(0)
    else:
        url = text

    url = url.rstrip('),;。！？!?,，')

    # Bilibili URL normalization (strips /zh-Hans/, /zh-Hant/, /en/, b23.tv, query parameters)
    if "bilibili.com" in url or "b23.tv" in url:
        url = re.sub(r'bilibili\.com/(?:en|zh-Hans|zh-Hant)/', 'bilibili.com/', url)
        bm = re.search(r'bangumi/play/(ep\d+|ss\d+)', url)
        if bm:
            return f"https://www.bilibili.com/bangumi/play/{bm.group(1)}"
        ep_m = re.search(r'/(ep\d+|ss\d+)', url)
        if ep_m:
            return f"https://www.bilibili.com/bangumi/play/{ep_m.group(1)}"
        m = re.search(r'video/(BV[a-zA-Z0-9]+|av\d+)', url)
        if m:
            return f"https://www.bilibili.com/video/{m.group(1)}"
        b23_bv = re.search(r'b23\.tv/(BV[a-zA-Z0-9]+|av\d+)', url)
        if b23_bv:
            return f"https://www.bilibili.com/video/{b23_bv.group(1)}"

    # NovelQuickApp / Hongguo short links
    if "novelquickapp.com" in url:
        m_sid = re.search(r'video_series_id=(\d+)', url)
        if m_sid:
            return f"https://hongguoduanju.com/player/{m_sid.group(1)}"
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            })
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
            resp = opener.open(req, timeout=8)
            final_u = resp.geturl()
            m2 = re.search(r'video_series_id=(\d+)', final_u)
            if m2:
                return f"https://hongguoduanju.com/player/{m2.group(1)}"
        except Exception:
            pass

    # Sabayflix URL normalization
    if "sabayflix.net" in url:
        m = re.search(r'sabayflix\.net/movie/([a-zA-Z0-9_-]+)', url)
        if m:
            return f"https://www.sabayflix.net/movie/{m.group(1)}"

    # KH Diamond URL normalization
    if "khdiamond.net" in url:
        m = re.search(r'khdiamond\.net/movies/([a-zA-Z0-9_-]+)', url)
        if m:
            return f"https://khdiamond.net/movies/{m.group(1)}/"

    # Hongguo Short Drama URL normalization
    if "hongguoduanju.com" in url:
        m = re.search(r'hongguoduanju\.com/(?:player|detail)[^/]*?/(\d+(?:/\d+)?)', url)
        if m:
            return f"https://hongguoduanju.com/player/{m.group(1)}"
        m_s = re.search(r'series_id=(\d+)', url)
        if m_s:
            return f"https://hongguoduanju.com/player/{m_s.group(1)}"

    # StardustTV URL normalization
    if "stardusttv.net" in url:
        m = re.search(r'stardusttv\.net/episodes/([a-zA-Z0-9_-]+)', url)
        if m:
            return f"https://www.stardusttv.net/episodes/{m.group(1)}"

    # Mango TV URL normalization
    if "mgtv.com" in url:
        m = re.search(r'mgtv\.com/([bv]/[a-zA-Z0-9_/]+\.html)', url)
        if m:
            return f"https://www.mgtv.com/{m.group(1)}"

    # KissKH URL normalization
    if "kisskh." in url:
        m = re.search(r'(kisskh\.[a-z]+/Drama/[^?]+(?:\?id=\d+&ep=\d+)?)', url)
        if m:
            return f"https://{m.group(1)}"

    # YouTube URL normalization
    if "youtube.com/playlist" in url:
        m = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
        if m:
            return f"https://www.youtube.com/playlist?list={m.group(1)}"
        return url
    elif "youtube.com/watch" in url:
        v_m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
        list_m = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', url)
        if list_m and list_m.group(1).startswith("RD"):
            if v_m:
                return f"https://www.youtube.com/watch?v={v_m.group(1)}"
        if v_m and list_m:
            return f"https://www.youtube.com/watch?v={v_m.group(1)}&list={list_m.group(1)}"
        if v_m:
            return f"https://www.youtube.com/watch?v={v_m.group(1)}"
    elif "youtu.be/" in url:
        m = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    elif "youtube.com/shorts/" in url:
        m = re.search(r'shorts/([a-zA-Z0-9_-]+)', url)
        if m:
            return f"https://www.youtube.com/shorts/{m.group(1)}"

    # Douyin URL normalization
    if "douyin.com" in url:
        m = re.search(r'[?&]modal_id=(\d+)', url)
        if m:
            return f"https://www.douyin.com/video/{m.group(1)}"
        m2 = re.search(r'modal_id[=/](\d+)', url)
        if m2:
            return f"https://www.douyin.com/video/{m2.group(1)}"

    # TikTok URL normalization
    if "tiktok.com" in url:
        m = re.search(r'[?&]modal_id=(\d+)', url)
        if m:
            return f"https://www.tiktok.com/video/{m.group(1)}"

    return url


def sanitize_folder_name(name: str) -> str:
    """Sanitizes movie/series titles into safe folder names across Windows/Linux/Mac."""
    if not name:
        return "downloaded_movie"
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    clean = re.sub(r'[\r\n\t]+', " ", clean).strip(". ")
    return clean[:70] if clean else "downloaded_movie"


def get_custom_referer(url: str) -> str:
    """Returns appropriate HTTP Referer header to bypass anti-hotlinking protections."""
    if not url:
        return ""
    u = url.lower()
    if "bilibili" in u or "bilivideo" in u:
        return "https://www.bilibili.com/"
    if "hongguoduanju" in u:
        return "https://hongguoduanju.com/"
    if "stardusttv" in u or "stardust-tv" in u:
        return "https://www.stardusttv.net/"
    if "novelquickapp" in u or "qznovelvod" in u:
        return "https://novelquickapp.com/"
    if "sabayflix" in u or "sf-api" in u:
        return "https://www.sabayflix.net/"
    if "khdiamond" in u or "dooplayer" in u:
        return "https://khdiamond.net/"
    if "iqiyi" in u or "qiyi" in u:
        return "https://www.iqiyi.com/"
    if "qq.com" in u or "v.qq.com" in u:
        return "https://v.qq.com/"
    if "youku" in u:
        return "https://www.youku.com/"
    if "mgtv" in u or "hunantv" in u:
        return "https://www.mgtv.com/"
    if "ixigua" in u:
        return "https://www.ixigua.com/"
    if "kuaishou" in u or "yximgs" in u:
        return "https://www.kuaishou.com/"
    if "kolabkhmer" in u:
        return "https://kolabkhmer.com/"
    if "phumikhmer" in u:
        return "https://phumikhmer.me/"
    if "merlmovie" in u:
        return "https://merlmovie.com/"
    if "kisskh." in u:
        return "https://kisskh.do/"
    if "dramabox" in u:
        return "https://www.dramaboxdb.com/"
    if "pngtree" in u:
        return "https://pngtree.com/"
    if "pinterest" in u or "pinimg" in u:
        return "https://www.pinterest.com/"
    if "facebook" in u or "fbcdn" in u:
        return "https://www.facebook.com/"
    if "instagram" in u or "cdninstagram" in u:
        return "https://www.instagram.com/"
    if "hainanyuyue" in u:
        return ""
    return ""


def format_duration_str(seconds: float) -> str:
    """Formats float duration into mm:ss or hh:mm:ss string."""
    try:
        s = int(float(seconds or 0))
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{sec:02d}"
        return f"{m:02d}:{sec:02d}"
    except Exception:
        return "--:--"


def download_cover_image(
    cover_url: str,
    output_folder: str,
    base_filename: str = "cover",
    headers: Optional[dict] = None
) -> Optional[str]:
    """
    Downloads high-resolution cover/poster image and saves it in the destination folder
    as both cover.jpg and poster.jpg for media players (VLC, Plex, Windows).
    """
    if not cover_url or not output_folder:
        return None
    try:
        os.makedirs(output_folder, exist_ok=True)
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
        }
        if headers:
            req_headers.update(headers)

        req = urllib.request.Request(cover_url, headers=req_headers)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = resp.read()
            if not data or len(data) < 100:
                return None

            ext = ".jpg"
            if data.startswith(b"\x89PNG"):
                ext = ".png"
            elif data.startswith(b"RIFF") and b"WEBP" in data[:12]:
                ext = ".webp"

            out_path = os.path.join(output_folder, f"{base_filename}{ext}")
            with open(out_path, "wb") as f:
                f.write(data)

            # Also create standard cover.jpg and poster.jpg if not conflicting
            cov_path = os.path.join(output_folder, "cover.jpg")
            pos_path = os.path.join(output_folder, "poster.jpg")
            if out_path != cov_path and not os.path.exists(cov_path):
                try:
                    shutil.copyfile(out_path, cov_path)
                except Exception:
                    pass
            if out_path != pos_path and not os.path.exists(pos_path):
                try:
                    shutil.copyfile(out_path, pos_path)
                except Exception:
                    pass

            return out_path
    except Exception as e:
        print(f"Warning: Failed to download cover image: {e}")
        return None

