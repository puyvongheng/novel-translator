"""
Downloader Service - Decoupled Architecture Core
Provides unified video & drama downloading, metadata analysis, format resolution,
multi-threaded acceleration, and CENC decryption.
Allows easy plug-and-play across any UI (PyQt, Web, CLI, API, Mobile).
"""

import os
import ssl
import time
import shutil
import subprocess
import threading
import urllib.request
from typing import Optional, List, Dict, Any, Callable, Tuple

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from services.downloader.models import DownloadProgress, QualityOption, VideoMetadata
from services.downloader.helpers import (
    get_ffmpeg_binary_path,
    strip_ansi,
    normalize_video_url,
    sanitize_folder_name,
    get_custom_referer,
    format_duration_str,
    download_cover_image
)
from services.downloader.cenc_decryptor import unwrap_spade
from services.downloader.bypass import BypassEngine
from services.downloader.extractors import (
    HongguoExtractor,
    HainanYuyueExtractor,
    StardustExtractor,
    KissKHExtractor,
    BilibiliBangumiExtractor,
    DouyinExtractor,
    SabayflixExtractor,
    KHDiamondExtractor
)


class DownloaderService:
    """
    Unified Downloader Service providing:
    - Multi-platform metadata extraction (YouTube, TikTok, Facebook, Douyin, Bilibili, Hongguo, Hainan Yuyue, StardustTV, KissKH)
    - Multi-threaded accelerated downloads & chunked streaming
    - Automatic CENC AES-128 decryption
    - Subtitle extraction & format remuxing
    - UI-agnostic event callbacks
    """

    def __init__(
        self,
        on_progress: Optional[Callable[[DownloadProgress], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        ffmpeg_path: Optional[str] = None
    ):
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_finished = on_finished
        self.on_error = on_error
        self.ffmpeg_path = ffmpeg_path or get_ffmpeg_binary_path()
        self.cancel_requested = False

        # Initialize platform extractors
        self.hongguo_extractor = HongguoExtractor(log_callback=self.log)
        self.hainanyuyue_extractor = HainanYuyueExtractor(log_callback=self.log)
        self.stardust_extractor = StardustExtractor(log_callback=self.log)
        self.kisskh_extractor = KissKHExtractor(log_callback=self.log)
        self.bilibili_extractor = BilibiliBangumiExtractor(log_callback=self.log)
        self.douyin_extractor = DouyinExtractor(log_callback=self.log)
        self.sabayflix_extractor = SabayflixExtractor(log_callback=self.log)
        self.khdiamond_extractor = KHDiamondExtractor(log_callback=self.log)

    def log(self, message: str):
        if self.on_log:
            self.on_log(message)

    def cancel(self):
        """Signals ongoing downloads to safely stop."""
        self.cancel_requested = True

    def reset_cancel(self):
        """Resets the cancellation flag."""
        self.cancel_requested = False

    # -------------------------------------------------------------
    # 1. METADATA EXTRACTION & QUALITY RESOLUTION
    # -------------------------------------------------------------
    def extract_info(
        self,
        url: str,
        cookie_file: str = "",
        proxy: str = "",
        fake_vpn: bool = False,
        custom_resolver: Optional[Callable[[str], str]] = None
    ) -> Dict[str, Any]:
        """Extracts comprehensive metadata, playlist entries, and stream options."""
        clean_url = normalize_video_url(url)

        # Check platform extractors first
        if self.hongguo_extractor.can_handle(clean_url):
            info = self.hongguo_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if self.hainanyuyue_extractor.can_handle(clean_url):
            info = self.hainanyuyue_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if self.stardust_extractor.can_handle(clean_url):
            info = self.stardust_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if self.bilibili_extractor.can_handle(clean_url):
            info = self.bilibili_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if self.douyin_extractor.can_handle(clean_url):
            info = self.douyin_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if self.sabayflix_extractor.can_handle(clean_url):
            info = self.sabayflix_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if self.khdiamond_extractor.can_handle(clean_url):
            info = self.khdiamond_extractor.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        if "kisskh." in clean_url.lower():
            kiss_ext = KissKHExtractor(log_callback=self.log, silent_resolver=custom_resolver)
            info = kiss_ext.extract_series(clean_url, cookie_file=cookie_file)
            if info:
                return info

        # Fallback to standard yt-dlp extractor
        if not yt_dlp:
            raise RuntimeError("yt_dlp library is not installed or available.")

        opts: Dict[str, Any] = {
            "quiet": True,
            "skip_download": True,
            "nocheckcertificate": True,
            "extract_flat": False,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            }
        }

        ref = get_custom_referer(clean_url)
        if ref:
            opts["http_headers"]["Referer"] = ref

        if self.ffmpeg_path:
            opts["ffmpeg_location"] = self.ffmpeg_path
        if cookie_file and os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
        if proxy:
            opts["proxy"] = proxy

        if fake_vpn or not proxy:
            opts["geo_bypass"] = True
            opts["geo_bypass_country"] = "CN"
            opts["http_headers"]["X-Forwarded-For"] = "116.228.89.24"
            opts["http_headers"]["Client-IP"] = "116.228.89.24"
            opts["http_headers"]["X-Real-IP"] = "116.228.89.24"

        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(clean_url, download=False)

    def calculate_quality_options(self, info: Dict[str, Any]) -> Tuple[List[str], Dict[str, str], List[str]]:
        """
        Parses stream formats and returns:
        - List of user-friendly quality labels
        - Mapping from quality label to yt-dlp format selector
        - List of available subtitle languages
        """
        formats = info.get("formats", [])
        duration = float(info.get("duration", 0) or 0)

        res_map: Dict[int, Dict[str, Any]] = {}
        audio_only_formats: List[Dict[str, Any]] = []

        # Find best audio size
        audio_bytes = 0
        audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
        for af in sorted(audio_formats, key=lambda x: (x.get("filesize") or 0, x.get("tbr") or 0), reverse=True):
            audio_bytes = af.get("filesize") or af.get("filesize_approx") or 0
            if not audio_bytes and af.get("tbr") and duration > 0:
                audio_bytes = int(min(af["tbr"], 160) * 1000 * duration / 8)
            break
        if not audio_bytes and duration > 0:
            audio_bytes = int(128 * 1000 * duration / 8)

        std_buckets = [4320, 2160, 1440, 1080, 720, 480, 360, 240]
        res_labels = {
            4320: "8K Ultra HD", 2160: "4K UHD (2160p)", 1440: "2K QHD (1440p)",
            1080: "Full HD (1080p)", 720: "HD (720p)", 480: "SD (480p)",
            360: "Low (360p)", 240: "240p"
        }

        # Exact simulation via yt-dlp format selector
        used_exact = False
        if yt_dlp:
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl_sim:
                    for std_h in std_buckets:
                        fmt_spec = f"bestvideo[height<={std_h}]+bestaudio/best[height<={std_h}]"
                        selector = ydl_sim.build_format_selector(fmt_spec)
                        chosen = list(selector({"formats": formats}))
                        if not chosen:
                            continue
                        ch = chosen[0]
                        rf = ch.get("requested_formats")
                        if rf:
                            v_f, a_f = rf[0], rf[1]
                            actual_h = v_f.get("height") or std_h
                            if actual_h < std_h * 0.7 and std_h > 720:
                                continue
                            v_sz = v_f.get("filesize") or v_f.get("filesize_approx") or 0
                            a_sz = a_f.get("filesize") or a_f.get("filesize_approx") or audio_bytes
                            fps = v_f.get("fps") or 30
                            if not v_sz and duration > 0:
                                cap_kbps = {2160: 15000, 1440: 8000, 1080: 3000, 720: 1500, 480: 600, 360: 350, 240: 200}.get(std_h, 1000)
                                real_br = min(v_f.get("vbr") or v_f.get("tbr") or cap_kbps, cap_kbps * 1.5)
                                v_sz = int(real_br * 1000 * duration / 8)
                            res_map[std_h] = {
                                "video_size": v_sz,
                                "size": v_sz + a_sz,
                                "fps": fps,
                                "format_id": f"bestvideo[height<={std_h}]+bestaudio/best[height<={std_h}]",
                                "has_audio": False
                            }
                        else:
                            sz = ch.get("filesize") or ch.get("filesize_approx") or 0
                            res_map[std_h] = {
                                "video_size": sz,
                                "size": sz,
                                "fps": ch.get("fps") or 30,
                                "format_id": ch.get("format_id"),
                                "has_audio": True
                            }
                if res_map:
                    used_exact = True
            except Exception:
                pass

        if not used_exact:
            for f in formats:
                vcodec = f.get("vcodec", "none")
                acodec = f.get("acodec", "none")
                h = f.get("height")
                fmt_id = f.get("format_id", "")
                filesize = f.get("filesize") or f.get("filesize_approx")
                fps = f.get("fps")

                if vcodec != "none" and h:
                    if h not in res_map or (filesize and filesize > (res_map[h].get("video_size") or 0)):
                        res_map[h] = {
                            "video_size": filesize or 0,
                            "size": (filesize or 0) + (0 if acodec != "none" else audio_bytes),
                            "format_id": fmt_id,
                            "fps": fps,
                            "has_audio": acodec != "none"
                        }
                elif vcodec == "none" and acodec != "none":
                    audio_only_formats.append(f)

        combo_items: List[str] = []
        format_data: Dict[str, str] = {}

        # 1. Best Available (Auto Highest Quality)
        combo_items.append("🌟 Best Available (Auto Highest Quality)")
        format_data["🌟 Best Available (Auto Highest Quality)"] = "bestvideo+bestaudio/best"

        # 2. Discrete Video Resolutions
        for h in sorted(res_map.keys(), reverse=True):
            r_info = res_map[h]
            label_base = res_labels.get(h, f"{h}p")
            fps_str = f" {r_info['fps']}fps" if r_info.get("fps") and r_info["fps"] > 30 else ""

            v_sz = r_info.get("video_size", 0)
            tot_sz = r_info.get("size", 0)
            v_mb = v_sz / (1024 * 1024)
            tot_mb = tot_sz / (1024 * 1024)

            if v_mb > 0 and tot_mb > v_mb:
                v_str = f"{v_mb/1024:.2f} GB" if v_mb >= 1024 else f"{v_mb:.1f} MB"
                tot_str = f"{tot_mb/1024:.2f} GB" if tot_mb >= 1024 else f"{tot_mb:.1f} MB"
                size_str = f" (~ {v_str} Video / {tot_str} Full)"
            elif tot_mb > 0:
                tot_str = f"{tot_mb/1024:.2f} GB" if tot_mb >= 1024 else f"{tot_mb:.1f} MB"
                size_str = f" (~ {tot_str})"
            else:
                size_str = ""

            full_label = f"🎬 {label_base}{fps_str}{size_str}"
            combo_items.append(full_label)
            if r_info.get("has_audio"):
                format_data[full_label] = r_info["format_id"]
            else:
                format_data[full_label] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"

        # 3. Audio Only Options
        audio_size_mb = 0.0
        if audio_only_formats and audio_only_formats[-1].get("filesize"):
            audio_size_mb = audio_only_formats[-1]["filesize"] / (1024 * 1024)
        elif duration > 0:
            audio_size_mb = (320 * 1000 / 8 * duration) / (1024 * 1024)

        a_size_str = f" (~{audio_size_mb:.1f} MB)" if audio_size_mb > 0 else ""
        a_label = f"🎵 Audio Only (MP3 320k High Quality){a_size_str}"
        combo_items.append(a_label)
        format_data[a_label] = "bestaudio/best"

        # 4. Subtitles list
        subs = info.get("subtitles", {})
        auto_subs = info.get("automatic_captions", {})
        all_subs = sorted(list(set(list(subs.keys()) + list(auto_subs.keys()))))

        return combo_items, format_data, all_subs

    # -------------------------------------------------------------
    # 2. STREAM DOWNLOADER & RESILIENT ENGINE
    # -------------------------------------------------------------
    def download_direct_stream(
        self,
        stream_url: str,
        output_path: str,
        referer: str = "",
        part_idx: int = 1,
        total_parts: int = 1,
        sublabel: str = "",
        cancel_event: Optional[threading.Event] = None
    ) -> bool:
        """
        Downloads a direct HTTP/HTTPS stream with chunked progress updates,
        automatic resume on network drop (HTTP Range requests), and referer spoofing.
        """
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        anti_headers = BypassEngine.get_anti_leech_headers(stream_url)
        base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
        base_headers.update(anti_headers)
        if referer:
            base_headers["Referer"] = referer

        max_retries = 6
        downloaded = 0
        total_size = 0

        if os.path.exists(output_path):
            try:
                downloaded = os.path.getsize(output_path)
            except Exception:
                downloaded = 0

        for attempt in range(max_retries):
            if self.cancel_requested or (cancel_event and cancel_event.is_set()):
                self.log("🛑 Download cancelled.")
                return False

            try:
                headers = dict(base_headers)
                mode = "wb"
                if downloaded > 0:
                    headers["Range"] = f"bytes={downloaded}-"
                    mode = "ab"

                req = urllib.request.Request(stream_url, headers=headers)
                with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                    content_range = resp.headers.get("Content-Range")
                    content_length = int(resp.headers.get("Content-Length", 0))

                    if content_range and "/" in content_range:
                        try:
                            total_size = int(content_range.split("/")[-1])
                        except Exception:
                            total_size = downloaded + content_length
                    elif total_size == 0:
                        total_size = content_length

                    start_time = time.time()
                    initial_downloaded = downloaded

                    with open(output_path, mode) as f:
                        while True:
                            if self.cancel_requested or (cancel_event and cancel_event.is_set()):
                                return False
                            chunk = resp.read(131072)  # 128 KB
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0 and self.on_progress:
                                pct = min(100.0, float(downloaded * 100.0 / total_size))
                                elapsed = max(0.1, time.time() - start_time)
                                speed_mb = ((downloaded - initial_downloaded) / (1024 * 1024)) / elapsed
                                self.on_progress(DownloadProgress(
                                    status="downloading",
                                    percent=pct,
                                    speed_mb=speed_mb,
                                    downloaded_bytes=downloaded,
                                    total_bytes=total_size,
                                    part_idx=part_idx,
                                    total_parts=total_parts,
                                    sublabel=sublabel
                                ))

                if total_size == 0 or downloaded >= total_size:
                    return True

            except urllib.error.HTTPError as he:
                if self.cancel_requested or (cancel_event and cancel_event.is_set()):
                    return False
                if he.code in (404, 403, 401, 410):
                    self.log(f"❌ [Downloader Error] HTTP Error {he.code}: {he.reason}")
                    return False
                self.log(f"⚠️ [Network Resume] HTTP {he.code} ({he.reason}) - Retrying ({attempt+1}/{max_retries})...")
                time.sleep(1.5)
            except Exception as e:
                if self.cancel_requested or (cancel_event and cancel_event.is_set()):
                    return False
                if os.path.exists(output_path):
                    downloaded = os.path.getsize(output_path)
                self.log(f"⚠️ [Network Resume] Network glitch ({e}) - Retrying ({attempt+1}/{max_retries})...")
                time.sleep(1.5)

        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    # -------------------------------------------------------------
    # 3. SPECIALIZED DRAMA DOWNLOADERS
    # -------------------------------------------------------------
    def download_hongguo_episode(
        self,
        series_id: str,
        vid: str,
        output_path: str,
        cookie_file: str = "",
        referer: str = "",
        part_idx: int = 1,
        total_parts: int = 1,
        cancel_event: Optional[threading.Event] = None
    ) -> bool:
        """Downloads full 720p HD video and audio stream from Hongguo and merges them with FFmpeg CENC decryption."""
        pi, err_info = self.hongguo_extractor.fetch_play_info(series_id, vid, cookie_file=cookie_file, return_err=True)
        v_url = pi.get("main_url")
        a_url = pi.get("audio", {}).get("main_url")
        spade_token = pi.get("player_access_key") or pi.get("audio", {}).get("player_access_key")
        dec_key = unwrap_spade(spade_token)

        if v_url and a_url:
            dur_val = pi.get('duration', 0)
            self.log(f"🎬 [Hongguo] Downloading 720p HD Episode ({dur_val:.0f}s)...")
            temp_v = output_path + ".vtemp.mp4"
            temp_a = output_path + ".atemp.m4a"
            try:
                # 1. Download Video Stream
                ok_v = self.download_direct_stream(v_url, temp_v, referer="https://hongguoduanju.com/", part_idx=part_idx, total_parts=total_parts, sublabel="Video 720p", cancel_event=cancel_event)
                if not ok_v or self.cancel_requested:
                    return False

                # 2. Download Audio Stream
                ok_a = self.download_direct_stream(a_url, temp_a, referer="https://hongguoduanju.com/", part_idx=part_idx, total_parts=total_parts, sublabel="Audio Track", cancel_event=cancel_event)
                if not ok_a or self.cancel_requested:
                    return False

                # 3. Merge & Decrypt with FFmpeg
                ff_bin = self.ffmpeg_path or "ffmpeg"
                merge_cmd = [ff_bin, "-y"]
                if dec_key:
                    self.log(f"🔑 [Hongguo DRM] Decrypting AES-128 CENC Key: {dec_key[:8]}...")
                    merge_cmd.extend(["-decryption_key", dec_key])
                merge_cmd.extend(["-i", temp_v])
                if dec_key:
                    merge_cmd.extend(["-decryption_key", dec_key])
                merge_cmd.extend([
                    "-i", temp_a,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    output_path
                ])

                res = subprocess.run(merge_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if res.returncode != 0:
                    # Fallback without decrypt key
                    res2 = subprocess.run([ff_bin, "-y", "-i", temp_v, "-i", temp_a, "-c:v", "copy", "-c:a", "copy", output_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    if res2.returncode != 0:
                        shutil.copyfile(temp_v, output_path)
                return True
            finally:
                for tmp in [temp_v, temp_a]:
                    if os.path.exists(tmp):
                        try: os.remove(tmp)
                        except Exception: pass
        else:
            if "protected_playback_unavailable" in str(err_info) or "403" in str(err_info):
                self.log(f"🔒 [Hongguo Locked] Episode {vid} is locked or requires login on Hongguo!")
                return False
            # Fallback to public stream
            fallback_url = f"https://hongguoduanju.com/video/public/{vid}/360p.mp4"
            return self.download_direct_stream(fallback_url, output_path, referer=referer, part_idx=part_idx, total_parts=total_parts, sublabel="Preview", cancel_event=cancel_event)

    # -------------------------------------------------------------
    # 4. MAIN ORCHESTRATED DOWNLOAD PIPELINE
    # -------------------------------------------------------------
    def download(
        self,
        url: str,
        output_dir: str,
        quality_format: str = "bestvideo+bestaudio/best",
        format_type: str = "Video (MP4)",
        download_cover: bool = True,
        download_subs: bool = False,
        sub_lang: str = "All Available",
        playlist_mode: str = "all",     # 'all', 'single', 'selected'
        selected_indices: Optional[List[int]] = None,
        cached_info: Optional[Dict[str, Any]] = None,
        cookie_file: str = "",
        proxy: str = "",
        fake_vpn: bool = False,
        num_threads: int = 8,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end download workflow:
        - Resolves target format containers (MP4, MKV, WebM, MP3, M4A, WAV, SRT)
        - Dispatches specialized extractors (Hongguo, Hainan Yuyue, StardustTV, KissKH)
        - Organizes clean folder per movie/series
        - Returns execution summary
        """
        self.reset_cancel()
        clean_url = normalize_video_url(url)

        # 1. Fetch info if not cached
        info = cached_info
        if not info:
            info = self.extract_info(clean_url, cookie_file=cookie_file, proxy=proxy, fake_vpn=fake_vpn)

        raw_title = info.get("title", "downloaded_movie")
        folder_name = sanitize_folder_name(raw_title)
        movie_folder = os.path.join(output_dir, folder_name)
        os.makedirs(movie_folder, exist_ok=True)

        is_subtitles_only = "Subtitles Only" in format_type
        is_cover_only = "Cover" in format_type or "Poster" in format_type
        is_audio = ("Audio" in format_type or "MP3" in format_type or "WAV" in format_type or "M4A" in format_type) and not is_subtitles_only and not is_cover_only

        # Save Cover / Poster image if requested
        saved_cover = None
        cover_url = info.get("thumbnail") or info.get("cover_url") or info.get("poster")
        if (download_cover or is_cover_only) and cover_url:
            self.log(f"🖼️ [Cover] Downloading High-Res Cover/Poster to: {folder_name}...")
            c_headers = BypassEngine.get_anti_leech_headers(cover_url)
            saved_cover = download_cover_image(cover_url, movie_folder, base_filename="cover", headers=c_headers)
            if saved_cover:
                self.log(f"✅ [Cover] Saved cover image: {os.path.basename(saved_cover)}")
            if is_cover_only:
                self.log(f"🎉 [Cover Only] Successfully finished cover download: {folder_name}")
                return {"status": "success", "folder": movie_folder, "cover": saved_cover}

        # 2. Check Hongguo Short Drama
        if info.get("is_hongguo"):
            entries = info.get("entries", [])
            targets = self._filter_playlist_targets(entries, playlist_mode, selected_indices)
            total_t = len(targets)
            if total_t == 0:
                raise ValueError("No episodes selected to download.")

            self.log(f"🎬 [Hongguo] Downloading {total_t} episodes to: {movie_folder}")
            for idx, ep in enumerate(targets, 1):
                if self.cancel_requested or (cancel_event and cancel_event.is_set()):
                    break
                ep_title = ep.get("title", f"Episode {idx}")
                ep_clean = sanitize_folder_name(ep_title)
                out_file = os.path.join(movie_folder, f"{idx:02d} - {ep_clean}.mp4")
                ep_vid = ep.get("id")
                ep_sid = ep.get("series_id") or info.get("id")

                self.download_hongguo_episode(ep_sid, ep_vid, out_file, cookie_file=cookie_file, referer=clean_url, part_idx=idx, total_parts=total_t, cancel_event=cancel_event)

            return {"status": "success", "folder": movie_folder, "count": total_t}

        # 3. Check Hainan Yuyue Short Drama
        if info.get("is_hainanyuyue"):
            entries = info.get("entries", [])
            targets = self._filter_playlist_targets(entries, playlist_mode, selected_indices)
            total_t = len(targets)
            if total_t == 0:
                raise ValueError("No episodes selected to download.")

            self.log(f"🎬 [Hainan Yuyue] Downloading {total_t} episodes to: {movie_folder}")
            for idx, ep in enumerate(targets, 1):
                if self.cancel_requested or (cancel_event and cancel_event.is_set()):
                    break
                ep_title = ep.get("title", f"Episode {idx}")
                ep_clean = sanitize_folder_name(ep_title)
                out_path = os.path.join(movie_folder, f"{idx:02d} - {ep_clean}.mp4")

                stream_u = ep.get("url")
                if not stream_u and ep.get("ch_id"):
                    stream_u = self.hainanyuyue_extractor.fetch_play_url(
                        ep.get("ch_id"),
                        ep.get("video_id", ""),
                        ep.get("enc_did", ""),
                        ep.get("uid", "")
                    )
                if stream_u:
                    self.download_direct_stream(stream_u, out_path, referer="", part_idx=idx, total_parts=total_t, sublabel=ep_clean, cancel_event=cancel_event)

            return {"status": "success", "folder": movie_folder, "count": total_t}

        # 4. Standard yt-dlp Download Pipeline
        if not yt_dlp:
            raise RuntimeError("yt_dlp library is required for this platform.")

        out_tmpl = os.path.join(movie_folder, f"{folder_name}.%(ext)s")

        def _yt_progress_hook(d: Dict[str, Any]):
            if self.on_progress and d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                down = d.get("downloaded_bytes", 0)
                speed = d.get("speed", 0) or 0
                pct = float(down * 100.0 / total) if total > 0 else 0.0
                self.on_progress(DownloadProgress(
                    status="downloading",
                    percent=pct,
                    speed_mb=speed / (1024 * 1024),
                    downloaded_bytes=down,
                    total_bytes=total,
                    title=raw_title
                ))

        opts: Dict[str, Any] = {
            "format": quality_format,
            "outtmpl": out_tmpl,
            "quiet": True,
            "no_warnings": True,
            "nopart": True,
            "overwrites": True,
            "continuedl": False,
            "nocheckcertificate": True,
            "concurrent_fragment_downloads": max(1, min(4, num_threads)),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            },
            "progress_hooks": [_yt_progress_hook]
        }

        # Apply Anti-Leech and GeoBypass headers
        anti_headers = BypassEngine.get_anti_leech_headers(clean_url)
        opts["http_headers"].update(anti_headers)
        if fake_vpn:
            geo_headers = BypassEngine.get_geo_bypass_headers("CN")
            opts["http_headers"].update(geo_headers)

        ref = get_custom_referer(clean_url)
        if ref:
            opts["http_headers"]["Referer"] = ref
        if self.ffmpeg_path:
            opts["ffmpeg_location"] = self.ffmpeg_path
        if cookie_file and os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
        if proxy:
            opts["proxy"] = proxy
        if fake_vpn or not proxy:
            opts["geo_bypass"] = True
            opts["geo_bypass_country"] = "CN"
            opts["http_headers"]["X-Forwarded-For"] = "116.228.89.24"
            opts["http_headers"]["Client-IP"] = "116.228.89.24"
            opts["http_headers"]["X-Real-IP"] = "116.228.89.24"

        # Container Format Selection
        if is_subtitles_only:
            opts["skip_download"] = True
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitlesformat"] = "srt/best"
        elif is_audio:
            opts["format"] = "bestaudio/best"
            if "WAV" in format_type:
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}]
            elif "M4A" in format_type:
                opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}]
            else:
                opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "320"}]
        else:
            if "MKV" in format_type:
                opts["merge_output_format"] = "mkv"
            elif "WebM" in format_type:
                opts["merge_output_format"] = "webm"
            else:
                opts["merge_output_format"] = "mp4"

            if download_cover:
                opts["writethumbnail"] = True
                opts.setdefault("postprocessors", [])
                opts["postprocessors"].append({
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                    "when": "before_dl"
                })
                if "mp4" in format_type.lower() or "mkv" in format_type.lower():
                    opts["postprocessors"].append({
                        "key": "EmbedThumbnail",
                        "already_have_thumbnail": False
                    })

        # Subtitle Handling
        if (download_subs or is_subtitles_only) and "No Subtitles" not in sub_lang:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitlesformat"] = "srt/best"
            opts["ignoreerrors"] = True
            opts.setdefault("postprocessors", [])
            opts["postprocessors"].append({
                "key": "FFmpegSubtitlesConvertor",
                "format": "srt",
                "when": "before_dl"
            })

            available_subs = list(info.get("subtitles", {}).keys()) + list(info.get("automatic_captions", {}).keys())
            if "zh-Hans" in sub_lang or "Chinese (zh" in sub_lang:
                opts["subtitleslangs"] = ["zh-Hans", "zh", "zh-CN"]
            elif "zh-Hant" in sub_lang:
                opts["subtitleslangs"] = ["zh-Hant", "zh-TW"]
            elif "English" in sub_lang or "en" in sub_lang:
                opts["subtitleslangs"] = ["en", "en-US", "en-orig"]
            elif "All" in sub_lang:
                opts["subtitleslangs"] = ["zh-Hans", "zh", "en", "zh-Hant"]
            else:
                # Smart Auto: ONLY 1 or 2 essential languages (Chinese + English) - avoid 80+ files
                chosen = []
                for pref in ["zh-Hans", "zh", "zh-CN", "zh-Hant", "zh-TW"]:
                    if pref in available_subs:
                        chosen.append(pref)
                        break
                for pref in ["en", "en-US", "en-orig", "en-GB"]:
                    if pref in available_subs:
                        chosen.append(pref)
                        break
                if not chosen and available_subs:
                    chosen.append(available_subs[0])
                opts["subtitleslangs"] = chosen if chosen else ["zh", "en"]

        # Playlist vs Single handling
        is_pl = info.get("_type") == "playlist" or bool(info.get("entries"))
        target_dl_url = clean_url

        if is_pl:
            if playlist_mode == "single":
                idx = (selected_indices[0] if selected_indices else 0)
                entries = info.get("entries", [])
                if 0 <= idx < len(entries):
                    target_dl_url = entries[idx].get("url") or clean_url
                    opts["noplaylist"] = True
                    single_title = sanitize_folder_name(entries[idx].get("title") or "video")
                    opts["outtmpl"] = os.path.join(movie_folder, f"{single_title}.%(ext)s")
            elif playlist_mode == "selected" and selected_indices:
                opts["noplaylist"] = False
                opts["playlist_items"] = ",".join(str(i + 1) for i in selected_indices)
                opts["outtmpl"] = os.path.join(movie_folder, "%(playlist_index)02d - %(title)s.%(ext)s")
            else:
                opts["noplaylist"] = False
                opts["outtmpl"] = os.path.join(movie_folder, "%(playlist_index)02d - %(title)s.%(ext)s")
        else:
            opts["noplaylist"] = True

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([target_dl_url])

        if self.on_finished:
            self.on_finished({"status": "success", "folder": movie_folder})

        return {"status": "success", "folder": movie_folder}

    @staticmethod
    def _filter_playlist_targets(entries: List[Dict[str, Any]], mode: str, selected_indices: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """Filters playlist entries based on single/selected/all criteria."""
        if not entries:
            return []
        if mode == "single":
            idx = selected_indices[0] if (selected_indices and 0 <= selected_indices[0] < len(entries)) else 0
            return [entries[idx]]
        elif mode == "selected" and selected_indices:
            return [entries[i] for i in selected_indices if 0 <= i < len(entries)]
        return list(entries)

