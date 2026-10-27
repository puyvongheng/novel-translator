"""
CapCut Voice Effects Studio Dialog
Interactive modern studio dialog allowing users to transform any voice line or MP3 audio clip
into popular CapCut voice effects (Kid, Robot, Chipmunk, Deep Male, Echo Hall, Megaphone, etc.).
"""

import os
from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QGridLayout, QSlider, QSpinBox,
    QDoubleSpinBox, QComboBox, QWidget, Qt, Signal, QColor, QSize, QIcon, QTimer
)
from services.dubbing.audio_effects import (
    CAPCUT_VOICE_EFFECTS, apply_voice_effect_to_file,
    preview_voice_effect, stop_voice_effect_preview,
    get_voice_effect_label, get_voice_effect_icon
)


class VoiceEffectCard(QFrame):
    """Clickable card displaying a single CapCut voice effect with icon and preview button."""
    selected = Signal(str)  # Emits fx_key
    preview_requested = Signal(str)  # Emits fx_key

    def __init__(self, fx_key: str, label: str, tag: str, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.fx_key = fx_key
        self.label = label
        self.tag = tag
        self.is_active = is_active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(82)
        self._init_ui()
        self.update_style()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        icon_char = get_voice_effect_icon(self.fx_key)
        self.lbl_icon = QLabel(icon_char)
        self.lbl_icon.setStyleSheet("font-size: 20px;")
        top_row.addWidget(self.lbl_icon)

        # Name and clean title
        clean_title = self.label
        if "(" in clean_title:
            main_name = clean_title.split("(")[0].strip()
            sub_name = "(" + clean_title.split("(")[1]
        else:
            main_name = clean_title
            sub_name = ""

        v_title = QVBoxLayout()
        v_title.setSpacing(1)
        self.lbl_name = QLabel(main_name)
        self.lbl_name.setStyleSheet("font-weight: bold; font-size: 11px; color: #f8fafc;")
        v_title.addWidget(self.lbl_name)

        if sub_name:
            self.lbl_sub = QLabel(sub_name)
            self.lbl_sub.setStyleSheet("font-size: 9px; color: #94a3b8;")
            v_title.addWidget(self.lbl_sub)
        top_row.addLayout(v_title, 1)

        # Quick Test Button
        self.btn_test = QPushButton("▶")
        self.btn_test.setToolTip("ស្តាប់សាកល្បង Effect នេះភ្លាមៗ")
        self.btn_test.setFixedSize(26, 24)
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)
        self.btn_test.clicked.connect(lambda: self.preview_requested.emit(self.fx_key))
        top_row.addWidget(self.btn_test)

        layout.addLayout(top_row)

        # Tag Badge
        tag_colors = {
            "pitch_up": "#ec4899",
            "pitch_down": "#f59e0b",
            "vocoder": "#06b6d4",
            "reverb": "#8b5cf6",
            "filter": "#10b981",
            "distortion": "#ef4444",
            "horror": "#9333ea",
            "synth": "#3b82f6",
            "mod": "#14b8a6",
            "cinema": "#eab308",
            "whisper": "#64748b",
            "none": "#475569"
        }
        tag_col = tag_colors.get(self.tag, "#38bdf8")
        self.lbl_tag = QLabel(self.tag.upper().replace("_", " "))
        self.lbl_tag.setStyleSheet(f"""
            background-color: rgba(255, 255, 255, 0.06);
            color: {tag_col};
            font-size: 8px;
            font-weight: bold;
            padding: 1px 4px;
            border-radius: 3px;
        """)
        self.lbl_tag.setFixedHeight(14)
        layout.addWidget(self.lbl_tag, 0, Qt.AlignmentFlag.AlignLeft)

    def set_active(self, active: bool):
        self.is_active = active
        self.update_style()

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                QFrame {
                    background-color: #172554;
                    border: 2px solid #38bdf8;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #161b26;
                    border: 1px solid #283548;
                    border-radius: 8px;
                }
                QFrame:hover {
                    background-color: #1e2638;
                    border-color: #0284c7;
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.fx_key)
        super().mousePressEvent(event)


