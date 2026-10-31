"""
AI Khmer Movie Studio - Modern Vertical Left Tool Rail & Drawer
Matches modern video editors (Canva, CapCut, Premiere, Figma):
- Vertical Left Tool Rail (48px) with clean icon dock
- Active icon highlighted with glowing rounded square background (#7c3aed)
- Collapsible Side Drawer (260px) with interactive templates for:
  * Media (Images, Stickers, GIFs, Uploads)
  * Video Overlay (PiP Clips)
  * Text (Heading, Subheading, Dialogue, Neon, Badges)
  * Shapes (Rounded Rect, Circle, Star, Capsule)
  * Blur & Censor (Gaussian, Mosaic, Glass, Blackout)
  * Color Presets (Cinematic LUTs, Film, Bright, Mono)
  * Canvas Ratio (16:9, 9:16, 1:1, 4:5, Fit)
- Monitor Header Bar with Undo/Redo and Canvas Dimensions (1280 x 720)
"""

import os
from typing import Optional

from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QGridLayout, QStackedWidget,
    QSlider, QComboBox, QFileDialog, Qt, Signal, QColor, QSize, QIcon, QTimer
)
from ui_v_PyQt6.icons import get_qta_icon


class StudioLeftToolRail(QWidget):
    """
    Sleek 48px vertical tool rail dock on the far left.
    Features modern icon buttons with glowing rounded square active states.
    """
    tool_triggered = Signal(str)  # Emits tool key ("media", "text", "shapes", etc.)
    undo_requested = Signal()
    redo_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(52)
        self.active_tool: Optional[str] = None
        self._buttons = {}

        self.setStyleSheet("""
            QWidget {
                background-color: #0c0e14;
                border-right: 1px solid #1a202c;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(8)

        # Top Studio Brand Logo / Icon
        btn_logo = QPushButton()
        btn_logo.setFixedSize(40, 40)
        btn_logo.setIcon(get_qta_icon("fa5s.bolt", color="#38bdf8"))
        btn_logo.setIconSize(QSize(20, 20))
        btn_logo.setStyleSheet("""
            QPushButton {
                background-color: #171b24;
                border: 1px solid #232b38;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1e2533;
                border: 1px solid #38bdf8;
            }
        """)
        btn_logo.setToolTip("AI Khmer Movie Studio - Pro Video Canvas")
        layout.addWidget(btn_logo, 0, Qt.AlignmentFlag.AlignCenter)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1e2430; max-height: 1px;")
        layout.addWidget(sep)

        # Tool Dock Buttons (Key, Tooltip, Icon, Default Color)
        tools = [
            ("templates", "Video Templates & Layouts (គំរូវីដេអូស្រាប់ៗ TikTok, YouTube, Reels)", "fa5s.th-large", "#f59e0b"),
            ("select", "Selection & Move (សញ្ញាព្រួញជ្រើសរើស)", "fa5s.mouse-pointer", "#94a3b8"),
            ("transform", "Transform & Pan Video (ទាញប្លង់វីដេអូ ឆ្វេង-ស្តាំ/លើ-ក្រោម)", "fa5s.arrows-alt", "#38bdf8"),
            ("cc", "Captions & Subtitles (អក្សររត់ SRT / ចាប់ CC / បកប្រែ / Export)", "fa5s.closed-captioning", "#38bdf8"),
            ("media", "Media & Stickers (រូបភាព និង GIF)", "fa5s.image", "#10b981"),
            ("video", "Video Overlay (វីដេអូ PiP)", "fa5s.video", "#06b6d4"),
            ("text", "Text & Titles (អក្សររត់ និងចំណងជើង)", "fa5s.font", "#38bdf8"),
            ("shapes", "Shapes & Elements (រាងធរណីមាត្រ)", "fa5s.shapes", "#8b5cf6"),
            ("face_ar", "AI Face Mesh, Stickers & Auto Blur (ចាប់ផ្ទៃមុខ AI & AR Stickers)", "fa5s.theater-masks", "#f43f5e"),
            ("blur", "Blur & Censor Box (បិទបាំងវីដេអូ)", "fa5s.shield-alt", "#ef4444"),
            ("effects", "Color Presets & LUTs (ពណ៌ភាពយន្ត)", "fa5s.magic", "#ec4899"),
            ("ratio", "Aspect Ratio & Grid (ទំហំ Canvas)", "fa5s.crop-alt", "#38bdf8")
        ]

        for key, tip, icon_name, col in tools:
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setIcon(get_qta_icon(icon_name, color=col))
            btn.setIconSize(QSize(18, 18))
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._on_button_clicked(k))
            self._buttons[key] = (btn, icon_name, col)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)

    def _style_sub_button(self, btn: QPushButton):
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #1e2533;
                border: 1px solid #334155;
            }
        """)

    def _on_button_clicked(self, key: str):
        if self.active_tool == key:
            # Clicking active tool toggles drawer closed
            self.set_active_tool(None)
            self.tool_triggered.emit("")
        else:
            self.set_active_tool(key)
            self.tool_triggered.emit(key)

    def set_active_tool(self, key: Optional[str]):
        """Highlights the active tool with glowing purple/blue rounded square background."""
        self.active_tool = key
        for k, (btn, icon_name, col) in self._buttons.items():
            if k == key:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #7c3aed;
                        border: 1px solid #a78bfa;
                        border-radius: 10px;
                    }
                """)
                btn.setIcon(get_qta_icon(icon_name, color="#ffffff"))
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        border: 1px solid transparent;
                        border-radius: 8px;
                    }
                    QPushButton:hover {
                        background-color: #1a202c;
                        border: 1px solid #2d3748;
                    }
                """)
                btn.setIcon(get_qta_icon(icon_name, color=col))


