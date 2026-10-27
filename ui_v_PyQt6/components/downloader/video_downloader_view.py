"""
Video Downloader View Component for PyQt6 / PySide6 Desktop Studio
Turbo downloader, live metadata inspection, dynamic quality selection with MB/GB sizes,
subtitle / SRT downloading, and automatic one-folder-per-movie organization.
"""

import os
import re
import urllib.request
import threading
from datetime import datetime
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QComboBox, QProgressBar, QGroupBox, QPlainTextEdit, QFileDialog, 
    QMessageBox, Qt, QTimer, Signal, QCheckBox, QPixmap, QImage,
    QSplitter, QFrame, QScrollArea
)
from utils import format_timestamp

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


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


def sanitize_folder_name(name: str) -> str:
    """Sanitizes movie/video title to be a safe, valid Windows directory name."""
    if not name:
        return "downloaded_movie"
    # Remove Windows illegal path characters
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    # Remove emojis or control characters that could break file systems if needed, but preserve Chinese/Khmer/English
    clean = re.sub(r'[\r\n\t]+', " ", clean).strip(". ")
    return clean[:70] if clean else "downloaded_movie"


class VideoDownloaderView(QWidget):
    """
    Video Downloader & Engine Studio:
    - Fast yt-dlp downloader with multi-connection stream acceleration
    - Dynamic video quality selection with accurate MB / GB file sizes
    - Downloads video + subtitles into one dedicated self-contained movie folder
    - Real-time thumbnail & subtitle metadata preview
    - Dedicated Live Logs Console with timestamps
    - Direct hand-off to Movie Studio
    """
    sig_dispatch = Signal(object)

    def __init__(self, parent=None, on_open_video_in_studio=None, log_callback=None):
        super().__init__(parent)
        self.on_open_video_in_studio = on_open_video_in_studio
        self.log_callback = log_callback

        self.sig_dispatch.connect(self._handle_dispatch)

        self.download_dir = os.path.abspath("downloads")
        os.makedirs(self.download_dir, exist_ok=True)
        self.is_downloading = False
        self.cancel_download = False
        self.current_info = None
        self._format_data = {}  # combo label -> ydl format selector

        self._init_ui()
        self._auto_detect_cookies(silent=True)

    def _handle_dispatch(self, fn):
        try:
            fn()
        except Exception as e:
            print(f"Downloader GUI dispatch error: {e}")

    def run_on_main(self, fn):
        self.sig_dispatch.emit(fn)

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setOpaqueResize(True)

        # ========================================================
        # 1. LEFT COLUMN: VIDEO METADATA & SOURCE PREVIEW
        # ========================================================
        self.card_prev = QGroupBox("Video Metadata & Source Preview")
        left_layout = QVBoxLayout(self.card_prev)
        left_layout.setContentsMargins(10, 12, 10, 10)
        left_layout.setSpacing(8)

        # Widescreen Thumbnail
        self.lbl_thumb = QLabel("No Preview")
        self.lbl_thumb.setFixedHeight(180)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet(
            "background-color: #171b22; border: 1px solid #363d4a; border-radius: 6px; color: #64748b; font-size: 11px;"
        )
        left_layout.addWidget(self.lbl_thumb)

        # Video Title
        self.lbl_prev_title = QLabel("Video Title: --")
        self.lbl_prev_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f1f5f9;")
        self.lbl_prev_title.setWordWrap(True)
        self.lbl_prev_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        left_layout.addWidget(self.lbl_prev_title)

        # Metadata rows
        self.lbl_prev_info = QLabel("Duration: -- | Creator: --")
        self.lbl_prev_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_prev_info.setWordWrap(True)
        left_layout.addWidget(self.lbl_prev_info)

        self.lbl_prev_cc = QLabel("Subtitles / CC: --")
        self.lbl_prev_cc.setStyleSheet("color: #34d399; font-weight: bold; font-size: 11px;")
        self.lbl_prev_cc.setWordWrap(True)
        left_layout.addWidget(self.lbl_prev_cc)

        self.lbl_prev_size = QLabel("Estimated Sizes: --")
        self.lbl_prev_size.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.lbl_prev_size.setWordWrap(True)
        left_layout.addWidget(self.lbl_prev_size)

        # Source URL Box
        source_box = QFrame()
        source_box.setStyleSheet("background-color: #171d25; border: 1px solid #283342; border-radius: 6px; padding: 6px;")
        sb_layout = QVBoxLayout(source_box)
        sb_layout.setContentsMargins(6, 6, 6, 6)
        sb_layout.setSpacing(4)
        sb_layout.addWidget(QLabel("Original Source URL (ប្រភពវីដេអូ):"))
        self.lbl_source_url = QLabel("--")
        self.lbl_source_url.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: Consolas;")
        self.lbl_source_url.setWordWrap(True)
        self.lbl_source_url.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sb_layout.addWidget(self.lbl_source_url)

        sb_btn_row = QHBoxLayout()
        sb_btn_row.setSpacing(6)
        btn_copy_source = QPushButton("Copy Link")
        btn_copy_source.clicked.connect(self._copy_source_url)
        sb_btn_row.addWidget(btn_copy_source)

        btn_open_browser = QPushButton("Open in Browser")
        btn_open_browser.clicked.connect(self._open_url_in_browser)
        sb_btn_row.addWidget(btn_open_browser)
        sb_layout.addLayout(sb_btn_row)

        left_layout.addWidget(source_box)
        left_layout.addStretch()

        self.splitter.addWidget(self.card_prev)

        # ========================================================
        # 2. RIGHT COLUMN: DOWNLOAD SETTINGS, ACTIONS, PROGRESS & LOGS
        # ========================================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # GROUP 1: Video URL & Format Settings
        group_top = QGroupBox("Video URL & Multi-Thread Turbo Settings")
        t_layout = QVBoxLayout(group_top)
        t_layout.setContentsMargins(10, 12, 10, 10)
        t_layout.setSpacing(8)

        # URL Row
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Video Link:"))
        self.entry_url = QLineEdit()
        self.entry_url.setPlaceholderText("Paste YouTube, Facebook, TikTok, Bilibili or any video link here...")
        self.entry_url.returnPressed.connect(self.start_preview_info)
        url_row.addWidget(self.entry_url, 1)

        btn_paste = QPushButton("Paste")
        btn_paste.clicked.connect(self._paste_url)
        url_row.addWidget(btn_paste)

        btn_preview = QPushButton("Preview Info")
        btn_preview.setObjectName("btn_primary")
        btn_preview.clicked.connect(self.start_preview_info)
        url_row.addWidget(btn_preview)
        t_layout.addLayout(url_row)

        # Options Row: Quality, Subtitles, Turbo
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)

        opt_row.addWidget(QLabel("Quality (គុណភាព / ទំហំ):"))
        self.combo_quality = QComboBox()
        self.combo_quality.setMinimumWidth(200)
        self.combo_quality.addItems(["Best Available (Auto)", "1080p (Full HD)", "720p (HD)", "480p (SD)", "MP3 Audio (192kbps)"])
        opt_row.addWidget(self.combo_quality, 1)

        self.check_download_subs = QCheckBox("ទាញយក Subtitles / SRT")
        self.check_download_subs.setChecked(True)
        self.check_download_subs.setToolTip("ទាញយកឯកសារ Subtitle SRT ដាក់ក្នុង Folder តែមួយជាមួយវីដេអូ")
        opt_row.addWidget(self.check_download_subs)

        self.combo_sub_lang = QComboBox()
        self.combo_sub_lang.setMinimumWidth(130)
        self.combo_sub_lang.addItems(["Auto / ភាសាដើម", "Chinese (zh)", "English (en)", "All Subtitles"])
        opt_row.addWidget(self.combo_sub_lang)

        opt_row.addWidget(QLabel("Turbo:"))
        self.combo_threads = QComboBox()
        self.combo_threads.addItems(["16 Threads (Max)", "8 Threads", "4 Threads", "Single Stream"])
        opt_row.addWidget(self.combo_threads)
        t_layout.addLayout(opt_row)

        # Folder Save Location Row
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("Save Folder:"))
        self.entry_folder = QLineEdit(self.download_dir)
        folder_row.addWidget(self.entry_folder, 1)

        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(btn_browse)
        t_layout.addLayout(folder_row)

        # Cookies File Row (for Douyin / VIP / restricted platforms)
        cookies_row = QHBoxLayout()
        cookies_row.addWidget(QLabel("Cookies (.txt):"))
        self.entry_cookies = QLineEdit()
        self.entry_cookies.setPlaceholderText("Optional: Netscape cookies.txt file for Douyin / restricted videos...")
        cookies_row.addWidget(self.entry_cookies, 1)

        btn_browse_cookies = QPushButton("Browse")
        btn_browse_cookies.clicked.connect(self._browse_cookies)
        cookies_row.addWidget(btn_browse_cookies)

        btn_detect_cookies = QPushButton("Auto-Detect")
        btn_detect_cookies.clicked.connect(lambda: self._auto_detect_cookies(silent=False))
        cookies_row.addWidget(btn_detect_cookies)

        btn_grab_browser = QPushButton("🌐 Grab from Browser (Auto)")
        btn_grab_browser.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold;")
        btn_grab_browser.setToolTip("បើក Built-in Browser ដើម្បីចាប់យក Cookies ពី Douyin ដោយស្វ័យប្រវត្ត មិនបាច់ដំឡើង Extension ឡើយ")
        btn_grab_browser.clicked.connect(self._open_cookie_grabber)
        cookies_row.addWidget(btn_grab_browser)
        t_layout.addLayout(cookies_row)

        # URL Source Option Checkbox (New user request)
        opt_save_row = QHBoxLayout()
        self.check_save_url = QCheckBox("Save Source URL (រក្សាទុក Link ប្រភពវីដេអូជា file .url និង .txt ដើម្បីងាយស្រួលរកប្រភព)")
        self.check_save_url.setChecked(True)
        self.check_save_url.setToolTip("រក្សាទុក shortcut .url (ចុច double click បើក link ក្នុង Browser ភ្លាម) និង file .txt កត់ត្រាប្រភពវីដេអូក្នុង folder ជាមួយគ្នា")
        self.check_save_url.setStyleSheet("color: #38bdf8; font-weight: bold;")
        opt_save_row.addWidget(self.check_save_url)
        opt_save_row.addStretch()
        t_layout.addLayout(opt_save_row)

        right_layout.addWidget(group_top)

        # GROUP 2: ACTION BUTTONS & PROGRESS
        group_prog = QGroupBox("Download Action & Transfer Progress")
        pr_layout = QVBoxLayout(group_prog)
        pr_layout.setContentsMargins(10, 12, 10, 10)
        pr_layout.setSpacing(6)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_download = QPushButton("Download Movie + Subtitles")
        self.btn_download.setObjectName("btn_primary")
        self.btn_download.setFixedHeight(34)
        self.btn_download.clicked.connect(lambda: self.start_download(auto_open=False))
        btn_row.addWidget(self.btn_download, 1)

        self.btn_download_open = QPushButton("Download & Open in Studio")
        self.btn_download_open.setObjectName("btn_success")
        self.btn_download_open.setFixedHeight(34)
        self.btn_download_open.clicked.connect(lambda: self.start_download(auto_open=True))
        btn_row.addWidget(self.btn_download_open, 1)

        self.btn_stop = QPushButton("Cancel Download")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_download)
        btn_row.addWidget(self.btn_stop)
        pr_layout.addLayout(btn_row)

        self.lbl_prog_title = QLabel("Ready to download")
        self.lbl_prog_title.setStyleSheet("font-weight: bold; color: #38bdf8;")
        pr_layout.addWidget(self.lbl_prog_title)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 100)
        self.prog_bar.setValue(0)
        pr_layout.addWidget(self.prog_bar)

        self.lbl_prog_stats = QLabel("Speed: 0.0 MB/s | Size: 0.0 MB / 0.0 MB | ETA: 00:00")
        self.lbl_prog_stats.setStyleSheet("font-family: Consolas; font-size: 11px; color: #94a3b8;")
        pr_layout.addWidget(self.lbl_prog_stats)

        right_layout.addWidget(group_prog)

        # GROUP 3: LIVE LOGS CONSOLE
        group_log = QGroupBox("Live Download & Engine Diagnostics Console")
        l_layout = QVBoxLayout(group_log)
        l_layout.setContentsMargins(10, 12, 10, 8)
        l_layout.setSpacing(4)

        log_top = QHBoxLayout()
        log_top.addStretch()

        btn_clr_log = QPushButton("Clear Logs")
        btn_clr_log.setFixedSize(90, 24)
        btn_clr_log.clicked.connect(lambda: self.txt_logs.clear())
        log_top.addWidget(btn_clr_log)
        l_layout.addLayout(log_top)

        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setStyleSheet("font-family: Consolas; font-size: 11px; background-color: #171b22; color: #34d399; border: 1px solid #282e3a; border-radius: 4px;")
        l_layout.addWidget(self.txt_logs)

        right_layout.addWidget(group_log, 1)

        self.splitter.addWidget(right_container)
        self.splitter.setSizes([380, 720])
        main_layout.addWidget(self.splitter)

    # ------------------ LOGGING & UI HELPERS ------------------
    def log(self, text: str):
        def _do():
            self.txt_logs.appendPlainText(text)
            self.txt_logs.ensureCursorVisible()
            if self.log_callback:
                self.log_callback(text)
        self.run_on_main(_do)

    def _browse_cookies(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Netscape cookies.txt File", self.download_dir, "Text Files (*.txt);;All Files (*)")
        if f:
            self.entry_cookies.setText(f)
            self.log(f"🍪 [Cookies] បានជ្រើសរើសឯកសារ Cookies: {f}")

    def _auto_detect_cookies(self, silent: bool = False):
        detected = self._get_auto_cookie_file()
        if detected:
            if hasattr(self, "entry_cookies"):
                self.entry_cookies.setText(detected)
            if not silent:
                self.log(f"🍪 [Cookies] រកឃើញឯកសារ Cookies ស្វ័យប្រវត្ត: {detected}")
            return detected
        elif not silent:
            self.log("ℹ️ [Cookies] មិនទាន់រកឃើញឯកសារ cookies.txt ក្នុង Folder កម្មវិធីនៅឡើយទេ។")
        return ""

    def _get_auto_cookie_file(self) -> str:
        candidates = [
            os.path.abspath("cookies.txt"),
            os.path.join(self.download_dir, "cookies.txt"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "cookies.txt"),
            os.path.expanduser("~/cookies.txt")
        ]
        for c in candidates:
            if os.path.isfile(c) and os.path.getsize(c) > 0:
                return os.path.abspath(c)
        return ""

    def _get_active_cookie_file(self) -> str:
        if hasattr(self, "entry_cookies"):
            p = self.entry_cookies.text().strip()
            if p and os.path.isfile(p):
                return os.path.abspath(p)
        return self._get_auto_cookie_file()

    def _open_cookie_grabber(self):
        """Opens built-in browser dialog to intercept Douyin / TikTok cookies safely."""
        from ui_v_PyQt6.components.downloader.cookie_grabber_dialog import CookieGrabberDialog
        url = self.entry_url.text().strip()
        target_site = "https://www.douyin.com"
        if url and "tiktok.com" in url:
            target_site = "https://www.tiktok.com"
        elif url and "bilibili.com" in url:
            target_site = "https://www.bilibili.com"
        elif url and "douyin.com" in url:
            target_site = url if url.startswith("http") else f"https://{url}"

        dlg = CookieGrabberDialog(
            parent=self,
            initial_url=target_site,
            on_cookies_saved=self._on_cookies_grabbed
        )
        dlg.exec()

    def _on_cookies_grabbed(self, cookie_file: str, total_count: int):
        """Callback when cookies are saved from built-in browser."""
        if hasattr(self, "entry_cookies"):
            self.entry_cookies.setText(cookie_file)
        self.log(f"🎉 [Cookies] បានចាប់យក និងរក្សាទុក Cookies ចំនួន {total_count} ដោយជោគជ័យតាម Built-in Browser!")
        self.log(f"📁 [Cookies] ឯកសារត្រូវបានរក្សាទុកក្នុង: {cookie_file}")
        # Automatically trigger preview if URL is present
        if self.entry_url.text().strip():
            self.start_preview_info()

    def _paste_url(self):
        from ui_v_PyQt6.qt_compat import QApplication
        cb = QApplication.clipboard().text().strip()
        if cb:
            clean_url = normalize_video_url(cb)
            self.entry_url.setText(clean_url)
            if clean_url != cb:
                self.log(f"🔄 [Downloader] បានស្រង់ និងសម្រួល Link ស្វ័យប្រវត្ត: {clean_url}")
            self.start_preview_info()

    def _browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Download Directory", self.download_dir)
        if d:
            self.download_dir = d
            self.entry_folder.setText(d)

    def _copy_source_url(self):
        url = self.entry_url.text().strip()
        if url:
            from ui_v_PyQt6.qt_compat import QApplication
            QApplication.clipboard().setText(url)
            self.log(f"📋 [Clipboard] បានចម្លង Link ប្រភព: {url}")

    def _open_url_in_browser(self):
        url = self.entry_url.text().strip()
        if url:
            import webbrowser
            webbrowser.open(url)
            self.log(f"🌐 [Browser] បើក Link ប្រភពក្នុង Browser: {url}")

    # ------------------ METADATA PREVIEW ------------------
    def start_preview_info(self):
        raw_url = self.entry_url.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "No URL", "សូមបញ្ចូល Video Link ជាមុនសិន!")
            return

        url = normalize_video_url(raw_url)
        if url != raw_url:
            self.entry_url.setText(url)
            self.log(f"🔄 [Downloader] បានសម្រួល Link ស្វ័យប្រវត្ត: {url}")

        self.lbl_prog_title.setText(f"🔍 Analyzing video metadata: {url[:50]}...")
        self.lbl_thumb.setText("⏳ Loading...")
        self.lbl_source_url.setText(url)
        self.log(f"🔍 [Downloader] កំពុងទាញយកព័ត៌មានវីដេអូ (Analyzing URL): {url}")

        def worker():
            try:
                if not yt_dlp:
                    raise Exception("yt-dlp is not installed")
                ydl_opts = {
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 15,
                    "extractor_args": {"youtube": {"player_client": ["android", "web"]}}
                }
                cookie_path = self._get_active_cookie_file()
                if cookie_path:
                    ydl_opts["cookiefile"] = cookie_path

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                self.current_info = info

                title = info.get("title", "Untitled")
                dur = float(info.get("duration", 0) or 0)
                uploader = info.get("uploader") or info.get("channel") or "Unknown"
                subs = info.get("subtitles", {})
                auto_subs = info.get("automatic_captions", {})

                # 1. Available subtitles
                sub_langs = list(subs.keys())
                auto_langs = list(auto_subs.keys())

                # 2. Extract and calculate MB / GB for each resolution
                audio_formats = [f for f in info.get("formats", []) if f.get("vcodec") == "none" and f.get("acodec") != "none"]
                best_audio = max(audio_formats, key=lambda f: f.get("tbr") or 0) if audio_formats else None
                audio_bytes = (best_audio.get("filesize") or best_audio.get("filesize_approx") or (best_audio.get("tbr", 128) * 1000 * dur / 8)) if best_audio else (128 * 1000 * dur / 8)

                res_map = {}
                for f in info.get("formats", []):
                    h = f.get("height")
                    if not h or f.get("vcodec") == "none":
                        continue
                    fs = f.get("filesize") or f.get("filesize_approx")
                    if not fs and f.get("tbr") and dur > 0:
                        fs = f.get("tbr") * 1000 * dur / 8
                    total_sz = (fs or 0) + (0 if f.get("acodec") != "none" else audio_bytes)
                    if h not in res_map or total_sz > res_map[h]["size"]:
                        res_map[h] = {"size": total_sz, "format_id": f.get("format_id")}

                # Build quality combo items with MB/GB
                combo_items = []
                self._format_data = {}

                # Audio option
                aud_sz_str = f"{audio_bytes / (1024**3):.2f} GB" if audio_bytes >= 1024**3 else f"{audio_bytes / (1024**2):.1f} MB"
                aud_lbl = f"🎵 MP3 Audio Only ~ {aud_sz_str}"
                combo_items.append(aud_lbl)
                self._format_data[aud_lbl] = "bestaudio/best"

                # Video resolutions sorted high to low
                size_summaries = []
                for h in sorted(res_map.keys(), reverse=True):
                    sz = res_map[h]["size"]
                    sz_str = f"{sz / (1024**3):.2f} GB" if sz >= 1024**3 else f"{sz / (1024**2):.1f} MB"
                    quality_name = "Full HD" if h == 1080 else ("HD" if h == 720 else ("2K" if h == 1440 else ("4K" if h >= 2160 else "SD")))
                    lbl = f"🎬 {h}p ({quality_name}) ~ {sz_str}"
                    combo_items.append(lbl)
                    self._format_data[lbl] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"
                    if len(size_summaries) < 3:
                        size_summaries.append(f"{h}p: {sz_str}")

                # Best available auto
                best_lbl = "🌟 Best Available (Auto Highest Quality)"
                combo_items.insert(0, best_lbl)
                self._format_data[best_lbl] = "bestvideo+bestaudio/best"

                # 3. Subtitle language combo items
                sub_combo_items = ["Auto / ភាសាដើម (Recommended)"]
                if "zh-Hans" in sub_langs or any("zh-Hans" in k for k in sub_langs):
                    sub_combo_items.append("Chinese Simplified (zh-Hans)")
                if "zh-Hant" in sub_langs or any("zh-Hant" in k for k in sub_langs):
                    sub_combo_items.append("Chinese Traditional (zh-Hant)")
                if "en" in sub_langs or any("en" in k for k in sub_langs):
                    sub_combo_items.append("English (en)")
                for sl in sub_langs:
                    if sl not in ["zh-Hans", "zh-Hant", "en"] and len(sub_combo_items) < 8:
                        sub_combo_items.append(sl)
                sub_combo_items.append("All Subtitles (ទាញយកទាំងអស់)")
                sub_combo_items.append("No Subtitles (មិនទាញយក)")

                # 4. Fetch Thumbnail Image
                pixmap = None
                thumb_url = info.get("thumbnail")
                if thumb_url:
                    try:
                        req = urllib.request.Request(thumb_url, headers={"User-Agent": "Mozilla/5.0"})
                        raw_data = urllib.request.urlopen(req, timeout=5).read()
                        qimg = QImage.fromData(raw_data)
                        if not qimg.isNull():
                            pixmap = QPixmap.fromImage(qimg).scaled(340, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    except Exception as th_err:
                        print(f"Thumbnail load error: {th_err}")

                def _apply_preview():
                    self.lbl_prev_title.setText(title)
                    self.lbl_prev_info.setText(f"⏱️ Duration: {format_timestamp(dur)} | 👤 Creator: {uploader}")
                    all_subs_display = sub_langs[:5] if sub_langs else (auto_langs[:4] if auto_langs else ["None"])
                    self.lbl_prev_cc.setText(f"💬 Subtitles / CC: {', '.join(all_subs_display)}")
                    self.lbl_prev_size.setText(f"📦 Estimated Sizes: {' | '.join(size_summaries) if size_summaries else '--'}")
                    self.lbl_source_url.setText(url)
                    self.lbl_prog_title.setText("✅ Video analyzed successfully!")

                    if pixmap:
                        self.lbl_thumb.setPixmap(pixmap)
                    else:
                        self.lbl_thumb.setText("🖼️ Preview Ready")

                    # Update Quality ComboBox
                    self.combo_quality.clear()
                    self.combo_quality.addItems(combo_items)
                    # Default to 1080p if available
                    for idx, ci in enumerate(combo_items):
                        if "1080p" in ci:
                            self.combo_quality.setCurrentIndex(idx)
                            break

                    # Update Subtitle Language ComboBox
                    self.combo_sub_lang.clear()
                    self.combo_sub_lang.addItems(sub_combo_items)

                    self.log(f"✅ [Downloader] វិភាគជោគជ័យ: \"{title[:50]}\" | រយៈពេល: {format_timestamp(dur)}")
                    if sub_langs:
                        self.log(f"📥 [Subtitles] រកឃើញ Subtitles: {', '.join(sub_langs)}")

                self.run_on_main(_apply_preview)

            except Exception as e:
                err_str = strip_ansi(str(e))
                def _apply_err():
                    self.lbl_thumb.setText("❌ Failed")
                    self.lbl_prog_title.setText(f"❌ Analysis failed: {err_str[:60]}")
                self.run_on_main(_apply_err)
                self.log(f"❌ [Downloader] បរាជ័យក្នុងការវិភាគ URL: {err_str}")
                if "Fresh cookies" in err_str or ("403" in err_str and "douyin" in url.lower()):
                    self.log("⚠️ [Douyin Notice] វីដេអូ Douyin នេះតម្រូវឱ្យមាន Cookies (cookies.txt) ដោយសារ anti-bot protection របស់ Douyin!")
                    self.log("💡 វិធីដោះស្រាយងាយស្រួលបំផុត & សុវត្ថិភាព 100% (មិនបាច់ប្រើ Extension ឡើយ):")
                    self.log("   👉 ចុចលើប៊ូតុងពណ៌ខៀវ '🌐 Grab from Browser (Auto)' នៅជួរ Cookies ខាងលើ")
                    self.log("   👉 ប្រព័ន្ធ Browser ក្នុងកម្មវិធីនឹងបើកទំព័រ Douyin ហើយចាប់យក Cookies/Token ដោយស្វ័យប្រវត្ត!")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------ DOWNLOAD ENGINE ------------------
    def start_download(self, auto_open: bool = False):
        raw_url = self.entry_url.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "No URL", "សូមបញ្ចូល Video Link ជាមុនសិន!")
            return
        if self.is_downloading:
            return

        url = normalize_video_url(raw_url)
        if url != raw_url:
            self.entry_url.setText(url)
            self.log(f"🔄 [Downloader] បានសម្រួល Link ស្វ័យប្រវត្ត: {url}")

        base_out_dir = self.entry_folder.text().strip() or self.download_dir
        quality_label = self.combo_quality.currentText()
        selected_format = self._format_data.get(quality_label, "bestvideo+bestaudio/best")
        download_subs = self.check_download_subs.isChecked()
        sub_lang_choice = self.combo_sub_lang.currentText()
        save_url_enabled = self.check_save_url.isChecked() if hasattr(self, "check_save_url") else True

        # Threads count
        thread_choice = self.combo_threads.currentText()
        num_threads = 16 if "16" in thread_choice else (8 if "8" in thread_choice else (4 if "4" in thread_choice else 1))

        self.is_downloading = True
        self.cancel_download = False
        self.btn_download.setEnabled(False)
        self.btn_download_open.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.log(f"🚀 [Downloader] ចាប់ផ្ដើមទាញយកវីដេអូ | {quality_label} | Turbo: {num_threads} Streams")

        def worker():
            try:
                cookie_path = self._get_active_cookie_file()

                # 1. Fetch info if not cached
                info = self.current_info
                if not info:
                    check_opts = {"quiet": True, "skip_download": True, "nocheckcertificate": True}
                    if cookie_path:
                        check_opts["cookiefile"] = cookie_path
                    with yt_dlp.YoutubeDL(check_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                    self.current_info = info

                raw_title = info.get("title", "downloaded_movie")
                # ── RULE: Dedicated single folder per movie/video ──
                folder_name = sanitize_folder_name(raw_title)
                movie_folder = os.path.join(base_out_dir, folder_name)
                os.makedirs(movie_folder, exist_ok=True)

                self.log(f"📁 [Downloader] រក្សាទុកក្នុង Folder រឿង: {folder_name}")

                # Only treat as audio if user specifically picked "MP3 Audio Only"
                is_audio = "MP3" in quality_label or "Audio Only" in quality_label or selected_format.startswith("bestaudio")
                out_tmpl = os.path.join(movie_folder, f"{folder_name}.%(ext)s")

                # 2. Build yt-dlp options with anti-403 YouTube client configuration
                opts = {
                    "format": selected_format,
                    "outtmpl": out_tmpl,
                    "quiet": True,
                    "no_warnings": True,
                    "nopart": True,
                    "nocheckcertificate": True,
                    "concurrent_fragment_downloads": max(1, min(4, num_threads)),
                    "extractor_args": {
                        "youtube": {
                            "player_client": ["android", "ios"]
                        }
                    },
                    "http_headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    },
                    "progress_hooks": [self._progress_hook]
                }
                if cookie_path:
                    opts["cookiefile"] = cookie_path

                # Ensure merged video format is clean MP4
                if not is_audio:
                    opts["merge_output_format"] = "mp4"

                # Add Subtitles download options
                if download_subs and "No Subtitles" not in sub_lang_choice:
                    opts["writesubtitles"] = True
                    opts["writeautomaticsub"] = True
                    opts["subtitlesformat"] = "srt/best"
                    opts["ignoreerrors"] = True  # Don't fail entire video if one subtitle gives 429

                    # Pick language
                    if "zh-Hans" in sub_lang_choice or "Chinese (zh" in sub_lang_choice:
                        opts["subtitleslangs"] = ["zh-Hans", "zh"]
                    elif "zh-Hant" in sub_lang_choice:
                        opts["subtitleslangs"] = ["zh-Hant", "zh-TW"]
                    elif "English" in sub_lang_choice or "en" in sub_lang_choice:
                        opts["subtitleslangs"] = ["en"]
                    elif "All" in sub_lang_choice:
                        opts["subtitleslangs"] = ["zh-Hans", "zh", "en", "all"]
                    else:
                        # Auto: pick first available subtitle or chinese/english
                        available_subs = list(info.get("subtitles", {}).keys()) + list(info.get("automatic_captions", {}).keys())
                        chosen = []
                        for pref in ["zh-Hans", "zh", "en", "zh-Hant"]:
                            if pref in available_subs:
                                chosen.append(pref)
                        if not chosen and available_subs:
                            chosen.append(available_subs[0])
                        opts["subtitleslangs"] = chosen if chosen else ["all"]

                    self.log(f"📥 [Subtitles] កំពុងទាញយកឯកសារ Subtitle (.srt): {opts.get('subtitleslangs')}")

                # Audio extraction options ONLY if MP3 was chosen
                if is_audio:
                    opts["postprocessors"] = [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }]

                # 3. Execute Download with resilient fallback if 403 Forbidden occurs
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                except Exception as dl_err:
                    err_text = str(dl_err)
                    if "403" in err_text or "forbidden" in err_text.lower() or "requested format" in err_text.lower():
                        self.log("⚠️ [Downloader] 403 Forbidden / Stream កម្រិតខ្ពស់, កំពុងប្ដូរទៅទាញយកតាម Android Stream ស្វ័យប្រវត្តិ...")
                        opts["format"] = "best[ext=mp4]/best"
                        opts["extractor_args"] = {"youtube": {"player_client": ["android"]}}
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            ydl.download([url])
                    else:
                        raise dl_err

                # 4. Post-Download: Find primary video & ensure .srt file is present next to video
                downloaded_video = None
                downloaded_srt = None

                media_exts = (".mp3", ".m4a", ".wav") if is_audio else (".mp4", ".mkv", ".webm", ".avi", ".mov")
                for fname in os.listdir(movie_folder):
                    fpath = os.path.join(movie_folder, fname)
                    if fname.lower().endswith(media_exts):
                        if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
                            downloaded_video = fpath
                    elif fname.lower().endswith((".srt", ".vtt")):
                        downloaded_srt = fpath

                # Check if video was successfully downloaded
                if not downloaded_video or not os.path.exists(downloaded_video) or os.path.getsize(downloaded_video) == 0:
                    raise Exception("ទាញយកវីដេអូមិនបានសម្រេច (0 Bytes / 403 Forbidden)។ សូមសាកល្បងជ្រើសរើស Quality ផ្សេង ឬចុច Download ម្ដងទៀត!")

                # Standardize subtitle filename to <folder_name>.srt so Movie Studio auto-loads it instantly
                if downloaded_srt and not os.path.exists(os.path.join(movie_folder, f"{folder_name}.srt")):
                    import shutil
                    target_srt = os.path.join(movie_folder, f"{folder_name}.srt")
                    try:
                        shutil.copy2(downloaded_srt, target_srt)
                        downloaded_srt = target_srt
                        self.log(f"📄 [Subtitles] បានកំណត់ឈ្មោះ SRT ស្វ័យប្រវត្ត: {os.path.basename(target_srt)}")
                    except Exception:
                        pass

                sz_mb = (os.path.getsize(downloaded_video) / (1024 * 1024)) if (downloaded_video and os.path.exists(downloaded_video)) else 0.0
                sz_str = f"{sz_mb / 1024:.2f} GB" if sz_mb >= 1024 else f"{sz_mb:.1f} MB"

                v_name = os.path.basename(downloaded_video) if downloaded_video else folder_name
                self.log(f"🎉 [Downloader] ទាញយកបានជោគជ័យ! -> {v_name} ({sz_str})")
                self.log(f"📁 [Folder] គ្រប់ឯកសារទាំងអស់ស្ថិតក្នុង: {movie_folder}")

                # Save source URL shortcut and metadata file if requested
                if save_url_enabled:
                    try:
                        webpage_url = (info.get("webpage_url") or url) if info else url
                        v_title = (info.get("title") or folder_name) if info else folder_name
                        uploader = (info.get("uploader") or info.get("channel") or "Unknown") if info else "Unknown"
                        v_dur = (info.get("duration") or 0) if info else 0

                        # 1. Standard Windows Internet Shortcut (.url) - double-clickable to open in browser
                        shortcut_path = os.path.join(movie_folder, f"{folder_name}.url")
                        with open(shortcut_path, "w", encoding="utf-8") as f:
                            f.write(f"[InternetShortcut]\nURL={webpage_url}\n")

                        # 2. Comprehensive archival text file (.txt)
                        txt_path = os.path.join(movie_folder, f"{folder_name}_source_url.txt")
                        with open(txt_path, "w", encoding="utf-8") as f:
                            f.write("=" * 80 + "\n")
                            f.write("🎥 VIDEO SOURCE INFORMATION / ព័ត៌មានប្រភពវីដេអូដើម\n")
                            f.write("=" * 80 + "\n")
                            f.write(f"📌 Original URL   : {webpage_url}\n")
                            f.write(f"🎬 Video Title    : {v_title}\n")
                            f.write(f"👤 Channel/Author : {uploader}\n")
                            f.write(f"⏱ Duration       : {format_timestamp(v_dur)} ({v_dur}s)\n")
                            f.write(f"📊 Quality Preset : {quality_label}\n")
                            f.write(f"💾 Download Date  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"📁 Local Folder   : {movie_folder}\n")
                            f.write(f"🎞 Video File     : {v_name}\n")
                            if downloaded_srt:
                                f.write(f"📄 Subtitle File  : {os.path.basename(downloaded_srt)}\n")
                            f.write("=" * 80 + "\n")
                            f.write(f"💡 ចំណាំ: អ្នកអាចចុច double-click លើ file \"{os.path.basename(shortcut_path)}\" ដើម្បីបើក Link នេះក្នុង Browser ភ្លាមៗ!\n")
                            f.write("=" * 80 + "\n")

                        self.log(f"🔗 [Source Link] បានរក្សាទុក Link ប្រភព: {os.path.basename(shortcut_path)} និង {os.path.basename(txt_path)}")
                    except Exception as ex:
                        self.log(f"⚠️ [Warning] មិនអាចរក្សាទុក URL shortcut: {ex}")

                def _show_success():
                    self.lbl_prog_title.setText(f"🎉 Download Complete: {v_name} ({sz_str})")
                    self.prog_bar.setValue(100)

                self.run_on_main(_show_success)

                # 5. Auto open in Movie Studio if requested
                if auto_open and downloaded_video and self.on_open_video_in_studio:
                    self.log(f"🎬 [Studio] បើកវីដេអូ {v_name} ចូលក្នុង Movie Studio...")
                    self.run_on_main(lambda: self.on_open_video_in_studio(downloaded_video))

            except Exception as e:
                err_msg = strip_ansi(str(e))
                if "Fresh cookies" in err_msg or ("403" in err_msg and "douyin" in url.lower()):
                    self.log("⚠️ [Douyin Notice] សូមចុចប៊ូតុង '🌐 Grab from Browser (Auto)' នៅជួរ Cookies ខាងលើ ដើម្បីចាប់យក Token Douyin ស្វ័យប្រវត្ត មិនបាច់ប្រើ Extension ឡើយ!")
                def _show_fail():
                    self.lbl_prog_title.setText("❌ Download failed")
                self.run_on_main(_show_fail)

            finally:
                self.is_downloading = False
                def _reset():
                    self.btn_download.setEnabled(True)
                    self.btn_download_open.setEnabled(True)
                    self.btn_stop.setEnabled(False)
                self.run_on_main(_reset)

        threading.Thread(target=worker, daemon=True).start()

    def stop_download(self):
        self.cancel_download = True
        self.log("⏹️ [Downloader] បានបញ្ឈប់ការទាញយក (Cancelled)")

    def _progress_hook(self, d: dict):
        if self.cancel_download:
            raise Exception("Cancelled by user")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            down = d.get("downloaded_bytes") or 0
            pct = int((down / max(1, total)) * 100)
            spd = (d.get("speed") or 0) / (1024 * 1024)

            def _update():
                self.prog_bar.setValue(pct)
                self.lbl_prog_title.setText(f"⚡ Downloading: {pct}% ({spd:.1f} MB/s)")
            self.run_on_main(_update)