class CapCutVoiceDialog(QDialog):
    """
    Studio Dialog allowing users to select and apply CapCut voice changer effects
    directly to audio clips and dialogue lines from the Timeline.
    """
    effect_applied = Signal(str, float, float)  # (effect_key, volume, speed)
    batch_effect_applied = Signal(str, str, str, float, float)  # (effect_key, scope, character_name, volume, speed)

    def __init__(self, audio_data: dict, parent=None):
        super().__init__(parent)
        self.audio_data = audio_data or {}
        self.raw_dict = self.audio_data.get("raw") if isinstance(self.audio_data.get("raw"), dict) else self.audio_data

        # Detect character name if this is a subtitle line
        self.target_character = (
            self.raw_dict.get("speaker")
            or self.raw_dict.get("actor")
            or self.raw_dict.get("character")
            or ""
        )
        if not self.target_character and self.raw_dict.get("gender"):
            g = self.raw_dict.get("gender")
            self.target_character = "តួស្រី (Female)" if g == "female" else ("តួប្រុស (Male)" if g == "male" else "")

        self.apply_scope = "clip"  # "clip", "character", "all"

        # Detect audio path
        self.audio_path = (
            self.raw_dict.get("orig_path")
            or self.raw_dict.get("path")
            or self.raw_dict.get("orig_audio")
            or self.raw_dict.get("audio_file")
            or self.raw_dict.get("audio_path")
            or self.audio_data.get("path")
        )
        self.selected_effect = self.raw_dict.get("voice_effect", "none") or "none"
        self._cards = {}

        self.setWindowTitle("✨ CapCut Voice Effects Studio (កែសម្រួលសំឡេង)")
        self.setMinimumSize(780, 600)
        self.resize(840, 640)
        self.setStyleSheet("background-color: #0d1117; color: #f8fafc;")

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:0.5 #0f172a, stop:1 #1e293b);
                border: 1px solid #312e81;
                border-radius: 10px;
                padding: 10px 14px;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(12)

        lbl_logo = QLabel("🎙️")
        lbl_logo.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(lbl_logo)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        lbl_h_title = QLabel("CapCut Voice Effects Studio (ប្តូរសំឡេងបែប CapCut)")
        lbl_h_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        v_head.addWidget(lbl_h_title)

        clip_name = self.audio_data.get("name", "Audio Clip")
        dur_val = float(self.audio_data.get("duration", 0.0))
        lbl_h_sub = QLabel(f"🎵 Clip: {clip_name[:40]} | ⏱️ រយៈពេល: {dur_val:.2f}s | File: {os.path.basename(self.audio_path) if self.audio_path else 'No audio file'}")
        lbl_h_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        v_head.addWidget(lbl_h_sub)
        h_layout.addLayout(v_head, 1)

        # Current Active Badge
        self.lbl_active_badge = QLabel(f"Current: {get_voice_effect_icon(self.selected_effect)} {self.selected_effect.upper()}")
        self.lbl_active_badge.setStyleSheet("""
            background-color: #0284c7;
            color: #ffffff;
            font-size: 11px;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 6px;
        """)
        h_layout.addWidget(self.lbl_active_badge)
        main_layout.addWidget(header_card)

        # Main Scrollable Grid of CapCut Effects
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background: transparent;")

        grid_container = QWidget()
        grid_container.setStyleSheet("background: transparent;")
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setContentsMargins(4, 4, 4, 4)
        self.grid_layout.setSpacing(8)

        cols = 3
        for idx, (fx_key, label, tag) in enumerate(CAPCUT_VOICE_EFFECTS):
            card = VoiceEffectCard(
                fx_key=fx_key,
                label=label,
                tag=tag,
                is_active=(fx_key == self.selected_effect)
            )
            card.selected.connect(self._on_card_selected)
            card.preview_requested.connect(self._on_preview_requested)
            self._cards[fx_key] = card
            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(card, row, col)

        scroll_area.setWidget(grid_container)
        main_layout.addWidget(scroll_area, 1)

        # Fine-Tuning Controls Card
        tuning_card = QFrame()
        tuning_card.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        tune_lay = QHBoxLayout(tuning_card)
        tune_lay.setContentsMargins(4, 4, 4, 4)
        tune_lay.setSpacing(14)

        # Volume
        tune_lay.addWidget(QLabel("🔊 Volume:"))
        self.spin_vol = QSpinBox()
        self.spin_vol.setRange(0, 300)
        curr_vol = int(round(float(self.audio_data.get("volume", 1.0)) * 100))
        self.spin_vol.setValue(curr_vol if curr_vol > 0 else 100)
        self.spin_vol.setSuffix("%")
        self.spin_vol.setFixedWidth(70)
        self.spin_vol.setStyleSheet(self._input_style())
        tune_lay.addWidget(self.spin_vol)

        # Speed
        tune_lay.addWidget(QLabel("⚡ Speed:"))
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.25, 3.0)
        self.spin_speed.setSingleStep(0.05)
        self.spin_speed.setValue(float(self.audio_data.get("speed", 1.0) or 1.0))
        self.spin_speed.setSuffix("x")
        self.spin_speed.setFixedWidth(70)
        self.spin_speed.setStyleSheet(self._input_style())
        tune_lay.addWidget(self.spin_speed)

        tune_lay.addStretch()

        # Play / Stop Preview Buttons
        self.btn_play_selected = QPushButton(" ▶️ ស្តាប់ Effect ដែលជ្រើស (Play)")
        self.btn_play_selected.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_selected.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.btn_play_selected.clicked.connect(lambda: self._on_preview_requested(self.selected_effect))
        tune_lay.addWidget(self.btn_play_selected)

        self.btn_stop = QPushButton(" ⏹️ ផ្អាក (Stop)")
        self.btn_stop.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #374151;
                color: #f3f4f6;
                font-weight: bold;
                border-radius: 5px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #4b5563; }
        """)
        self.btn_stop.clicked.connect(stop_voice_effect_preview)
        tune_lay.addWidget(self.btn_stop)

        main_layout.addWidget(tuning_card)

        # Scope Selection Card (Single Clip vs Character vs Full Project)
        scope_card = QFrame()
        scope_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e293b);
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px 12px;
            }
        """)
        scope_lay = QHBoxLayout(scope_card)
        scope_lay.setContentsMargins(4, 4, 4, 4)
        scope_lay.setSpacing(10)

        lbl_sc_title = QLabel("🎯 វិសាលភាពអនុវត្ត (Scope):")
        lbl_sc_title.setStyleSheet("font-weight: bold; font-size: 11px; color: #38bdf8;")
        scope_lay.addWidget(lbl_sc_title)

        self.combo_scope = QComboBox()
        self.combo_scope.addItem("🎯 អនុវត្តតែ Clip នេះប៉ុណ្ណោះ (Only This Clip)", "clip")
        if self.target_character:
            self.combo_scope.addItem(f"🎭 អនុវត្តលើតួអង្គ '{self.target_character}' ទាំងអស់ (All Lines of Character)", "character")
        self.combo_scope.addItem("🌐 អនុវត្តលើគ្រប់សំឡេងទាំងអស់ (Full: All Voices in Movie)", "all")
        self.combo_scope.setStyleSheet("""
            QComboBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: bold;
                min-width: 300px;
            }
            QComboBox:hover { border-color: #38bdf8; }
        """)
        self.combo_scope.currentIndexChanged.connect(self._on_scope_changed)
        scope_lay.addWidget(self.combo_scope, 1)
        main_layout.addWidget(scope_card)

        # Bottom Action Buttons
        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)

        self.lbl_status = QLabel("ជ្រើសរើស Effect ណាមួយខាងលើដើម្បីស្តាប់ ឬ អនុវត្ត")
        self.lbl_status.setStyleSheet("color: #a855f7; font-size: 11px; font-weight: bold;")
        bot_row.addWidget(self.lbl_status, 1)

        btn_cancel = QPushButton("✕ បោះបង់ (Cancel)")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1f2937;
                color: #9ca3af;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #374151; color: #ffffff; }
        """)
        btn_cancel.clicked.connect(self.reject)
        bot_row.addWidget(btn_cancel)

        self.btn_apply = QPushButton("✨ អនុវត្ត CapCut Voice Effect លើ Clip នេះ (Apply)")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                border: 1px solid #34d399;
                border-radius: 6px;
                padding: 6px 20px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
            }
        """)
        self.btn_apply.clicked.connect(self._on_apply_clicked)
        bot_row.addWidget(self.btn_apply)

        main_layout.addLayout(bot_row)

    def _on_scope_changed(self, idx: int):
        scope = self.combo_scope.currentData() or "clip"
        self.apply_scope = scope
        fx_name = get_voice_effect_label(self.selected_effect)
        if scope == "character" and self.target_character:
            self.btn_apply.setText(f"🎭 អនុវត្ត Effect លើតួអង្គ '{self.target_character}' ទាំងអស់")
            self.btn_apply.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #7c3aed);
                    color: #ffffff;
                    border: 1px solid #a78bfa;
                    border-radius: 6px;
                    padding: 6px 20px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6);
                }
            """)
        elif scope == "all":
            self.btn_apply.setText("🌐 អនុវត្ត Effect លើគ្រប់សំឡេងទាំងអស់ (Full All Lines)")
            self.btn_apply.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #06b6d4);
                    color: #ffffff;
                    border: 1px solid #38bdf8;
                    border-radius: 6px;
                    padding: 6px 20px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0891b2);
                }
            """)
        else:
            self.btn_apply.setText("✨ អនុវត្ត CapCut Voice Effect លើ Clip នេះ (Apply)")
            self.btn_apply.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                    color: #ffffff;
                    border: 1px solid #34d399;
                    border-radius: 6px;
                    padding: 6px 20px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #047857, stop:1 #059669);
                }
            """)

    def _input_style(self) -> str:
        return """
            QSpinBox, QDoubleSpinBox {
                background-color: #1e293b;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 4px;
                font-weight: bold;
            }
        """

    def _on_card_selected(self, fx_key: str):
        self.selected_effect = fx_key
        for k, card in self._cards.items():
            card.set_active(k == fx_key)
        self.lbl_active_badge.setText(f"Selected: {get_voice_effect_icon(fx_key)} {fx_key.upper()}")
        self.lbl_status.setText(f"ជ្រើស: {get_voice_effect_label(fx_key)}")
        self._on_scope_changed(self.combo_scope.currentIndex())
        # Auto preview when clicked
        self._on_preview_requested(fx_key)

    def _on_preview_requested(self, fx_key: str):
        if not self.audio_path or not os.path.exists(self.audio_path):
            self.lbl_status.setText("⚠️ រកមិនឃើញ File សំឡេងដើមសម្រាប់ស្តាប់! សូម Generate សំឡេងសិន")
            return

        self.lbl_status.setText(f"🔊 កំពុងចាក់សាកល្បង: {get_voice_effect_label(fx_key)}...")
        ok = preview_voice_effect(self.audio_path, fx_key)
        if not ok:
            self.lbl_status.setText(f"❌ មិនអាចចាក់សំឡេង Effect: {fx_key}")

    def _on_apply_clicked(self):
        stop_voice_effect_preview()
        vol = self.spin_vol.value() / 100.0
        spd = self.spin_speed.value()
        fx_key = self.selected_effect
        self.apply_scope = self.combo_scope.currentData() or "clip"

        # Apply to underlying raw dictionary
        if self.raw_dict is not None:
            self.raw_dict["voice_effect"] = fx_key
            self.raw_dict["volume"] = vol
            self.raw_dict["speed"] = spd

            # If audio path exists, transform audio file directly
            if self.audio_path and os.path.exists(self.audio_path):
                if not self.raw_dict.get("orig_path") and not self.raw_dict.get("orig_audio"):
                    if self.audio_data.get("is_track"):
                        self.raw_dict["orig_path"] = self.audio_path
                    else:
                        self.raw_dict["orig_audio"] = self.audio_path

                orig_file = self.raw_dict.get("orig_path") or self.raw_dict.get("orig_audio") or self.audio_path
                if fx_key != "none":
                    new_file = apply_voice_effect_to_file(orig_file, fx_key)
                    if self.audio_data.get("is_track"):
                        self.raw_dict["path"] = new_file
                        self.audio_data["path"] = new_file
                    else:
                        self.raw_dict["audio_file"] = new_file
                        self.raw_dict["audio_path"] = new_file
                else:
                    if self.audio_data.get("is_track"):
                        self.raw_dict["path"] = orig_file
                        self.audio_data["path"] = orig_file
                    else:
                        self.raw_dict["audio_file"] = orig_file
                        self.raw_dict["audio_path"] = orig_file

        self.audio_data["voice_effect"] = fx_key
        self.audio_data["volume"] = vol
        self.audio_data["speed"] = spd

        self.effect_applied.emit(fx_key, vol, spd)
        if self.apply_scope in ("character", "all"):
            self.batch_effect_applied.emit(fx_key, self.apply_scope, self.target_character, vol, spd)
        self.accept()

    def closeEvent(self, event):
        stop_voice_effect_preview()
        super().closeEvent(event)
