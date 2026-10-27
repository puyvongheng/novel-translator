"""
AI Creator Studio - Left Panel: Media & AI Tools Library
Provides collapsible navigation and instant access to:
1. Media: Project Files, Videos, Audio, Images, Stickers, Templates
2. AI Tools: Speech Recognition, AI Translation, Speaker Detection, Text-to-Speech,
   Voice Cloning, Voice Separation, AI Reframe (9:16), AI Highlights & Chunker
3. Editing: Text, Captions, Transitions, Video Effects, Color LUTs, Shapes & Blurs
Includes search bar, category filtering, drag-and-drop support, and direct action triggers.
"""

import os
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QFrame, QSizePolicy, Qt, Signal, QCursor, QFont,
    QDrag, QMimeData, QPoint
)
from ui_v_PyQt6.styles import (
    COLOR_MAIN_BG, COLOR_SECONDARY_BG, COLOR_PANEL_BG, COLOR_ELEVATED,
    COLOR_ACCENT, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_SECONDARY,
    COLOR_SUCCESS, COLOR_WARNING
)
from ui_v_PyQt6.components.responsive import ResponsivePanel, ResponsiveBreakpoint, FlowLayout


class MediaAiPanel(ResponsivePanel):
    """
    Professional Responsive Sidebar for AI Creator Studio.
    Integrates Media Library, AI Pipelines, and Creative Editing Tools with dynamic reflow.
    """
    # Action Signals
    tool_triggered = Signal(str)  # tool identifier
    media_imported = Signal(str)  # file path
    add_overlay_requested = Signal(str, str)  # (type, param)
    request_workspace = Signal(str)  # workspace preset name

    def __init__(self, parent=None, **callbacks):
        super().__init__(compact_threshold=320, normal_threshold=500, wide_threshold=850, parent=parent)
        self.callbacks = callbacks
        self.setMinimumWidth(220)
        self.setMaximumWidth(1600)  # Flexible docking & multi-monitor support

        self.current_category = "media"  # "media", "ai_tools", "editing"
        self.active_subfilter = "All"
        self.search_query = ""

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # 1. Header with Title & Import Button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(2, 0, 2, 0)
        top_bar.setSpacing(6)

        lbl_title = QLabel("🎨 Studio Library")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {COLOR_ACCENT};")
        top_bar.addWidget(lbl_title)
        top_bar.addStretch()

        self.btn_import = QPushButton("📥 Import")
        self.btn_import.setToolTip("Import Video, Audio, or Subtitle File into Project")
        self.btn_import.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ELEVATED};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                border-color: #7A87FF;
                color: #ffffff;
            }}
        """)
        self.btn_import.clicked.connect(self._on_import_clicked)
        top_bar.addWidget(self.btn_import)
        layout.addLayout(top_bar)

        # 2. Search Input Box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search media, AI tools, effects...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_SECONDARY_BG};
                color: {COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {COLOR_ACCENT};
                background-color: {COLOR_PANEL_BG};
            }}
        """)
        self.search_input.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_input)

        # 3. Main Navigation Category Switcher Tabs (Media | AI Tools | Editing)
        cat_bar = QHBoxLayout()
        cat_bar.setSpacing(4)
        self.cat_buttons = {}

        categories = [
            ("media", "📁 Media"),
            ("ai_tools", "🤖 AI Tools"),
            ("editing", "🎨 Editing")
        ]

        for cat_id, label in categories:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(cat_id == self.current_category)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _, c=cat_id: self._set_category(c))
            self.cat_buttons[cat_id] = btn
            cat_bar.addWidget(btn)

        layout.addLayout(cat_bar)
        self._update_cat_button_styles()

        # 4. Sub-Filter Pills Row (FlowLayout for dynamic multi-line wrapping)
        self.filter_container = QWidget()
        self.filter_bar = FlowLayout(self.filter_container, margin=0, h_spacing=4, v_spacing=4)
        layout.addWidget(self.filter_container)

        # 5. Scrollable Content Area with Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(2, 4, 2, 4)
        self.cards_layout.setSpacing(6)

        self.scroll_area.setWidget(self.cards_container)
        layout.addWidget(self.scroll_area, 1)

        # Initial Render
        self._render_current_view()

    def _update_cat_button_styles(self):
        for cat_id, btn in self.cat_buttons.items():
            is_active = (cat_id == self.current_category)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT if is_active else COLOR_ELEVATED};
                    color: {"#ffffff" if is_active else COLOR_TEXT_SECONDARY};
                    border: 1px solid {COLOR_ACCENT if is_active else COLOR_BORDER};
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 2px 4px;
                }}
                QPushButton:hover {{
                    background-color: {COLOR_ACCENT};
                    color: #ffffff;
                }}
            """)

    def _set_category(self, cat_id: str):
        self.current_category = cat_id
        self.active_subfilter = "All"
        self._update_cat_button_styles()
        self._render_current_view()

    def _on_search_changed(self, text: str):
        self.search_query = text.strip().lower()
        self._render_cards()

    def _on_import_clicked(self):
        cb = self.callbacks.get("on_import")
        if cb:
            cb()
        else:
            from ui_v_PyQt6.qt_compat import QFileDialog
            fpath, _ = QFileDialog.getOpenFileName(
                self, "Import Media into AI Creator Studio", "",
                "Media Files (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.srt *.vtt);;All Files (*.*)"
            )
            if fpath:
                self.media_imported.emit(fpath)

    def _render_current_view(self):
        # Clear filter pills
        while self.filter_bar.count():
            item = self.filter_bar.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build subfilters based on category
        if self.current_category == "media":
            subfilters = ["All", "Videos", "Audio", "Images", "Stickers"]
        elif self.current_category == "ai_tools":
            subfilters = ["All", "Speech", "Translate", "Dubbing", "Video AI"]
        else:
            subfilters = ["All", "Text", "Effects", "LUTs", "Shapes"]

        for sf in subfilters:
            btn = QPushButton(sf)
            btn.setFixedHeight(22)
            btn.setCheckable(True)
            btn.setChecked(sf == self.active_subfilter)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            is_active = (sf == self.active_subfilter)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLOR_ACCENT if is_active else COLOR_SECONDARY_BG};
                    color: {"#ffffff" if is_active else COLOR_TEXT_SECONDARY};
                    border: 1px solid {COLOR_ACCENT if is_active else COLOR_BORDER};
                    border-radius: 11px;
                    font-size: 10px;
                    font-weight: 600;
                    padding: 1px 8px;
                }}
                QPushButton:hover {{
                    border-color: {COLOR_ACCENT};
                    color: #ffffff;
                }}
            """)
            btn.clicked.connect(lambda _, s=sf: self._set_subfilter(s))
            self.filter_bar.addWidget(btn)

        self._render_cards()

    def _set_subfilter(self, sf: str):
        self.active_subfilter = sf
        self._render_current_view()

    def _render_cards(self):
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items = self._get_items_for_category()

        # Filter by search & subfilter
        filtered = []
        for it in items:
            if self.active_subfilter != "All" and it.get("sub") != self.active_subfilter:
                continue
            if self.search_query:
                name_match = self.search_query in it.get("name", "").lower()
                desc_match = self.search_query in it.get("desc", "").lower()
                if not (name_match or desc_match):
                    continue
            filtered.append(it)

        if not filtered:
            lbl_empty = QLabel("🔍 No matching items found")
            lbl_empty.setStyleSheet(f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; padding: 16px; text-align: center;")
            lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(lbl_empty)
        else:
            for it in filtered:
                card = self._create_item_card(it)
                self.cards_layout.addWidget(card)

        self.cards_layout.addStretch()

    def _get_items_for_category(self):
        if self.current_category == "media":
            return [
                {"id": "m_sample_video", "sub": "Videos", "icon": "🎬", "name": "Active Project Video", "desc": "Master timeline video clip", "action": "open_video"},
                {"id": "m_import_video", "sub": "Videos", "icon": "📹", "name": "+ Import Video File", "desc": "MP4, MKV, MOV, WebM", "action": "import_video"},
                {"id": "m_import_audio", "sub": "Audio", "icon": "🎵", "name": "+ Add Soundtrack / BGM", "desc": "MP3, WAV, M4A, FLAC", "action": "import_audio"},
                {"id": "m_import_srt", "sub": "Videos", "icon": "📝", "name": "+ Import Subtitles (SRT)", "desc": "SRT, VTT, ASS, SSA", "action": "import_srt"},
                {"id": "m_logo_sticker", "sub": "Images", "icon": "🖼️", "name": "Studio Watermark Logo", "desc": "Corner branding overlay", "action": "add_logo"},
                {"id": "m_pip_overlay", "sub": "Stickers", "icon": "📺", "name": "Picture-in-Picture (PiP)", "desc": "Secondary video overlay", "action": "add_pip"},
            ]
        elif self.current_category == "ai_tools":
            return [
                {"id": "ai_asr", "sub": "Speech", "icon": "🎙️", "name": "Speech Recognition (ASR)", "desc": "Faster-Whisper & FunASR Paraformer", "action": "ai_asr", "badge": "AI Turbo"},
                {"id": "ai_trans", "sub": "Translate", "icon": "🌐", "name": "AI Movie Translation", "desc": "Google GTX, Gemini 2.0 & ChatGPT", "action": "ai_translate", "badge": "Accurate"},
                {"id": "ai_diarize", "sub": "Speech", "icon": "👥", "name": "Speaker Detection", "desc": "Actor A / B Voice Separation (WhisperX)", "action": "ai_diarize", "badge": "Smart"},
                {"id": "ai_tts", "sub": "Dubbing", "icon": "🗣️", "name": "Khmer TTS Voice Studio", "desc": "Edge Neural (Piseth & Sreymom)", "action": "ai_tts", "badge": "Natural"},
                {"id": "ai_clone", "sub": "Dubbing", "icon": "🧬", "name": "Voice Cloning Engine", "desc": "Clone actor timbre & tone", "action": "ai_clone", "badge": "Studio"},
                {"id": "ai_reframe", "sub": "Video AI", "icon": "📱", "name": "Auto Reframe 9:16", "desc": "MediaPipe Face Tracking for TikTok", "action": "ai_reframe", "badge": "TikTok"},
                {"id": "ai_vocal_sep", "sub": "Dubbing", "icon": "🎼", "name": "Vocal & BGM Separation", "desc": "Demucs AI Clean Dialogue Extraction", "action": "ai_vocal_sep", "badge": "Clean"},
                {"id": "ai_chunker", "sub": "Video AI", "icon": "✂️", "name": "AI Dialogue Chunker", "desc": "Smart SRT Splitter & Highlights", "action": "ai_chunker", "badge": "Fast"},
            ]
        else: # editing
            return [
                {"id": "ed_text", "sub": "Text", "icon": "🔤", "name": "Add Dialogue Text", "desc": "Custom title or subtitle box", "action": "add_text"},
                {"id": "ed_glass", "sub": "Effects", "icon": "✨", "name": "Frosted Glass Censor", "desc": "Modern frosted glass overlay", "action": "add_glass"},
                {"id": "ed_blur", "sub": "Effects", "icon": "🌫️", "name": "Smooth Blur Box", "desc": "Customizable Gaussian blur box", "action": "add_blur"},
                {"id": "ed_mosaic", "sub": "Effects", "icon": "🔲", "name": "Mosaic Pixelate Censor", "desc": "Hide watermarks & logos", "action": "add_mosaic"},
                {"id": "ed_blackout", "sub": "Shapes", "icon": "⬛", "name": "Blackout Dialogue Bar", "desc": "Covers hardcoded subtitles", "action": "add_blackout"},
                {"id": "ed_lut_cinematic", "sub": "LUTs", "icon": "🎭", "name": "Cinematic Teal & Orange", "desc": "Hollywood cinema color grade", "action": "lut_cinematic"},
                {"id": "ed_lut_warm", "sub": "LUTs", "icon": "🌅", "name": "Golden Sunset Warmth", "desc": "Rich warm documentary grade", "action": "lut_warm"},
                {"id": "ed_shape_rect", "sub": "Shapes", "icon": "⏹️", "name": "Rounded Vector Badge", "desc": "Dynamic lower third background", "action": "add_rect"},
            ]

    def _create_item_card(self, it: dict) -> QFrame:
        card = QFrame()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLOR_ELEVATED};
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
            QFrame:hover {{
                border-color: {COLOR_ACCENT};
                background-color: #343A46;
            }}
        """)

        h_layout = QHBoxLayout(card)
        h_layout.setContentsMargins(6, 4, 6, 4)
        h_layout.setSpacing(8)

        # Icon box
        lbl_icon = QLabel(it.get("icon", "📄"))
        lbl_icon.setStyleSheet("font-size: 18px; min-width: 24px;")
        h_layout.addWidget(lbl_icon)

        # Texts
        v_txt = QVBoxLayout()
        v_txt.setSpacing(1)

        h_top = QHBoxLayout()
        h_top.setSpacing(4)
        lbl_name = QLabel(it.get("name", ""))
        lbl_name.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {COLOR_TEXT_PRIMARY};")
        h_top.addWidget(lbl_name)

        badge_txt = it.get("badge")
        if badge_txt:
            lbl_badge = QLabel(badge_txt)
            lbl_badge.setStyleSheet(f"""
                background-color: #384260;
                color: #A5B4FC;
                font-size: 9px;
                font-weight: bold;
                padding: 1px 4px;
                border-radius: 4px;
            """)
            h_top.addWidget(lbl_badge)
        h_top.addStretch()
        v_txt.addLayout(h_top)

        lbl_desc = QLabel(it.get("desc", ""))
        lbl_desc.setStyleSheet(f"font-size: 10px; color: {COLOR_TEXT_SECONDARY};")
        v_txt.addWidget(lbl_desc)

        h_layout.addLayout(v_txt, 1)

        # Action Trigger Button
        btn_action = QPushButton("Run" if self.current_category == "ai_tools" else "+ Add")
        btn_action.setFixedSize(46, 22)
        is_ai = (self.current_category == "ai_tools")
        btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT if is_ai else COLOR_SECONDARY_BG};
                color: {"#ffffff" if is_ai else COLOR_TEXT_PRIMARY};
                border: 1px solid {COLOR_BORDER};
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT};
                color: #ffffff;
                border-color: #7A87FF;
            }}
        """)
        btn_action.clicked.connect(lambda _, a=it.get("action"): self._trigger_action(a))
        h_layout.addWidget(btn_action)

        return card

    def _trigger_action(self, action_id: str):
        if not action_id:
            return

        self.tool_triggered.emit(action_id)
        cb = self.callbacks.get(action_id)
        if cb:
            cb()
        else:
            # Route generic actions
            if action_id == "open_video":
                c = self.callbacks.get("on_open_video")
                if c: c()
            elif action_id == "import_video":
                c = self.callbacks.get("on_import")
                if c: c()
            elif action_id == "import_audio":
                c = self.callbacks.get("on_import_audio")
                if c: c()
            elif action_id == "import_srt":
                c = self.callbacks.get("on_import_srt")
                if c: c()
            elif action_id in ("add_glass", "add_blur", "add_mosaic", "add_blackout"):
                mode = action_id.replace("add_", "")
                self.add_overlay_requested.emit("blur_box", mode)
                c = self.callbacks.get("on_add_blur_mode")
                if c: c(mode)
            elif action_id == "ai_asr":
                c = self.callbacks.get("on_ai_asr")
                if c: c()
            elif action_id == "ai_translate":
                c = self.callbacks.get("on_ai_translate")
                if c: c()
            elif action_id == "ai_tts":
                c = self.callbacks.get("on_ai_tts")
                if c: c()
            elif action_id == "ai_reframe":
                c = self.callbacks.get("on_ai_reframe")
                if c: c()
