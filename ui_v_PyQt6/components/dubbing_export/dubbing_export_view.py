"""
Dubbing & Export View Component for PyQt6 / PySide6 Desktop Studio
Controls multi-track audio mixing, Khmer typography & karaoke styling,
watermarking, and master video composition export settings.
"""

import os
import json
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, 
    QComboBox, QCheckBox, QFrame, QGroupBox, QScrollArea, QFileDialog, Qt, QSplitter,
    QDialog, QInputDialog, QMessageBox, QLineEdit, QTabWidget
)
from ui_v_PyQt6.icons import (
    get_qta_icon, get_listen_icon, get_stop_icon, get_export_icon
)
from config import (
    KHMER_VOICES, SUBTITLE_COLORS, SPEECH_SPEED_PRESETS, EXPORT_RESOLUTIONS,
    EXPORT_FPS, EXPORT_FORMATS, EXPORT_CODECS, EXPORT_QUALITY, WATERMARK_POSITIONS,
    get_installed_khmer_fonts, KHMER_FONT_FAMILY, CC_ANIMATION_PRESETS,
    CC_BG_STYLES, CC_BORDER_PRESETS, CC_HIGHLIGHT_COLORS
)


class ExportDialog(QDialog):
    """
    Modal Dialog for Master Video Export Settings.
    Shown as a popup only when the user requests an export.
    Defaults to MP4 + H.265 / HEVC (CRF 26) for optimal data-saving upload!
    """
    def __init__(
        self,
        parent=None,
        on_export_srt=None,
        on_burn_video=None,
        on_export_all=None,
        on_export_dub_audio=None,
        on_export_video_no_cc=None,
        on_export_normal_project=None,
        initial_settings=None,
        **kwargs
    ):
        super().__init__(parent)
        self.setWindowTitle("🚀 Master Video Export Settings")
        self.setFixedWidth(460)
        self.setModal(True)
        self.on_export_srt = on_export_srt
        self.on_burn_video = on_burn_video
        self.on_export_all = on_export_all
        self.on_export_dub_audio = on_export_dub_audio
        self.on_export_video_no_cc = on_export_video_no_cc
        self.on_export_normal_project = on_export_normal_project
        self._initial = initial_settings or {}
        self.selected_action = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Container Card matching user's visual style
        card_exp = QGroupBox("🚀 Master Video & Audio Export Settings")
        exp_layout = QVBoxLayout(card_exp)
        exp_layout.setContentsMargins(12, 14, 12, 12)
        exp_layout.setSpacing(10)

        # 1. Export Target / Type Selection (Select Mode)
        v_target = QVBoxLayout()
        v_target.setSpacing(4)
        v_target.addWidget(QLabel("Export Mode / Target (ប្រភេទ Export):"))
        self.combo_target = QComboBox()
        self.combo_target.addItems([
            "🎬 នាំចេញគ្រប់យ៉ាងដូចពេលចាក់ Play (WYSIWYG: Cuts, Dub Audio, CC, Img Overlays)",
            "⚡ Fast Draft / Test Export (Export លឿនទម្លាក់គុណភាពសម្រាប់ Test ភ្លាមៗ)",
            "🎬 វីដេអូគម្រោង + អក្សររត់ (Normal Video + Subtitles CC - Original Audio)",
            "🎬 Master Movie + Khmer Dubbing (សំឡេងបញ្ចូលខ្មែរ - Clean No CC)",
            "🎬 Full Movie + Khmer Dubbing + Subtitles (សំឡេងខ្មែរ + អក្សររត់ Hardsub CC)",
            "🎙️ Khmer Dubbed Audio Only (.mp3 / .wav)",
            "📄 Subtitles File Only (.srt)",
            "📱 TikTok / Shorts 9:16 Vertical Video"
        ])
        v_target.addWidget(self.combo_target)
        exp_layout.addLayout(v_target)

        # 2. Format & Codec Selection (Default: MP4 + H.265 CRF 26 for 50% data saving)
        v_codec = QVBoxLayout()
        v_codec.setSpacing(4)
        v_codec.addWidget(QLabel("Video Codec (ទម្រង់វីដេអូ & Codec):"))
        self.combo_codec = QComboBox()
        self.combo_codec.addItems(EXPORT_FORMATS)
        self.combo_codec.setCurrentIndex(0)
        v_codec.addWidget(self.combo_codec)
        exp_layout.addLayout(v_codec)

        # 3. Resolution & FPS Grid
        grid = QHBoxLayout()
        grid.setSpacing(10)

        v_res = QVBoxLayout()
        v_res.setSpacing(4)
        v_res.addWidget(QLabel("Resolution (ទំហំ):"))
        self.combo_res = QComboBox()
        self.combo_res.addItems(list(EXPORT_RESOLUTIONS.keys()))
        res_val = self._initial.get("resolution", "Original (តាមវីដេអូដើម)")
        if res_val in EXPORT_RESOLUTIONS:
            self.combo_res.setCurrentText(res_val)
        v_res.addWidget(self.combo_res)
        grid.addLayout(v_res)

        v_fps = QVBoxLayout()
        v_fps.setSpacing(4)
        v_fps.addWidget(QLabel("FPS (ល្បឿនប្លង់):"))
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(list(EXPORT_FPS.keys()))
        fps_val = self._initial.get("fps", "30 FPS (Standard)")
        if fps_val in EXPORT_FPS:
            self.combo_fps.setCurrentText(fps_val)
        v_fps.addWidget(self.combo_fps)
        grid.addLayout(v_fps)

        exp_layout.addLayout(grid)

        # 4. Quality Preset (CRF)
        v_qual = QVBoxLayout()
        v_qual.setSpacing(4)
        v_qual.addWidget(QLabel("Quality Preset (គុណភាព / CRF):"))
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(list(EXPORT_QUALITY.keys()))
        self.combo_quality.setCurrentIndex(0)
        v_qual.addWidget(self.combo_quality)
        exp_layout.addLayout(v_qual)

        self.combo_target.currentTextChanged.connect(self._on_target_mode_changed)

        # 5. ONLY ONE HERO ACTION BUTTON!
        self.btn_export_now = QPushButton("🚀 EXPORT NOW")
        self.btn_export_now.setFixedHeight(40)
        self.btn_export_now.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #34d399;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                border: 1px solid #6ee7b7;
            }
            QPushButton:pressed {
                background: #047857;
            }
        """)
        self.btn_export_now.clicked.connect(self._do_unified_export)
        exp_layout.addWidget(self.btn_export_now)

        # Backward compatibility aliases
        self.btn_master = self.btn_export_now
        self.btn_exp_dub = self.btn_export_now
        self.btn_exp_srt = self.btn_export_now

        layout.addWidget(card_exp)

        # Close / Cancel footer
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = QPushButton("✕ Cancel")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def get_settings(self) -> dict:
        chosen_fmt = self.combo_codec.currentText()
        codec_info = EXPORT_CODECS.get(chosen_fmt, {"codec": "hevc", "crf": "26"})
        crf = codec_info.get("crf", "26")
        if hasattr(self, "combo_quality"):
            q_text = self.combo_quality.currentText()
            if q_text in EXPORT_QUALITY:
                crf = EXPORT_QUALITY[q_text]
        return {
            "target": self.combo_target.currentText() if hasattr(self, "combo_target") else "master",
            "resolution": self.combo_res.currentText(),
            "fps": self.combo_fps.currentText(),
            "format": chosen_fmt,
            "codec": codec_info.get("codec", "hevc"),
            "crf": crf
        }

    def _on_target_mode_changed(self, text: str):
        if "Fast Draft" in text or "Test Export" in text:
            # Auto-tune for maximum export speed: CRF 32 + 480p SD
            if hasattr(self, "combo_quality"):
                for i in range(self.combo_quality.count()):
                    if "Fast Draft" in self.combo_quality.itemText(i) or "32" in self.combo_quality.itemText(i):
                        self.combo_quality.setCurrentIndex(i)
                        break
            if hasattr(self, "combo_res"):
                for i in range(self.combo_res.count()):
                    if "480p" in self.combo_res.itemText(i):
                        self.combo_res.setCurrentIndex(i)
                        break
            if hasattr(self, "combo_codec"):
                for i in range(self.combo_codec.count()):
                    if "Fast Test" in self.combo_codec.itemText(i) or "H.264" in self.combo_codec.itemText(i):
                        self.combo_codec.setCurrentIndex(i)
                        break

    def _do_unified_export(self):
        target = self.combo_target.currentText() if hasattr(self, "combo_target") else ""
        settings = self.get_settings()
        codec = settings.get("codec", "hevc")
        crf = settings.get("crf", "26")

        if "Fast Draft" in target or "Test Export" in target or "ទម្លាក់គុណភាព" in target:
            self._do_export_normal_project(burn_cc=False)
        elif "WYSIWYG" in target or "ដូចពេលចាក់ Play" in target or "Normal Project Video" in target or "វីដេអូគម្រោងធម្មតា" in target:
            self._do_export_normal_project(burn_cc=None)
        elif "Normal Video + Subtitles" in target or "វីដេអូគម្រោង + អក្សររត់" in target:
            self._do_export_normal_project(burn_cc=True)
        elif "Clean - No CC" in target or "No CC" in target:
            self._do_export_video_no_cc()
        elif "Hardsub CC" in target or ("Subtitles" in target and "Hardsub" in target):
            self._do_burn_video()
        elif "Dubbed Audio" in target or "Audio" in target:
            self._do_export_dub()
        elif "Subtitles File Only" in target or ".srt" in target:
            self._do_export_srt()
        elif "TikTok" in target or "9:16" in target:
            self.selected_action = "tiktok_916"
            self.accept()
            parent_win = self.window()
            if hasattr(parent_win, "open_auto_reframe_dialog"):
                parent_win.open_auto_reframe_dialog()
            elif self.on_burn_video:
                self.on_burn_video(codec=codec, crf=crf)
            elif self.on_export_video_no_cc:
                self.on_export_video_no_cc(codec=codec, crf=crf)
        else:
            self._do_export_normal_project(burn_cc=False)

    def _do_export_normal_project(self, burn_cc: bool = False):
        self.selected_action = "normal_project"
        self.accept()
        settings = self.get_settings()
        codec = settings.get("codec", "hevc")
        crf = settings.get("crf", "26")
        if hasattr(self, "on_export_normal_project") and self.on_export_normal_project:
            self.on_export_normal_project(burn_cc=burn_cc, codec=codec, crf=crf)
        elif burn_cc and self.on_burn_video:
            self.on_burn_video(codec=codec, crf=crf)
        elif self.on_export_video_no_cc:
            self.on_export_video_no_cc(codec=codec, crf=crf)

    def _do_export_srt(self):
        self.selected_action = "srt"
        self.accept()
        if self.on_export_srt:
            self.on_export_srt()

    def _do_export_dub(self):
        self.selected_action = "dub_audio"
        self.accept()
        if self.on_export_dub_audio:
            self.on_export_dub_audio()

    def _do_burn_video(self):
        self.selected_action = "burn"
        self.accept()
        settings = self.get_settings()
        if self.on_burn_video:
            self.on_burn_video(codec=settings["codec"], crf=settings["crf"])

    def _do_export_video_no_cc(self):
        self.selected_action = "video_no_cc"
        self.accept()
        settings = self.get_settings()
        if self.on_export_video_no_cc:
            self.on_export_video_no_cc(codec=settings["codec"], crf=settings["crf"])
        elif self.on_export_all:
            self.on_export_all(burn_cc=False, codec=settings["codec"], crf=settings["crf"])

    def _do_export_all(self):
        self._do_export_video_no_cc()
def _make_modern_slider_qss(accent_start="#0284c7", accent_end="#38bdf8", glow="#38bdf8"):
    return f"""
        QSlider {{
            min-height: 20px;
        }}
        QSlider::groove:horizontal {{
            border: 1px solid #232b38;
            height: 5px;
            background: #141822;
            border-radius: 3px;
        }}
        QSlider::sub-page:horizontal {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent_start}, stop:1 {accent_end});
            border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 #ffffff, stop:0.6 #f1f5f9, stop:1 #cbd5e1);
            border: 2px solid {glow};
            width: 14px;
            margin-top: -5px;
            margin-bottom: -5px;
            border-radius: 7px;
        }}
        QSlider::handle:horizontal:hover {{
            background: #ffffff;
            border: 2px solid #ffffff;
        }}
    """


class DubbingExportView(QWidget):
    """
    Right Inspector Studio Panel:
    - Multi-Track Audio Mix (Original, Khmer Dub, BGM, Auto-Ducking)
    - Khmer CC Typography & Animation Style
    - Launches Master Video Export popup dialog on demand
    """
    def __init__(
        self,
        parent=None,
        on_generate_dub=None,
        on_open_voices=None,
        on_export_srt=None,
        on_burn_video=None,
        on_export_all=None,
        on_font_change=None,
        on_filter_change=None,
        on_watermark_change=None,
        on_bg_music_browse=None,
        on_audio_mix_change=None,
        on_cc_style_change=None,
        on_auto_sync_all=None,
        on_export_dub_audio=None,
        on_export_video_no_cc=None,
        on_apply_voice_sync=None,
        on_apply_character_voice=None,
        on_preview_character_voice=None,
        on_separate_vocals=None,
        on_mute_srt_intervals=None,
        on_export_normal_project=None
    ):
        super().__init__(parent)
        self.on_generate_dub = on_generate_dub
        self.on_open_voices = on_open_voices
        self.on_export_srt = on_export_srt
        self.on_burn_video = on_burn_video
        self.on_export_all = on_export_all
        self.on_export_dub_audio = on_export_dub_audio
        self.on_export_video_no_cc = on_export_video_no_cc
        self.on_export_normal_project = on_export_normal_project
        self.on_font_change = on_font_change
        self.on_filter_change = on_filter_change
        self.on_watermark_change = on_watermark_change
        self.on_bg_music_browse = on_bg_music_browse
        self.on_audio_mix_change = on_audio_mix_change
        self.on_cc_style_change = on_cc_style_change
        self.on_auto_sync_all = on_auto_sync_all
        self.on_apply_voice_sync = on_apply_voice_sync
        self.on_apply_character_voice = on_apply_character_voice
        self.on_preview_character_voice = on_preview_character_voice
        self.on_separate_vocals = on_separate_vocals
        self.on_mute_srt_intervals = on_mute_srt_intervals

        self._current_sub_idx = -1
        self._current_sub_data = None
        self._char_presets = {}
        self._character_voice_map = {}

        self.watermark_path = None
        self.bgm_path = None
        self.export_settings = {
            "resolution": "Original (តាមវីដេអូដើម)",
            "fps": "30 FPS (Standard)"
        }

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tabbed Inspector to separate Voice Cast, Audio Mix, Voice Sync, and Export
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #232b3b;
                background-color: #12151c;
                border-radius: 6px;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #171b26;
                color: #94a3b8;
                border: 1px solid #232b3b;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
                margin-right: 2px;
            }
            QTabBar::tab:hover {
                background-color: #1e2434;
                color: #f1f5f9;
            }
            QTabBar::tab:selected {
                background-color: #12151c;
                color: #38bdf8;
                border: 1px solid #232b3b;
                border-top: 2.5px solid #38bdf8;
                border-bottom: 1px solid #12151c;
                font-weight: bold;
            }
        """)

        def _wrap_tab(widget: QWidget) -> QScrollArea:
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.Shape.NoFrame)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            sc.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            sc.setStyleSheet("QScrollArea { background-color: #12151c; border: none; }")
            w = QWidget()
            w.setStyleSheet("background-color: transparent;")
            ly = QVBoxLayout(w)
            ly.setContentsMargins(6, 6, 6, 8)
            ly.setSpacing(6)
            ly.addWidget(widget)
            ly.addStretch()
            sc.setWidget(w)
            return sc

        # ---------------- 0. CHARACTER VOICE CAST & TUNING CARD ----------------
        self.card_char_cast = self._create_card("🎭 Character Voice Cast Tuning (កំណត់សំឡេងតួអង្គ)")
        cc_cast_layout = QVBoxLayout(self.card_char_cast)
        cc_cast_layout.setContentsMargins(10, 12, 10, 10)
        cc_cast_layout.setSpacing(8)

        # 1. Character Selector & Summary
        char_h_row = QHBoxLayout()
        lbl_c_title = QLabel("តួអង្គក្នុងរឿង (Character):")
        lbl_c_title.setStyleSheet("font-weight: bold; color: #f1f5f9; font-size: 11px;")
        char_h_row.addWidget(lbl_c_title)
        char_h_row.addStretch()
        self.lbl_char_count_badge = QLabel("0 Characters")
        self.lbl_char_count_badge.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #8b5cf6); color: #ffffff; border-radius: 4px; padding: 2px 7px; font-size: 9px; font-weight: bold;")
        char_h_row.addWidget(self.lbl_char_count_badge)
        cc_cast_layout.addLayout(char_h_row)

        self.combo_character = QComboBox()
        self.combo_character.addItem("All Lines (គ្រប់បន្ទាត់ទាំងអស់)")
        self.combo_character.currentIndexChanged.connect(self._on_selected_character_changed)
        self.combo_character.setStyleSheet("""
            QComboBox {
                background-color: #171b25;
                color: #f1f5f9;
                border: 1px solid #283244;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
        """)
        cc_cast_layout.addWidget(self.combo_character)

        # 2. Voice Style Presets (កូនក្មេង, តាចាស់, ភាពយន្ត, ស្រីក្រមុំ...)
        lbl_p_title = QLabel("ស្ទីលតួអង្គ (Character Role Preset):")
        lbl_p_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 500;")
        cc_cast_layout.addWidget(lbl_p_title)

        p_row = QHBoxLayout()
        self.combo_char_role = QComboBox()
        self.combo_char_role.setStyleSheet("""
            QComboBox {
                background-color: #171b25;
                color: #f1f5f9;
                border: 1px solid #283244;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
        """)
        p_row.addWidget(self.combo_char_role, 1)

        btn_save_preset = QPushButton(" Save")
        btn_save_preset.setIcon(get_qta_icon("fa5s.save", color="#38bdf8"))
        btn_save_preset.setToolTip("Save current voice tuning as a reusable Preset")
        btn_save_preset.setFixedWidth(60)
        btn_save_preset.setStyleSheet("""
            QPushButton {
                background-color: #1b2331;
                color: #38bdf8;
                border: 1px solid #2d3b52;
                border-radius: 5px;
                padding: 4px 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        btn_save_preset.clicked.connect(self._on_save_preset_clicked)
        p_row.addWidget(btn_save_preset)
        cc_cast_layout.addLayout(p_row)

        # 3. Voice Model / Persona
        lbl_v_title = QLabel("Edge-TTS Voice:")
        lbl_v_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 500;")
        cc_cast_layout.addWidget(lbl_v_title)

        self.combo_char_voice = QComboBox()
        self.combo_char_voice.addItems([
            "Edge-TTS: Piseth Neural (ប្រុស / Male)",
            "Edge-TTS: Sreymom Neural (ស្រី / Female)"
        ])
        self.combo_char_voice.currentIndexChanged.connect(self._on_char_manual_tuning_changed)
        self.combo_char_voice.setStyleSheet("""
            QComboBox {
                background-color: #171b25;
                color: #f1f5f9;
                border: 1px solid #283244;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
        """)
        cc_cast_layout.addWidget(self.combo_char_voice)

        # 4. Voice Pitch / Tone Slider (-50Hz to +50Hz)
        pitch_header = QHBoxLayout()
        lbl_pitch_title = QLabel("Voice Pitch / Tone (ថូនសំឡេង គ្រលរ / ស្រាល):")
        lbl_pitch_title.setStyleSheet("color: #cbd5e1; font-size: 10px;")
        pitch_header.addWidget(lbl_pitch_title)
        self.lbl_char_pitch_val = QLabel("+0Hz (ធម្មជាតិ)")
        self.lbl_char_pitch_val.setStyleSheet("background-color: #064e3b; color: #6ee7b7; border: 1px solid #059669; border-radius: 4px; padding: 1px 7px; font-weight: bold; font-size: 10px;")
        pitch_header.addStretch()
        pitch_header.addWidget(self.lbl_char_pitch_val)
        cc_cast_layout.addLayout(pitch_header)

        self.slider_char_pitch = QSlider(Qt.Orientation.Horizontal)
        self.slider_char_pitch.setRange(-50, 50)
        self.slider_char_pitch.setValue(0)
        self.slider_char_pitch.setStyleSheet(_make_modern_slider_qss("#059669", "#34d399", "#34d399"))
        self.slider_char_pitch.valueChanged.connect(self._on_char_pitch_changed)
        cc_cast_layout.addWidget(self.slider_char_pitch)

        # 5. Speech Rate Slider (-40% to +50%)
        rate_header = QHBoxLayout()
        lbl_rate_title = QLabel("Speech Rate (ល្បឿននិយាយ):")
        lbl_rate_title.setStyleSheet("color: #cbd5e1; font-size: 10px;")
        rate_header.addWidget(lbl_rate_title)
        self.lbl_char_rate_val = QLabel("1.00x (+0%)")
        self.lbl_char_rate_val.setStyleSheet("background-color: #0c4a6e; color: #7dd3fc; border: 1px solid #0284c7; border-radius: 4px; padding: 1px 7px; font-weight: bold; font-size: 10px;")
        rate_header.addStretch()
        rate_header.addWidget(self.lbl_char_rate_val)
        cc_cast_layout.addLayout(rate_header)

        self.slider_char_rate = QSlider(Qt.Orientation.Horizontal)
        self.slider_char_rate.setRange(-40, 50)
        self.slider_char_rate.setValue(0)
        self.slider_char_rate.setStyleSheet(_make_modern_slider_qss("#0284c7", "#38bdf8", "#38bdf8"))
        self.slider_char_rate.valueChanged.connect(self._on_char_rate_changed)
        cc_cast_layout.addWidget(self.slider_char_rate)

        # 6. CapCut Voice Effect Dropdown (Voice Changers / Robot / Kid / Echo...)
        lbl_fx_title = QLabel("CapCut Voice Effect (កែសំឡេងបែប CapCut):")
        lbl_fx_title.setStyleSheet("color: #cbd5e1; font-size: 10px;")
        cc_cast_layout.addWidget(lbl_fx_title)

        self.combo_char_effect = QComboBox()
        from services.dubbing.audio_effects import CAPCUT_VOICE_EFFECTS, get_voice_effect_icon
        for fx_k, fx_lbl, _ in CAPCUT_VOICE_EFFECTS:
            ic = get_voice_effect_icon(fx_k)
            self.combo_char_effect.addItem(f"{ic} {fx_lbl}", fx_k)
        self.combo_char_effect.currentIndexChanged.connect(self._on_char_manual_tuning_changed)
        self.combo_char_effect.setStyleSheet("""
            QComboBox {
                background-color: #171b25;
                color: #f1f5f9;
                border: 1px solid #283244;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }
            QComboBox:hover {
                border-color: #38bdf8;
            }
        """)
        cc_cast_layout.addWidget(self.combo_char_effect)

        # Initialize presets after sliders & voice dropdown are created
        self._load_character_presets()
        self.combo_char_role.currentIndexChanged.connect(self._on_char_role_changed)
        if self.combo_char_role.count() > 0:
            self._on_char_role_changed(self.combo_char_role.currentIndex())

        # 6. Action Row: Preview Test Line & Apply to ALL Lines of this Character
        btn_action_row = QHBoxLayout()
        btn_action_row.setSpacing(6)
        self.btn_preview_char = QPushButton(" ចាក់តេស្ត")
        self.btn_preview_char.setIcon(get_listen_icon(13, color="#38bdf8"))
        self.btn_preview_char.setToolTip("Test hear this character voice with current pitch and rate")
        self.btn_preview_char.setStyleSheet("""
            QPushButton {
                background-color: #161e2c;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        self.btn_preview_char.clicked.connect(self._on_preview_char_clicked)
        btn_action_row.addWidget(self.btn_preview_char)

        self.btn_apply_char = QPushButton(" ⚡ អនុវត្តគ្រប់បន្ទាត់តួនេះ")
        self.btn_apply_char.setIcon(get_qta_icon("fa5s.magic", color="#ffffff"))
        self.btn_apply_char.setToolTip("Apply this voice, pitch, and speed to ALL lines spoken by this character")
        self.btn_apply_char.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #4f46e5, stop:1 #7c3aed);
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #818cf8;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366f1, stop:1 #8b5cf6);
                border-color: #c084fc;
            }
        """)
        self.btn_apply_char.clicked.connect(self._on_apply_char_clicked)
        btn_action_row.addWidget(self.btn_apply_char, 1)

        cc_cast_layout.addLayout(btn_action_row)

        # ---------------- 1. AUDIO MIXING & DUCKING CARD ----------------
        self.card_audio = self._create_card("Multi-Track Audio Mix")
        ca_layout = QVBoxLayout(self.card_audio)
        ca_layout.setContentsMargins(10, 12, 10, 10)
        ca_layout.setSpacing(9)

        # 1.1 Original Audio Track Strip
        orig_box = QFrame()
        orig_box.setStyleSheet("background-color: #141720; border: 1px solid #232a38; border-radius: 7px;")
        orig_layout = QVBoxLayout(orig_box)
        orig_layout.setContentsMargins(8, 6, 8, 6)
        orig_layout.setSpacing(4)

        orig_top = QHBoxLayout()
        lbl_orig = QLabel("🎬 Original Audio:")
        lbl_orig.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 11px;")
        orig_top.addWidget(lbl_orig)
        orig_top.addStretch()

        self.lbl_orig_vol = QLabel("85%")
        self.lbl_orig_vol.setStyleSheet("background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 10px;")
        orig_top.addWidget(self.lbl_orig_vol)

        self.check_mute_orig = QCheckBox("Mute")
        self.check_mute_orig.setStyleSheet("""
            QCheckBox {
                color: #94a3b8;
                font-size: 10px;
                font-weight: 600;
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #3b4559;
                background-color: #161b24;
            }
            QCheckBox::indicator:hover {
                border-color: #ef4444;
            }
            QCheckBox::indicator:checked {
                background-color: #dc2626;
                border-color: #f87171;
            }
        """)
        self.check_mute_orig.stateChanged.connect(self._emit_audio_mix)
        orig_top.addWidget(self.check_mute_orig)
        orig_layout.addLayout(orig_top)

        self.slider_orig_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_orig_vol.setRange(0, 100)
        self.slider_orig_vol.setValue(85)
        self.slider_orig_vol.setStyleSheet(_make_modern_slider_qss("#0284c7", "#38bdf8", "#38bdf8"))
        self.slider_orig_vol.valueChanged.connect(lambda v: self.lbl_orig_vol.setText(f"{v}%"))
        self.slider_orig_vol.valueChanged.connect(self._emit_audio_mix)
        orig_layout.addWidget(self.slider_orig_vol)
        ca_layout.addWidget(orig_box)

        # 1.2 Khmer Dub Voice Track Strip
        dub_box = QFrame()
        dub_box.setStyleSheet("background-color: #141720; border: 1px solid #232a38; border-radius: 7px;")
        dub_layout = QVBoxLayout(dub_box)
        dub_layout.setContentsMargins(8, 6, 8, 6)
        dub_layout.setSpacing(4)

        dub_top = QHBoxLayout()
        lbl_dub = QLabel("🎙️ Khmer Dub Voice:")
        lbl_dub.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 11px;")
        dub_top.addWidget(lbl_dub)
        dub_top.addStretch()

        self.lbl_dub_vol = QLabel("100%")
        self.lbl_dub_vol.setStyleSheet("background-color: #3b1d6e; color: #c084fc; border: 1px solid #7c3aed; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 10px;")
        dub_top.addWidget(self.lbl_dub_vol)

        self.check_mute_dub = QCheckBox("Mute")
        self.check_mute_dub.setStyleSheet("""
            QCheckBox {
                color: #94a3b8;
                font-size: 10px;
                font-weight: 600;
                spacing: 4px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #3b4559;
                background-color: #161b24;
            }
            QCheckBox::indicator:hover {
                border-color: #ef4444;
            }
            QCheckBox::indicator:checked {
                background-color: #dc2626;
                border-color: #f87171;
            }
        """)
        self.check_mute_dub.stateChanged.connect(self._emit_audio_mix)
        dub_top.addWidget(self.check_mute_dub)
        dub_layout.addLayout(dub_top)

        self.slider_dub_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_dub_vol.setRange(0, 100)
        self.slider_dub_vol.setValue(100)
        self.slider_dub_vol.setStyleSheet(_make_modern_slider_qss("#7c3aed", "#a855f7", "#c084fc"))
        self.slider_dub_vol.valueChanged.connect(lambda v: self.lbl_dub_vol.setText(f"{v}%"))
        self.slider_dub_vol.valueChanged.connect(self._emit_audio_mix)
        dub_layout.addWidget(self.slider_dub_vol)
        ca_layout.addWidget(dub_box)

        # 1.3 Background Music (BGM) Track Strip
        bgm_box = QFrame()
        bgm_box.setStyleSheet("background-color: #141720; border: 1px solid #232a38; border-radius: 7px;")
        bgm_layout = QVBoxLayout(bgm_box)
        bgm_layout.setContentsMargins(8, 6, 8, 6)
        bgm_layout.setSpacing(4)

        bgm_top = QHBoxLayout()
        lbl_bgm = QLabel("🎵 BGM Music:")
        lbl_bgm.setStyleSheet("font-weight: 600; color: #e2e8f0; font-size: 11px;")
        bgm_top.addWidget(lbl_bgm)
        bgm_top.addStretch()

        self.lbl_bgm_vol = QLabel("35%")
        self.lbl_bgm_vol.setStyleSheet("background-color: #452907; color: #fbbf24; border: 1px solid #d97706; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 10px;")
        bgm_top.addWidget(self.lbl_bgm_vol)

        btn_bgm = QPushButton(" Browse...")
        btn_bgm.setIcon(get_qta_icon("fa5s.folder-open", color="#fbbf24"))
        btn_bgm.setStyleSheet("""
            QPushButton {
                background-color: #1e2430;
                color: #fbbf24;
                border: 1px solid #4a3818;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #d97706;
                color: #ffffff;
                border-color: #f59e0b;
            }
        """)
        btn_bgm.clicked.connect(self._browse_bgm)
        bgm_top.addWidget(btn_bgm)
        bgm_layout.addLayout(bgm_top)

        self.slider_bgm_vol = QSlider(Qt.Orientation.Horizontal)
        self.slider_bgm_vol.setRange(0, 100)
        self.slider_bgm_vol.setValue(35)
        self.slider_bgm_vol.setStyleSheet(_make_modern_slider_qss("#d97706", "#f59e0b", "#fbbf24"))
        self.slider_bgm_vol.valueChanged.connect(lambda v: self.lbl_bgm_vol.setText(f"{v}%"))
        self.slider_bgm_vol.valueChanged.connect(self._emit_audio_mix)
        bgm_layout.addWidget(self.slider_bgm_vol)
        ca_layout.addWidget(bgm_box)

        self.check_auto_duck = QCheckBox("Auto Ducking (បន្ថយសំឡេងដើមស្វ័យប្រវត្តិ)")
        self.check_auto_duck.setChecked(True)
        self.check_auto_duck.setToolTip("បន្ថយសំឡេងដើមស្វ័យប្រវត្តិកំឡុងពេលមានសំឡេងបកប្រែ (Auto Ducking)")
        self.check_auto_duck.setStyleSheet("""
            QCheckBox {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 500;
                spacing: 6px;
                margin-top: 2px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #3b4559;
                background-color: #141820;
            }
            QCheckBox::indicator:hover {
                border-color: #38bdf8;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)
        self.check_auto_duck.stateChanged.connect(self._emit_audio_mix)
        ca_layout.addWidget(self.check_auto_duck)

        # Smart SRT Interval Mute Button (Instant 1-2 Sec Mute strictly during SRT cues)
        self.btn_mute_srt = QPushButton(" 🔇 Mute សំឡេងដើមតាម SRT (1-Sec Fast)")
        self.btn_mute_srt.setIcon(get_qta_icon("fa5s.volume-mute", color="#f87171"))
        self.btn_mute_srt.setToolTip(
            "លុប/Mute សំឡេងដើមតែត្រង់ចន្លោះម៉ោងណាដែលមាន Subtitle SRT (ឧ. 1:05 - 1:40)\n"
            "ដោយរក្សាសំឡេងភ្លេង BGM និង Effects នៅកន្លែងផ្សេងទៀត 100%! ល្បឿនលឿនត្រឹមតែ ១-២ វិនាទី!"
        )
        self.btn_mute_srt.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1114, stop:0.5 #2d141a, stop:1 #1e1114);
                color: #fca5a5;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                border: 1px solid #991b1b;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #991b1b, stop:1 #dc2626);
                color: #ffffff;
                border-color: #ef4444;
            }
            QPushButton:pressed {
                background: #7f1d1d;
            }
        """)
        self.btn_mute_srt.clicked.connect(self._on_mute_srt_clicked)
        ca_layout.addWidget(self.btn_mute_srt)

        self.lbl_vocal_status = QLabel("ℹ️ សំឡេងដើមវីដេអូ (Original Track)")
        self.lbl_vocal_status.setStyleSheet("color: #64748b; font-size: 10px; font-style: italic; padding-left: 2px;")
        ca_layout.addWidget(self.lbl_vocal_status)

        btn_sync_speeds = QPushButton(" ⚡ Auto-Sync Speech Rates")
        btn_sync_speeds.setIcon(get_qta_icon("fa5s.sync-alt", color="#38bdf8"))
        btn_sync_speeds.setToolTip("Auto-calculate and sync speech rate (+10%, +25%, etc.) to fit dialogue duration")
        btn_sync_speeds.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2230, stop:1 #212c3f);
                color: #38bdf8;
                font-weight: 600;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 11px;
                border: 1px solid #0284c7;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        btn_sync_speeds.clicked.connect(self._on_sync_all_clicked)
        ca_layout.addWidget(btn_sync_speeds)

        # ---------------- 2. VOICE SYNC PROPERTIES CARD ----------------
        self.card_voice_sync = self._create_card("Voice Sync Properties")
        vs_layout = QVBoxLayout(self.card_voice_sync)
        vs_layout.setContentsMargins(10, 12, 10, 10)
        vs_layout.setSpacing(8)

        # Header Badge
        h_row = QHBoxLayout()
        lbl_vs_title = QLabel("Voice Sync Engine")
        lbl_vs_title.setStyleSheet("font-weight: bold; color: #f1f5f9; font-size: 11px;")
        h_row.addWidget(lbl_vs_title)
        h_row.addStretch()
        lbl_badge = QLabel("⚡ AI Auto-Sync")
        lbl_badge.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0ea5e9); color: #ffffff; border-radius: 4px; padding: 2px 7px; font-size: 9px; font-weight: bold;")
        h_row.addWidget(lbl_badge)
        vs_layout.addLayout(h_row)

        # Auto Fit to SRT Checkbox
        self.check_auto_fit = QCheckBox("Auto Fit to SRT (តម្រឹមល្បឿនសមនឹង SRT ស្វ័យប្រវត្តិ)")
        self.check_auto_fit.setChecked(True)
        self.check_auto_fit.setToolTip("Automatically adjust voice speed so it fits within the subtitle duration")
        self.check_auto_fit.setStyleSheet("""
            QCheckBox {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 500;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border-radius: 3px;
                border: 1px solid #3b4559;
                background-color: #141820;
            }
            QCheckBox::indicator:hover {
                border-color: #38bdf8;
            }
            QCheckBox::indicator:checked {
                background-color: #0284c7;
                border-color: #38bdf8;
            }
        """)
        vs_layout.addWidget(self.check_auto_fit)

        # Voice Speed Slider
        speed_row = QHBoxLayout()
        lbl_v_speed = QLabel("Voice Speed:")
        lbl_v_speed.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 500;")
        speed_row.addWidget(lbl_v_speed)
        self.lbl_speed_val = QLabel("1.00x")
        self.lbl_speed_val.setStyleSheet("background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 10px; min-width: 42px; text-align: center;")
        speed_row.addStretch()
        speed_row.addWidget(self.lbl_speed_val)
        vs_layout.addLayout(speed_row)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(50, 200)  # 0.50x to 2.00x
        self.slider_speed.setValue(100)
        self.slider_speed.setStyleSheet(_make_modern_slider_qss("#0891b2", "#22d3ee", "#22d3ee"))
        self.slider_speed.valueChanged.connect(self._on_speed_slider_changed)
        vs_layout.addWidget(self.slider_speed)

        # Audio Offset Slider
        offset_row = QHBoxLayout()
        lbl_v_offset = QLabel("Audio Offset:")
        lbl_v_offset.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: 500;")
        offset_row.addWidget(lbl_v_offset)
        self.lbl_offset_val = QLabel("0 ms")
        self.lbl_offset_val.setStyleSheet("background-color: #26214d; color: #a5b4fc; border: 1px solid #6366f1; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 10px; min-width: 50px; text-align: center;")
        offset_row.addStretch()
        offset_row.addWidget(self.lbl_offset_val)
        vs_layout.addLayout(offset_row)

        self.slider_offset = QSlider(Qt.Orientation.Horizontal)
        self.slider_offset.setRange(-500, 500)
        self.slider_offset.setValue(0)
        self.slider_offset.setStyleSheet(_make_modern_slider_qss("#6366f1", "#818cf8", "#818cf8"))
        self.slider_offset.valueChanged.connect(self._on_offset_slider_changed)
        vs_layout.addWidget(self.slider_offset)

        # Duration Comparison Container
        dur_frame = QFrame()
        dur_frame.setStyleSheet("background-color: #131722; border: 1px solid #242c3d; border-radius: 8px;")
        dur_layout = QHBoxLayout(dur_frame)
        dur_layout.setContentsMargins(10, 8, 10, 8)
        dur_layout.setSpacing(12)

        # Left Column: SRT Duration
        v_srt = QVBoxLayout()
        v_srt.setSpacing(2)
        lbl_s_title = QLabel("⏱️ SRT Duration")
        lbl_s_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 500;")
        v_srt.addWidget(lbl_s_title)
        self.lbl_srt_dur = QLabel("3.00s")
        self.lbl_srt_dur.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8; font-family: Consolas, monospace;")
        v_srt.addWidget(self.lbl_srt_dur)
        dur_layout.addLayout(v_srt)

        # Vertical Divider
        div_line = QFrame()
        div_line.setFrameShape(QFrame.Shape.VLine)
        div_line.setStyleSheet("color: #242c3d; max-width: 1px;")
        dur_layout.addWidget(div_line)

        # Right Column: TTS Duration
        v_tts = QVBoxLayout()
        v_tts.setSpacing(2)
        lbl_t_title = QLabel("🎙️ Estimated / Actual TTS")
        lbl_t_title.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: 500;")
        v_tts.addWidget(lbl_t_title)
        self.lbl_tts_dur = QLabel("4.00s")
        self.lbl_tts_dur.setStyleSheet("font-size: 15px; font-weight: bold; color: #fbbf24; font-family: Consolas, monospace;")
        v_tts.addWidget(self.lbl_tts_dur)
        dur_layout.addLayout(v_tts)

        vs_layout.addWidget(dur_frame)

        # Ratio Formula & Advice
        self.lbl_ratio_formula = QLabel("Speed Ratio = TTS Duration / SRT Duration ≈ 1.33x")
        self.lbl_ratio_formula.setStyleSheet("background-color: #141822; color: #94a3b8; border: 1px solid #222938; border-radius: 4px; padding: 4px 8px; font-size: 10px; font-family: Consolas, monospace;")
        vs_layout.addWidget(self.lbl_ratio_formula)

        self.lbl_sync_advice = QLabel("💡 ត្រូវបង្កើនល្បឿនប្រហែល 1.33 ដង ដើម្បីឱ្យសមនឹង SRT")
        self.lbl_sync_advice.setWordWrap(True)
        self.lbl_sync_advice.setStyleSheet("color: #38bdf8; font-size: 10px;")
        vs_layout.addWidget(self.lbl_sync_advice)

        # Auto Fit Button
        self.btn_auto_fit = QPushButton(" 🔄 Auto Fit (តម្រឹមសំឡេងស្វ័យប្រវត្តិ)")
        self.btn_auto_fit.setIcon(get_qta_icon("fa5s.magic", color="#ffffff"))
        self.btn_auto_fit.setToolTip("Auto-fit voice duration to SRT timing using formula: Speed Ratio = TTS / SRT")
        self.btn_auto_fit.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0ea5e9);
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
                border-color: #7dd3fc;
            }
        """)
        self.btn_auto_fit.clicked.connect(self._on_auto_fit_clicked)
        vs_layout.addWidget(self.btn_auto_fit)

        # ---------------- 3. MASTER MOVIE & AUDIO EXPORT CARD ----------------
        self.card_export = self._create_card("🚀 Master Movie & Audio Export")
        exp_layout = QVBoxLayout(self.card_export)
        exp_layout.setContentsMargins(10, 12, 10, 12)
        exp_layout.setSpacing(8)

        # 1. Export Target / Type Selection (Select Mode)
        exp_layout.addWidget(QLabel("Export Mode / Target (ប្រភេទ Export):"))
        self.combo_panel_target = QComboBox()
        self.combo_panel_target.addItems([
            "🎬 Export វីដេអូគម្រោងធម្មតា (Normal Project Video - Edits & Original Audio)",
            "⚡ Fast Draft / Test Export (Export លឿនទម្លាក់គុណភាពសម្រាប់ Test ភ្លាមៗ)",
            "🎬 វីដេអូគម្រោង + អក្សររត់ (Normal Video + Subtitles CC - Original Audio)",
            "🎬 Master Movie + Khmer Dubbing (សំឡេងបញ្ចូលខ្មែរ - Clean No CC)",
            "🎬 Full Movie + Khmer Dubbing + Subtitles (សំឡេងខ្មែរ + អក្សររត់ Hardsub CC)",
            "🎙️ Khmer Dubbed Audio Only (.mp3 / .wav)",
            "📄 Subtitles File Only (.srt)",
            "📱 TikTok / Shorts 9:16 Vertical Video"
        ])
        exp_layout.addWidget(self.combo_panel_target)

        # 2. Format & Codec selector
        exp_layout.addWidget(QLabel("Video Format & Codec:"))
        self.combo_panel_codec = QComboBox()
        self.combo_panel_codec.addItems(EXPORT_FORMATS)
        self.combo_panel_codec.setCurrentIndex(0)
        exp_layout.addWidget(self.combo_panel_codec)

        # 3. Resolution & Quality Grid (Selects)
        h_res_qual = QHBoxLayout()
        h_res_qual.setSpacing(8)

        v_res = QVBoxLayout()
        v_res.setSpacing(2)
        v_res.addWidget(QLabel("Resolution:"))
        self.combo_panel_res = QComboBox()
        self.combo_panel_res.addItems(list(EXPORT_RESOLUTIONS.keys()))
        res_val = self.export_settings.get("resolution", "Original (តាមវីដេអូដើម)")
        if res_val in EXPORT_RESOLUTIONS:
            self.combo_panel_res.setCurrentText(res_val)
        v_res.addWidget(self.combo_panel_res)
        h_res_qual.addLayout(v_res)

        v_qual = QVBoxLayout()
        v_qual.setSpacing(2)
        v_qual.addWidget(QLabel("Quality:"))
        self.combo_panel_quality = QComboBox()
        self.combo_panel_quality.addItems(list(EXPORT_QUALITY.keys()))
        self.combo_panel_quality.setCurrentIndex(0)
        v_qual.addWidget(self.combo_panel_quality)
        h_res_qual.addLayout(v_qual)

        exp_layout.addLayout(h_res_qual)

        self.combo_panel_target.currentTextChanged.connect(self._on_panel_target_changed)

        # 4. ONLY ONE HERO ACTION BUTTON!
        self.btn_export_video = QPushButton("🚀 EXPORT NOW")
        self.btn_export_video.setIcon(get_qta_icon("fa5s.rocket", color="#ffffff"))
        self.btn_export_video.setToolTip("Export according to the selected mode and settings above")
        self.btn_export_video.setFixedHeight(38)
        self.btn_export_video.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #34d399;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                border: 1px solid #6ee7b7;
            }
            QPushButton:pressed {
                background: #047857;
            }
        """)
        self.btn_export_video.clicked.connect(self._on_panel_export_clicked)
        exp_layout.addWidget(self.btn_export_video)

        # Full backward compatibility aliases
        self.btn_export = self.btn_export_video
        self.btn_master = self.btn_export_video
        self.btn_export_all = self.btn_export_video
        self.btn_export_dub = self.btn_export_video
        self.btn_export_srt = self.btn_export_video

        # Add 4 clean tabs to eliminate cramming
        self.tab_widget.addTab(_wrap_tab(self.card_char_cast), "🎭 Voice Cast")
        self.tab_widget.addTab(_wrap_tab(self.card_audio), "🎚️ Audio Mix")
        self.tab_widget.addTab(_wrap_tab(self.card_voice_sync), "⚡ Voice Sync")
        self.tab_widget.addTab(_wrap_tab(self.card_export), "🚀 Export")

        main_layout.addWidget(self.tab_widget)

    def _create_card(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        box.setStyleSheet("""
            QGroupBox {
                background-color: #161a24;
                border: 1px solid #242c3d;
                border-radius: 8px;
                margin-top: 22px;
                padding: 10px 8px 8px 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                top: 0px;
                padding: 2px 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a2232, stop:1 #222d42);
                border: 1px solid #334155;
                border-radius: 4px;
                color: #38bdf8;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        return box

    def toggle_audio_mix_card(self) -> bool:
        """Switches to the Multi-Track Audio Mix tab"""
        if hasattr(self, "tab_widget"):
            self.tab_widget.setCurrentIndex(1)
            if self.isHidden():
                self.setVisible(True)
            return True
        return False

    def is_audio_mix_card_visible(self) -> bool:
        return getattr(self, "tab_widget", None) is not None and not self.isHidden() and self.tab_widget.currentIndex() == 1

    def _on_panel_target_changed(self, text: str):
        if "Fast Draft" in text or "Test Export" in text:
            if hasattr(self, "combo_panel_quality"):
                for i in range(self.combo_panel_quality.count()):
                    if "Fast Draft" in self.combo_panel_quality.itemText(i) or "32" in self.combo_panel_quality.itemText(i):
                        self.combo_panel_quality.setCurrentIndex(i)
                        break
            if hasattr(self, "combo_panel_res"):
                for i in range(self.combo_panel_res.count()):
                    if "480p" in self.combo_panel_res.itemText(i):
                        self.combo_panel_res.setCurrentIndex(i)
                        break
            if hasattr(self, "combo_panel_codec"):
                for i in range(self.combo_panel_codec.count()):
                    if "Fast Test" in self.combo_panel_codec.itemText(i) or "H.264" in self.combo_panel_codec.itemText(i):
                        self.combo_panel_codec.setCurrentIndex(i)
                        break

    def _on_panel_export_clicked(self):
        target = self.combo_panel_target.currentText() if hasattr(self, "combo_panel_target") else ""
        chosen_fmt = self.combo_panel_codec.currentText() if hasattr(self, "combo_panel_codec") else "MP4 (H.265 / HEVC - CRF 26)"
        codec_info = EXPORT_CODECS.get(chosen_fmt, {"codec": "hevc", "crf": "26"})
        
        crf = codec_info.get("crf", "26")
        if hasattr(self, "combo_panel_quality"):
            q_text = self.combo_panel_quality.currentText()
            if q_text in EXPORT_QUALITY:
                crf = EXPORT_QUALITY[q_text]
        codec = codec_info.get("codec", "hevc")

        if hasattr(self, "combo_panel_res"):
            self.export_settings["resolution"] = self.combo_panel_res.currentText()
        self.export_settings["format"] = chosen_fmt
        self.export_settings["codec"] = codec
        self.export_settings["crf"] = crf

        if "Fast Draft" in target or "Test Export" in target or "ទម្លាក់គុណភាព" in target:
            if hasattr(self, "on_export_normal_project") and self.on_export_normal_project:
                self.on_export_normal_project(burn_cc=False, codec=codec, crf=crf)
            elif self.on_export_video_no_cc:
                self.on_export_video_no_cc(codec=codec, crf=crf)
            elif self.on_burn_video:
                self.on_burn_video(codec=codec, crf=crf)
        elif "Normal Project Video" in target or "វីដេអូគម្រោងធម្មតា" in target:
            if hasattr(self, "on_export_normal_project") and self.on_export_normal_project:
                self.on_export_normal_project(burn_cc=False, codec=codec, crf=crf)
            elif self.on_burn_video:
                self.on_burn_video(codec=codec, crf=crf)
            elif self.on_export_video_no_cc:
                self.on_export_video_no_cc(codec=codec, crf=crf)
        elif "Normal Video + Subtitles" in target or "វីដេអូគម្រោង + អក្សររត់" in target:
            if hasattr(self, "on_export_normal_project") and self.on_export_normal_project:
                self.on_export_normal_project(burn_cc=True, codec=codec, crf=crf)
            elif self.on_burn_video:
                self.on_burn_video(codec=codec, crf=crf)
            elif self.on_export_all:
                self.on_export_all(burn_cc=True, codec=codec, crf=crf)
        elif "Clean - No CC" in target or "No CC" in target:
            if self.on_export_video_no_cc:
                self.on_export_video_no_cc(codec=codec, crf=crf)
            elif self.on_export_all:
                self.on_export_all(burn_cc=False, codec=codec, crf=crf)
        elif "Hardsub CC" in target or ("Subtitles" in target and "Hardsub" in target):
            if self.on_burn_video:
                self.on_burn_video(codec=codec, crf=crf)
            elif self.on_export_all:
                self.on_export_all(burn_cc=True, codec=codec, crf=crf)
        elif "Dubbed Audio" in target or "Audio" in target:
            if self.on_export_dub_audio:
                self.on_export_dub_audio()
        elif "Subtitles File Only" in target or ".srt" in target:
            self._on_export_srt_clicked()
        elif "TikTok" in target or "9:16" in target:
            win = self.window()
            if hasattr(win, "open_auto_reframe_dialog"):
                win.open_auto_reframe_dialog()
            elif self.on_burn_video:
                self.on_burn_video(codec=codec, crf=crf)
            elif self.on_export_video_no_cc:
                self.on_export_video_no_cc(codec=codec, crf=crf)
        else:
            if hasattr(self, "on_export_normal_project") and self.on_export_normal_project:
                self.on_export_normal_project(burn_cc=False, codec=codec, crf=crf)
            elif self.on_export_video_no_cc:
                self.on_export_video_no_cc(codec=codec, crf=crf)
            elif self.on_export_all:
                self.on_export_all(burn_cc=False, codec=codec, crf=crf)

    def _on_panel_export_video_clicked(self):
        chosen_fmt = self.combo_panel_codec.currentText() if hasattr(self, "combo_panel_codec") else "MP4 (H.265 / HEVC - CRF 26)"
        codec_info = EXPORT_CODECS.get(chosen_fmt, {"codec": "hevc", "crf": "26"})
        if self.on_export_video_no_cc:
            self.on_export_video_no_cc(codec=codec_info.get("codec", "hevc"), crf=codec_info.get("crf", "26"))
        elif self.on_export_all:
            self.on_export_all(burn_cc=False, codec=codec_info.get("codec", "hevc"), crf=codec_info.get("crf", "26"))

    def _on_panel_export_dub_clicked(self):
        if self.on_export_dub_audio:
            self.on_export_dub_audio()

    def toggle_export_card(self) -> bool:
        """Toggles Master Movie & Audio Export card visibility inside Inspector"""
        if hasattr(self, "card_export"):
            new_vis = self.card_export.isHidden()
            self.card_export.setVisible(new_vis)
            if new_vis and self.isHidden():
                self.setVisible(True)
            return not self.card_export.isHidden()
        return False

    def toggle_cc_style_card(self) -> bool:
        return self.toggle_export_card()

    def is_export_card_visible(self) -> bool:
        return getattr(self, "card_export", None) is not None and not self.card_export.isHidden() and not self.isHidden()

    def is_cc_style_card_visible(self) -> bool:
        return self.is_export_card_visible()

    def show_export_dialog(self):
        """Shows the Master Video Export Settings popup dialog"""
        dlg = ExportDialog(
            self,
            on_export_srt=self._on_export_srt_clicked,
            on_burn_video=self._on_burn_video_clicked,
            on_export_all=self._on_export_all_clicked,
            on_export_dub_audio=self.on_export_dub_audio,
            on_export_video_no_cc=self._on_export_video_no_cc_clicked,
            on_export_normal_project=self.on_export_normal_project,
            initial_settings=self.export_settings
        )
        if dlg.exec():
            self.export_settings = dlg.get_settings()
        return dlg.selected_action

    def _on_export_video_no_cc_clicked(self, *args, codec="hevc", crf="26", **kwargs):
        real_codec = "hevc"
        real_crf = "26"
        if args and isinstance(args[0], str):
            real_codec = args[0]
        elif isinstance(codec, str) and not isinstance(codec, bool):
            real_codec = codec

        if len(args) > 1 and isinstance(args[1], str):
            real_crf = args[1]
        elif isinstance(crf, str) and not isinstance(crf, bool):
            real_crf = crf

        if self.on_export_video_no_cc:
            self.on_export_video_no_cc(codec=real_codec, crf=real_crf)

    def _emit_audio_mix(self):
        if self.on_audio_mix_change:
            settings = {
                "orig_vol": self.slider_orig_vol.value() / 100.0,
                "mute_orig": self.check_mute_orig.isChecked(),
                "dub_vol": self.slider_dub_vol.value() / 100.0,
                "mute_dub": self.check_mute_dub.isChecked(),
                "bgm_vol": self.slider_bgm_vol.value() / 100.0,
                "auto_duck": self.check_auto_duck.isChecked()
            }
            self.on_audio_mix_change(settings)

    def _emit_font_change(self):
        if self.on_font_change and hasattr(self, 'combo_font'):
            self.on_font_change(self.combo_font.currentText())

    def _emit_cc_style(self):
        if self.on_cc_style_change and hasattr(self, 'combo_anim'):
            style = {
                "animation": self.combo_anim.currentText(),
                "bg_style": self.combo_bg.currentText(),
                "highlight_color": self.combo_color.currentText()
            }
            self.on_cc_style_change(style)

    def _browse_bgm(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Background Music", "", "Audio Files (*.mp3 *.wav *.aac *.m4a)")
        if f:
            self.bgm_path = f
            if self.on_bg_music_browse:
                self.on_bg_music_browse(f)

    def _browse_watermark(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Watermark / Logo", "", "Images (*.png *.jpg *.jpeg *.webp)")
        if f:
            self.watermark_path = f
            if hasattr(self, 'lbl_wm_file'):
                self.lbl_wm_file.setText(os.path.basename(f))
            self._emit_watermark()

    def _emit_watermark(self):
        if self.on_watermark_change:
            pos = self.combo_wm_pos.currentText() if hasattr(self, 'combo_wm_pos') else "Top-Right (លើ ស្ដាំ)"
            self.on_watermark_change({
                "path": self.watermark_path,
                "pos": pos
            })

    def _on_export_srt_clicked(self):
        if self.on_export_srt:
            self.on_export_srt()

    def _on_burn_video_clicked(self, *args, codec="hevc", crf="26", **kwargs):
        real_codec = "hevc"
        real_crf = "26"
        if args and isinstance(args[0], str):
            real_codec = args[0]
        elif isinstance(codec, str) and not isinstance(codec, bool):
            real_codec = codec

        if len(args) > 1 and isinstance(args[1], str):
            real_crf = args[1]
        elif isinstance(crf, str) and not isinstance(crf, bool):
            real_crf = crf

        if self.on_burn_video:
            self.on_burn_video(codec=real_codec, crf=real_crf)

    def _on_export_all_clicked(self, *args, burn_cc=True, codec="hevc", crf="26", **kwargs):
        real_burn_cc = True
        real_codec = "hevc"
        real_crf = "26"
        if isinstance(burn_cc, bool):
            real_burn_cc = burn_cc
        if args and isinstance(args[0], str):
            real_codec = args[0]
        elif isinstance(codec, str) and not isinstance(codec, bool):
            real_codec = codec

        if len(args) > 1 and isinstance(args[1], str):
            real_crf = args[1]
        elif isinstance(crf, str) and not isinstance(crf, bool):
            real_crf = crf

        if self.on_export_all:
            self.on_export_all(burn_cc=real_burn_cc, codec=real_codec, crf=real_crf)

    def _on_sync_all_clicked(self):
        if self.on_auto_sync_all:
            self.on_auto_sync_all()

    def _on_mute_srt_clicked(self):
        if self.on_mute_srt_intervals:
            self.on_mute_srt_intervals()

    def _on_speed_slider_changed(self, val: int):
        speed_x = val / 100.0
        self.lbl_speed_val.setText(f"{speed_x:.2f}x")
        if self._current_sub_data and self.on_apply_voice_sync:
            self.on_apply_voice_sync(self._current_sub_idx, speed_x, self.slider_offset.value())

    def _on_offset_slider_changed(self, val: int):
        self.lbl_offset_val.setText(f"{val:+d} ms")
        if self._current_sub_data and self.on_apply_voice_sync:
            speed_x = self.slider_speed.value() / 100.0
            self.on_apply_voice_sync(self._current_sub_idx, speed_x, val)

    def update_selected_subtitle(self, sub: dict, idx: int = -1):
        """Updates the Voice Sync Properties panel dynamically based on the selected subtitle."""
        self._current_sub_idx = idx
        self._current_sub_data = sub
        if not sub:
            self.lbl_srt_dur.setText("0.00s")
            self.lbl_tts_dur.setText("0.00s")
            self.lbl_ratio_formula.setText("Speed Ratio = TTS Duration / SRT Duration")
            self.lbl_sync_advice.setText("ជ្រើសរើសបន្ទាត់ Subtitle ដើម្បីតម្រឹមសំឡេង")
            return

        from services.dubbing.timing_ducking import get_audio_duration
        srt_dur = max(0.0, float(sub.get("end", 0.0)) - float(sub.get("start", 0.0)))
        self.lbl_srt_dur.setText(f"{srt_dur:.2f}s")

        audio_file = sub.get("audio_file") or sub.get("audio_path")
        tts_dur = 0.0
        if audio_file and os.path.exists(audio_file):
            tts_dur = get_audio_duration(audio_file)
        elif sub.get("audio_dur"):
            try:
                tts_dur = float(sub["audio_dur"])
            except Exception:
                pass
        else:
            km_text = sub.get("khmer_text") or sub.get("translated") or ""
            if km_text:
                char_count = len(km_text.replace(" ", "").replace("\n", ""))
                tts_dur = max(0.8, char_count / 10.5)

        self.lbl_tts_dur.setText(f"{tts_dur:.2f}s")
        ratio = (tts_dur / srt_dur) if srt_dur > 0 else 1.0

        # Update slider without feedback loop
        self.slider_speed.blockSignals(True)
        self.slider_speed.setValue(int(max(0.5, min(2.0, ratio)) * 100))
        self.lbl_speed_val.setText(f"{ratio:.2f}x")
        self.slider_speed.blockSignals(False)

        self.lbl_ratio_formula.setText(f"Speed Ratio = {tts_dur:.2f}s / {srt_dur:.2f}s ≈ {ratio:.2f}x")

        if ratio <= 1.05:
            self.lbl_sync_advice.setText(f"✅ សំឡេងត្រូវគ្នានឹងពេលវេលា SRT រួចរាល់ ({tts_dur:.2f}s <= {srt_dur:.2f}s)")
            self.lbl_sync_advice.setStyleSheet("color: #34d399; font-size: 10px;")
        elif ratio <= 1.35:
            self.lbl_sync_advice.setText(f"⚡ ត្រូវបង្កើនល្បឿនប្រហែល {ratio:.2f} ដង ដើម្បីឱ្យសមនឹង SRT")
            self.lbl_sync_advice.setStyleSheet("color: #38bdf8; font-size: 10px;")
        else:
            self.lbl_sync_advice.setText(f"⚠️ Ratio {ratio:.2f}x លឿនពេក! គួរបង្រួមអត្ថបទ ឬពង្រីក SRT ជំនួសការបង្ខំល្បឿន")
            self.lbl_sync_advice.setStyleSheet("color: #f59e0b; font-size: 10px; font-weight: bold;")

    def _on_auto_fit_clicked(self):
        """Auto-adjusts voice duration using formula: Speed Ratio = TTS / SRT."""
        if not self._current_sub_data or self._current_sub_idx < 0:
            if self.on_auto_sync_all:
                self.on_auto_sync_all()
            return

        sub = self._current_sub_data
        srt_dur = max(0.2, float(sub.get("end", 0.0)) - float(sub.get("start", 0.0)))
        audio_file = sub.get("audio_file") or sub.get("audio_path")
        if audio_file and os.path.exists(audio_file):
            from services.dubbing.timing_ducking import get_audio_duration, fit_audio_to_duration
            tts_dur = get_audio_duration(audio_file)
            if tts_dur > srt_dur * 1.04:
                ratio = tts_dur / srt_dur
                fit_audio_to_duration(audio_file, srt_dur, max_ratio=1.40)
                sub["audio_dur"] = get_audio_duration(audio_file)
                pct = int((ratio - 1.0) * 100)
                sub["rate"] = f"+{pct}%"
                self.update_selected_subtitle(sub, self._current_sub_idx)
                if self.on_apply_voice_sync:
                    self.on_apply_voice_sync(self._current_sub_idx, ratio, self.slider_offset.value())
        else:
            km_text = sub.get("khmer_text") or sub.get("translated") or ""
            char_count = len(km_text.replace(" ", "").replace("\n", ""))
            tts_dur = max(0.8, char_count / 10.5)
            ratio = tts_dur / srt_dur
            pct = max(0, min(35, int((ratio - 1.0) * 100)))
            sub["rate"] = f"+{pct}%"
            self.update_selected_subtitle(sub, self._current_sub_idx)
            if self.on_apply_voice_sync:
                self.on_apply_voice_sync(self._current_sub_idx, ratio, self.slider_offset.value())

    def toggle_voice_sync_card(self) -> bool:
        """Switches to the Voice Sync Properties tab"""
        if hasattr(self, "tab_widget"):
            self.tab_widget.setCurrentIndex(2)
            if self.isHidden():
                self.setVisible(True)
            return True
        return False

    def is_voice_sync_card_visible(self) -> bool:
        return getattr(self, "tab_widget", None) is not None and not self.isHidden() and self.tab_widget.currentIndex() == 2

    def get_export_settings(self) -> dict:
        return getattr(self, "export_settings", {
            "resolution": "Original (តាមវីដេអូដើម)",
            "fps": "30 FPS (Standard)"
        })

    # ---------------- CHARACTER VOICE CAST & TUNING METHODS ----------------
    def _get_preset_file_path(self) -> str:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        p_path = os.path.join(base_dir, "character_voice_presets.json")
        if os.path.exists(p_path):
            return p_path
        return os.path.abspath("character_voice_presets.json")

    def _load_character_presets(self):
        """Loads presets from character_voice_presets.json and populates combo_char_role."""
        p_path = self._get_preset_file_path()
        if os.path.exists(p_path):
            try:
                with open(p_path, "r", encoding="utf-8") as f:
                    self._char_presets = json.load(f)
            except Exception as e:
                print(f"Error loading presets: {e}")
                self._char_presets = {}

        if not self._char_presets:
            self._char_presets = {
                "👦 កូនក្មេង (Cute Child / Youth)": {"voice_name": "km-KH-PisethNeural", "pitch": "+35Hz", "rate": "+15%", "voice_effect": "kid"},
                "👨 តួប្រុសកំលោះ (Natural Male Hero)": {"voice_name": "km-KH-PisethNeural", "pitch": "+0Hz", "rate": "+0%", "voice_effect": "none"},
                "👩 តួស្រីក្រមុំ (Natural Sweet Female)": {"voice_name": "km-KH-SreymomNeural", "pitch": "+0Hz", "rate": "+0%", "voice_effect": "none"},
                "👵 តាយាយ / ព្រឹទ្ធាចារ្យ (Old Wise Master)": {"voice_name": "km-KH-PisethNeural", "pitch": "-30Hz", "rate": "-15%", "voice_effect": "deep_male"},
                "🎬 អ្នកអធិប្បាយរឿង (Deep Cinema Narrator)": {"voice_name": "km-KH-PisethNeural", "pitch": "-15Hz", "rate": "+5%", "voice_effect": "cinema_bass"},
                "👧 ក្មេងស្រីស្រទន់ (Soft Anime Girl)": {"voice_name": "km-KH-SreymomNeural", "pitch": "+25Hz", "rate": "+10%", "voice_effect": "kid"},
                "⚡ TikTok / Shorts រហ័ស (Turbo Fast Recap)": {"voice_name": "km-KH-PisethNeural", "pitch": "+5Hz", "rate": "+30%", "voice_effect": "chipmunk"},
                "🤖 Robot / មេកានិច (Futuristic Cyborg)": {"voice_name": "km-KH-PisethNeural", "pitch": "+0Hz", "rate": "+0%", "voice_effect": "robot"},
                "🏛️ សាលអេកូ / ព្រះពុទ្ធដីកា (Echo Hall Reverb)": {"voice_name": "km-KH-PisethNeural", "pitch": "-5Hz", "rate": "-5%", "voice_effect": "echo_hall"},
                "⚙️ កំណត់តាមចិត្ត (Custom Manual Tuning)": {"voice_name": "km-KH-PisethNeural", "pitch": "+0Hz", "rate": "+0%", "voice_effect": "none"}
            }

        if hasattr(self, "combo_char_role"):
            self.combo_char_role.blockSignals(True)
            self.combo_char_role.clear()
            for name in self._char_presets.keys():
                self.combo_char_role.addItem(name)
            self.combo_char_role.blockSignals(False)

    def _on_char_role_changed(self, idx: int):
        role_name = self.combo_char_role.currentText()
        if role_name not in self._char_presets:
            return
        preset = self._char_presets[role_name]
        v_name = preset.get("voice_name", "km-KH-PisethNeural")
        p_str = preset.get("pitch", "+0Hz").replace("Hz", "").replace("+", "").strip()
        r_str = preset.get("rate", "+0%").replace("%", "").replace("+", "").strip()
        fx_name = preset.get("voice_effect", "none")

        try:
            pitch_val = int(p_str)
        except Exception:
            pitch_val = 0

        try:
            rate_val = int(r_str)
        except Exception:
            rate_val = 0

        # Update Voice Combo
        self.combo_char_voice.blockSignals(True)
        if "Sreymom" in v_name:
            for i in range(self.combo_char_voice.count()):
                if "Sreymom" in self.combo_char_voice.itemText(i):
                    self.combo_char_voice.setCurrentIndex(i)
                    break
        elif "Piseth" in v_name:
            for i in range(self.combo_char_voice.count()):
                if "Piseth" in self.combo_char_voice.itemText(i):
                    self.combo_char_voice.setCurrentIndex(i)
                    break
        self.combo_char_voice.blockSignals(False)

        # Update CapCut Voice Effect
        if hasattr(self, "combo_char_effect"):
            self.combo_char_effect.blockSignals(True)
            f_idx = self.combo_char_effect.findData(fx_name)
            if f_idx >= 0:
                self.combo_char_effect.setCurrentIndex(f_idx)
            else:
                self.combo_char_effect.setCurrentIndex(0)
            self.combo_char_effect.blockSignals(False)

        # Update Sliders
        self.slider_char_pitch.blockSignals(True)
        self.slider_char_pitch.setValue(pitch_val)
        self.slider_char_pitch.blockSignals(False)
        self._update_char_pitch_display(pitch_val)

        self.slider_char_rate.blockSignals(True)
        self.slider_char_rate.setValue(rate_val)
        self.slider_char_rate.blockSignals(False)
        self._update_char_rate_display(rate_val)

    def _update_char_pitch_display(self, val: int):
        if val > 0:
            self.lbl_char_pitch_val.setText(f"+{val}Hz (ស្រាល/ខ្ពស់)")
            self.lbl_char_pitch_val.setStyleSheet("color: #ec4899; font-weight: bold; font-size: 10px;")
        elif val < 0:
            self.lbl_char_pitch_val.setText(f"{val}Hz (គ្រលរ/ធ្ងន់)")
            self.lbl_char_pitch_val.setStyleSheet("color: #818cf8; font-weight: bold; font-size: 10px;")
        else:
            self.lbl_char_pitch_val.setText("+0Hz (ធម្មជាតិ)")
            self.lbl_char_pitch_val.setStyleSheet("color: #34d399; font-weight: bold; font-size: 10px;")

    def _update_char_rate_display(self, val: int):
        speed_x = 1.0 + (val / 100.0)
        sign = "+" if val >= 0 else ""
        self.lbl_char_rate_val.setText(f"{speed_x:.2f}x ({sign}{val}%)")
        if val > 0:
            self.lbl_char_rate_val.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 10px;")
        elif val < 0:
            self.lbl_char_rate_val.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 10px;")
        else:
            self.lbl_char_rate_val.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 10px;")

    def _on_char_pitch_changed(self, val: int):
        self._update_char_pitch_display(val)
        # Select custom manual tuning without triggering loop
        self._set_preset_to_custom()

    def _on_char_rate_changed(self, val: int):
        self._update_char_rate_display(val)
        self._set_preset_to_custom()

    def _on_char_manual_tuning_changed(self, idx: int):
        self._set_preset_to_custom()

    def _set_preset_to_custom(self):
        self.combo_char_role.blockSignals(True)
        custom_idx = self.combo_char_role.findText("⚙️ កំណត់តាមចិត្ត (Custom Manual Tuning)")
        if custom_idx >= 0:
            self.combo_char_role.setCurrentIndex(custom_idx)
        self.combo_char_role.blockSignals(False)

    def _on_save_preset_clicked(self):
        text, ok = QInputDialog.getText(
            self,
            "រក្សាទុក Preset ស្ទីលសំឡេង",
            "បញ្ចូលឈ្មោះស្ទីលតួអង្គ (Preset Name):",
            QLineEdit.EchoMode.Normal,
            "🎭 "
        )
        if ok and text.strip():
            preset_name = text.strip()
            settings = self.get_current_character_settings()
            self._char_presets[preset_name] = {
                "voice_name": settings.get("raw_voice", "km-KH-PisethNeural"),
                "pitch": settings.get("pitch", "+0Hz"),
                "rate": settings.get("rate", "+0%"),
                "voice_effect": settings.get("voice_effect", "none"),
                "volume": "+0%",
                "desc": "Custom user-saved preset"
            }
            # Save to JSON
            p_path = self._get_preset_file_path()
            try:
                with open(p_path, "w", encoding="utf-8") as f:
                    json.dump(self._char_presets, f, ensure_ascii=False, indent=4)
                QMessageBox.information(self, "ជោគជ័យ", f"បានរក្សាទុកស្ទីល '{preset_name}' រួចរាល់!")
            except Exception as e:
                QMessageBox.warning(self, "បរាជ័យ", f"មិនអាចរក្សាទុក Preset បានទេ: {e}")

            # Reload combo and select new
            self.combo_char_role.blockSignals(True)
            self.combo_char_role.clear()
            for name in self._char_presets.keys():
                self.combo_char_role.addItem(name)
            idx = self.combo_char_role.findText(preset_name)
            if idx >= 0:
                self.combo_char_role.setCurrentIndex(idx)
            self.combo_char_role.blockSignals(False)

    def _on_selected_character_changed(self, idx: int):
        char_key = self.combo_character.currentData()
        if not char_key or char_key == "ALL":
            return
        if char_key in self._character_voice_map:
            cfg = self._character_voice_map[char_key]
            # Restore saved tuning
            p_val = cfg.get("pitch_val", 0)
            r_val = cfg.get("rate_val", 0)
            v_name = cfg.get("voice", "")
            fx_val = cfg.get("voice_effect", "none")

            self.slider_char_pitch.blockSignals(True)
            self.slider_char_pitch.setValue(p_val)
            self.slider_char_pitch.blockSignals(False)
            self._update_char_pitch_display(p_val)

            self.slider_char_rate.blockSignals(True)
            self.slider_char_rate.setValue(r_val)
            self.slider_char_rate.blockSignals(False)
            self._update_char_rate_display(r_val)

            if v_name:
                self.combo_char_voice.blockSignals(True)
                for i in range(self.combo_char_voice.count()):
                    if v_name in self.combo_char_voice.itemText(i):
                        self.combo_char_voice.setCurrentIndex(i)
                        break
                self.combo_char_voice.blockSignals(False)

            if hasattr(self, "combo_char_effect") and fx_val:
                self.combo_char_effect.blockSignals(True)
                f_idx = self.combo_char_effect.findData(fx_val)
                if f_idx >= 0:
                    self.combo_char_effect.setCurrentIndex(f_idx)
                else:
                    self.combo_char_effect.setCurrentIndex(0)
                self.combo_char_effect.blockSignals(False)

    def _on_preview_char_clicked(self):
        settings = self.get_current_character_settings()
        if self.on_preview_character_voice:
            self.on_preview_character_voice(settings)

    def _on_apply_char_clicked(self):
        char_key = self.combo_character.currentData() or "ALL"
        settings = self.get_current_character_settings()
        self._character_voice_map[char_key] = settings
        if self.on_apply_character_voice:
            self.on_apply_character_voice(char_key, settings)

    def get_current_character_settings(self) -> dict:
        v_text = self.combo_char_voice.currentText()
        if "Sreymom" in v_text:
            raw_v = "km-KH-SreymomNeural"
            gender = "female"
        else:
            raw_v = "km-KH-PisethNeural"
            gender = "male"

        p_val = self.slider_char_pitch.value()
        pitch_str = f"+{p_val}Hz" if p_val >= 0 else f"{p_val}Hz"

        r_val = self.slider_char_rate.value()
        rate_str = f"+{r_val}%" if r_val >= 0 else f"{r_val}%"

        fx_val = self.combo_char_effect.currentData() if hasattr(self, "combo_char_effect") else "none"

        return {
            "voice": v_text,
            "raw_voice": raw_v,
            "gender": gender,
            "pitch_val": p_val,
            "pitch": pitch_str,
            "rate_val": r_val,
            "rate": rate_str,
            "voice_effect": fx_val or "none",
            "volume": "+0%"
        }

    def update_character_list(self, subtitles: list):
        """Analyzes all subtitles to extract distinct characters/speakers and updates combo_character."""
        if not hasattr(self, "combo_character"):
            return

        char_counts = {}
        for sub in (subtitles or []):
            spk = (
                sub.get("speaker")
                or sub.get("actor")
                or sub.get("character")
            )
            if not spk:
                g = sub.get("gender")
                if g == "female":
                    spk = "តួស្រី (Female)"
                elif g == "male":
                    spk = "តួប្រុស (Male)"
                else:
                    spk = "តួទូទៅ (Dialogue)"
            char_counts[spk] = char_counts.get(spk, 0) + 1

        self.combo_character.blockSignals(True)
        self.combo_character.clear()

        total_lines = len(subtitles or [])
        self.combo_character.addItem(f"All Lines (គ្រប់បន្ទាត់ទាំងអស់) - [{total_lines} បន្ទាត់]", "ALL")

        for char_name, count in sorted(char_counts.items(), key=lambda x: -x[1]):
            icon_badge = "👧" if "ស្រី" in char_name or "Female" in char_name else ("👦" if "ក្មេង" in char_name else "🎭")
            self.combo_character.addItem(f"{icon_badge} {char_name} - [{count} បន្ទាត់]", char_name)

        self.combo_character.blockSignals(False)

        count_unique = len(char_counts)
        self.lbl_char_count_badge.setText(f"{count_unique} តួអង្គ")

