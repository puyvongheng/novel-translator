"""
Video Downloader View Component for PyQt6 / PySide6 Desktop Studio
Modern Turbo Downloader with:
1. Built-in Media Browser & Smart Video Sniffer (auto-detects video URLs while browsing)
2. Format Selection: Video (MP4, MKV, WebM), Audio (MP3 320k, M4A, WAV), Subtitles Only (SRT)
3. Dynamic Quality Selection with accurate MB / GB file sizes and FPS across all resolutions (4K, 2K, 1080p 60fps, 720p, 480p, 360p)
4. Multi-connection acceleration, live diagnostics console, automatic cookie handling, and one-folder-per-movie organization.
"""

import os
import re
import ssl
import json
import time
import shutil
import subprocess
import urllib.request
import threading
from datetime import datetime
from typing import Optional

from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit, 
    QComboBox, QProgressBar, QGroupBox, QPlainTextEdit, QFileDialog, 
    QMessageBox, Qt, QTimer, Signal, QCheckBox, QPixmap, QImage,
    QSplitter, QFrame, QScrollArea, QMenu,
    QTableWidget, QTableWidgetItem, QHeaderView, QRadioButton, QButtonGroup, QAbstractItemView,
    QPainter, QColor, QBrush, QPen, QPainterPath, QSizePolicy, QLinearGradient
)
from utils import format_timestamp
from ui_v_PyQt6.components.downloader.media_browser_dialog import MediaBrowserDialog, format_duration_str, SnifferWebEnginePage
from ui_v_PyQt6.components.downloader.cookie_grabber_dialog import CookieGrabberDialog

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from PySide6.QtCore import QUrl, QEventLoop
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
    WEBENGINE_AVAILABLE = True
except ImportError:
    try:
        from PyQt6.QtCore import QUrl, QEventLoop
        from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineUrlRequestInterceptor
        WEBENGINE_AVAILABLE = True
    except ImportError:
        WEBENGINE_AVAILABLE = False



from services.downloader import (
    DownloaderService,
    DownloadProgress,
    get_ffmpeg_binary_path,
    strip_ansi,
    normalize_video_url,
    sanitize_folder_name,
    get_custom_referer,
    download_cover_image,
    unwrap_spade
)


def get_rounded_pixmap(pixmap: QPixmap, radius: int = 8) -> QPixmap:
    """Helper to clip a QPixmap with smooth rounded corners."""
    if pixmap.isNull():
        return pixmap
    rounded = QPixmap(pixmap.size())
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return rounded