class StudioToolDrawer(QFrame):
    """
    Collapsible 260px drawer panel showing rich templates and interactive controls
    for the currently selected tool (Media, Video, Text, Shapes, Blur, Effects, Ratio).
    """
    add_text_requested = Signal(str, dict)       # (text, style_dict)
    add_media_requested = Signal(str)            # file_path
    add_video_requested = Signal(str)            # file_path
    add_shape_requested = Signal(str, str)       # (shape_type, color)
    add_blur_requested = Signal(str)             # blur_mode
    color_preset_requested = Signal(str, float)  # (preset_id, intensity)
    open_presets_gallery = Signal()
    aspect_ratio_requested = Signal(str)         # ratio_mode
    close_drawer_requested = Signal()
    import_srt_requested = Signal()
    capture_cc_requested = Signal(str)           # engine: "whisper", "funasr", "whisperx"
    export_cc_requested = Signal()
    translate_cc_requested = Signal()
    add_empty_cc_requested = Signal()
    apply_cc_style_preset = Signal(str)          # preset_name
    show_cc_analytics_requested = Signal()

    def __init__(self, parent=None, canvas=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setMinimumWidth(220)
        self.setMaximumWidth(700)
        self.setStyleSheet("""
            StudioToolDrawer {
                background-color: #13161f;
                border-right: 1px solid #232b3b;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # 1. Header Bar with Category Title & Close Button
        hdr = QHBoxLayout()
        self.lbl_title = QLabel("🎨 Elements & Media")
        self.lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f1f5f9;")
        hdr.addWidget(self.lbl_title)
        hdr.addStretch()

        btn_close = QPushButton()
        btn_close.setFixedSize(24, 24)
        btn_close.setIcon(get_qta_icon("fa5s.times", color="#94a3b8"))
        btn_close.setIconSize(QSize(12, 12))
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #262e3d;
            }
        """)
        btn_close.setToolTip("Close Drawer (បិទ)")
        btn_close.clicked.connect(self.close_drawer_requested.emit)
        hdr.addWidget(btn_close)
        root.addLayout(hdr)

        # 2. Search Bar
        self.entry_search = QLineEdit()
        self.entry_search.setPlaceholderText("🔍 Search templates & media...")
        self.entry_search.setStyleSheet("""
            QLineEdit {
                background-color: #1a202c;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #171d28;
            }
        """)
        self.entry_search.textChanged.connect(self._on_search_changed)
        root.addWidget(self.entry_search)

        # 3. Stacked Content Pages
        self.pages = QStackedWidget()
        self._page_map = {}

        # Build Pages
        self._page_map["templates"] = self.pages.addWidget(self._build_templates_page())
        self._page_map["transform"] = self.pages.addWidget(self._build_transform_page())
        self._page_map["cc"] = self.pages.addWidget(self._build_cc_page())
        self._page_map["media"] = self.pages.addWidget(self._build_media_page())
        self._page_map["video"] = self.pages.addWidget(self._build_video_page())
        self._page_map["text"] = self.pages.addWidget(self._build_text_page())
        self._page_map["shapes"] = self.pages.addWidget(self._build_shapes_page())
        try:
            from ui_v_PyQt6.components.player.face_ar_panel import FaceARStudioPanel
            self.face_ar_panel = FaceARStudioPanel(canvas=self.canvas)
            self._page_map["face_ar"] = self.pages.addWidget(self.face_ar_panel)
        except Exception as e:
            pass
        self._page_map["blur"] = self.pages.addWidget(self._build_blur_page())
        self._page_map["effects"] = self.pages.addWidget(self._build_effects_page())
        self._page_map["ratio"] = self.pages.addWidget(self._build_ratio_page())

        root.addWidget(self.pages, 1)

    # ------------------ CC / SUBTITLES PAGE ------------------
    def _create_cc_action_card(self, title: str, desc: str, accent: str, callback) -> QFrame:
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #141822;
                border: 1px solid #232b3b;
                border-left: 4px solid {accent};
                border-radius: 6px;
                padding: 6px;
            }}
            QFrame:hover {{
                background-color: #1a2232;
                border: 1px solid {accent};
                border-left: 4px solid {accent};
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet("color: #f1f5f9; font-weight: bold; font-size: 11px;")
        lbl_d = QLabel(desc)
        lbl_d.setStyleSheet("color: #94a3b8; font-size: 10px;")
        lbl_d.setWordWrap(True)

        lay.addWidget(lbl_t)
        lay.addWidget(lbl_d)

        def _on_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                callback()
        card.mousePressEvent = _on_click
        return card

    def _build_cc_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        # 1. Header Card with CC Overview
        hdr_card = QFrame()
        hdr_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b);
                border: 1px solid #0284c7;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        hc_layout = QVBoxLayout(hdr_card)
        hc_layout.setContentsMargins(4, 4, 4, 4)
        hc_layout.setSpacing(3)
        lbl_h = QLabel("💬 Closed Captions & CC AI")
        lbl_h.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px;")
        lbl_d = QLabel("នាំចូល ចាប់សំឡេង AI បកប្រែ និង Export អក្សររត់")
        lbl_d.setStyleSheet("color: #94a3b8; font-size: 10px;")
        lbl_d.setWordWrap(True)
        hc_layout.addWidget(lbl_h)
        hc_layout.addWidget(lbl_d)
        layout.addWidget(hdr_card)

        # Scrollable container for CC actions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 4, 0)
        c_layout.setSpacing(8)

        # 2. Main 4 Core Action Buttons
        # (1) 📥 Import SRT
        btn_import = self._create_cc_action_card(
            title="📥 Import SRT Subtitles",
            desc="នាំចូលឯកសារ .SRT, .VTT, .ASS ពីកុំព្យូទ័រ",
            accent="#0284c7",
            callback=self.import_srt_requested.emit
        )
        c_layout.addWidget(btn_import)

        # (2) 🎙️ ចាប់ CC (Auto ASR Transcribe)
        btn_capture = self._create_cc_action_card(
            title="🎙️ ចាប់ CC (AI Speech-to-SRT)",
            desc="ចាប់អក្សររត់ស្វ័យប្រវត្តិពីសំឡេងវីដេអូដោយ Faster-Whisper",
            accent="#10b981",
            callback=lambda: self.capture_cc_requested.emit("whisper")
        )
        c_layout.addWidget(btn_capture)

        # (3) 🌐 បកប្រែ CC (AI Translate Subtitles)
        btn_trans = self._create_cc_action_card(
            title="🌐 បកប្រែ CC (AI Translate)",
            desc="បកប្រែជាភាសាខ្មែរតាម Google / Gemini / ChatGPT",
            accent="#8b5cf6",
            callback=self.translate_cc_requested.emit
        )
        c_layout.addWidget(btn_trans)

        # (4) 📤 Export CC (នាំចេញ Subtitle)
        btn_export = self._create_cc_action_card(
            title="📤 Export CC (នាំចេញអក្សររត់)",
            desc="Save ជាឯកសារ .SRT, .VTT ទុកប្រើប្រាស់",
            accent="#f59e0b",
            callback=self.export_cc_requested.emit
        )
        c_layout.addWidget(btn_export)

        # 3. Quick Actions
        lbl_quick = QLabel("⚡ Quick CC Tools:")
        lbl_quick.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px; margin-top: 4px;")
        c_layout.addWidget(lbl_quick)

        # Button: Add Subtitle Line at Playhead
        btn_add_line = QPushButton("➕ បន្ថែមបន្ទាត់ CC ត្រង់ Playhead")
        btn_add_line.setStyleSheet("""
            QPushButton {
                background-color: #1e2532;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #273042;
                border: 1px solid #38bdf8;
                color: #38bdf8;
            }
        """)
        btn_add_line.clicked.connect(self.add_empty_cc_requested.emit)
        c_layout.addWidget(btn_add_line)

        # Button: Open CC Properties & Analytics
        btn_view_props = QPushButton("📊 មើលស្ថិតិ CC ក្នុងផ្ទាំង Properties")
        btn_view_props.setStyleSheet("""
            QPushButton {
                background-color: #0c4a6e;
                color: #38bdf8;
                font-weight: bold;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #0369a1;
                color: #ffffff;
            }
        """)
        btn_view_props.clicked.connect(self.show_cc_analytics_requested.emit)
        c_layout.addWidget(btn_view_props)

        # 4. Quick Style Presets
        lbl_style = QLabel("🎨 Subtitle Style Presets:")
        lbl_style.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px; margin-top: 4px;")
        c_layout.addWidget(lbl_style)

        styles_grid = QGridLayout()
        styles_grid.setSpacing(6)
        presets = [
            ("🟡 Movie Yellow", "yellow_cinema", "#facc15"),
            ("⚪ Cinema White", "white_glow", "#ffffff"),
            ("🟣 TikTok Neon", "neon_purple", "#c084fc"),
            ("⬛ Box Backing", "box_black", "#94a3b8"),
        ]
        for idx, (p_title, p_id, p_col) in enumerate(presets):
            btn_p = QPushButton(p_title)
            btn_p.setStyleSheet(f"""
                QPushButton {{
                    background-color: #161b26;
                    color: {p_col};
                    border: 1px solid #283144;
                    border-radius: 5px;
                    padding: 6px 4px;
                    font-size: 10px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border: 1px solid {p_col};
                    background-color: #1e2636;
                }}
            """)
            btn_p.clicked.connect(lambda _, pid=p_id: self.apply_cc_style_preset.emit(pid))
            styles_grid.addWidget(btn_p, idx // 2, idx % 2)

        c_layout.addLayout(styles_grid)
        c_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        return w

    # ------------------ MEDIA PAGE ------------------
    def _build_media_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        # Big Upload Button
        btn_upload = QPushButton(" + Upload Image / GIF / Sticker")
        btn_upload.setIcon(get_qta_icon("fa5s.upload", color="#ffffff"))
        btn_upload.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #8b5cf6;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        btn_upload.clicked.connect(self._browse_media_file)
        layout.addWidget(btn_upload)

        # Dropzone label
        lbl_hint = QLabel("💡 Tip: You can also drag & drop any image, GIF, or sticker directly onto the video monitor.")
        lbl_hint.setWordWrap(True)
        lbl_hint.setStyleSheet("color: #64748b; font-size: 10px; line-height: 1.4;")
        layout.addWidget(lbl_hint)

        # Scrollable Quick Stickers & Watermarks
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        c_w = QWidget()
        c_layout = QVBoxLayout(c_w)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(8)

        lbl_sec = QLabel("Quick Watermarks & Badges:")
        lbl_sec.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 11px;")
        c_layout.addWidget(lbl_sec)

        watermarks = [
            ("🎬 Cinema VIP Stamp", "text", {"text": "CINEMA 4K VIP", "bg_color": "#e11d48", "color": "#ffffff"}),
            ("⚡ 1080p FHD Badge", "text", {"text": "FULL HD 1080P", "bg_color": "#0284c7", "color": "#ffffff"}),
            ("⭐ Exclusive Movie", "text", {"text": "★ EXCLUSIVE ★", "bg_color": "#d97706", "color": "#000000"}),
            ("🔒 Copyright Protected", "text", {"text": "© ALL RIGHTS RESERVED", "bg_color": "#1e293b", "color": "#94a3b8"}),
        ]
        for name, itype, p in watermarks:
            btn = QPushButton(name)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a202c;
                    color: #e2e8f0;
                    border: 1px solid #2d3748;
                    border-radius: 6px;
                    padding: 8px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border: 1px solid #7c3aed;
                    background-color: #222938;
                }
            """)
            btn.clicked.connect(lambda _, props=p: self.add_text_requested.emit(props["text"], props))
            c_layout.addWidget(btn)

        c_layout.addStretch()
        scroll.setWidget(c_w)
        layout.addWidget(scroll, 1)
        return w

    # ------------------ VIDEO OVERLAY PAGE ------------------
    def _build_video_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        btn_add_v = QPushButton(" + Add Picture-in-Picture Video")
        btn_add_v.setIcon(get_qta_icon("fa5s.film", color="#ffffff"))
        btn_add_v.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        btn_add_v.clicked.connect(self._browse_video_file)
        layout.addWidget(btn_add_v)

        card_info = QFrame()
        card_info.setStyleSheet("background-color: #18202f; border: 1px solid #25334a; border-radius: 6px; padding: 10px;")
        ci_layout = QVBoxLayout(card_info)
        ci_layout.setContentsMargins(4, 4, 4, 4)
        lbl_v_title = QLabel("🎬 Zero-Lag Overlay Engine")
        lbl_v_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 11px;")
        ci_layout.addWidget(lbl_v_title)

        lbl_v_desc = QLabel(
            "Video overlays automatically pre-cache frames into memory, allowing live 60fps playback "
            "that stays in perfect sync with the playhead, exactly like an animated GIF!"
        )
        lbl_v_desc.setWordWrap(True)
        lbl_v_desc.setStyleSheet("color: #94a3b8; font-size: 10px; line-height: 1.4;")
        ci_layout.addWidget(lbl_v_desc)
        layout.addWidget(card_info)

        layout.addStretch()
        return w

    # ------------------ TEXT & TITLES PAGE ------------------
    def _build_text_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        # Quick Add Templates
        templates = [
            ("Add a heading (ចំណងជើងធំ)", "Heading Title", 36, True, "#ffffff", "#00000000"),
            ("Add a subheading (ចំណងជើងរង)", "Subheading Text", 22, True, "#38bdf8", "#00000000"),
            ("Add dialogue body (អត្ថបទសន្ទនា)", "Cinema Dialogue Line...", 18, False, "#ffffff", "#00000000"),
            ("★ Golden Subtitle Pill", "Khmer Cinema Golden", 22, True, "#facc15", "#cc000000"),
            ("⚡ Neon Cyan Callout", "CYBER NEON CALLOUT", 24, True, "#00f0ff", "#101626"),
            ("🔴 Hot Red Warning Banner", "HOT BREAKING UPDATE", 20, True, "#ef4444", "#ffffff"),
        ]

        for desc, text, size, is_bold, color, bg in templates:
            btn = QPushButton(desc)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a202c;
                    color: #f1f5f9;
                    border: 1px solid #2d3748;
                    border-radius: 6px;
                    padding: 8px 10px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border: 1px solid #f59e0b;
                    background-color: #242c3d;
                }
            """)
            style_d = {"font_size": size, "is_bold": is_bold, "color": color, "bg_color": bg}
            btn.clicked.connect(lambda _, t=text, s=style_d: self.add_text_requested.emit(t, s))
            layout.addWidget(btn)

        layout.addStretch()
        return w

    # ------------------ SHAPES PAGE ------------------
    def _build_shapes_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        shapes = [
            ("➖ Straight Line (បន្ទាត់ត្រង់)", "line", "#38bdf8"),
            ("➡️ Arrow Line (បន្ទាត់ព្រួញ)", "arrow", "#06b6d4"),
            ("↔️ Double Arrow (ព្រួញសងខាង)", "double_arrow", "#0ea5e9"),
            ("🟦 Rounded Rectangle (ចតុកោណមូល)", "rounded_rect", "#0ea5e9"),
            ("⬛ Sharp Rectangle (ចតុកោណកែង)", "rect", "#8b5cf6"),
            ("⚪ Perfect Circle (រង្វង់មូល)", "circle", "#38bdf8"),
            ("🔺 Triangle (ត្រីកោណ)", "triangle", "#f59e0b"),
            ("⭐ 5-Point Star (ផ្កាយ)", "star", "#eab308"),
            ("❤️ Heart (បេះដូង)", "heart", "#f43f5e"),
            ("🏷️ Capsule Badge (ផ្លាកសញ្ញា)", "badge", "#ec4899")
        ]

        for label, stype, col in shapes:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a202c;
                    color: #f1f5f9;
                    border: 1px solid #2d3748;
                    border-radius: 6px;
                    padding: 9px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border: 1px solid #8b5cf6;
                    background-color: #222938;
                }
            """)
            btn.clicked.connect(lambda _, s=stype, c=col: self.add_shape_requested.emit(s, c))
            layout.addWidget(btn)

        layout.addStretch()
        return w

    # ------------------ BLUR & CENSOR PAGE ------------------
    def _build_blur_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        blurs = [
            ("🌫️ Gaussian Blur Box (ប្រអប់ព្រិល)", "blur"),
            ("🔲 Mosaic Pixelate Box (ប្រអប់ក្រឡា)", "mosaic"),
            ("❄️ Frosted Glass Box (កញ្ចក់ថ្លា)", "glass"),
            ("⬛ Cinema Blackout Bar (បន្ទះខ្មៅ)", "blackout")
        ]

        for label, bmode in blurs:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a202c;
                    color: #f1f5f9;
                    border: 1px solid #2d3748;
                    border-radius: 6px;
                    padding: 9px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border: 1px solid #ef4444;
                    background-color: #242c3d;
                }
            """)
            btn.clicked.connect(lambda _, m=bmode: self.add_blur_requested.emit(m))
            layout.addWidget(btn)

        # Subtitle sync button
        btn_sync = QPushButton("⚡ Sync to All Subtitles (ចម្លងតាម Subtitles)")
        btn_sync.setIcon(get_qta_icon("fa5s.sync", color="#38bdf8"))
        btn_sync.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                border: 1px dashed #38bdf8;
                border-radius: 6px;
                padding: 8px;
                margin-top: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #24344d;
            }
        """)
        btn_sync.clicked.connect(self._sync_blur_all_subs)
        layout.addWidget(btn_sync)

        layout.addStretch()
        return w

    # ------------------ COLOR PRESETS & EFFECTS PAGE ------------------
    def _build_effects_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        btn_gallery = QPushButton("🎨 Open Full Color Presets Gallery...")
        btn_gallery.setStyleSheet("""
            QPushButton {
                background-color: #272f3f;
                color: #f97316;
                font-weight: bold;
                border: 1px solid #f97316;
                border-radius: 6px;
                padding: 10px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #323b4f;
            }
        """)
        btn_gallery.clicked.connect(self.open_presets_gallery.emit)
        layout.addWidget(btn_gallery)

        # Quick preset buttons
        quick_presets = [
            ("🎬 Teal & Orange (Cinema)", "cine_teal_orange"),
            ("⭐ Cinema Gold (35mm)", "cine_gold"),
            ("📷 Kodak 2383 (Film)", "film_kodak"),
            ("✨ Vivid Pop (Bright)", "bright_vivid"),
            ("🎞️ Noir B&W (Mono)", "mono_noir"),
            ("🌆 Cyberpunk Neon (Night)", "night_cyber"),
            ("⏳ 70s Golden (Vintage)", "past_70s"),
            ("↺ Reset to Original (None)", "none")
        ]

        for label, pid in quick_presets:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a202c;
                    color: #e2e8f0;
                    border: 1px solid #2d3748;
                    border-radius: 6px;
                    padding: 8px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border: 1px solid #f97316;
                    background-color: #232a38;
                }
            """)
            btn.clicked.connect(lambda _, p=pid: self.color_preset_requested.emit(p, 0.80))
            layout.addWidget(btn)

        layout.addStretch()
        return w

    # ------------------ ASPECT RATIO PAGE ------------------
    def _build_ratio_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        ratios = [
            ("🎬 16:9 Long Video (YouTube / Cinema)", "16:9"),
            ("📱 9:16 Short Video (TikTok / Reels / Shorts)", "9:16"),
            ("⏹️ 1:1 Square (Instagram Feed)", "1:1"),
            ("📸 4:5 Portrait (Instagram Feed)", "4:5"),
            ("🎞️ 21:9 Cinema Scope (Ultrawide)", "21:9"),
            ("📺 Fit Original Video (ទំហំដើម)", "fit")
        ]

        for label, r in ratios:
            btn = QPushButton(label)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1a202c;
                    color: #e2e8f0;
                    border: 1px solid #2d3748;
                    border-radius: 6px;
                    padding: 8px;
                    text-align: left;
                    font-size: 11px;
                }
                QPushButton:hover {
                    border: 1px solid #38bdf8;
                    background-color: #232b38;
                }
            """)
            btn.clicked.connect(lambda _, ratio=r: self.aspect_ratio_requested.emit(ratio))
            layout.addWidget(btn)

        # Custom Resolution Button
        btn_custom = QPushButton("⚙️ Custom Size (កំណត់ទំហំ W x H)...")
        btn_custom.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 8px;
                text-align: left;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
            }
        """)
        btn_custom.clicked.connect(lambda: self.canvas.open_custom_size_dialog() if hasattr(self, "canvas") and self.canvas else None)
        layout.addWidget(btn_custom)

        # Framing / Crop style options
        lbl_framing = QLabel("✂️ របៀបកាត់តម្រឹម (Framing Mode):")
        lbl_framing.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 11px; margin-top: 8px;")
        layout.addWidget(lbl_framing)

        btn_fill = QPushButton("✂️ Fill Center Crop (ពេញអេក្រង់)")
        btn_blur = QPushButton("📐 Fit + Blur Backdrop (ដាក់ព្រាល CapCut)")

        def update_framing_btns(mode):
            if mode == "fit":
                btn_blur.setStyleSheet("background-color: #064e3b; color: #6ee7b7; border: 1.5px solid #10b981; border-radius: 5px; padding: 6px; font-size: 11px; font-weight: bold; text-align: left;")
                btn_fill.setStyleSheet("background-color: #1a202c; color: #94a3b8; border: 1px solid #2d3748; border-radius: 5px; padding: 6px; font-size: 11px; text-align: left;")
            else:
                btn_fill.setStyleSheet("background-color: #0c4a6e; color: #7dd3fc; border: 1.5px solid #0284c7; border-radius: 5px; padding: 6px; font-size: 11px; font-weight: bold; text-align: left;")
                btn_blur.setStyleSheet("background-color: #1a202c; color: #94a3b8; border: 1px solid #2d3748; border-radius: 5px; padding: 6px; font-size: 11px; text-align: left;")

        def on_set_mode(mode):
            if hasattr(self, "canvas") and self.canvas:
                self.canvas.set_video_fit_mode(mode)
            update_framing_btns(mode)

        btn_fill.clicked.connect(lambda: on_set_mode("fill"))
        btn_blur.clicked.connect(lambda: on_set_mode("fit"))

        cur_init_mode = getattr(self.canvas, "video_fit_mode", "fill") if hasattr(self, "canvas") and self.canvas else "fill"
        update_framing_btns(cur_init_mode)

        layout.addWidget(btn_fill)
        layout.addWidget(btn_blur)

        layout.addStretch()
        return w

    # ------------------ ACTIONS & HELPERS ------------------
    def set_active_tool(self, key: Optional[str]):
        """Switches the drawer page to match the selected tool in the rail."""
        if not key or key not in self._page_map:
            self.hide()
            return

        self.pages.setCurrentIndex(self._page_map[key])
        titles = {
            "templates": "📐 Video Templates & Presets (គំរូវីដេអូស្រាប់ៗ)",
            "transform": "✥ Transform & Pan Video (ទាញប្លង់វីដេអូ)",
            "cc": "💬 Captions & CC AI Studio (អក្សររត់)",
            "media": "🖼️ Media, GIFs & Stickers",
            "video": "🎬 Video Overlay (PiP)",
            "text": "🔤 Typography & Text",
            "shapes": "🔷 Vector Shapes & Badges",
            "face_ar": "🎭 AI Face Mesh & AR Studio (ចាប់ផ្ទៃមុខ AI)",
            "blur": "🌫️ Blur & Censor Boxes",
            "effects": "🎨 Cinematic Color Presets",
            "ratio": "📐 Aspect Ratio & Sizing"
        }
        self.lbl_title.setText(titles.get(key, "Tool"))
        self.show()
        if key == "cc":
            self.show_cc_analytics_requested.emit()

    # ------------------ TRANSFORM & FRAMING PAGE ------------------
    def _build_transform_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        # 1. Active Instruction Card
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background-color: #0c4a6e;
                border: 1px solid #0284c7;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setContentsMargins(4, 4, 4, 4)
        ic_layout.setSpacing(4)
        lbl_info_title = QLabel("✥ Transform Mode Active")
        lbl_info_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        ic_layout.addWidget(lbl_info_title)

        lbl_info_desc = QLabel("• Drag monitor directly to pan ↔ ↕\n  (ទាញប្លង់វីដេអូ ឆ្វេង-ស្តាំ/លើ-ក្រោម)\n• Scroll wheel to zoom in/out smoothly")
        lbl_info_desc.setStyleSheet("color: #e0f2fe; font-size: 10px; line-height: 1.3;")
        ic_layout.addWidget(lbl_info_desc)
        layout.addWidget(info_card)

        # 2. Zoom Level Slider (50% to 300%)
        sec_zoom = QFrame()
        sec_zoom.setStyleSheet("background-color: #1a202c; border: 1px solid #2d3748; border-radius: 6px; padding: 6px;")
        sz_layout = QVBoxLayout(sec_zoom)
        sz_layout.setContentsMargins(4, 4, 4, 4)
        sz_layout.setSpacing(6)

        hdr_zoom = QHBoxLayout()
        hdr_zoom.addWidget(QLabel("🔍 Zoom Scale:"))
        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        hdr_zoom.addWidget(self.lbl_zoom_val)
        hdr_zoom.addStretch()

        btn_rst_zoom = QPushButton("↺ 100%")
        btn_rst_zoom.setFixedSize(46, 22)
        btn_rst_zoom.setStyleSheet("font-size: 10px; background-color: #262e3d; color: #94a3b8; border: 1px solid #334155; border-radius: 4px;")
        btn_rst_zoom.clicked.connect(lambda: self._set_zoom_from_drawer(1.0))
        hdr_zoom.addWidget(btn_rst_zoom)
        sz_layout.addLayout(hdr_zoom)

        self.slider_transform_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_transform_zoom.setRange(50, 300)
        self.slider_transform_zoom.setValue(100)
        self.slider_transform_zoom.valueChanged.connect(self._on_drawer_zoom_changed)
        sz_layout.addWidget(self.slider_transform_zoom)
        layout.addWidget(sec_zoom)

        # 3. Fine Pan Nudge Controls (4 directions)
        sec_nudge = QFrame()
        sec_nudge.setStyleSheet("background-color: #1a202c; border: 1px solid #2d3748; border-radius: 6px; padding: 6px;")
        sn_layout = QVBoxLayout(sec_nudge)
        sn_layout.setContentsMargins(4, 4, 4, 4)
        sn_layout.setSpacing(4)
        lbl_nudge_title = QLabel("🎯 Pan Position Nudge (កែសម្រួលទីតាំង):")
        lbl_nudge_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #cbd5e1;")
        sn_layout.addWidget(lbl_nudge_title)

        grid_nudge = QGridLayout()
        grid_nudge.setSpacing(4)

        btn_up = QPushButton("▲ Up")
        btn_up.setStyleSheet("background-color: #232b3b; color: #f1f5f9; border-radius: 4px; padding: 4px; font-size: 10px;")
        btn_up.clicked.connect(lambda: self._nudge_pan(0.0, -0.05))
        grid_nudge.addWidget(btn_up, 0, 1)

        btn_left = QPushButton("◀ Left")
        btn_left.setStyleSheet("background-color: #232b3b; color: #f1f5f9; border-radius: 4px; padding: 4px; font-size: 10px;")
        btn_left.clicked.connect(lambda: self._nudge_pan(-0.05, 0.0))
        grid_nudge.addWidget(btn_left, 1, 0)

        btn_center = QPushButton("• Center")
        btn_center.setStyleSheet("background-color: #0c4a6e; color: #38bdf8; font-weight: bold; border-radius: 4px; padding: 4px; font-size: 10px;")
        btn_center.clicked.connect(lambda: self._center_pan())
        grid_nudge.addWidget(btn_center, 1, 1)

        btn_right = QPushButton("Right ▶")
        btn_right.setStyleSheet("background-color: #232b3b; color: #f1f5f9; border-radius: 4px; padding: 4px; font-size: 10px;")
        btn_right.clicked.connect(lambda: self._nudge_pan(0.05, 0.0))
        grid_nudge.addWidget(btn_right, 1, 2)

        btn_down = QPushButton("▼ Down")
        btn_down.setStyleSheet("background-color: #232b3b; color: #f1f5f9; border-radius: 4px; padding: 4px; font-size: 10px;")
        btn_down.clicked.connect(lambda: self._nudge_pan(0.0, 0.05))
        grid_nudge.addWidget(btn_down, 2, 1)

        sn_layout.addLayout(grid_nudge)
        layout.addWidget(sec_nudge)

        # 4. Framing Mode Presets (Fit / Fill)
        sec_mode = QFrame()
        sec_mode.setStyleSheet("background-color: #1a202c; border: 1px solid #2d3748; border-radius: 6px; padding: 6px;")
        sm_layout = QVBoxLayout(sec_mode)
        sm_layout.setContentsMargins(4, 4, 4, 4)
        sm_layout.setSpacing(6)

        lbl_mode = QLabel("📐 Framing Mode:")
        lbl_mode.setStyleSheet("font-size: 11px; font-weight: bold; color: #cbd5e1;")
        sm_layout.addWidget(lbl_mode)

        row_mode = QHBoxLayout()
        btn_fit = QPushButton("📐 Fit + Blur")
        btn_fit.setToolTip("Fit video with blurred video background (ល្អសម្រាប់ TikTok/Shorts)")
        btn_fit.setStyleSheet("background-color: #232b3b; color: #38bdf8; border-radius: 4px; padding: 6px; font-size: 10px;")
        btn_fit.clicked.connect(lambda: self._set_fit_mode("fit"))
        row_mode.addWidget(btn_fit)

        btn_fill = QPushButton("✂️ Fill / Crop")
        btn_fill.setToolTip("Crop to fill full screen without black bars")
        btn_fill.setStyleSheet("background-color: #232b3b; color: #10b981; border-radius: 4px; padding: 6px; font-size: 10px;")
        btn_fill.clicked.connect(lambda: self._set_fit_mode("fill"))
        row_mode.addWidget(btn_fill)
        sm_layout.addLayout(row_mode)
        layout.addWidget(sec_mode)

        # 5. Flip & Rotate Actions
        row_tf = QHBoxLayout()
        btn_flip_h = QPushButton("↔ Flip H")
        btn_flip_h.setStyleSheet("background-color: #232b3b; color: #cbd5e1; border-radius: 4px; padding: 6px; font-size: 10px;")
        btn_flip_h.clicked.connect(lambda: self.canvas.toggle_flip_horizontal() if self.canvas else None)
        row_tf.addWidget(btn_flip_h)

        btn_flip_v = QPushButton("↕ Flip V")
        btn_flip_v.setStyleSheet("background-color: #232b3b; color: #cbd5e1; border-radius: 4px; padding: 6px; font-size: 10px;")
        btn_flip_v.clicked.connect(lambda: self.canvas.toggle_flip_vertical() if self.canvas else None)
        row_tf.addWidget(btn_flip_v)

        btn_rot = QPushButton("🔄 Rotate")
        btn_rot.setStyleSheet("background-color: #232b3b; color: #cbd5e1; border-radius: 4px; padding: 6px; font-size: 10px;")
        btn_rot.clicked.connect(lambda: self.canvas.rotate_video_90() if self.canvas else None)
        row_tf.addWidget(btn_rot)
        layout.addLayout(row_tf)

        # 6. Keyframe & Reset
        btn_kf = QPushButton("◆+ Add Keyframe at Current Time")
        btn_kf.setStyleSheet("""
            QPushButton {
                background-color: #0c4a6e;
                color: #38bdf8;
                border: 1px solid #0284c7;
                font-weight: bold;
                border-radius: 6px;
                padding: 7px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        btn_kf.clicked.connect(lambda: self.canvas.add_keyframe_at_current_time() if self.canvas else None)
        layout.addWidget(btn_kf)

        btn_reset_all = QPushButton("↺ Reset All Framing (កំណត់ឡើងវិញ)")
        btn_reset_all.setStyleSheet("""
            QPushButton {
                background-color: #232b3b;
                color: #f87171;
                border: 1px solid #7f1d1d;
                border-radius: 6px;
                padding: 7px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f1d1d;
                color: #ffffff;
            }
        """)
        btn_reset_all.clicked.connect(self._reset_all_framing)
        layout.addWidget(btn_reset_all)

        layout.addStretch()
        return w

    def _on_drawer_zoom_changed(self, val: int):
        scale = round(val / 100.0, 2)
        if hasattr(self, "lbl_zoom_val"):
            self.lbl_zoom_val.setText(f"{val}%")
        if self.canvas and hasattr(self.canvas, "set_video_scale"):
            self.canvas.set_video_scale(scale)

    def _set_zoom_from_drawer(self, scale: float):
        if hasattr(self, "slider_transform_zoom"):
            self.slider_transform_zoom.setValue(int(scale * 100))

    def _nudge_pan(self, dx: float, dy: float):
        if self.canvas and hasattr(self.canvas, "nudge_video_pan"):
            self.canvas.nudge_video_pan(dx, dy)

    def _center_pan(self):
        if self.canvas and hasattr(self.canvas, "set_crop_offset"):
            self.canvas.set_crop_offset(0.0, 0.0)

    def _set_fit_mode(self, mode: str):
        if self.canvas and hasattr(self.canvas, "set_video_fit_mode"):
            self.canvas.set_video_fit_mode(mode)

    def _reset_all_framing(self):
        if self.canvas and hasattr(self.canvas, "reset_video_transform"):
            self.canvas.reset_video_transform()
        if hasattr(self, "slider_transform_zoom"):
            self.slider_transform_zoom.setValue(100)

    def _on_search_changed(self, text: str):
        if hasattr(self, "_filter_templates"):
            self._filter_templates()

    # ------------------ VIDEO TEMPLATES PAGE & ENGINE ------------------
    def _build_templates_page(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        # Status & Feedback Banner
        self.lbl_template_status = QLabel("")
        self.lbl_template_status.setStyleSheet("""
            QLabel {
                background-color: #064e3b;
                color: #34d399;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.lbl_template_status.hide()
        layout.addWidget(self.lbl_template_status)

        # Header Quick Action: Clear Overlays
        row_top = QHBoxLayout()
        row_top.setSpacing(6)
        btn_clear = QPushButton("↺ Clear Template Overlays")
        btn_clear.setIcon(get_qta_icon("fa5s.trash-alt", color="#f87171"))
        btn_clear.setToolTip("Remove applied template overlays while keeping your video and subtitles")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #1f2937;
                color: #fca5a5;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 5px 8px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f1d1d;
                color: #ffffff;
                border: 1px solid #ef4444;
            }
        """)
        btn_clear.clicked.connect(self._clear_template_overlays)
        row_top.addWidget(btn_clear)
        layout.addLayout(row_top)

        # Category Filter Tabs
        cat_box = QHBoxLayout()
        cat_box.setSpacing(4)
        self._current_template_cat = "all"
        self._cat_buttons = {}

        categories = [
            ("all", "All"),
            ("shorts", "9:16 Shorts"),
            ("cinema", "16:9 Cinema"),
            ("square", "1:1 Square"),
            ("broadcast", "Broadcast")
        ]

        for cat_id, cat_lbl in categories:
            btn = QPushButton(cat_lbl)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, c=cat_id: self._filter_templates(c))
            self._cat_buttons[cat_id] = btn
            cat_box.addWidget(btn)

        layout.addLayout(cat_box)

        # Scrollable Templates Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        c_w = QWidget()
        c_layout = QVBoxLayout(c_w)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(10)

        # Template Definitions
        self._templates_data = [
            {
                "id": "tiktok_viral",
                "name": "📱 TikTok Viral Short (9:16)",
                "category": "shorts",
                "tag": "9:16 Shorts",
                "tag_color": "#ec4899",
                "ratio": "9:16",
                "fit_mode": "fill",
                "description": "Full vertical portrait with top movie title bar, glowing subtitle backdrop, and follower CTA.",
                "chips": ["📐 9:16 Vertical", "🔤 Title Bar", "🌫️ Subtitle Glass", "🔴 Follow CTA"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Top Header Box",
                        "x": 0.5, "y": 0.08, "w": 0.88, "h": 0.065,
                        "fill_color": "#090d16", "border_color": "#38bdf8", "border_width": 2,
                        "corner_radius": 8.0, "glow_enabled": True, "glow_color": "#38bdf8", "glow_radius": 12
                    },
                    {
                        "type": "text", "name": "Top Header Text",
                        "x": 0.5, "y": 0.08, "w": 0.84, "h": 0.05,
                        "text": "🔥 សម្រង់រឿងពិសេស | MOVIE HIGHLIGHTS",
                        "font_size": 24, "color": "#ffffff", "is_bold": True
                    },
                    {
                        "type": "blur_box", "name": "Subtitle Glass Backdrop",
                        "blur_mode": "glass", "blur_strength": 25, "corner_radius": 12,
                        "x": 0.5, "y": 0.76, "w": 0.90, "h": 0.10
                    },
                    {
                        "type": "text", "name": "Subtitle Glow Text",
                        "x": 0.5, "y": 0.76, "w": 0.86, "h": 0.08,
                        "text": "សម្រង់ពាក្យសន្ទនាភាពយន្ត (Auto Subtitles)",
                        "font_size": 26, "color": "#fde047", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Follow CTA Pill",
                        "x": 0.5, "y": 0.92, "w": 0.65, "h": 0.045,
                        "fill_color": "#e11d48", "border_color": "#ffffff", "border_width": 0, "corner_radius": 16.0
                    },
                    {
                        "type": "text", "name": "Follow CTA Text",
                        "x": 0.5, "y": 0.92, "w": 0.60, "h": 0.04,
                        "text": "🔴 Follow សម្រាប់ទស្សនាភាគបន្ត",
                        "font_size": 18, "color": "#ffffff", "is_bold": True
                    }
                ]
            },
            {
                "id": "cinema_masterpiece",
                "name": "🎬 Cinema Masterpiece (16:9)",
                "category": "cinema",
                "tag": "16:9 Cinema",
                "tag_color": "#38bdf8",
                "ratio": "16:9",
                "fit_mode": "fill",
                "description": "YouTube / Cinema 16:9 layout with top-right VIP stamp and lower-third cinematic backdrop.",
                "chips": ["📐 16:9 Widescreen", "★ VIP Stamp", "⬛ Cinematic Bar", "💬 Subtitles"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "VIP Stamp Box",
                        "x": 0.88, "y": 0.08, "w": 0.18, "h": 0.05,
                        "fill_color": "#e11d48", "border_color": "#ffffff", "border_width": 1, "corner_radius": 6.0
                    },
                    {
                        "type": "text", "name": "VIP Stamp Text",
                        "x": 0.88, "y": 0.08, "w": 0.16, "h": 0.04,
                        "text": "CINEMA 4K VIP",
                        "font_size": 20, "color": "#ffffff", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Lower Third Bar",
                        "x": 0.5, "y": 0.88, "w": 0.80, "h": 0.09,
                        "fill_color": "#05070a", "border_color": "#1e293b", "border_width": 1, "corner_radius": 8.0
                    },
                    {
                        "type": "text", "name": "Cinema Subtitle Text",
                        "x": 0.5, "y": 0.88, "w": 0.76, "h": 0.07,
                        "text": "អក្សររត់ភាពយន្តខ្មែរ (Khmer Dialogue)",
                        "font_size": 30, "color": "#ffffff", "is_bold": True
                    }
                ]
            },
            {
                "id": "facebook_square",
                "name": "🔲 Social Feed Square (1:1)",
                "category": "square",
                "tag": "1:1 Square",
                "tag_color": "#10b981",
                "ratio": "1:1",
                "fit_mode": "fit",
                "description": "1080x1080 Square post with bold top headline, center video with blur backdrop, and share CTA.",
                "chips": ["📐 1:1 Feed", "🌫️ Blur Backdrop", "🔤 Top Header", "💬 Share CTA"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "rect", "name": "Top Header Box",
                        "x": 0.5, "y": 0.08, "w": 0.96, "h": 0.12,
                        "fill_color": "#090d16", "border_color": "#f59e0b", "border_width": 2, "corner_radius": 0.0
                    },
                    {
                        "type": "text", "name": "Top Header Text",
                        "x": 0.5, "y": 0.08, "w": 0.92, "h": 0.10,
                        "text": "🎬 រឿងភាគល្បីប្រចាំឆ្នាំ | BEST HIGHLIGHTS",
                        "font_size": 24, "color": "#f59e0b", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rect", "name": "Bottom CTA Box",
                        "x": 0.5, "y": 0.92, "w": 0.96, "h": 0.12,
                        "fill_color": "#090d16", "border_color": "#334155", "border_width": 1, "corner_radius": 0.0
                    },
                    {
                        "type": "text", "name": "Bottom CTA Text",
                        "x": 0.5, "y": 0.92, "w": 0.92, "h": 0.10,
                        "text": "💬 ចុច Like & Share ដើម្បីរក្សាទុកទស្សនា",
                        "font_size": 22, "color": "#94a3b8", "is_bold": True
                    }
                ]
            },
            {
                "id": "reaction_pip",
                "name": "🎙️ Commentary & Reaction PiP",
                "category": "broadcast",
                "tag": "16:9 Reaction",
                "tag_color": "#8b5cf6",
                "ratio": "16:9",
                "fit_mode": "fill",
                "description": "Picture-in-picture commentary layout with webcam facecam frame and LIVE reaction badge.",
                "chips": ["📐 16:9 Cinema", "🔴 LIVE Tag", "🖼️ PiP Frame", "🎙️ Mic Audio"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Live Badge Box",
                        "x": 0.13, "y": 0.08, "w": 0.20, "h": 0.05,
                        "fill_color": "#dc2626", "border_color": "#ffffff", "border_width": 0, "corner_radius": 6.0
                    },
                    {
                        "type": "text", "name": "Live Badge Text",
                        "x": 0.13, "y": 0.08, "w": 0.18, "h": 0.04,
                        "text": "🔴 LIVE REACTION",
                        "font_size": 18, "color": "#ffffff", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Webcam PiP Box",
                        "x": 0.84, "y": 0.74, "w": 0.26, "h": 0.28,
                        "fill_color": "#090d16", "border_color": "#38bdf8", "border_width": 3,
                        "corner_radius": 12.0, "glow_enabled": True, "glow_color": "#38bdf8", "glow_radius": 15
                    },
                    {
                        "type": "text", "name": "PiP Box Label",
                        "x": 0.84, "y": 0.74, "w": 0.22, "h": 0.06,
                        "text": "🎙️ FACECAM / PIP",
                        "font_size": 18, "color": "#38bdf8", "is_bold": True
                    }
                ]
            },
            {
                "id": "breaking_news",
                "name": "📰 Breaking News Broadcast",
                "category": "broadcast",
                "tag": "16:9 News",
                "tag_color": "#ef4444",
                "ratio": "16:9",
                "fit_mode": "fill",
                "description": "TV broadcast studio with red alert tag, lower-third headline bar, and yellow live ticker tape.",
                "chips": ["📐 16:9 TV", "⚡ Breaking News", "🔴 Red Lower-Third", "⚡ Ticker Tape"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "News Tag Box",
                        "x": 0.15, "y": 0.08, "w": 0.24, "h": 0.05,
                        "fill_color": "#b91c1c", "border_color": "#ffffff", "border_width": 0, "corner_radius": 4.0
                    },
                    {
                        "type": "text", "name": "News Tag Text",
                        "x": 0.15, "y": 0.08, "w": 0.22, "h": 0.04,
                        "text": "⚡ BREAKING NEWS",
                        "font_size": 18, "color": "#ffffff", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rect", "name": "Headline Lower Third Bar",
                        "x": 0.5, "y": 0.85, "w": 1.0, "h": 0.09,
                        "fill_color": "#090d16", "border_color": "#e11d48", "border_width": 2, "corner_radius": 0.0
                    },
                    {
                        "type": "text", "name": "Headline Lower Third Text",
                        "x": 0.5, "y": 0.85, "w": 0.96, "h": 0.07,
                        "text": "🔴 ព្រឹត្តិការណ៍ពិសេសទាន់ហេតុការណ៍ | SPECIAL REPORT",
                        "font_size": 24, "color": "#ffffff", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rect", "name": "Ticker Tape Bar",
                        "x": 0.5, "y": 0.95, "w": 1.0, "h": 0.05,
                        "fill_color": "#eab308", "border_color": "#ffffff", "border_width": 0, "corner_radius": 0.0
                    },
                    {
                        "type": "text", "name": "Ticker Tape Text",
                        "x": 0.5, "y": 0.95, "w": 0.96, "h": 0.04,
                        "text": "⚡ UPDATE: AI KHMER MOVIE STUDIO • ព័ត៌មានទាន់ហេតុការណ៍ 24/7",
                        "font_size": 17, "color": "#000000", "is_bold": True
                    }
                ]
            },
            {
                "id": "sponsor_showcase",
                "name": "🏷️ Sponsor & Brand Ad (16:9)",
                "category": "cinema",
                "tag": "16:9 Brand",
                "tag_color": "#f59e0b",
                "ratio": "16:9",
                "fit_mode": "fill",
                "description": "Monetized video layout with sponsor branding stamp and discount coupon promo card.",
                "chips": ["📐 16:9 Cinema", "⭐ Partner Stamp", "🎁 Coupon Card", "🏷️ Promo Code"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Partner Stamp Box",
                        "x": 0.14, "y": 0.08, "w": 0.22, "h": 0.05,
                        "fill_color": "#0284c7", "border_color": "#ffffff", "border_width": 0, "corner_radius": 6.0
                    },
                    {
                        "type": "text", "name": "Partner Stamp Text",
                        "x": 0.14, "y": 0.08, "w": 0.20, "h": 0.04,
                        "text": "★ OFFICIAL SPONSOR ★",
                        "font_size": 18, "color": "#ffffff", "is_bold": True
                    },
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Promo Coupon Box",
                        "x": 0.82, "y": 0.84, "w": 0.30, "h": 0.14,
                        "fill_color": "#090d16", "border_color": "#f59e0b", "border_width": 2, "corner_radius": 10.0
                    },
                    {
                        "type": "text", "name": "Promo Title Text",
                        "x": 0.82, "y": 0.80, "w": 0.28, "h": 0.04,
                        "text": "🎁 SPECIAL PROMOTION",
                        "font_size": 17, "color": "#f59e0b", "is_bold": True
                    },
                    {
                        "type": "text", "name": "Promo Code Text",
                        "x": 0.82, "y": 0.87, "w": 0.28, "h": 0.04,
                        "text": "CODE: KHMER2025 (-25%)",
                        "font_size": 19, "color": "#ffffff", "is_bold": True
                    }
                ]
            },
            {
                "id": "shorts_split",
                "name": "🍿 Split-Screen Dual (9:16 Shorts)",
                "category": "shorts",
                "tag": "9:16 Split",
                "tag_color": "#06b6d4",
                "ratio": "9:16",
                "fit_mode": "fit",
                "description": "Vertical dual split-screen format with glowing center divider line and scene tags.",
                "chips": ["📐 9:16 Vertical", "⚡ Neon Divider", "🎬 Part Tag", "👇 Engagement"],
                "elements": [
                    {
                        "type": "shape", "shape_type": "line", "name": "Center Divider Line",
                        "x": 0.5, "y": 0.50, "w": 0.92, "h": 0.02,
                        "fill_color": "#38bdf8", "border_color": "#38bdf8", "border_width": 4
                    },
                    {
                        "type": "shape", "shape_type": "rounded_rect", "name": "Top Part Tag Box",
                        "x": 0.5, "y": 0.06, "w": 0.70, "h": 0.05,
                        "fill_color": "#1e293b", "border_color": "#38bdf8", "border_width": 1, "corner_radius": 8.0
                    },
                    {
                        "type": "text", "name": "Top Part Tag Text",
                        "x": 0.5, "y": 0.06, "w": 0.66, "h": 0.04,
                        "text": "🎬 PART 1 / ភាគទី ១",
                        "font_size": 20, "color": "#38bdf8", "is_bold": True
                    },
                    {
                        "type": "text", "name": "Bottom Question Text",
                        "x": 0.5, "y": 0.94, "w": 0.85, "h": 0.05,
                        "text": "តើអ្នកគិតថាតួអង្គនឹងជ្រើសរើសផ្លូវណា? 👇",
                        "font_size": 19, "color": "#fde047", "is_bold": True
                    }
                ]
            },
            {
                "id": "ultrawide_scope",
                "name": "📽️ 21:9 Cinema Scope",
                "category": "cinema",
                "tag": "21:9 Scope",
                "tag_color": "#a855f7",
                "ratio": "21:9",
                "fit_mode": "fill",
                "description": "Hollywood 2.39:1 anamorphic ultra-widescreen ratio with sleek minimalist typography.",
                "chips": ["📐 21:9 UltraWide", "🎞️ Cinema Scope", "★ Watermark", "💬 Subtitles"],
                "elements": [
                    {
                        "type": "text", "name": "Cinema Scope Watermark",
                        "x": 0.88, "y": 0.08, "w": 0.20, "h": 0.04,
                        "text": "STUDIO CINEMASCOPE 21:9",
                        "font_size": 18, "color": "#94a3b8", "is_bold": True
                    },
                    {
                        "type": "text", "name": "Cinema Scope Subtitle",
                        "x": 0.5, "y": 0.88, "w": 0.80, "h": 0.06,
                        "text": "Khmer Cinematic Dubbing Masterpiece",
                        "font_size": 24, "color": "#f8fafc", "is_bold": True
                    }
                ]
            }
        ]

        self._template_cards = []

        # Render each template card
        for tmpl in self._templates_data:
            card = self._create_template_card(tmpl)
            c_layout.addWidget(card)
            self._template_cards.append((card, tmpl["category"], tmpl["name"], tmpl["description"]))

        c_layout.addStretch(1)
        scroll.setWidget(c_w)
        layout.addWidget(scroll, 1)

        self._filter_templates("all")
        return w

    def _create_template_card(self, tmpl: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #171c26;
                border: 1px solid #232b3b;
                border-radius: 8px;
            }
            QFrame:hover {
                border: 1px solid #38bdf8;
                background-color: #1c2331;
            }
        """)
        c_vbox = QVBoxLayout(card)
        c_vbox.setContentsMargins(10, 8, 10, 8)
        c_vbox.setSpacing(6)

        # 1. Header with Badge & Title
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        lbl_tag = QLabel(tmpl.get("tag", "Preset"))
        tag_col = tmpl.get("tag_color", "#38bdf8")
        lbl_tag.setStyleSheet(f"""
            QLabel {{
                background-color: {tag_col};
                color: #ffffff;
                font-size: 9px;
                font-weight: bold;
                border-radius: 4px;
                padding: 2px 6px;
            }}
        """)
        hdr.addWidget(lbl_tag)

        lbl_title = QLabel(tmpl["name"])
        lbl_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #f8fafc;")
        hdr.addWidget(lbl_title, 1)
        c_vbox.addLayout(hdr)

        # 2. Description
        lbl_desc = QLabel(tmpl["description"])
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 10px; line-height: 1.3;")
        c_vbox.addWidget(lbl_desc)

        # 3. Feature Chips
        chips_text = "  •  ".join(tmpl.get("chips", []))
        lbl_chips = QLabel(chips_text)
        lbl_chips.setStyleSheet("color: #64748b; font-size: 9px;")
        lbl_chips.setWordWrap(True)
        c_vbox.addWidget(lbl_chips)

        # 4. Action Button: [ ⚡ Apply Template ]
        btn_apply = QPushButton("⚡ Apply Template to Video")
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #8b5cf6;
                border-radius: 5px;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
            QPushButton:pressed {
                background-color: #5b21b6;
            }
        """)
        btn_apply.clicked.connect(lambda _, tid=tmpl["id"]: self._apply_template(tid))
        c_vbox.addWidget(btn_apply)

        return card

    def _filter_templates(self, category: str = None):
        if category is not None:
            self._current_template_cat = category
            for cat_key, btn in self._cat_buttons.items():
                if cat_key == category:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #7c3aed;
                            color: #ffffff;
                            font-weight: bold;
                            border: 1px solid #a78bfa;
                            border-radius: 4px;
                            padding: 3px 8px;
                            font-size: 10px;
                        }
                    """)
                else:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #1a202c;
                            color: #94a3b8;
                            border: 1px solid #2d3748;
                            border-radius: 4px;
                            padding: 3px 8px;
                            font-size: 10px;
                        }
                        QPushButton:hover {
                            background-color: #272f3d;
                            color: #e2e8f0;
                        }
                    """)

        search_q = self.entry_search.text().lower().strip() if hasattr(self, "entry_search") else ""
        cur_cat = getattr(self, "_current_template_cat", "all")

        for card, cat, title, desc in getattr(self, "_template_cards", []):
            match_cat = (cur_cat == "all" or cat == cur_cat)
            match_query = True
            if search_q:
                match_query = (search_q in title.lower() or search_q in desc.lower() or search_q in cat.lower())
            card.setVisible(match_cat and match_query)

    def _apply_template(self, tmpl_id: str):
        if not self.canvas:
            return

        from ui_v_PyQt6.components.player.canvas_item import CanvasItem

        tmpl = next((t for t in getattr(self, "_templates_data", []) if t["id"] == tmpl_id), None)
        if not tmpl:
            return

        # 1. Save Undo State
        if hasattr(self.canvas, "save_undo_state"):
            self.canvas.save_undo_state()

        # 2. Apply Canvas Aspect Ratio & Fit Mode
        ratio = tmpl.get("ratio", "16:9")
        fit_mode = tmpl.get("fit_mode", "fill")
        if hasattr(self.canvas, "set_aspect_ratio"):
            self.canvas.set_aspect_ratio(ratio)
        if hasattr(self.canvas, "set_video_fit_mode"):
            self.canvas.set_video_fit_mode(fit_mode)

        # 3. Remove previous template items (preserving user images, videos & subtitles)
        self.canvas.items = [it for it in self.canvas.items if not getattr(it, "is_template_item", False)]

        # 4. Add template elements
        dur = getattr(self.canvas, "duration", 0.0)
        end_t = dur if dur > 0 else 3600.0

        for elem in tmpl.get("elements", []):
            el_type = elem.get("type", "text")
            if el_type == "text":
                it = CanvasItem(
                    item_type="text",
                    x=elem.get("x", 0.5),
                    y=elem.get("y", 0.5),
                    w=elem.get("w", 0.6),
                    h=elem.get("h", 0.1),
                    z_index=len(self.canvas.items) + 1,
                    name=elem.get("name", "Template Text"),
                    start_time=0.0,
                    end_time=end_t
                )
                it.text = elem.get("text", "")
                it.font_size = elem.get("font_size", 28)
                it.font_color = QColor(elem.get("color", "#ffffff"))
                bg_col = elem.get("bg_color")
                if bg_col:
                    it.bg_color = QColor(bg_col)
                else:
                    it.bg_color = QColor(0, 0, 0, 0)
                it.is_bold = elem.get("is_bold", True)
                it.corner_radius = elem.get("corner_radius", 0.0)
                it.is_template_item = True
                self.canvas.items.append(it)
                self.canvas.item_added.emit(it)

            elif el_type == "shape":
                it = CanvasItem(
                    item_type="shape",
                    x=elem.get("x", 0.5),
                    y=elem.get("y", 0.5),
                    w=elem.get("w", 0.4),
                    h=elem.get("h", 0.15),
                    z_index=len(self.canvas.items) + 1,
                    name=elem.get("name", "Template Shape"),
                    start_time=0.0,
                    end_time=end_t
                )
                it.shape_type = elem.get("shape_type", "rect")
                it.fill_color = QColor(elem.get("fill_color", "#000000"))
                it.border_color = QColor(elem.get("border_color", "#ffffff"))
                it.border_width = elem.get("border_width", 0)
                it.stroke_style = "solid" if it.border_width > 0 else "none"
                it.corner_radius = elem.get("corner_radius", 0.0)
                if elem.get("glow_enabled"):
                    it.glow_enabled = True
                    it.glow_color = QColor(elem.get("glow_color", "#38bdf8"))
                    it.glow_radius = elem.get("glow_radius", 15)
                it.is_template_item = True
                self.canvas.items.append(it)
                self.canvas.item_added.emit(it)

            elif el_type == "blur_box":
                it = CanvasItem(
                    item_type="blur_box",
                    x=elem.get("x", 0.5),
                    y=elem.get("y", 0.5),
                    w=elem.get("w", 0.8),
                    h=elem.get("h", 0.12),
                    z_index=len(self.canvas.items) + 1,
                    name=elem.get("name", "Template Glass Box"),
                    blur_mode=elem.get("blur_mode", "glass"),
                    blur_strength=elem.get("blur_strength", 25),
                    corner_radius=elem.get("corner_radius", 10),
                    start_time=0.0,
                    end_time=end_t
                )
                it.is_template_item = True
                self.canvas.items.append(it)
                self.canvas.item_added.emit(it)

        self.canvas.canvas_modified.emit()
        self.canvas.update()

        # Visual Feedback Banner
        if hasattr(self, "lbl_template_status"):
            self.lbl_template_status.setText(f"✅ Applied: {tmpl['name']}")
            self.lbl_template_status.show()
            QTimer.singleShot(3000, self.lbl_template_status.hide)

    def _clear_template_overlays(self):
        if not self.canvas:
            return
        if hasattr(self.canvas, "save_undo_state"):
            self.canvas.save_undo_state()
        self.canvas.items = [it for it in self.canvas.items if not getattr(it, "is_template_item", False)]
        self.canvas.canvas_modified.emit()
        self.canvas.update()
        if hasattr(self, "lbl_template_status"):
            self.lbl_template_status.setText("↺ Template overlays cleared")
            self.lbl_template_status.show()
            QTimer.singleShot(2500, self.lbl_template_status.hide)

    def _browse_media_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Overlay Media / Image / Sticker / GIF", "",
            "Media Files (*.png *.jpg *.jpeg *.webp *.svg *.bmp *.gif)"
        )
        if f:
            self.add_media_requested.emit(f)

    def _browse_video_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Overlay Video Clip (PiP)", "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts)"
        )
        if f:
            self.add_video_requested.emit(f)

    def _sync_blur_all_subs(self):
        if self.canvas and hasattr(self.canvas, "replicate_selected_for_all_subtitles"):
            self.canvas.replicate_selected_for_all_subtitles()


class MonitorHeaderBar(QFrame):
    """
    Sleek top bar directly above the canvas monitor matching the user's reference screenshot:
    - Undo / Redo buttons
    - Canvas dimensions indicator (e.g. 1280 x 720)
    - Aspect Ratio & Zoom Quick Dropdowns
    """
    undo_clicked = Signal()
    redo_clicked = Signal()
    aspect_changed = Signal(str)
    zoom_changed = Signal(float)
    presets_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setStyleSheet("""
            MonitorHeaderBar {
                background-color: #11141c;
                border-bottom: 1px solid #1e2533;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        # Undo / Redo
        btn_undo = QPushButton()
        btn_undo.setFixedSize(28, 26)
        btn_undo.setIcon(get_qta_icon("fa5s.undo", color="#94a3b8"))
        btn_undo.setIconSize(QSize(13, 13))
        btn_undo.setToolTip("Undo (Ctrl+Z)")
        btn_undo.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background-color: #1e2533; }")
        btn_undo.clicked.connect(self.undo_clicked.emit)
        layout.addWidget(btn_undo)

        btn_redo = QPushButton()
        btn_redo.setFixedSize(28, 26)
        btn_redo.setIcon(get_qta_icon("fa5s.redo", color="#94a3b8"))
        btn_redo.setIconSize(QSize(13, 13))
        btn_redo.setToolTip("Redo (Ctrl+Y)")
        btn_redo.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background-color: #1e2533; }")
        btn_redo.clicked.connect(self.redo_clicked.emit)
        layout.addWidget(btn_redo)

        # Canvas Resolution / Aspect display
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("background-color: #283142; max-width: 1px;")
        layout.addWidget(sep)

        self.lbl_dims = QLabel("1280 x 720")
        self.lbl_dims.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px; padding: 0 4px;")
        layout.addWidget(self.lbl_dims)

        layout.addStretch()

        # Aspect Ratio Selector
        layout.addWidget(QLabel("Ratio:"))
        self.combo_ratio = QComboBox()
        self.combo_ratio.addItems(["Fit Video", "16:9 Long Video", "9:16 TikTok / Shorts", "1:1 Square", "4:5 Portrait", "21:9 Cinema", "Custom Size..."])
        self.combo_ratio.setStyleSheet("""
            QComboBox {
                background-color: #1a202c;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
        """)
        self.combo_ratio.currentTextChanged.connect(self._on_ratio_changed)
        layout.addWidget(self.combo_ratio)

        # Quick Framing / Crop Toggle Button: [ ✂️ Crop / Fill ]
        self.btn_fit_toggle = QPushButton("✂️ Crop")
        self.btn_fit_toggle.setToolTip("Framing Style: Toggle between Fill & Center Crop vs Fit with Blur Background")
        self.btn_fit_toggle.setStyleSheet("""
            QPushButton {
                background-color: #1a202c;
                color: #38bdf8;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #232b38;
                border: 1px solid #38bdf8;
            }
        """)
        self.btn_fit_toggle.clicked.connect(self._toggle_fit_mode)
        layout.addWidget(self.btn_fit_toggle)

        # 🤖 Auto Reframe (TikTok 9:16) AI Face & Speaker Tracking Button
        self.btn_reframe = QPushButton(" 🤖 Auto Reframe")
        self.btn_reframe.setIcon(get_qta_icon("fa5s.crop-alt", color="#38bdf8"))
        self.btn_reframe.setToolTip("Auto Face Tracking & SciPy Camera Reframe for TikTok / Shorts (9:16)")
        self.btn_reframe.setStyleSheet("""
            QPushButton {
                background-color: #1a2333;
                color: #38bdf8;
                font-weight: bold;
                border: 1px solid #0284c7;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        self.btn_reframe.clicked.connect(self._on_auto_reframe_clicked)
        layout.addWidget(self.btn_reframe)

        # Presets Button
        btn_fx = QPushButton(" 🎨 Color Presets")
        btn_fx.setIcon(get_qta_icon("fa5s.magic", color="#f97316"))
        btn_fx.setStyleSheet("""
            QPushButton {
                background-color: #272f3f;
                color: #f97316;
                font-weight: bold;
                border: 1px solid #f97316;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #323b4f;
            }
        """)
        btn_fx.clicked.connect(self.presets_clicked.emit)
        layout.addWidget(btn_fx)

    def _toggle_fit_mode(self):
        player = self.parent()
        canvas = getattr(player, "canvas", None)
        if canvas:
            cur = getattr(canvas, "video_fit_mode", "fill")
            new_mode = "fit" if cur == "fill" else "fill"
            canvas.set_video_fit_mode(new_mode)
            self.btn_fit_toggle.setText("📐 Blur" if new_mode == "fit" else "✂️ Crop")

    def _on_auto_reframe_clicked(self):
        player = self.parent()
        if hasattr(player, "open_auto_reframe_dialog"):
            player.open_auto_reframe_dialog()

    def _on_ratio_changed(self, text: str):
        if "Custom" in text:
            player = self.parent()
            canvas = getattr(player, "canvas", None)
            if canvas:
                canvas.open_custom_size_dialog()
            return

        mapping = {
            "Fit Video": "fit",
            "16:9 Long Video": "16:9",
            "9:16 TikTok / Shorts": "9:16",
            "1:1 Square": "1:1",
            "4:5 Portrait": "4:5",
            "21:9 Cinema": "21:9"
        }
        self.aspect_changed.emit(mapping.get(text, "fit"))

    def set_dimensions(self, w: int, h: int, tag: str = ""):
        suffix = f" ({tag})" if tag else ""
        self.lbl_dims.setText(f"{w} x {h}{suffix}")
