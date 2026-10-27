"""
Player View Component for PyQt6 / PySide6 Desktop Studio
Dedicated high-performance video monitor display, phone mockup frame,
full-width transport scrubber with hero play button, and fullscreen mode.
"""

import os
import cv2
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QFrame, QGroupBox, QSlider, Qt, QImage, QPixmap,
    QDialog, QShortcut, QKeySequence, QSize, Signal, QColor,
    QMenu, QCursor, QInputDialog, QSplitter
)
from ui_v_PyQt6.icons import (
    get_play_icon, get_pause_icon, get_rewind_icon, get_forward_icon,
    get_fullscreen_icon, get_speed_icon, get_qta_icon
)
from utils import format_timestamp
from config import PREVIEW_ASPECT_RATIOS
from ui_v_PyQt6.components.player.canva_preview_canvas import CanvaPreviewCanvas
from ui_v_PyQt6.components.player.canva_controls_bar import CanvaControlsBar
from ui_v_PyQt6.components.player.studio_tool_rail import (
    StudioLeftToolRail, StudioToolDrawer, MonitorHeaderBar
)


class FullscreenMonitorWindow(QDialog):
    """
    Dedicated borderless fullscreen video monitor with live subtitles and transport hotkeys.
    - Press Space or click to Play/Pause
    - Press Left/Right arrows to seek +/- 5 seconds
    - Press Escape or click '✕' to exit Fullscreen
    """
    def __init__(self, parent_player):
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.player = parent_player
        self.setStyleSheet("background-color: #000000;")
        self.showFullScreen()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video Label Screen
        self.lbl_screen = QLabel()
        self.lbl_screen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_screen.setStyleSheet("background-color: #000000;")
        layout.addWidget(self.lbl_screen, 1)

        # Overlay CC Subtitles
        self.lbl_cc = QLabel(self)
        self.lbl_cc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cc.setStyleSheet("""
            background-color: rgba(0, 0, 0, 180);
            color: #facc15;
            font-size: 24px;
            font-weight: bold;
            border-radius: 0px;
        """)
        self.lbl_cc.setFixedHeight(54)
        self.lbl_cc.hide()

        # Floating Close / Restore button in top-right corner
        self.btn_close = QPushButton("✕ ត្រឡប់មកតូចវិញ (Exit Esc)", self)
        self.btn_close.setGeometry(16, 16, 180, 36)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: rgba(15, 23, 42, 220);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                border: 1px solid #ffffff;
            }
        """)
        self.btn_close.clicked.connect(self.close)
        self.btn_close.raise_()

        # Hotkeys
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self.close)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(self.player._toggle_play)
        QShortcut(QKeySequence(Qt.Key.Key_Left), self).activated.connect(lambda: self.player._seek_relative(-5))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self).activated.connect(lambda: self.player._seek_relative(5))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'btn_close'):
            self.btn_close.move(self.width() - 200, 16)
            self.btn_close.raise_()
        if hasattr(self, 'lbl_cc') and self.lbl_cc.isVisible():
            self.lbl_cc.setFixedWidth(min(self.width() - 80, 800))
            self.lbl_cc.move((self.width() - self.lbl_cc.width()) // 2, self.height() - 100)
            self.lbl_cc.raise_()

    def update_frame(self, pixmap, cc_text=""):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(self.width(), self.height(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.lbl_screen.setPixmap(scaled)

        if cc_text:
            self.lbl_cc.setText(cc_text)
            self.lbl_cc.setFixedWidth(min(self.width() - 80, 800))
            self.lbl_cc.move((self.width() - self.lbl_cc.width()) // 2, self.height() - 100)
            self.lbl_cc.show()
            self.lbl_cc.raise_()
        else:
            self.lbl_cc.hide()

        if hasattr(self, 'btn_close'):
            self.btn_close.raise_()

    def mouseDoubleClickEvent(self, event):
        self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.player._toggle_play()
        super().mousePressEvent(event)


class PlayerView(QWidget):
    """
    High-Performance Qt Video Player:
    - Default High Fullscreen Size & Phone View (9:16 TikTok / Reels / Shorts)
    - Full-width transport scrubber bar with hero square Play button (matches user sketch)
    - True Fullscreen Monitor Mode
    - Subtitle overlay rendered cleanly in the lower third
    - Multi-track timeline synchronization
    """
    video_dropped = Signal(str)
    subtitle_dropped = Signal(str)
    lut_dropped = Signal(str)
    speed_changed = Signal(float)
    item_selected = Signal(object)
    add_subtitle_requested = Signal(float)
    cc_tool_requested = Signal()
    import_srt_requested = Signal()
    capture_cc_requested = Signal(str)
    export_cc_requested = Signal()
    translate_cc_requested = Signal()
    show_cc_analytics_requested = Signal()

    def __init__(
        self,
        parent=None,
        on_seek=None,
        on_toggle_play=None,
        on_seek_relative=None,
        on_select_sub=None,
        **kwargs
    ):
        super().__init__(parent)
        self.on_seek = on_seek
        self.on_toggle_play = on_toggle_play
        self.on_seek_relative = on_seek_relative
        self.on_select_sub = on_select_sub

        self.video_path = None
        self.cap = None
        self.fps = 24.0
        self.duration = 0.0
        self.current_time = 0.0
        self.is_playing = False
        self._last_frame = None
        self._is_scrubbing = False
        self._active_cc_text = ""
        self.playback_speed = 1.0
        self._is_seeking = False
        self.subtitles = []
        # Audio playback controlled dynamically by Multi-Track Audio Mix
        self.auto_dub_on_play = True

        # Connected external TimelineEditor
        self.timeline_editor = None
        self.timeline = None

        # Fullscreen monitor window instance
        self._fs_window = None

        self._init_ui()

    def set_timeline_editor(self, timeline_editor):
        """Attaches external TimelineEditor component for synchronized playback & seeking."""
        self.timeline_editor = timeline_editor
        if timeline_editor:
            self.timeline = timeline_editor.canvas
            if hasattr(self.timeline, "overlay_selected"):
                try:
                    self.timeline.overlay_selected.connect(self._on_timeline_overlay_selected)
                except Exception:
                    pass
            if hasattr(self.timeline, "overlays_modified"):
                try:
                    self.timeline.overlays_modified.connect(self._on_timeline_overlays_modified)
                except Exception:
                    pass
            # Synchronize Video Keyframes between Canva Preview Canvas and Timeline Canvas
            if hasattr(self, "canvas") and hasattr(self.timeline, "set_video_keyframes"):
                try:
                    self.canvas.keyframes_modified.connect(self.timeline.set_video_keyframes)
                    self.timeline.keyframes_modified.connect(lambda kfs: setattr(self.canvas, "video_keyframes", kfs))
                    self.timeline.keyframe_added.connect(lambda t: self.canvas.add_keyframe_at_current_time())
                    self.timeline.keyframe_selected.connect(lambda kf: self.canvas.update())
                except Exception:
                    pass
            self._sync_canvas_items_to_timeline()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Root Studio Layout: [ Left Tool Rail ] [ Tool Drawer ] [ Center Monitor + Transport ]
        studio_h_layout = QHBoxLayout()
        studio_h_layout.setContentsMargins(0, 0, 0, 0)
        studio_h_layout.setSpacing(0)

        # ---------------- 1. VIDEO MONITOR DISPLAY CONTAINER ----------------
        group_monitor = QFrame()
        group_monitor.setStyleSheet("""
            QFrame {
                margin: 0px;
                padding: 0px;
                border: 1px solid #1a202c;
                border-radius: 4px;
                background-color: #0d1117;
            }
        """)

        m_layout = QVBoxLayout(group_monitor)
        m_layout.setContentsMargins(0, 0, 0, 0)
        m_layout.setSpacing(0)

        # Outer Monitor Frame
        self.preview_card = QFrame()
        prev_layout = QVBoxLayout(self.preview_card)
        prev_layout.setSpacing(2)
        prev_layout.setContentsMargins(0, 0, 0, 0)

        # Canva-Like Interactive Video Preview Canvas (defaults to Fit Video)
        self.canvas = CanvaPreviewCanvas(self)
        self.canvas.player = self
        self.canvas.set_aspect_ratio("fit")
        self.lbl_video = self.canvas  # Backward-compatibility alias
        self.controls_bar = None

        # Connect canvas signals
        self.canvas.item_selected.connect(self.item_selected.emit)
        self.canvas.item_added.connect(self._on_canvas_item_added)
        self.canvas.item_deleted.connect(self._on_canvas_item_deleted)
        self.canvas.canvas_modified.connect(self._on_canvas_modified)
        self.canvas.video_dropped.connect(self.video_dropped.emit)
        self.canvas.subtitle_dropped.connect(self.subtitle_dropped.emit)
        self.canvas.lut_dropped.connect(self.lut_dropped.emit)

        prev_layout.addWidget(self.canvas, 1)
        m_layout.addWidget(self.preview_card, 1)

        # 1. Left Vertical Tool Rail Dock (48px)
        self.tool_rail = StudioLeftToolRail(self)
        studio_h_layout.addWidget(self.tool_rail)

        # Resizable Splitter between Collapsible Tool Drawer and Center Video Monitor
        self.drawer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.drawer_splitter.setOpaqueResize(True)
        self.drawer_splitter.setChildrenCollapsible(True)
        self.drawer_splitter.setStyleSheet("""
            QSplitter::handle:horizontal {
                background-color: #1a2232;
                width: 5px;
            }
            QSplitter::handle:horizontal:hover {
                background-color: #38bdf8;
                width: 5px;
            }
        """)

        # 2. Collapsible Tool Drawer (Resizable from 220px to 700px, default 280px)
        self.tool_drawer = StudioToolDrawer(self, canvas=self.canvas)
        self.tool_drawer.hide()
        self.drawer_splitter.addWidget(self.tool_drawer)

        # Connect Rail & Drawer signals
        self.tool_rail.tool_triggered.connect(self._on_rail_tool_triggered)
        self.tool_rail.undo_requested.connect(self.canvas.undo)
        self.tool_rail.redo_requested.connect(self.canvas.redo)
        self.canvas.transform_mode_changed.connect(self._on_transform_mode_changed)

        self.tool_drawer.close_drawer_requested.connect(self._close_drawer)
        self.tool_drawer.add_text_requested.connect(self._on_drawer_add_text)
        self.tool_drawer.add_media_requested.connect(self.canvas.add_image_item)
        self.tool_drawer.add_video_requested.connect(self.canvas.add_video_item)
        self.tool_drawer.add_shape_requested.connect(self.canvas.add_shape_item)
        self.tool_drawer.add_blur_requested.connect(lambda m: self.canvas.add_blur_box_item(blur_mode=m))
        self.tool_drawer.color_preset_requested.connect(self.canvas.set_color_preset)
        self.tool_drawer.open_presets_gallery.connect(self.canvas.open_color_presets_dialog)
        self.tool_drawer.aspect_ratio_requested.connect(self.canvas.set_aspect_ratio)
        self.tool_drawer.import_srt_requested.connect(self.import_srt_requested.emit)
        self.tool_drawer.capture_cc_requested.connect(self.capture_cc_requested.emit)
        self.tool_drawer.export_cc_requested.connect(self.export_cc_requested.emit)
        self.tool_drawer.translate_cc_requested.connect(self.translate_cc_requested.emit)
        self.tool_drawer.add_empty_cc_requested.connect(lambda: self.add_subtitle_requested.emit(self.current_time))
        self.tool_drawer.show_cc_analytics_requested.connect(self.show_cc_analytics_requested.emit)
        self.tool_drawer.apply_cc_style_preset.connect(self.apply_cc_style_preset)

        # ---------------- 2. PROFESSIONAL NLE TRANSPORT & PLAYBACK BAR (CAPCUT / PREMIERE STYLE) ----------------
        control_card = QFrame()
        control_card.setObjectName("player_transport_card")
        control_card.setStyleSheet("""
            QFrame#player_transport_card {
                background-color: #14171f; 
                border-top: 1px solid #28313f; 
                border-bottom: 1px solid #1a202c;
                border-left: none;
                border-right: none;
                border-radius: 0px;
            }
        """)
        c_layout = QVBoxLayout(control_card)
        c_layout.setContentsMargins(8, 4, 8, 6)
        c_layout.setSpacing(4)

        # === ROW 1: 100% FULL-WIDTH NLE PROGRESS SCRUBBER ===
        # Spans the entire width of the video monitor for maximum scrubbing precision
        self.slider_progress = QSlider(Qt.Orientation.Horizontal)
        self.slider_progress.setRange(0, 1000)
        self.slider_progress.setValue(0)
        self.slider_progress.setFixedHeight(18)
        self.slider_progress.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider_progress.setStyleSheet("""
            QSlider {
                height: 18px;
                background: transparent;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #252e3d;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #0284c7;
                width: 12px;
                height: 12px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #38bdf8;
                border: 2px solid #ffffff;
                width: 14px;
                height: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
        """)
        self.slider_progress.sliderPressed.connect(self._on_slider_pressed)
        self.slider_progress.sliderMoved.connect(self._on_slider_moved)
        self.slider_progress.sliderReleased.connect(self._on_slider_released)
        c_layout.addWidget(self.slider_progress)

        # === ROW 2: CAPCUT-STYLE STUDIO TRANSPORT & NAVIGATION CONTROLS ===
        # Matching user reference:
        # [ ◇ 312 /2067 ∨ ] 00:00:00 / 00:00:00   |<<  <|  ▶  |>  >>|   < ● >   [ 1.0x ∨ ]  [ 16:9 ∨ ]  [ ⤢ ]
        row2_transport = QHBoxLayout()
        row2_transport.setContentsMargins(4, 2, 4, 2)
        row2_transport.setSpacing(6)

        # 1. LEFT: Cue Index Pill & Digital Timecode
        tools_left = QHBoxLayout()
        tools_left.setSpacing(6)
        tools_left.setContentsMargins(0, 0, 0, 0)

        self.btn_cue_nav = None

        # Digital SMPTE Monospace Timecode
        self.lbl_time = QLabel("00:00:00 / 00:00:00")
        self.lbl_time.setStyleSheet("""
            QLabel {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                font-weight: 700;
                color: #38bdf8;
                background: transparent;
                border: none;
                padding: 0px 2px;
            }
        """)
        tools_left.addWidget(self.lbl_time)
        row2_transport.addLayout(tools_left)

        row2_transport.addStretch(1)

        # 2. CENTER: Pro NLE Transport Cluster [ |<< ] [ <| ] [ ▶ ] [ |> ] [ >>| ]
        transport_cluster = QHBoxLayout()
        transport_cluster.setSpacing(4)
        transport_cluster.setContentsMargins(0, 0, 0, 0)

        nav_btn_style = """
            QPushButton {
                background: #141923;
                border: 1px solid #232c3d;
                border-radius: 5px;
                color: #cbd5e1;
            }
            QPushButton:hover {
                background: #1e2636;
                border: 1px solid #38bdf8;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #0284c7;
            }
        """

        # |<< Jump to Start
        self.btn_first = QPushButton()
        self.btn_first.setIcon(get_qta_icon("fa5s.step-backward", color="#94a3b8"))
        self.btn_first.setIconSize(QSize(12, 12))
        self.btn_first.setFixedSize(28, 28)
        self.btn_first.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_first.setToolTip("Jump to Beginning (Home)")
        self.btn_first.setStyleSheet(nav_btn_style)
        self.btn_first.clicked.connect(self.jump_to_first)
        transport_cluster.addWidget(self.btn_first)

        # <| Previous Subtitle Cue / Step Back
        self.btn_prev_cue = QPushButton()
        self.btn_prev_cue.setIcon(get_qta_icon("fa5s.backward", color="#cbd5e1"))
        self.btn_prev_cue.setIconSize(QSize(13, 13))
        self.btn_prev_cue.setFixedSize(28, 28)
        self.btn_prev_cue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev_cue.setToolTip("Previous Subtitle Cue ([ / Left)")
        self.btn_prev_cue.setStyleSheet(nav_btn_style)
        self.btn_prev_cue.clicked.connect(self.jump_to_prev_cue)
        transport_cluster.addWidget(self.btn_prev_cue)

        # ▶ Hero Play / Pause Button Centerpiece
        self.btn_play = QPushButton()
        self.btn_play.setIcon(get_play_icon(size=16, color="#ffffff"))
        self.btn_play.setIconSize(QSize(16, 16))
        self.btn_play.setFixedSize(36, 30)
        self.btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play.setToolTip("Play / Pause (Space)")
        self.btn_play.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 15px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0ea5e9, stop:1 #0284c7);
                border: 1px solid #7dd3fc;
            }
            QPushButton:pressed {
                background: #0284c7;
            }
        """)
        self.btn_play.clicked.connect(self._toggle_play)
        transport_cluster.addWidget(self.btn_play)

        # |> Next Subtitle Cue / Step Forward
        self.btn_next_cue = QPushButton()
        self.btn_next_cue.setIcon(get_qta_icon("fa5s.forward", color="#cbd5e1"))
        self.btn_next_cue.setIconSize(QSize(13, 13))
        self.btn_next_cue.setFixedSize(28, 28)
        self.btn_next_cue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next_cue.setToolTip("Next Subtitle Cue (] / Right)")
        self.btn_next_cue.setStyleSheet(nav_btn_style)
        self.btn_next_cue.clicked.connect(self.jump_to_next_cue)
        transport_cluster.addWidget(self.btn_next_cue)

        # >>| Jump to End
        self.btn_last = QPushButton()
        self.btn_last.setIcon(get_qta_icon("fa5s.step-forward", color="#94a3b8"))
        self.btn_last.setIconSize(QSize(12, 12))
        self.btn_last.setFixedSize(28, 28)
        self.btn_last.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_last.setToolTip("Jump to End (End)")
        self.btn_last.setStyleSheet(nav_btn_style)
        self.btn_last.clicked.connect(self.jump_to_last)
        transport_cluster.addWidget(self.btn_last)

        row2_transport.addLayout(transport_cluster)

        row2_transport.addStretch(1)

        # 3. RIGHT TOOLS: Keyframe Segment, Speed, Quick Ratio, Fullscreen
        tools_right = QHBoxLayout()
        tools_right.setSpacing(6)
        tools_right.setContentsMargins(0, 0, 0, 0)

        self.btn_kf_prev = None
        self.btn_kf_add = None
        self.btn_kf_next = None
        self.combo_play_speed = None

        # Quick Aspect Ratio / Crop Toggle Button: [ 16:9 ∨ ]
        self.btn_quick_aspect = QPushButton("16:9 ∨")
        self.btn_quick_aspect.setFixedHeight(26)
        self.btn_quick_aspect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_quick_aspect.setToolTip("Quick Aspect Ratio / Crop (16:9 Long Video, 9:16 TikTok, 1:1 Square, Custom)")
        self.btn_quick_aspect.setStyleSheet("""
            QPushButton {
                background: #141923;
                border: 1px solid #283344;
                border-radius: 5px;
                color: #38bdf8;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background: #1e2636;
                border: 1px solid #38bdf8;
                color: #ffffff;
            }
        """)
        self.btn_quick_aspect.clicked.connect(self._show_quick_aspect_menu)
        tools_right.addWidget(self.btn_quick_aspect)

        # Quick CC Subtitle Visibility Toggle [ 💬 CC ]
        self.btn_transport_cc = QPushButton("CC")
        self.btn_transport_cc.setCheckable(True)
        self.btn_transport_cc.setChecked(True)
        self.btn_transport_cc.setFixedSize(32, 26)
        self.btn_transport_cc.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_transport_cc.setToolTip("Show CC in Video (បង្ហាញ CC លើវីដេអូ & Export ជាប់ CC ដូច Crop/Blur/Text)")
        self._update_transport_cc_style(True)
        self.btn_transport_cc.toggled.connect(self._on_transport_cc_toggled)
        tools_right.addWidget(self.btn_transport_cc)

        # Fullscreen Monitor Toggle Button: [ ⤢ ]
        self.btn_fullscreen = QPushButton()
        self.btn_fullscreen.setIcon(get_qta_icon("fa5s.expand", color="#cbd5e1"))
        self.btn_fullscreen.setIconSize(QSize(13, 13))
        self.btn_fullscreen.setFixedSize(28, 26)
        self.btn_fullscreen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fullscreen.setToolTip("Fullscreen Preview (F11 / F / Double Click)")
        self.btn_fullscreen.setStyleSheet("""
            QPushButton {
                background: #141923;
                border: 1px solid #283344;
                border-radius: 5px;
                color: #cbd5e1;
            }
            QPushButton:hover {
                background: #1e2636;
                border: 1px solid #38bdf8;
                color: #38bdf8;
            }
        """)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        tools_right.addWidget(self.btn_fullscreen)

        row2_transport.addLayout(tools_right)

        c_layout.addLayout(row2_transport)

        m_layout.addWidget(control_card)

        # Center Column (Monitor Header Bar + Monitor Container)
        center_container = QWidget()
        center_col_layout = QVBoxLayout(center_container)
        center_col_layout.setContentsMargins(0, 0, 0, 0)
        center_col_layout.setSpacing(0)

        # Top Monitor Header Bar removed to provide a clean, large video monitor canvas
        self.monitor_header = None
        self.canvas.resolution_changed.connect(self._on_canvas_resolution_changed)

        center_col_layout.addWidget(group_monitor, 1)

        self.drawer_splitter.addWidget(center_container)
        self.drawer_splitter.setStretchFactor(0, 0)
        self.drawer_splitter.setStretchFactor(1, 1)
        studio_h_layout.addWidget(self.drawer_splitter, 1)

        main_layout.addLayout(studio_h_layout)

        # Setup Dedicated Transport Shortcuts (Space, Left/Right Arrows, J/K/L)
        self._setup_player_shortcuts()

    def _setup_player_shortcuts(self):
        """Transport shortcuts so Space & Left/Right arrows seek reliably whether focused or not."""
        def _add_sc(seq, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)
            return sc

        _add_sc(Qt.Key.Key_Space, self._toggle_play)
        _add_sc(Qt.Key.Key_Left, lambda: self._seek_relative(-2.0))
        _add_sc(Qt.Key.Key_Right, lambda: self._seek_relative(2.0))
        _add_sc("Shift+Left", lambda: self._seek_relative(-5.0))
        _add_sc("Shift+Right", lambda: self._seek_relative(5.0))
        _add_sc("Ctrl+Left", lambda: self._seek_relative(-1.0 / max(1.0, getattr(self, "fps", 24.0))))
        _add_sc("Ctrl+Right", lambda: self._seek_relative(1.0 / max(1.0, getattr(self, "fps", 24.0))))
        _add_sc(Qt.Key.Key_J, lambda: self._seek_relative(-2.0))
        _add_sc(Qt.Key.Key_K, self._toggle_play)
        _add_sc(Qt.Key.Key_L, lambda: self._seek_relative(2.0))

    def _ensure_drawer_visible(self):
        self.tool_drawer.show()
        if hasattr(self, "drawer_splitter"):
            sizes = self.drawer_splitter.sizes()
            if sizes and sizes[0] < 220:
                tot = sum(sizes)
                saved_w = getattr(self, "_saved_drawer_w", 280) or 280
                self.drawer_splitter.setSizes([saved_w, max(200, tot - saved_w)])

    def _on_rail_tool_triggered(self, key: str):
        if not key or key == "select":
            self._close_drawer()
        elif key == "transform":
            self.canvas.set_transform_mode(True)
            self.tool_drawer.set_active_tool(key)
            self._ensure_drawer_visible()
        elif key == "cc":
            self.canvas.set_transform_mode(False)
            self.tool_drawer.set_active_tool(key)
            self._ensure_drawer_visible()
            self.cc_tool_requested.emit()
            self.show_cc_analytics_requested.emit()
        else:
            self.canvas.set_transform_mode(False)
            self.tool_drawer.set_active_tool(key)
            self._ensure_drawer_visible()

    def apply_cc_style_preset(self, preset_id: str):
        """Applies visual subtitle styling preset (Cinema Yellow, White Glow, Neon Purple, Box)."""
        if hasattr(self, "canvas") and self.canvas:
            sub_item = getattr(self.canvas, "_subtitle_item", None)
            if not sub_item and hasattr(self.canvas, "set_active_subtitle"):
                self.canvas.set_active_subtitle("គំរូអក្សររត់ Subtitle Preview")
                sub_item = getattr(self.canvas, "_subtitle_item", None)
            if sub_item:
                if preset_id == "yellow_cinema":
                    sub_item.font_color = QColor("#facc15")
                    sub_item.is_bold = True
                    sub_item.bg_color = QColor(0, 0, 0, 0)
                elif preset_id == "white_glow":
                    sub_item.font_color = QColor("#ffffff")
                    sub_item.is_bold = True
                    sub_item.bg_color = QColor(0, 0, 0, 0)
                elif preset_id == "neon_purple":
                    sub_item.font_color = QColor("#c084fc")
                    sub_item.is_bold = True
                    sub_item.bg_color = QColor(25, 10, 45, 180)
                elif preset_id == "box_black":
                    sub_item.font_color = QColor("#ffffff")
                    sub_item.is_bold = True
                    sub_item.bg_color = QColor(0, 0, 0, 200)
                if hasattr(self.canvas, "canvas_modified"):
                    self.canvas.canvas_modified.emit()
                self.canvas.update()

    def _close_drawer(self):
        if hasattr(self, "drawer_splitter"):
            sizes = self.drawer_splitter.sizes()
            if sizes and sizes[0] > 0:
                self._saved_drawer_w = sizes[0]
        self.tool_drawer.hide()
        self.tool_rail.set_active_tool(None)
        self.canvas.set_transform_mode(False)

    def _on_transform_mode_changed(self, active: bool):
        if active:
            self.tool_rail.set_active_tool("transform")
            self.tool_drawer.set_active_tool("transform")
        else:
            if getattr(self.tool_rail, "active_tool", None) == "transform":
                self.tool_rail.set_active_tool(None)
                self.tool_drawer.hide()

    def _on_drawer_add_text(self, text: str, styles: dict):
        item = self.canvas.add_text_item(text)
        if item and styles:
            if "font_size" in styles:
                item.font_size = styles["font_size"]
            if "is_bold" in styles:
                item.is_bold = styles["is_bold"]
            if "color" in styles:
                item.font_color = QColor(styles["color"])
            if "bg_color" in styles:
                item.bg_color = QColor(styles["bg_color"])
            self.canvas.canvas_modified.emit()
            self.canvas.update()

    # ------------------ SPEED & AUTO-DUB STATE ------------------
    def _on_speed_changed(self, text: str):
        try:
            cleaned = text.replace("x", "").replace("X", "").strip()
            speed = float(cleaned)
        except Exception:
            speed = 1.0
        self.playback_speed = max(0.1, min(10.0, speed))
        self.speed_changed.emit(self.playback_speed)

    def set_playback_speed(self, speed: float):
        self.playback_speed = speed
        if hasattr(self, "combo_play_speed") and self.combo_play_speed:
            txt = f"{speed:.1f}x" if speed != 1.25 else "1.25x"
            self.combo_play_speed.blockSignals(True)
            self.combo_play_speed.setCurrentText(txt)
            self.combo_play_speed.blockSignals(False)
        self.speed_changed.emit(speed)

    def _on_auto_dub_toggled(self, checked: bool = True):
        self.auto_dub_on_play = checked

    # ------------------ PLAYBACK LOGIC & SEEKING ------------------
    def load_video(self, video_path: str):
        if not os.path.exists(video_path):
            return
        self.video_path = video_path
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(video_path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 24.0
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1
        self.duration = frame_count / self.fps
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.duration = self.duration
            self.canvas.current_time = 0.0

        if hasattr(self, "monitor_header") and self.monitor_header and self.cap:
            vw = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
            vh = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
            self.monitor_header.set_dimensions(vw, vh)

        if self.timeline_editor:
            self.timeline_editor.set_duration(self.duration)
            self.timeline_editor.set_data(
                video_clips=[{"path": video_path, "duration": self.duration}],
                video_path=video_path
            )
        elif self.timeline:
            self.timeline.set_duration(self.duration)
            self.timeline.set_data(
                video_clips=[{"path": video_path, "duration": self.duration}],
                video_path=video_path
            )

        self.seek(0.0)

    def read_next_frame(self) -> bool:
        """Reads the next frame sequentially without seeking, eliminating H.264 NAL errors and stutter"""
        if getattr(self, "_is_seeking", False) or not self.cap or not self.cap.isOpened():
            return True

        # If fast-forwarding >= 2.0x on high-fps media, skip 1 frame via fast grab to ensure real-time speed
        speed = getattr(self, "playback_speed", 1.0)
        if speed >= 2.0 and getattr(self, "fps", 24.0) >= 30.0:
            self.cap.grab()

        ret, frame = self.cap.read()
        if ret:
            self._last_frame = frame
            pos_msec = self.cap.get(cv2.CAP_PROP_POS_MSEC)
            if pos_msec > 0:
                self.current_time = pos_msec / 1000.0
            else:
                self.current_time = min(self.duration, self.current_time + (1.0 / max(1.0, self.fps)))

            if hasattr(self, "canvas") and self.canvas:
                self.canvas.current_time = self.current_time
                self.canvas.duration = self.duration

            if self.timeline_editor:
                self.timeline_editor.set_current_time(self.current_time)
            elif self.timeline:
                self.timeline.set_current_time(self.current_time)

            self._update_time_and_slider()
            self._display_frame(frame)
            return True
        return False

    def seek(self, t: float):
        """Seeks to a specific timestamp when user scrubs slider or clicks timeline"""
        self._is_seeking = True
        try:
            max_dur = self.duration if (self.duration and self.duration > 0) else (float(self.subtitles[-1].get("end", 0.0)) if self.subtitles else float("inf"))
            self.current_time = max(0.0, min(max_dur, t)) if max_dur < float("inf") else max(0.0, t)

            if hasattr(self, "canvas") and self.canvas:
                self.canvas.current_time = self.current_time
                self.canvas.duration = self.duration

            if self.timeline_editor:
                self.timeline_editor.set_current_time(self.current_time)
            elif self.timeline:
                self.timeline.set_current_time(self.current_time)

            self._update_time_and_slider()

            if self.cap and self.cap.isOpened():
                try:
                    self.cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, self.current_time * 1000.0))
                    ret, frame = self.cap.read()
                    if ret:
                        self._last_frame = frame
                        self._display_frame(frame)
                except Exception:
                    pass
        finally:
            self._is_seeking = False

    def _display_frame(self, frame):
        self._last_frame = frame
        self.canvas.set_frame(frame)
        if hasattr(self, "monitor_header") and self.monitor_header and frame is not None:
            h, w = frame.shape[:2]
            self.monitor_header.set_dimensions(w, h)

        # Update Fullscreen Monitor if open - render 100% clean cinematic frame (no frame borders, no handles)
        if self._fs_window and self._fs_window.isVisible():
            if hasattr(self, "canvas") and hasattr(self.canvas, "render_clean_canvas"):
                self._fs_window.update_frame(self.canvas.render_clean_canvas(), "")
            elif hasattr(self, "canvas") and self.canvas:
                self._fs_window.update_frame(self.canvas.grab(), "")
            else:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                pix = QPixmap.fromImage(qimg)
                self._fs_window.update_frame(pix, self._active_cc_text)

    def _on_aspect_changed(self):
        txt = self.combo_aspect.currentText() if hasattr(self, "combo_aspect") else "fit"
        if "9:16" in txt:
            self.canvas.set_aspect_ratio("9:16")
        elif "16:9" in txt:
            self.canvas.set_aspect_ratio("16:9")
        elif "1:1" in txt:
            self.canvas.set_aspect_ratio("1:1")
        elif "4:5" in txt:
            self.canvas.set_aspect_ratio("4:5")
        else:
            self.canvas.set_aspect_ratio("fit")
        if self._last_frame is not None:
            self._display_frame(self._last_frame)

    def _on_canvas_item_added(self, item):
        """Automatically sets duration and synchronizes overlay/blur box with timeline."""
        dur = getattr(self, "duration", 10.0) or 10.0
        cur_t = getattr(self, "current_time", 0.0)
        if getattr(item, "end_time", 0.0) <= 0.0:
            item.start_time = cur_t
            item.end_time = min(dur, cur_t + 5.0) if dur > 0 else cur_t + 5.0
        self._sync_canvas_items_to_timeline()

    def _on_canvas_item_deleted(self, item):
        """Refreshes timeline when an overlay/blur box is deleted."""
        self._sync_canvas_items_to_timeline()

    def _on_canvas_modified(self):
        """Called when user drags, moves, resizes, or rotates items on preview."""
        self._sync_canvas_items_to_timeline()

    def _sync_canvas_items_to_timeline(self):
        """Pushes current preview canvas items (images, blur boxes, shapes) to timeline Overlays Track."""
        if not (self.timeline_editor and hasattr(self.timeline_editor, "canvas")):
            return
        tc = self.timeline_editor.canvas
        dur = getattr(self, "duration", 10.0) or 10.0
        sub_item = getattr(self.canvas, "_subtitle_item", None)
        for it in self.canvas.items:
            if it is not sub_item and getattr(it, "end_time", 0.0) <= 0.0:
                st = getattr(it, "start_time", 0.0)
                it.end_time = min(dur, st + 5.0) if dur > 0 else st + 5.0

        non_sub_items = [it for it in self.canvas.items if it is not sub_item]
        if hasattr(tc, "set_overlay_clips"):
            tc.set_overlay_clips(non_sub_items)

    def _on_timeline_overlay_selected(self, item):
        """Highlights the selected overlay clip on the video preview canvas and seeks to it."""
        if hasattr(self.canvas, "items") and item in self.canvas.items:
            self.canvas.selected_items = [item]
            self.item_selected.emit(item)
            st = float(getattr(item, "start_time", 0.0))
            if not getattr(self, "is_playing", False):
                self.seek(st)
            else:
                self.canvas.update()

    def _on_timeline_overlays_modified(self):
        """Refreshes video monitor when overlay duration/timing is trimmed or moved on timeline."""
        self.canvas.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._last_frame is not None:
            self._display_frame(self._last_frame)

    def _update_time_and_slider(self):
        curr_str = format_timestamp(self.current_time).split(",")[0]
        dur_str = format_timestamp(self.duration).split(",")[0]
        self.lbl_time.setText(f"{curr_str} / {dur_str}")
        self._update_cue_counter()

        if not self._is_scrubbing and self.duration > 0:
            val = int((self.current_time / self.duration) * 1000)
            self.slider_progress.blockSignals(True)
            self.slider_progress.setValue(val)
            self.slider_progress.blockSignals(False)

    def _on_slider_pressed(self):
        self._is_scrubbing = True

    def _on_slider_moved(self, val: int):
        if self.duration > 0:
            t = (val / 1000.0) * self.duration
            self.seek(t)
            if self.on_seek:
                try:
                    self.on_seek(t, from_player=True, scrubbing=True)
                except TypeError:
                    self.on_seek(t)

    def _on_slider_released(self):
        self._is_scrubbing = False
        val = self.slider_progress.value()
        if self.duration > 0:
            t = (val / 1000.0) * self.duration
            self.seek(t)
            if self.on_seek:
                try:
                    self.on_seek(t, from_player=True, scrubbing=False)
                except TypeError:
                    self.on_seek(t)

    def set_playing_state(self, is_playing: bool):
        self.is_playing = is_playing
        if self.is_playing:
            self.btn_play.setIcon(get_pause_icon(size=18, color="#ffffff"))
        else:
            self.btn_play.setIcon(get_play_icon(size=18, color="#ffffff"))
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.update()

    def _toggle_play(self):
        self.set_playing_state(not self.is_playing)
        if self.on_toggle_play:
            self.on_toggle_play()

    def _seek_relative(self, delta_s: float):
        max_dur = self.duration if (self.duration and self.duration > 0) else (float(self.subtitles[-1].get("end", 0.0)) if getattr(self, "subtitles", None) else float("inf"))
        new_t = max(0.0, min(max_dur, self.current_time + delta_s)) if max_dur < float("inf") else max(0.0, self.current_time + delta_s)
        self.seek(new_t)
        if self.on_seek_relative:
            self.on_seek_relative(delta_s)
        elif self.on_seek:
            try:
                self.on_seek(new_t, from_player=True, scrubbing=False)
            except TypeError:
                self.on_seek(new_t)

    def _update_transport_cc_style(self, checked: bool):
        if not hasattr(self, "btn_transport_cc"):
            return
        if checked:
            self.btn_transport_cc.setStyleSheet("""
                QPushButton {
                    background: #064e3b;
                    border: 1px solid #10b981;
                    border-radius: 5px;
                    color: #34d399;
                    font-weight: 700;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #047857;
                    border-color: #6ee7b7;
                }
            """)
        else:
            self.btn_transport_cc.setStyleSheet("""
                QPushButton {
                    background: #141923;
                    border: 1px solid #283344;
                    border-radius: 5px;
                    color: #94a3b8;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background: #1e2636;
                    color: #cbd5e1;
                }
            """)

    def _on_transport_cc_toggled(self, checked: bool):
        self._update_transport_cc_style(checked)
        self.set_subtitle_visibility(checked)
        if hasattr(self, "controls_bar") and self.controls_bar and hasattr(self.controls_bar, "_sync_cc_button"):
            self.controls_bar._sync_cc_button(checked)

    def set_subtitle_visibility(self, visible: bool):
        self._is_cc_visible = bool(visible)
        if hasattr(self, "btn_transport_cc") and self.btn_transport_cc.isChecked() != visible:
            self.btn_transport_cc.blockSignals(True)
            self.btn_transport_cc.setChecked(visible)
            self._update_transport_cc_style(visible)
            self.btn_transport_cc.blockSignals(False)
        self.canvas.set_subtitle_visibility(visible)
        if self._fs_window and self._fs_window.isVisible():
            self._fs_window.lbl_cc.setVisible(visible and bool(self._active_cc_text))
        if not visible:
            self._active_cc_text = ""

    def set_active_subtitle_text(self, text: str, start_time: float = None, end_time: float = None):
        self._active_cc_text = text
        self.canvas.set_active_subtitle(text, start_time=start_time, end_time=end_time)
        if self._fs_window and self._fs_window.isVisible():
            is_vis = getattr(self, "_is_cc_visible", True) and bool(text)
            self._fs_window.lbl_cc.setText(text)
            self._fs_window.lbl_cc.setVisible(is_vis)

    def update_timeline_data(self, subtitles=None, video_clips=None, audio_tracks=None, video_path=None):
        if subtitles is not None:
            self.subtitles = subtitles
            self._update_cue_counter()
        v_path = video_path or self.video_path
        if self.timeline_editor:
            self.timeline_editor.set_data(
                subtitles=subtitles, 
                video_clips=video_clips, 
                audio_tracks=audio_tracks,
                video_path=v_path
            )
        elif self.timeline:
            self.timeline.set_data(
                subtitles=subtitles, 
                video_clips=video_clips, 
                audio_tracks=audio_tracks,
                video_path=v_path
            )

    def toggle_fullscreen(self):
        """Toggles true fullscreen monitor mode"""
        if self._fs_window and self._fs_window.isVisible():
            self._fs_window.close()
            self._fs_window = None
        else:
            self._fs_window = FullscreenMonitorWindow(self)
            if hasattr(self, "canvas") and hasattr(self.canvas, "render_clean_canvas"):
                self._fs_window.update_frame(self.canvas.render_clean_canvas(), "")
            elif hasattr(self, "canvas") and self.canvas:
                self._fs_window.update_frame(self.canvas.grab(), "")
            elif self._last_frame is not None:
                rgb = cv2.cvtColor(self._last_frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                self._fs_window.update_frame(QPixmap.fromImage(qimg), self._active_cc_text)
            self._fs_window.show()

    def _on_canvas_resolution_changed(self, w: int, h: int, tag: str):
        if hasattr(self, "monitor_header") and self.monitor_header:
            self.monitor_header.set_dimensions(w, h, tag)
        if hasattr(self, "btn_quick_aspect"):
            mode = getattr(self.canvas, "aspect_ratio_mode", "16:9")
            lbl_map = {"16:9": "16:9 ∨", "9:16": "9:16 ∨", "1:1": "1:1 ∨", "4:5": "4:5 ∨", "21:9": "21:9 ∨", "fit": "Fit ∨"}
            self.btn_quick_aspect.setText(lbl_map.get(mode, f"{w}x{h} ∨"))

    # ------------------ CAPCUT-STYLE CUE & TRANSPORT NAVIGATION ------------------
    def _prompt_jump_to_sub(self):
        total = len(getattr(self, "subtitles", []))
        if total == 0:
            return
        num, ok = QInputDialog.getInt(
            self,
            "Jump to Subtitle (រំលងទៅបន្ទាត់)",
            f"Enter Subtitle Number (1 to {total}):",
            1, 1, total, 1
        )
        if ok and 1 <= num <= total:
            target_sub = self.subtitles[num - 1]
            st = float(target_sub.get("start", 0.0))
            self.seek(st)
            if self.on_seek:
                try:
                    self.on_seek(st, from_player=True)
                except TypeError:
                    self.on_seek(st)

    def _update_cue_counter(self):
        if not hasattr(self, "btn_cue_nav") or not self.btn_cue_nav:
            return
        total = len(getattr(self, "subtitles", []))
        if total == 0:
            self.btn_cue_nav.setText("◇ 0 / 0 ∨")
            return
        cur_idx = -1
        t = self.current_time
        for i, sub in enumerate(self.subtitles):
            st = float(sub.get("start", 0.0))
            et = float(sub.get("end", st + 0.1))
            if st <= t <= et:
                cur_idx = i
                break
        if cur_idx == -1:
            for i, sub in enumerate(self.subtitles):
                if float(sub.get("start", 0.0)) <= t:
                    cur_idx = i
                else:
                    break
        disp = (cur_idx + 1) if cur_idx >= 0 else 1
        self.btn_cue_nav.setText(f"◇ {disp} /{total} ∨")

    def jump_to_first(self):
        """|<< Jump to start of video or first subtitle"""
        self.seek(0.0)
        if self.on_seek:
            try:
                self.on_seek(0.0, from_player=True)
            except TypeError:
                self.on_seek(0.0)

    def jump_to_last(self):
        """>>| Jump to end of video or last subtitle"""
        if self.subtitles:
            last_st = float(self.subtitles[-1].get("start", 0.0))
            self.seek(last_st)
            target = last_st
        else:
            self.seek(self.duration)
            target = self.duration
        if self.on_seek:
            try:
                self.on_seek(target, from_player=True)
            except TypeError:
                self.on_seek(target)

    def jump_to_prev_cue(self):
        """<| Jump to previous video keyframe or subtitle cue or -2s"""
        kfs = getattr(self.canvas, "video_keyframes", []) if hasattr(self, "canvas") else []
        kf_times = [float(k.get("time", 0.0)) for k in kfs]
        sub_times = [float(s.get("start", 0.0)) for s in self.subtitles] if self.subtitles else []
        all_cues = sorted(set(kf_times + sub_times))
        if all_cues:
            t = self.current_time - 0.08
            prev_cues = [c for c in all_cues if c < t]
            if prev_cues:
                target = prev_cues[-1]
                self.seek(target)
                if self.on_seek:
                    try:
                        self.on_seek(target, from_player=True)
                    except TypeError:
                        self.on_seek(target)
                return
        self._seek_relative(-2.0)

    def jump_to_next_cue(self):
        """|> Jump to next video keyframe or subtitle cue or +2s"""
        kfs = getattr(self.canvas, "video_keyframes", []) if hasattr(self, "canvas") else []
        kf_times = [float(k.get("time", 0.0)) for k in kfs]
        sub_times = [float(s.get("start", 0.0)) for s in self.subtitles] if self.subtitles else []
        all_cues = sorted(set(kf_times + sub_times))
        if all_cues:
            t = self.current_time + 0.08
            next_cues = [c for c in all_cues if c > t]
            if next_cues:
                target = next_cues[0]
                self.seek(target)
                if self.on_seek:
                    try:
                        self.on_seek(target, from_player=True)
                    except TypeError:
                        self.on_seek(target)
                return
        self._seek_relative(2.0)

    def _on_add_kf_clicked(self):
        """Adds video animation keyframe at current playhead and emits subtitle cue signal."""
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.add_keyframe_at_current_time()
        self.add_subtitle_requested.emit(self.current_time)

    def _show_quick_aspect_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #11141c;
                border: 1px solid #283344;
                color: #e2e8f0;
                padding: 4px;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        menu.addAction("🎬 16:9 Long Video (YouTube / Cinema)").triggered.connect(lambda: self._set_aspect_from_quick("16:9"))
        menu.addAction("📱 9:16 Short Video (TikTok / Reels)").triggered.connect(lambda: self._set_aspect_from_quick("9:16"))
        menu.addAction("🤖 AI Auto Face Tracking & Reframe (TikTok 9:16)...").triggered.connect(self.open_auto_reframe_dialog)
        menu.addAction("⏹️ 1:1 Square (Instagram / Post)").triggered.connect(lambda: self._set_aspect_from_quick("1:1"))
        menu.addAction("📸 4:5 Portrait (Instagram Feed)").triggered.connect(lambda: self._set_aspect_from_quick("4:5"))
        menu.addAction("📺 Fit Original Video").triggered.connect(lambda: self._set_aspect_from_quick("fit"))
        menu.addSeparator()
        menu.addAction("⚙️ Custom Size (W x H)...").triggered.connect(self.canvas.open_custom_size_dialog)
        menu.exec(QCursor.pos())

    def _set_aspect_from_quick(self, mode: str):
        self.canvas.set_aspect_ratio(mode)
        lbl_map = {"16:9": "16:9 ∨", "9:16": "9:16 ∨", "1:1": "1:1 ∨", "4:5": "4:5 ∨", "fit": "Fit ∨"}
        self.btn_quick_aspect.setText(lbl_map.get(mode, "Ratio ∨"))

    def open_auto_reframe_dialog(self):
        """Opens AI Face Tracking and Auto Reframe (16:9 to 9:16 TikTok) Dialog"""
        from ui_v_PyQt6.components.player.auto_reframe_dialog import AutoReframeDialog
        v_path = self.video_path
        if not v_path:
            p = self.parent()
            while p and not getattr(p, "video_path", None):
                p = getattr(p, "parent", lambda: None)()
            if p and getattr(p, "video_path", None):
                v_path = p.video_path

        dlg = AutoReframeDialog(parent=self, video_path=v_path)
        dlg.reframe_applied.connect(self._on_reframe_applied)
        dlg.video_selected.connect(lambda p: self.load_video(p) if (not self.video_path or self.video_path != p) else None)
        dlg.exec()

    def _on_reframe_applied(self, data: dict):
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.set_reframe_data(data)
            self.canvas.set_aspect_ratio("9:16")
        if hasattr(self, "btn_quick_aspect"):
            self.btn_quick_aspect.setText("9:16 ∨")
        if hasattr(self, "monitor_header") and self.monitor_header and hasattr(self.monitor_header, "combo_ratio"):
            self.monitor_header.combo_ratio.blockSignals(True)
            self.monitor_header.combo_ratio.setCurrentText("9:16 TikTok / Shorts")
            self.monitor_header.combo_ratio.blockSignals(False)
