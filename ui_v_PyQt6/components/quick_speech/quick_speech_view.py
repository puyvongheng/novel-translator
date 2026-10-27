"""
Quick Speech View Component for PyQt6 / PySide6 Desktop Studio
Generates fast Khmer AI Voice audio from custom text, previews sound in real time,
and exports high-quality MP3/WAV audio files.
"""

import os
import threading
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, 
    QComboBox, QSlider, QGroupBox, QFileDialog, QMessageBox, QPlainTextEdit, 
    QLineEdit, QCheckBox, QFrame, Qt
)
from utils import play_audio_file


class QuickSpeechView(QWidget):
    """
    Fast Khmer Text-To-Speech & MP3 Studio:
    - Multiline Khmer dialogue input
    - Multi-engine AI Voice Selection
    - Voice Pitch & Speed rate sliders
    - One-click Audio Preview and MP3 Export
    - Integrated diagnostic logs
    """
    def __init__(self, parent=None, log_callback=None):
        super().__init__(parent)
        self.log_callback = log_callback
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Title
        lbl_head = QLabel(" Quick Speech ")
        lbl_head.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        main_layout.addWidget(lbl_head)

        # Content Split Layout
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Left Card: Text Input
        group_text = QGroupBox("📝 Khmer Dialogue Script & Input")
        l_layout = QVBoxLayout(group_text)
        l_layout.setContentsMargins(10, 12, 10, 10)
        l_layout.setSpacing(8)

        self.txt_input = QTextEdit()
        self.txt_input.setPlaceholderText("សូមបញ្ចូលអត្ថបទដែលអ្នកចង់បង្កើតជាសំឡេង AI នៅទីនេះ...")
        self.txt_input.setStyleSheet("font-size: 13px; line-height: 1.5;")
        l_layout.addWidget(self.txt_input, 1)

        btn_row = QHBoxLayout()
        btn_sample = QPushButton("📋 Insert Sample Text")
        btn_sample.clicked.connect(self._insert_sample)
        btn_row.addWidget(btn_sample)

        btn_clear = QPushButton("🧹 Clear Text")
        btn_clear.clicked.connect(lambda: self.txt_input.clear())
        btn_row.addWidget(btn_clear)
        l_layout.addLayout(btn_row)

        content_layout.addWidget(group_text, 3)

        # Right Card: Voice Settings & Controls
        group_voice = QGroupBox("🎙️ AI Voice Settings & MP3 Export")
        r_layout = QVBoxLayout(group_voice)
        r_layout.setContentsMargins(10, 12, 10, 10)
        r_layout.setSpacing(8)

        r_layout.addWidget(QLabel("AI Voice Persona:"))
        self.combo_voice = QComboBox()
        self.combo_voice.addItems([
            "Edge-TTS: Piseth Neural (ប្រុស - ធម្មជាតិឥតគិតថ្លៃ)",
            "Edge-TTS: Sreymom Neural (ស្រី - ធម្មជាតិឥតគិតថ្លៃ)"
        ])
        self.combo_voice.currentTextChanged.connect(self._on_voice_changed)
        r_layout.addWidget(self.combo_voice)

        # Optional Gemini API Key (Only shown when Gemini Voice is selected)
        self.lbl_api_key = QLabel("🔑 Gemini API Key (សម្រាប់ Gemini Voice):")
        self.edit_api_key = QLineEdit()
        self.edit_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_api_key.setPlaceholderText("បញ្ចូល Gemini API Key នៅទីនេះ (ស្រេចចិត្ត)...")
        from config import GEMINI_API_KEY
        if GEMINI_API_KEY:
            self.edit_api_key.setText(GEMINI_API_KEY)
        r_layout.addWidget(self.lbl_api_key)
        r_layout.addWidget(self.edit_api_key)

        # ── Edge-TTS Tuning Controls (Style Presets, Pitch, Volume, Studio Enhancer) ──
        self.edge_controls_widget = QWidget()
        edge_layout = QVBoxLayout(self.edge_controls_widget)
        edge_layout.setContentsMargins(0, 0, 0, 0)
        edge_layout.setSpacing(6)

        # 1. Quick Voice Style Presets
        edge_layout.addWidget(QLabel("🎭 Voice Style Presets (ស្ទីលនិយាយរហ័ស):"))
        self.combo_edge_style = QComboBox()
        self.combo_edge_style.addItems([
            "🎬 ភាពយន្តស្តង់ដារ (Standard Movie Dub)",
            "⚡ និទានរឿងរហ័ស (Fast Storyteller)",
            "🎙️ គ្រលរធ្ងន់បែបភាពយន្ត (Deep Cinema Baritone)",
            "👧 ស្រាលស្រទន់ (Soft & Gentle)",
            "🚀 TikTok / Shorts សម្រាយរឿងលឿន (Turbo Recap)",
            "⚙️ កំណត់តាមចិត្ត (Custom Manual Tuning)"
        ])
        self.combo_edge_style.currentIndexChanged.connect(self._on_edge_style_preset_changed)
        edge_layout.addWidget(self.combo_edge_style)

        # 2. Voice Pitch / Tone Slider (-30Hz to +30Hz)
        edge_layout.addWidget(QLabel("🎵 Voice Pitch / Tone (ថូនសំឡេង គ្រលរ / ស្រាល):"))
        self.slider_pitch = QSlider(Qt.Orientation.Horizontal)
        self.slider_pitch.setRange(-30, 30)
        self.slider_pitch.setValue(0)
        self.lbl_pitch_val = QLabel("+0Hz (ធម្មជាតិ)")
        self.lbl_pitch_val.setStyleSheet("color: #34d399; font-weight: bold;")
        self.slider_pitch.valueChanged.connect(self._on_pitch_slider_changed)
        pitch_row = QHBoxLayout()
        pitch_row.addWidget(self.slider_pitch)
        pitch_row.addWidget(self.lbl_pitch_val)
        edge_layout.addLayout(pitch_row)

        # 3. Volume Boost Slider (-50% to +50%)
        edge_layout.addWidget(QLabel("🔊 Volume Boost (កម្រិតសំឡេង):"))
        self.slider_volume = QSlider(Qt.Orientation.Horizontal)
        self.slider_volume.setRange(-50, 50)
        self.slider_volume.setValue(0)
        self.lbl_volume_val = QLabel("+0% (ធម្មតា)")
        self.lbl_volume_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.slider_volume.valueChanged.connect(self._on_volume_slider_changed)
        vol_row = QHBoxLayout()
        vol_row.addWidget(self.slider_volume)
        vol_row.addWidget(self.lbl_volume_val)
        edge_layout.addLayout(vol_row)

        # 4. Studio Audio Filter Checkbox
        self.chk_enhance = QCheckBox("✨ Studio Voice Filter (កាត់ Noise, បន្ថែម Warmth EQ & Broadcast Compand)")
        self.chk_enhance.setChecked(True)
        self.chk_enhance.setStyleSheet("color: #38bdf8; font-weight: bold;")
        edge_layout.addWidget(self.chk_enhance)

        # 5. Reset Tuning Button
        btn_reset_edge = QPushButton("🔄 កំណត់ដើមវិញ (Reset Tuning)")
        btn_reset_edge.setFixedHeight(24)
        btn_reset_edge.setStyleSheet("font-size: 11px; padding: 2px 8px; color: #94a3b8;")
        btn_reset_edge.clicked.connect(self._reset_edge_tuning)
        edge_layout.addWidget(btn_reset_edge)

        r_layout.addWidget(self.edge_controls_widget)

        # Universal Speech Rate Slider (Used across all models)
        r_layout.addWidget(QLabel("⚡ Speech Rate (ល្បឿននិយាយ លឿន/យឺត):"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(60, 180)
        self.slider_speed.setValue(100)
        self.lbl_speed_val = QLabel("1.00x (ធម្មតា)")
        self.lbl_speed_val.setStyleSheet("color: #34d399; font-weight: bold;")
        self.slider_speed.valueChanged.connect(self._on_speed_slider_changed)
        sp_row = QHBoxLayout()
        sp_row.addWidget(self.slider_speed)
        sp_row.addWidget(self.lbl_speed_val)
        r_layout.addLayout(sp_row)

        r_layout.addStretch()

        # Action Buttons
        self.btn_preview = QPushButton("🔊 Preview Voice (ស្ដាប់សំឡេង)")
        self.btn_preview.setFixedHeight(38)
        self.btn_preview.setObjectName("btn_primary")
        self.btn_preview.clicked.connect(self._preview_voice)
        r_layout.addWidget(self.btn_preview)

        self.btn_export_mp3 = QPushButton("💾 Export to Audio File (.mp3 / .wav)")
        self.btn_export_mp3.setFixedHeight(38)
        self.btn_export_mp3.setObjectName("btn_success")
        self.btn_export_mp3.clicked.connect(self._export_mp3)
        r_layout.addWidget(self.btn_export_mp3)

        content_layout.addWidget(group_voice, 2)
        main_layout.addLayout(content_layout, 1)

        # Bottom Diagnostic Logs Group
        group_logs = QGroupBox("📜 Live Speech Generation Logs")
        log_layout = QVBoxLayout(group_logs)
        log_layout.setContentsMargins(8, 12, 8, 8)
        log_layout.setSpacing(4)

        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setFixedHeight(90)
        self.txt_logs.setStyleSheet("font-family: Consolas; font-size: 11px; background-color: #171b22; color: #a5f3fc; border: 1px solid #282e3a; border-radius: 4px;")
        log_layout.addWidget(self.txt_logs)
        main_layout.addWidget(group_logs)

        # Initial visibility setup
        self._updating_sliders = False
        self._on_voice_changed()

    def _on_voice_changed(self, voice_text: str = None):
        """Shows/hides settings based on selected engine: Hides Gemini API key when Edge-TTS is chosen"""
        voice = voice_text or (self.combo_voice.currentText() if hasattr(self, "combo_voice") else "")
        v_low = voice.lower()
        is_gemini = "gemini" in v_low
        is_edge = "edge" in v_low or "neural" in v_low or ("google" not in v_low and "gemini" not in v_low)

        if hasattr(self, "lbl_api_key"):
            self.lbl_api_key.setVisible(is_gemini)
        if hasattr(self, "edit_api_key"):
            self.edit_api_key.setVisible(is_gemini)
        if hasattr(self, "edge_controls_widget"):
            self.edge_controls_widget.setVisible(is_edge)

    def _on_edge_style_preset_changed(self, idx: int):
        if self._updating_sliders:
            return
        preset = self.combo_edge_style.currentText()
        if "Custom" in preset or "កំណត់តាមចិត្ត" in preset:
            return
        self._updating_sliders = True
        try:
            if "Standard" in preset:
                self.slider_speed.setValue(100)
                self.slider_pitch.setValue(0)
                self.slider_volume.setValue(0)
                self.chk_enhance.setChecked(True)
            elif "Fast Storyteller" in preset:
                self.slider_speed.setValue(115)
                self.slider_pitch.setValue(5)
                self.slider_volume.setValue(0)
                self.chk_enhance.setChecked(True)
            elif "Deep Cinema" in preset:
                self.slider_speed.setValue(95)
                self.slider_pitch.setValue(-15)
                self.slider_volume.setValue(10)
                self.chk_enhance.setChecked(True)
            elif "Soft & Gentle" in preset:
                self.slider_speed.setValue(100)
                self.slider_pitch.setValue(15)
                self.slider_volume.setValue(0)
                self.chk_enhance.setChecked(True)
            elif "Turbo Recap" in preset:
                self.slider_speed.setValue(125)
                self.slider_pitch.setValue(0)
                self.slider_volume.setValue(10)
                self.chk_enhance.setChecked(True)
            self._update_slider_labels()
        finally:
            self._updating_sliders = False

    def _on_speed_slider_changed(self, v: int):
        self._update_speed_label(v)
        if not self._updating_sliders and hasattr(self, "combo_edge_style"):
            self.combo_edge_style.blockSignals(True)
            self.combo_edge_style.setCurrentIndex(5)  # Custom Manual Tuning
            self.combo_edge_style.blockSignals(False)

    def _on_pitch_slider_changed(self, v: int):
        self._update_pitch_label(v)
        if not self._updating_sliders and hasattr(self, "combo_edge_style"):
            self.combo_edge_style.blockSignals(True)
            self.combo_edge_style.setCurrentIndex(5)  # Custom Manual Tuning
            self.combo_edge_style.blockSignals(False)

    def _on_volume_slider_changed(self, v: int):
        self._update_volume_label(v)
        if not self._updating_sliders and hasattr(self, "combo_edge_style"):
            self.combo_edge_style.blockSignals(True)
            self.combo_edge_style.setCurrentIndex(5)  # Custom Manual Tuning
            self.combo_edge_style.blockSignals(False)

    def _update_speed_label(self, v: int):
        speed_factor = v / 100.0
        pct = v - 100
        desc = "ធម្មតា" if pct == 0 else ("លឿន" if pct > 0 else "យឺត")
        self.lbl_speed_val.setText(f"{speed_factor:.2f}x ({desc} {pct:+d}%)")
        if pct > 0:
            self.lbl_speed_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        elif pct < 0:
            self.lbl_speed_val.setStyleSheet("color: #f59e0b; font-weight: bold;")
        else:
            self.lbl_speed_val.setStyleSheet("color: #34d399; font-weight: bold;")

    def _update_pitch_label(self, v: int):
        if v < -5:
            desc = "គ្រលរ / Deep Bass"
            color = "#f59e0b"
        elif v > 5:
            desc = "ស្រាល / Bright Tone"
            color = "#f472b6"
        else:
            desc = "ធម្មជាតិ / Natural"
            color = "#34d399"
        self.lbl_pitch_val.setText(f"{v:+d}Hz ({desc})")
        self.lbl_pitch_val.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _update_volume_label(self, v: int):
        desc = "ធម្មតា" if v == 0 else ("ឮខ្លាំង" if v > 0 else "ស្រាល")
        self.lbl_volume_val.setText(f"{v:+d}% ({desc})")
        self.lbl_volume_val.setStyleSheet("color: #38bdf8; font-weight: bold;")

    def _update_slider_labels(self):
        self._update_speed_label(self.slider_speed.value())
        self._update_pitch_label(self.slider_pitch.value())
        self._update_volume_label(self.slider_volume.value())

    def _reset_edge_tuning(self):
        self._updating_sliders = True
        try:
            self.combo_edge_style.setCurrentIndex(0)
            self.slider_speed.setValue(100)
            self.slider_pitch.setValue(0)
            self.slider_volume.setValue(0)
            self.chk_enhance.setChecked(True)
            self._update_slider_labels()
        finally:
            self._updating_sliders = False

    def log(self, text: str):
        self.txt_logs.appendPlainText(text)
        if self.log_callback:
            self.log_callback(text)

    def _insert_sample(self):
        sample = "សួស្ដីអ្នកទាំងអស់គ្នា! នេះគឺជាការបង្កើតសំឡេងអានដោយស្វ័យប្រវត្តិតាមរយៈបច្ចេកវិទ្យាបញ្ញាសិប្បនិម្មិត AI Khmer Movie Studio។"
        self.txt_input.setPlainText(sample)

    def _preview_voice(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "No Text", "សូមបញ្ចូលអត្ថបទជាមុនសិន!")
            return
        voice = self.combo_voice.currentText()
        speed_val = self.slider_speed.value()
        rate_str = f"{speed_val - 100:+d}%"
        pitch_val = self.slider_pitch.value() if hasattr(self, "slider_pitch") else 0
        pitch_str = f"{pitch_val:+d}Hz"
        vol_val = self.slider_volume.value() if hasattr(self, "slider_volume") else 0
        vol_str = f"{vol_val:+d}%"
        enhance = bool(self.chk_enhance.isChecked()) if hasattr(self, "chk_enhance") else True
        api_key = self.edit_api_key.text().strip() or os.environ.get("GEMINI_API_KEY", "")
        self.log(f"🎙️ [QuickSpeech] កំពុងបង្កើតសំឡេង Preview... | Voice: {voice} | Rate: {rate_str} | Pitch: {pitch_str} | Vol: {vol_str} | Enhancer: {'On' if enhance else 'Off'}")

        def worker():
            try:
                from services.speech import generate_voice_file
                out_tmp = os.path.abspath("preview_speech.mp3")
                if "gemini" in voice.lower() and not api_key:
                    self.log("ℹ️ [Gemini] មិនទាន់មាន Gemini API Key ទេ (សូមបញ្ចូល API Key ឬប្រើ Edge-TTS ធម្មជាតិឥតគិតថ្លៃ) -> កំពុងប្រើ Edge-TTS ស្វ័យប្រវត្តិ...")
                ok = generate_voice_file(
                    text,
                    out_tmp,
                    voice_name=voice,
                    rate=rate_str,
                    pitch=pitch_str,
                    volume=vol_str,
                    enhance=enhance,
                    api_key=api_key
                )
                if ok and os.path.exists(out_tmp):
                    self.log(f"✅ [QuickSpeech] បង្កើតសំឡេងជោគជ័យ! កំពុងចាក់ស្ដាប់...")
                    play_audio_file(out_tmp)
                else:
                    self.log("❌ [QuickSpeech] មិនអាចបង្កើតសំឡេងបានទេ!")
            except Exception as e:
                self.log(f"❌ [QuickSpeech] បរាជ័យ: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _export_mp3(self):
        text = self.txt_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "No Text", "សូមបញ្ចូលអត្ថបទជាមុនសិន!")
            return
        f, _ = QFileDialog.getSaveFileName(
            self,
            "Save Audio File",
            "output_speech.mp3",
            "MP3 Audio (*.mp3);;WAV Audio (*.wav)"
        )
        if not f:
            return

        voice = self.combo_voice.currentText()
        speed_val = self.slider_speed.value()
        rate_str = f"{speed_val - 100:+d}%"
        pitch_val = self.slider_pitch.value() if hasattr(self, "slider_pitch") else 0
        pitch_str = f"{pitch_val:+d}Hz"
        vol_val = self.slider_volume.value() if hasattr(self, "slider_volume") else 0
        vol_str = f"{vol_val:+d}%"
        enhance = bool(self.chk_enhance.isChecked()) if hasattr(self, "chk_enhance") else True
        api_key = self.edit_api_key.text().strip() or os.environ.get("GEMINI_API_KEY", "")
        self.log(f"💾 [QuickSpeech] កំពុង Export ទៅកាន់: {os.path.basename(f)} | Voice: {voice} | Rate: {rate_str} | Pitch: {pitch_str}...")

        def worker():
            try:
                from services.speech import generate_voice_file
                if "gemini" in voice.lower() and not api_key:
                    self.log("ℹ️ [Gemini] មិនទាន់មាន Gemini API Key ទេ -> កំពុងប្រើ Edge-TTS ស្វ័យប្រវត្តិ...")
                ok = generate_voice_file(
                    text,
                    f,
                    voice_name=voice,
                    rate=rate_str,
                    pitch=pitch_str,
                    volume=vol_str,
                    enhance=enhance,
                    api_key=api_key
                )
                if ok and os.path.exists(f):
                    self.log(f"🎉 [QuickSpeech] រួចរាល់! បានរក្សាទុកនៅ: {os.path.basename(f)}")
                else:
                    self.log("❌ [QuickSpeech] បរាជ័យក្នុងការ Export!")
            except Exception as e:
                self.log(f"❌ [QuickSpeech] បរាជ័យក្នុងការ Export: {e}")

        threading.Thread(target=worker, daemon=True).start()