class ResponsiveGridContainer(QWidget):
    """Container widget that auto-calculates dynamic responsive columns on panel resize."""
    sig_resized = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_cols = 5

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.width()
        if w > 0:
            if w < 240:
                cols = 3
            elif w < 315:
                cols = 4
            elif w < 440:
                cols = 5
            elif w < 540:
                cols = 6
            else:
                cols = max(6, min(10, w // 75))
            if cols != self._last_cols:
                self._last_cols = cols
                self.sig_resized.emit(cols)


class EpisodeGridTile(QPushButton):
    """
    Ultra-Modern Responsive Short Drama Episode Tile:
    - Flexible width expanding responsively to panel resize
    - Bigger button: height 50px, min-width 44px, 10px rounded corners
    - Modern Dark Theme with rich gradients and subtle borders
    - Live Equalizer Animation: 3 animated bouncing audio wave bars when active
    - VIP / Lock Indicator: luxury crimson/red badge & padlock icon for locked episodes
    """
    doubleClicked = Signal(int)

    _anim_timer = None
    _anim_frame = 0
    _active_tiles = set()

    @classmethod
    def _register_active_tile(cls, tile):
        cls._active_tiles.add(tile)
        if cls._anim_timer is None:
            cls._anim_timer = QTimer()
            cls._anim_timer.setInterval(150)
            cls._anim_timer.timeout.connect(cls._on_timer_tick)
            cls._anim_timer.start()

    @classmethod
    def _unregister_active_tile(cls, tile):
        cls._active_tiles.discard(tile)
        if not cls._active_tiles and cls._anim_timer is not None:
            cls._anim_timer.stop()
            cls._anim_timer = None

    @classmethod
    def _on_timer_tick(cls):
        cls._anim_frame = (cls._anim_frame + 1) % 4
        for t in list(cls._active_tiles):
            t.update()

    def __init__(self, ep_num: int, is_locked: bool = False, parent=None):
        super().__init__(parent)
        self.ep_num = ep_num
        self.is_active = False
        self.is_locked = is_locked
        self.setMinimumSize(42, 44)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setActive(self, active: bool):
        if self.is_active != active:
            self.is_active = active
            if active:
                EpisodeGridTile._register_active_tile(self)
            else:
                EpisodeGridTile._unregister_active_tile(self)
            self.update()

    def setLocked(self, locked: bool):
        if self.is_locked != locked:
            self.is_locked = locked
            self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        self.doubleClicked.emit(self.ep_num - 1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        r = 10
        is_hover = self.underMouse()

        if self.is_active:
            grad = QLinearGradient(0, 0, 0, rect.height())
            if self.is_locked:
                grad.setColorAt(0.0, QColor("#4c0519"))
                grad.setColorAt(1.0, QColor("#220710"))
                border_color = QColor("#f43f5e")
                text_color = QColor("#ffffff")
            else:
                grad.setColorAt(0.0, QColor("#351c11"))
                grad.setColorAt(1.0, QColor("#221109"))
                border_color = QColor("#f97316")
                text_color = QColor("#ff8a3d")
            bg_brush = QBrush(grad)
            pen = QPen(border_color, 1.6)
        elif is_hover:
            if self.is_locked:
                bg_brush = QBrush(QColor("#331823"))
                border_color = QColor("#f43f5e")
                text_color = QColor("#ffffff")
            else:
                bg_brush = QBrush(QColor("#2f343e"))
                border_color = QColor("#60a5fa")
                text_color = QColor("#ffffff")
            pen = QPen(border_color, 1.4)
        elif self.is_locked:
            # Sleek modern locked tile with red accent
            bg_brush = QBrush(QColor("#23181f"))
            pen = QPen(QColor("#b91c1c"), 1.2)
            text_color = QColor("#fca5a5")
        else:
            bg_brush = QBrush(QColor("#1f2229"))
            pen = QPen(QColor("#313642"), 1.0)
            text_color = QColor("#e2e8f0")

        painter.setBrush(bg_brush)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, r, r)

        font = self.font()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(text_color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.ep_num))

        # Padlock Icon for locked episodes (Vibrant red/rose matching DramaBox UI)
        if self.is_locked:
            lock_color = QColor("#f43f5e" if (self.is_active or is_hover) else "#ef4444")
            # If active, shift lock slightly left to make room for audio wave bars
            lx = rect.right() - (24 if self.is_active else 14)
            ly = rect.top() + 6
            # Lock shackle (curved arch)
            painter.setPen(QPen(lock_color, 1.3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(lx + 2, ly, 6, 6, 0, 180 * 16)
            # Lock body (rounded rect)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(lock_color))
            painter.drawRoundedRect(lx + 1, ly + 3, 8, 7, 1, 1)

        # Live Equalizer Wave Animation when Active
        if self.is_active:
            frames = [(4, 9, 6), (7, 4, 8), (9, 7, 3), (5, 10, 5)]
            h1, h2, h3 = frames[EpisodeGridTile._anim_frame]
            wave_color = QColor("#f43f5e" if self.is_locked else "#f97316")
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(wave_color))
            rx = rect.right() - 12
            ry = rect.top() + 7
            max_h = 10
            painter.drawRoundedRect(rx, ry + (max_h - h1), 2, h1, 1, 1)
            painter.drawRoundedRect(rx + 3, ry + (max_h - h2), 2, h2, 1, 1)
            painter.drawRoundedRect(rx + 6, ry + (max_h - h3), 2, h3, 1, 1)

        painter.end()


class VideoDownloaderView(QWidget):
    """
    Modern Video Downloader & Media Studio:
    - Built-in Chromium Browser with Active Video Sniffer (auto-detects video while browsing)
    - Target Format Selection: Video (MP4, MKV, WebM), Audio (MP3 320k, M4A, WAV), Subtitles Only (SRT)
    - Rich Quality Selector: 4K, 2K, 1080p (60fps), 720p, 480p, 360p with live calculated sizes
    - Multi-Thread Turbo Download Engine with FFmpeg stream remuxing
    - Dedicated live diagnostics console
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
        self.is_playlist = False
        self.playlist_entries = []
        self.selected_playlist_index = 0

        self._init_ui()
        self._auto_detect_cookies(silent=True)

        # Initialize decoupled DownloaderService
        self.downloader_service = DownloaderService(
            on_log=self.log,
            on_progress=self._on_service_progress
        )

        # Log FFmpeg engine status
        ff = get_ffmpeg_binary_path()
        if ff:
            self.log(f"🎬 [FFmpeg Engine] រកឃើញ FFmpeg ដំណើរការល្អ: {os.path.basename(ff)}")
        else:
            self.log("⚠️ [FFmpeg Engine] មិនទាន់រកឃើញ FFmpeg ឡើយ (ការទាញយក 1080p/4K អាចត្រូវការ ffmpeg)")

    def _handle_dispatch(self, fn):
        try:
            fn()
        except Exception as e:
            print(f"Downloader GUI dispatch error: {e}")

    def run_on_main(self, fn):
        self.sig_dispatch.emit(fn)

    def run_on_main_sync(self, fn, timeout_sec=15):
        if threading.current_thread() is threading.main_thread():
            return fn()

        res = [None]
        err = [None]
        evt = threading.Event()

        def _wrapper():
            try:
                res[0] = fn()
            except Exception as e:
                err[0] = e
            finally:
                evt.set()

        self.sig_dispatch.emit(_wrapper)
        evt.wait(timeout=timeout_sec)
        if err[0]:
            raise err[0]
        return res[0]

    def _on_service_progress(self, p: DownloadProgress):
        """Bridge service callback into Qt GUI thread."""
        lbl_sub = f" ({p.sublabel})" if p.sublabel else ""
        self.run_on_main(lambda: (
            self.prog_bar.setValue(int(p.percent)),
            self.lbl_prog_stats.setText(f"Part [{p.part_idx}/{p.total_parts}]{lbl_sub}: {int(p.percent)}% ({p.speed_mb:.2f} MB/s)")
        ))

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setOpaqueResize(True)

        # ========================================================
        # 1. LEFT COLUMN: VIDEO METADATA & SOURCE PREVIEW
        # ========================================================
        self.card_prev = QFrame()
        self.card_prev.setObjectName("card_prev")
        self.card_prev.setStyleSheet("""
            QFrame#card_prev {
                background-color: #141416;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        card_main_layout = QVBoxLayout(self.card_prev)
        card_main_layout.setContentsMargins(8, 8, 8, 8)
        card_main_layout.setSpacing(8)

        # Scroll Area to handle any content length cleanly
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(scroll_content)
        left_layout.setContentsMargins(4, 4, 4, 4)
        left_layout.setSpacing(12)

        # ── 1. TOP HEADER: POSTER + TITLE + CATEGORY BADGES ──
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        # Smart Auto-Fit Video Thumbnail (Auto-adapts to 16:9 Landscape YouTube, 9:16 Drama Poster, or Square)
        self.lbl_thumb = QLabel("No Cover\n(ចុច Preview Info)")
        self.lbl_thumb.setFixedSize(110, 120)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setScaledContents(False)
        self.lbl_thumb.setStyleSheet(
            "background-color: #1c1c1f; border: 1px solid #27272a; border-radius: 8px; color: #71717a; font-size: 10px; padding: 2px;"
        )
        header_layout.addWidget(self.lbl_thumb, 0, Qt.AlignmentFlag.AlignTop)

        # Right Metadata Column
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 2, 0, 2)
        info_col.setSpacing(6)

        # Video / Drama Title (Bold, modern white)
        self.lbl_prev_title = QLabel("Video Title: --")
        self.lbl_prev_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; line-height: 1.25;")
        self.lbl_prev_title.setWordWrap(True)
        self.lbl_prev_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info_col.addWidget(self.lbl_prev_title)

        # Platform Brand Badge + Category Tags Pill Row
        self.tags_widget = QWidget()
        self.tags_widget.setStyleSheet("background: transparent;")
        self.tags_layout = QHBoxLayout(self.tags_widget)
        self.tags_layout.setContentsMargins(0, 2, 0, 2)
        self.tags_layout.setSpacing(6)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Real Platform Logo Badge (e.g. YouTube, Hongguo, Bilibili...)
        self.badge_platform = QFrame()
        self.badge_platform.setObjectName("badge_platform")
        self.badge_platform.setStyleSheet("""
            QFrame#badge_platform {
                background-color: #1e1e24;
                border: 1px solid #2e2e38;
                border-radius: 4px;
                padding: 2px 6px;
            }
        """)
        bp_layout = QHBoxLayout(self.badge_platform)
        bp_layout.setContentsMargins(4, 2, 6, 2)
        bp_layout.setSpacing(5)

        self.lbl_platform_icon = QLabel()
        self.lbl_platform_icon.setFixedSize(16, 16)
        self.lbl_platform_icon.setScaledContents(True)
        bp_layout.addWidget(self.lbl_platform_icon)

        self.lbl_platform_name = QLabel("Web")
        self.lbl_platform_name.setStyleSheet("color: #f4f4f5; font-size: 11px; font-weight: bold;")
        bp_layout.addWidget(self.lbl_platform_name)

        self.badge_platform.setVisible(False)
        self.tags_layout.addWidget(self.badge_platform)
        info_col.addWidget(self.tags_widget)

        # Metadata rows (Creator, duration, CC, sizes)
        self.lbl_prev_info = QLabel("Duration: -- | Creator: --")
        self.lbl_prev_info.setStyleSheet("color: #71717a; font-size: 11px;")
        self.lbl_prev_info.setWordWrap(True)
        info_col.addWidget(self.lbl_prev_info)

        self.lbl_prev_cc = QLabel("Subtitles / CC: --")
        self.lbl_prev_cc.setStyleSheet("color: #34d399; font-weight: bold; font-size: 10px;")
        self.lbl_prev_cc.setWordWrap(True)
        info_col.addWidget(self.lbl_prev_cc)

        self.lbl_prev_size = QLabel("Estimated Sizes: --")
        self.lbl_prev_size.setStyleSheet("color: #38bdf8; font-size: 10px;")
        self.lbl_prev_size.setWordWrap(True)
        info_col.addWidget(self.lbl_prev_size)

        info_col.addStretch()
        header_layout.addLayout(info_col, 1)
        left_layout.addWidget(header_widget)

        # Play / Watch Video Stream Button
        self.btn_preview_play = QPushButton("▶️ Play Stream / ចាក់មើលវីដេអូផ្ទាល់")
        self.btn_preview_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_preview_play.setToolTip("ចាក់វីដេអូ ឬភាគដែលបានជ្រើសរើសផ្ទាល់ជាមួយ FFplay / Built-in Player (Bypass Error)")
        self.btn_preview_play.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_preview_play.setMinimumWidth(0)
        self.btn_preview_play.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 10px;
                border: 1px solid #7c3aed;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #6d28d9;
            }
        """)
        self.btn_preview_play.clicked.connect(self._play_current_preview_video)
        left_layout.addWidget(self.btn_preview_play)

        # ── 2. SYNOPSIS / 简介 SECTION (Modern Seamless Streaming Layout) ──
        self.desc_box = QWidget()
        self.desc_box.setStyleSheet("background: transparent;")
        desc_layout = QVBoxLayout(self.desc_box)
        desc_layout.setContentsMargins(0, 2, 0, 2)
        desc_layout.setSpacing(4)

        lbl_desc_heading = QLabel("简介")
        lbl_desc_heading.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 15px;")
        desc_layout.addWidget(lbl_desc_heading)

        self.lbl_desc_text = QLabel("无简介")
        self.lbl_desc_text.setStyleSheet("color: #8e8e93; font-size: 12px; line-height: 1.45;")
        self.lbl_desc_text.setWordWrap(True)
        self.lbl_desc_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lbl_desc_text.setOpenExternalLinks(False)
        self.lbl_desc_text.linkActivated.connect(self._on_desc_link_clicked)
        desc_layout.addWidget(self.lbl_desc_text)
        self.desc_box.setVisible(False)
        left_layout.addWidget(self.desc_box)

        # ── 3. EPISODES SELECTOR / 选集 SECTION (Grid + List Switcher) ──
        self.episodes_box = QWidget()
        self.episodes_box.setObjectName("episodes_box")
        self.episodes_box.setStyleSheet("background: transparent;")
        ep_box_layout = QVBoxLayout(self.episodes_box)
        ep_box_layout.setContentsMargins(0, 4, 0, 4)
        ep_box_layout.setSpacing(6)

        # Header with Title and Mode Switcher (Grid vs List)
        ep_top_bar = QHBoxLayout()
        ep_top_bar.setContentsMargins(0, 0, 0, 0)
        self.lbl_episodes_title = QLabel("选集")
        self.lbl_episodes_title.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 16px;")
        ep_top_bar.addWidget(self.lbl_episodes_title, 1)

        self.btn_view_grid = QPushButton("🔲 Grid")
        self.btn_view_grid.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_grid.clicked.connect(lambda: self._set_episode_view_mode("grid"))
        ep_top_bar.addWidget(self.btn_view_grid)

        self.btn_view_list = QPushButton("📋 List")
        self.btn_view_list.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_list.clicked.connect(lambda: self._set_episode_view_mode("list"))
        ep_top_bar.addWidget(self.btn_view_list)
        ep_box_layout.addLayout(ep_top_bar)

        # Grid View Wrapper
        self.ep_grid_wrapper = QWidget()
        ep_grid_wrap_layout = QVBoxLayout(self.ep_grid_wrapper)
        ep_grid_wrap_layout.setContentsMargins(0, 0, 0, 0)
        ep_grid_wrap_layout.setSpacing(6)

        # Range Tabs Bar (1-15, 16-30, 31-45, 46-60, 61-75...)
        self.range_tabs_scroll = QScrollArea()
        self.range_tabs_scroll.setFixedHeight(34)
        self.range_tabs_scroll.setWidgetResizable(True)
        self.range_tabs_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.range_tabs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.range_tabs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.range_tabs_scroll.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.range_tabs_scroll.setMinimumWidth(0)
        self.range_tabs_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:horizontal { height: 4px; background: #18181b; }
            QScrollBar::handle:horizontal { background: #3f3f46; border-radius: 2px; }
        """)
        range_tabs_container = QWidget()
        self.range_tabs_layout = QHBoxLayout(range_tabs_container)
        self.range_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.range_tabs_layout.setSpacing(8)
        self.range_tabs_scroll.setWidget(range_tabs_container)
        ep_grid_wrap_layout.addWidget(self.range_tabs_scroll)

        # Responsive Square Tile Grid (dynamic columns on resize)
        self.ep_grid_container = ResponsiveGridContainer()
        self.ep_grid_layout = QGridLayout(self.ep_grid_container)
        self.ep_grid_layout.setContentsMargins(0, 2, 0, 2)
        self.ep_grid_layout.setSpacing(6)
        self.ep_grid_container.sig_resized.connect(self._relayout_grid_tiles)
        ep_grid_wrap_layout.addWidget(self.ep_grid_container)

        ep_box_layout.addWidget(self.ep_grid_wrapper)

        # ── PLAYLIST ITEMS LIST SECTION (Preserved Table View) ──
        self.playlist_box = QFrame()
        self.playlist_box.setObjectName("playlist_box")
        self.playlist_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.playlist_box.setMinimumWidth(0)
        self.playlist_box.setStyleSheet("""
            QFrame#playlist_box {
                background-color: #0b1120;
                border: 1px solid #0284c7;
                border-radius: 6px;
            }
        """)
        pl_layout = QVBoxLayout(self.playlist_box)
        pl_layout.setContentsMargins(6, 6, 6, 6)
        pl_layout.setSpacing(6)

        pl_header = QHBoxLayout()
        self.lbl_playlist_title = QLabel("📋 Playlist Items (0):")
        self.lbl_playlist_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        pl_header.addWidget(self.lbl_playlist_title, 1)

        self.btn_pl_select_all = QPushButton("✅ All")
        self.btn_pl_select_all.setToolTip("ជ្រើសរើសវីដេអូទាំងអស់ក្នុង Playlist")
        self.btn_pl_select_all.setFixedHeight(22)
        self.btn_pl_select_all.setStyleSheet("background-color: #0369a1; color: white; font-size: 10px; font-weight: bold; padding: 2px 6px; border-radius: 3px;")
        self.btn_pl_select_all.clicked.connect(self._select_all_playlist_items)
        pl_header.addWidget(self.btn_pl_select_all)

        self.btn_pl_deselect_all = QPushButton("⬜ None")
        self.btn_pl_deselect_all.setToolTip("ដោះការជ្រើសរើសទាំងអស់")
        self.btn_pl_deselect_all.setFixedHeight(22)
        self.btn_pl_deselect_all.setStyleSheet("background-color: #334155; color: #94a3b8; font-size: 10px; padding: 2px 6px; border-radius: 3px;")
        self.btn_pl_deselect_all.clicked.connect(self._deselect_all_playlist_items)
        pl_header.addWidget(self.btn_pl_deselect_all)

        self.btn_pl_copy_all = QPushButton("📋 Copy All URLs")
        self.btn_pl_copy_all.setToolTip("ចម្លង Link វីដេអូទាំងអស់ក្នុង Playlist ទៅកាន់ Clipboard")
        self.btn_pl_copy_all.setFixedHeight(22)
        self.btn_pl_copy_all.setStyleSheet("background-color: #4338ca; color: #c7d2fe; font-size: 10px; font-weight: bold; padding: 2px 8px; border-radius: 3px;")
        self.btn_pl_copy_all.clicked.connect(self._copy_all_playlist_urls)
        pl_header.addWidget(self.btn_pl_copy_all)

        self.btn_pl_export = QPushButton("💾 Export")
        self.btn_pl_export.setToolTip("រក្សាទុក Link ទាំងអស់ជាឯកសារ .txt")
        self.btn_pl_export.setFixedHeight(22)
        self.btn_pl_export.setStyleSheet("background-color: #1e293b; color: #94a3b8; font-size: 10px; padding: 2px 8px; border-radius: 3px;")
        self.btn_pl_export.clicked.connect(self._export_all_playlist_urls)
        pl_header.addWidget(self.btn_pl_export)

        pl_layout.addLayout(pl_header)

        # Playlist Items Table in Preview
        self.table_playlist = QTableWidget()
        self.table_playlist.setColumnCount(3)
        self.table_playlist.setHorizontalHeaderLabels(["# / Select", "Video / Episode Title", "Duration"])
        self.table_playlist.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_playlist.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_playlist.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_playlist.verticalHeader().setVisible(False)
        self.table_playlist.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_playlist.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_playlist.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_playlist.customContextMenuRequested.connect(self._show_playlist_context_menu)
        self.table_playlist.setFixedHeight(200)
        self.table_playlist.setStyleSheet("""
            QTableWidget {
                background-color: #111827;
                color: #f1f5f9;
                gridline-color: #1f2937;
                font-size: 11px;
                border: 1px solid #1f2937;
                border-radius: 4px;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: bold;
                padding: 3px;
                border: 1px solid #334155;
            }
            QTableWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.table_playlist.itemClicked.connect(self._on_playlist_item_clicked)
        self.table_playlist.itemChanged.connect(self._on_playlist_item_changed)
        pl_layout.addWidget(self.table_playlist)

        self.lbl_pl_summary = QLabel("💡 ចុចលើវីដេអូណាមួយដើម្បី Preview មើលរូបភាព & ព័ត៌មានលម្អិត")
        self.lbl_pl_summary.setStyleSheet("color: #a7f3d0; font-size: 10px;")
        self.lbl_pl_summary.setWordWrap(True)
        pl_layout.addWidget(self.lbl_pl_summary)

        ep_box_layout.addWidget(self.playlist_box)
        left_layout.addWidget(self.episodes_box)

        self.episodes_box.setVisible(False)
        self._set_episode_view_mode("grid")

        self.lbl_source_url = None
        left_layout.addStretch()

        scroll_area.setWidget(scroll_content)
        card_main_layout.addWidget(scroll_area)

        self.splitter.addWidget(self.card_prev)

        # ========================================================
        # 2. RIGHT COLUMN: DOWNLOAD SETTINGS, ACTIONS, PROGRESS & LOGS
        # ========================================================
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # GROUP 1: Video URL & Format Settings
        group_top = QFrame()
        group_top.setObjectName("group_top")
        group_top.setStyleSheet("""
            QFrame#group_top {
                background-color: #141416;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
        """)
        t_layout = QVBoxLayout(group_top)
        t_layout.setContentsMargins(10, 10, 10, 10)
        t_layout.setSpacing(8)

        # URL Row with Browser Sniffer Button
        url_row = QHBoxLayout()
        url_row.setSpacing(6)
        url_row.addWidget(QLabel("Video Link:"))
        self.entry_url = QLineEdit()
        self.entry_url.setPlaceholderText("Paste YouTube, TikTok, Douyin, Facebook, Bilibili or any link here...")
        self.entry_url.returnPressed.connect(self.start_preview_info)
        url_row.addWidget(self.entry_url, 1)

        btn_paste = QPushButton("Paste")
        btn_paste.clicked.connect(self._paste_url)
        url_row.addWidget(btn_paste)

        # Built-in Browser Sniffer Button
        btn_open_sniffer = QPushButton("🌐 Open Browser (Sniffer)")
        btn_open_sniffer.setToolTip("បើក Built-in Browser រុករកក្នុង YouTube/TikTok/Facebook ហើយចាប់យក Video URL ស្វ័យប្រវត្ត")
        btn_open_sniffer.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #026597);
                color: #ffffff;
                font-weight: bold;
                padding: 5px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #0369a1;
            }
        """)
        btn_open_sniffer.clicked.connect(self._open_media_browser)
        url_row.addWidget(btn_open_sniffer)

        btn_preview = QPushButton("Preview Info")
        btn_preview.setObjectName("btn_primary")
        btn_preview.clicked.connect(self.start_preview_info)
        url_row.addWidget(btn_preview)
        t_layout.addLayout(url_row)

        # Row 2: Format Type (MP4, MKV, WebM, MP3, M4A, WAV, Subtitles Only)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(8)

        fmt_row.addWidget(QLabel("Format (ទម្រង់):"))
        self.combo_format_type = QComboBox()
        self.combo_format_type.setMinimumWidth(230)
        self.combo_format_type.addItems([
            "🎬 Video: MP4 (H.264 / AAC - Universal + Cover)",
            "🎬 Video: MKV (Original High Quality + Cover)",
            "🎬 Video: WebM (VP9 / AV1 Stream)",
            "🎵 Audio: MP3 (320 kbps High Quality)",
            "🎵 Audio: M4A (Original AAC Stream - Fast)",
            "🎵 Audio: WAV (Studio Lossless 16-bit PCM)",
            "🖼️ Cover Only: JPG / PNG (ទាញយករូប Poster / Cover តែប៉ុណ្ណោះ)",
            "📝 Subtitles Only: SRT (ទាញយក Subtitles តែប៉ុណ្ណោះ)"
        ])
        self.combo_format_type.currentIndexChanged.connect(self._on_format_type_changed)
        fmt_row.addWidget(self.combo_format_type, 1)

        fmt_row.addWidget(QLabel("Quality (គុណភាព / ទំហំ):"))
        self.combo_quality = QComboBox()
        self.combo_quality.setMinimumWidth(250)
        # Default rich preset list before preview
        self.combo_quality.addItems([
            "🌟 Best Available (Auto Highest Quality)",
            "🎬 4K (2160p Ultra HD)",
            "🎬 2K (1440p Quad HD)",
            "🎬 1080p (Full HD / 60fps)",
            "🎬 720p (HD Standard)",
            "🎬 480p (SD Standard)",
            "🎬 360p (Fast / Data Saver)",
            "🎵 MP3 Audio (320 kbps High Quality)",
            "🎵 M4A Audio (Original Stream)",
            "🎵 WAV Audio (Studio Lossless)"
        ])
        fmt_row.addWidget(self.combo_quality, 1)
        t_layout.addLayout(fmt_row)

        # Row 3: Cover, Subtitles, Language, Turbo
        opt_row = QHBoxLayout()
        opt_row.setSpacing(8)

        self.check_download_cover = QCheckBox("ទាញយករូប Cover (.jpg)")
        self.check_download_cover.setChecked(True)
        self.check_download_cover.setToolTip("ទាញយករូប Cover / Poster គុណភាពខ្ពស់ (.jpg) ដាក់ក្នុង Folder រឿង និងបង្កប់ក្នុងវីដេអូ")
        self.check_download_cover.setStyleSheet("color: #f472b6; font-weight: bold;")
        opt_row.addWidget(self.check_download_cover)

        self.check_download_subs = QCheckBox("ទាញយក Subtitles / SRT")
        self.check_download_subs.setChecked(True)
        self.check_download_subs.setToolTip("ទាញយកឯកសារ Subtitle SRT ដាក់ក្នុង Folder តែមួយជាមួយវីដេអូ")
        opt_row.addWidget(self.check_download_subs)

        self.combo_sub_lang = QComboBox()
        self.combo_sub_lang.setMinimumWidth(150)
        self.combo_sub_lang.addItems(["Auto / ភាសាដើម", "Chinese (zh)", "English (en)", "All Subtitles", "No Subtitles"])
        opt_row.addWidget(self.combo_sub_lang)

        opt_row.addWidget(QLabel("Turbo:"))
        self.combo_threads = QComboBox()
        self.combo_threads.addItems(["16 Threads (Max)", "8 Threads", "4 Threads", "Single Stream"])
        opt_row.addWidget(self.combo_threads)
        opt_row.addStretch()
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

        btn_grab_browser = QPushButton("🌐 Grab Cookies (Browser)")
        btn_grab_browser.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold;")
        btn_grab_browser.setToolTip("បើក Built-in Browser ដើម្បីចាប់យក Cookies ពី Douyin/TikTok ដោយស្វ័យប្រវត្ត")
        btn_grab_browser.clicked.connect(self._open_cookie_grabber)
        cookies_row.addWidget(btn_grab_browser)
        t_layout.addLayout(cookies_row)

        # Proxy / Fake VPN Geo-Bypass Row
        proxy_row = QHBoxLayout()
        proxy_row.addWidget(QLabel("Proxy / VPN Bypass:"))
        self.entry_proxy = QLineEdit()
        self.entry_proxy.setPlaceholderText("Optional Proxy (e.g. socks5://127.0.0.1:1080 or http://127.0.0.1:7890)")
        proxy_row.addWidget(self.entry_proxy, 1)

        self.check_fake_vpn = QCheckBox("🛡️ Auto Fake IP / Geo-Bypass (China/Global)")
        self.check_fake_vpn.setChecked(True)
        self.check_fake_vpn.setToolTip("Automatically spoof Mainland China / Local IP headers (X-Forwarded-For) to bypass regional restrictions on MangoTV, iQiyi, Bilibili, Douyin, etc.")
        self.check_fake_vpn.setStyleSheet("color: #a7f3d0; font-weight: bold;")
        proxy_row.addWidget(self.check_fake_vpn)
        t_layout.addLayout(proxy_row)

        # URL Source Option Checkbox
        opt_save_row = QHBoxLayout()
        self.check_save_url = QCheckBox("Save Source URL (រក្សាទុក Link ប្រភពវីដេអូជា file .url និង .txt ដើម្បីងាយស្រួលរកប្រភព)")
        self.check_save_url.setChecked(True)
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

        # Playlist Download Mode Selector (Visible when URL is a playlist)
        self.group_pl_mode = QFrame()
        self.group_pl_mode.setStyleSheet("background-color: #0f172a; border: 1px solid #0284c7; border-radius: 6px; padding: 4px;")
        pl_mode_layout = QHBoxLayout(self.group_pl_mode)
        pl_mode_layout.setContentsMargins(6, 4, 6, 4)
        pl_mode_layout.setSpacing(10)

        lbl_mode = QLabel("📋 Download Mode:")
        lbl_mode.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        pl_mode_layout.addWidget(lbl_mode)

        self.radio_pl_all = QRadioButton("ទាញយកទាំងអស់ (All)")
        self.radio_pl_all.setChecked(True)
        self.radio_pl_all.setStyleSheet("color: #f1f5f9; font-size: 11px; font-weight: bold;")
        self.radio_pl_all.toggled.connect(self._update_download_button_text)
        pl_mode_layout.addWidget(self.radio_pl_all)

        self.radio_pl_selected = QRadioButton("ទាញយកតែភាគដែល Check (Selected)")
        self.radio_pl_selected.setStyleSheet("color: #f1f5f9; font-size: 11px;")
        self.radio_pl_selected.toggled.connect(self._update_download_button_text)
        pl_mode_layout.addWidget(self.radio_pl_selected)

        self.radio_pl_single = QRadioButton("ទាញយកតែវីដេអូមួយនេះ (Single)")
        self.radio_pl_single.setStyleSheet("color: #f1f5f9; font-size: 11px;")
        self.radio_pl_single.toggled.connect(self._update_download_button_text)
        pl_mode_layout.addWidget(self.radio_pl_single)

        pl_mode_layout.addStretch()
        pr_layout.addWidget(self.group_pl_mode)
        self.group_pl_mode.setVisible(False)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_download = QPushButton("Download Video / Audio")
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

        # Resilient aliases for progress & stats labels
        self.progress_bar = self.prog_bar
        self.lbl_prog_details = self.lbl_prog_stats

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

        right_layout.addWidget(group_log)

        self.card_prev.setMinimumWidth(320)
        self.splitter.addWidget(right_container)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 6)
        self.splitter.setSizes([380, 720])
        main_layout.addWidget(self.splitter)

    def log(self, msg: str):
        def _do():
            ts = datetime.now().strftime("%H:%M:%S")
            text = f"[{ts}] {msg}"
            self.txt_logs.appendPlainText(text)
            self.txt_logs.ensureCursorVisible()
            if self.log_callback:
                self.log_callback(text)
        self.run_on_main(_do)

    # ------------------ BROWSER & SNIFFER INTEGRATION ------------------
    def _open_media_browser(self):
        """Opens built-in Chromium browser with active video sniffer."""
        url = self.entry_url.text().strip()
        initial_site = "https://www.youtube.com"
        if url and url.startswith("http"):
            initial_site = url
        elif url:
            if "tiktok" in url:
                initial_site = "https://www.tiktok.com"
            elif "douyin" in url:
                initial_site = "https://www.douyin.com"
            elif "bilibili" in url:
                initial_site = "https://www.bilibili.com"
            elif "facebook" in url:
                initial_site = "https://www.facebook.com"
            elif "instagram" in url:
                initial_site = "https://www.instagram.com"

        proxy_val = getattr(self, "entry_proxy", None) and self.entry_proxy.text().strip()

        dlg = MediaBrowserDialog(
            parent=self,
            initial_url=initial_site,
            on_video_selected=self._on_video_sniffed,
            on_cookies_saved=self._on_cookies_grabbed,
            proxy=proxy_val
        )
        dlg.exec()

    def _on_video_sniffed(self, video_url: str, cookie_file: str = ""):
        """Callback when user clicks 'Download Video' from the built-in browser."""
        if not video_url:
            return
        clean_url = normalize_video_url(video_url)
        self.entry_url.setText(clean_url)
        if cookie_file and os.path.exists(cookie_file):
            self.entry_cookies.setText(cookie_file)
        self.log(f"🎯 [Browser Sniffer] ចាប់បាន Video URL: {clean_url}")
        # Automatically trigger Preview Info
        self.start_preview_info()

    def _open_cookie_grabber(self):
        """Opens cookie grabber browser dialog."""
        url = self.entry_url.text().strip()
        target_site = "https://www.douyin.com"
        if url and "tiktok.com" in url:
            target_site = "https://www.tiktok.com"
        elif url and "bilibili.com" in url:
            target_site = "https://www.bilibili.com"
        elif url and url.startswith("http"):
            target_site = url

        dlg = CookieGrabberDialog(
            parent=self,
            initial_url=target_site,
            on_cookies_saved=self._on_cookies_grabbed
        )
        dlg.exec()

    def _on_cookies_grabbed(self, cookie_file: str, total_count: int):
        if hasattr(self, "entry_cookies"):
            self.entry_cookies.setText(cookie_file)
        self.log(f"🎉 [Cookies] បានចាប់យក និងរក្សាទុក Cookies ចំនួន {total_count} ដោយជោគជ័យ!")

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

    def _on_format_type_changed(self, idx: int):
        """Adjusts quality dropdown based on whether user wants video, audio, or subtitles."""
        fmt_text = self.combo_format_type.currentText()
        if "Cover Only" in fmt_text or "Cover / Poster" in fmt_text:
            self.check_download_cover.setChecked(True)
            self.lbl_prog_title.setText("🖼️ Selected: Cover Image Only (JPG/PNG)")
        elif "Audio" in fmt_text:
            # Switch to audio options
            for i in range(self.combo_quality.count()):
                t = self.combo_quality.itemText(i)
                if "Audio" in t or "MP3" in t or "M4A" in t or "WAV" in t:
                    self.combo_quality.setCurrentIndex(i)
                    break
        elif "Subtitles Only" in fmt_text:
            self.check_download_subs.setChecked(True)
        else:
            # Video: select best or 1080p
            self.check_download_cover.setChecked(True)
            for i in range(self.combo_quality.count()):
                t = self.combo_quality.itemText(i)
                if "1080p" in t or "Best Available" in t:
                    self.combo_quality.setCurrentIndex(i)
                    break

    # ------------------ PLAYLIST PREVIEW CONTROLS ------------------
    def _select_all_playlist_items(self):
        self.table_playlist.blockSignals(True)
        for r in range(self.table_playlist.rowCount()):
            it = self.table_playlist.item(r, 0)
            if it:
                it.setCheckState(Qt.CheckState.Checked)
        self.table_playlist.blockSignals(False)
        self._update_download_button_text()

    def _deselect_all_playlist_items(self):
        self.table_playlist.blockSignals(True)
        for r in range(self.table_playlist.rowCount()):
            it = self.table_playlist.item(r, 0)
            if it:
                it.setCheckState(Qt.CheckState.Unchecked)
        self.table_playlist.blockSignals(False)
        self._update_download_button_text()

    def _copy_all_playlist_urls(self):
        """Grabs and copies all video URLs from the previewed playlist to clipboard."""
        entries = getattr(self, "playlist_entries", [])
        if not entries:
            QMessageBox.information(self, "No URLs", "មិនទាន់មានបញ្ជីវីដេអូត្រូវបាន Preview ទេ!")
            return
        
        urls = []
        for idx, e in enumerate(entries, 1):
            u = e.get("webpage_url") or e.get("url")
            if u:
                urls.append(u)
        
        if urls:
            from ui_v_PyQt6.qt_compat import QApplication
            QApplication.clipboard().setText("\n".join(urls))
            self.log(f"📋 [Clipboard] បានចម្លង {len(urls)} Video URLs ទៅកាន់ Clipboard ដោយជោគជ័យ!")
            self.lbl_pl_summary.setText(f"✅ បានចម្លង {len(urls)} Video URLs ទាំងអស់ទៅកាន់ Clipboard រួចរាល់!")
            QTimer.singleShot(3000, lambda: self.lbl_pl_summary.setText("💡 ចុចលើវីដេអូណាមួយដើម្បី Preview មើលរូបភាព & ព័ត៌មានលម្អិត"))

    def _export_all_playlist_urls(self):
        """Exports all previewed video URLs to a text file."""
        entries = getattr(self, "playlist_entries", [])
        if not entries:
            QMessageBox.information(self, "No URLs", "មិនទាន់មានបញ្ជីវីដេអូត្រូវបាន Preview ទេ!")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Video URLs", "playlist_urls.txt", "Text Files (*.txt);;All Files (*)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                for idx, e in enumerate(entries, 1):
                    u = e.get("webpage_url") or e.get("url") or ""
                    f.write(f"{u}\n")
            self.log(f"💾 [Export] បានរក្សាទុក {len(entries)} URLs ទៅក្នុងឯកសារ: {os.path.basename(path)}")

    def _show_playlist_context_menu(self, pos):
        """Context menu on right-click of playlist preview table."""
        menu = QMenu(self)
        sel_row = self.table_playlist.currentRow()
        entries = getattr(self, "playlist_entries", [])

        if 0 <= sel_row < len(entries):
            e = entries[sel_row]
            sel_u = e.get("webpage_url") or e.get("url") or ""
            act_sel = menu.addAction(f"📋 Copy Video #{sel_row+1} URL")
            def _copy_cur():
                from ui_v_PyQt6.qt_compat import QApplication
                QApplication.clipboard().setText(sel_u)
                self.log(f"📋 [Clipboard] បានចម្លង URL ភាគ #{sel_row+1}: {sel_u}")
            act_sel.triggered.connect(_copy_cur)

        if entries:
            act_all = menu.addAction(f"📋 Copy All Video URLs ({len(entries)} វីដេអូ)")
            act_all.triggered.connect(self._copy_all_playlist_urls)
            act_exp = menu.addAction("💾 Export All URLs to Text File (.txt)")
            act_exp.triggered.connect(self._export_all_playlist_urls)
            menu.addSeparator()

        act_chk_all = menu.addAction("✅ Select All (ជ្រើសរើសទាំងអស់)")
        act_chk_all.triggered.connect(self._select_all_playlist_items)
        act_unchk_all = menu.addAction("⬜ Deselect All (ដោះការជ្រើសរើស)")
        act_unchk_all.triggered.connect(self._deselect_all_playlist_items)

        menu.exec(self.table_playlist.viewport().mapToGlobal(pos))

    def _play_current_preview_video(self):
        """Plays the currently selected video or preview stream directly via FFplay with CENC decryption."""
        cur_u = self.entry_url.text().strip()
        stream_u = cur_u
        dec_key = ""

        # Check if it's a Hongguo drama
        if "hongguoduanju.com" in cur_u:
            sid = ""
            vid = ""
            m_s = re.findall(r'/(\d{10,25})', cur_u)
            if m_s:
                sid = m_s[0]
                vid = m_s[1] if len(m_s) >= 2 else sid
            entries = getattr(self, "playlist_entries", [])
            if entries and 0 <= self.selected_playlist_index < len(entries):
                ep = entries[self.selected_playlist_index]
                vid = ep.get("id") or vid
                sid = ep.get("series_id") or sid

            if sid and vid:
                pi = self._fetch_hongguo_play_info(sid, vid)
                if pi.get("main_url"):
                    stream_u = pi["main_url"]
                    spade_t = pi.get("player_access_key")
                    dec_key = unwrap_spade(spade_t)
                else:
                    stream_u = f"https://hongguoduanju.com/video/public/{vid}/360p.mp4"
        else:
            entries = getattr(self, "playlist_entries", [])
            if entries and 0 <= self.selected_playlist_index < len(entries):
                ep = entries[self.selected_playlist_index]
                if not ep.get("url") and ep.get("is_hainanyuyue"):
                    pu = self._fetch_hainanyuyue_play_url(
                        ep.get("ch_id", ""),
                        ep.get("video_id", ""),
                        ep.get("enc_did", ""),
                        ep.get("uid", "")
                    )
                    if pu:
                        ep["url"] = pu
                elif not ep.get("url") and (ep.get("is_kisskh") or "kisskh." in str(ep.get("webpage_url", "")).lower() or "kisskh." in cur_u.lower()):
                    self.log("🔍 [KissKH] កំពុងដោះសោ Stream វីដេអូសម្រាប់ចាក់ផ្ទាល់...")
                    pu = self._resolve_kisskh_stream_silent(ep.get("webpage_url") or cur_u)
                    if pu:
                        ep["url"] = pu
                stream_u = ep.get("url") or ep.get("webpage_url") or cur_u
            elif "kisskh." in cur_u.lower():
                self.log("🔍 [KissKH] កំពុងដោះសោ Stream វីដេអូសម្រាប់ចាក់ផ្ទាល់...")
                pu = self._resolve_kisskh_stream_silent(cur_u)
                if pu:
                    stream_u = pu

        ffplay_bin = shutil.which("ffplay") or os.path.abspath("bin/ffplay.exe")
        if ffplay_bin and os.path.exists(ffplay_bin):
            title = self.lbl_prev_title.text() or "Video Player"
            cmd = [
                ffplay_bin,
                "-window_title", f"🎬 {title[:50]}",
                "-autoexit"
            ]
            if "kisskh" in cur_u.lower() or "cdnvideo" in str(stream_u):
                cmd.extend(["-headers", "Referer: https://kisskh.do/\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"])
            elif "dramabox" in cur_u.lower() or "dramabox" in str(stream_u):
                cmd.extend(["-headers", "Referer: https://www.dramaboxdb.com/\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"])
            if dec_key:
                self.log(f"🔑 [Stream Player] ប្រើប្រាស់ Decryption Key: {dec_key[:8]}... (គ្មានបញ្ហាបែកពណ៌)")
                cmd.extend(["-decryption_key", dec_key])
            cmd.append(stream_u)
            self.log(f"▶️ [Stream Player] កំពុងចាក់វីដេអូ: {title[:50]}...")
            subprocess.Popen(cmd)
        else:
            import webbrowser
            webbrowser.open(stream_u)

    def _on_playlist_item_clicked(self, item):
        row = item.row()
        if 0 <= row < len(self.playlist_entries):
            e = self.playlist_entries[row]
            self.selected_playlist_index = row
            t = e.get("title") or f"Video {row+1}"
            dur = float(e.get("duration", 0) or 0)
            self.lbl_prev_title.setText(f"#{row+1}: {t}")
            d_str = format_duration_str(dur) if dur > 0 else "--:--"
            self.lbl_prev_info.setText(f"⏱️ Duration: {d_str} | 🔢 Part {row+1} of {len(self.playlist_entries)}")

            # Sync range and grid tile highlight
            range_size = 15
            target_range = row // range_size
            if getattr(self, "_current_range_index", 0) != target_range:
                self._select_range(target_range)
            else:
                self._refresh_grid_tiles_styling()

            # Load thumbnail in background
            th_url = (e.get("thumbnails") and e["thumbnails"][-1].get("url")) or e.get("thumbnail")
            if th_url:
                threading.Thread(target=self._load_item_thumbnail, args=(th_url,), daemon=True).start()

            # If Hongguo episode has no duration yet, fetch it on demand
            if dur <= 0 and e.get("series_id") and e.get("id"):
                self.lbl_prev_info.setText(f"⏱️ Duration: ⏳ Loading... | 🔢 Part {row+1} of {len(self.playlist_entries)}")
                def _fetch_dur_task(target_row=row, target_e=e):
                    try:
                        pi = self._fetch_hongguo_play_info(target_e["series_id"], target_e["id"])
                        real_d = float(pi.get("duration", 0) or 0)
                        if real_d > 0:
                            target_e["duration"] = real_d
                            def _update_ui():
                                if self.selected_playlist_index == target_row:
                                    self.lbl_prev_info.setText(f"⏱️ Duration: {format_duration_str(real_d)} | 🔢 Part {target_row+1} of {len(self.playlist_entries)}")
                                it_dur = self.table_playlist.item(target_row, 2)
                                if it_dur:
                                    it_dur.setText(format_duration_str(real_d))
                            self.run_on_main(_update_ui)
                    except Exception:
                        pass
                threading.Thread(target=_fetch_dur_task, daemon=True).start()

            # If Hainan Yuyue episode stream URL is not yet resolved, fetch in background
            if not e.get("url") and e.get("is_hainanyuyue"):
                def _fetch_yuyue_task(target_e=e):
                    pu = self._fetch_hainanyuyue_play_url(
                        target_e.get("ch_id", ""),
                        target_e.get("video_id", ""),
                        target_e.get("enc_did", ""),
                        target_e.get("uid", "")
                    )
                    if pu:
                        target_e["url"] = pu
                threading.Thread(target=_fetch_yuyue_task, daemon=True).start()

            # If KissKH episode stream URL is not yet resolved, fetch in background
            if not e.get("url") and (e.get("is_kisskh") or "kisskh." in str(e.get("webpage_url", "")).lower()):
                def _fetch_kisskh_task(target_e=e):
                    pu = self._resolve_kisskh_stream_silent(target_e.get("webpage_url", ""))
                    if pu:
                        target_e["url"] = pu
                threading.Thread(target=_fetch_kisskh_task, daemon=True).start()

        self._update_download_button_text()

    def _get_platform_info(self, url: str) -> tuple[str, str]:
        """
        Detects platform identity and returns (display_name, icon_filepath):
        e.g. ("YouTube", ".../youtube.png"), ("Hongguo (红果短剧)", ".../hongguo.png")
        """
        u = (url or "").lower()
        fav_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "favicons"))

        mapping = [
            (["youtube.com", "youtu.be"], "YouTube", "youtube.png"),
            (["bilibili.com", "b23.tv"], "Bilibili (哔哩哔哩)", "bilibili.png"),
            (["hongguoduanju.com", "novelquickapp.com"], "Hongguo (红果短剧)", "hongguo.png"),
            (["douyin.com"], "Douyin (抖音)", "douyin.png"),
            (["tiktok.com"], "TikTok", "tiktok.png"),
            (["facebook.com", "fb.watch"], "Facebook", "facebook.png"),
            (["kisskh."], "KissKH Drama", "kisskh.png"),
            (["hainanyuyue.com"], "Hainan Yuyue (海南愉悦)", "hainanyuyue.png"),
            (["stardusttv.net"], "StardustTV", "stardusttv.png"),
            (["sabayflix.net"], "Sabayflix", "sabayflix.png"),
            (["mgtv.com"], "Mango TV (芒果TV)", "mangotv.png"),
            (["iqiyi.com"], "iQIYI (爱奇艺)", "iqiyi.png"),
            (["v.qq.com"], "Tencent Video (腾讯视频)", "tencent.png"),
            (["youku.com"], "Youku (优酷)", "youku.png"),
            (["kuaishou.com"], "Kuaishou (快手)", "kuaishou.png"),
            (["khdiamond.net"], "KH Diamond", "khdiamond.png"),
            (["dramaboxdb.com", "dramabox.com"], "DramaBox (短剧)", "dramabox.png"),
            (["pngtree.com"], "Pngtree (PNG)", "pngtree.png"),
            (["pinterest.com", "pin.it"], "Pinterest", "pinterest.png"),
            (["t.me", "telegram.me"], "Telegram", "telegram.png"),
            (["xigua.com"], "Xigua Video (西瓜视频)", "xigua.png"),
            (["kolabkhmer.com"], "Kolab Khmer", "kolabkhmer.png"),
            (["phumikhmer.me"], "Phumi Khmer", "phumikhmer.png"),
            (["merlmovie.com"], "Merl Movie", "merlmovie.png"),
        ]

        for keys, name, icon_file in mapping:
            if any(k in u for k in keys):
                full_path = os.path.join(fav_dir, icon_file)
                if os.path.isfile(full_path):
                    return name, full_path

        fallback = os.path.join(fav_dir, "google.png")
        return "Web Media", fallback if os.path.isfile(fallback) else ""

    def _update_platform_badge(self, url: str):
        """Updates and displays the real website logo and name badge."""
        name, icon_path = self._get_platform_info(url)
        if icon_path and os.path.isfile(icon_path):
            pix = QPixmap(icon_path)
            if not pix.isNull():
                self.lbl_platform_icon.setPixmap(pix.scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.lbl_platform_name.setText(name)
                self.badge_platform.setVisible(True)
                return
        self.badge_platform.setVisible(False)

    def _apply_auto_fit_thumbnail(self, pixmap: QPixmap):
        """
        Dynamically adapts thumbnail container dimensions and scales the cover image:
        - Landscape (YouTube / Bilibili 16:9, aspect >= 1.25): 160 x 92 px
        - Portrait (Short Drama 9:16 or 3:4, aspect <= 0.85): 100 x 140 px
        - Standard / Square (4:3 or 1:1): 115 x 115 px
        """
        if not pixmap or pixmap.isNull():
            self.lbl_thumb.setFixedSize(100, 140)
            self.lbl_thumb.setText("🖼️ No Cover")
            return

        w = pixmap.width()
        h = pixmap.height()
        aspect = w / max(1, h)

        if aspect >= 1.25:
            target_w, target_h = 160, 92
        elif aspect <= 0.85:
            target_w, target_h = 100, 140
        else:
            target_w, target_h = 115, 115

        self.lbl_thumb.setScaledContents(False)
        self.lbl_thumb.setFixedSize(target_w, target_h)

        scaled = pixmap.scaled(
            target_w, target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        if scaled.width() > target_w or scaled.height() > target_h:
            cx = max(0, (scaled.width() - target_w) // 2)
            cy = max(0, (scaled.height() - target_h) // 2)
            scaled = scaled.copy(cx, cy, target_w, target_h)

        rounded = get_rounded_pixmap(scaled, radius=8)
        self.lbl_thumb.setPixmap(rounded)

    def _render_tags(self, tags: list, url: str = ""):
        """Renders real platform logo badge and category tags matching official drama apps."""
        # Clean existing dynamic tags (preserve badge_platform at index 0)
        while self.tags_layout.count() > 1:
            item = self.tags_layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()

        if url:
            self._update_platform_badge(url)

        has_tags = bool(tags)
        has_badge = self.badge_platform.isVisible()
        if not has_tags and not has_badge:
            self.tags_widget.setVisible(False)
            return

        self.tags_widget.setVisible(True)
        for t in (tags or [])[:5]:
            t_str = str(t).strip()
            if not t_str:
                continue
            lbl = QLabel(t_str)
            lbl.setStyleSheet("""
                QLabel {
                    background-color: #242426;
                    color: #a1a1aa;
                    font-size: 11px;
                    font-weight: 500;
                    padding: 3px 8px;
                    border-radius: 4px;
                    border: none;
                }
            """)
            self.tags_layout.addWidget(lbl)
        self.tags_layout.addStretch()

    def _on_desc_link_clicked(self, link: str):
        """Toggles between collapsed and expanded synopsis text."""
        self._desc_expanded = not getattr(self, "_desc_expanded", False)
        self._update_desc_text()

    def _update_desc_text(self):
        full_text = getattr(self, "_full_description", "").strip()
        if not full_text:
            self.lbl_desc_text.setText("无简介")
            return
        is_expanded = getattr(self, "_desc_expanded", False)
        cutoff = 100
        if len(full_text) <= cutoff:
            self.lbl_desc_text.setText(full_text)
        else:
            if is_expanded:
                self.lbl_desc_text.setText(f"{full_text} <a href='toggle' style='color: #9ca3af; text-decoration: none; font-weight: bold;'>收起</a>")
            else:
                short = full_text[:cutoff]
                self.lbl_desc_text.setText(f"{short}... <a href='toggle' style='color: #9ca3af; text-decoration: none; font-weight: bold;'>展开</a>")

    def _set_episode_view_mode(self, mode: str):
        """Switches between Square Grid View and List Table View."""
        self._episode_view_mode = mode
        if mode == "grid":
            self.ep_grid_wrapper.setVisible(True)
            self.playlist_box.setVisible(False)
            self.btn_view_grid.setStyleSheet("""
                background-color: #ea580c;
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                border: none;
            """)
            self.btn_view_list.setStyleSheet("""
                background-color: #27272a;
                color: #a1a1aa;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #3f3f46;
            """)
        else:
            self.ep_grid_wrapper.setVisible(False)
            self.playlist_box.setVisible(True)
            self.btn_view_grid.setStyleSheet("""
                background-color: #27272a;
                color: #a1a1aa;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #3f3f46;
            """)
            self.btn_view_list.setStyleSheet("""
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 4px;
                border: none;
            """)

    def _render_episode_ranges(self, total_episodes: int, current_ep_index: int = 0, range_size: int = None):
        """Builds range tabs (e.g. 1-50 | 51-74 or 1-15 | 16-30...) and initializes grid tiles."""
        self.selected_playlist_index = current_ep_index
        while self.range_tabs_layout.count():
            it = self.range_tabs_layout.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        if range_size is None:
            if getattr(self, "is_dramabox", False) or total_episodes > 50:
                range_size = 50
            else:
                range_size = 15
        self._current_range_size = range_size

        self._current_range_index = current_ep_index // range_size
        self._range_buttons = []

        num_ranges = (total_episodes + range_size - 1) // range_size
        for r_idx in range(num_ranges):
            start_ep = r_idx * range_size + 1
            end_ep = min((r_idx + 1) * range_size, total_episodes)
            btn = QPushButton(f"{start_ep}-{end_ep}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, ri=r_idx: self._select_range(ri))
            self._range_buttons.append(btn)
            self.range_tabs_layout.addWidget(btn)

            # Sleek pipe separator '|' between range tabs (matches DramaBox web UI)
            if r_idx < num_ranges - 1:
                sep = QLabel("|")
                sep.setStyleSheet("color: #52525b; font-size: 13px; font-weight: bold; padding: 0 1px;")
                self.range_tabs_layout.addWidget(sep)

        if num_ranges > 1:
            btn_chevron = QPushButton(">")
            btn_chevron.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_chevron.setToolTip("Next Range")
            btn_chevron.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #71717a;
                    font-size: 14px;
                    font-weight: bold;
                    border: none;
                    padding: 2px 4px;
                }
                QPushButton:hover {
                    color: #ffffff;
                }
            """)
            def _adv():
                next_r = (getattr(self, "_current_range_index", 0) + 1) % num_ranges
                self._select_range(next_r)
            btn_chevron.clicked.connect(_adv)
            self.range_tabs_layout.addWidget(btn_chevron)

        self.range_tabs_layout.addStretch()
        self._update_range_tabs_style()
        self._render_grid_tiles(self._current_range_index)

    def _select_range(self, range_idx: int):
        self._current_range_index = range_idx
        self._update_range_tabs_style()
        self._render_grid_tiles(range_idx)

    def _update_range_tabs_style(self):
        for idx, btn in enumerate(getattr(self, "_range_buttons", [])):
            if idx == getattr(self, "_current_range_index", 0):
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #f43f5e;
                        font-size: 14px;
                        font-weight: bold;
                        border: none;
                        padding: 2px 6px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #71717a;
                        font-size: 14px;
                        font-weight: normal;
                        border: none;
                        padding: 2px 6px;
                    }
                    QPushButton:hover {
                        color: #e4e4e7;
                    }
                """)

    def _render_grid_tiles(self, range_idx: int):
        while self.ep_grid_layout.count():
            it = self.ep_grid_layout.takeAt(0)
            w_it = it.widget()
            if w_it:
                w_it.setParent(None)
                w_it.deleteLater()

        self._grid_buttons = {}
        range_size = getattr(self, "_current_range_size", 15)
        start_idx = range_idx * range_size
        end_idx = min(start_idx + range_size, len(self.playlist_entries))

        # Dynamic responsive column calculation
        w = self.ep_grid_container.width()
        if w < 240:
            col_count = 3
        elif w < 315:
            col_count = 4
        elif w < 440:
            col_count = 5
        elif w < 540:
            col_count = 6
        else:
            col_count = max(6, min(10, w // 75)) if w > 0 else 5
        self.ep_grid_container._last_cols = col_count

        for c in range(12):
            self.ep_grid_layout.setColumnStretch(c, 0)
        for c in range(col_count):
            self.ep_grid_layout.setColumnStretch(c, 1)

        for pos, ep_idx in enumerate(range(start_idx, end_idx)):
            ep_num = ep_idx + 1
            r = pos // col_count
            c = pos % col_count

            ep_data = self.playlist_entries[ep_idx] if ep_idx < len(self.playlist_entries) else {}
            is_locked = bool(
                ep_data.get("is_locked") or
                ep_data.get("locked") or
                ep_data.get("is_vip") or
                ep_data.get("vip") or
                ep_data.get("pay_type", 0) == 1 or
                ep_data.get("price", 0) > 0 or
                (ep_data.get("is_hongguo") and ep_num > 15) or
                any(k in (ep_data.get("title") or "") for k in ["[VIP]", "🔒", "Lock", "付费"])
            )

            tile = EpisodeGridTile(ep_num, is_locked=is_locked)
            tooltip_txt = ep_data.get("title") or f"Episode {ep_num}"
            if is_locked:
                tooltip_txt += " (🔒 VIP / Locked)"
            tile.setToolTip(tooltip_txt)
            tile.clicked.connect(lambda _, ei=ep_idx: self._on_grid_tile_clicked(ei))
            tile.doubleClicked.connect(lambda ei: (self._on_grid_tile_clicked(ei), self._play_current_preview_video()))

            self._grid_buttons[ep_idx] = tile
            self.ep_grid_layout.addWidget(tile, r, c)

        self._refresh_grid_tiles_styling()

    def _relayout_grid_tiles(self, cols: int):
        """Smoothly re-arranges tiles into new column count on panel resize."""
        if not hasattr(self, "_grid_buttons") or not self._grid_buttons:
            return
        if cols < 3:
            cols = 3
        while self.ep_grid_layout.count():
            self.ep_grid_layout.takeAt(0)
        for c in range(12):
            self.ep_grid_layout.setColumnStretch(c, 0)
        for c in range(cols):
            self.ep_grid_layout.setColumnStretch(c, 1)
        for pos, (ep_idx, tile) in enumerate(self._grid_buttons.items()):
            r = pos // cols
            c = pos % cols
            self.ep_grid_layout.addWidget(tile, r, c)

    def _refresh_grid_tiles_styling(self):
        sel_idx = getattr(self, "selected_playlist_index", 0)
        for ep_idx, tile in getattr(self, "_grid_buttons", {}).items():
            tile.setActive(ep_idx == sel_idx)

    def _on_grid_tile_clicked(self, ep_idx: int):
        if not (0 <= ep_idx < len(self.playlist_entries)):
            return
        self.selected_playlist_index = ep_idx
        self._refresh_grid_tiles_styling()

        total_eps = len(self.playlist_entries)
        if getattr(self, "is_dramabox", False):
            self.lbl_episodes_title.setText(f"Episodes ({ep_idx+1}/{total_eps})")
        else:
            self.lbl_episodes_title.setText(f"选集 ({ep_idx+1}/{total_eps})")

        if 0 <= ep_idx < self.table_playlist.rowCount():
            self.table_playlist.blockSignals(True)
            self.table_playlist.selectRow(ep_idx)
            self.table_playlist.blockSignals(False)
            item = self.table_playlist.item(ep_idx, 0)
            if item:
                self._on_playlist_item_clicked(item)
        else:
            e = self.playlist_entries[ep_idx]
            t = e.get("title") or f"Episode {ep_idx+1}"
            dur = float(e.get("duration", 0) or 0)
            self.lbl_prev_title.setText(f"#{ep_idx+1}: {t}")
            d_str = format_duration_str(dur) if dur > 0 else "--:--"
            self.lbl_prev_info.setText(f"⏱️ Duration: {d_str} | 🔢 Part {ep_idx+1} of {len(self.playlist_entries)}")

    def _on_playlist_item_changed(self, item):
        if item.column() == 0:
            self._update_download_button_text()

    def _update_download_button_text(self):
        if not getattr(self, "is_playlist", False):
            self.btn_download.setText("Download Video / Audio")
            return

        checked_count = 0
        for r in range(self.table_playlist.rowCount()):
            it = self.table_playlist.item(r, 0)
            if it and it.checkState() == Qt.CheckState.Checked:
                checked_count += 1

        total = len(self.playlist_entries)
        if self.radio_pl_single.isChecked():
            self.btn_download.setText(f"📥 Download Single Video (#{self.selected_playlist_index+1})")
        elif self.radio_pl_selected.isChecked():
            self.btn_download.setText(f"📥 Download Selected ({checked_count}/{total} Videos)")
        else:
            self.btn_download.setText(f"📥 Download All Playlist ({total} Videos)")

    def _load_item_thumbnail(self, thumb_url: str):
        if not thumb_url:
            return
        try:
            req = urllib.request.Request(thumb_url, headers={"User-Agent": "Mozilla/5.0"})
            raw_data = urllib.request.urlopen(req, timeout=5).read()
            qimg = QImage.fromData(raw_data)
            if not qimg.isNull():
                pix = QPixmap.fromImage(qimg)
                self.run_on_main(lambda: self._apply_auto_fit_thumbnail(pix))
        except Exception:
            pass

    def _extract_hongguo_series(self, url: str) -> dict:
        """
        Specialized extractor for Hongguo Short Drama (红果短剧 - hongguoduanju.com / novelquickapp.com):
        Scans all drama episodes, title, cover, and builds direct video stream entries.
        """
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
                    import json
                    d = json.loads(s)
                    if d.get("@type") == "VideoObject":
                        raw_name = d.get("name", "")
                        title = re.sub(r'\s*第\d+集.*', '', raw_name).strip() or raw_name
                        desc = d.get("description", "")
                        thumbs = d.get("thumbnailUrl") or []
                        if isinstance(thumbs, list) and len(thumbs) > 0:
                            cover = thumbs[0]
                        elif isinstance(thumbs, str):
                            cover = thumbs
                        
                        dur_str = d.get("duration", "")
                        dur_m = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', dur_str)
                        if dur_m:
                            h = int(dur_m.group(1) or 0)
                            m_val = int(dur_m.group(2) or 0)
                            s_val = int(dur_m.group(3) or 0)
                            ep1_duration = h * 3600 + m_val * 60 + s_val
                        break
                except Exception:
                    pass

            if not title or title == "Hongguo Short Drama":
                t_m = re.search(r'<title>(.*?)</title>', html)
                if t_m:
                    title = t_m.group(1).split("-")[0].strip()

            # Episode 1 video ID if present in JSON or HTML
            ep1_vid = ""
            vids_match = re.findall(r'/video/public/(\d+)/', html)
            if vids_match:
                ep1_vid = vids_match[0]
            if not ep1_vid:
                vid_json = re.findall(r'\"vid\":\s*\"(\d+)\"', html)
                if vid_json:
                    ep1_vid = vid_json[0]

            episodes = []
            seen_eps = set()

            # 1. Primary Strategy: Extract ALL episodes (e.g. all 1-1000 episodes across all segments 1-15, 16-30... 991-1000)
            # from ModernJS _ROUTER_DATA loaderData
            router_m = re.search(r'_ROUTER_DATA\s*=\s*(\{.*)', html)
            if router_m:
                try:
                    import json
                    decoder = json.JSONDecoder()
                    router_obj, _ = decoder.raw_decode(router_m.group(1))
                    loader_data = router_obj.get("loaderData", {})
                    # Check publicVideoSeo for exact durationSeconds (e.g. Episode 1: 381.737s = 6:22 min)
                    for lk, lv in loader_data.items():
                        if isinstance(lv, dict) and "publicVideoSeo" in lv:
                            seo_dur = lv["publicVideoSeo"].get("durationSeconds")
                            if seo_dur:
                                try:
                                    ep1_duration = int(round(float(seo_dur)))
                                except Exception:
                                    pass

                    for k, v in loader_data.items():
                        if isinstance(v, dict) and "seriesDetail" in v:
                            sd = v["seriesDetail"]
                            s_name = sd.get("series_name") or title
                            if s_name:
                                title = s_name
                            desc = sd.get("series_intro") or desc
                            cover = sd.get("series_cover") or cover
                            tags = sd.get("tags") or tags
                            vids = sd.get("vid_list", [])
                            target_index = 0
                            target_dur = 0
                            if target_vid:
                                t_pi = self._fetch_hongguo_play_info(series_id, target_vid)
                                if t_pi and t_pi.get("duration"):
                                    try:
                                        target_dur = int(round(float(t_pi.get("duration"))))
                                    except Exception:
                                        pass

                            if vids:
                                for idx, vid in enumerate(vids):
                                    ep_num = idx + 1
                                    full_page = f"https://hongguoduanju.com/player/{series_id}/{vid}" if idx > 0 else f"https://hongguoduanju.com/player/{series_id}"
                                    stream_url = f"https://hongguoduanju.com/video/public/{vid}/360p.mp4"
                                    # Duration resolution: target episode or Episode 1, otherwise 0 (fetched in background)
                                    dur = 0
                                    if target_vid and vid == target_vid and target_dur > 0:
                                        dur = target_dur
                                        target_index = idx
                                    elif ep_num == 1 and ep1_duration > 0:
                                        dur = ep1_duration

                                    episodes.append({
                                        "id": vid,
                                        "ep_num": ep_num,
                                        "title": f"{title} 第{ep_num}集",
                                        "url": stream_url,
                                        "webpage_url": full_page,
                                        "duration": dur,
                                        "thumbnail": cover,
                                        "series_id": series_id,
                                    })
                                    seen_eps.add(ep_num)
                                break
                except Exception as r_err:
                    self.log(f"⚠️ [Hongguo] _ROUTER_DATA decode error: {r_err}")

            # 2. Fallback Strategy: Extract prerendered episode links from HTML <a> tags
            if not episodes:
                link_pattern = re.compile(r'href=[\"\'](/player/' + series_id + r'(?:/(\d+))?)[\"\'][^>]*>(.*?)</a>', re.DOTALL)
                target_index = 0
                for m in link_pattern.finditer(html):
                    href = m.group(1)
                    ep_id = m.group(2) or ""
                    txt = re.sub(r'<[^>]+>', '', m.group(3)).strip()
                    if txt.isdigit():
                        ep_num = int(txt)
                        if ep_num not in seen_eps:
                            seen_eps.add(ep_num)
                            full_page = f"https://hongguoduanju.com{href}"
                            cur_vid = ep_id if ep_id else ep1_vid
                            stream_url = f"https://hongguoduanju.com/video/public/{cur_vid}/360p.mp4" if cur_vid else full_page
                            dur = 0
                            if target_vid and cur_vid == target_vid and target_dur > 0:
                                dur = target_dur
                                target_index = len(episodes)
                            elif ep_num == 1 and ep1_duration > 0:
                                dur = ep1_duration
                            episodes.append({
                                "id": cur_vid or ep_id or f"ep_{ep_num}",
                                "ep_num": ep_num,
                                "title": f"{title} 第{ep_num}集",
                                "url": stream_url,
                                "webpage_url": full_page,
                                "duration": dur,
                                "thumbnail": cover,
                                "series_id": series_id,
                            })

            episodes.sort(key=lambda x: x["ep_num"])

            formats = [
                {"format_id": "720p", "ext": "mp4", "resolution": "1280x720", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "format": "720P HD (Protected Full Stream)", "url": episodes[0]["url"] if episodes else ""},
                {"format_id": "360p", "ext": "mp4", "resolution": "640x360", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "format": "360P SD (Public Preview)", "url": episodes[0]["url"] if episodes else ""},
            ]

            return {
                "_type": "playlist",
                "id": series_id,
                "title": f"🎬 {title} (红果短剧)",
                "uploader": "红果短剧 (Hongguo)",
                "thumbnail": cover,
                "description": desc,
                "tags": tags,
                "entries": episodes,
                "formats": formats,
                "is_hongguo": True,
                "target_index": target_index
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.log(f"⚠️ [Hongguo] Scan failed: {e}")
            return None

    def _load_cookies_str_from_file(self, cookie_file: str, domain: str = "") -> str:
        """Parses a Netscape cookies.txt file and formats as a Cookie header string."""
        if not cookie_file or not os.path.exists(cookie_file):
            return ""
        pairs = []
        try:
            with open(cookie_file, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 7:
                        c_dom, _, _, _, _, c_name, c_val = parts[:7]
                        if not domain or domain in c_dom:
                            pairs.append(f"{c_name}={c_val}")
        except Exception:
            pass
        return "; ".join(pairs)

    def _fetch_hongguo_play_info(self, series_id: str, item_id: str, return_err: bool = False):
        """Fetches full HD 720p stream info (video + audio) for Hongguo episode."""
        try:
            api_url = "https://hongguoduanju.com/api/video/protected/play-info"
            payload = json.dumps({"series_id": str(series_id), "item_id": str(item_id), "definition": "720p"}).encode('utf-8')
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": f"https://hongguoduanju.com/player/{series_id}/{item_id}",
                "Content-Type": "application/json",
                "Origin": "https://hongguoduanju.com"
            }
            # Attach cookies if available
            c_file = self._get_active_cookie_file()
            if c_file and os.path.exists(c_file):
                c_str = self._load_cookies_str_from_file(c_file, "hongguoduanju.com")
                if c_str:
                    headers["Cookie"] = c_str

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(api_url, data=payload, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=12) as r:
                data = json.loads(r.read().decode('utf-8'))
                pi = data.get("play_info", {})
                return (pi, "") if return_err else pi
        except urllib.error.HTTPError as he:
            err_body = ""
            try:
                err_body = he.read().decode('utf-8', errors='ignore')
            except Exception:
                pass
            return ({}, f"HTTP {he.code}: {err_body}") if return_err else {}
        except Exception as e:
            return ({}, str(e)) if return_err else {}

    def _resolve_hongguo_durations_background(self, series_id: str, entries: list):
        """Asynchronously resolves actual full durations for Hongguo drama episodes in background."""
        def _worker():
            import time
            from concurrent.futures import ThreadPoolExecutor, as_completed
            # Resolve up to first 30 episodes that have no duration
            targets = [(idx, e) for idx, e in enumerate(entries[:30]) if e.get("duration", 0) <= 0 and e.get("id")]
            if not targets:
                return

            def _fetch_one(item):
                idx, ep = item
                try:
                    time.sleep(0.12)  # gentle pacing to avoid rate limits
                    pi = self._fetch_hongguo_play_info(series_id, ep["id"])
                    d = float(pi.get("duration", 0) or 0)
                    return idx, ep, d
                except Exception:
                    return idx, ep, 0

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(_fetch_one, it) for it in targets]
                for f in as_completed(futures):
                    try:
                        idx, ep, real_d = f.result()
                        if real_d > 0:
                            ep["duration"] = real_d
                            def _update_row(r=idx, dur_s=real_d):
                                it_dur = self.table_playlist.item(r, 2)
                                if it_dur:
                                    it_dur.setText(format_duration_str(dur_s))
                                if self.selected_playlist_index == r:
                                    self.lbl_prev_info.setText(f"⏱️ Duration: {format_duration_str(dur_s)} | 🔢 Part {r+1} of {len(self.playlist_entries)}")
                            self.run_on_main(_update_row)
                    except Exception:
                        pass

        threading.Thread(target=_worker, daemon=True).start()

    def _download_hongguo_episode(self, series_id: str, vid: str, output_path: str, referer: str = "", part_idx: int = 1, total_parts: int = 1):
        """Downloads full 720p HD video and audio stream from Hongguo and merges them with FFmpeg."""
        pi, err_info = self._fetch_hongguo_play_info(series_id, vid, return_err=True)
        v_url = pi.get("main_url")
        a_url = pi.get("audio", {}).get("main_url")
        spade_token = pi.get("player_access_key") or pi.get("audio", {}).get("player_access_key")
        dec_key = unwrap_spade(spade_token)

        if v_url and a_url:
            dur_val = pi.get('duration', 0)
            self.log(f"🎬 [Hongguo] ទាញយកកញ្ចប់ 720p HD ពេញលេញ ({dur_val:.0f}s)...")
            temp_v = output_path + ".vtemp.mp4"
            temp_a = output_path + ".atemp.m4a"
            try:
                # 1. Download Video Stream
                self._download_direct_stream(v_url, temp_v, referer="https://hongguoduanju.com/", part_idx=part_idx, total_parts=total_parts, sublabel="Video 720p")
                if getattr(self, "cancel_download", False):
                    return
                # 2. Download Audio Stream
                self._download_direct_stream(a_url, temp_a, referer="https://hongguoduanju.com/", part_idx=part_idx, total_parts=total_parts, sublabel="Audio Track")
                if getattr(self, "cancel_download", False):
                    return

                # 3. Merge & Decrypt with FFmpeg (Fixes broken colors & restores 100% full quality)
                ff_bin = get_ffmpeg_binary_path() or "ffmpeg"
                merge_cmd = [ff_bin, "-y"]
                if dec_key:
                    self.log(f"🔑 [Hongguo DRM] ដោះសោ CENC AES-128 Key: {dec_key[:8]}... (ជួសជុលបញ្ហាបែកពណ៌)")
                    merge_cmd.extend(["-decryption_key", dec_key])
                merge_cmd.extend(["-i", temp_v])
                if dec_key:
                    merge_cmd.extend(["-decryption_key", dec_key])
                merge_cmd.extend([
                    "-i", temp_a,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-movflags", "+faststart",
                    output_path
                ])
                kwargs = {"check": True, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
                if os.name == "nt":
                    kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
                subprocess.run(merge_cmd, **kwargs)
                self.log(f"✅ [Hongguo] បញ្ចូលរូបភាព 720p និងសំឡេងជោគជ័យ: {os.path.basename(output_path)}")
            finally:
                if os.path.exists(temp_v):
                    try: os.remove(temp_v)
                    except: pass
                if os.path.exists(temp_a):
                    try: os.remove(temp_a)
                    except: pass
        else:
            if "protected_playback_unavailable" in str(err_info) or "403" in str(err_info):
                self.log(f"🔒 [Hongguo Locked / VIP] ភាគនេះ ({vid}) ត្រូវបានចាក់សោ (Locked / App Only) នៅលើ Server របស់ Hongguo!")
                self.log("💡 [Hongguo Notice] ភាគនេះតម្រូវឱ្យស្កេន QR Code មើលក្នុង Hongguo App ឬមាន Account/Cookie ដែលបានដោះសោរឿងនេះ។")
                self.log("👉 ប្រសិនបើអ្នកបាន Login លើ Browser រួចហើយ សូមចុច '🍪 Grab Cookies' ដើម្បីទាញយក។")
                return

            # Fallback to public stream if available
            fallback_url = f"https://hongguoduanju.com/video/public/{vid}/360p.mp4"
            self.log("ℹ️ [Hongguo] សាកល្បង Public Preview Stream...")
            self._download_direct_stream(fallback_url, output_path, referer=referer, part_idx=part_idx, total_parts=total_parts, sublabel="Preview")

    def _download_direct_stream(self, stream_url: str, output_path: str, referer: str = "", part_idx: int = 1, total_parts: int = 1, sublabel: str = ""):
        """
        Downloads a direct stream with chunked progress updates, auto-resume on SSL/network drop (Range requests),
        and referer header. Fully immune against UNEXPECTED_EOF_WHILE_READING.
        """
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": referer or "https://hongguoduanju.com/",
            "Connection": "keep-alive"
        }

        max_retries = 10
        total_size = 0
        downloaded = 0

        if os.path.exists(output_path):
            downloaded = os.path.getsize(output_path)

        for attempt in range(max_retries):
            if getattr(self, "cancel_download", False):
                break
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
                            if getattr(self, "cancel_download", False):
                                break
                            chunk = resp.read(131072)  # 128 KB
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0:
                                pct = min(100, int(downloaded * 100 / total_size))
                                elapsed = max(0.1, time.time() - start_time)
                                speed_mb = ((downloaded - initial_downloaded) / (1024 * 1024)) / elapsed
                                lbl_sub = f" ({sublabel})" if sublabel else ""
                                self.run_on_main(lambda p=pct, i=part_idx, t=total_parts, sp=speed_mb, s=lbl_sub: (
                                    self.prog_bar.setValue(p),
                                    self.lbl_prog_stats.setText(f"Part [{i}/{t}]{s}: {p}% ({sp:.2f} MB/s)")
                                ))

                # Check if download completed successfully
                if total_size == 0 or downloaded >= total_size:
                    break

            except urllib.error.HTTPError as he:
                if getattr(self, "cancel_download", False):
                    break
                # Fatal HTTP errors (404 Not Found, 403 Forbidden, 401 Unauthorized) - stop retrying
                if he.code in (404, 403, 401, 410):
                    self.log(f"❌ [Downloader Error] មិនអាចទាញយកបាន (HTTP Error {he.code}: {he.reason}) - Stream មិនមាននៅលើ Server ទេ")
                    break
                self.log(f"⚠️ [Network Resume] ជួបបញ្ហា HTTP {he.code} ({he.reason}) - កំពុងភ្ជាប់បន្តឡើងវិញ (Attempt {attempt+1}/{max_retries})...")
                time.sleep(1.5)
            except Exception as e:
                if getattr(self, "cancel_download", False):
                    break
                if os.path.exists(output_path):
                    downloaded = os.path.getsize(output_path)
                self.log(f"⚠️ [Network Resume] ជួបបញ្ហា network/SSL ({e}) - កំពុងភ្ជាប់បន្តឡើងវិញ (Attempt {attempt+1}/{max_retries} នៅត្រង់ {downloaded/(1024*1024):.1f} MB)...")
                time.sleep(1.5)

    def _extract_stardust_series(self, url: str) -> dict:
        """
        Specialized extractor for StardustTV Short Drama (stardusttv.net):
        Scans all drama episodes, m3u8 streams, title, cover, and builds playlist entries.
        """
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

            # All episodes m3u8 streams (supports agilecdn-v, tcdn-v, etc.)
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

    def _resolve_kisskh_stream_silent(self, webpage_url: str, timeout_ms: int = 18000) -> str:
        """
        Silent thread-safe resolver for KissKH video streams using persistent default QWebEngineProfile
        without popup dialogs or profile destruction collisions.
        """
        if not WEBENGINE_AVAILABLE:
            return ""

        def _do_resolve():
            try:
                result = {}
                class SilentInterceptor(QWebEngineUrlRequestInterceptor):
                    def __init__(self, parent=None):
                        super().__init__(parent)
                    def interceptRequest(self, info):
                        u = info.requestUrl().toString()
                        if "DramaList/Episode" in u:
                            result["api_url"] = u
                        elif (".m3u8" in u or ".mp4" in u) and not u.endswith(".png") and not u.endswith(".js"):
                            result["m3u8_url"] = u
                        elif "sub.cdnvideo" in u or ".srt" in u:
                            result["sub_url"] = u

                from ui_v_PyQt6.components.downloader.media_browser_dialog import get_shared_persistent_profile
                profile = get_shared_persistent_profile() or QWebEngineProfile.defaultProfile()
                interceptor = SilentInterceptor(self)
                profile.setUrlRequestInterceptor(interceptor)
                self._kisskh_interceptor = interceptor

                page = SnifferWebEnginePage(profile, self)
                self._kisskh_page = page
                page.setUrl(QUrl(webpage_url))

                loop = QEventLoop()
                timer = QTimer()
                timer.setInterval(200)

                def poll():
                    if result.get("api_url") or result.get("m3u8_url"):
                        timer.stop()
                        loop.quit()

                timer.timeout.connect(poll)
                timer.start()

                QTimer.singleShot(timeout_ms, loop.quit)
                loop.exec()

                if result.get("sub_url"):
                    self._latest_kisskh_sub_url = result["sub_url"]

                if result.get("m3u8_url"):
                    return result["m3u8_url"]

                if result.get("api_url"):
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(
                        result["api_url"],
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                            "Referer": webpage_url
                        }
                    )
                    with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
                        d = json.loads(r.read().decode('utf-8', errors='ignore'))
                        for k in ["Video", "Video_tmp", "dataSaver", "ThirdParty"]:
                            v = d.get(k)
                            if v and str(v).startswith("http"):
                                return str(v)
            except Exception as e:
                self.log(f"⚠️ [KissKH Resolver Error] {e}")
            return ""

        return self.run_on_main_sync(_do_resolve, timeout_sec=22) or ""

    def _extract_kisskh_series(self, url: str) -> dict:
        """
        Specialized extractor for KissKH Asian Drama (kisskh.do, kisskh.me, kisskh.co):
        Delegates to KissKHExtractor with search auto-resolve and silent stream resolver.
        """
        from services.downloader.extractors.kisskh import KissKHExtractor
        extractor = KissKHExtractor(log_callback=self.log, silent_resolver=self._resolve_kisskh_stream_silent)
        return extractor.extract_series(url)

    def _extract_sabayflix_series(self, url: str) -> dict:
        """
        Specialized extractor for SabayFlix Cambodian movies and series:
        Delegates to SabayflixExtractor with API metadata and stream resolution.
        """
        from services.downloader.extractors.sabayflix import SabayflixExtractor
        cookie_path = self._get_active_cookie_file()
        extractor = SabayflixExtractor(log_callback=self.log, silent_resolver=self._resolve_kisskh_stream_silent)
        return extractor.extract_series(url, cookie_file=cookie_path)

    def _extract_khdiamond_series(self, url: str) -> dict:
        """
        Specialized extractor for KH Diamond (khdiamond.net) movies and anime/drama series:
        Delegates to KHDiamondExtractor with episode listings and silent stream resolver.
        """
        from services.downloader.extractors.khdiamond import KHDiamondExtractor
        cookie_path = self._get_active_cookie_file()
        extractor = KHDiamondExtractor(log_callback=self.log, silent_resolver=self._resolve_kisskh_stream_silent)
        return extractor.extract_series(url, cookie_file=cookie_path)

    def _fetch_hainanyuyue_play_url(self, ch_id: str, video_id: str, enc_did: str, uid: str) -> str:
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
            req = urllib.request.Request(ep_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'})
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

    def _extract_hainanyuyue_series(self, url: str) -> dict:
        """
        Specialized extractor for Hainan Yuyue Short Drama (海南愉悦短剧 - hainanyuyue.com / kylin.hainanyuyue.com):
        Scans drama episodes, metadata, cover, and builds direct video stream entries.
        """
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'})
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
                "description": desc,
                "tags": tags,
                "entries": episodes,
                "formats": formats,
                "is_hainanyuyue": True,
                "target_index": target_idx
            }
        except Exception as e:
            self.log(f"⚠️ [Hainan Yuyue] Scan failed: {e}")
            return None

    def _extract_bilibili_bangumi(self, url: str) -> Optional[dict]:
        """
        Specialized extractor for Bilibili Bangumi & Short Dramas:
        Uses Bilibili PGC Web API to scan all episodes, season title, cover, duration and bvid/cid.
        """
        try:
            ep_m = re.search(r'ep(\d+)', url)
            ss_m = re.search(r'ss(\d+)', url)

            if ep_m:
                api_url = f"https://api.bilibili.com/pgc/view/web/season?ep_id={ep_m.group(1)}"
            elif ss_m:
                api_url = f"https://api.bilibili.com/pgc/view/web/season?season_id={ss_m.group(1)}"
            else:
                return None

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(api_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/"
            })
            with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))

            if data.get("code") != 0:
                return None

            res = data.get("result", {})
            title = res.get("title") or res.get("series_title") or "Bilibili Short Drama"
            cover = res.get("cover") or ""
            desc = res.get("evaluate") or ""
            eps = res.get("episodes", [])
            if not eps:
                return None

            entries = []
            target_idx = 0
            cur_ep_str = ep_m.group(1) if ep_m else ""
            for idx, ep in enumerate(eps):
                dur = float(ep.get("duration", 0) or 0) / 1000.0
                lt = ep.get("long_title") or ""
                ep_id_str = str(ep.get("id") or ep.get("ep_id") or "")
                if cur_ep_str and ep_id_str == cur_ep_str:
                    target_idx = idx

                entries.append({
                    "id": ep_id_str,
                    "title": f"第{idx+1}集 {lt}".strip(),
                    "url": f"https://www.bilibili.com/bangumi/play/ep{ep_id_str}",
                    "duration": dur,
                    "thumbnail": ep.get("cover") or cover,
                    "bvid": ep.get("bvid"),
                    "cid": ep.get("cid"),
                    "is_bilibili_bangumi": True
                })

            tags = ["Bilibili", "短剧", "国创"]
            type_name = res.get("type_name")
            if type_name:
                tags.append(type_name)

            return {
                "_type": "playlist",
                "id": str(res.get("season_id") or (ep_m and ep_m.group(1))),
                "title": f"🎬 {title} (Bilibili)",
                "uploader": "Bilibili (哔哩哔哩)",
                "description": desc,
                "thumbnail": cover,
                "tags": tags,
                "entries": entries,
                "target_index": target_idx,
                "is_bilibili_bangumi": True,
                "formats": [
                    {"format_id": "1080p", "ext": "mp4", "resolution": "1920x1080", "format_note": "Full HD 1080p", "height": 1080, "vcodec": "avc1", "acodec": "mp4a"},
                    {"format_id": "720p", "ext": "mp4", "resolution": "1280x720", "format_note": "HD 720p", "height": 720, "vcodec": "avc1", "acodec": "mp4a"},
                    {"format_id": "480p", "ext": "mp4", "resolution": "854x480", "format_note": "SD 480p", "height": 480, "vcodec": "avc1", "acodec": "mp4a"}
                ]
            }
        except Exception as e:
            self.log(f"⚠️ [Bilibili Bangumi] Scan error: {e}")
            return None

    # ------------------ METADATA PREVIEW ------------------
    def start_preview_info(self):
        raw_url = self.entry_url.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "No URL", "សូមបញ្ចូល Video Link ឬបើក Browser ដើម្បីចាប់វីដេអូជាមុនសិន!")
            return

        url = normalize_video_url(raw_url)
        if url != raw_url:
            self.entry_url.setText(url)
            self.log(f"🔄 [Downloader] បានសម្រួល Link ស្វ័យប្រវត្ត: {url}")

        self.lbl_prog_title.setText(f"🔍 Analyzing video metadata: {url[:50]}...")
        self.lbl_thumb.setText("⏳ Loading...")
        if self.lbl_source_url:
            self.lbl_source_url.setText(url)
        self.log(f"🔍 [Downloader] កំពុងវិភាគ និងទាញយកជម្រើសគុណភាពទាំងអស់ (Analyzing URL): {url}")

        def worker():
            try:
                if not yt_dlp:
                    raise Exception("yt-dlp is not installed")

                # Configure yt-dlp to support both playlists and single videos
                ydl_opts = {
                    "extract_flat": "in_playlist",
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                    "nocheckcertificate": True,
                    "socket_timeout": 15,
                    "http_headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                    }
                }
                ref = get_custom_referer(url)
                if ref:
                    ydl_opts["http_headers"]["Referer"] = ref

                # Proxy / Fake VPN Geo-Bypass Configuration
                proxy_val = getattr(self, "entry_proxy", None) and self.entry_proxy.text().strip()
                if proxy_val:
                    ydl_opts["proxy"] = proxy_val
                    self.log(f"🛡️ [Proxy] ប្រើប្រាស់ Proxy: {proxy_val}")

                use_fake_vpn = getattr(self, "check_fake_vpn", None) and self.check_fake_vpn.isChecked()
                if use_fake_vpn or not proxy_val:
                    ydl_opts["geo_bypass"] = True
                    ydl_opts["geo_bypass_country"] = "CN"
                    ydl_opts["http_headers"]["X-Forwarded-For"] = "116.228.89.24"
                    ydl_opts["http_headers"]["Client-IP"] = "116.228.89.24"
                    ydl_opts["http_headers"]["X-Real-IP"] = "116.228.89.24"

                # Attach FFmpeg location if available
                ff_bin = get_ffmpeg_binary_path()
                if ff_bin:
                    ydl_opts["ffmpeg_location"] = ff_bin

                cookie_path = self._get_active_cookie_file()
                if cookie_path:
                    ydl_opts["cookiefile"] = cookie_path

                # Auto-detect web-only streaming platforms (Sabayflix, KH Diamond, etc.)
                browser_only_domains = [
                    "sabayflix.net", "khdiamond.net", "kolabkhmer.com", "phumikhmer.me", "merlmovie.com"
                ]
                if any(dom in url.lower() for dom in browser_only_domains):
                    self.log(f"🎬 [Web-Player Notice] វេបសាយនេះ ({url[:45]}...) ជា Web Streaming Portal:")
                    self.log("💡 ប្រសិនបើត្រូវការចាប់យក Stream (.m3u8) ដោយផ្ទាល់ លោកអ្នកអាចចុចប៊ូតុង '🌐 Open Browser (Sniffer)' បានគ្រប់ពេល!")

                info = None
                if any(dom in url.lower() for dom in ["hongguoduanju.com", "novelquickapp.com"]):
                    self.log(f"🎬 [Hongguo] កំពុងស្កែនគ្រប់ភាគក្នុងរឿង (Scanning drama episodes)...")
                    info = self._extract_hongguo_series(url)
                elif "stardusttv.net" in url:
                    self.log(f"🎬 [StardustTV] កំពុងស្កែនគ្រប់ភាគក្នុងរឿង (Scanning drama episodes)...")
                    info = self._extract_stardust_series(url)
                elif "kisskh." in url.lower():
                    self.log(f"🎬 [KissKH] កំពុងស្កែនព័ត៌មានរឿង និងភាគទាំងអស់ (Scanning KissKH Asian Drama)...")
                    info = self._extract_kisskh_series(url)
                elif "hainanyuyue.com" in url.lower():
                    self.log(f"🎬 [Hainan Yuyue] កំពុងស្កែនព័ត៌មានរឿង និងភាគទាំងអស់ (Scanning Hainan Yuyue Drama)...")
                    info = self._extract_hainanyuyue_series(url)
                elif (("bilibili.com" in url.lower() or "b23.tv" in url.lower()) and
                      re.search(r'/(?:ep|ss)\d+', url.lower())):
                    self.log(f"🎬 [Bilibili Bangumi] កំពុងស្កែនព័ត៌មានរឿងភាគ និងបញ្ជីភាគទាំងអស់...")
                    info = self._extract_bilibili_bangumi(url)
                elif "sabayflix.net" in url.lower():
                    self.log(f"🎬 [SabayFlix] កំពុងស្កែនព័ត៌មានរឿង និងទិន្នន័យ SabayFlix...")
                    info = self._extract_sabayflix_series(url)
                elif "khdiamond.net" in url.lower():
                    self.log(f"🎬 [KH Diamond] កំពុងស្កែនព័ត៌មានរឿង និងបញ្ជីភាគទាំងអស់ (Scanning KH Diamond Series)...")
                    info = self._extract_khdiamond_series(url)
                elif any(d in url.lower() for d in ["dramaboxdb.com", "dramabox.com", "dramaboxapp.com"]):
                    from services.downloader.extractors.dramabox import DramaBoxExtractor
                    cookie_path = self._get_active_cookie_file()
                    db_ex = DramaBoxExtractor(log_callback=self.log)
                    info = db_ex.extract_series(url, cookie_file=cookie_path)
                elif any(d in url.lower() for d in ["t.me/", "telegram.me/", "pinterest.com", "pin.it", "pngtree.com", "facebook.com", "fb.watch", "instagram.com"]):
                    from services.downloader.extractors.universal_social import UniversalSocialExtractor
                    cookie_path = self._get_active_cookie_file()
                    social_ex = UniversalSocialExtractor(log_callback=self.log)
                    info = social_ex.extract_series(url, cookie_file=cookie_path)

                if not info:
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                    except Exception as ydl_e:
                        if any(sd in url.lower() for sd in ["facebook.com", "fb.watch", "instagram.com", "t.me", "pngtree.com"]):
                            self.log(f"🔒 [Sniffer Notice] Link នេះត្រូវបានការពារ ឬទាមទារ Login គណនី (Protected Media):")
                            self.log("   👉 សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ខាងលើ ដើម្បីបើកទំព័រនេះ នោះប្រព័ន្ធនឹងចាប់យក Stream / Image ស្វ័យប្រវត្តិ!")
                        raise ydl_e
                self.current_info = info

                is_playlist = (
                    info.get("_type") == "playlist" or
                    (bool(info.get("entries")) and not info.get("formats"))
                )

                entries = []
                if is_playlist:
                    self.is_playlist = True
                    entries = list(info.get("entries") or [])
                    self.playlist_entries = entries
                    playlist_title = info.get("title") or "Playlist"
                    uploader = info.get("uploader") or info.get("channel") or "Unknown"

                    sample_formats = []
                    sample_dur = 0
                    sample_thumb = None
                    sample_subs = {}
                    sample_auto_subs = {}

                    if entries:
                        first_e = entries[0]
                        first_url = first_e.get("url") or (f"https://www.youtube.com/watch?v={first_e.get('id')}" if first_e.get("id") else None)
                        sample_thumb = (first_e.get("thumbnails") and first_e["thumbnails"][-1].get("url")) or first_e.get("thumbnail")
                        sample_dur = float(first_e.get("duration", 0) or 0)
                        if info.get("is_stardust") or info.get("is_kisskh") or info.get("is_bilibili_bangumi") or info.get("is_dramabox"):
                            sample_formats = info.get("formats", [])
                            sample_dur = 3600 if info.get("is_kisskh") else (float(entries[0].get("duration", 0) or 120))
                        elif first_url:
                            try:
                                ydl_sample_opts = dict(ydl_opts)
                                ydl_sample_opts["extract_flat"] = False
                                with yt_dlp.YoutubeDL(ydl_sample_opts) as ydl_s:
                                    s_info = ydl_s.extract_info(first_url, download=False)
                                    sample_formats = s_info.get("formats", [])
                                    sample_thumb = s_info.get("thumbnail") or sample_thumb
                                    sample_dur = float(s_info.get("duration", 0) or sample_dur)
                                    sample_subs = s_info.get("subtitles", {})
                                    sample_auto_subs = s_info.get("automatic_captions", {})
                            except Exception as sample_err:
                                print(f"Sample video format error: {sample_err}")

                    title = f"📋 {playlist_title} ({len(entries)} Videos)"
                    dur = sample_dur if sample_dur > 0 else (float(info.get("duration", 0) or 0) or 90)
                    formats = sample_formats if sample_formats else (info.get("formats") or [])
                    subs = sample_subs
                    auto_subs = sample_auto_subs
                    thumb_url = sample_thumb or info.get("thumbnail")
                else:
                    self.is_playlist = False
                    self.playlist_entries = []
                    title = info.get("title", "Untitled")
                    dur = float(info.get("duration", 0) or 0)
                    uploader = info.get("uploader") or info.get("channel") or "Unknown"
                    subs = info.get("subtitles", {})
                    auto_subs = info.get("automatic_captions", {})
                    formats = info.get("formats", [])
                    thumb_url = info.get("thumbnail")

                # 1. Available subtitles
                sub_langs = list(subs.keys())
                auto_langs = list(auto_subs.keys())

                # 2. Extract accurate best audio stream size
                formats = info.get("formats", [])
                audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
                best_audio = None
                for af in sorted(audio_formats, key=lambda x: (x.get("filesize") or 0, x.get("tbr") or 0), reverse=True):
                    best_audio = af
                    break
                audio_bytes = 0
                if best_audio:
                    audio_bytes = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0
                    if not audio_bytes and best_audio.get("tbr") and dur > 0:
                        audio_bytes = int(min(best_audio["tbr"], 160) * 1000 * dur / 8)
                if not audio_bytes and dur > 0:
                    audio_bytes = int(128 * 1000 * dur / 8)

                # 3. Parse all video heights into standard resolution buckets with REAL file sizes
                res_map = {}
                std_buckets = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144]
                bucket_labels = {
                    4320: "8K Ultra HD", 2160: "4K Ultra HD", 1440: "2K Quad HD",
                    1080: "Full HD", 720: "HD Standard", 480: "SD Standard",
                    360: "SD 360p", 240: "240p", 144: "144p"
                }

                # High accuracy exact format selection via yt-dlp build_format_selector
                used_exact_selector = False
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
                                    v_f = rf[0]
                                    a_f = rf[1]
                                    actual_h = v_f.get("height") or std_h
                                    if actual_h < std_h * 0.7 and std_h > 720:
                                        continue
                                    v_sz = v_f.get("filesize") or v_f.get("filesize_approx") or 0
                                    a_sz = a_f.get("filesize") or a_f.get("filesize_approx") or audio_bytes
                                    fps = v_f.get("fps") or 30
                                    if not v_sz and dur > 0:
                                        cap_kbps = {2160: 15000, 1440: 8000, 1080: 3000, 720: 1500, 480: 600, 360: 350, 240: 200}.get(std_h, 1000)
                                        real_br = min(v_f.get("vbr") or v_f.get("tbr") or cap_kbps, cap_kbps * 1.5)
                                        v_sz = int(real_br * 1000 * dur / 8)
                                    res_map[std_h] = {
                                        "video_size": v_sz,
                                        "audio_size": a_sz,
                                        "size": v_sz + a_sz,
                                        "fps": fps,
                                        "label": bucket_labels.get(std_h, f"{std_h}p"),
                                        "format_id": v_f.get("format_id"),
                                        "actual_h": actual_h
                                    }
                                else:
                                    actual_h = ch.get("height") or std_h
                                    if actual_h < std_h * 0.7 and std_h > 720:
                                        continue
                                    sz = ch.get("filesize") or ch.get("filesize_approx") or 0
                                    if not sz and dur > 0:
                                        cap_kbps = {2160: 16000, 1440: 9000, 1080: 3500, 720: 1800, 480: 800, 360: 450, 240: 250}.get(std_h, 1200)
                                        real_br = min(ch.get("tbr") or cap_kbps, cap_kbps * 1.5)
                                        sz = int(real_br * 1000 * dur / 8)
                                    res_map[std_h] = {
                                        "video_size": sz,
                                        "audio_size": 0,
                                        "size": sz,
                                        "fps": ch.get("fps") or 30,
                                        "label": bucket_labels.get(std_h, f"{std_h}p"),
                                        "format_id": ch.get("format_id"),
                                        "actual_h": actual_h
                                    }
                        if res_map:
                            used_exact_selector = True
                    except Exception as sim_err:
                        print(f"Format simulation error: {sim_err}")

                if not used_exact_selector:
                    for f in formats:
                        h = f.get("height")
                        if not h or f.get("vcodec") == "none":
                            continue
                        fs = f.get("filesize") or f.get("filesize_approx")
                        if not fs and f.get("tbr") and dur > 0:
                            cap_kbps = {2160: 15000, 1440: 8000, 1080: 3000, 720: 1500, 480: 600, 360: 350, 240: 200}.get(h, 1000)
                            real_br = min(f.get("tbr") or cap_kbps, cap_kbps * 1.5)
                            fs = int(real_br * 1000 * dur / 8)
                        total_sz = (fs or 0) + (0 if f.get("acodec") != "none" else audio_bytes)
                        fps = f.get("fps") or 30
                        closest = min(std_buckets, key=lambda b: abs(b - h))
                        if closest not in res_map or (fs and not res_map[closest].get("has_real_fs")):
                            res_map[closest] = {
                                "video_size": fs or 0,
                                "audio_size": audio_bytes,
                                "size": total_sz,
                                "fps": fps,
                                "label": bucket_labels.get(closest, f"{closest}p"),
                                "format_id": f.get("format_id"),
                                "actual_h": h,
                                "has_real_fs": bool(f.get("filesize"))
                            }

                # 4. Build Quality ComboBox items
                combo_items = []
                self._format_data = {}

                if info.get("is_image"):
                    img_fmt = (info.get("formats") or [{}])[0]
                    ext = img_fmt.get("ext", "png").upper()
                    img_lbl = f"🖼️ Original Lossless Graphic / Image ({ext} Pristine Quality)"
                    combo_items.append(img_lbl)
                    self._format_data[img_lbl] = "original"
                    size_summaries = [f"Graphic: {ext} HD"]
                else:
                    # A) Best Available Auto (Always on top)
                    best_lbl = "🌟 Best Available (Auto Highest Quality)"
                    combo_items.append(best_lbl)
                    self._format_data[best_lbl] = "bestvideo+bestaudio/best"

                    # B) Video resolutions sorted highest to lowest
                    size_summaries = []
                    for std_h in sorted(res_map.keys(), reverse=True):
                        item = res_map[std_h]
                        v_sz = item.get("video_size", 0)
                        tot_sz = item.get("size", 0)
                        v_str = f"{v_sz / (1024**3):.2f} GB" if v_sz >= 1024**3 else f"{v_sz / (1024**2):.1f} MB"
                        tot_str = f"{tot_sz / (1024**3):.2f} GB" if tot_sz >= 1024**3 else f"{tot_sz / (1024**2):.1f} MB"
                        fps_str = " 60fps" if item["fps"] >= 50 else ""
                        q_label = item["label"]

                        if v_sz > 0 and tot_sz > v_sz:
                            sz_display = f"~ {v_str} (Video) / {tot_str} (Full)"
                        else:
                            sz_display = f"~ {tot_str}"

                        lbl = f"🎬 {std_h}p{fps_str} ({q_label}) {sz_display}"
                        combo_items.append(lbl)

                        # High quality format selector for yt-dlp
                        self._format_data[lbl] = f"bestvideo[height<={std_h+40}]+bestaudio/best[height<={std_h+40}]"
                        if len(size_summaries) < 4:
                            size_summaries.append(f"{std_h}p: {v_str if v_sz > 0 else tot_str}")

                    # C) Audio Formats (MP3, M4A, WAV)
                    aud_sz_str = f"{audio_bytes / (1024**3):.2f} GB" if audio_bytes >= 1024**3 else f"{audio_bytes / (1024**2):.1f} MB"
                    mp3_lbl = f"🎵 MP3 Audio Only (320 kbps High Quality) ~ {aud_sz_str}"
                    m4a_lbl = f"🎵 M4A Audio Only (Original AAC Stream) ~ {aud_sz_str}"
                    wav_sz = audio_bytes * 3.5  # Approximate uncompressed WAV size
                    wav_sz_str = f"{wav_sz / (1024**3):.2f} GB" if wav_sz >= 1024**3 else f"{wav_sz / (1024**2):.1f} MB"
                    wav_lbl = f"🎵 WAV Audio Only (Studio Lossless PCM) ~ {wav_sz_str}"

                    combo_items.append(mp3_lbl)
                    self._format_data[mp3_lbl] = "bestaudio/best"
                    combo_items.append(m4a_lbl)
                    self._format_data[m4a_lbl] = "bestaudio[ext=m4a]/bestaudio/best"
                    combo_items.append(wav_lbl)
                    self._format_data[wav_lbl] = "bestaudio/best"

                # 5. Smart Subtitle Combo Items (English + Chinese by default, avoid 80+ files)
                sub_combo_items = [
                    "🌟 Smart Auto (English + Chinese តែប៉ុណ្ណោះ)",
                    "English (en)",
                    "Chinese Simplified (zh-Hans)",
                    "Chinese Traditional (zh-Hant)",
                    "All Available Subtitles (គ្រប់ភាសាទាំងអស់)",
                    "No Subtitles (មិនទាញយក)"
                ]

                # 6. Fetch Thumbnail Image
                pixmap = None
                thumb_url = info.get("thumbnail")
                if thumb_url:
                    try:
                        ref = get_custom_referer(thumb_url) or get_custom_referer(url)
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                        }
                        if ref:
                            headers["Referer"] = ref
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        req = urllib.request.Request(thumb_url, headers=headers)
                        raw_data = urllib.request.urlopen(req, context=ctx, timeout=8).read()
                        qimg = QImage.fromData(raw_data)
                        if not qimg.isNull():
                            pixmap = QPixmap.fromImage(qimg)
                    except Exception as th_err:
                        print(f"Thumbnail load error: {th_err}")

                def _apply_preview():
                    # 1. Tags / Category badges
                    tags = info.get("tags") or []
                    if not tags:
                        if info.get("is_hongguo"):
                            tags = ["短剧", "红果", "HD"]
                        elif info.get("is_hainanyuyue"):
                            tags = ["短剧", "海南愉悦", "720P HD"]
                        elif info.get("is_kisskh"):
                            tags = ["Asian Drama", "KissKH", "1080p HD"]
                        elif info.get("is_stardust"):
                            tags = ["Short Drama", "StardustTV", "Vertical HD"]
                        elif info.get("is_dramabox"):
                            tags = ["短剧", "DramaBox", f"{len(entries)} ភាគ", "Vertical HD"]
                        elif info.get("categories"):
                            tags = info.get("categories")[:3]
                        elif is_playlist:
                            tags = ["Playlist", f"{len(entries)} ភាគ"]
                        else:
                            tags = ["Video", "HD"]
                    self._render_tags(tags, url=url)

                    # 2. Synopsis / Description
                    desc = info.get("description") or ""
                    if desc:
                        self.desc_box.setVisible(True)
                        self._full_description = desc
                        self._desc_expanded = False
                        self._update_desc_text()
                    else:
                        self.desc_box.setVisible(False)

                    if is_playlist:
                        display_title = title
                        if info.get("is_hongguo"):
                            display_title = info.get("title", "").replace("🎬 ", "").replace(" (红果短剧)", "")
                        elif info.get("is_hainanyuyue"):
                            display_title = info.get("title", "").replace("🎬 ", "").replace(" (海南愉悦)", "")
                        elif info.get("is_bilibili_bangumi"):
                            display_title = info.get("title", "").replace("🎬 ", "").replace(" (Bilibili)", "")
                        elif info.get("is_dramabox"):
                            display_title = info.get("title", "").replace("🎬 ", "").replace(" (DramaBox)", "")
                        self.lbl_prev_title.setText(display_title)
                        self.lbl_prev_info.setText(f"📋 Playlist: {len(entries)} វីដេអូ | Creator: {uploader}")
                        self.lbl_playlist_title.setText(f"📋 Playlist Items ({len(entries)} Videos):")
                        self.lbl_episodes_title.setText("选集")

                        # Populate table_playlist
                        self.table_playlist.blockSignals(True)
                        self.table_playlist.setRowCount(0)
                        for idx, e in enumerate(entries):
                            r = self.table_playlist.rowCount()
                            self.table_playlist.insertRow(r)

                            # Col 0: Checkbox + Part number
                            chk_item = QTableWidgetItem(f"#{idx+1}")
                            chk_item.setCheckState(Qt.CheckState.Checked)
                            chk_item.setData(Qt.ItemDataRole.UserRole, idx)
                            self.table_playlist.setItem(r, 0, chk_item)

                            # Col 1: Title
                            e_title = e.get("title") or f"Video {idx+1}"
                            t_item = QTableWidgetItem(e_title)
                            t_item.setToolTip(e_title)
                            self.table_playlist.setItem(r, 1, t_item)

                            # Col 2: Duration
                            e_dur = float(e.get("duration", 0) or 0)
                            d_str = format_duration_str(e_dur) if e_dur > 0 else "--:--"
                            dur_item = QTableWidgetItem(d_str)
                            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            self.table_playlist.setItem(r, 2, dur_item)

                            self.table_playlist.setRowHeight(r, 26)
                        self.table_playlist.blockSignals(False)

                        # Auto-select target episode if specified in URL (e.g. Episode 2)
                        t_idx = info.get("target_index", 0)
                        self.selected_playlist_index = t_idx if 0 <= t_idx < len(entries) else 0

                        # Render range tabs and modern square episode grid
                        self._render_episode_ranges(len(entries), current_ep_index=self.selected_playlist_index)
                        self._set_episode_view_mode("grid")

                        if 0 <= self.selected_playlist_index < len(entries):
                            self.table_playlist.selectRow(self.selected_playlist_index)
                            sel_item = self.table_playlist.item(self.selected_playlist_index, 0)
                            if sel_item:
                                self._on_playlist_item_clicked(sel_item)

                        self.episodes_box.setVisible(True)
                        self.group_pl_mode.setVisible(True)
                        self._update_download_button_text()

                        # Resolve true episode durations in background for Hongguo
                        if info.get("is_hongguo"):
                            self._resolve_hongguo_durations_background(info.get("id"), entries)
                    else:
                        self.lbl_prev_title.setText(title)
                        dur_text = f"⏱️ Duration: {format_timestamp(dur)}" if not info.get("is_image") else "🖼️ Format: Lossless Graphic"
                        self.lbl_prev_info.setText(f"{dur_text} | 👤 Creator: {uploader}")
                        self.episodes_box.setVisible(False)
                        self.group_pl_mode.setVisible(False)
                        if info.get("is_image"):
                            self.btn_download.setText("📥 Download Image (Lossless HD)")
                        else:
                            self.btn_download.setText("Download Video / Audio")
                    all_subs_display = sub_langs[:5] if sub_langs else (auto_langs[:4] if auto_langs else ["None"])
                    self.lbl_prev_cc.setText(f"💬 Subtitles / CC: {', '.join(all_subs_display)}")
                    self.lbl_prev_size.setText(f"📦 Estimated Sizes: {' | '.join(size_summaries) if size_summaries else '--'}")
                    if self.lbl_source_url:
                        self.lbl_source_url.setText(url)
                    self.lbl_prog_title.setText("✅ Analyzed successfully!")

                    if pixmap:
                        self._apply_auto_fit_thumbnail(pixmap)
                    else:
                        self.lbl_thumb.setText("🖼️ Preview Ready")

                    # Update Quality ComboBox
                    self.combo_quality.clear()
                    self.combo_quality.addItems(combo_items)

                    # Default to 1080p if available, else Best Available
                    selected_idx = 0
                    for idx, ci in enumerate(combo_items):
                        if "1080p" in ci:
                            selected_idx = idx
                            break
                    self.combo_quality.setCurrentIndex(selected_idx)

                    # Update Subtitle Language ComboBox
                    self.combo_sub_lang.clear()
                    self.combo_sub_lang.addItems(sub_combo_items)

                    if info.get("is_image"):
                        img_ext = (info.get("formats") or [{}])[0].get("ext", "png").upper()
                        self.log(f"✅ [Downloader] វិភាគជោគជ័យ: \"{title[:50]}\" | 🖼️ រូបភាពច្បាស់ Lossless HD ({img_ext})")
                    else:
                        self.log(f"✅ [Downloader] វិភាគជោគជ័យ: \"{title[:50]}\" | រកឃើញគុណភាព {len(res_map)} កម្រិត")
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
                    self.log("⚠️ [Douyin Notice] វីដេអូ Douyin នេះតម្រូវឱ្យមាន Cookies (cookies.txt) ដោយសារ anti-bot protection!")
                    self.log("💡 វិធីដោះស្រាយ: ចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីចាប់យកទាំង Video និង Cookies ស្វ័យប្រវត្ត!")
                elif "bilibili" in url.lower() or "initial state" in err_str.lower():
                    self.log("💡 [Bilibili Notice] Bilibili តម្រូវឱ្យទាញយកតាម Session របស់ Browser:")
                    self.log("   👉 1. ចុចប៊ូតុង '🌐 Open Browser (Sniffer)'")
                    self.log("   👉 2. ពេលវីដេអូចាក់ ចុចលើផ្ទាំង '📡 Network Processing' ដើម្បីទាញយក .m4s Stream ផ្ទាល់ ឬចុច '💾 Save Cookies'!")
                elif "geo restriction" in err_str.lower() or "not available from your location" in err_str.lower():
                    self.log("🌏 [Geo-Restriction Notice] វីដេអូនេះជាប់ការកំណត់តំបន់ (Geo-restricted to Mainland China) ដោយសារបញ្ហារក្សាសិទ្ធិ:")
                    self.log("   👉 1. បើកប្រើប្រាស់ VPN ប្រទេសចិន (China VPN/Proxy) ឬកំណត់ Proxy ក្នុងកម្មវិធី។")
                    self.log("   👉 2. ឬចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីចាក់វីដេអូនោះ នោះកម្មវិធី Sniffer នឹងចាប់យក Network Stream (.m3u8/.mp4) មកទាញយកដោយស្វ័យប្រវត្តិ!")
                elif "unsupported url" in err_str.lower():
                    self.log("💡 [Sniffer Notice] Link នេះដំណើរការលើ Client-Side Web Player:")
                    self.log("   👉 សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីបើកមើល និងឱ្យប្រព័ន្ធចាប់យក Stream (.m3u8) ដោយស្វ័យប្រវត្តិ!")
                elif "iqiyi" in url.lower() or "can't find any video" in err_str.lower():
                    self.log("💡 [iQiyi Notice] វីដេអូ iQiyi នេះតម្រូវឱ្យទាញយកតាម Session របស់ Browser:")
                    self.log("   👉 សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីបើកទំព័រនេះ រួច Sniffer នឹងចាប់យក Stream ដោយស្វ័យប្រវត្តិ!")

        threading.Thread(target=worker, daemon=True).start()

    # ------------------ DOWNLOAD ENGINE ------------------
    def start_download(self, auto_open: bool = False):
        raw_url = self.entry_url.text().strip()
        if not raw_url:
            QMessageBox.warning(self, "No URL", "សូមបញ្ចូល Video Link ឬបើក Browser ដើម្បីចាប់វីដេអូជាមុនសិន!")
            return
        if self.is_downloading:
            return

        url = normalize_video_url(raw_url)
        if url != raw_url:
            self.entry_url.setText(url)
            self.log(f"🔄 [Downloader] បានសម្រួល Link ស្វ័យប្រវត្ត: {url}")

        base_out_dir = self.entry_folder.text().strip() or self.download_dir
        quality_label = self.combo_quality.currentText()
        format_type_choice = self.combo_format_type.currentText()
        selected_format = self._format_data.get(quality_label, "bestvideo+bestaudio/best")
        download_subs = self.check_download_subs.isChecked()
        sub_lang_choice = self.combo_sub_lang.currentText()
        save_url_enabled = self.check_save_url.isChecked() if hasattr(self, "check_save_url") else True

        # Threads count
        thread_choice = self.combo_threads.currentText()
        num_threads = 16 if "16" in thread_choice else (8 if "8" in thread_choice else (4 if "4" in thread_choice else 1))

        # Check if user specifically requested Audio Only or Subtitle Only
        is_subtitles_only = "Subtitles Only" in format_type_choice
        is_audio = ("Audio" in format_type_choice or "Audio" in quality_label or "MP3" in quality_label or selected_format.startswith("bestaudio")) and not is_subtitles_only

        self.is_downloading = True
        self.cancel_download = False
        self.btn_download.setEnabled(False)
        self.btn_download_open.setEnabled(False)
        self.btn_stop.setEnabled(True)

        mode_name = "Subtitles Only" if is_subtitles_only else ("Audio Track" if is_audio else "Video + Audio")
        self.log(f"🚀 [Downloader] ចាប់ផ្ដើមទាញយក: {mode_name} | {quality_label} | Turbo: {num_threads} Streams")

        def worker():
            try:
                cookie_path = self._get_active_cookie_file()
                ff_bin = get_ffmpeg_binary_path()

                # 1. Fetch info if not cached
                info = self.current_info
                proxy_val = getattr(self, "entry_proxy", None) and self.entry_proxy.text().strip()
                use_fake_vpn = getattr(self, "check_fake_vpn", None) and self.check_fake_vpn.isChecked()

                if not info:
                    if "hongguoduanju.com" in url:
                        info = self._extract_hongguo_series(url)
                    elif "stardusttv.net" in url:
                        info = self._extract_stardust_series(url)
                    elif "kisskh." in url.lower():
                        info = self._extract_kisskh_series(url)
                    elif "hainanyuyue.com" in url.lower():
                        info = self._extract_hainanyuyue_series(url)
                    elif "sabayflix.net" in url.lower():
                        info = self._extract_sabayflix_series(url)
                    else:
                        check_opts = {"quiet": True, "skip_download": True, "nocheckcertificate": True}
                        if ff_bin:
                            check_opts["ffmpeg_location"] = ff_bin
                        if cookie_path:
                            check_opts["cookiefile"] = cookie_path
                        if proxy_val:
                            check_opts["proxy"] = proxy_val
                        if use_fake_vpn or not proxy_val:
                            check_opts["geo_bypass"] = True
                            check_opts["geo_bypass_country"] = "CN"
                        with yt_dlp.YoutubeDL(check_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                    self.current_info = info

                raw_title = info.get("title", "downloaded_movie")
                folder_name = sanitize_folder_name(raw_title)
                movie_folder = os.path.join(base_out_dir, folder_name)
                os.makedirs(movie_folder, exist_ok=True)

                self.log(f"📁 [Downloader] រក្សាទុកក្នុង Folder: {folder_name}")

                download_cover = getattr(self, "check_download_cover", None) and self.check_download_cover.isChecked()
                is_cover_only = "Cover Only" in format_type_choice or "Cover / Poster" in format_type_choice

                # 2. Cover / Poster Image Download
                saved_cover = None
                cover_url = info.get("thumbnail") or info.get("cover_url") or info.get("poster")
                if (download_cover or is_cover_only) and cover_url:
                    self.log(f"🖼️ [Cover] កំពុងទាញយករូប Cover/Poster គុណភាពខ្ពស់ដាក់ក្នុង Folder...")
                    ref_hdr = get_custom_referer(url)
                    c_headers = {"Referer": ref_hdr} if ref_hdr else {}
                    saved_cover = download_cover_image(cover_url, movie_folder, base_filename="cover", headers=c_headers)
                    if saved_cover:
                        self.log(f"✅ [Cover] បានរក្សាទុករូប Cover: {os.path.basename(saved_cover)}")

                if is_cover_only:
                    def _show_cover_done():
                        c_name = os.path.basename(saved_cover) if saved_cover else "cover.jpg"
                        self.lbl_prog_title.setText(f"🎉 Cover Image Downloaded: {c_name}")
                        self.prog_bar.setValue(100)
                    self.run_on_main(_show_cover_done)
                    self.is_downloading = False
                    def _reset_cover_btn():
                        self.btn_download.setEnabled(True)
                        self.btn_download_open.setEnabled(True)
                        self.btn_stop.setEnabled(False)
                    self.run_on_main(_reset_cover_btn)
                    return

                out_tmpl = os.path.join(movie_folder, f"{folder_name}.%(ext)s")

                # 2. Build yt-dlp options
                opts = {
                    "format": selected_format,
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
                    "progress_hooks": [self._progress_hook]
                }

                if proxy_val:
                    opts["proxy"] = proxy_val
                if use_fake_vpn or not proxy_val:
                    opts["geo_bypass"] = True
                    opts["geo_bypass_country"] = "CN"
                    opts["http_headers"]["X-Forwarded-For"] = "116.228.89.24"
                    opts["http_headers"]["Client-IP"] = "116.228.89.24"
                    opts["http_headers"]["X-Real-IP"] = "116.228.89.24"

                if info and info.get("is_hongguo"):
                    # Custom direct downloader for Hongguo drama episodes
                    targets = []
                    if self.radio_pl_single.isChecked():
                        idx = max(0, min(self.selected_playlist_index, len(self.playlist_entries) - 1)) if self.playlist_entries else 0
                        if self.playlist_entries:
                            targets = [self.playlist_entries[idx]]
                    elif self.radio_pl_selected.isChecked():
                        max_r = min(self.table_playlist.rowCount(), len(self.playlist_entries))
                        for r in range(max_r):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                targets.append(self.playlist_entries[r])
                    else:
                        targets = list(self.playlist_entries)

                    total_t = len(targets)
                    if total_t == 0:
                        self.log("⚠️ [Downloader] មិនមានភាគណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                        self.is_downloading = False
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        return

                    self.log(f"🎬 [Hongguo] ចាប់ផ្ដើមទាញយក {total_t} ភាគទៅកាន់: {movie_folder}")
                    for idx, ep in enumerate(targets, 1):
                        if getattr(self, "cancel_download", False):
                            self.log("🛑 [Downloader] បានផ្អាកការទាញយក!")
                            break
                        ep_title = ep.get("title", f"Episode {idx}")
                        ep_clean_title = sanitize_folder_name(ep_title)
                        out_file = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.mp4")
                        stream_url = ep.get("url")
                        page_ref = ep.get("webpage_url") or url

                        self.log(f"📥 [{idx}/{total_t}] កំពុងទាញយក: {ep_title}...")
                        self.run_on_main(lambda i=idx, t=total_t, tit=ep_title: self.lbl_prog_title.setText(f"Part [{i}/{t}]: {tit}"))

                        ep_vid = ep.get("id")
                        ep_series_id = ep.get("series_id") or info.get("id")
                        self._download_hongguo_episode(ep_series_id, ep_vid, out_file, referer=page_ref, part_idx=idx, total_parts=total_t)

                    self.log(f"🎉 [Hongguo] បានទាញយកចប់សព្វគ្រប់ {len(targets)} ភាគ!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                if info and info.get("is_stardust"):
                    # Custom direct downloader for StardustTV drama episodes via yt-dlp native m3u8
                    targets = []
                    if self.radio_pl_single.isChecked():
                        idx = max(0, min(self.selected_playlist_index, len(self.playlist_entries) - 1)) if self.playlist_entries else 0
                        if self.playlist_entries:
                            targets = [self.playlist_entries[idx]]
                    elif self.radio_pl_selected.isChecked():
                        max_r = min(self.table_playlist.rowCount(), len(self.playlist_entries))
                        for r in range(max_r):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                targets.append(self.playlist_entries[r])
                    else:
                        targets = list(self.playlist_entries)

                    total_t = len(targets)
                    if total_t == 0:
                        self.log("⚠️ [Downloader] មិនមានភាគណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                        self.is_downloading = False
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        return

                    self.log(f"🎬 [StardustTV] ចាប់ផ្ដើមទាញយក {total_t} ភាគទៅកាន់: {movie_folder}")
                    for idx, ep in enumerate(targets, 1):
                        if getattr(self, "cancel_download", False):
                            self.log("🛑 [Downloader] បានផ្អាកការទាញយក!")
                            break
                        ep_title = ep.get("title", f"Episode {idx}")
                        ep_clean_title = sanitize_folder_name(ep_title)
                        out_path = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.%(ext)s")
                        stream_url = ep.get("url")

                        self.log(f"📥 [{idx}/{total_t}] កំពុងទាញយក: {ep_title}...")
                        self.run_on_main(lambda i=idx, t=total_t, tit=ep_title: self.lbl_prog_title.setText(f"Part [{i}/{t}]: {tit}"))

                        ep_opts = dict(opts)
                        ep_opts["outtmpl"] = out_path
                        ep_opts["http_headers"] = {"Referer": "https://www.stardusttv.net/", "User-Agent": "Mozilla/5.0"}
                        if ff_bin:
                            ep_opts["ffmpeg_location"] = ff_bin

                        with yt_dlp.YoutubeDL(ep_opts) as ydl:
                            ydl.download([stream_url])

                    self.log(f"🎉 [StardustTV] បានទាញយកចប់សព្វគ្រប់ {len(targets)} ភាគ!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                if info and info.get("is_kisskh"):
                    # Custom direct downloader for KissKH drama episodes via yt-dlp native m3u8
                    targets = []
                    if self.radio_pl_single.isChecked():
                        idx = max(0, min(self.selected_playlist_index, len(self.playlist_entries) - 1)) if self.playlist_entries else 0
                        if self.playlist_entries:
                            targets = [self.playlist_entries[idx]]
                    elif self.radio_pl_selected.isChecked():
                        max_r = min(self.table_playlist.rowCount(), len(self.playlist_entries))
                        for r in range(max_r):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                targets.append(self.playlist_entries[r])
                    else:
                        targets = list(self.playlist_entries)

                    total_t = len(targets)
                    if total_t == 0:
                        self.log("⚠️ [Downloader] មិនមានភាគណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                        self.is_downloading = False
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        return

                    self.log(f"🎬 [KissKH] ចាប់ផ្ដើមទាញយក {total_t} ភាគទៅកាន់: {movie_folder}")
                    for idx, ep in enumerate(targets, 1):
                        if getattr(self, "cancel_download", False):
                            self.log("🛑 [Downloader] បានផ្អាកការទាញយក!")
                            break
                        ep_title = ep.get("title", f"Episode {idx}")
                        ep_clean_title = sanitize_folder_name(ep_title)
                        out_path = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.%(ext)s")

                        stream_url = ep.get("url")
                        is_stream = bool(stream_url and ("m3u8" in stream_url.lower() or ".mp4" in stream_url.lower() or "cdn" in stream_url.lower()))
                        if not is_stream and ep.get("webpage_url"):
                            self.log(f"🔍 [KissKH] កំពុងដោះសោ Stream សម្រាប់ {ep_title}...")
                            stream_url = self._resolve_kisskh_stream_silent(ep.get("webpage_url"))
                            if stream_url:
                                ep["url"] = stream_url

                        if not stream_url or ("kisskh." in stream_url.lower() and "m3u8" not in stream_url.lower()):
                            self.log(f"⚠️ [KissKH] មិនទាន់ដោះសោ Stream ភាគ {ep_title} បានឡើយ! សូមចុច '🌐 Open Browser (Sniffer)' ដើម្បីចាប់យក Stream (.m3u8) ស្វ័យប្រវត្តិ។")
                            continue

                        self.log(f"📥 [{idx}/{total_t}] កំពុងទាញយក: {ep_title}...")
                        self.run_on_main(lambda i=idx, t=total_t, tit=ep_title: self.lbl_prog_title.setText(f"Part [{i}/{t}]: {tit}"))

                        ep_opts = dict(opts)
                        ep_opts["outtmpl"] = out_path
                        ep_opts["format"] = "best/bestvideo+bestaudio"
                        ep_opts["http_headers"] = {
                            "Referer": "https://kisskh.do/",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        }
                        if ff_bin:
                            ep_opts["ffmpeg_location"] = ff_bin

                        with yt_dlp.YoutubeDL(ep_opts) as ydl:
                            ydl.download([stream_url])

                        # Auto-download KissKH Subtitle (.srt) if captured
                        sub_dl_url = ep.get("sub_url") or getattr(self, "_latest_kisskh_sub_url", None)
                        if sub_dl_url and isinstance(sub_dl_url, str) and sub_dl_url.startswith("http"):
                            srt_target = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.srt")
                            try:
                                self.log(f"📝 [KissKH Subtitle] កំពុងទាញយកឯកសារ Subtitle (.srt)...")
                                s_ctx = ssl.create_default_context()
                                s_ctx.check_hostname = False
                                s_ctx.verify_mode = ssl.CERT_NONE
                                s_req = urllib.request.Request(
                                    sub_dl_url,
                                    headers={
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                                        "Referer": "https://kisskh.do/"
                                    }
                                )
                                with urllib.request.urlopen(s_req, context=s_ctx, timeout=12) as s_resp:
                                    srt_bytes = s_resp.read()
                                    with open(srt_target, "wb") as sf:
                                        sf.write(srt_bytes)
                                self.log(f"✅ [KissKH Subtitle] បានទាញយក Subtitle (.srt) ដោយជោគជ័យ: {os.path.basename(srt_target)}")
                            except Exception as srt_err:
                                self.log(f"⚠️ [KissKH Subtitle] មិនអាចទាញយក Subtitle បានទេ: {srt_err}")

                    self.log(f"🎉 [KissKH] បានទាញយកចប់សព្វគ្រប់ {len(targets)} ភាគ!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                if info and info.get("is_khdiamond"):
                    # Custom direct downloader for KH Diamond drama / anime episodes
                    targets = []
                    if self.radio_pl_single.isChecked():
                        idx = max(0, min(self.selected_playlist_index, len(self.playlist_entries) - 1)) if self.playlist_entries else 0
                        if self.playlist_entries:
                            targets = [self.playlist_entries[idx]]
                    elif self.radio_pl_selected.isChecked():
                        max_r = min(self.table_playlist.rowCount(), len(self.playlist_entries))
                        for r in range(max_r):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                targets.append(self.playlist_entries[r])
                    else:
                        targets = list(self.playlist_entries)

                    total_t = len(targets)
                    if total_t == 0:
                        self.log("⚠️ [Downloader] មិនមានភាគណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                        self.is_downloading = False
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        return

                    self.log(f"🎬 [KH Diamond] ចាប់ផ្ដើមទាញយក {total_t} ភាគទៅកាន់: {movie_folder}")
                    for idx, ep in enumerate(targets, 1):
                        if getattr(self, "cancel_download", False):
                            self.log("🛑 [Downloader] បានផ្អាកការទាញយក!")
                            break
                        ep_title = ep.get("title", f"Episode {idx}")
                        ep_clean_title = sanitize_folder_name(ep_title)
                        out_path = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.%(ext)s")

                        stream_url = ep.get("url")
                        is_stream = bool(stream_url and ("m3u8" in stream_url.lower() or ".mp4" in stream_url.lower()))
                        if not is_stream and ep.get("webpage_url"):
                            self.log(f"🔍 [KH Diamond] កំពុងដោះសោ Stream សម្រាប់ {ep_title}...")
                            stream_url = self._resolve_kisskh_stream_silent(ep.get("webpage_url"))
                            if stream_url:
                                ep["url"] = stream_url

                        if not stream_url or ("khdiamond." in stream_url.lower() and "m3u8" not in stream_url.lower()):
                            self.log(f"⚠️ [KH Diamond] មិនទាន់ដោះសោ Stream ភាគ {ep_title} បានឡើយ! សូមចុច '🌐 Open Browser (Sniffer)' ដើម្បីចាប់យក Stream (.m3u8) ស្វ័យប្រវត្តិ។")
                            continue

                        self.log(f"📥 [{idx}/{total_t}] កំពុងទាញយក: {ep_title}...")
                        self.run_on_main(lambda i=idx, t=total_t, tit=ep_title: self.lbl_prog_title.setText(f"Part [{i}/{t}]: {tit}"))

                        ep_opts = dict(opts)
                        ep_opts["outtmpl"] = out_path
                        ep_opts["format"] = "best/bestvideo+bestaudio"
                        ep_opts["http_headers"] = {
                            "Referer": "https://khdiamond.net/",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        }
                        if ff_bin:
                            ep_opts["ffmpeg_location"] = ff_bin

                        with yt_dlp.YoutubeDL(ep_opts) as ydl:
                            ydl.download([stream_url])

                    self.log(f"🎉 [KH Diamond] បានទាញយកចប់សព្វគ្រប់ {len(targets)} ភាគ!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                if info and info.get("is_dramabox"):
                    # Custom direct downloader for DramaBox Asian drama episodes
                    targets = []
                    if self.radio_pl_single.isChecked():
                        idx = max(0, min(self.selected_playlist_index, len(self.playlist_entries) - 1)) if self.playlist_entries else 0
                        if self.playlist_entries:
                            targets = [self.playlist_entries[idx]]
                    elif self.radio_pl_selected.isChecked():
                        max_r = min(self.table_playlist.rowCount(), len(self.playlist_entries))
                        for r in range(max_r):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                targets.append(self.playlist_entries[r])
                    else:
                        targets = list(self.playlist_entries)

                    total_t = len(targets)
                    if total_t == 0:
                        self.log("⚠️ [Downloader] មិនមានភាគណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                        self.is_downloading = False
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        return

                    self.log(f"🎬 [DramaBox] ចាប់ផ្ដើមទាញយក {total_t} ភាគទៅកាន់: {movie_folder}")
                    for idx, ep in enumerate(targets, 1):
                        if getattr(self, "cancel_download", False):
                            self.log("🛑 [Downloader] បានផ្អាកការទាញយក!")
                            break
                        ep_title = ep.get("title", f"Episode {idx}")
                        ep_clean_title = sanitize_folder_name(ep_title)
                        out_path = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.mp4")
                        # Prefer HLS (m3u8) for full duration if available, then mp4, then direct URL
                        stream_url = ep.get("m3u8_url") or ep.get("mp4_url") or ep.get("url")
                        is_preview = bool(ep.get("is_preview") or ("15s" in str(stream_url)) or (ep.get("is_locked") and not ep.get("m3u8_url")))

                        from urllib.parse import urlparse
                        cdn_host = urlparse(stream_url).netloc or "dramaboxdb.com"
                        if ".m3u8" in stream_url:
                            stream_kind = "🎬 HLS Master Stream (.m3u8) [Full HD 1080p/720p]"
                        elif "15s" in stream_url:
                            stream_kind = "⚠️ Preview Teaser (15s MP4) [VIP Locked]"
                        elif ".mp4" in stream_url:
                            stream_kind = "🎥 Direct MP4 Stream (.mp4) [Full Episode]"
                        else:
                            stream_kind = "🌐 Web Page / Public API Endpoint"

                        clean_stream_url = stream_url.split("?")[0]

                        if is_preview:
                            self.log(f"⚠️ [{idx}/{total_t}] {ep_title} គឺជា VIP/Locked នៅលើ DramaBox (គេហទំព័រផ្ដល់ជូនតែ Trailer Preview 15 វិនាទីប៉ុណ្ណោះ)! បើចង់បានភាគពេញ (~01:13) សូមចុច '🌐 Open Browser (Sniffer)' រួច Login គណនី DramaBox។")
                        elif ep.get("is_locked") and not (stream_url and ("mp4" in stream_url or "m3u8" in stream_url)):
                            self.log(f"🔒 [{idx}/{total_t}] {ep_title} ជាប់សោរ (VIP/Locked) - សូម Login ក្នុង Browser Sniffer!")
                            continue

                        self.log(f"🌐 [CDN Source] Host: {cdn_host} | Mode: {stream_kind}")
                        self.log(f"🔗 [API/Stream URL] {clean_stream_url}")
                        self.log(f"📥 [{idx}/{total_t}] កំពុងទាញយក: {ep_title}...")
                        self.run_on_main(lambda i=idx, t=total_t, tit=ep_title: self.lbl_prog_title.setText(f"Part [{i}/{t}]: {tit}"))

                        ep_opts = dict(opts)
                        ep_opts["outtmpl"] = out_path
                        ep_opts["overwrites"] = True
                        ep_opts["continuedl"] = False
                        ep_opts["http_headers"] = {
                            "Referer": "https://www.dramaboxdb.com/",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        }
                        if ff_bin:
                            ep_opts["ffmpeg_location"] = ff_bin

                        # Remove existing file if present to eliminate HTTP 416 range errors
                        if os.path.exists(out_path):
                            try:
                                os.remove(out_path)
                            except Exception:
                                pass

                        try:
                            with yt_dlp.YoutubeDL(ep_opts) as ydl:
                                ydl.download([stream_url])
                        except Exception as dl_err:
                            err_str = str(dl_err)
                            if "416" in err_str:
                                self.log(f"⚠️ [DramaBox] បានជួបប្រទះ HTTP 416 - កំពុងសម្អាតឯកសារចាស់ និងទាញយកឡើងវិញ...")
                                if os.path.exists(out_path):
                                    try: os.remove(out_path)
                                    except Exception: pass
                                ep_opts["nopart"] = False
                                with yt_dlp.YoutubeDL(ep_opts) as ydl:
                                    ydl.download([stream_url])
                            else:
                                raise dl_err

                    self.log(f"🎉 [DramaBox] បានទាញយកចប់សព្វគ្រប់ {len(targets)} ភាគ!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                if info and info.get("is_hainanyuyue"):
                    # Custom direct downloader for Hainan Yuyue drama episodes
                    targets = []
                    if self.radio_pl_single.isChecked():
                        idx = max(0, min(self.selected_playlist_index, len(self.playlist_entries) - 1)) if self.playlist_entries else 0
                        if self.playlist_entries:
                            targets = [self.playlist_entries[idx]]
                    elif self.radio_pl_selected.isChecked():
                        max_r = min(self.table_playlist.rowCount(), len(self.playlist_entries))
                        for r in range(max_r):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                targets.append(self.playlist_entries[r])
                    else:
                        targets = list(self.playlist_entries)

                    total_t = len(targets)
                    if total_t == 0:
                        self.log("⚠️ [Downloader] មិនមានភាគណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                        self.is_downloading = False
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        return

                    self.log(f"🎬 [Hainan Yuyue] ចាប់ផ្ដើមទាញយក {total_t} ភាគទៅកាន់: {movie_folder}")
                    for idx, ep in enumerate(targets, 1):
                        if getattr(self, "cancel_download", False):
                            self.log("🛑 [Downloader] បានផ្អាកការទាញយក!")
                            break
                        ep_title = ep.get("title", f"Episode {idx}")
                        ep_clean_title = sanitize_folder_name(ep_title)
                        out_path = os.path.join(movie_folder, f"{idx:02d} - {ep_clean_title}.%(ext)s")

                        stream_url = ep.get("url")
                        if not stream_url and ep.get("ch_id"):
                            self.log(f"🔍 [Hainan Yuyue] កំពុងទាញយក Link Stream សម្រាប់ {ep_title}...")
                            stream_url = self._fetch_hainanyuyue_play_url(
                                ep.get("ch_id"),
                                ep.get("video_id", ""),
                                ep.get("enc_did", ""),
                                ep.get("uid", "")
                            )
                            if stream_url:
                                ep["url"] = stream_url

                        if not stream_url:
                            self.log(f"⚠️ [Hainan Yuyue] មិនអាចចាប់យក Link Stream ភាគ {ep_title} បានឡើយ - រំលង!")
                            continue

                        self.log(f"📥 [{idx}/{total_t}] កំពុងទាញយក: {ep_title}...")
                        self.run_on_main(lambda i=idx, t=total_t, tit=ep_title: self.lbl_prog_title.setText(f"Part [{i}/{t}]: {tit}"))

                        ep_opts = dict(opts)
                        ep_opts["outtmpl"] = out_path
                        ep_opts["http_headers"] = {
                            "Referer": "",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                        }
                        if ff_bin:
                            ep_opts["ffmpeg_location"] = ff_bin

                        with yt_dlp.YoutubeDL(ep_opts) as ydl:
                            ydl.download([stream_url])

                    self.log(f"🎉 [Hainan Yuyue] បានទាញយកចប់សព្វគ្រប់ {len(targets)} ភាគ!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                if info and info.get("is_sabayflix"):
                    stream_url = info.get("url") or (info.get("entries", [{}])[0].get("url") if info.get("entries") else "")
                    is_valid_stream = bool(stream_url and ("m3u8" in stream_url.lower() or ".mp4" in stream_url.lower()))
                    if not is_valid_stream:
                        self.log("🔒 [SabayFlix Protected/VIP] រឿងនេះតម្រូវឱ្យមាន Login គណនី SabayFlix ឬចាក់ក្នុង Web Browser!")
                        self.log("💡 [Sniffer Notice] សូមចុចប៊ូតុង '🌐 Open Browser (Sniffer)' ដើម្បីបើក Login លើ SabayFlix ហើយចាក់វីដេអូ នោះប្រព័ន្ធនឹងចាប់យក Stream (.m3u8) ដោយស្វ័យប្រវត្តិ!")
                        self.run_on_main(lambda: self.set_download_ui_state(False))
                        return

                    m_title = sanitize_folder_name(info.get("title", "SabayFlix Movie"))
                    out_path = os.path.join(movie_folder, f"{m_title}.%(ext)s")
                    ep_opts = dict(opts)
                    ep_opts["outtmpl"] = out_path
                    ep_opts["format"] = "best/bestvideo+bestaudio"
                    ep_opts["http_headers"] = {
                        "Referer": "https://www.sabayflix.net/",
                        "Origin": "https://www.sabayflix.net",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    }
                    if ff_bin:
                        ep_opts["ffmpeg_location"] = ff_bin

                    self.log(f"📥 [SabayFlix] កំពុងទាញយកភាពយន្ត: {m_title}...")
                    with yt_dlp.YoutubeDL(ep_opts) as ydl:
                        ydl.download([stream_url])

                    self.log("🎉 [SabayFlix] បានទាញយកចប់សព្វគ្រប់!")
                    self.run_on_main(lambda: self.prog_bar.setValue(100))
                    self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Download Complete!"))
                    self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                    self.run_on_main(lambda: self.btn_download.setEnabled(True))
                    self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                    self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                    self.is_downloading = False
                    return

                download_target_url = url
                if getattr(self, "is_playlist", False):
                    # Playlist download customization
                    if self.radio_pl_single.isChecked():
                        if 0 <= self.selected_playlist_index < len(self.playlist_entries):
                            selected_entry = self.playlist_entries[self.selected_playlist_index]
                            download_target_url = selected_entry.get("url") or (f"https://www.youtube.com/watch?v={selected_entry.get('id')}" if selected_entry.get('id') else url)
                            opts["noplaylist"] = True
                            single_title = sanitize_folder_name(selected_entry.get("title") or "video")
                            opts["outtmpl"] = os.path.join(movie_folder, f"{single_title}.%(ext)s")
                            self.log(f"📥 [Downloader] កំពុងទាញយកវីដេអូទោល #{self.selected_playlist_index+1}: {single_title}")
                    elif self.radio_pl_selected.isChecked():
                        checked_indices = []
                        for r in range(self.table_playlist.rowCount()):
                            chk = self.table_playlist.item(r, 0)
                            if chk and chk.checkState() == Qt.CheckState.Checked:
                                checked_indices.append(r + 1)
                        if not checked_indices:
                            self.log("⚠️ [Downloader] មិនមានវីដេអូណាមួយត្រូវបានជ្រើសរើសឡើយ!")
                            self.is_downloading = False
                            self.run_on_main(lambda: self.btn_download.setEnabled(True))
                            return
                        opts["noplaylist"] = False
                        opts["playlist_items"] = ",".join(str(idx) for idx in checked_indices)
                        opts["outtmpl"] = os.path.join(movie_folder, "%(playlist_index)02d - %(title)s.%(ext)s")
                        self.log(f"📥 [Downloader] កំពុងទាញយក {len(checked_indices)} ភាគដែលបានជ្រើសរើស: {opts['playlist_items']}")
                    else:
                        opts["noplaylist"] = False
                        opts["outtmpl"] = os.path.join(movie_folder, "%(playlist_index)02d - %(title)s.%(ext)s")
                        self.log(f"📥 [Downloader] កំពុងទាញយកវីដេអូទាំងអស់ក្នុង Playlist: {len(self.playlist_entries)} វីដេអូ")
                else:
                    opts["noplaylist"] = True

                ref = get_custom_referer(url)
                if ref:
                    opts["http_headers"]["Referer"] = ref

                if ff_bin:
                    opts["ffmpeg_location"] = ff_bin

                if cookie_path:
                    opts["cookiefile"] = cookie_path

                # 3. Handle Target Containers (MP4, MKV, WebM, MP3, M4A, WAV, Subtitles Only)
                if is_subtitles_only:
                    opts["skip_download"] = True
                    opts["writesubtitles"] = True
                    opts["writeautomaticsub"] = True
                    opts["subtitlesformat"] = "srt/best"
                elif is_audio:
                    opts["format"] = "bestaudio/best"
                    if "WAV" in format_type_choice or "WAV" in quality_label:
                        opts["postprocessors"] = [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "wav"
                        }]
                    elif "M4A" in format_type_choice or "M4A" in quality_label:
                        opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
                        opts["postprocessors"] = [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "m4a"
                        }]
                    else:  # Default MP3
                        opts["postprocessors"] = [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "320"
                        }]
                else:
                    # Video containers
                    if "MKV" in format_type_choice:
                        opts["merge_output_format"] = "mkv"
                    elif "WebM" in format_type_choice:
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
                        if "mp4" in format_type_choice.lower() or "mkv" in format_type_choice.lower():
                            opts["postprocessors"].append({
                                "key": "EmbedThumbnail",
                                "already_have_thumbnail": False
                            })

                # 4. Handle Subtitles Download
                if (download_subs or is_subtitles_only) and "No Subtitles" not in sub_lang_choice:
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

                    if "English" in sub_lang_choice or "en" in sub_lang_choice:
                        opts["subtitleslangs"] = ["en", "en-US", "en-orig"]
                    elif "Chinese Simplified" in sub_lang_choice or "zh-Hans" in sub_lang_choice:
                        opts["subtitleslangs"] = ["zh-Hans", "zh", "zh-CN"]
                    elif "Chinese Traditional" in sub_lang_choice or "zh-Hant" in sub_lang_choice:
                        opts["subtitleslangs"] = ["zh-Hant", "zh-TW"]
                    elif "All Available" in sub_lang_choice:
                        opts["subtitleslangs"] = ["zh-Hans", "zh", "en", "zh-Hant"]
                    else:
                        # Smart Auto: ONLY 1 or 2 essential languages (Chinese + English) - avoid 80+ files
                        chosen = []
                        # Priority 1: Chinese
                        for pref in ["zh-Hans", "zh", "zh-CN", "zh-Hant", "zh-TW"]:
                            if pref in available_subs:
                                chosen.append(pref)
                                break
                        # Priority 2: English
                        for pref in ["en", "en-US", "en-orig", "en-GB"]:
                            if pref in available_subs:
                                chosen.append(pref)
                                break
                        if not chosen and available_subs:
                            chosen.append(available_subs[0])
                        opts["subtitleslangs"] = chosen if chosen else ["zh", "en"]

                    self.log(f"📥 [Subtitles] កំពុងទាញយកឯកសារ Subtitle SRT (English / Chinese តែប៉ុណ្ណោះ): {opts.get('subtitleslangs')}")

                # 4.5 Image / Photo / Transparent PNG Downloader Handler
                if info and info.get("is_image"):
                    self.log(f"🖼️ [Image Downloader] កំពុងទាញយករូបភាពគុណភាពដើម (Downloading High-Res Image/PNG)...")
                    img_dl_url = info.get("url") or download_target_url
                    ext = "png" if ".png" in img_dl_url.lower() else "jpg"
                    clean_f_title = sanitize_folder_name(info.get("title") or "image")
                    target_img_file = os.path.join(movie_folder, f"{clean_f_title}.{ext}")
                    
                    try:
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        req_img = urllib.request.Request(
                            img_dl_url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                                "Referer": "https://www.google.com/"
                            }
                        )
                        with urllib.request.urlopen(req_img, context=ctx, timeout=20) as img_resp:
                            img_data = img_resp.read()
                            with open(target_img_file, "wb") as imf:
                                imf.write(img_data)

                        sz_kb = len(img_data) / 1024.0
                        self.log(f"✅ [Image Downloader] បានទាញយករូបភាពដោយជោគជ័យ: {os.path.basename(target_img_file)} ({sz_kb:.1f} KB)")
                        self.run_on_main(lambda: self.prog_bar.setValue(100))
                        self.run_on_main(lambda: self.lbl_prog_title.setText("✅ Image Download Complete!"))
                        self.run_on_main(lambda: self.lbl_prog_stats.setText(f"📁 Saved to: {movie_folder}"))
                        self.run_on_main(lambda: self.btn_download.setEnabled(True))
                        self.run_on_main(lambda: self.btn_download_open.setEnabled(True))
                        self.run_on_main(lambda: self.btn_stop.setEnabled(False))
                        self.is_downloading = False
                        return
                    except Exception as im_err:
                        self.log(f"⚠️ [Image Downloader] បរាជ័យក្នុងការទាញយករូបភាព: {im_err}")

                # 5. Execute Download with resilient fallback
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([download_target_url])
                except Exception as dl_err:
                    err_text = str(dl_err)
                    if "403" in err_text or "forbidden" in err_text.lower() or "requested format" in err_text.lower():
                        self.log("⚠️ [Downloader] 403 Forbidden / Stream បង្កក, កំពុងប្ដូរទៅ Best Stream បម្រុង...")
                        opts["format"] = "best[ext=mp4]/best"
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            ydl.download([download_target_url])
                    else:
                        raise dl_err

                # 6. Post-Download Discovery
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

                # Subtitles Only completion handler
                if is_subtitles_only:
                    srt_files = [f for f in os.listdir(movie_folder) if f.lower().endswith(".srt")]
                    s_name = srt_files[0] if srt_files else (os.path.basename(downloaded_srt) if downloaded_srt else "subtitles.srt")
                    s_path = os.path.join(movie_folder, s_name)
                    sz_k = (os.path.getsize(s_path) / 1024) if os.path.exists(s_path) else 0
                    self.log(f"🎉 [Subtitles Only] ទាញយកបានជោគជ័យ! -> {s_name} ({sz_k:.1f} KB) [{len(srt_files)} ឯកសារ SRT]")
                    def _show_sub_done():
                        self.lbl_prog_title.setText(f"🎉 Subtitles Complete: {s_name} ({sz_k:.1f} KB)")
                        self.prog_bar.setValue(100)
                    self.run_on_main(_show_sub_done)
                    self.is_downloading = False
                    def _reset_sub_btn():
                        self.btn_download.setEnabled(True)
                        self.btn_download_open.setEnabled(True)
                        self.btn_stop.setEnabled(False)
                    self.run_on_main(_reset_sub_btn)
                    return

                # Standardize subtitle filename to <folder_name>.srt
                if downloaded_srt and not os.path.exists(os.path.join(movie_folder, f"{folder_name}.srt")):
                    target_srt = os.path.join(movie_folder, f"{folder_name}.srt")
                    try:
                        shutil.copy2(downloaded_srt, target_srt)
                        downloaded_srt = target_srt
                        self.log(f"📄 [Subtitles] បានកំណត់ឈ្មោះ SRT ស្វ័យប្រវត្ត: {os.path.basename(target_srt)}")
                    except Exception:
                        pass

                sz_mb = (os.path.getsize(downloaded_video) / (1024 * 1024)) if (downloaded_video and os.path.exists(downloaded_video)) else 0.0
                sz_str = f"{sz_mb / 1024:.2f} GB" if sz_mb >= 1024 else f"{sz_mb:.1f} MB"
                v_name = os.path.basename(downloaded_video) if downloaded_video else (os.path.basename(downloaded_srt) if downloaded_srt else folder_name)

                self.log(f"🎉 [Downloader] ទាញយកបានជោគជ័យ! -> {v_name} ({sz_str})")
                self.log(f"📁 [Folder] គ្រប់ឯកសារទាំងអស់ស្ថិតក្នុង: {movie_folder}")

                # Save source URL shortcut and metadata file if requested
                if save_url_enabled:
                    try:
                        webpage_url = (info.get("webpage_url") or url) if info else url
                        v_title = (info.get("title") or folder_name) if info else folder_name
                        uploader = (info.get("uploader") or info.get("channel") or "Unknown") if info else "Unknown"
                        v_dur = (info.get("duration") or 0) if info else 0

                        shortcut_path = os.path.join(movie_folder, f"{folder_name}.url")
                        with open(shortcut_path, "w", encoding="utf-8") as f:
                            f.write(f"[InternetShortcut]\nURL={webpage_url}\n")

                        txt_path = os.path.join(movie_folder, f"{folder_name}_source_url.txt")
                        with open(txt_path, "w", encoding="utf-8") as f:
                            f.write("=" * 80 + "\n")
                            f.write("🎥 VIDEO SOURCE INFORMATION / ព័ត៌មានប្រភពវីដេអូដើម\n")
                            f.write("=" * 80 + "\n")
                            f.write(f"📌 Original URL   : {webpage_url}\n")
                            f.write(f"🎬 Video Title    : {v_title}\n")
                            f.write(f"👤 Channel/Author : {uploader}\n")
                            f.write(f"⏱ Duration       : {format_timestamp(v_dur)} ({v_dur}s)\n")
                            f.write(f"📊 Format & Quality: {format_type_choice} | {quality_label}\n")
                            f.write(f"💾 Download Date  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"📁 Local Folder   : {movie_folder}\n")
                            f.write(f"🎞 Media File     : {v_name}\n")
                            if downloaded_srt:
                                f.write(f"📄 Subtitle File  : {os.path.basename(downloaded_srt)}\n")
                            f.write("=" * 80 + "\n")

                        self.log(f"🔗 [Source Link] បានរក្សាទុក Link ប្រភព: {os.path.basename(shortcut_path)}")
                    except Exception as ex:
                        self.log(f"⚠️ [Warning] មិនអាចរក្សាទុក URL shortcut: {ex}")

                def _show_success():
                    self.lbl_prog_title.setText(f"🎉 Download Complete: {v_name} ({sz_str})")
                    self.prog_bar.setValue(100)

                self.run_on_main(_show_success)

                # 7. Auto open in Movie Studio if requested
                if auto_open and downloaded_video and self.on_open_video_in_studio:
                    self.log(f"🎬 [Studio] បើកវីដេអូ {v_name} ចូលក្នុង Movie Studio...")
                    self.run_on_main(lambda: self.on_open_video_in_studio(downloaded_video))

            except Exception as e:
                err_msg = strip_ansi(str(e))
                self.log(f"❌ [Downloader Error] {err_msg}")
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

            pl_idx = d.get("info_dict", {}).get("playlist_index")
            pl_count = d.get("info_dict", {}).get("n_entries") or len(getattr(self, "playlist_entries", []))

            def _update():
                self.prog_bar.setValue(pct)
                if pl_idx and pl_count > 1:
                    self.lbl_prog_title.setText(f"⚡ Downloading Part [{pl_idx}/{pl_count}]: {pct}% ({spd:.1f} MB/s)")
                else:
                    self.lbl_prog_title.setText(f"⚡ Downloading: {pct}% ({spd:.1f} MB/s)")
            self.run_on_main(_update)
        elif d.get("status") == "finished":
            fn = os.path.basename(d.get("filename") or "")
            if fn:
                self.log(f"✅ [Finished] បានទាញយកចប់: {fn}")
