import os
import io
import re
import time
import shutil
import threading
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from utils import format_timestamp


def _get_aria2c_path():
    """Detect aria2c binary location for multi-connection download acceleration"""
    found = shutil.which("aria2c")
    if found and os.path.exists(found):
        return found
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_link = os.path.join(local_app_data, "Microsoft", "WinGet", "Links", "aria2c.EXE")
        if os.path.exists(winget_link):
            return winget_link
        winget_link_lower = os.path.join(local_app_data, "Microsoft", "WinGet", "Links", "aria2c.exe")
        if os.path.exists(winget_link_lower):
            return winget_link_lower
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
      https://www.douyin.com/discover?modal_id=... -> https://www.douyin.com/video/...
      https://www.douyin.com/user/...?modal_id=... -> https://www.douyin.com/video/...
      https://www.douyin.com/search/...?modal_id=... -> https://www.douyin.com/video/...
    - Normalizes TikTok modal_id URLs
    """
    if not raw_input:
        return ""
    
    text = raw_input.strip()
    
    # 1. Extract URL if mixed with share text or comments
    url_match = re.search(r'https?://[^\s<>"\']+', text)
    if url_match:
        url = url_match.group(0)
    else:
        url = text

    # Strip trailing punctuation
    url = url.rstrip('),;。！？!?,，')

    # 2. Douyin URL normalization
    if "douyin.com" in url:
        m = re.search(r'[?&]modal_id=(\d+)', url)
        if m:
            return f"https://www.douyin.com/video/{m.group(1)}"
        m2 = re.search(r'modal_id[=/](\d+)', url)
        if m2:
            return f"https://www.douyin.com/video/{m2.group(1)}"

    # 3. TikTok URL normalization
    if "tiktok.com" in url:
        m = re.search(r'[?&]modal_id=(\d+)', url)
        if m:
            return f"https://www.tiktok.com/video/{m.group(1)}"

    return url


class VideoDownloaderView(ctk.CTkScrollableFrame):
    """
    Ultra-Modern Video Downloader Studio:
    - Paste any video URL (YouTube, TikTok, Facebook, Douyin, Bilibili, Twitter/X, Instagram, etc.)
    - Instant preview with high-res thumbnail, title, channel, duration, and available CC
    - Multi-resolution selector (Best 4K/1080p, 720p, 480p, MP3 Audio)
    - Auto-download CC/Subtitles (.srt) for immediate translation
    - Real-time download progress, speed, ETA, and size tracking
    - 1-Click 'Download & Open in Studio' to directly load video into Cinema Monitor & Subtitle editor
    """
    def __init__(self, parent, on_open_video_in_studio=None, log_callback=None):
        super().__init__(parent, fg_color="#0e1014", corner_radius=0)
        self.on_open_video_in_studio = on_open_video_in_studio
        self.log_callback = log_callback

        self.current_info = None
        self.thumbnail_photo = None
        self.is_downloading = False
        self.cancel_download = False
        self.downloaded_items = []
        self._last_log_step = -1

        # Default downloads folder in workspace
        self.download_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))
        os.makedirs(self.download_dir, exist_ok=True)

        self._build_ui()
        self.log("📥 Video Downloader Engine initialized. Ready for video links.")

    def log(self, text: str):
        """Outputs a timestamped message to the local Live Logs Console and dispatches to log_callback"""
        t_str = time.strftime("%H:%M:%S")
        msg = f"[{t_str}] {text}"
        if hasattr(self, "txt_logs"):
            def _append():
                try:
                    self.txt_logs.configure(state="normal")
                    self.txt_logs.insert("end", f"{msg}\n")
                    self.txt_logs.see("end")
                    self.txt_logs.configure(state="disabled")
                except Exception:
                    pass
            self.after(0, _append)
        if self.log_callback:
            try:
                self.log_callback(text)
            except Exception:
                pass
        else:
            print(f"[VideoDownloader] {msg}")

    def _clear_logs(self):
        if hasattr(self, "txt_logs"):
            self.txt_logs.configure(state="normal")
            self.txt_logs.delete("1.0", "end")
            self.txt_logs.configure(state="disabled")
            self.log("Download logs console cleared.")

    def _copy_logs(self):
        if hasattr(self, "txt_logs"):
            content = self.txt_logs.get("1.0", "end").strip()
            if content:
                try:
                    self.clipboard_clear()
                    self.clipboard_append(content)
                    messagebox.showinfo("Copied", "Logs copied to clipboard!")
                except Exception:
                    pass

    def _build_ui(self):
        # 1. Header Banner
        banner = ctk.CTkFrame(self, fg_color="#141822", corner_radius=6, border_width=1, border_color="#222b3d")
        banner.pack(fill="x", padx=16, pady=(12, 10))

        hdr_row = ctk.CTkFrame(banner, fg_color="transparent")
        hdr_row.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            hdr_row,
            text="📥 VIDEO & MOVIE DOWNLOADER",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_row,
            text="● YouTube, TikTok, Facebook, Douyin, Bilibili, X/Twitter, 1000+ sites",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(side="left", padx=12)

        ctk.CTkLabel(
            hdr_row,
            text="⚡ TURBO MULTI-THREAD ENGINE",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color="#10b981"
        ).pack(side="right", padx=10)

        # 2. URL Input Card
        url_card = ctk.CTkFrame(self, fg_color="#181c26", corner_radius=6, border_width=1, border_color="#2a3346")
        url_card.pack(fill="x", padx=16, pady=6)

        lbl_input = ctk.CTkLabel(
            url_card,
            text="🔗 Video Link / URL (YouTube, TikTok, Facebook, etc.):",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#e2e8f0"
        )
        lbl_input.pack(anchor="w", padx=14, pady=(10, 4))

        row_input = ctk.CTkFrame(url_card, fg_color="transparent")
        row_input.pack(fill="x", padx=14, pady=(0, 10))

        self.entry_url = ctk.CTkEntry(
            row_input,
            placeholder_text="Paste video URL here... (e.g. https://www.youtube.com/watch?v=... or TikTok link)",
            height=34,
            corner_radius=4,
            font=ctk.CTkFont(size=12)
        )
        self.entry_url.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry_url.bind("<Return>", lambda e: self.start_preview_info())

        btn_paste = ctk.CTkButton(
            row_input,
            text="📋 Paste",
            command=self._paste_clipboard,
            width=70,
            height=34,
            corner_radius=4,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        btn_paste.pack(side="left", padx=3)

        btn_clear = ctk.CTkButton(
            row_input,
            text="❌",
            command=self._clear_url,
            width=36,
            height=34,
            corner_radius=4,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=11)
        )
        btn_clear.pack(side="left", padx=3)

        self.btn_preview = ctk.CTkButton(
            row_input,
            text="👁️ Preview Info",
            command=self.start_preview_info,
            width=110,
            height=34,
            corner_radius=4,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_preview.pack(side="left", padx=(3, 0))

        # Status / Feedback label below URL bar
        self.lbl_feedback = ctk.CTkLabel(
            url_card,
            text="💡 Tip: Paste any video link and click 'Preview Info' or press Enter to inspect video details & CC.",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        )
        self.lbl_feedback.pack(anchor="w", padx=14, pady=(0, 8))

        # 3. Video Preview Box (Hidden until URL is analyzed)
        self.preview_card = ctk.CTkFrame(self, fg_color="#151922", corner_radius=6, border_width=1, border_color="#273248")
        self.preview_card.pack(fill="x", padx=16, pady=8)

        self._build_preview_card_contents()

        # 4. Download Settings & Options Card
        opts_card = ctk.CTkFrame(self, fg_color="#181c26", corner_radius=6, border_width=1, border_color="#2a3346")
        opts_card.pack(fill="x", padx=16, pady=8)

        ctk.CTkLabel(
            opts_card,
            text="⚙️ DOWNLOAD CONFIGURATION",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f59e0b"
        ).pack(anchor="w", padx=14, pady=(10, 4))

        row_cfg1 = ctk.CTkFrame(opts_card, fg_color="transparent")
        row_cfg1.pack(fill="x", padx=14, pady=4)

        ctk.CTkLabel(row_cfg1, text="Resolution / Quality:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left", padx=(0, 8))
        self.combo_quality = ctk.CTkComboBox(
            row_cfg1,
            values=[
                "Best Available (4K / 1080p)",
                "1080p Full HD",
                "720p HD",
                "480p SD",
                "360p Low",
                "🎵 MP3 Audio Only (Best Quality)"
            ],
            width=230,
            height=28,
            corner_radius=4,
            font=ctk.CTkFont(size=11)
        )
        self.combo_quality.set("Best Available (4K / 1080p)")
        self.combo_quality.pack(side="left")

        # Auto-download CC Checkbox
        self.check_download_subs = ctk.CTkCheckBox(
            row_cfg1,
            text="💬 Download Subtitles / CC (.srt companion)",
            font=ctk.CTkFont(size=11),
            text_color="#38bdf8",
            corner_radius=3
        )
        self.check_download_subs.select()
        self.check_download_subs.pack(side="left", padx=20)

        # Row 2: Turbo Multi-Thread & Speed Configuration
        row_cfg2 = ctk.CTkFrame(opts_card, fg_color="transparent")
        row_cfg2.pack(fill="x", padx=14, pady=(2, 6))

        self.check_turbo = ctk.CTkCheckBox(
            row_cfg2,
            text="⚡ Turbo Multi-Thread Acceleration (Ultra-Fast)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#10b981",
            corner_radius=3
        )
        self.check_turbo.select()
        self.check_turbo.pack(side="left")

        ctk.CTkLabel(row_cfg2, text="Speed / Threads:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left", padx=(16, 8))
        self.combo_threads = ctk.CTkComboBox(
            row_cfg2,
            values=[
                "16 Threads (Recommended - Max Speed)",
                "32 Threads (Extreme Turbo Gigabit)",
                "8 Threads (Standard Fast)",
                "4 Threads (Moderate)",
            ],
            width=255,
            height=28,
            corner_radius=4,
            font=ctk.CTkFont(size=11)
        )
        self.combo_threads.set("16 Threads (Recommended - Max Speed)")
        self.combo_threads.pack(side="left")

        aria2_found = _get_aria2c_path()
        badge_text = "🚀 Aria2c Multi-Connection Enabled" if aria2_found else "⚡ 16x Multi-Stream Active"
        ctk.CTkLabel(
            row_cfg2,
            text=badge_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left", padx=10)

        # Output Folder Row
        row_folder = ctk.CTkFrame(opts_card, fg_color="transparent")
        row_folder.pack(fill="x", padx=14, pady=(6, 12))

        ctk.CTkLabel(row_folder, text="Save Folder:", font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(side="left", padx=(0, 8))
        self.entry_folder = ctk.CTkEntry(row_folder, height=28, font=ctk.CTkFont(size=10), corner_radius=4)
        self.entry_folder.insert(0, self.download_dir)
        self.entry_folder.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_browse_dir = ctk.CTkButton(
            row_folder,
            text="📁 Browse...",
            width=85,
            height=28,
            corner_radius=4,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=10),
            command=self._browse_save_folder
        )
        btn_browse_dir.pack(side="left", padx=2)

        btn_open_dir = ctk.CTkButton(
            row_folder,
            text="📂 Open Folder",
            width=95,
            height=28,
            corner_radius=4,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=10),
            command=self._open_downloads_folder
        )
        btn_open_dir.pack(side="left")

        # Action Buttons Row
        row_actions = ctk.CTkFrame(opts_card, fg_color="transparent")
        row_actions.pack(fill="x", padx=14, pady=(0, 12))

        self.btn_download = ctk.CTkButton(
            row_actions,
            text="⬇️ Start Download",
            command=self.start_download_thread,
            width=150,
            height=36,
            corner_radius=4,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_download.pack(side="left", padx=(0, 8))

        self.btn_download_and_open = ctk.CTkButton(
            row_actions,
            text="⚡ Download & Open in Studio",
            command=lambda: self.start_download_thread(auto_open=True),
            width=210,
            height=36,
            corner_radius=4,
            fg_color="#9333ea",
            hover_color="#7e22ce",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.btn_download_and_open.pack(side="left", padx=(0, 8))

        self.btn_stop_download = ctk.CTkButton(
            row_actions,
            text="⏹️ Stop Download",
            command=self.stop_download,
            width=140,
            height=36,
            corner_radius=4,
            fg_color="#dc2626",
            hover_color="#b91c1c",
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled"
        )
        self.btn_stop_download.pack(side="left")

        # 5. Live Download Progress Bar & Speed Status
        self.prog_frame = ctk.CTkFrame(self, fg_color="#10131a", corner_radius=6, border_width=1, border_color="#20293a")
        self.prog_frame.pack(fill="x", padx=16, pady=8)

        self.lbl_prog_title = ctk.CTkLabel(
            self.prog_frame,
            text="📊 Download Status: Idle",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8"
        )
        self.lbl_prog_title.pack(anchor="w", padx=14, pady=(10, 2))

        self.prog_bar = ctk.CTkProgressBar(
            self.prog_frame,
            height=12,
            corner_radius=3,
            progress_color="#0284c7",
            fg_color="#1e293b"
        )
        self.prog_bar.set(0.0)
        self.prog_bar.pack(fill="x", padx=14, pady=4)

        self.lbl_prog_stats = ctk.CTkLabel(
            self.prog_frame,
            text="Speed: 0 KB/s | Downloaded: 0 MB / 0 MB | ETA: --:--",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#64748b"
        )
        self.lbl_prog_stats.pack(anchor="w", padx=14, pady=(0, 10))

        # 6. Live Download Logs & Console Card
        logs_card = ctk.CTkFrame(self, fg_color="#10131a", corner_radius=6, border_width=1, border_color="#20293a")
        logs_card.pack(fill="x", padx=16, pady=6)

        l_hdr = ctk.CTkFrame(logs_card, fg_color="transparent")
        l_hdr.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(
            l_hdr,
            text="📋 DOWNLOAD LOGS & CONSOLE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#10b981"
        ).pack(side="left")

        ctk.CTkLabel(
            l_hdr,
            text="● Live Terminal & Multi-Thread Stream",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(side="left", padx=10)

        btn_copy_logs = ctk.CTkButton(
            l_hdr,
            text="📋 Copy Logs",
            width=78,
            height=20,
            corner_radius=2,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=9),
            command=self._copy_logs
        )
        btn_copy_logs.pack(side="right", padx=(4, 0))

        btn_clear_logs = ctk.CTkButton(
            l_hdr,
            text="🗑️ Clear",
            width=58,
            height=20,
            corner_radius=2,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=9),
            command=self._clear_logs
        )
        btn_clear_logs.pack(side="right")

        self.txt_logs = ctk.CTkTextbox(
            logs_card,
            height=125,
            fg_color="#07080c",
            text_color="#cbd5e1",
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=4
        )
        self.txt_logs.pack(fill="x", padx=14, pady=(2, 10))
        self.txt_logs.configure(state="disabled")

        # 7. Downloaded Items History Card
        hist_card = ctk.CTkFrame(self, fg_color="#141822", corner_radius=6, border_width=1, border_color="#222b3d")
        hist_card.pack(fill="x", padx=16, pady=(6, 16))

        h_hdr = ctk.CTkFrame(hist_card, fg_color="transparent")
        h_hdr.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(
            h_hdr,
            text="📁 DOWNLOAD HISTORY (THIS SESSION)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left")

        self.lbl_hist_count = ctk.CTkLabel(h_hdr, text="0 files", font=ctk.CTkFont(size=10), text_color="#64748b")
        self.lbl_hist_count.pack(side="left", padx=8)

        self.box_history = ctk.CTkFrame(hist_card, fg_color="#0c0e14", corner_radius=4)
        self.box_history.pack(fill="x", padx=14, pady=(4, 12))

        self.lbl_no_hist = ctk.CTkLabel(
            self.box_history,
            text="No videos downloaded in this session yet. Downloaded videos will appear here with 1-click 'Open in Studio' button.",
            font=ctk.CTkFont(size=10),
            text_color="#475569"
        )
        self.lbl_no_hist.pack(padx=14, pady=12)

    def _build_preview_card_contents(self):
        """Constructs layout inside the preview card"""
        row_prev = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        row_prev.pack(fill="x", padx=14, pady=12)

        # Left Thumbnail box
        self.box_thumb = ctk.CTkFrame(row_prev, width=240, height=135, fg_color="#090a0f", corner_radius=4)
        self.box_thumb.pack(side="left", padx=(0, 14))
        self.box_thumb.pack_propagate(False)

        self.lbl_thumb = tk.Label(
            self.box_thumb,
            text="🎬\nPreview Thumbnail",
            font=("Segoe UI", 10),
            fg="#64748b",
            bg="#090a0f"
        )
        self.lbl_thumb.pack(fill="both", expand=True)

        # Right Metadata info
        meta_frame = ctk.CTkFrame(row_prev, fg_color="transparent")
        meta_frame.pack(side="left", fill="both", expand=True)

        self.lbl_prev_title = ctk.CTkLabel(
            meta_frame,
            text="[ No video loaded ] Paste URL above to preview",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#f8fafc",
            anchor="w",
            wraplength=550,
            justify="left"
        )
        self.lbl_prev_title.pack(anchor="w", pady=(0, 4))

        self.lbl_prev_uploader = ctk.CTkLabel(
            meta_frame,
            text="👤 Uploader: --",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
            anchor="w"
        )
        self.lbl_prev_uploader.pack(anchor="w", pady=1)

        self.lbl_prev_duration = ctk.CTkLabel(
            meta_frame,
            text="⏱️ Duration: --:--  |  👁️ Views: --",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
            anchor="w"
        )
        self.lbl_prev_duration.pack(anchor="w", pady=1)

        self.lbl_prev_cc = ctk.CTkLabel(
            meta_frame,
            text="💬 Subtitles / CC: --",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#34d399",
            anchor="w"
        )
        self.lbl_prev_cc.pack(anchor="w", pady=2)

    # ------------------ URL & CLIPBOARD ACTIONS ------------------
    def _paste_clipboard(self):
        try:
            cb = self.clipboard_get().strip()
            if cb:
                clean_url = normalize_video_url(cb)
                self.entry_url.delete(0, "end")
                self.entry_url.insert(0, clean_url)
                if clean_url != cb:
                    self.log(f"🔄 [Downloader] បានស្រង់ និងសម្រួល Link ស្វ័យប្រវត្ត: {clean_url}")
                self.start_preview_info()
        except Exception:
            pass

    def _clear_url(self):
        self.entry_url.delete(0, "end")
        self.lbl_feedback.configure(
            text="💡 Tip: Paste any video link and click 'Preview Info' or press Enter to inspect video details & CC.",
            text_color="#64748b"
        )

    def _browse_save_folder(self):
        chosen = filedialog.askdirectory(title="Select Download Directory", initialdir=self.download_dir)
        if chosen:
            self.download_dir = chosen
            self.entry_folder.delete(0, "end")
            self.entry_folder.insert(0, chosen)

    def _open_downloads_folder(self):
        d = self.entry_folder.get().strip() or self.download_dir
        if os.path.exists(d):
            try:
                os.startfile(d)
            except Exception:
                pass
        else:
            messagebox.showinfo("Folder", f"Directory: {d}")

    # ------------------ ASYNC METADATA PREVIEW ------------------
    def start_preview_info(self):
        raw_url = self.entry_url.get().strip()
        if not raw_url:
            self.lbl_feedback.configure(text="⚠️ Please paste a valid video URL first!", text_color="#f59e0b")
            return

        url = normalize_video_url(raw_url)
        if url != raw_url:
            self.entry_url.delete(0, "end")
            self.entry_url.insert(0, url)
            self.log(f"🔄 [Downloader] បានសម្រួល Link ស្វ័យប្រវត្ត: {url}")

        self.btn_preview.configure(state="disabled", text="⏳ Loading...")
        self.lbl_feedback.configure(text=f"🔍 Analyzing video metadata: {url[:55]}...", text_color="#38bdf8")
        self.log(f"🔍 [Downloader] កំពុងទាញយកព័ត៌មានវីដេអូ (Analyzing URL): {url}")

        def worker():
            try:
                if not yt_dlp:
                    raise Exception("yt-dlp is not installed in environment")

                ydl_opts = {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": False,
                    "nocheckcertificate": True,
                    "socket_timeout": 15,
                    "http_headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                    },
                    "extractor_args": {
                        "youtube": {
                            "player_client": ["android", "ios", "web"]
                        }
                    }
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                self.current_info = info
                self.after(0, lambda: self._update_preview_ui(info))

            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._show_preview_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _update_preview_ui(self, info: dict):
        self.btn_preview.configure(state="normal", text="👁️ Preview Info")
        title = info.get("title", "Untitled Video")
        uploader = info.get("uploader") or info.get("channel") or info.get("creator") or "Unknown Creator"
        dur = info.get("duration", 0)
        dur_str = format_timestamp(dur) if dur else "Live / Unknown"
        views = info.get("view_count")
        view_str = f"{views:,} views" if views else "Views: N/A"

        # Check subtitles
        subs = info.get("subtitles", {})
        auto_subs = info.get("automatic_captions", {})
        sub_langs = list(subs.keys()) + [f"{k} (auto)" for k in list(auto_subs.keys())[:5]]
        if sub_langs:
            cc_str = f"💬 Subtitles Available: {', '.join(sub_langs[:4])}"
            cc_color = "#34d399"
        else:
            cc_str = "💬 Subtitles: None found (Whisper Speech Recognition can auto-transcribe!)"
            cc_color = "#fbbf24"

        self.lbl_prev_title.configure(text=title)
        self.lbl_prev_uploader.configure(text=f"👤 Creator: {uploader}")
        self.lbl_prev_duration.configure(text=f"⏱️ Duration: {dur_str}  |  👁️ {view_str}")
        self.lbl_prev_cc.configure(text=cc_str, text_color=cc_color)
        self.lbl_feedback.configure(text="✅ Video analyzed successfully! Choose quality and click Download.", text_color="#10b981")
        self.log(f"✅ [Downloader] វិភាគជោគជ័យ: \"{title}\" | រយៈពេល: {dur_str} | អ្នកបង្កើត: {uploader}")
        if sub_langs:
            self.log(f"💬 [Downloader] រកឃើញ CC/Subtitles ស្រាប់: {', '.join(sub_langs[:5])}")

        # Load thumbnail in background
        thumb_url = info.get("thumbnail")
        if thumb_url:
            threading.Thread(target=self._load_thumbnail, args=(thumb_url,), daemon=True).start()

    def _load_thumbnail(self, url: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = resp.read()
            pil_img = Image.open(io.BytesIO(data))
            pil_img = pil_img.resize((240, 135), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil_img)

            def _show():
                self.thumbnail_photo = photo
                self.lbl_thumb.configure(image=photo, text="")
            self.after(0, _show)
        except Exception:
            pass

    def _show_preview_error(self, err: str):
        clean_err = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', str(err)).strip()
        self.btn_preview.configure(state="normal", text="👁️ Preview Info")
        short_err = clean_err.split("\n")[0][:80]
        self.lbl_feedback.configure(text=f"❌ Failed to extract video: {short_err}", text_color="#ef4444")
        self.log(f"❌ [Downloader] បរាជ័យក្នុងការវិភាគ URL: {short_err}")

    # ------------------ ASYNC VIDEO DOWNLOAD ------------------
    def start_download_thread(self, auto_open: bool = False):
        raw_url = self.entry_url.get().strip()
        if not raw_url:
            messagebox.showwarning("URL Missing", "Please paste a video URL to download!")
            return
        if self.is_downloading:
            messagebox.showinfo("In Progress", "A download is already in progress. Please wait.")
            return

        url = normalize_video_url(raw_url)
        if url != raw_url:
            self.entry_url.delete(0, "end")
            self.entry_url.insert(0, url)
            self.log(f"🔄 [Downloader] បានសម្រួល Link ស្វ័យប្រវត្ត: {url}")

        out_dir = self.entry_folder.get().strip() or self.download_dir
        os.makedirs(out_dir, exist_ok=True)
        quality = self.combo_quality.get()
        download_subs = bool(self.check_download_subs.get())

        # Read turbo configuration
        threads = 16
        if hasattr(self, "combo_threads"):
            th_val = self.combo_threads.get()
            m = re.search(r"(\d+)", th_val)
            if m:
                threads = int(m.group(1))

        turbo_enabled = bool(self.check_turbo.get()) if hasattr(self, "check_turbo") else True

        self._last_prog_time = time.time()
        self._last_prog_bytes = 0
        self._last_log_step = -1

        self.is_downloading = True
        self.cancel_download = False
        self.btn_download.configure(state="disabled")
        self.btn_download_and_open.configure(state="disabled")
        self.btn_stop_download.configure(state="normal")
        self.lbl_prog_title.configure(text=f"⚡ Initializing Turbo Download ({threads} Threads)...", text_color="#38bdf8")
        self.prog_bar.set(0.0)
        self.log(f"🚀 [Downloader] ចាប់ផ្ដើមទាញយកវីដេអូ | Quality: {quality} | Turbo: {threads} Threads | Folder: {out_dir}")

        def worker():
            try:
                # Format selection logic
                is_audio = "MP3" in quality or "Audio" in quality
                if is_audio:
                    ydl_format = "bestaudio/best"
                    postprocessors = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }]
                elif "1080p" in quality:
                    ydl_format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
                    postprocessors = []
                elif "720p" in quality:
                    ydl_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
                    postprocessors = []
                elif "480p" in quality:
                    ydl_format = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
                    postprocessors = []
                elif "360p" in quality:
                    ydl_format = "bestvideo[height<=360]+bestaudio/best[height<=360]/best"
                    postprocessors = []
                else:
                    ydl_format = "bestvideo+bestaudio/best"
                    postprocessors = []

                out_template = os.path.join(out_dir, "%(title)s.%(ext)s")

                base_opts = {
                    "format": ydl_format,
                    "outtmpl": out_template,
                    "quiet": True,
                    "no_warnings": True,
                    "progress_hooks": [self._progress_hook],
                    "postprocessors": list(postprocessors),
                    "merge_output_format": "mp4" if not is_audio else None,
                    "nopart": True,
                    "nocheckcertificate": True,
                    "continuedl": True,
                    "retries": 10,
                    "fragment_retries": 10,
                    "skip_unavailable_fragments": True,
                    "socket_timeout": 30,
                    "http_headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-us,en;q=0.5",
                    },
                    "extractor_args": {
                        "youtube": {
                            "player_client": ["android", "ios", "web"]
                        }
                    }
                }

                if turbo_enabled:
                    # Multi-fragment concurrent streams (greatly accelerates YouTube, HLS, DASH)
                    base_opts["concurrent_fragment_downloads"] = threads
                    base_opts["buffersize"] = 1048576       # 1MB buffer
                    base_opts["http_chunk_size"] = 10485760 # 10MB chunk size (bypasses YouTube CDN throttling)

                    # External multi-connection downloader (Aria2c)
                    aria2_bin = _get_aria2c_path()
                    if aria2_bin:
                        conn_limit = str(min(16, threads))
                        base_opts["external_downloader"] = {"default": aria2_bin}
                        base_opts["external_downloader_args"] = {
                            "default": [
                                "-x", conn_limit,
                                "-s", conn_limit,
                                "-j", str(threads),
                                "-k", "1M",
                                "--min-split-size=1M",
                                "--file-allocation=none",
                                "--summary-interval=1",
                                f"--max-connection-per-server={conn_limit}",
                            ]
                        }

                ydl_opts = dict(base_opts)
                sub_warning = None
                attempt_with_subs = download_subs and not is_audio

                if attempt_with_subs:
                    ydl_opts.update({
                        "writesubtitles": True,
                        "writeautomaticsub": False,  # Manual subs first to avoid 429 rate limit
                        "subtitleslangs": ["all", "zh.*", "en.*", "km.*"],
                        "subtitlesformat": "srt/best",
                        "ignoreerrors": True,
                    })

                info = None
                target_file = None

                def _run_ydl(opts):
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        inf = ydl.extract_info(url, download=True)
                        tgt = ydl.prepare_filename(inf)
                        return inf, tgt

                try:
                    info, target_file = _run_ydl(ydl_opts)
                except Exception as first_err:
                    err_lower = str(first_err).lower()

                    # Fallback 1: If aria2c downloader had issues with specific video stream, retry with native turbo
                    if "external_downloader" in ydl_opts:
                        try:
                            self.after(0, lambda: self.lbl_prog_title.configure(
                                text="⚡ Reconnecting via Native Turbo Engine...",
                                text_color="#38bdf8"
                            ))
                            self.log("⚡ [Downloader] Reconnecting stream via Native Turbo Engine...")
                            fallback_native = dict(ydl_opts)
                            fallback_native.pop("external_downloader", None)
                            fallback_native.pop("external_downloader_args", None)
                            info, target_file = _run_ydl(fallback_native)
                        except Exception as native_err:
                            err_lower = str(native_err).lower()
                            first_err = native_err

                    # Fallback 2: Subtitle rate limit 429
                    if info is None and attempt_with_subs and ("subtitles" in err_lower or "429" in err_lower or "timedtext" in err_lower):
                        sub_warning = "YouTube subtitle rate limit (HTTP 429) was bypassed. Video downloaded directly."
                        self.log("⚠️ [Downloader] YouTube Subtitle 429 rate-limited! កំពុងទាញយកវីដេអូដោយផ្ទាល់...")
                        self.after(0, lambda: self.lbl_prog_title.configure(
                            text="⚠️ Subtitle rate-limited (429). Downloading video directly...",
                            text_color="#f59e0b"
                        ))
                        try:
                            info, target_file = _run_ydl(base_opts)
                        except Exception as sub_fb_err:
                            if "external_downloader" in base_opts:
                                base_opts_no_aria = dict(base_opts)
                                base_opts_no_aria.pop("external_downloader", None)
                                base_opts_no_aria.pop("external_downloader_args", None)
                                info, target_file = _run_ydl(base_opts_no_aria)
                            else:
                                raise sub_fb_err
                    elif info is None:
                        raise first_err

                if self.cancel_download:
                    raise Exception("Download cancelled by user")

                if is_audio:
                    target_file = os.path.splitext(target_file)[0] + ".mp3"
                else:
                    if not os.path.exists(target_file):
                        mp4_alt = os.path.splitext(target_file)[0] + ".mp4"
                        if os.path.exists(mp4_alt):
                            target_file = mp4_alt
                        elif os.path.exists(target_file + ".part"):
                            try:
                                os.rename(target_file + ".part", target_file)
                            except Exception:
                                target_file = target_file + ".part"
                        elif os.path.exists(mp4_alt + ".part"):
                            try:
                                os.rename(mp4_alt + ".part", mp4_alt)
                                target_file = mp4_alt
                            except Exception:
                                target_file = mp4_alt + ".part"

                if not self.cancel_download:
                    self.after(0, lambda: self._on_download_complete(target_file, info, auto_open, sub_warning))

            except Exception as e:
                err = str(e)
                if self.cancel_download or "cancelled" in err.lower():
                    self.after(0, self._on_download_cancelled)
                else:
                    self.after(0, lambda: self._on_download_failed(err))
            finally:
                self.is_downloading = False
                self.after(0, lambda: [
                    self.btn_download.configure(state="normal"),
                    self.btn_download_and_open.configure(state="normal"),
                    self.btn_stop_download.configure(state="disabled")
                ])

        threading.Thread(target=worker, daemon=True).start()

    def stop_download(self):
        """Immediately halts video download in progress and kills external aria2c processes"""
        if not self.is_downloading:
            return

        self.cancel_download = True
        self.btn_stop_download.configure(state="disabled")
        self.lbl_prog_title.configure(text="⏹️ Stopping Download...", text_color="#f59e0b")
        self.lbl_prog_stats.configure(text="Cancelling download...")

        def _kill():
            try:
                import subprocess
                subprocess.run(["taskkill", "/f", "/im", "aria2c.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        threading.Thread(target=_kill, daemon=True).start()

    def _on_download_cancelled(self):
        self.prog_bar.set(0.0)
        self.lbl_prog_title.configure(text="⏹️ Download Cancelled", text_color="#f59e0b")
        self.lbl_prog_stats.configure(text="The download was stopped by user.")
        self.log("⏹️ [Downloader] ការទាញយកត្រូវបានបញ្ឈប់ដោយអ្នកប្រើប្រាស់ (Cancelled)")
        messagebox.showinfo("Download Stopped", "បានបញ្ឈប់ការទាញយក (Download Cancelled).")

    def _progress_hook(self, d: dict):
        if self.cancel_download:
            raise Exception("Download cancelled by user")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            downloaded = d.get("downloaded_bytes") or 0
            pct = max(0.0, min(1.0, downloaded / max(1, total)))
            speed = d.get("speed")
            eta = d.get("eta") or 0

            # Calculate smoothed speed if external downloader or fragmented stream reports 0
            now = time.time()
            if not hasattr(self, "_last_prog_time"):
                self._last_prog_time = now
                self._last_prog_bytes = downloaded

            dt = now - self._last_prog_time
            if (speed is None or speed <= 0) and dt >= 0.5:
                speed = max(0, (downloaded - self._last_prog_bytes) / dt)
                self._last_prog_time = now
                self._last_prog_bytes = downloaded
            elif speed and speed > 0 and dt >= 0.5:
                self._last_prog_time = now
                self._last_prog_bytes = downloaded

            speed = speed or 0
            speed_mb = speed / (1024 * 1024)
            down_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            eta_m, eta_s = divmod(int(eta), 60)

            stats_text = f"🚀 Speed: {speed_mb:.2f} MB/s | Size: {down_mb:.1f} MB / {tot_mb:.1f} MB ({int(pct*100)}%) | ETA: {eta_m:02d}:{eta_s:02d}"

            # Log periodically (every 20%) to keep log clean and informative
            step = int(pct * 100) // 20
            if not hasattr(self, "_last_log_step") or step > self._last_log_step:
                self._last_log_step = step
                self.log(f"⚡ [Downloader] ទាញយកបាន: {int(pct*100)}% | ល្បឿន: {speed_mb:.2f} MB/s | {down_mb:.1f}/{tot_mb:.1f} MB | ETA: {eta_m:02d}:{eta_s:02d}")

            def _update():
                self.prog_bar.set(pct)
                self.lbl_prog_title.configure(text=f"⚡ Turbo Downloading: {int(pct*100)}% ({speed_mb:.1f} MB/s)", text_color="#38bdf8")
                self.lbl_prog_stats.configure(text=stats_text)

            self.after(0, _update)

    def _on_download_complete(self, target_file: str, info: dict, auto_open: bool, sub_warning: str = None):
        self.prog_bar.set(1.0)
        title = info.get("title", "Video") if info else "Video"
        filename = os.path.basename(target_file)
        self.lbl_prog_title.configure(text="🎉 Download Finished Successfully!", text_color="#10b981")
        if sub_warning:
            self.lbl_prog_stats.configure(text=f"Saved: {target_file} ({sub_warning})")
        else:
            self.lbl_prog_stats.configure(text=f"Saved: {target_file}")

        sz_mb = os.path.getsize(target_file) / (1024 * 1024) if os.path.exists(target_file) else 0.0
        self.log(f"🎉 [Downloader] ទាញយកវីដេអូបានជោគជ័យ! -> {filename} ({sz_mb:.1f} MB)")
        if sub_warning:
            self.log(f"ℹ️ [Downloader] {sub_warning}")

        # Add to download history box
        self._add_to_history(target_file, title)

        if auto_open and self.on_open_video_in_studio:
            self.log(f"🎬 [Downloader] បើកវីដេអូ {filename} ចូលក្នុង Movie Studio ស្វ័យប្រវត្តិ...")
            self.on_open_video_in_studio(target_file)
        else:
            msg = f"🎉 Downloaded successfully!\n\nFile:\n{filename}\n\nSaved to:\n{os.path.dirname(target_file)}"
            if sub_warning:
                msg += f"\n\nNote: {sub_warning}\n(You can use '🎙️ Capture CC' in Studio to auto-generate subtitles with Whisper AI!)"
            messagebox.showinfo("Download Complete", msg)

    def _on_download_failed(self, err: str):
        clean_err = re.sub(r'\x1b\[[0-9;]*[mGKH]', '', str(err)).strip()
        self.lbl_prog_title.configure(text="❌ Download Failed", text_color="#ef4444")
        short_err = clean_err.split("\n")[0][:90]
        self.lbl_prog_stats.configure(text=f"Error: {short_err}")
        self.log(f"❌ [Downloader] ការទាញយកបរាជ័យ: {clean_err[:120]}")

        if "429" in clean_err:
            friendly_msg = (
                "⚠️ YouTube Server Rate Limit (HTTP 429: Too Many Requests)\n\n"
                "YouTube is temporarily rate-limiting requests.\n"
                "Solutions:\n"
                "1. Uncheck 'Download Subtitles (.srt)' and try again.\n"
                "2. Try choosing another quality resolution (e.g. 720p HD or 480p).\n"
                "3. In the Studio, you can click '🎙️ Capture CC' to extract subtitles with Whisper AI."
            )
            messagebox.showerror("Download Rate Limited", friendly_msg)
        else:
            messagebox.showerror("Download Error", f"Failed to download video:\n\n{clean_err}")

    def _add_to_history(self, file_path: str, title: str):
        if not os.path.exists(file_path):
            return
        if hasattr(self, "lbl_no_hist") and self.lbl_no_hist.winfo_exists():
            self.lbl_no_hist.pack_forget()

        self.downloaded_items.append(file_path)
        self.lbl_hist_count.configure(text=f"{len(self.downloaded_items)} files")

        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        fname = os.path.basename(file_path)

        card = ctk.CTkFrame(self.box_history, fg_color="#161b24", corner_radius=4, border_width=1, border_color="#242e42")
        card.pack(fill="x", padx=6, pady=3)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=6)

        ctk.CTkLabel(row, text="🎬", font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 6))

        info_col = ctk.CTkFrame(row, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(info_col, text=fname, font=ctk.CTkFont(size=11, weight="bold"), text_color="#e2e8f0", anchor="w").pack(anchor="w")
        ctk.CTkLabel(info_col, text=f"Size: {size_mb:.1f} MB | {file_path}", font=ctk.CTkFont(size=9), text_color="#64748b", anchor="w").pack(anchor="w")

        # Action buttons
        btn_studio = ctk.CTkButton(
            row,
            text="🎬 Open in Studio",
            width=115,
            height=26,
            corner_radius=3,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda f=file_path: self.on_open_video_in_studio and self.on_open_video_in_studio(f)
        )
        btn_studio.pack(side="right", padx=(4, 0))

        btn_show = ctk.CTkButton(
            row,
            text="📁 Show in Folder",
            width=100,
            height=26,
            corner_radius=3,
            fg_color="#1e293b",
            hover_color="#334155",
            font=ctk.CTkFont(size=10),
            command=lambda f=file_path: os.system(f'explorer /select,"{f}"')
        )
        btn_show.pack(side="right", padx=2)
