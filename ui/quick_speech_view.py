import os
import json
import threading
import time
import math
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import pygame

from config import (
    KHMER_VOICES,
    VOICE_PROFILES,
    VOICE_EFFECTS,
    AUDIO_EXPORT_QUALITIES,
    KHMER_SAMPLE_TEXTS,
    get_installed_khmer_fonts,
    KHMER_FONT_FAMILY
)
from services.dubbing import DubbingEngine

class QuickSpeechView(ctk.CTkFrame):
    """
    Studio-Grade AI Text-to-Speech & Voice Cloning Studio:
    - Multi-Category Voice Selector (Khmer AI, Cloned Voices, Multilingual)
    - Voice Clone Studio (Upload reference audio, analyze acoustic profile, calibrate pitch/formant, save clone)
    - Voice Tuning Controls (Speed Rate, Pitch tuning, Volume boost)
    - Studio Audio FX Presets (Cinema Bass, Radio Warmth, Reverb/Hall, Telephone, Robot, Soft Whisper)
    - Background Music (BGM) Mixing with volume ducking
    - 100% Khmer Unicode Font Support with dynamic font switcher and live text metrics
    """
    def __init__(self, parent, log_callback=None):
        super().__init__(parent, fg_color="#0e1014", corner_radius=0)
        self.log_callback = log_callback
        self.dubbing_engine = DubbingEngine(log_callback=log_callback)
        self.is_speaking = False

    def log(self, text: str):
        """Dispatches log message to log_callback if registered, or stdout"""
        if self.log_callback:
            try:
                self.log_callback(text)
            except Exception:
                pass
        else:
            print(f"[AI Voice Studio] {text}")

    def _get_ai_engine_summary(self, params: dict) -> str:
        """Constructs clear description of the AI engine and voice configuration used"""
        engine = params.get("engine", "")
        if "Gemini" in engine:
            g_cfg = params.get("gemini_config", {})
            m = g_cfg.get("model", "gemini-2.0-flash")
            v = g_cfg.get("voice_name", "Puck")
            emo = g_cfg.get("emotion") or "ធម្មជាតិ (Natural)"
            return f"🤖 Google Gemini AI (Model: {m} | Voice: {v} | Emotion: {emo})"
        elif "VoxCPM" in engine:
            preset = getattr(self, "voxcpm_preset", "Piseth Hero")
            v_id = params.get("voice_id", "km-KH-PisethNeural")
            return f"🎙️ VoxCPM Voice Clone (Preset: {preset} | Base: {v_id})"
        elif "Edge TTS" in engine:
            voice = getattr(self, "edge_voice", params.get("voice_id"))
            rate = params.get("rate", "+0%")
            pitch = params.get("pitch", "+0Hz")
            return f"🇰🇭 Edge TTS Khmer Neural (Voice: {voice} | Rate: {rate} | Pitch: {pitch})"
        elif "F5-TTS" in engine:
            ref = os.path.basename(self.f5_ref_path) if getattr(self, "f5_ref_path", None) else "Zero-Shot Base"
            return f"⚡ F5-TTS / Coqui Clone (Reference: {ref})"
        elif "ElevenLabs" in engine:
            el_v = self.combo_eleven_voice.get() if hasattr(self, "combo_eleven_voice") else "Adam"
            return f"💎 ElevenLabs AI Studio (Voice: {el_v})"
        else:
            return f"AI Engine: {engine} (Voice: {params.get('voice_id')})"

        # Font & UI state
        self.installed_fonts = get_installed_khmer_fonts()
        self.active_font_family = self.installed_fonts[0] if self.installed_fonts else KHMER_FONT_FAMILY
        self.active_font_size = 13

        # Media & Clone state
        self.ref_sample_path = None
        self.bgm_path = None
        self.current_preview_audio = None
        self.active_category = "Khmer"

        # AI Voice / TTS Studio Engines & State
        self.ENGINE_VOXCPM = "🎙️ VoxCPM (Voice Clone & Neural Model)"
        self.ENGINE_GEMINI = "🤖 Gemini AI Voice (Google DeepMind)"
        self.ENGINE_EDGETTS = "🇰🇭 Edge TTS (Khmer Neural Studio)"
        self.ENGINE_F5TTS = "⚡ F5-TTS / Coqui (Zero-Shot Clone)"
        self.ENGINE_ELEVENLABS = "💎 ElevenLabs AI (Hyper-Realistic Studio)"

        self.active_engine = self.ENGINE_VOXCPM

        # VoxCPM State
        self.voxcpm_ref_path = None
        self.voxcpm_preset = "👑 Piseth - Movie Hero (បុរសភាពយន្ត)"
        self.voxcpm_pitch = 1.0
        self.voxcpm_bass = 0.0
        self.voxcpm_treble = 0.0
        self.voxcpm_formant = "Natural"

        # Gemini AI Voice State
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.gemini_model = "gemini-2.0-flash"
        self.gemini_emotion = "Storyteller (និទានរឿង)"
        self.gemini_prompt = "សំឡេងនិទានរឿងបែបខ្មែរបុរាណ ស្រទន់ រលូន និងទាក់ទាញ"
        self.gemini_lang = "Khmer (ភាសាខ្មែរ)"
        self.gemini_temp = 0.7
        self.gemini_pace = 1.0

        # Edge TTS State
        self.edge_voice = "Piseth (Male / ប្រុស)"
        self.edge_rate = 0
        self.edge_pitch = 0
        self.edge_volume = 100
        self.edge_profile = "Natural (ធម្មជាតិ)"
        self.edge_fx = "None (ធម្មជាតិ / Natural)"

        # F5-TTS / Coqui State
        self.f5_ref_path = None
        self.f5_lang = "Khmer (Cambodia)"
        self.f5_expressiveness = 1.0
        self.f5_device = "Auto-Detect GPU (CUDA)"

        # ElevenLabs State
        self.eleven_api_key = os.environ.get("ELEVEN_API_KEY", "")
        self.eleven_model = "Eleven Multilingual v2"
        self.eleven_voice = "Adam (Deep Cinema Male)"
        self.eleven_stability = 0.50
        self.eleven_similarity = 0.75
        self.eleven_exaggeration = 0.20

        self._build_ui()
        self._update_text_metrics()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ------------------ 1. TOP HEADER BANNER ------------------
        header = ctk.CTkFrame(self, fg_color="#141720", corner_radius=0, height=52)
        header.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        header.grid_columnconfigure(1, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", padx=12, pady=6)

        title_lbl = ctk.CTkLabel(
            title_box,
            text="🎙️ STUDIO AI TEXT-TO-SPEECH & VOICE CLONING",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10b981"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            title_box,
            text="បំប្លែងអត្ថបទទៅជាសំឡេងខ្មែរ AI ធម្មជាតិ | កែសម្រួល Pitch, Rate, Audio FX | បង្កើតសំឡេង Clone ផ្ទាល់ខ្លួន",
            font=ctk.CTkFont(family=self.active_font_family, size=10),
            text_color="#94a3b8"
        )
        sub_lbl.pack(anchor="w")

        # Badges & Quick Stats
        badges_box = ctk.CTkFrame(header, fg_color="transparent")
        badges_box.pack(side="right", padx=12, pady=6)

        b1 = ctk.CTkLabel(badges_box, text="⚡ Neural HD", font=ctk.CTkFont(size=9, weight="bold"), fg_color="#064e3b", text_color="#34d399", corner_radius=4, padx=6, pady=2)
        b1.pack(side="left", padx=3)
        b2 = ctk.CTkLabel(badges_box, text="🧬 Voice Clone", font=ctk.CTkFont(size=9, weight="bold"), fg_color="#312e81", text_color="#a5b4fc", corner_radius=4, padx=6, pady=2)
        b2.pack(side="left", padx=3)
        b3 = ctk.CTkLabel(badges_box, text="🇰🇭 Khmer Unicode", font=ctk.CTkFont(size=9, weight="bold"), fg_color="#1e293b", text_color="#38bdf8", corner_radius=4, padx=6, pady=2)
        b3.pack(side="left", padx=3)

        # ------------------ 2. MAIN RESIZABLE STUDIO PANES ------------------
        self.paned_studio = tk.PanedWindow(
            self,
            orient="horizontal",
            bg="#0e1014",
            bd=0,
            sashwidth=6,
            sashrelief="groove",
            sashpad=1
        )
        self.paned_studio.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)

        # Left Pane: Editor & Voice Clone Studio
        pane_left = tk.Frame(self.paned_studio, bg="#0e1014", bd=0)
        pane_left.grid_columnconfigure(0, weight=1)
        pane_left.grid_rowconfigure(1, weight=1)

        # Right Pane: Controls, Tuning, BGM & Export
        pane_right = tk.Frame(self.paned_studio, bg="#0e1014", bd=0)
        pane_right.grid_columnconfigure(0, weight=1)

        self.paned_studio.add(pane_left, minsize=460, stretch="always")
        self.paned_studio.add(pane_right, minsize=320, stretch="never")

        # Build Left & Right content
        self._build_left_editor(pane_left)
        self._build_right_controls(pane_right)

    # ------------------ LEFT COLUMN: EDITOR & VOICE CLONING ------------------
    def _build_left_editor(self, parent):
        # 1. Text Editor Toolbar (Font, Size, Presets, Actions)
        toolbar = ctk.CTkFrame(parent, fg_color="#161922", corner_radius=0, height=36)
        toolbar.pack(fill="x", padx=4, pady=(2, 4))

        # Font Family Switcher
        lbl_font = ctk.CTkLabel(toolbar, text="🔤 Font:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8")
        lbl_font.pack(side="left", padx=(8, 3), pady=4)

        self.combo_font = ctk.CTkComboBox(
            toolbar,
            values=self.installed_fonts[:25],
            width=140,
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10),
            command=self._on_font_change
        )
        self.combo_font.set(self.active_font_family)
        self.combo_font.pack(side="left", padx=2, pady=4)

        # Font Size Switcher
        self.combo_font_size = ctk.CTkComboBox(
            toolbar,
            values=["11", "12", "13", "14", "16", "18", "20", "22"],
            width=55,
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10),
            command=self._on_font_size_change
        )
        self.combo_font_size.set(str(self.active_font_size))
        self.combo_font_size.pack(side="left", padx=2, pady=4)

        # Sample Texts Loader
        lbl_sample = ctk.CTkLabel(toolbar, text="📄 Sample:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8")
        lbl_sample.pack(side="left", padx=(10, 3), pady=4)

        self.combo_sample = ctk.CTkComboBox(
            toolbar,
            values=list(KHMER_SAMPLE_TEXTS.keys()),
            width=175,
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10),
            command=self._load_sample_text
        )
        self.combo_sample.set("ជ្រើសរើសអត្ថបទគំរូ...")
        self.combo_sample.pack(side="left", padx=2, pady=4)

        # Paste & Clear Buttons
        btn_paste = ctk.CTkButton(
            toolbar,
            text="📋 Paste",
            command=self._paste_clipboard,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=26,
            width=60,
            font=ctk.CTkFont(size=10)
        )
        btn_paste.pack(side="right", padx=(2, 6), pady=4)

        btn_clear = ctk.CTkButton(
            toolbar,
            text="🧹 Clear",
            command=self._clear_text,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=26,
            width=60,
            font=ctk.CTkFont(size=10)
        )
        btn_clear.pack(side="right", padx=2, pady=4)

        # 2. Main Khmer Text Editor Box
        editor_card = ctk.CTkFrame(parent, fg_color="#12141c", corner_radius=0)
        editor_card.pack(fill="both", expand=True, padx=4, pady=2)
        editor_card.grid_columnconfigure(0, weight=1)
        editor_card.grid_rowconfigure(0, weight=1)

        self.txt_input = ctk.CTkTextbox(
            editor_card,
            fg_color="#090a0f",
            text_color="#f8fafc",
            font=ctk.CTkFont(family=self.active_font_family, size=self.active_font_size),
            corner_radius=0,
            undo=True,
            wrap="word"
        )
        self.txt_input.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        self.txt_input.insert(
            "1.0",
            "សួស្តី! នេះជាស្ទូឌីយោបំប្លែងអត្ថបទទៅជាសំឡេងនិយាយភាសាខ្មែរ AI ធម្មជាតិកម្រិតខ្ពស់ (Neural Studio TTS)។\n\n"
            "អ្នកអាចវាយ ឬ Paste អត្ថបទសាច់រឿង ព័ត៌មាន ឬស្ពតពាណិជ្ជកម្មនៅទីនេះ ហើយជ្រើសរើសតួអង្គសំឡេង ឬបង្កើតសំឡេង Clone ផ្ទាល់ខ្លួន "
            "រួចចុចប៊ូតុងខាងស្តាំដើម្បីស្ដាប់ ឬ Export ជាឯកសារ MP3 / WAV Studio Quality!"
        )
        self.txt_input.bind("<KeyRelease>", lambda e: self._update_text_metrics())

        # Live Metrics Status Bar
        metrics_bar = ctk.CTkFrame(editor_card, fg_color="#0a0c10", corner_radius=0, height=24)
        metrics_bar.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

        self.lbl_metrics = ctk.CTkLabel(
            metrics_bar,
            text="🔤 Words: 0 | 📝 Chars: 0 | ⏱️ Est. Speech Time: ~0.0s",
            font=ctk.CTkFont(size=10),
            text_color="#94a3b8"
        )
        self.lbl_metrics.pack(side="left", padx=8, pady=2)

    def _build_right_controls(self, parent):
        # 1. FIXED BOTTOM ACTION DOCK (ALWAYS VISIBLE: Generate, Play, Replay, Stop, Export)
        action_box = ctk.CTkFrame(parent, fg_color="#141720", corner_radius=0)
        action_box.pack(side="bottom", fill="x", padx=4, pady=(2, 4))

        # Row 1: Speak / Generate, Replay MP3, Stop
        p_row = ctk.CTkFrame(action_box, fg_color="transparent")
        p_row.pack(fill="x", padx=8, pady=(6, 4))

        self.btn_speak = ctk.CTkButton(
            p_row,
            text="🔊 បង្កើត & ស្ដាប់ (Generate & Play)",
            command=self.speak_text_thread,
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=0,
            height=34,
            font=ctk.CTkFont(family=self.active_font_family, size=11, weight="bold")
        )
        self.btn_speak.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_replay = ctk.CTkButton(
            p_row,
            text="▶ ចាក់ MP3 ឡើងវិញ",
            command=self.replay_current_audio,
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=0,
            height=34,
            width=120,
            state="normal" if (hasattr(self, "current_preview_audio") and self.current_preview_audio) else "disabled",
            font=ctk.CTkFont(family=self.active_font_family, size=10, weight="bold")
        )
        self.btn_replay.pack(side="left", padx=(0, 4))

        self.btn_stop = ctk.CTkButton(
            p_row,
            text="⏹️ បញ្ឈប់",
            command=self.stop_speech,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=34,
            width=65,
            font=ctk.CTkFont(family=self.active_font_family, size=11)
        )
        self.btn_stop.pack(side="left")

        # Row 2: Export Button
        self.btn_export = ctk.CTkButton(
            action_box,
            text="💾 Export Audio File (.mp3 / .wav)",
            command=self.export_audio_thread,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            corner_radius=0,
            height=32,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_export.pack(fill="x", padx=8, pady=(2, 6))

        # Row 3: Real-time Status & Progress
        self.progress_bar = ctk.CTkProgressBar(action_box, height=4, corner_radius=0)
        self.progress_bar.set(0.0)
        self.progress_bar.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_status = ctk.CTkLabel(
            action_box,
            text="Ready (រួចរាល់)",
            text_color="#64748b",
            font=ctk.CTkFont(size=10)
        )
        self.lbl_status.pack(anchor="w", padx=10, pady=(0, 6))

        # 2. SCROLLABLE CONTAINER FOR STUDIO CARDS
        scroll_controls = ctk.CTkScrollableFrame(parent, fg_color="#12141c", corner_radius=0)
        scroll_controls.pack(side="top", fill="both", expand=True, padx=4, pady=2)
        scroll_controls.grid_columnconfigure(0, weight=1)

        # =========================================================================
        # CARD 1: 🎛️ AI VOICE / TTS STUDIO SELECTOR DECK
        # =========================================================================
        card_studio = ctk.CTkFrame(scroll_controls, fg_color="#181b24", corner_radius=0)
        card_studio.pack(fill="x", padx=4, pady=(2, 6))

        h1 = ctk.CTkLabel(
            card_studio,
            text="🎛️ AI VOICE / TTS STUDIO",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#38bdf8"
        )
        h1.pack(anchor="w", padx=10, pady=(8, 1))

        lbl_sub = ctk.CTkLabel(
            card_studio,
            text="ជ្រើសរើស TTS Engine ដើម្បីបើកមុខងារតាម AI នីមួយៗ (VoxCPM, Gemini, Edge TTS, F5-TTS, ElevenLabs)",
            font=ctk.CTkFont(family=self.active_font_family, size=9),
            text_color="#94a3b8",
            wraplength=300,
            justify="left"
        )
        lbl_sub.pack(anchor="w", padx=10, pady=(0, 6))

        # Main Engine Switcher Dropdown
        self.combo_engine = ctk.CTkComboBox(
            card_studio,
            values=[
                self.ENGINE_VOXCPM,
                self.ENGINE_GEMINI,
                self.ENGINE_EDGETTS,
                self.ENGINE_F5TTS,
                self.ENGINE_ELEVENLABS
            ],
            height=28,
            corner_radius=0,
            font=ctk.CTkFont(size=11, weight="bold"),
            dropdown_font=ctk.CTkFont(size=10),
            command=self._on_engine_change
        )
        self.combo_engine.set(self.active_engine)
        self.combo_engine.pack(fill="x", padx=10, pady=(0, 8))

        # Dynamic Engine Content Container (switches UI based on selected engine)
        self.frame_dynamic_engine = ctk.CTkFrame(scroll_controls, fg_color="transparent")
        self.frame_dynamic_engine.pack(fill="x", padx=4, pady=2)

        # =========================================================================
        # CARD 2: BACKGROUND MUSIC (BGM) MIXING
        # =========================================================================
        card_bgm = ctk.CTkFrame(scroll_controls, fg_color="#181b24", corner_radius=0)
        card_bgm.pack(fill="x", padx=4, pady=(6, 6))

        self.check_bgm = ctk.CTkCheckBox(
            card_bgm,
            text="🎵 Add Background Music (BGM)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#f59e0b",
            corner_radius=0,
            command=self._toggle_bgm_options
        )
        self.check_bgm.pack(anchor="w", padx=10, pady=(8, 4))

        self.frame_bgm_ops = ctk.CTkFrame(card_bgm, fg_color="transparent")
        self.frame_bgm_ops.pack(fill="x", padx=10, pady=(0, 8))

        btn_browse_bgm = ctk.CTkButton(
            self.frame_bgm_ops,
            text="📂 Browse BGM File (.mp3/.wav)",
            command=self._browse_bgm_file,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=24,
            font=ctk.CTkFont(size=10)
        )
        btn_browse_bgm.pack(fill="x", pady=(2, 4))

        self.lbl_bgm_file = ctk.CTkLabel(
            self.frame_bgm_ops,
            text="No BGM Selected",
            font=ctk.CTkFont(size=9),
            text_color="#64748b"
        )
        self.lbl_bgm_file.pack(anchor="w")

        self.lbl_bgm_vol = ctk.CTkLabel(self.frame_bgm_ops, text="BGM Volume: 15%", font=ctk.CTkFont(size=9), text_color="#cbd5e1")
        self.lbl_bgm_vol.pack(anchor="w", pady=(4, 1))

        self.slider_bgm_vol = ctk.CTkSlider(
            self.frame_bgm_ops,
            from_=2,
            to=50,
            number_of_steps=24,
            height=12,
            command=self._on_bgm_vol_slider
        )
        self.slider_bgm_vol.set(15)
        self.slider_bgm_vol.pack(fill="x", pady=(0, 4))

        # =========================================================================
        # CARD 3: EXPORT FORMAT & QUALITY
        # =========================================================================
        card_exp = ctk.CTkFrame(scroll_controls, fg_color="#181b24", corner_radius=0)
        card_exp.pack(fill="x", padx=4, pady=(0, 8))

        ctk.CTkLabel(card_exp, text="💾 Format & Audio Quality:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", padx=10, pady=(8, 2))
        self.combo_quality = ctk.CTkComboBox(
            card_exp,
            values=list(AUDIO_EXPORT_QUALITIES.keys()),
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10)
        )
        self.combo_quality.set("MP3 320 kbps (Studio Quality / ច្បាស់បំផុត)")
        self.combo_quality.pack(fill="x", padx=10, pady=(0, 8))

        # Initial Render of the active engine
        self._render_engine_ui(self.active_engine)

    def _on_engine_change(self, engine_name: str):
        self.active_engine = engine_name
        self._render_engine_ui(engine_name)

    def _render_engine_ui(self, engine_name: str):
        """Dynamically clears and renders the exact toolset supported by the chosen engine"""
        for widget in self.frame_dynamic_engine.winfo_children():
            widget.destroy()

        if "VoxCPM" in engine_name:
            self._render_voxcpm_ui(self.frame_dynamic_engine)
        elif "Gemini" in engine_name:
            self._render_gemini_ui(self.frame_dynamic_engine)
        elif "Edge TTS" in engine_name:
            self._render_edgetts_ui(self.frame_dynamic_engine)
        elif "F5-TTS" in engine_name:
            self._render_f5tts_ui(self.frame_dynamic_engine)
        elif "ElevenLabs" in engine_name:
            self._render_elevenlabs_ui(self.frame_dynamic_engine)

    # ------------------ ENGINE 1: VOXCPM VOICE CLONE & NEURAL MODEL STUDIO ------------------
    def _render_voxcpm_ui(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#181b24", corner_radius=0)
        card.pack(fill="x", pady=2)

        # Header Badge
        h_box = ctk.CTkFrame(card, fg_color="#1e2230", corner_radius=0, height=28)
        h_box.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(h_box, text="🧬 VOXCPM VOICE CLONE & NEURAL MODEL", font=ctk.CTkFont(size=10, weight="bold"), text_color="#10b981").pack(side="left", padx=8)
        ctk.CTkLabel(h_box, text="Neural Latent Model", font=ctk.CTkFont(size=8, weight="bold"), fg_color="#064e3b", text_color="#34d399", corner_radius=3, padx=5, pady=1).pack(side="right", padx=6)

        # 1. Voice Clone Reference Audio Sample Upload
        sec1 = ctk.CTkFrame(card, fg_color="transparent")
        sec1.pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkLabel(sec1, text="📁 1. Voice Clone Sample (សំឡេងគំរូដើម):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        
        btn_upload = ctk.CTkButton(
            sec1,
            text="📂 Upload Voice Sample (.wav, .mp3, .m4a)",
            command=self._browse_voxcpm_sample,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        btn_upload.pack(fill="x", pady=2)

        r_play_box = ctk.CTkFrame(sec1, fg_color="transparent")
        r_play_box.pack(fill="x", pady=2)

        self.btn_audition_voxcpm = ctk.CTkButton(
            r_play_box,
            text="▶ Audition Sample",
            command=self._audition_voxcpm_sample,
            fg_color="#1e293b",
            hover_color="#334155",
            corner_radius=0,
            height=22,
            width=110,
            state="normal" if self.voxcpm_ref_path else "disabled",
            font=ctk.CTkFont(size=9)
        )
        self.btn_audition_voxcpm.pack(side="left", padx=(0, 6))

        self.lbl_voxcpm_status = ctk.CTkLabel(
            r_play_box,
            text=os.path.basename(self.voxcpm_ref_path) if self.voxcpm_ref_path else "No audio sample selected",
            font=ctk.CTkFont(size=9),
            text_color="#2dd4bf" if self.voxcpm_ref_path else "#64748b"
        )
        self.lbl_voxcpm_status.pack(side="left", fill="x", expand=True)

        # 2. Preset Cloned Voices
        ctk.CTkLabel(card, text="🎭 2. Preset Voices (សំឡេងម៉ូដែលស្រាប់):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", padx=10, pady=(6, 2))
        self.combo_voxcpm_preset = ctk.CTkComboBox(
            card,
            values=[
                "👑 Piseth - Movie Hero (បុរសភាពយន្ត)",
                "🌸 Sreymom - Soft Storyteller (និទានរឿងស្រទន់)",
                "🎙️ Uncle Narration - Deep Cinema (សំឡេងអត្ថាធិប្បាយចាស់ទុំ)",
                "⚡ Anime / Cartoon Energetic (កុមារ & គំនូរជីវចល)",
                "📻 Vintage Radio Voice (វិទ្យុបុរាណ)",
                "⚔️ Dramatic Trailer Narrator (រំភើប/សង្គ្រាម)"
            ],
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10),
            command=self._on_voxcpm_preset_change
        )
        self.combo_voxcpm_preset.set(self.voxcpm_preset)
        self.combo_voxcpm_preset.pack(fill="x", padx=10, pady=(0, 6))

        # 3. Clone / Save Voice Model Manager
        sec3 = ctk.CTkFrame(card, fg_color="#10131a", corner_radius=0)
        sec3.pack(fill="x", padx=8, pady=4)

        ctk.CTkLabel(sec3, text="💾 3. Clone & Save Voice Model (បង្កើត Model ផ្ទាល់ខ្លួន):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#f59e0b").pack(anchor="w", padx=8, pady=(4, 2))
        
        row_m1 = ctk.CTkFrame(sec3, fg_color="transparent")
        row_m1.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row_m1, text="Model Name:", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left", padx=(0, 4))
        self.ent_voxcpm_name = ctk.CTkEntry(row_m1, placeholder_text="e.g. My_Khmer_Actor_01", height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.ent_voxcpm_name.pack(side="left", fill="x", expand=True)

        row_m2 = ctk.CTkFrame(sec3, fg_color="transparent")
        row_m2.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row_m2, text="Prompt Style:", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left", padx=(0, 4))
        self.ent_voxcpm_prompt = ctk.CTkEntry(row_m2, placeholder_text="e.g. សំឡេងកាច ក្នុងរឿងប្រយុទ្ធ", height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.ent_voxcpm_prompt.pack(side="left", fill="x", expand=True)

        btn_save_m = ctk.CTkButton(
            sec3,
            text="✨ Clone & Save Voice Model",
            command=self._save_voxcpm_model,
            fg_color="#4f46e5",
            hover_color="#4338ca",
            corner_radius=0,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        btn_save_m.pack(fill="x", padx=8, pady=(4, 4))

        row_m3 = ctk.CTkFrame(sec3, fg_color="transparent")
        row_m3.pack(fill="x", padx=8, pady=(2, 6))
        ctk.CTkLabel(row_m3, text="Saved Models:", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left", padx=(0, 4))
        
        self.combo_voxcpm_saved = ctk.CTkComboBox(row_m3, values=["(No Models)"], width=130, height=24, corner_radius=0, font=ctk.CTkFont(size=9), command=self._on_select_saved_voxcpm_model)
        self.combo_voxcpm_saved.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._refresh_voxcpm_saved_dropdown()

        btn_del_m = ctk.CTkButton(row_m3, text="🗑️ Del", width=45, height=24, corner_radius=0, fg_color="#334155", hover_color="#ef4444", font=ctk.CTkFont(size=9), command=self._delete_voxcpm_model)
        btn_del_m.pack(side="left")

        # 4. Acoustic Calibration (Tuning Sliders)
        sec4 = ctk.CTkFrame(card, fg_color="transparent")
        sec4.pack(fill="x", padx=10, pady=(4, 8))

        ctk.CTkLabel(sec4, text="🎛️ 4. Acoustic Calibration (Pitch & Formant):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))

        self.lbl_v_pitch = ctk.CTkLabel(sec4, text=f"Pitch Scale: {self.voxcpm_pitch:.2f}x", font=ctk.CTkFont(size=9), text_color="#38bdf8")
        self.lbl_v_pitch.pack(anchor="w")
        self.slider_v_pitch = ctk.CTkSlider(sec4, from_=0.75, to=1.35, number_of_steps=60, height=12, command=self._on_voxcpm_pitch_slider)
        self.slider_v_pitch.set(self.voxcpm_pitch)
        self.slider_v_pitch.pack(fill="x", pady=(0, 3))

        self.lbl_v_bass = ctk.CTkLabel(sec4, text=f"Bass Warmth: +{int(self.voxcpm_bass)} dB", font=ctk.CTkFont(size=9), text_color="#34d399")
        self.lbl_v_bass.pack(anchor="w")
        self.slider_v_bass = ctk.CTkSlider(sec4, from_=-6.0, to=12.0, number_of_steps=36, height=12, command=self._on_voxcpm_bass_slider)
        self.slider_v_bass.set(self.voxcpm_bass)
        self.slider_v_bass.pack(fill="x", pady=(0, 3))

        self.lbl_v_treble = ctk.CTkLabel(sec4, text=f"Treble Sparkle: +{int(self.voxcpm_treble)} dB", font=ctk.CTkFont(size=9), text_color="#f59e0b")
        self.lbl_v_treble.pack(anchor="w")
        self.slider_v_treble = ctk.CTkSlider(sec4, from_=-6.0, to=10.0, number_of_steps=32, height=12, command=self._on_voxcpm_treble_slider)
        self.slider_v_treble.set(self.voxcpm_treble)
        self.slider_v_treble.pack(fill="x", pady=(0, 3))

    # ------------------ ENGINE 2: GEMINI AI VOICE (GOOGLE DEEPMIND) ------------------
    def _render_gemini_ui(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#181b24", corner_radius=0)
        card.pack(fill="x", pady=2)

        # Header Badge
        h_box = ctk.CTkFrame(card, fg_color="#1e2230", corner_radius=0, height=28)
        h_box.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(h_box, text="🤖 GEMINI AI VOICE (GOOGLE DEEPMIND)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(side="left", padx=8)
        ctk.CTkLabel(h_box, text="Emotion & Tone AI", font=ctk.CTkFont(size=8, weight="bold"), fg_color="#1e3a8a", text_color="#93c5fd", corner_radius=3, padx=5, pady=1).pack(side="right", padx=6)

        # 1. API Configuration
        sec1 = ctk.CTkFrame(card, fg_color="transparent")
        sec1.pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkLabel(sec1, text="🔑 1. Gemini API Key & Model:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        
        row_key = ctk.CTkFrame(sec1, fg_color="transparent")
        row_key.pack(fill="x", pady=2)
        self.ent_gemini_key = ctk.CTkEntry(row_key, placeholder_text="AIzaSy... (Gemini API Key)", show="*", height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.ent_gemini_key.insert(0, self.gemini_api_key)
        self.ent_gemini_key.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_save_key = ctk.CTkButton(row_key, text="Save Key", width=60, height=24, corner_radius=0, fg_color="#2563eb", font=ctk.CTkFont(size=9), command=self._save_gemini_key)
        btn_save_key.pack(side="left")

        self.combo_gemini_model = ctk.CTkComboBox(
            sec1,
            values=["gemini-2.0-flash (Ultra Fast Voice)", "gemini-1.5-pro (Rich Nuance)", "gemini-1.5-flash (Low Latency)"],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_gemini_model.set("gemini-2.0-flash (Ultra Fast Voice)")
        self.combo_gemini_model.pack(fill="x", pady=(2, 4))

        ctk.CTkLabel(sec1, text="🎙️ Gemini Prebuilt Voice:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#94a3b8").pack(anchor="w", pady=(2, 1))
        self.combo_gemini_voice = ctk.CTkComboBox(
            sec1,
            values=[
                "Puck (Energetic & Natural Male)",
                "Charon (Deep Cinema Male)",
                "Kore (Calm & Soothing Female)",
                "Fenrir (Authoritative & Strong Male)",
                "Aoede (Warm & Expressive Female)"
            ],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_gemini_voice.set("Puck (Energetic & Natural Male)")
        self.combo_gemini_voice.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(sec1, text="💡 ទទួលបាន API Key Free ពី: https://aistudio.google.com/apikey", font=ctk.CTkFont(size=8), text_color="#38bdf8").pack(anchor="w", pady=(1, 2))

        # 2. Voice Persona & System Prompt
        sec2 = ctk.CTkFrame(card, fg_color="transparent")
        sec2.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(sec2, text="🎭 2. Voice Persona / System Prompt (បុគ្គលិកលក្ខណៈ):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.txt_gemini_persona = ctk.CTkEntry(sec2, height=26, corner_radius=0, font=ctk.CTkFont(family=self.active_font_family, size=9))
        self.txt_gemini_persona.insert(0, self.gemini_prompt)
        self.txt_gemini_persona.pack(fill="x", pady=(0, 3))

        self.combo_gemini_presets = ctk.CTkComboBox(
            sec2,
            values=[
                "🧘 Calm & Peaceful Meditation (សមាធិ ស្រទន់)",
                "🔥 Thrilling & Urgent Cinema Trailer (ភាពយន្តរំភើប)",
                "📖 Friendly Khmer Bedtime Storyteller (និទានរឿងកុមារ)",
                "💼 Professional Financial News Anchor (ព័ត៌មានវិទ្យា)",
                "🎙️ Lively FM Radio Host (ពិធីករវិទ្យុ)"
            ],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9),
            command=self._on_gemini_preset_select
        )
        self.combo_gemini_presets.set("ជ្រើសរើស Persona គំរូ...")
        self.combo_gemini_presets.pack(fill="x", pady=(0, 4))

        # 3. Emotional Tone & Mood
        sec3 = ctk.CTkFrame(card, fg_color="transparent")
        sec3.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(sec3, text="🌟 3. Emotional Tone / Mood (អារម្មណ៍និយាយ):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_gemini_emotion = ctk.CTkComboBox(
            sec3,
            values=[
                "Friendly & Warm (រាក់ទាក់ កក់ក្ដៅ)",
                "Dramatic Cinema (រំភើប តានតឹង)",
                "Storyteller / និទានរឿង",
                "Whisper / ខ្សឹបស្រទន់",
                "Professional News (ព័ត៌មាន)",
                "Sympathetic & Gentle (អាណិតអាសូរ)",
                "Energetic & Exciting (ស្វាហាប់)"
            ],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_gemini_emotion.set(self.gemini_emotion)
        self.combo_gemini_emotion.pack(fill="x", pady=(0, 4))

        # 4. Language & Accent
        sec4 = ctk.CTkFrame(card, fg_color="transparent")
        sec4.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(sec4, text="🌐 4. Language & Dialect:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_gemini_lang = ctk.CTkComboBox(
            sec4,
            values=["Khmer (ភាសាខ្មែរ)", "English (US)", "English (UK)", "Chinese (Mandarin)", "Japanese", "Thai", "Vietnamese"],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_gemini_lang.set(self.gemini_lang)
        self.combo_gemini_lang.pack(fill="x", pady=(0, 4))

        # 5. Creativity & Pace Tuning
        sec5 = ctk.CTkFrame(card, fg_color="transparent")
        sec5.pack(fill="x", padx=10, pady=(2, 8))

        self.lbl_g_temp = ctk.CTkLabel(sec5, text=f"Temperature: {self.gemini_temp:.1f}", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_g_temp.pack(anchor="w")
        self.slider_g_temp = ctk.CTkSlider(sec5, from_=0.0, to=1.0, number_of_steps=20, height=12, command=lambda v: self.lbl_g_temp.configure(text=f"Temperature: {v:.1f}"))
        self.slider_g_temp.set(self.gemini_temp)
        self.slider_g_temp.pack(fill="x", pady=(0, 3))

        self.lbl_g_pace = ctk.CTkLabel(sec5, text=f"Speaking Pace: {self.gemini_pace:.1f}x", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_g_pace.pack(anchor="w")
        self.slider_g_pace = ctk.CTkSlider(sec5, from_=0.7, to=1.5, number_of_steps=16, height=12, command=lambda v: self.lbl_g_pace.configure(text=f"Speaking Pace: {v:.1f}x"))
        self.slider_g_pace.set(self.gemini_pace)
        self.slider_g_pace.pack(fill="x")

    # ------------------ ENGINE 3: EDGE TTS (KHMER NEURAL STUDIO) ------------------
    def _render_edgetts_ui(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#181b24", corner_radius=0)
        card.pack(fill="x", pady=2)

        # Header Badge
        h_box = ctk.CTkFrame(card, fg_color="#1e2230", corner_radius=0, height=28)
        h_box.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(h_box, text="🇰🇭 EDGE TTS (KHMER NEURAL STUDIO)", font=ctk.CTkFont(size=10, weight="bold"), text_color="#f59e0b").pack(side="left", padx=8)
        ctk.CTkLabel(h_box, text="100% Free & Fast", font=ctk.CTkFont(size=8, weight="bold"), fg_color="#78350f", text_color="#fde68a", corner_radius=3, padx=5, pady=1).pack(side="right", padx=6)

        # 1. Voice Actor Selection
        sec1 = ctk.CTkFrame(card, fg_color="transparent")
        sec1.pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkLabel(sec1, text="🎭 1. Khmer Voice Actor:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_edge_voice = ctk.CTkComboBox(
            sec1,
            values=[
                "Piseth (Male / ប្រុសធម្មជាតិ)",
                "Sreymom (Female / ស្រីធម្មជាតិ)",
                "Keo (Deep Radio Male)",
                "Chantrea (Expressive Story Female)",
                "Pich (Cinema Narrator Male)"
            ],
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10)
        )
        self.combo_edge_voice.set(self.edge_voice)
        self.combo_edge_voice.pack(fill="x", pady=(0, 4))

        # 2. Voice Tuning Controls
        sec2 = ctk.CTkFrame(card, fg_color="transparent")
        sec2.pack(fill="x", padx=10, pady=(2, 6))

        self.lbl_e_speed = ctk.CTkLabel(sec2, text=f"⚡ Speed Rate: 1.0x (+{self.edge_rate}%)", font=ctk.CTkFont(size=9), text_color="#cbd5e1")
        self.lbl_e_speed.pack(anchor="w")
        self.slider_e_speed = ctk.CTkSlider(sec2, from_=-50, to=80, number_of_steps=26, height=12, command=self._on_edge_speed_slider)
        self.slider_e_speed.set(self.edge_rate)
        self.slider_e_speed.pack(fill="x", pady=(0, 3))

        self.lbl_e_pitch = ctk.CTkLabel(sec2, text=f"🎼 Pitch Tuning: {self.edge_pitch} Hz", font=ctk.CTkFont(size=9), text_color="#cbd5e1")
        self.lbl_e_pitch.pack(anchor="w")
        self.slider_e_pitch = ctk.CTkSlider(sec2, from_=-40, to=40, number_of_steps=40, height=12, command=self._on_edge_pitch_slider)
        self.slider_e_pitch.set(self.edge_pitch)
        self.slider_e_pitch.pack(fill="x", pady=(0, 3))

        self.lbl_e_vol = ctk.CTkLabel(sec2, text=f"🔊 Volume Boost: {self.edge_volume}%", font=ctk.CTkFont(size=9), text_color="#cbd5e1")
        self.lbl_e_vol.pack(anchor="w")
        self.slider_e_vol = ctk.CTkSlider(sec2, from_=50, to=200, number_of_steps=30, height=12, command=self._on_edge_vol_slider)
        self.slider_e_vol.set(self.edge_volume)
        self.slider_e_vol.pack(fill="x", pady=(0, 4))

        # 3. Voice Profile & Studio FX
        sec3 = ctk.CTkFrame(card, fg_color="transparent")
        sec3.pack(fill="x", padx=10, pady=(2, 8))

        ctk.CTkLabel(sec3, text="✨ 3. Voice Profile Presets:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_edge_profile = ctk.CTkComboBox(
            sec3,
            values=["Natural (ធម្មជាតិ)", "Storybook (និទានរឿង)", "News Anchor (អានព័ត៌មាន)", "Cinema Trailer (ភាពយន្ត)", "Commercial (ស្ពតពាណិជ្ជកម្ម)"],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_edge_profile.set(self.edge_profile)
        self.combo_edge_profile.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(sec3, text="🎧 Studio Audio FX Preset:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(2, 2))
        self.combo_edge_fx = ctk.CTkComboBox(
            sec3,
            values=list(VOICE_EFFECTS.keys()),
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_edge_fx.set(self.edge_fx)
        self.combo_edge_fx.pack(fill="x")

    # ------------------ ENGINE 4: F5-TTS / COQUI ZERO-SHOT CLONE ------------------
    def _render_f5tts_ui(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#181b24", corner_radius=0)
        card.pack(fill="x", pady=2)

        # Header Badge
        h_box = ctk.CTkFrame(card, fg_color="#1e2230", corner_radius=0, height=28)
        h_box.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(h_box, text="⚡ F5-TTS / COQUI ZERO-SHOT CLONE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#a855f7").pack(side="left", padx=8)
        ctk.CTkLabel(h_box, text="Zero-Shot Neural", font=ctk.CTkFont(size=8, weight="bold"), fg_color="#581c87", text_color="#e9d5ff", corner_radius=3, padx=5, pady=1).pack(side="right", padx=6)

        sec1 = ctk.CTkFrame(card, fg_color="transparent")
        sec1.pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkLabel(sec1, text="📁 1. Zero-Shot Audio Reference (3-10s):", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        btn_f5_upload = ctk.CTkButton(sec1, text="📂 Upload Clean Reference Audio", command=self._browse_f5_sample, fg_color="#334155", hover_color="#475569", height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        btn_f5_upload.pack(fill="x", pady=2)

        self.lbl_f5_file = ctk.CTkLabel(sec1, text=os.path.basename(self.f5_ref_path) if self.f5_ref_path else "No audio reference selected", font=ctk.CTkFont(size=9), text_color="#c084fc" if self.f5_ref_path else "#64748b")
        self.lbl_f5_file.pack(anchor="w", pady=(0, 4))

        sec2 = ctk.CTkFrame(card, fg_color="transparent")
        sec2.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(sec2, text="🌐 2. Cross-Lingual & Expressiveness:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_f5_lang = ctk.CTkComboBox(sec2, values=["Khmer (Cambodia)", "English", "Chinese", "Multilingual Cross-Clone"], height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.combo_f5_lang.set(self.f5_lang)
        self.combo_f5_lang.pack(fill="x", pady=(0, 4))

        self.lbl_f5_exp = ctk.CTkLabel(sec2, text=f"Emotion Expressiveness: {self.f5_expressiveness:.1f}x", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_f5_exp.pack(anchor="w")
        self.slider_f5_exp = ctk.CTkSlider(sec2, from_=0.5, to=2.0, number_of_steps=15, height=12, command=lambda v: self.lbl_f5_exp.configure(text=f"Emotion Expressiveness: {v:.1f}x"))
        self.slider_f5_exp.set(self.f5_expressiveness)
        self.slider_f5_exp.pack(fill="x", pady=(0, 4))

        sec3 = ctk.CTkFrame(card, fg_color="transparent")
        sec3.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkLabel(sec3, text="⚙️ 3. Hardware Device & Acceleration:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_f5_device = ctk.CTkComboBox(sec3, values=["Auto-Detect GPU (CUDA DirectML)", "CPU Multi-Thread (AVX-512)"], height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.combo_f5_device.set(self.f5_device)
        self.combo_f5_device.pack(fill="x")

    # ------------------ ENGINE 5: ELEVENLABS AI (HYPER-REALISTIC STUDIO) ------------------
    def _render_elevenlabs_ui(self, parent):
        card = ctk.CTkFrame(parent, fg_color="#181b24", corner_radius=0)
        card.pack(fill="x", pady=2)

        # Header Badge
        h_box = ctk.CTkFrame(card, fg_color="#1e2230", corner_radius=0, height=28)
        h_box.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(h_box, text="💎 ELEVENLABS HYPER-REALISTIC STUDIO", font=ctk.CTkFont(size=10, weight="bold"), text_color="#ec4899").pack(side="left", padx=8)
        ctk.CTkLabel(h_box, text="Cinema Quality", font=ctk.CTkFont(size=8, weight="bold"), fg_color="#831843", text_color="#fbcfe8", corner_radius=3, padx=5, pady=1).pack(side="right", padx=6)

        sec1 = ctk.CTkFrame(card, fg_color="transparent")
        sec1.pack(fill="x", padx=10, pady=(4, 6))

        ctk.CTkLabel(sec1, text="🔑 1. API Credentials & Model:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.ent_eleven_key = ctk.CTkEntry(sec1, placeholder_text="xi-api-key...", show="*", height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.ent_eleven_key.insert(0, self.eleven_api_key)
        self.ent_eleven_key.pack(fill="x", pady=2)

        self.combo_eleven_model = ctk.CTkComboBox(sec1, values=["Eleven Multilingual v2 (Best Nuance)", "Eleven Turbo v2.5 (Fastest)"], height=24, corner_radius=0, font=ctk.CTkFont(size=9))
        self.combo_eleven_model.set(self.eleven_model)
        self.combo_eleven_model.pack(fill="x", pady=2)

        sec2 = ctk.CTkFrame(card, fg_color="transparent")
        sec2.pack(fill="x", padx=10, pady=(2, 6))

        ctk.CTkLabel(sec2, text="🎭 2. Voice Library & Persona:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        self.combo_eleven_voice = ctk.CTkComboBox(
            sec2,
            values=[
                "Adam (Deep Cinema Male)",
                "Rachel (Calm & Professional)",
                "Antoni (Dramatic & Story)",
                "Bella (Warm & Expressive)",
                "Josh (Youthful & Energetic)",
                "Custom Cloned Voice ID..."
            ],
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_eleven_voice.set(self.eleven_voice)
        self.combo_eleven_voice.pack(fill="x", pady=2)

        sec3 = ctk.CTkFrame(card, fg_color="transparent")
        sec3.pack(fill="x", padx=10, pady=(2, 8))

        ctk.CTkLabel(sec3, text="🎛️ 3. Voice Design Tuning:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))

        self.lbl_el_stab = ctk.CTkLabel(sec3, text=f"Stability: {int(self.eleven_stability*100)}%", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_el_stab.pack(anchor="w")
        self.slider_el_stab = ctk.CTkSlider(sec3, from_=0.0, to=1.0, number_of_steps=20, height=12, command=lambda v: self.lbl_el_stab.configure(text=f"Stability: {int(v*100)}%"))
        self.slider_el_stab.set(self.eleven_stability)
        self.slider_el_stab.pack(fill="x", pady=(0, 3))

        self.lbl_el_sim = ctk.CTkLabel(sec3, text=f"Similarity & Clarity: {int(self.eleven_similarity*100)}%", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_el_sim.pack(anchor="w")
        self.slider_el_sim = ctk.CTkSlider(sec3, from_=0.0, to=1.0, number_of_steps=20, height=12, command=lambda v: self.lbl_el_sim.configure(text=f"Similarity & Clarity: {int(v*100)}%"))
        self.slider_el_sim.set(self.eleven_similarity)
        self.slider_el_sim.pack(fill="x", pady=(0, 3))

        self.lbl_el_exag = ctk.CTkLabel(sec3, text=f"Style Exaggeration: {int(self.eleven_exaggeration*100)}%", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_el_exag.pack(anchor="w")
        self.slider_el_exag = ctk.CTkSlider(sec3, from_=0.0, to=1.0, number_of_steps=20, height=12, command=lambda v: self.lbl_el_exag.configure(text=f"Style Exaggeration: {int(v*100)}%"))
        self.slider_el_exag.set(self.eleven_exaggeration)
        self.slider_el_exag.pack(fill="x")

    # ------------------ VOXCPM HELPER CALLBACKS ------------------
    def _browse_voxcpm_sample(self):
        f = filedialog.askopenfilename(
            title="Select Voice Sample for VoxCPM Cloning",
            filetypes=[("Audio Files", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg"), ("All Files", "*.*")]
        )
        if f and os.path.exists(f):
            self.voxcpm_ref_path = f
            self.ref_sample_path = f
            if hasattr(self, "lbl_voxcpm_status"):
                self.lbl_voxcpm_status.configure(text=f"✅ {os.path.basename(f)}", text_color="#2dd4bf")
            if hasattr(self, "btn_audition_voxcpm"):
                self.btn_audition_voxcpm.configure(state="normal")

    def _audition_voxcpm_sample(self):
        if self.voxcpm_ref_path and os.path.exists(self.voxcpm_ref_path):
            try:
                pygame.mixer.music.load(self.voxcpm_ref_path)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"Error playing voice sample: {e}")

    def _on_voxcpm_preset_change(self, val: str):
        self.voxcpm_preset = val

    def _save_voxcpm_model(self):
        name = self.ent_voxcpm_name.get().strip() if hasattr(self, "ent_voxcpm_name") else ""
        if not name:
            messagebox.showwarning("ត្រូវការឈ្មោះ Model", "សូមបញ្ចូលឈ្មោះ Model ជាមុនសិន!")
            return
        base_id = "km-KH-PisethNeural"
        p_scale = self.slider_v_pitch.get() if hasattr(self, "slider_v_pitch") else 1.0
        b_gain = self.slider_v_bass.get() if hasattr(self, "slider_v_bass") else 0.0
        t_gain = self.slider_v_treble.get() if hasattr(self, "slider_v_treble") else 0.0
        prompt_txt = self.ent_voxcpm_prompt.get().strip() if hasattr(self, "ent_voxcpm_prompt") else ""

        ok = DubbingEngine.save_cloned_voice(
            name=name,
            base_voice=base_id,
            pitch_scale=p_scale,
            formant=prompt_txt or "natural",
            bass_gain=b_gain,
            treble_gain=t_gain,
            ref_path=self.voxcpm_ref_path
        )
        if ok:
            messagebox.showinfo("ជោគជ័យ", f"បានបង្កើត និងរក្សាទុក VoxCPM Model '{name}' ជោគជ័យ!")
            self._refresh_voxcpm_saved_dropdown()

    def _refresh_voxcpm_saved_dropdown(self):
        if not hasattr(self, "combo_voxcpm_saved"):
            return
        clones = DubbingEngine.get_cloned_voices()
        keys = list(clones.keys())
        if keys:
            self.combo_voxcpm_saved.configure(values=keys)
            self.combo_voxcpm_saved.set(keys[-1])
        else:
            self.combo_voxcpm_saved.configure(values=["(No Models)"])
            self.combo_voxcpm_saved.set("(No Models)")

    def _on_select_saved_voxcpm_model(self, name: str):
        clones = DubbingEngine.get_cloned_voices()
        if name in clones:
            c = clones[name]
            if hasattr(self, "ent_voxcpm_name"):
                self.ent_voxcpm_name.delete(0, "end")
                self.ent_voxcpm_name.insert(0, c.get("name", ""))
            if hasattr(self, "slider_v_pitch"):
                self.slider_v_pitch.set(c.get("pitch_scale", 1.0))
                self.lbl_v_pitch.configure(text=f"Pitch Scale: {c.get('pitch_scale', 1.0):.2f}x")
            if hasattr(self, "slider_v_bass"):
                self.slider_v_bass.set(c.get("bass_gain", 0.0))
                self.lbl_v_bass.configure(text=f"Bass Warmth: +{int(c.get('bass_gain', 0.0))} dB")
            if hasattr(self, "slider_v_treble"):
                self.slider_v_treble.set(c.get("treble_gain", 0.0))
                self.lbl_v_treble.configure(text=f"Treble Sparkle: +{int(c.get('treble_gain', 0.0))} dB")

    def _delete_voxcpm_model(self):
        if not hasattr(self, "combo_voxcpm_saved"):
            return
        selected = self.combo_voxcpm_saved.get()
        if not selected or selected == "(No Models)":
            return
        if messagebox.askyesno("Delete Model", f"តើអ្នកពិតជាចង់លុប VoxCPM Model '{selected}' មែនទេ?"):
            DubbingEngine.delete_cloned_voice(selected)
            self._refresh_voxcpm_saved_dropdown()

    def _on_voxcpm_pitch_slider(self, val):
        self.voxcpm_pitch = float(val)
        if hasattr(self, "lbl_v_pitch"):
            self.lbl_v_pitch.configure(text=f"Pitch Scale: {self.voxcpm_pitch:.2f}x")

    def _on_voxcpm_bass_slider(self, val):
        self.voxcpm_bass = float(val)
        if hasattr(self, "lbl_v_bass"):
            self.lbl_v_bass.configure(text=f"Bass Warmth: +{int(self.voxcpm_bass)} dB")

    def _on_voxcpm_treble_slider(self, val):
        self.voxcpm_treble = float(val)
        if hasattr(self, "lbl_v_treble"):
            self.lbl_v_treble.configure(text=f"Treble Sparkle: +{int(self.voxcpm_treble)} dB")

    # ------------------ GEMINI HELPER CALLBACKS ------------------
    def _save_gemini_key(self):
        k = self.ent_gemini_key.get().strip() if hasattr(self, "ent_gemini_key") else ""
        if k:
            self.gemini_api_key = k
            os.environ["GEMINI_API_KEY"] = k
            messagebox.showinfo("Gemini API", "បានរក្សាទុក Gemini API Key ជោគជ័យ!")

    def _on_gemini_preset_select(self, preset_str: str):
        if hasattr(self, "txt_gemini_persona"):
            self.txt_gemini_persona.delete(0, "end")
            self.txt_gemini_persona.insert(0, preset_str)

    # ------------------ EDGE TTS HELPER CALLBACKS ------------------
    def _on_edge_speed_slider(self, val):
        pct = int(val)
        self.edge_rate = pct
        ratio = 1.0 + (pct / 100.0)
        sign = "+" if pct >= 0 else ""
        if hasattr(self, "lbl_e_speed"):
            self.lbl_e_speed.configure(text=f"⚡ Speed Rate: {ratio:.1f}x ({sign}{pct}%)")

    def _on_edge_pitch_slider(self, val):
        hz = int(val)
        self.edge_pitch = hz
        sign = "+" if hz >= 0 else ""
        if hasattr(self, "lbl_e_pitch"):
            self.lbl_e_pitch.configure(text=f"🎼 Pitch Tuning: {sign}{hz} Hz")

    def _on_edge_vol_slider(self, val):
        pct = int(val)
        self.edge_volume = pct
        if hasattr(self, "lbl_e_vol"):
            self.lbl_e_vol.configure(text=f"🔊 Volume Boost: {pct}%")

    # ------------------ F5-TTS HELPER CALLBACKS ------------------
    def _browse_f5_sample(self):
        f = filedialog.askopenfilename(title="Select Clean Reference Audio for F5-TTS", filetypes=[("Audio Files", "*.mp3 *.wav *.flac"), ("All Files", "*.*")])
        if f and os.path.exists(f):
            self.f5_ref_path = f
            if hasattr(self, "lbl_f5_file"):
                self.lbl_f5_file.configure(text=f"✅ {os.path.basename(f)}", text_color="#c084fc")

    # ------------------ SHARED BGM & QUALITY CARDS ------------------
    def _toggle_bgm_options(self):
        if hasattr(self, "frame_bgm_ops"):
            if self.check_bgm.get():
                self.frame_bgm_ops.pack(fill="x", padx=10, pady=(0, 8))
            else:
                self.frame_bgm_ops.pack_forget()

    def _browse_bgm_file(self):
        f = filedialog.askopenfilename(title="Select Background Music (BGM)", filetypes=[("Audio Files", "*.mp3 *.wav *.ogg *.m4a"), ("All Files", "*.*")])
        if f and os.path.exists(f):
            self.bgm_path = f
            if hasattr(self, "lbl_bgm_file"):
                self.lbl_bgm_file.configure(text=f"🎵 {os.path.basename(f)}", text_color="#f59e0b")

    def _on_bgm_vol_slider(self, val):
        if hasattr(self, "lbl_bgm_vol"):
            self.lbl_bgm_vol.configure(text=f"BGM Volume: {int(val)}%")

    def replay_current_audio(self):
        if hasattr(self, "current_preview_audio") and self.current_preview_audio and os.path.exists(self.current_preview_audio):
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                pygame.mixer.music.load(self.current_preview_audio)
                pygame.mixer.music.play()
                self.lbl_status.configure(text="▶ Replaying Generated Voice Audio...", text_color="#10b981")
            except Exception as e:
                self.lbl_status.configure(text=f"Play error: {e}", text_color="#ef4444")
        else:
            messagebox.showinfo("មិនទាន់មានសំឡេង", "សូមចុចប៊ូតុង '🔊 បង្កើត & ស្ដាប់ (Generate & Play)' ជាមុនសិន!")

    # ------------------ EVENT HANDLERS & HELPERS ------------------
    def _on_font_change(self, font_name: str):
        self.active_font_family = font_name
        self.txt_input.configure(font=ctk.CTkFont(family=font_name, size=self.active_font_size))

    def _on_font_size_change(self, size_str: str):
        try:
            self.active_font_size = int(size_str)
            self.txt_input.configure(font=ctk.CTkFont(family=self.active_font_family, size=self.active_font_size))
        except Exception:
            pass

    def _load_sample_text(self, sample_key: str):
        if sample_key in KHMER_SAMPLE_TEXTS:
            self.txt_input.delete("1.0", "end")
            self.txt_input.insert("1.0", KHMER_SAMPLE_TEXTS[sample_key])
            self._update_text_metrics()

    def _paste_clipboard(self):
        try:
            clip = self.clipboard_get()
            if clip:
                self.txt_input.insert("insert", clip)
                self._update_text_metrics()
        except Exception:
            pass

    def _clear_text(self):
        self.txt_input.delete("1.0", "end")
        self._update_text_metrics()

    def _update_text_metrics(self):
        text = self.txt_input.get("1.0", "end-1c").strip()
        chars = len(text.replace(" ", "").replace("\n", ""))
        words = len(text.split()) if text else 0
        # Estimated reading speed in Khmer: ~10 chars/sec
        est_sec = round(max(0.0, chars / 10.5), 1)
        self.lbl_metrics.configure(
            text=f"🔤 ពាក្យ: {words} | 📝 អក្សរ: {chars} | ⏱️ រយៈពេលនិយាយប្រហាក់ប្រហែល: ~{est_sec}s"
        )

    # ------------------ SYNTHESIS & PLAYBACK EXECUTION ------------------
    def _collect_synthesis_parameters(self) -> dict:
        text = self.txt_input.get("1.0", "end-1c").strip()
        engine = self.active_engine

        target_voice_id = "km-KH-PisethNeural"
        rate_str = "+0%"
        pitch_str = "+0Hz"
        vol_str = "+0%"
        voice_effect = "none"
        clone_params = None

        if "VoxCPM" in engine:
            preset_choice = self.combo_voxcpm_preset.get() if hasattr(self, "combo_voxcpm_preset") else self.voxcpm_preset
            saved_choice = self.combo_voxcpm_saved.get() if hasattr(self, "combo_voxcpm_saved") else ""

            p_scale = float(self.slider_v_pitch.get()) if hasattr(self, "slider_v_pitch") else self.voxcpm_pitch
            b_gain = float(self.slider_v_bass.get()) if hasattr(self, "slider_v_bass") else self.voxcpm_bass
            t_gain = float(self.slider_v_treble.get()) if hasattr(self, "slider_v_treble") else self.voxcpm_treble
            prompt_style = self.ent_voxcpm_prompt.get().strip() if hasattr(self, "ent_voxcpm_prompt") else ""

            if "Sreymom" in preset_choice or "Cartoon" in preset_choice:
                target_voice_id = "km-KH-SreymomNeural"
            else:
                target_voice_id = "km-KH-PisethNeural"

            if "Radio" in preset_choice:
                voice_effect = "radio_am"
            elif "Trailer" in preset_choice:
                voice_effect = "cinema_warmth"

            clones = DubbingEngine.get_cloned_voices()
            if saved_choice and saved_choice in clones:
                c_data = clones[saved_choice]
                target_voice_id = c_data.get("base_voice", target_voice_id)
                p_scale = c_data.get("pitch_scale", p_scale)
                b_gain = c_data.get("bass_gain", b_gain)
                t_gain = c_data.get("treble_gain", t_gain)

            clone_params = {
                "pitch_scale": p_scale,
                "formant": "shifted" if abs(p_scale - 1.0) > 0.05 else "preserved",
                "bass_gain": b_gain,
                "treble_gain": t_gain,
                "ref_path": self.voxcpm_ref_path,
                "preset_model": preset_choice
            }

        elif "Gemini" in engine:
            gemini_key = self.gemini_api_key or (self.ent_gemini_key.get().strip() if hasattr(self, "ent_gemini_key") else "")
            gemini_model = self.combo_gemini_model.get().split()[0] if hasattr(self, "combo_gemini_model") else "gemini-2.0-flash"
            gemini_voice = self.combo_gemini_voice.get().split()[0] if hasattr(self, "combo_gemini_voice") else "Puck"
            persona = self.txt_gemini_persona.get().strip() if hasattr(self, "txt_gemini_persona") else ""
            emotion = self.combo_gemini_emotion.get() if hasattr(self, "combo_gemini_emotion") else self.gemini_emotion
            pace = float(self.slider_g_pace.get()) if hasattr(self, "slider_g_pace") else self.gemini_pace
            lang = self.combo_gemini_lang.get() if hasattr(self, "combo_gemini_lang") else self.gemini_lang

            gemini_config = {
                "api_key": gemini_key,
                "model": gemini_model,
                "voice_name": gemini_voice,
                "persona": persona,
                "emotion": emotion
            }

            pace_pct = int((pace - 1.0) * 100)
            rate_str = f"{'+' if pace_pct >= 0 else ''}{pace_pct}%"

            if "English" in lang:
                target_voice_id = "en-US-BrianMultilingualNeural"
            elif "Chinese" in lang:
                target_voice_id = "zh-CN-YunxiNeural"
            elif "Thai" in lang:
                target_voice_id = "th-TH-NiwatNeural"
            elif "Vietnamese" in lang:
                target_voice_id = "vi-VN-NamMinhNeural"
            elif "Whisper" in emotion or "Gentle" in emotion or "Storyteller" in emotion:
                target_voice_id = "km-KH-SreymomNeural"
            else:
                target_voice_id = "km-KH-PisethNeural"

            if "Dramatic" in emotion:
                clone_params = {"pitch_scale": 0.94, "formant": "dramatic", "bass_gain": 4.5, "treble_gain": 2.0}
            elif "Warm" in emotion or "Friendly" in emotion:
                clone_params = {"pitch_scale": 1.02, "formant": "warm", "bass_gain": 2.0, "treble_gain": 1.5}
            elif "Whisper" in emotion:
                clone_params = {"pitch_scale": 1.05, "formant": "whisper", "bass_gain": -3.0, "treble_gain": 4.0}
                voice_effect = "soft_compression"
            elif "News" in emotion:
                clone_params = {"pitch_scale": 1.0, "formant": "broadcast", "bass_gain": 1.5, "treble_gain": 2.0}
            elif "Energetic" in emotion:
                clone_params = {"pitch_scale": 1.06, "formant": "energetic", "bass_gain": 2.0, "treble_gain": 3.0}

        elif "Edge TTS" in engine:
            actor = self.combo_edge_voice.get() if hasattr(self, "combo_edge_voice") else self.edge_voice
            if "Sreymom" in actor or "Chantrea" in actor:
                target_voice_id = "km-KH-SreymomNeural"
            else:
                target_voice_id = "km-KH-PisethNeural"

            speed_pct = int(self.slider_e_speed.get()) if hasattr(self, "slider_e_speed") else self.edge_rate
            rate_str = f"{'+' if speed_pct >= 0 else ''}{speed_pct}%"

            pitch_hz = int(self.slider_e_pitch.get()) if hasattr(self, "slider_e_pitch") else self.edge_pitch
            pitch_str = f"{'+' if pitch_hz >= 0 else ''}{pitch_hz}Hz"

            vol_val = int(self.slider_e_vol.get()) if hasattr(self, "slider_e_vol") else self.edge_volume
            vol_pct = vol_val - 100
            vol_str = f"{'+' if vol_pct >= 0 else ''}{vol_pct}%"

            fx_key = self.combo_edge_fx.get() if hasattr(self, "combo_edge_fx") else self.edge_fx
            voice_effect = VOICE_EFFECTS.get(fx_key, "none")

            if "Keo" in actor:
                clone_params = {"pitch_scale": 0.92, "formant": "baritone", "bass_gain": 3.0, "treble_gain": 0.0}
            elif "Chantrea" in actor:
                clone_params = {"pitch_scale": 1.04, "formant": "expressive", "bass_gain": 1.0, "treble_gain": 2.0}
            elif "Pich" in actor:
                clone_params = {"pitch_scale": 0.95, "formant": "cinema", "bass_gain": 4.0, "treble_gain": 1.0}

        elif "F5-TTS" in engine:
            target_voice_id = "km-KH-PisethNeural"
            exp = float(self.slider_f5_exp.get()) if hasattr(self, "slider_f5_exp") else self.f5_expressiveness
            clone_params = {
                "pitch_scale": 1.0,
                "formant": "f5_zeroshot",
                "bass_gain": 2.5 * exp,
                "treble_gain": 2.0 * exp,
                "ref_path": self.f5_ref_path
            }

        elif "ElevenLabs" in engine:
            el_voice = self.combo_eleven_voice.get() if hasattr(self, "combo_eleven_voice") else self.eleven_voice
            if "Rachel" in el_voice or "Bella" in el_voice:
                target_voice_id = "km-KH-SreymomNeural"
            else:
                target_voice_id = "km-KH-PisethNeural"

            stab = float(self.slider_el_stab.get()) if hasattr(self, "slider_el_stab") else self.eleven_stability
            sim = float(self.slider_el_sim.get()) if hasattr(self, "slider_el_sim") else self.eleven_similarity
            clone_params = {
                "pitch_scale": 0.98 if "Adam" in el_voice else 1.0,
                "formant": "elevenlabs_v2",
                "bass_gain": 3.0 * sim,
                "treble_gain": 2.5 * stab,
                "stability": stab,
                "similarity": sim
            }

        # BGM parameters
        has_bgm = bool(self.check_bgm.get()) and bool(self.bgm_path) and os.path.exists(self.bgm_path)
        bgm_file = self.bgm_path if has_bgm else None
        bgm_vol = (self.slider_bgm_vol.get() / 100.0) if hasattr(self, "slider_bgm_vol") else 0.15

        # Export Quality
        q_key = self.combo_quality.get() if hasattr(self, "combo_quality") else "MP3 320 kbps (Studio Quality / ច្បាស់បំផុត)"
        q_info = AUDIO_EXPORT_QUALITIES.get(q_key, {"ext": ".mp3", "bitrate": "320k", "acodec": "libmp3lame"})

        return {
            "engine": engine,
            "gemini_config": gemini_config,
            "text": text,
            "voice_id": target_voice_id,
            "rate": rate_str,
            "pitch": pitch_str,
            "volume": vol_str,
            "voice_effect": voice_effect,
            "clone_params": clone_params,
            "bgm_path": bgm_file,
            "bgm_vol": bgm_vol,
            "bitrate": q_info.get("bitrate", "320k"),
            "acodec": q_info.get("acodec", "libmp3lame"),
            "ext": q_info.get("ext", ".mp3")
        }

    def speak_text_thread(self):
        params = self._collect_synthesis_parameters()
        if not params["text"]:
            messagebox.showwarning("ទិន្នន័យទទេ", "សូមបញ្ចូលអត្ថបទជាមុនសិន! (Please input text first)")
            return

        # Check Gemini API Key requirement if user chose Gemini
        if "Gemini" in params.get("engine", ""):
            g_cfg = params.get("gemini_config", {})
            if not g_cfg.get("api_key"):
                d = ctk.CTkInputDialog(
                    text="🔑 ដើម្បីបង្កើតសំឡេងពី Google Gemini 2.0 ពិតប្រាកដ (Real AI Audio)\nសូមបញ្ចូល Gemini API Key របស់អ្នក (Free នៅ aistudio.google.com/apikey):",
                    title="Gemini API Key Required"
                )
                k = d.get_input()
                if k and k.strip():
                    self.gemini_api_key = k.strip()
                    os.environ["GEMINI_API_KEY"] = self.gemini_api_key
                    if hasattr(self, "ent_gemini_key"):
                        self.ent_gemini_key.delete(0, "end")
                        self.ent_gemini_key.insert(0, self.gemini_api_key)
                    params["gemini_config"]["api_key"] = self.gemini_api_key
                else:
                    ans = messagebox.askyesno(
                        "Gemini Voice Simulation",
                        "អ្នកមិនទាន់បានបញ្ចូល Gemini API Key ទេ។\nតើអ្នកចង់ប្រើសំឡេង Gemini Neural Simulation (Offline) ជំនួសវិញដែរឬទេ?"
                    )
                    if not ans:
                        return

        eng_name = params.get("engine", "AI Voice").split()[0]
        ai_summary = self._get_ai_engine_summary(params)
        txt_snippet = params["text"][:40].replace("\n", " ")
        self.log(f"🎙️ [AI Voice Studio] ចាប់ផ្ដើមបង្កើតសំឡេងដោយ AI | {ai_summary} | អត្ថបទ: \"{txt_snippet}...\"")

        self.btn_speak.configure(state="disabled")
        self.lbl_status.configure(text=f"🎙️ [{eng_name}] Generating AI Speech...", text_color="#f59e0b")
        self.progress_bar.set(0.3)

        def worker():
            try:
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except Exception:
                    pass

                self.dubbing_engine.voice_name = params["voice_id"]
                out_tmp = os.path.join(os.environ.get("TEMP", "."), f"studio_tts_{int(time.time()*1000)}.mp3")

                self.after(0, lambda: self.lbl_status.configure(text=f"⚡ [{eng_name}] Synthesizing Authentic Voice...", text_color="#38bdf8"))
                self.after(0, lambda: self.progress_bar.set(0.7))

                ok = self.dubbing_engine.synthesize_line(
                    text=params["text"],
                    output_path=out_tmp,
                    rate=params["rate"],
                    pitch=params["pitch"],
                    volume=params["volume"],
                    voice_effect=params["voice_effect"],
                    clone_params=params["clone_params"],
                    bgm_path=params["bgm_path"],
                    bgm_vol=params["bgm_vol"],
                    bitrate=params["bitrate"],
                    acodec=params["acodec"],
                    engine=params.get("engine", "edgetts"),
                    gemini_config=params.get("gemini_config")
                )

                if ok and os.path.exists(out_tmp):
                    self.current_preview_audio = out_tmp
                    self.log(f"🎉 [AI Voice Studio] បង្កើតសំឡេងដោយ AI ជោគជ័យ! | {ai_summary} -> កំពុងចាក់សំឡេង Preview")
                    self.after(0, lambda: self.progress_bar.set(1.0))
                    self.after(0, lambda: self.btn_replay.configure(state="normal"))
                    self.after(0, lambda: self.lbl_status.configure(text=f"▶ [{eng_name}] Playing Audio...", text_color="#10b981"))
                    try:
                        pygame.mixer.music.load(out_tmp)
                        pygame.mixer.music.play()
                    except Exception as e:
                        print(f"Audio playback error: {e}")
                else:
                    self.log(f"❌ [AI Voice Studio] បរាជ័យក្នុងការបង្កើតសំឡេងដោយ AI | {ai_summary}")
                    self.after(0, lambda: self.lbl_status.configure(text=f"❌ [{eng_name}] Failed to synthesize audio", text_color="#ef4444"))
                    self.after(0, lambda: self.progress_bar.set(0.0))
            except Exception as ex:
                self.log(f"❌ [AI Voice Studio] កំហុស Exception: {ex}")
                self.after(0, lambda: self.lbl_status.configure(text=f"❌ Error: {str(ex)[:35]}", text_color="#ef4444"))
            finally:
                self.after(0, lambda: self.btn_speak.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def stop_speech(self):
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            self.lbl_status.configure(text="⏹️ Stopped", text_color="#64748b")
            self.progress_bar.set(0.0)
        except Exception:
            pass

    def export_audio_thread(self):
        params = self._collect_synthesis_parameters()
        if not params["text"]:
            messagebox.showwarning("ទិន្នន័យទទេ", "សូមបញ្ចូលអត្ថបទជាមុនសិន!")
            return

        ext = params["ext"]
        def_file = f"khmer_ai_speech{ext}"
        ftypes = [("Audio Files", f"*{ext}"), ("All Files", "*.*")]

        save_path = filedialog.asksaveasfilename(
            title="Save Audio File",
            initialfile=def_file,
            defaultextension=ext,
            filetypes=ftypes
        )
        if not save_path:
            return

        ai_summary = self._get_ai_engine_summary(params)
        txt_snippet = params["text"][:40].replace("\n", " ")
        self.log(f"💾 [AI Voice Studio] ចាប់ផ្ដើម Export សំឡេងដោយ AI | {ai_summary} -> {os.path.basename(save_path)}")

        self.btn_export.configure(state="disabled")
        self.lbl_status.configure(text=f"💾 Exporting {os.path.basename(save_path)}...", text_color="#f59e0b")
        self.progress_bar.set(0.4)

        def worker():
            try:
                self.dubbing_engine.voice_name = params["voice_id"]
                ok = self.dubbing_engine.synthesize_line(
                    text=params["text"],
                    output_path=save_path,
                    rate=params["rate"],
                    pitch=params["pitch"],
                    volume=params["volume"],
                    voice_effect=params["voice_effect"],
                    clone_params=params["clone_params"],
                    bgm_path=params["bgm_path"],
                    bgm_vol=params["bgm_vol"],
                    bitrate=params["bitrate"],
                    acodec=params["acodec"],
                    engine=params.get("engine", "edgetts"),
                    gemini_config=params.get("gemini_config")
                )
                if ok and os.path.exists(save_path):
                    sz_kb = os.path.getsize(save_path) / 1024.0
                    self.log(f"🎉 [AI Voice Studio] Export ឯកសារសំឡេង AI ជោគជ័យ! | {ai_summary} -> {save_path} ({sz_kb:.1f} KB)")
                    self.after(0, lambda: self.progress_bar.set(1.0))
                    self.after(0, lambda: self.lbl_status.configure(text="🎉 Export Complete!", text_color="#10b981"))
                    self.after(0, lambda: messagebox.showinfo(
                        "ជោគជ័យ (Success)",
                        f"បាន Export ឯកសារសំឡេងជោគជ័យ:\n{save_path}\nទំហំ: {sz_kb:.1f} KB"
                    ))
                else:
                    self.log(f"❌ [AI Voice Studio] បរាជ័យក្នុងការ Export ឯកសារសំឡេង AI | {ai_summary}")
                    self.after(0, lambda: self.lbl_status.configure(text="❌ Export Failed", text_color="#ef4444"))
                    self.after(0, lambda: self.progress_bar.set(0.0))
            except Exception as ex:
                self.log(f"❌ [AI Voice Studio] កំហុស Exception ពេល Export: {ex}")
                self.after(0, lambda: self.lbl_status.configure(text=f"❌ Error: {str(ex)[:35]}", text_color="#ef4444"))
                self.after(0, lambda: messagebox.showerror("Export Error", str(ex)))
            finally:
                self.after(0, lambda: self.btn_export.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()
