import os
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from config import (
    KHMER_VOICES,
    SUBTITLE_COLORS,
    SPEECH_SPEED_PRESETS,
    EXPORT_RESOLUTIONS,
    EXPORT_FPS,
    EXPORT_FORMATS,
    EXPORT_QUALITY,
    WATERMARK_POSITIONS,
    get_installed_khmer_fonts,
    KHMER_FONT_FAMILY,
    CC_ANIMATION_PRESETS,
    CC_BG_STYLES,
    CC_BORDER_PRESETS,
    CC_HIGHLIGHT_COLORS
)

class DubbingExportView(ctk.CTkScrollableFrame):
    """
    Right Pane: Khmer Dubbing Studio & Master Video Composition Exporter
    - Full Khmer font selector supporting all fonts installed on Windows PC
    - CC Animation & Karaoke presets (Active Word Highlight, Popup, Fade, Slide, Bounce)
    - Non-linear multi-track audio mix (Video, Khmer Dub, BGM) with volume & mute
    - Real-time video effects & color grading (Brightness, Contrast, Saturation)
    - Watermark logo / GFX overlay placement & scaling
    - Master Export: MP4 / WebM, 720p / 1080p / 4K, 24 / 30 / 60 FPS, CRF quality
    """
    def __init__(
        self,
        parent,
        on_generate_dub,
        on_open_voices,
        on_export_srt,
        on_burn_video,
        on_export_all,
        on_font_change=None,
        on_filter_change=None,
        on_watermark_change=None,
        on_bg_music_browse=None,
        on_audio_mix_change=None,
        on_cc_style_change=None
    ):
        super().__init__(parent, fg_color="#14161b", corner_radius=0)
        self.on_generate_dub = on_generate_dub
        self.on_open_voices = on_open_voices
        self.on_export_srt = on_export_srt
        self.on_burn_video = on_burn_video
        self.on_export_all = on_export_all
        self.on_font_change = on_font_change
        self.on_filter_change = on_filter_change
        self.on_watermark_change = on_watermark_change
        self.on_bg_music_browse = on_bg_music_browse
        self.on_audio_mix_change = on_audio_mix_change
        self.on_cc_style_change = on_cc_style_change

        self.watermark_path = None
        self.watermark_rel_x = 0.90
        self.watermark_rel_y = 0.10
        self.bg_music_path = None

        self._build_ui()

    def _build_ui(self):
        # ========================================================
        # 1. KHMER DUBBING & AUDIO MIX CARD
        # ========================================================
        tts_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        tts_card.pack(fill="x", padx=4, pady=4)

        # Hidden widget bindings preserved so backend logic remains 100% compatible
        self.combo_voice = ctk.CTkComboBox(self, values=list(KHMER_VOICES.keys()))
        self.combo_voice.set("Piseth (Male / ប្រុស)")
        self.combo_speed = ctk.CTkComboBox(self, values=list(SPEECH_SPEED_PRESETS.keys()))
        self.combo_speed.set("1.1x (+10%)")
        self.btn_dub = ctk.CTkButton(self, text="🎧 Generate Voices", command=self.on_generate_dub if hasattr(self, "on_generate_dub") else None)
        self.btn_open_folder = ctk.CTkButton(self, text="📂 Open Voice Files Folder", command=self.on_open_voices if hasattr(self, "on_open_voices") else None)

        # Audio Track Mixers (Video, Dub, BGM)
        mix_title = ctk.CTkLabel(tts_card, text="🎚️ AUDIO TRACKS VOLUME & MUTE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#10b981")
        mix_title.pack(anchor="w", padx=8, pady=(6, 4))

        # Smart Auto-Ducking Checkbox (Auto-lower original audio during speech, auto-raise during silence)
        self.check_auto_ducking = ctk.CTkCheckBox(
            tts_card,
            text="🦆 Auto-Ducking (បន្ថយសំឡេងដើមពេលនិយាយ)",
            corner_radius=0,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#38bdf8",
            command=self._on_audio_slider_change
        )
        self.check_auto_ducking.select()
        self.check_auto_ducking.pack(anchor="w", padx=8, pady=(2, 4))

        # Original Video Audio Volume + Mute
        row_v = ctk.CTkFrame(tts_card, fg_color="transparent")
        row_v.pack(fill="x", padx=8, pady=1)
        ctk.CTkLabel(row_v, text="🎬 Video Audio (ពេលមិននិយាយ):", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left")
        self.check_mute_orig = ctk.CTkCheckBox(row_v, text="Mute", width=45, height=18, font=ctk.CTkFont(size=9), corner_radius=0, command=self._on_audio_slider_change)
        self.check_mute_orig.pack(side="right")
        self.slider_orig_vol = ctk.CTkSlider(tts_card, from_=0.0, to=1.0, number_of_steps=20, height=14, corner_radius=0, command=self._on_audio_slider_change)
        self.slider_orig_vol.set(0.85)
        self.slider_orig_vol.pack(fill="x", padx=8, pady=(0, 4))

        # Khmer Dub Volume + Mute
        row_d = ctk.CTkFrame(tts_card, fg_color="transparent")
        row_d.pack(fill="x", padx=8, pady=1)
        ctk.CTkLabel(row_d, text="🎙️ Khmer Dub:", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left")
        self.check_mute_dub = ctk.CTkCheckBox(row_d, text="Mute", width=45, height=18, font=ctk.CTkFont(size=9), corner_radius=0, command=self._on_audio_slider_change)
        self.check_mute_dub.pack(side="right")
        self.slider_dub_vol = ctk.CTkSlider(tts_card, from_=0.0, to=1.5, number_of_steps=20, height=14, corner_radius=0, command=self._on_audio_slider_change)
        self.slider_dub_vol.set(1.0)
        self.slider_dub_vol.pack(fill="x", padx=8, pady=(0, 4))

        # BGM Music Volume + Browse + Mute
        row_m = ctk.CTkFrame(tts_card, fg_color="transparent")
        row_m.pack(fill="x", padx=8, pady=1)
        ctk.CTkLabel(row_m, text="🎵 BGM Music:", font=ctk.CTkFont(size=9), text_color="#f59e0b").pack(side="left")
        self.check_mute_bgm = ctk.CTkCheckBox(row_m, text="Mute", width=45, height=18, font=ctk.CTkFont(size=9), corner_radius=0, command=self._on_audio_slider_change)
        self.check_mute_bgm.pack(side="right")

        self.btn_browse_bgm = ctk.CTkButton(
            tts_card,
            text="📁 Browse Music (MP3/WAV)",
            command=self._browse_bg_music,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=22,
            font=ctk.CTkFont(size=9)
        )
        self.btn_browse_bgm.pack(fill="x", padx=8, pady=(1, 2))

        self.slider_bgm_vol = ctk.CTkSlider(tts_card, from_=0.0, to=1.0, number_of_steps=20, height=14, corner_radius=0, command=self._on_audio_slider_change)
        self.slider_bgm_vol.set(0.35)
        self.slider_bgm_vol.pack(fill="x", padx=8, pady=(0, 8))

        # ========================================================
        # 2. KHMER FONT & CC STYLE CARD (Universal Khmer Font Picker)
        # ========================================================
        font_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        font_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(
            font_card,
            text="✍️ KHMER FONT & CC STYLE",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ec4899"
        ).pack(anchor="w", padx=8, pady=(6, 2))

        # Khmer Font Dropdown (All installed fonts)
        ctk.CTkLabel(font_card, text="ពុម្ពអក្សរខ្មែរ (Khmer Font Family):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        installed_fonts = get_installed_khmer_fonts()
        self.combo_font = ctk.CTkComboBox(
            font_card,
            values=installed_fonts,
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(family=KHMER_FONT_FAMILY, size=11),
            command=self._on_font_select
        )
        self.combo_font.set("Leelawadee UI")
        self.combo_font.pack(fill="x", padx=8, pady=(0, 4))

        # Subtitle Color
        ctk.CTkLabel(font_card, text="Subtitle Color:", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_color = ctk.CTkComboBox(font_card, values=list(SUBTITLE_COLORS.keys()), height=24, corner_radius=0, font=ctk.CTkFont(size=10))
        self.combo_color.set("White (ស)")
        self.combo_color.pack(fill="x", padx=8, pady=(0, 4))

        # Font Size Slider
        self.lbl_font_size_val = ctk.CTkLabel(font_card, text="Font Size: 18pt", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_font_size_val.pack(anchor="w", padx=8, pady=(2, 1))
        self.slider_font_size = ctk.CTkSlider(font_card, from_=14, to=40, number_of_steps=13, height=14, corner_radius=0, command=self._on_font_size_slider)
        self.slider_font_size.set(18)
        self.slider_font_size.pack(fill="x", padx=8, pady=(0, 4))

        # Dual CC Checkbox
        self.check_dual = ctk.CTkCheckBox(font_card, text="Dual CC (ខ្មែរ + ចិន/អង់គ្លេស)", corner_radius=0, font=ctk.CTkFont(size=10))
        self.check_dual.pack(anchor="w", padx=8, pady=(2, 8))

        # ========================================================
        # 2.5 CC ANIMATIONS & KARAOKE STYLING CARD
        # ========================================================
        anim_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        anim_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(
            anim_card,
            text="🌟 CC ANIMATION & KARAOKE (ចលនា & កាយ៉ាអូខេ)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=8, pady=(6, 2))

        # Animation Preset Dropdown
        ctk.CTkLabel(anim_card, text="Animation Preset (បែបផែនចលនា):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_anim = ctk.CTkComboBox(
            anim_card,
            values=CC_ANIMATION_PRESETS,
            height=26,
            corner_radius=0,
            font=ctk.CTkFont(size=10),
            command=self._on_cc_style_update
        )
        self.combo_anim.set("🎤 Karaoke (Active Word Highlight)")
        self.combo_anim.pack(fill="x", padx=8, pady=(0, 4))

        # Background Box Style Dropdown
        ctk.CTkLabel(anim_card, text="Background Box (ប្រអប់ផ្ទៃក្រោយ):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_bg_style = ctk.CTkComboBox(
            anim_card,
            values=list(CC_BG_STYLES.keys()),
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9),
            command=self._on_cc_style_update
        )
        self.combo_bg_style.set("Black Box 50% (ប្រអប់ខ្មៅស្រាល)")
        self.combo_bg_style.pack(fill="x", padx=8, pady=(0, 4))

        # Active Word Highlight Color Dropdown
        ctk.CTkLabel(anim_card, text="Highlight Color (ពណ៌លោតតាមពាក្យ):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_highlight = ctk.CTkComboBox(
            anim_card,
            values=list(CC_HIGHLIGHT_COLORS.keys()),
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9),
            command=self._on_cc_style_update
        )
        self.combo_highlight.set("Gold / Yellow (លឿងទុំ)")
        self.combo_highlight.pack(fill="x", padx=8, pady=(0, 4))

        # Border Outline Dropdown
        ctk.CTkLabel(anim_card, text="Border Outline (កម្រាស់ស៊ុមអក្សរ):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_border = ctk.CTkComboBox(
            anim_card,
            values=list(CC_BORDER_PRESETS.keys()),
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9),
            command=self._on_cc_style_update
        )
        self.combo_border.set("Medium Outline (3px)")
        self.combo_border.pack(fill="x", padx=8, pady=(0, 8))

        # ========================================================
        # 3. VIDEO EFFECTS, COLOR GRADING & WATERMARK CARD
        # ========================================================
        fx_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        fx_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(
            fx_card,
            text="🎨 EFFECTS, COLOR & WATERMARK",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f59e0b"
        ).pack(anchor="w", padx=8, pady=(6, 2))

        # Brightness Slider
        self.lbl_bright = ctk.CTkLabel(fx_card, text="Brightness (ពន្លឺ): 0.00", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_bright.pack(anchor="w", padx=8, pady=(2, 0))
        self.slider_bright = ctk.CTkSlider(fx_card, from_=-0.4, to=0.4, number_of_steps=20, height=12, corner_radius=0, command=self._on_filter_slider)
        self.slider_bright.set(0.0)
        self.slider_bright.pack(fill="x", padx=8, pady=(0, 3))

        # Contrast Slider
        self.lbl_contrast = ctk.CTkLabel(fx_card, text="Contrast (កម្រិតពណ៌): 1.00", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_contrast.pack(anchor="w", padx=8, pady=(1, 0))
        self.slider_contrast = ctk.CTkSlider(fx_card, from_=0.6, to=1.6, number_of_steps=20, height=12, corner_radius=0, command=self._on_filter_slider)
        self.slider_contrast.set(1.0)
        self.slider_contrast.pack(fill="x", padx=8, pady=(0, 3))

        # Saturation Slider
        self.lbl_sat = ctk.CTkLabel(fx_card, text="Saturation (កំហាប់ពណ៌): 1.00", font=ctk.CTkFont(size=9), text_color="#94a3b8")
        self.lbl_sat.pack(anchor="w", padx=8, pady=(1, 0))
        self.slider_sat = ctk.CTkSlider(fx_card, from_=0.0, to=2.0, number_of_steps=20, height=12, corner_radius=0, command=self._on_filter_slider)
        self.slider_sat.set(1.0)
        self.slider_sat.pack(fill="x", padx=8, pady=(0, 4))

        # Reset Effects Button
        btn_reset_fx = ctk.CTkButton(
            fx_card,
            text="🔄 Reset Color Grading",
            command=self._reset_color_filters,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=20,
            font=ctk.CTkFont(size=9)
        )
        btn_reset_fx.pack(fill="x", padx=8, pady=(1, 6))

        # Watermark / Logo / GFX Overlay Section
        ctk.CTkLabel(fx_card, text="🖼️ Watermark Logo / GFX Overlay:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", padx=8, pady=(3, 1))

        self.btn_browse_wm = ctk.CTkButton(
            fx_card,
            text="📁 Browse Logo (PNG/JPG)",
            command=self._browse_watermark,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=22,
            font=ctk.CTkFont(size=9)
        )
        self.btn_browse_wm.pack(fill="x", padx=8, pady=(1, 3))

        ctk.CTkLabel(fx_card, text="Position (ទីតាំង):", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(anchor="w", padx=8, pady=(1, 0))
        self.combo_wm_pos = ctk.CTkComboBox(
            fx_card,
            values=list(WATERMARK_POSITIONS.keys()),
            height=24,
            corner_radius=0,
            font=ctk.CTkFont(size=9),
            command=self._on_wm_pos_change
        )
        self.combo_wm_pos.set("Top-Right (លើ ស្ដាំ)")
        self.combo_wm_pos.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_wm_scale = ctk.CTkLabel(fx_card, text="Logo Scale (ទំហំ): 15%", font=ctk.CTkFont(size=9), text_color="#cbd5e1")
        self.lbl_wm_scale.pack(anchor="w", padx=8, pady=(1, 0))
        self.slider_wm_scale = ctk.CTkSlider(fx_card, from_=0.04, to=0.50, number_of_steps=23, height=12, corner_radius=0, command=self._on_wm_scale_slider)
        self.slider_wm_scale.set(0.15)
        self.slider_wm_scale.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_wm_opacity = ctk.CTkLabel(fx_card, text="Logo Opacity (ភាពថ្លា): 100%", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8")
        self.lbl_wm_opacity.pack(anchor="w", padx=8, pady=(1, 0))
        self.slider_wm_opacity = ctk.CTkSlider(fx_card, from_=0.10, to=1.0, number_of_steps=18, height=12, corner_radius=0, command=self._on_wm_opacity_slider)
        self.slider_wm_opacity.set(1.0)
        self.slider_wm_opacity.pack(fill="x", padx=8, pady=(0, 8))

        # ========================================================
        # 4. MASTER EXPORT CARD (Full HD, 4K, 60fps, WebM/MP4)
        # ========================================================
        exp_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        exp_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(
            exp_card,
            text="💾 MASTER VIDEO EXPORT",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8"
        ).pack(anchor="w", padx=8, pady=(6, 2))

        # Resolution Dropdown
        ctk.CTkLabel(exp_card, text="Resolution (ទំហំគុណភាព):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_res = ctk.CTkComboBox(exp_card, values=list(EXPORT_RESOLUTIONS.keys()), height=24, corner_radius=0, font=ctk.CTkFont(size=10))
        self.combo_res.set("1080p (Full HD - 1920x1080)")
        self.combo_res.pack(fill="x", padx=8, pady=(0, 4))

        # Frame Rate Dropdown
        ctk.CTkLabel(exp_card, text="Frame Rate (FPS):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_fps = ctk.CTkComboBox(exp_card, values=list(EXPORT_FPS.keys()), height=24, corner_radius=0, font=ctk.CTkFont(size=10))
        self.combo_fps.set("30 FPS (Standard)")
        self.combo_fps.pack(fill="x", padx=8, pady=(0, 4))

        # Format Dropdown (MP4 / WebM)
        ctk.CTkLabel(exp_card, text="Format (ប្រភេទឯកសារ):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_format = ctk.CTkComboBox(exp_card, values=EXPORT_FORMATS, height=24, corner_radius=0, font=ctk.CTkFont(size=10))
        self.combo_format.set("MP4 Video (.mp4)")
        self.combo_format.pack(fill="x", padx=8, pady=(0, 4))

        # Quality / CRF
        ctk.CTkLabel(exp_card, text="Quality (គុណភាព & ទំហំ file):", font=ctk.CTkFont(size=10)).pack(anchor="w", padx=8, pady=(2, 1))
        self.combo_quality = ctk.CTkComboBox(exp_card, values=list(EXPORT_QUALITY.keys()), height=24, corner_radius=0, font=ctk.CTkFont(size=10))
        self.combo_quality.set("Balanced (CRF 22)")
        self.combo_quality.pack(fill="x", padx=8, pady=(0, 4))

        # CC Inclusion in Exported Video (With CC vs Clean/No CC)
        ctk.CTkLabel(exp_card, text="ចំណងជើងរត់ CC ក្នុងវីដេអូ Export:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#f59e0b").pack(anchor="w", padx=8, pady=(4, 1))
        
        self.cc_export_mode = ctk.StringVar(value="with_cc")
        f_cc_mode = ctk.CTkFrame(exp_card, fg_color="transparent")
        f_cc_mode.pack(fill="x", padx=8, pady=(1, 6))

        self.radio_with_cc = ctk.CTkRadioButton(
            f_cc_mode,
            text="💬 With CC (មានអក្សររត់)",
            variable=self.cc_export_mode,
            value="with_cc",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#38bdf8",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_with_cc.pack(side="left", padx=(0, 10))

        self.radio_no_cc = ctk.CTkRadioButton(
            f_cc_mode,
            text="🚫 No CC (វីដេអូ Clean គ្មានអក្សរ)",
            variable=self.cc_export_mode,
            value="no_cc",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8",
            radiobutton_width=16,
            radiobutton_height=16
        )
        self.radio_no_cc.pack(side="left")

        # Export Buttons
        self.btn_export_all = ctk.CTkButton(
            exp_card,
            text="🎬 Export Master Movie (Full Composition)",
            command=self.on_export_all,
            fg_color="#b45309",
            hover_color="#92400e",
            corner_radius=0,
            height=30,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_export_all.pack(fill="x", padx=8, pady=(2, 3))

        self.btn_burn = ctk.CTkButton(
            exp_card,
            text="🎞️ Burn CC to MP4 Video",
            command=self.on_burn_video,
            fg_color="#be123c",
            hover_color="#9f1239",
            corner_radius=0,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_burn.pack(fill="x", padx=8, pady=2)

        self.btn_srt = ctk.CTkButton(
            exp_card,
            text="📄 Save .SRT Subtitles",
            command=self.on_export_srt,
            fg_color="#334155",
            hover_color="#475569",
            corner_radius=0,
            height=24,
            font=ctk.CTkFont(size=10)
        )
        self.btn_srt.pack(fill="x", padx=8, pady=(2, 8))

        # ========================================================
        # 5. STATUS & PROGRESS CARD
        # ========================================================
        prog_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        prog_card.pack(fill="x", padx=4, pady=4)

        ctk.CTkLabel(prog_card, text="Status:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd5e1").pack(anchor="w", padx=8, pady=(4, 1))
        self.progress_bar = ctk.CTkProgressBar(prog_card, progress_color="#10b981", corner_radius=0, height=8)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=8, pady=2)

        self.lbl_status = ctk.CTkLabel(prog_card, text="Ready", text_color="#10b981", wraplength=190, font=ctk.CTkFont(size=10))
        self.lbl_status.pack(anchor="w", padx=8, pady=(1, 6))

    # ------------------ EVENT HANDLERS ------------------
    def _on_font_select(self, font_name: str):
        if self.on_font_change:
            self.on_font_change(font_name)

    def _on_font_size_slider(self, val):
        sz = int(val)
        self.lbl_font_size_val.configure(text=f"Font Size: {sz}pt")

    def _on_filter_slider(self, _=None):
        b = round(self.slider_bright.get(), 2)
        c = round(self.slider_contrast.get(), 2)
        s = round(self.slider_sat.get(), 2)
        self.lbl_bright.configure(text=f"Brightness (ពន្លឺ): {b:+.2f}")
        self.lbl_contrast.configure(text=f"Contrast (កម្រិតពណ៌): {c:.2f}")
        self.lbl_sat.configure(text=f"Saturation (កំហាប់ពណ៌): {s:.2f}")
        if self.on_filter_change:
            self.on_filter_change(b, c, s)

    def _reset_color_filters(self):
        self.slider_bright.set(0.0)
        self.slider_contrast.set(1.0)
        self.slider_sat.set(1.0)
        self._on_filter_slider()

    def _browse_watermark(self):
        f = filedialog.askopenfilename(
            title="Select Logo / Watermark Image",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All Files", "*.*")]
        )
        if f:
            self.watermark_path = f
            self.btn_browse_wm.configure(text=f"✓ {os.path.basename(f)[:16]}")
            self._notify_watermark_change()

    def _on_wm_pos_change(self, _=None):
        self._notify_watermark_change()

    def _on_wm_scale_slider(self, val):
        pct = int(round(val * 100))
        self.lbl_wm_scale.configure(text=f"Logo Scale (ទំហំ): {pct}%")
        self._notify_watermark_change()

    def _on_wm_opacity_slider(self, val):
        pct = int(round(val * 100))
        self.lbl_wm_opacity.configure(text=f"Logo Opacity (ភាពថ្លា): {pct}%")
        self._notify_watermark_change()

    def _notify_watermark_change(self):
        if self.watermark_path and self.on_watermark_change:
            pos_key = self.combo_wm_pos.get()
            scale_val = round(self.slider_wm_scale.get(), 2)
            opacity_val = round(self.slider_wm_opacity.get(), 2)
            self.on_watermark_change(self.watermark_path, pos_key, scale_val, opacity_val, self.watermark_rel_x, self.watermark_rel_y)

    def sync_watermark_ui(self, scale: float, opacity: float, rel_x: float = None, rel_y: float = None):
        """Synchronizes UI sliders and labels when user moves or scales logo directly on video preview"""
        if rel_x is not None:
            self.watermark_rel_x = rel_x
        if rel_y is not None:
            self.watermark_rel_y = rel_y
        self.slider_wm_scale.set(scale)
        self.lbl_wm_scale.configure(text=f"Logo Scale (ទំហំ): {int(round(scale * 100))}%")
        self.slider_wm_opacity.set(opacity)
        self.lbl_wm_opacity.configure(text=f"Logo Opacity (ភាពថ្លា): {int(round(opacity * 100))}%")
        try:
            self.combo_wm_pos.set("Custom (អូសតាមចិត្ត / Drag & Drop)")
        except Exception:
            pass

    def _browse_bg_music(self):
        f = filedialog.askopenfilename(
            title="Select Background Music (BGM)",
            filetypes=[("Audio Files", "*.mp3;*.wav;*.m4a;*.aac;*.ogg"), ("All Files", "*.*")]
        )
        if f:
            self.bg_music_path = f
            self.btn_browse_bgm.configure(text=f"✓ {os.path.basename(f)[:16]}")
            if self.on_bg_music_browse:
                self.on_bg_music_browse(f)

    def _on_audio_slider_change(self, _=None):
        if self.on_audio_mix_change:
            self.on_audio_mix_change(self.get_audio_settings())

    def _on_cc_style_update(self, _=None):
        if self.on_cc_style_change:
            self.on_cc_style_change(self.get_cc_style_settings())

    # ------------------ SETTINGS GETTERS ------------------
    def get_cc_style_settings(self) -> dict:
        anim_str = self.combo_anim.get() if hasattr(self, 'combo_anim') else "🎤 Karaoke (Active Word Highlight)"
        code = "karaoke"
        if "Popup" in anim_str:
            code = "popup"
        elif "Fade" in anim_str:
            code = "fade"
        elif "Slide" in anim_str:
            code = "slide_up"
        elif "Bounce" in anim_str:
            code = "bounce"
        elif "Classic" in anim_str:
            code = "none"

        bg_key = self.combo_bg_style.get() if hasattr(self, 'combo_bg_style') else "Black Box 50% (ប្រអប់ខ្មៅស្រាល)"
        hi_key = self.combo_highlight.get() if hasattr(self, 'combo_highlight') else "Gold / Yellow (លឿងទុំ)"
        b_key = self.combo_border.get() if hasattr(self, 'combo_border') else "Medium Outline (3px)"

        from config import CC_BORDER_PRESETS, CC_HIGHLIGHT_COLORS
        return {
            "animation_display": anim_str,
            "animation_code": code,
            "bg_style": bg_key,
            "highlight_color": CC_HIGHLIGHT_COLORS.get(hi_key, {}).get("hex", "#facc15"),
            "highlight_ass": CC_HIGHLIGHT_COLORS.get(hi_key, {}).get("ass", "&H0000E6FF"),
            "border_width": CC_BORDER_PRESETS.get(b_key, 3)
        }

    def get_dubbing_settings(self) -> dict:
        color_name = self.combo_color.get()
        speed_choice = self.combo_speed.get() if hasattr(self, 'combo_speed') else "1.1x (+10%)"
        rate_code = SPEECH_SPEED_PRESETS.get(speed_choice, "+10%")
        font_name = self.combo_font.get() if hasattr(self, 'combo_font') else "Leelawadee UI"

        return {
            "voice_key": self.combo_voice.get(),
            "orig_vol": self.slider_orig_vol.get(),
            "dub_vol": self.slider_dub_vol.get(),
            "bgm_vol": self.slider_bgm_vol.get(),
            "auto_ducking": bool(self.check_auto_ducking.get()) if hasattr(self, "check_auto_ducking") else True,
            "duck_vol": 0.15,
            "mute_orig": bool(self.check_mute_orig.get()),
            "mute_dub": bool(self.check_mute_dub.get()),
            "mute_bgm": bool(self.check_mute_bgm.get()),
            "speed_rate": rate_code,
            "is_dual": bool(self.check_dual.get()),
            "font_name": font_name,
            "font_size": int(self.slider_font_size.get()),
            "color_code": SUBTITLE_COLORS.get(color_name, "&H00FFFFFF"),
            "burn_cc": (self.cc_export_mode.get() == "with_cc") if hasattr(self, "cc_export_mode") else True
        }

    def get_audio_settings(self) -> dict:
        return {
            "orig_vol": self.slider_orig_vol.get(),
            "mute_orig": bool(self.check_mute_orig.get()),
            "dub_vol": self.slider_dub_vol.get(),
            "mute_dub": bool(self.check_mute_dub.get()),
            "bgm_vol": self.slider_bgm_vol.get(),
            "mute_bgm": bool(self.check_mute_bgm.get()),
            "auto_ducking": bool(self.check_auto_ducking.get()) if hasattr(self, "check_auto_ducking") else True,
            "duck_vol": 0.15,
            "bg_music_path": self.bg_music_path
        }

    def get_filter_settings(self) -> dict:
        return {
            "brightness": round(self.slider_bright.get(), 2),
            "contrast": round(self.slider_contrast.get(), 2),
            "saturation": round(self.slider_sat.get(), 2),
            "speed": 1.0
        }

    def get_watermark_settings(self) -> dict:
        return {
            "path": self.watermark_path,
            "pos": self.combo_wm_pos.get(),
            "scale": round(self.slider_wm_scale.get(), 2),
            "opacity": round(self.slider_wm_opacity.get(), 2),
            "rel_x": getattr(self, "watermark_rel_x", None),
            "rel_y": getattr(self, "watermark_rel_y", None)
        }

    def get_master_export_settings(self) -> dict:
        res_key = self.combo_res.get()
        target_res = EXPORT_RESOLUTIONS.get(res_key, (1920, 1080))

        fps_key = self.combo_fps.get()
        target_fps = EXPORT_FPS.get(fps_key, 30)

        qual_key = self.combo_quality.get()
        crf_val = EXPORT_QUALITY.get(qual_key, "22")

        is_webm = "WebM" in self.combo_format.get()
        color_name = self.combo_color.get()
        cc_style = self.get_cc_style_settings()

        return {
            "resolution": target_res,
            "fps": target_fps,
            "quality": crf_val,
            "is_webm": is_webm,
            "font_name": self.combo_font.get(),
            "font_size": int(self.slider_font_size.get()),
            "font_color": SUBTITLE_COLORS.get(color_name, "&H00FFFFFF"),
            "is_dual": bool(self.check_dual.get()),
            "animation": cc_style["animation_code"],
            "bg_style": cc_style["bg_style"],
            "highlight_color": cc_style["highlight_ass"],
            "border_width": cc_style["border_width"],
            "burn_cc": (self.cc_export_mode.get() == "with_cc") if hasattr(self, "cc_export_mode") else True
        }

    def set_status(self, text: str, progress: float = None):
        self.lbl_status.configure(text=text)
        if progress is not None:
            self.progress_bar.set(progress)
