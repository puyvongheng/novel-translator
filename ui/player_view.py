import os
import time
import math
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk
from PIL import Image, ImageTk
import cv2
from config import (
    KHMER_FONT_FAMILY,
    WATERMARK_POSITIONS,
    CC_BG_STYLES,
    CC_ANIMATION_PRESETS,
    CC_HIGHLIGHT_COLORS,
    CC_BORDER_PRESETS,
    PREVIEW_ASPECT_RATIOS,
    get_installed_khmer_fonts
)
from utils import format_timestamp

class PlayerView(ctk.CTkFrame):
    """
    CapCut Professional Multi-Track Video Player & Non-Linear Timeline Studio:
    - Dynamic N Rows Audio Tracks (Audio 1, Audio 2, Audio 3... Audio N) with Volume & Mute
    - Dynamic N Rows CC Subtitle Tracks (CC 1, CC 2... CC N)
    - Aspect Ratio Video Preview Formats (16:9, 9:16 TikTok, 1:1 Instagram, 4:3, Auto)
    - Incremental Chunk Progress & Buffering State Indicators
    - Split, Trim, Delete, Add Music, Undo, Redo, Zoom
    """
    def __init__(
        self,
        parent,
        on_seek,
        on_toggle_play,
        on_seek_relative,
        on_select_sub=None,
        on_move_sub_timing=None,
        on_commit_sub_timing=None,
        on_split_clip=None,
        on_trim_clip=None,
        on_delete_clip=None,
        on_add_clip=None,
        on_add_music=None,
        on_undo=None,
        on_redo=None,
        on_add_cc_track=None,
        on_add_audio_track=None,
        on_toggle_audio_mute=None,
        on_retry_chunk=None,
        on_apply_edit=None,
        on_auto_sync_speed=None,
        on_duplicate_sub=None,
        on_delete_sub=None,
        on_audition_sub=None,
        on_watermark_move_or_scale=None,
        on_toggle_inspector=None,
        on_auto_pipeline=None,
        on_batch_open=None,
        on_speed_change=None,
        on_fps_change=None,
        on_volume_change=None,
        on_object_selected=None,
        timeline_parent=None
    ):
        super().__init__(parent, fg_color="#14161b", corner_radius=0)
        self.on_seek = on_seek
        self.on_toggle_play = on_toggle_play
        self.on_seek_relative = on_seek_relative
        self.on_select_sub = on_select_sub
        self.on_move_sub_timing = on_move_sub_timing
        self.on_commit_sub_timing = on_commit_sub_timing
        self.on_split_clip = on_split_clip
        self.on_trim_clip = on_trim_clip
        self.on_delete_clip = on_delete_clip
        self.on_add_clip = on_add_clip
        self.on_add_music = on_add_music
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_add_cc_track = on_add_cc_track
        self.on_add_audio_track = on_add_audio_track
        self.on_toggle_audio_mute = on_toggle_audio_mute
        self.on_retry_chunk = on_retry_chunk
        self.on_apply_edit = on_apply_edit
        self.on_auto_sync_speed = on_auto_sync_speed
        self.on_duplicate_sub = on_duplicate_sub
        self.on_delete_sub = on_delete_sub
        self.on_audition_sub = on_audition_sub
        self.on_watermark_move_or_scale = on_watermark_move_or_scale
        self.on_toggle_inspector = on_toggle_inspector
        self.on_auto_pipeline = on_auto_pipeline
        self.on_batch_open = on_batch_open
        self.on_speed_change = on_speed_change
        self.on_fps_change = on_fps_change
        self.on_volume_change = on_volume_change
        self.on_object_selected = on_object_selected
        self.timeline_parent = timeline_parent

        self.playback_speed = 1.0
        self.duration_sec = 1.0
        self.current_sec = 0.0
        self.subtitles_data = []
        self.video_clips = []
        self.bg_music_data = None
        self.zoom_px_per_sec = 35
        self._clip_thumbnails = {}  # {clip_path: [(time_sec, PhotoImage, width), ...]}
        self._thumbnail_loading = set()

        # Audio Volume and Fullscreen state
        self.player_volume = 1.0
        self.is_player_muted = False
        self._prev_player_volume = 1.0
        self._is_fullscreen = False

        # Object Selection & Manipulation (CC / Watermark / Shapes)
        self._selected_object = None  # None, "cc", "watermark"
        self._object_history = []
        self.wm_rotation = 0

        # Timeline Trimming, Snapping & Panning state
        self._hover_trim = None  # None or (trim_edge, sub_idx, block_type)
        self._trim_active = None
        self._pan_start_x = 0
        self._last_video_rect = (0, 0, 640, 360)

        # Dynamic Tracks State
        self.cc_tracks = [
            {"id": 0, "name": "CC 1 (Khmer)", "color": "#db2777", "subtitles": []}
        ]
        self.audio_tracks = [
            {"id": 0, "name": "Audio 1 (Original Video)", "type": "original", "volume": 0.15, "is_muted": False, "color": "#0d9488"},
            {"id": 1, "name": "Audio 2 (Khmer Dub)", "type": "dub", "volume": 1.0, "is_muted": False, "color": "#14b8a6"},
            {"id": 2, "name": "Audio 3 (Music BGM)", "type": "bgm", "volume": 0.35, "is_muted": False, "color": "#d97706"}
        ]
        self.active_aspect_ratio_key = "Auto (Fit Original)"
        self.show_green_frame = True
        self.active_fps_key = "30 FPS"
        self._video_w = 0
        self._video_h = 0
        self._video_fps = 30.0
        self.chunks_data = []

        self.last_pil_img = None
        self.current_tk_photo = None
        self.watermark_tk_photo = None
        self.watermark_config = None
        self.wm_rel_x = 0.90
        self.wm_rel_y = 0.10
        self.wm_scale = 0.15
        self.wm_opacity = 1.0
        self._wm_drag_start_x = 0
        self._wm_drag_start_y = 0
        self.color_grading = {"brightness": 0.0, "contrast": 1.0, "saturation": 1.0}

        # Subtitle positioning & styling
        self.cc_rel_x = 0.50
        self.cc_rel_y = 0.88
        self.cc_font_size = 18
        self.cc_font_family = KHMER_FONT_FAMILY
        self._drag_start_x = 0
        self._drag_start_y = 0
        self.is_cc_active = False

        # CC Styling & Animation Presets
        self.cc_animation = "🎤 Karaoke (Active Word Highlight)"
        self.cc_bg_style = "Black Box 50% (ប្រអប់ខ្មៅស្រាល)"
        self.cc_highlight_color = "#facc15"
        self.cc_text_color = "#ffffff"
        self.cc_border_width = 3
        self.is_preview_collapsed = False
        self._last_popup_sub_id = None
        self.lbl_cc_stats = None

        # Timeline CC Block & Video Clip dragging & selection
        self._dragging_sub_idx = None
        self._selected_sub_idx = None
        self._selected_clip_idx = None
        self._drag_sub_start_x = 0
        self._drag_sub_orig_start = 0.0
        self._drag_sub_orig_end = 0.0
        self._rendered_blocks = []  # List of (x1, y1, x2, y2, s_idx, type) for precise 2D hit-testing
        self._rendered_video_clips = []  # List of (x1, y1, x2, y2, c_idx) for video clip selection
        self._resize_timer = None
        self._timeline_redraw_timer = None

        self.grid_columnconfigure(0, weight=1)

        self._build_ui()

    def _set_speed(self, speed: float):
        self.playback_speed = speed
        if hasattr(self, "_speed_buttons"):
            for s, b in self._speed_buttons.items():
                if abs(s - speed) < 0.05:
                    b.configure(fg_color="#2563eb", font=ctk.CTkFont(size=9, weight="bold"))
                else:
                    b.configure(fg_color="#1e293b", font=ctk.CTkFont(size=9, weight="normal"))
        if self.on_speed_change:
            self.on_speed_change(speed)

    def set_resolution(self, width: int, height: int, fps: float = 0.0):
        self._video_w = width
        self._video_h = height
        if fps > 0:
            self._video_fps = fps
            if hasattr(self, "combo_fps_hdr") and self.combo_fps_hdr:
                for val in ["30 FPS", "60 FPS", "24 FPS (Cinema)", "25 FPS"]:
                    if str(int(fps)) in val:
                        self.combo_fps_hdr.set(val)
                        break
        if hasattr(self, "lbl_resolution") and self.lbl_resolution:
            if width > 0 and height > 0:
                fps_txt = f" | {self._video_fps:.0f} FPS" if hasattr(self, "_video_fps") and self._video_fps > 0 else ""
                self.lbl_resolution.configure(text=f"[ {width}x{height}{fps_txt} ]")
            else:
                self.lbl_resolution.configure(text="[ No Video ]")

    def _build_ui(self):
        row_idx = 0
        if self.timeline_parent:
            # 0. Live Studio Cinema Monitor Header with Aspect Ratio & FPS & Green Frame Guide
            mon_hdr = ctk.CTkFrame(self, fg_color="#181a20", height=28, corner_radius=0)
            mon_hdr.grid(row=row_idx, column=0, padx=6, pady=(4, 2), sticky="ew")

            ctk.CTkLabel(
                mon_hdr,
                text="🖥️ Live Studio Cinema Monitor",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#94a3b8"
            ).pack(side="left", padx=8, pady=3)

            self.lbl_resolution = ctk.CTkLabel(
                mon_hdr,
                text="[ No Video ]",
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color="#64748b"
            )
            self.lbl_resolution.pack(side="left", padx=4, pady=3)

            if self.on_toggle_inspector:
                self.btn_toggle_inspector = ctk.CTkButton(
                    mon_hdr,
                    text="⚙️ Settings & Audio Mix",
                    command=self.on_toggle_inspector,
                    fg_color="#1e293b",
                    hover_color="#334155",
                    corner_radius=3,
                    height=20,
                    width=135,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color="#38bdf8"
                )
                self.btn_toggle_inspector.pack(side="right", padx=(2, 6), pady=3)

            # Green Frame Guide Checkbox
            self.check_green_frame = ctk.CTkCheckBox(
                mon_hdr,
                text="🟩 Green Frame",
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#10b981",
                width=90,
                height=18,
                checkbox_width=13,
                checkbox_height=13,
                corner_radius=2,
                command=self._on_green_frame_toggle
            )
            self.check_green_frame.select()
            self.check_green_frame.pack(side="right", padx=(4, 6), pady=3)

            # Video Aspect Ratio / Size Selector (ខ្នាត Video)
            self.combo_ratio_hdr = ctk.CTkComboBox(
                mon_hdr,
                values=list(PREVIEW_ASPECT_RATIOS.keys()),
                width=115,
                height=20,
                font=ctk.CTkFont(size=9),
                dropdown_font=ctk.CTkFont(size=9),
                corner_radius=2,
                command=self._on_aspect_ratio_change
            )
            self.combo_ratio_hdr.set(self.active_aspect_ratio_key)
            self.combo_ratio_hdr.pack(side="right", padx=2, pady=3)
            ctk.CTkLabel(mon_hdr, text="📐 ខ្នាត:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8").pack(side="right", padx=(4, 1))

            # Frame Rate (FPS) Selector
            self.combo_fps_hdr = ctk.CTkComboBox(
                mon_hdr,
                values=["30 FPS", "60 FPS", "24 FPS (Cinema)", "25 FPS"],
                width=88,
                height=20,
                font=ctk.CTkFont(size=9),
                dropdown_font=ctk.CTkFont(size=9),
                corner_radius=2,
                command=self._on_fps_change
            )
            self.combo_fps_hdr.set("30 FPS")
            self.combo_fps_hdr.pack(side="right", padx=2, pady=3)
            ctk.CTkLabel(mon_hdr, text="🎞️ FPS:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#a855f7").pack(side="right", padx=(6, 1))

            row_idx += 1

        # 1. Video Container (Screen)
        self.video_container = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0)
        self.video_container.grid(row=row_idx, column=0, padx=6, pady=(2, 2), sticky="nsew")
        self.video_container.grid_rowconfigure(0, weight=1)
        self.video_container.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(row_idx, weight=1)
        row_idx += 1

        # High-performance native Tkinter Label for silky smooth video frames
        self.lbl_screen = tk.Label(
            self.video_container,
            text="🎬\nOPEN VIDEO TO PREVIEW",
            font=("Segoe UI", 12, "bold"),
            fg="#475569",
            bg="#000000",
            cursor="arrow"
        )
        self.lbl_screen.grid(row=0, column=0, sticky="nsew")

        # Video Screen Interactive Mouse Bindings: Click Play/Pause, Double Click Fullscreen, Context Menu, Wheel Volume
        self.lbl_screen.bind("<Button-1>", self._on_screen_click)
        self.lbl_screen.bind("<Double-Button-1>", lambda e: self.toggle_fullscreen())
        self.lbl_screen.bind("<Button-3>", self._on_screen_context_menu)
        self.lbl_screen.bind("<MouseWheel>", self._on_screen_mousewheel)

        # Watermark Logo overlay on video screen (Interactive Drag & Cursor Scaling & Layer Selection)
        self.lbl_watermark = ctk.CTkLabel(
            self.video_container,
            text="",
            fg_color="transparent",
            cursor="fleur",
            corner_radius=4
        )
        self.lbl_watermark.place(relx=self.wm_rel_x, rely=self.wm_rel_y, anchor="center")
        self.lbl_watermark.bind("<Button-1>", self._on_wm_drag_start)
        self.lbl_watermark.bind("<B1-Motion>", self._on_wm_drag_motion)
        self.lbl_watermark.bind("<ButtonRelease-1>", self._on_wm_drag_release)
        self.lbl_watermark.bind("<MouseWheel>", self._on_wm_mousewheel)
        self.lbl_watermark.bind("<Button-3>", self._on_wm_context_menu)

        # Progressive Playback Buffering Toast Overlay
        self.lbl_buffering_toast = ctk.CTkLabel(
            self.video_container,
            text="⏳ Buffering Chunk... Processing dialogue in background",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#0f172a",
            text_color="#38bdf8",
            corner_radius=4,
            padx=12,
            pady=6
        )

        # Volume HUD Toast Overlay (fades out after 1.2s)
        self.lbl_volume_toast = ctk.CTkLabel(
            self.video_container,
            text="🔊 100%",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0f172a",
            text_color="#38bdf8",
            corner_radius=4,
            padx=14,
            pady=6
        )

        # Draggable / Zoomable Subtitle Overlay on Video Screen (Layer 2)
        self.lbl_cc_overlay = ctk.CTkLabel(
            self.video_container,
            text="[ 💬 អូសរំកិលទីតាំង CC / Drag CC Overlay ]",
            font=ctk.CTkFont(family=self.cc_font_family, size=self.cc_font_size, weight="bold"),
            text_color="#94a3b8",
            fg_color="#090a0f",
            corner_radius=4,
            wraplength=640,
            cursor="fleur"
        )
        self.lbl_cc_overlay.place(relx=self.cc_rel_x, rely=self.cc_rel_y, anchor="center")

        # Drag, Mouse Wheel Zoom, Selection and Context Menu bindings for Subtitle Overlay
        self.lbl_cc_overlay.bind("<Button-1>", self._on_cc_drag_start)
        self.lbl_cc_overlay.bind("<B1-Motion>", self._on_cc_drag_motion)
        self.lbl_cc_overlay.bind("<ButtonRelease-1>", self._on_cc_drag_release)
        self.lbl_cc_overlay.bind("<MouseWheel>", self._on_cc_mousewheel)
        self.lbl_cc_overlay.bind("<Button-3>", self._on_cc_context_menu)

        # Floating Seeker Time Preview Tooltip
        self.lbl_seeker_tooltip = ctk.CTkLabel(
            self,
            text="⏱️ 00:00",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            fg_color="#1e293b",
            text_color="#38bdf8",
            corner_radius=3,
            padx=6,
            pady=2
        )

        # 2. Player Controls Bar
        ctrl_bar = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0, height=32)
        ctrl_bar.grid(row=row_idx, column=0, padx=6, pady=2, sticky="ew")
        row_idx += 1

        self.btn_back = ctk.CTkButton(
            ctrl_bar, text="⏮ -5s", width=44, height=22, corner_radius=0, 
            fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=10),
            command=lambda: self.on_seek_relative(-5)
        )
        self.btn_back.pack(side="left", padx=(6, 2), pady=4)

        self.btn_play = ctk.CTkButton(
            ctrl_bar, text="▶ Play", width=58, height=22, corner_radius=0,
            fg_color="#2563eb", hover_color="#1d4ed8", font=ctk.CTkFont(size=11, weight="bold"),
            command=self.on_toggle_play
        )
        self.btn_play.pack(side="left", padx=2, pady=4)

        btn_stop = ctk.CTkButton(
            ctrl_bar, text="⏹", width=28, height=22, corner_radius=0,
            fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=10),
            command=lambda: [self.on_seek(0.0), self.on_toggle_play() if getattr(self, "is_playing", False) else None]
        )
        btn_stop.pack(side="left", padx=2, pady=4)

        self.btn_fwd = ctk.CTkButton(
            ctrl_bar, text="+5s ⏭", width=44, height=22, corner_radius=0, 
            fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=10),
            command=lambda: self.on_seek_relative(5)
        )
        self.btn_fwd.pack(side="left", padx=2, pady=4)

        self.lbl_timecode = ctk.CTkLabel(ctrl_bar, text="00:00:00 / 00:00:00", font=ctk.CTkFont(family="Consolas", size=11))
        self.lbl_timecode.pack(side="left", padx=8, pady=4)

        # Seeker slider in transport bar with hover preview
        self.slider_seeker = ctk.CTkSlider(
            ctrl_bar,
            from_=0.0,
            to=100.0,
            height=14,
            command=lambda val: self.on_seek(val),
            fg_color="#0f172a",
            progress_color="#2563eb",
            button_color="#38bdf8",
            button_hover_color="#0284c7"
        )
        self.slider_seeker.set(0.0)
        self.slider_seeker.pack(side="left", fill="x", expand=True, padx=8, pady=4)
        self.slider_seeker.bind("<Motion>", self._on_seeker_hover)
        self.slider_seeker.bind("<Leave>", self._on_seeker_leave)

        # Fullscreen Icon Button (⛶)
        self.btn_fullscreen = ctk.CTkButton(
            ctrl_bar, text="⛶", width=26, height=22, corner_radius=0,
            fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_fullscreen
        )
        self.btn_fullscreen.pack(side="right", padx=(2, 6), pady=4)

        # Volume Mute Icon Button and Volume Slider
        self.btn_volume = ctk.CTkButton(
            ctrl_bar, text="🔊", width=26, height=22, corner_radius=0,
            fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=11),
            command=self.toggle_mute
        )
        self.btn_volume.pack(side="right", padx=1, pady=4)

        self.slider_volume = ctk.CTkSlider(
            ctrl_bar, from_=0.0, to=1.0, width=54, height=12,
            command=self.set_player_volume, fg_color="#0f172a",
            progress_color="#10b981", button_color="#34d399", button_hover_color="#059669"
        )
        self.slider_volume.set(1.0)
        self.slider_volume.pack(side="right", padx=(2, 4), pady=4)

        # Audio Switches
        self.check_khmer_audio = ctk.CTkCheckBox(ctrl_bar, text="🔊 Dub", width=54, corner_radius=0, font=ctk.CTkFont(size=10), text_color="#10b981")
        self.check_khmer_audio.select()
        self.check_khmer_audio.pack(side="right", padx=(2, 4))

        self.check_bgm_audio = ctk.CTkCheckBox(ctrl_bar, text="🎵 BGM", width=54, corner_radius=0, font=ctk.CTkFont(size=10), text_color="#f59e0b")
        self.check_bgm_audio.select()
        self.check_bgm_audio.pack(side="right", padx=1)

        # 3. Speed & Studio Action Bar (Rust app.rs style)
        speed_bar = ctk.CTkFrame(self, fg_color="#141822", corner_radius=0, height=28)
        speed_bar.grid(row=row_idx, column=0, padx=6, pady=(1, 2), sticky="ew")
        row_idx += 1

        ctk.CTkLabel(speed_bar, text="⚡ Speed:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(side="left", padx=(6, 2))
        self._speed_buttons = {}
        for spd, lbl in [(0.5, "0.5x"), (1.0, "1.0x Normal"), (1.25, "1.25x"), (1.5, "1.5x"), (2.0, "2.0x")]:
            btn_sp = ctk.CTkButton(
                speed_bar,
                text=lbl,
                width=len(lbl)*6 + 10,
                height=20,
                corner_radius=2,
                fg_color="#2563eb" if spd == 1.0 else "#1e293b",
                hover_color="#1d4ed8",
                font=ctk.CTkFont(size=9, weight="bold" if spd == 1.0 else "normal"),
                command=lambda s=spd: self._set_speed(s)
            )
            btn_sp.pack(side="left", padx=1, pady=3)
            self._speed_buttons[spd] = btn_sp

        if self.on_auto_pipeline:
            btn_pipe = ctk.CTkButton(
                speed_bar,
                text="⚡ 1-Click Pipeline",
                command=self.on_auto_pipeline,
                fg_color="#059669",
                hover_color="#047857",
                corner_radius=2,
                height=20,
                width=105,
                font=ctk.CTkFont(size=9, weight="bold")
            )
            btn_pipe.pack(side="left", padx=(6, 2), pady=3)

        if self.on_batch_open:
            btn_batch = ctk.CTkButton(
                speed_bar,
                text="📁 Batch Open...",
                command=self.on_batch_open,
                fg_color="#1e293b",
                hover_color="#334155",
                corner_radius=2,
                height=20,
                width=85,
                font=ctk.CTkFont(size=9)
            )
            btn_batch.pack(side="left", padx=2, pady=3)

        # Video Format Selector on Right of Speed Bar
        self.combo_ratio = ctk.CTkComboBox(
            speed_bar,
            values=list(PREVIEW_ASPECT_RATIOS.keys()),
            width=135,
            height=20,
            font=ctk.CTkFont(size=9),
            dropdown_font=ctk.CTkFont(size=9),
            corner_radius=2,
            command=self._on_aspect_ratio_change
        )
        self.combo_ratio.set("Auto (Fit Original)")
        self.combo_ratio.pack(side="right", padx=(2, 6), pady=3)
        ctk.CTkLabel(speed_bar, text="📐 Format:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8").pack(side="right", padx=(4, 1))

        # 4. Active Subtitle Info Banner
        self.sub_info_banner = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0, height=24)
        self.sub_info_banner.grid(row=row_idx, column=0, padx=6, pady=(1, 3), sticky="ew")
        row_idx += 1

        self.lbl_active_time = ctk.CTkLabel(
            self.sub_info_banner,
            text="⏱️ CC: [--:-- -> --:--]",
            font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_active_time.pack(side="left", padx=6, pady=2)

        self.lbl_active_text = ctk.CTkLabel(
            self.sub_info_banner,
            text="CC: No subtitle at current timestamp (Drag CC box to move anywhere)",
            font=ctk.CTkFont(family=self.cc_font_family, size=11),
            text_color="#94a3b8"
        )
        self.lbl_active_text.pack(side="left", padx=6, pady=2)

        # 5. CapCut Professional N-Track Dynamic Timeline Editor
        if self.timeline_parent:
            # Place timeline in dedicated container (e.g. bottom section of right column)
            self.timeline_card = ctk.CTkFrame(self.timeline_parent, fg_color="#0f1115", corner_radius=0)
            self.timeline_card.pack(fill="both", expand=True, padx=2, pady=2)
        else:
            # Vertical Resize Sash Bar between Video Player and Timeline
            self.sash_timeline_resize = tk.Frame(self, bg="#1e293b", height=8, cursor="sb_v_double_arrow")
            self.sash_timeline_resize.grid(row=row_idx, column=0, padx=6, pady=(1, 1), sticky="ew")
            row_idx += 1

            self.sash_grip = tk.Frame(self.sash_timeline_resize, bg="#475569", width=42, height=3)
            self.sash_grip.place(relx=0.5, rely=0.5, anchor="center")

            def _enter_tl_sash(e):
                self.sash_timeline_resize.configure(bg="#0284c7")
                self.sash_grip.configure(bg="#38bdf8")

            def _leave_tl_sash(e):
                self.sash_timeline_resize.configure(bg="#1e293b")
                self.sash_grip.configure(bg="#475569")

            self.sash_timeline_resize.bind("<Enter>", _enter_tl_sash)
            self.sash_timeline_resize.bind("<Leave>", _leave_tl_sash)
            self.sash_grip.bind("<Enter>", _enter_tl_sash)
            self.sash_grip.bind("<Leave>", _leave_tl_sash)
            self.sash_timeline_resize.bind("<Button-1>", self._on_timeline_resize_start)
            self.sash_timeline_resize.bind("<B1-Motion>", self._on_timeline_resize_motion)
            self.sash_grip.bind("<Button-1>", self._on_timeline_resize_start)
            self.sash_grip.bind("<B1-Motion>", self._on_timeline_resize_motion)

            self.timeline_card = ctk.CTkFrame(self, fg_color="#0f1115", corner_radius=0, height=220)
            self.timeline_card.grid(row=row_idx, column=0, padx=6, pady=(1, 6), sticky="nsew")
            self.timeline_card.grid_propagate(False)

        # Timeline Editing Tools Toolbar
        t_tools = ctk.CTkFrame(self.timeline_card, fg_color="#181a20", corner_radius=0, height=26)
        t_tools.pack(fill="x")

        # Tool buttons: Add Clip, Split, Trim, Delete, Add Music, Undo, Redo
        btn_add_c = ctk.CTkButton(t_tools, text="➕ Clip", width=46, height=20, corner_radius=0, font=ctk.CTkFont(size=9, weight="bold"), fg_color="#1e293b", hover_color="#334155", command=self.on_add_clip)
        btn_add_c.pack(side="left", padx=(6, 2), pady=3)

        btn_split = ctk.CTkButton(t_tools, text="✂️ Split", width=48, height=20, corner_radius=0, font=ctk.CTkFont(size=9, weight="bold"), fg_color="#0284c7", hover_color="#0369a1", command=self._split_at_playhead)
        btn_split.pack(side="left", padx=2, pady=3)

        btn_trim = ctk.CTkButton(t_tools, text="✂️ Trim", width=46, height=20, corner_radius=0, font=ctk.CTkFont(size=9), fg_color="#334155", hover_color="#475569", command=self.on_trim_clip)
        btn_trim.pack(side="left", padx=2, pady=3)

        btn_del = ctk.CTkButton(t_tools, text="🗑️ Del", width=40, height=20, corner_radius=0, font=ctk.CTkFont(size=9), fg_color="#be123c", hover_color="#9f1239", command=self.on_delete_clip)
        btn_del.pack(side="left", padx=2, pady=3)

        btn_music = ctk.CTkButton(t_tools, text="🎵 +Music", width=58, height=20, corner_radius=0, font=ctk.CTkFont(size=9, weight="bold"), fg_color="#b45309", hover_color="#92400e", command=self.on_add_music)
        btn_music.pack(side="left", padx=(6, 2), pady=3)

        # Undo / Redo
        btn_undo = ctk.CTkButton(t_tools, text="↩️", width=26, height=20, corner_radius=0, font=ctk.CTkFont(size=10), fg_color="#334155", hover_color="#475569", command=self.on_undo)
        btn_undo.pack(side="left", padx=2, pady=3)

        btn_redo = ctk.CTkButton(t_tools, text="↪️", width=26, height=20, corner_radius=0, font=ctk.CTkFont(size=10), fg_color="#334155", hover_color="#475569", command=self.on_redo)
        btn_redo.pack(side="left", padx=2, pady=3)

        # Dynamic Track Adders (➕ CC Track & ➕ Audio Track)
        btn_add_cc = ctk.CTkButton(t_tools, text="➕ CC Track", width=68, height=20, corner_radius=0, font=ctk.CTkFont(size=9, weight="bold"), fg_color="#831843", hover_color="#9d174d", command=self._on_btn_add_cc_track)
        btn_add_cc.pack(side="left", padx=(6, 2), pady=3)

        btn_add_audio = ctk.CTkButton(t_tools, text="➕ Audio Track", width=78, height=20, corner_radius=0, font=ctk.CTkFont(size=9, weight="bold"), fg_color="#0f766e", hover_color="#115e59", command=self._on_btn_add_audio_track)
        btn_add_audio.pack(side="left", padx=2, pady=3)

        # Timeline Zoom Controls
        btn_zoom_in = ctk.CTkButton(t_tools, text="🔍+", width=26, height=20, corner_radius=0, font=ctk.CTkFont(size=9), fg_color="#334155", command=self.zoom_in)
        btn_zoom_in.pack(side="right", padx=(2, 6), pady=3)
        btn_zoom_out = ctk.CTkButton(t_tools, text="🔍-", width=26, height=20, corner_radius=0, font=ctk.CTkFont(size=9), fg_color="#334155", command=self.zoom_out)
        btn_zoom_out.pack(side="right", padx=2, pady=3)

        # Canvas with Scrollbar
        canvas_box = ctk.CTkFrame(self.timeline_card, fg_color="#090a0f", corner_radius=0)
        canvas_box.pack(fill="both", expand=True, padx=2, pady=2)

        self.h_scrollbar = ttk.Scrollbar(canvas_box, orient="horizontal")
        self.h_scrollbar.pack(side="bottom", fill="x")

        self.timeline_canvas = tk.Canvas(
            canvas_box,
            bg="#090a0f",
            height=165,
            xscrollcommand=self.h_scrollbar.set,
            highlightthickness=0
        )
        self.timeline_canvas.pack(side="top", fill="both", expand=True)
        self.h_scrollbar.config(command=self.timeline_canvas.xview)

        # Canvas Mouse Bindings: Left Click (Select/Ruler Seek), Drag (Trim edge / Move clip with snap / Playhead scrub), Double-Click (Edit), Right-Click (Context Menu), Middle Click Drag (Pan), Mouse Wheel (Ctrl+Zoom, Shift+HScroll, VScroll), Motion (Edge Trim Cursor)
        self.timeline_canvas.bind("<Button-1>", self._on_canvas_click)
        self.timeline_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.timeline_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.timeline_canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.timeline_canvas.bind("<Button-3>", self._on_canvas_right_click)
        self.timeline_canvas.bind("<Motion>", self._on_canvas_motion)
        self.timeline_canvas.bind("<Button-2>", self._on_canvas_middle_press)
        self.timeline_canvas.bind("<B2-Motion>", self._on_canvas_middle_drag)
        self.timeline_canvas.bind("<ButtonRelease-2>", self._on_canvas_middle_release)
        self.timeline_canvas.bind("<MouseWheel>", self._on_canvas_mousewheel)

        # Timeline Keyboard Shortcuts: Delete/Backspace, Escape (Deselect), Ctrl+Z (Undo), Arrow Keys (Nudge Playhead)
        self.timeline_canvas.bind("<Delete>", self._on_timeline_delete)
        self.timeline_canvas.bind("<BackSpace>", self._on_timeline_delete)
        self.timeline_canvas.bind("<Escape>", self._on_timeline_escape)
        self.timeline_canvas.bind("<Left>", lambda e: self.on_seek_relative(-0.5))
        self.timeline_canvas.bind("<Right>", lambda e: self.on_seek_relative(0.5))
        self.timeline_canvas.bind("<Control-z>", lambda e: self.on_undo() if self.on_undo else None)
        self.timeline_canvas.bind("<Control-Z>", lambda e: self.on_undo() if self.on_undo else None)

        self.video_container.bind("<Configure>", self._on_container_resize)

    # ------------------ FONT SELECTION & WYSIWYG ------------------
    def set_font_family(self, font_name: str):
        """Changes the active Khmer font across the video preview and editor"""
        self.cc_font_family = font_name
        self.lbl_cc_overlay.configure(font=ctk.CTkFont(family=self.cc_font_family, size=self.cc_font_size, weight="bold"))
        self.lbl_active_text.configure(font=ctk.CTkFont(family=self.cc_font_family, size=11))
        self.redraw_timeline()

    def set_watermark_image(self, img_path: str, pos_key: str = "Top-Right (លើ ស្ដាំ)", scale: float = 0.15, opacity: float = 1.0, rel_x: float = None, rel_y: float = None):
        """Loads and overlays watermark image on video screen with scaling and opacity %"""
        self.watermark_config = {
            "path": img_path,
            "pos": pos_key,
            "scale": scale,
            "opacity": opacity,
            "rel_x": rel_x,
            "rel_y": rel_y
        }
        self.wm_scale = scale
        self.wm_opacity = opacity

        if not img_path or not os.path.exists(img_path):
            self.lbl_watermark.configure(image="")
            return

        # Position placement
        if rel_x is not None and rel_y is not None:
            self.wm_rel_x = rel_x
            self.wm_rel_y = rel_y
        elif pos_key in WATERMARK_POSITIONS and WATERMARK_POSITIONS[pos_key] is not None:
            pos_map = {
                "Top-Right (លើ ស្ដាំ)": (0.90, 0.10),
                "Top-Left (លើ ឆ្វេង)": (0.10, 0.10),
                "Bottom-Right (ក្រោម ស្ដាំ)": (0.90, 0.90),
                "Bottom-Left (ក្រោម ឆ្វេង)": (0.10, 0.90),
                "Center (កណ្ដាល)": (0.50, 0.50)
            }
            rx, ry = pos_map.get(pos_key, (0.90, 0.10))
            self.wm_rel_x = rx
            self.wm_rel_y = ry

        self._render_watermark_image()
        self.lbl_watermark.place(relx=self.wm_rel_x, rely=self.wm_rel_y, anchor="center")
        self.lbl_watermark.lift()

    def _render_watermark_image(self):
        if not self.watermark_config or not self.watermark_config.get("path"):
            return
        img_path = self.watermark_config["path"]
        if not os.path.exists(img_path):
            return

        try:
            vx, vy, vw, vh = getattr(self, "_last_video_rect", (0, 0, self.video_container.winfo_width(), self.video_container.winfo_height()))
            target_w = max(24, int(max(100, vw) * self.wm_scale))
            ratio = target_w / max(1, pil_wm.width)
            target_h = max(16, int(pil_wm.height * ratio))
            pil_wm_resized = pil_wm.resize((target_w, target_h), Image.Resampling.BILINEAR)

            # Apply Opacity percentage (e.g. 10% - 100%)
            eff_opacity = max(0.05, min(1.0, self.wm_opacity))
            if eff_opacity < 0.999:
                r, g, b, a = pil_wm_resized.split()
                a = a.point(lambda p: int(p * eff_opacity))
                pil_wm_resized = Image.merge("RGBA", (r, g, b, a))

            self.watermark_tk_photo = ImageTk.PhotoImage(image=pil_wm_resized)
            self.lbl_watermark.configure(image=self.watermark_tk_photo)
            self._reposition_watermark()
            self.lbl_watermark.lift()
        except Exception as e:
            print(f"Watermark overlay error: {e}")

    # ------------------ OBJECT LAYER SELECTION & MANIPULATION (CC / WATERMARK) ------------------
    def _select_object(self, obj_type: str):
        """
        Selects an object layer in Video Preview (Layer 1: Watermark/Logo, Layer 2: CC Subtitle)
        Displays bounding box highlight and syncs with Inspector Panel on the right!
        """
        self._selected_object = obj_type
        if obj_type == "watermark":
            self.lbl_watermark.configure(border_width=2, border_color="#10b981")
            self.lbl_cc_overlay.configure(border_width=0, border_color="transparent")
        elif obj_type == "cc":
            self.lbl_cc_overlay.configure(border_width=2, border_color="#38bdf8")
            self.lbl_watermark.configure(border_width=0, border_color="transparent")

        # Bind keyboard shortcuts for object editing (Arrow keys nudge, Delete, Esc, Ctrl+Z)
        top = self.winfo_toplevel()
        top.bind("<Up>", lambda e: self._nudge_selected_object(0, -0.01 if not (e.state & 0x0001) else -0.002))
        top.bind("<Down>", lambda e: self._nudge_selected_object(0, 0.01 if not (e.state & 0x0001) else 0.002))
        top.bind("<Left>", lambda e: self._nudge_selected_object(-0.01 if not (e.state & 0x0001) else -0.002, 0))
        top.bind("<Right>", lambda e: self._nudge_selected_object(0.01 if not (e.state & 0x0001) else 0.002, 0))
        top.bind("<Escape>", lambda e: self._deselect_all_objects())

        # Notify Inspector Panel to open / sync
        if self.on_object_selected:
            self.on_object_selected(obj_type)
        elif self.on_toggle_inspector and hasattr(self, "btn_toggle_inspector"):
            if "Open" in self.btn_toggle_inspector.cget("text"):
                self.on_toggle_inspector()

    def _deselect_all_objects(self):
        """Clears selection bounding boxes on all video overlay layers"""
        self._selected_object = None
        self.lbl_watermark.configure(border_width=0, border_color="transparent")
        self.lbl_cc_overlay.configure(border_width=0, border_color="transparent")

    def _nudge_selected_object(self, dx: float, dy: float):
        """Arrow keys micro-nudge object position"""
        if self._selected_object == "watermark":
            self.wm_rel_x = max(0.02, min(0.98, round(self.wm_rel_x + dx, 3)))
            self.wm_rel_y = max(0.02, min(0.98, round(self.wm_rel_y + dy, 3)))
            self._reposition_watermark()
            if self.watermark_config:
                self.watermark_config["rel_x"] = self.wm_rel_x
                self.watermark_config["rel_y"] = self.wm_rel_y
        elif self._selected_object == "cc":
            self.cc_rel_x = max(0.05, min(0.95, round(self.cc_rel_x + dx, 3)))
            self.cc_rel_y = max(0.05, min(0.95, round(self.cc_rel_y + dy, 3)))
            self._reposition_cc_overlay()
            self._update_cc_stats_label()

    def _delete_selected_object(self):
        """Deletes/clears selected overlay object"""
        if self._selected_object == "watermark":
            self.lbl_watermark.configure(image="")
            self.watermark_config = None
            self._deselect_all_objects()
        elif self._selected_object == "cc":
            self.toggle_cc_overlay()
            self._deselect_all_objects()

    # ------------------ WATERMARK INTERACTION & CONTEXT MENU ------------------
    def _on_wm_drag_start(self, event):
        self._select_object("watermark")
        self._wm_drag_start_x = event.x_root
        self._wm_drag_start_y = event.y_root
        self._object_history.append(("wm", self.wm_rel_x, self.wm_rel_y, self.wm_scale, self.wm_opacity))

    def _on_wm_drag_motion(self, event):
        dx = event.x_root - self._wm_drag_start_x
        dy = event.y_root - self._wm_drag_start_y
        self._wm_drag_start_x = event.x_root
        self._wm_drag_start_y = event.y_root

        # Shift + Drag: fine precision drag (slowed down 4x)
        if event.state & 0x0001:
            dx *= 0.25
            dy *= 0.25

        vx, vy, vw, vh = getattr(self, "_last_video_rect", (0, 0, self.video_container.winfo_width(), self.video_container.winfo_height()))
        new_x = max(0.03, min(0.97, self.wm_rel_x + (dx / max(10, vw))))
        new_y = max(0.03, min(0.97, self.wm_rel_y + (dy / max(10, vh))))
        self.wm_rel_x = round(new_x, 3)
        self.wm_rel_y = round(new_y, 3)

        self._reposition_watermark()
        if self.watermark_config:
            self.watermark_config["rel_x"] = self.wm_rel_x
            self.watermark_config["rel_y"] = self.wm_rel_y
            self.watermark_config["pos"] = "Custom (អូសតាមចិត្ត / Drag & Drop)"

        if self.on_watermark_move_or_scale and self.watermark_config:
            self.on_watermark_move_or_scale(
                self.watermark_config.get("path"),
                "Custom (អូសតាមចិត្ត / Drag & Drop)",
                self.wm_scale,
                self.wm_opacity,
                self.wm_rel_x,
                self.wm_rel_y
            )

    def _on_wm_drag_release(self, event):
        pass

    def _on_wm_mousewheel(self, event):
        """Scroll to Scale logo by cursor, or Ctrl+Scroll to adjust Opacity %"""
        if event.state & 0x0004:
            # Ctrl + Scroll: adjust opacity %
            if event.delta > 0:
                self.wm_opacity = min(1.0, round(self.wm_opacity + 0.05, 2))
            else:
                self.wm_opacity = max(0.10, round(self.wm_opacity - 0.05, 2))
        else:
            # Scroll: adjust scale by cursor
            if event.delta > 0:
                self.wm_scale = min(0.50, round(self.wm_scale + 0.02, 2))
            else:
                self.wm_scale = max(0.04, round(self.wm_scale - 0.02, 2))

        if self.watermark_config:
            self.watermark_config["scale"] = self.wm_scale
            self.watermark_config["opacity"] = self.wm_opacity

        self._render_watermark_image()

        if self.on_watermark_move_or_scale and self.watermark_config:
            self.on_watermark_move_or_scale(
                self.watermark_config.get("path"),
                self.watermark_config.get("pos", "Custom (អូសតាមចិត្ត / Drag & Drop)"),
                self.wm_scale,
                self.wm_opacity,
                self.wm_rel_x,
                self.wm_rel_y
            )

    def _on_wm_context_menu(self, event):
        """Right-click context menu for Watermark Logo object"""
        menu = tk.Menu(self, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        menu.add_command(label="🖼️ Watermark Logo Layer", state="disabled")
        menu.add_separator()
        menu.add_command(label="🔄 Reset Position to Top-Right", command=lambda: self.set_watermark_image(self.watermark_config.get("path") if self.watermark_config else "", "Top-Right (លើ ស្ដាំ)"))
        menu.add_command(label="⚙️ Inspector Properties...", command=lambda: self._select_object("watermark"))
        menu.add_command(label="🗑️ Remove Watermark", command=self._delete_selected_object)
        menu.tk_popup(event.x_root, event.y_root)

    def set_color_grading(self, brightness: float = 0.0, contrast: float = 1.0, saturation: float = 1.0):
        """Sets live color grading filters"""
        self.color_grading = {"brightness": brightness, "contrast": contrast, "saturation": saturation}
        if self.last_pil_img:
            self._render_scaled_image(self.last_pil_img)

    # ------------------ CC SUBTITLE OVERLAY INTERACTION & CONTEXT MENU ------------------
    def _reposition_cc_overlay(self):
        vx, vy, vw, vh = getattr(self, "_last_video_rect", (0, 0, self.video_container.winfo_width(), self.video_container.winfo_height()))
        actual_x = vx + int(vw * self.cc_rel_x)
        actual_y = vy + int(vh * self.cc_rel_y)
        self.lbl_cc_overlay.place(x=actual_x, y=actual_y, anchor="center")

    def _reposition_watermark(self):
        if not self.watermark_config or not self.watermark_config.get("path"):
            return
        vx, vy, vw, vh = getattr(self, "_last_video_rect", (0, 0, self.video_container.winfo_width(), self.video_container.winfo_height()))
        actual_x = vx + int(vw * self.wm_rel_x)
        actual_y = vy + int(vh * self.wm_rel_y)
        self.lbl_watermark.place(x=actual_x, y=actual_y, anchor="center")

    def _on_cc_drag_start(self, event):
        self._select_object("cc")
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._object_history.append(("cc", self.cc_rel_x, self.cc_rel_y, self.cc_font_size))

    def _on_cc_drag_motion(self, event):
        dx = event.x_root - self._drag_start_x
        dy = event.y_root - self._drag_start_y
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

        # Shift + Drag: fine precision drag
        if event.state & 0x0001:
            dx *= 0.25
            dy *= 0.25

        vx, vy, vw, vh = getattr(self, "_last_video_rect", (0, 0, self.video_container.winfo_width(), self.video_container.winfo_height()))
        new_x = max(0.05, min(0.95, self.cc_rel_x + (dx / max(10, vw))))
        new_y = max(0.05, min(0.95, self.cc_rel_y + (dy / max(10, vh))))
        self.cc_rel_x = round(new_x, 3)
        self.cc_rel_y = round(new_y, 3)

        self._reposition_cc_overlay()
        self._update_cc_stats_label()

    def _on_cc_drag_release(self, event):
        pass

    def _on_cc_mousewheel(self, event):
        if event.delta > 0:
            self.increase_cc_font()
        elif event.delta < 0:
            self.decrease_cc_font()

    def increase_cc_font(self):
        self.cc_font_size = min(40, self.cc_font_size + 2)
        self.lbl_cc_overlay.configure(font=ctk.CTkFont(family=self.cc_font_family, size=self.cc_font_size, weight="bold"))
        self._update_cc_stats_label()

    def decrease_cc_font(self):
        self.cc_font_size = max(12, self.cc_font_size - 2)
        self.lbl_cc_overlay.configure(font=ctk.CTkFont(family=self.cc_font_family, size=self.cc_font_size, weight="bold"))
        self._update_cc_stats_label()

    def _on_cc_context_menu(self, event):
        """Right click context menu on CC Subtitle Overlay"""
        menu = tk.Menu(self, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        menu.add_command(label="💬 Subtitle (CC) Overlay Layer", state="disabled")
        menu.add_separator()
        menu.add_command(label="🔍 Increase Font Size (Wheel Up)", command=self.increase_cc_font)
        menu.add_command(label="🔍 Decrease Font Size (Wheel Down)", command=self.decrease_cc_font)
        menu.add_command(label="📍 Reset Position to Bottom-Center", command=self._reset_cc_pos)
        menu.add_command(label="⚙️ Open CC Styles in Inspector...", command=lambda: self._select_object("cc"))
        menu.tk_popup(event.x_root, event.y_root)

    def _reset_cc_pos(self):
        self.cc_rel_x = 0.50
        self.cc_rel_y = 0.88
        self._reposition_cc_overlay()
        self._update_cc_stats_label()

    def _update_cc_stats_label(self):
        lbl = getattr(self, "lbl_cc_stats", None)
        if lbl and hasattr(lbl, "configure"):
            try:
                lbl.configure(
                    text=f"Pos: ({int(self.cc_rel_x*100)}%, {int(self.cc_rel_y*100)}%) | {self.cc_font_size}pt"
                )
            except Exception:
                pass

    def get_cc_layout(self) -> dict:
        return {
            "pos_x_rel": self.cc_rel_x,
            "pos_y_rel": self.cc_rel_y,
            "font_size": self.cc_font_size,
            "font_name": self.cc_font_family
        }

    # ------------------ VIDEO PLAYER MOUSE ACTIONS, VOLUME & FULLSCREEN ------------------
    def _on_screen_click(self, event):
        """Left Click on video preview screen: deselects active object and toggles Play/Pause"""
        if getattr(self, "_selected_object", None):
            self._deselect_all_objects()
            return
        if self.on_toggle_play:
            self.on_toggle_play()

    def _on_screen_mousewheel(self, event):
        """Mouse Wheel Up/Down on video screen: Smooth Volume Adjustment (+/- 5%)"""
        if event.delta > 0:
            new_vol = min(1.0, round(self.player_volume + 0.05, 2))
        else:
            new_vol = max(0.0, round(self.player_volume - 0.05, 2))
        self.set_player_volume(new_vol)

    def set_player_volume(self, val):
        """Updates player audio volume (0.0 to 1.0) and notifies background audio engine"""
        self.player_volume = float(val)
        if self.player_volume > 0.0:
            self.is_player_muted = False
            if hasattr(self, "btn_volume"):
                self.btn_volume.configure(text="🔊")
        else:
            self.is_player_muted = True
            if hasattr(self, "btn_volume"):
                self.btn_volume.configure(text="🔇")

        if hasattr(self, "slider_volume"):
            self.slider_volume.set(self.player_volume)

        self._show_volume_toast()

        if self.on_volume_change:
            self.on_volume_change(self.player_volume)

    def toggle_mute(self):
        """Mutes / Unmutes player volume"""
        if self.is_player_muted:
            self.is_player_muted = False
            self.player_volume = getattr(self, "_prev_player_volume", 1.0) or 1.0
            if hasattr(self, "btn_volume"):
                self.btn_volume.configure(text="🔊")
        else:
            self._prev_player_volume = self.player_volume
            self.is_player_muted = True
            self.player_volume = 0.0
            if hasattr(self, "btn_volume"):
                self.btn_volume.configure(text="🔇")

        if hasattr(self, "slider_volume"):
            self.slider_volume.set(self.player_volume)

        self._show_volume_toast()

        if self.on_volume_change:
            self.on_volume_change(self.player_volume)

    def _show_volume_toast(self):
        """Shows floating volume percentage badge on video screen"""
        if hasattr(self, "lbl_volume_toast"):
            icon = "🔇 Mute" if self.is_player_muted or self.player_volume == 0 else f"🔊 {int(self.player_volume * 100)}%"
            self.lbl_volume_toast.configure(text=icon)
            self.lbl_volume_toast.place(relx=0.5, rely=0.15, anchor="center")
            self.lbl_volume_toast.lift()
            if hasattr(self, "_vol_toast_timer") and self._vol_toast_timer:
                self.after_cancel(self._vol_toast_timer)
            self._vol_toast_timer = self.after(1200, self.lbl_volume_toast.place_forget)

    def toggle_fullscreen(self):
        """Toggles true borderless fullscreen playback mode"""
        top = self.winfo_toplevel()
        self._is_fullscreen = not getattr(self, "_is_fullscreen", False)
        try:
            top.attributes("-fullscreen", self._is_fullscreen)
        except Exception:
            pass
        if hasattr(self, "btn_fullscreen"):
            self.btn_fullscreen.configure(text="🗗" if self._is_fullscreen else "⛶")

    def _on_seeker_hover(self, event):
        """Hover over Progress Bar shows floating timestamp preview"""
        if self.duration_sec <= 0:
            return
        slider_w = max(10, self.slider_seeker.winfo_width())
        ratio = max(0.0, min(1.0, event.x / slider_w))
        hover_sec = ratio * self.duration_sec
        time_str = time.strftime('%H:%M:%S' if self.duration_sec >= 3600 else '%M:%S', time.gmtime(hover_sec))
        if hasattr(self, "lbl_seeker_tooltip"):
            try:
                self.lbl_seeker_tooltip.configure(text=f"⏱️ {time_str}")
                # Position tooltip directly above cursor in seeker bar relative to PlayerView (self)
                bar = self.slider_seeker.master
                sx = bar.winfo_x() + self.slider_seeker.winfo_x() + event.x
                sy = bar.winfo_y() + self.slider_seeker.winfo_y() - 16
                self.lbl_seeker_tooltip.place(in_=self, x=sx, y=sy, anchor="center")
                self.lbl_seeker_tooltip.lift()
            except Exception:
                pass

    def _on_seeker_leave(self, event):
        if hasattr(self, "lbl_seeker_tooltip"):
            try:
                self.lbl_seeker_tooltip.place_forget()
            except Exception:
                pass

    def _on_screen_context_menu(self, event):
        """Right Click on Video Preview opens comprehensive Player Context Menu"""
        menu = tk.Menu(self, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        play_label = "⏸ Pause Video" if getattr(self, "is_playing", False) else "▶ Play Video"
        menu.add_command(label=play_label, command=self.on_toggle_play)
        menu.add_command(label="⛶ Fullscreen Mode (Double Click)", command=self.toggle_fullscreen)
        menu.add_separator()

        # Aspect Ratio (ខ្នាត Video) submenu
        ratio_menu = tk.Menu(menu, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        for r_name in PREVIEW_ASPECT_RATIOS.keys():
            ratio_menu.add_command(label=r_name, command=lambda r=r_name: self._on_aspect_ratio_change(r))
        menu.add_cascade(label="📐 Aspect Ratio / ខ្នាត Video", menu=ratio_menu)

        # Green Frame Toggle
        menu.add_command(label="🟩 Toggle Green Frame Guide", command=self.toggle_green_frame)
        menu.add_command(label="💬 Toggle CC Subtitle Overlay", command=self.toggle_cc_overlay)
        menu.add_separator()

        # Volume & Mute
        mute_lbl = "🔊 Unmute" if self.is_player_muted else "🔇 Mute"
        menu.add_command(label=mute_lbl, command=self.toggle_mute)

        # Speed submenu
        speed_menu = tk.Menu(menu, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        for spd_val, spd_lbl in [(0.5, "0.5x"), (1.0, "1.0x Normal"), (1.25, "1.25x"), (1.5, "1.5x"), (2.0, "2.0x")]:
            speed_menu.add_command(label=spd_lbl, command=lambda s=spd_val: self._set_speed(s))
        menu.add_cascade(label="⚡ Playback Speed", menu=speed_menu)

        menu.add_separator()
        menu.add_command(label="⚙️ Settings & Properties (Inspector)...", command=lambda: self.on_toggle_inspector() if self.on_toggle_inspector else None)

        menu.tk_popup(event.x_root, event.y_root)

    def toggle_green_frame(self):
        """Toggles the green safe margin guide frame"""
        self.show_green_frame = not getattr(self, "show_green_frame", True)
        if hasattr(self, "btn_green_frame"):
            self.btn_green_frame.configure(
                text="🟩 Frame On" if self.show_green_frame else "⬜ Frame Off",
                fg_color="#065f46" if self.show_green_frame else "#1e293b"
            )
        if self.last_pil_img:
            self._render_scaled_image(self.last_pil_img)

    def toggle_cc_overlay(self):
        """Toggles subtitle overlay visibility on video screen"""
        self.is_cc_active = not getattr(self, "is_cc_active", True)
        if self.is_cc_active:
            self._reposition_cc_overlay()
            self.lbl_cc_overlay.lift()
        else:
            self.lbl_cc_overlay.place_forget()

    # ------------------ TIMELINE MULTI-TRACK CONTROLLER ------------------
    def _on_container_resize(self, event):
        if hasattr(self, "_resize_timer") and self._resize_timer:
            self.after_cancel(self._resize_timer)
        self._resize_timer = self.after(30, self._delayed_container_resize)

    def _delayed_container_resize(self):
        self._resize_timer = None
        if self.last_pil_img:
            self._render_scaled_image(self.last_pil_img)

    def zoom_in(self):
        self.zoom_px_per_sec = min(120, self.zoom_px_per_sec + 10)
        self.redraw_timeline()

    def zoom_out(self):
        self.zoom_px_per_sec = max(10, self.zoom_px_per_sec - 10)
        self.redraw_timeline()

    def set_duration(self, duration: float):
        self.duration_sec = max(1.0, duration)
        # Adapt zoom scale for long movies (1h - 4h+) so canvas width stays responsive & memory efficient
        if self.duration_sec > 7200:      # >= 2 hours (e.g. 4 hours)
            self.zoom_px_per_sec = 2
        elif self.duration_sec > 3600:    # >= 1 hour
            self.zoom_px_per_sec = 5
        elif self.duration_sec > 1800:    # >= 30 mins
            self.zoom_px_per_sec = 10
        elif self.duration_sec > 600:     # >= 10 mins
            self.zoom_px_per_sec = 15
        else:
            self.zoom_px_per_sec = 35
        self.redraw_timeline()

    def set_subtitles(self, subtitles: list):
        self.subtitles_data = subtitles
        if self.cc_tracks:
            self.cc_tracks[0]["subtitles"] = subtitles
        self.redraw_timeline()

    def set_cc_tracks(self, tracks: list):
        self.cc_tracks = tracks
        self.redraw_timeline()

    def set_audio_tracks(self, tracks: list):
        self.audio_tracks = tracks
        self.redraw_timeline()

    def clear_thumbnails_cache(self):
        """Clears cached video frame thumbnails when opening a new video"""
        self._clip_thumbnails.clear()
        self._thumbnail_loading.clear()
        self.redraw_timeline()

    def reset_player_for_new_video(self, duration: float = 0.0, width: int = 1280, height: int = 720):
        """Completely resets video player and timeline state for clean video loading without hanging"""
        self.set_play_state(False)
        self.current_time_sec = 0.0
        self.duration_sec = max(1.0, duration)
        self.set_time_pos(0.0)
        self.set_resolution(width, height)
        self.select_subtitle(None)
        self.select_video_clip(None)
        self.update_active_subtitle("", is_active=False)
        self.clear_thumbnails_cache()
        self.reset_timeline_scroll()
        self.subtitles_data = []
        if self.cc_tracks:
            self.cc_tracks[0]["subtitles"] = []
        self.redraw_timeline()

    def reset_timeline_scroll(self):
        """Resets timeline scroll view to time 0:00"""
        try:
            self.timeline_canvas.xview_moveto(0)
        except Exception:
            pass

    def _request_clip_thumbnails(self, clip_path: str, duration: float):
        """Asynchronously extracts video frame thumbnails covering 100% of the clip duration"""
        if not clip_path or not os.path.exists(clip_path) or clip_path in self._thumbnail_loading or clip_path in self._clip_thumbnails:
            return
        self._thumbnail_loading.add(clip_path)

        def worker():
            try:
                cap = cv2.VideoCapture(clip_path)
                if not cap.isOpened():
                    return
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                dur = duration if duration > 0 else (total_frames / fps if fps > 0 else 10.0)

                # Sample 12 to 48 frames evenly distributed across the FULL movie duration
                num_thumbs = max(12, min(48, int(dur / 2.0)))
                interval = dur / max(1, num_thumbs)

                thumbs = []
                last_pil_img = None
                last_w = 60

                for i in range(num_thumbs):
                    sec = min(dur - 0.1, i * interval)
                    # Use POS_MSEC for rock-solid seeking across all video formats
                    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, sec * 1000.0))
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        # Fallback to frame position if msec fails
                        frame_num = int(sec * fps)
                        cap.set(cv2.CAP_PROP_POS_FRAMES, min(frame_num, max(0, total_frames - 1)))
                        ret, frame = cap.read()

                    if ret and frame is not None:
                        fh, fw = frame.shape[:2]
                        target_h = 48
                        target_w = max(45, min(80, int(target_h * (fw / max(1, fh)))))
                        frame_resized = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_AREA)
                        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                        pil_img = Image.fromarray(frame_rgb)
                        last_pil_img = pil_img
                        last_w = target_w
                        thumbs.append((sec, pil_img, target_w))
                    elif last_pil_img is not None:
                        # Duplicate last frame so there is never a gap in the filmstrip
                        thumbs.append((sec, last_pil_img, last_w))

                cap.release()

                def _apply():
                    tk_thumbs = []
                    for s, p_img, tw in thumbs:
                        try:
                            tk_img = ImageTk.PhotoImage(p_img)
                            tk_thumbs.append((s, tk_img, tw))
                        except Exception:
                            pass
                    self._clip_thumbnails[clip_path] = tk_thumbs
                    if clip_path in self._thumbnail_loading:
                        self._thumbnail_loading.remove(clip_path)
                    self.redraw_timeline()

                self.after(0, _apply)
            except Exception as e:
                print(f"Thumbnail extraction error: {e}")
                if clip_path in self._thumbnail_loading:
                    self._thumbnail_loading.remove(clip_path)

        threading.Thread(target=worker, daemon=True).start()

    def set_video_clips(self, clips: list):
        self.video_clips = clips
        for c in clips:
            cp = c.get("path")
            cdur = c.get("duration", 10.0)
            if cp and cp not in self._clip_thumbnails:
                self._request_clip_thumbnails(cp, cdur)
        self.redraw_timeline()

    def set_bg_music(self, bg_music_dict: dict):
        self.bg_music_data = bg_music_dict
        self.redraw_timeline()

    # ------------------ TIMELINE SELECTION & ACTIVE CLIP ------------------
    def select_subtitle(self, idx: int):
        """Highlights the active CC / Voice clip on the timeline without freezing or full redraw"""
        prev_idx = getattr(self, "_selected_sub_idx", None)
        self._selected_sub_idx = idx
        self._selected_clip_idx = None

        if prev_idx is not None and prev_idx != idx:
            try:
                self.timeline_canvas.itemconfig(f"sub_{prev_idx}", outline="#34d399", width=1.5)
                self.timeline_canvas.itemconfig(f"cc_sub_{prev_idx}", outline="#ec4899", width=1.5)
            except Exception:
                pass

        if idx is not None:
            try:
                self.timeline_canvas.itemconfig(f"sub_{idx}", outline="#ffffff", width=2.5)
                self.timeline_canvas.itemconfig(f"cc_sub_{idx}", outline="#ffffff", width=2.5)
            except Exception:
                pass

    def select_video_clip(self, clip_idx: int):
        """Highlights the active Video clip on the timeline with glowing frame"""
        self._selected_clip_idx = clip_idx
        self._selected_sub_idx = None
        self.redraw_timeline()

    def set_font_family(self, font_name: str):
        """Sets active font family for video CC preview overlay and timeline blocks"""
        if not font_name:
            return
        self.cc_font_family = font_name
        try:
            self.lbl_cc_overlay.configure(font=ctk.CTkFont(family=font_name, size=self.cc_font_size, weight="bold"))
        except Exception:
            pass
        self.redraw_timeline()

    # ------------------ TIMELINE VERTICAL RESIZING (↕ size_ns) ------------------
    def _on_timeline_resize_start(self, event):
        self._timeline_resize_start_y = event.y_root
        self._timeline_orig_h = self.timeline_card.cget("height")

    def _on_timeline_resize_motion(self, event):
        dy = self._timeline_resize_start_y - event.y_root
        new_h = max(130, min(550, int(self._timeline_orig_h + dy)))
        self.timeline_card.configure(height=new_h)
        canvas_h = max(80, new_h - 55)
        self.timeline_canvas.configure(height=canvas_h)
        if hasattr(self, "_timeline_redraw_timer") and self._timeline_redraw_timer:
            self.after_cancel(self._timeline_redraw_timer)
        self._timeline_redraw_timer = self.after(20, self.redraw_timeline)

    def set_chunks_status(self, chunks: list):
        """Streaming chunks data update (UI bar removed per user request)"""
        self.chunks_data = chunks
        if hasattr(self, "chunk_badges_container") and self.chunk_badges_container.winfo_exists():
            for child in self.chunk_badges_container.winfo_children():
                child.destroy()

    def _on_chunk_badge_click(self, chunk_id: int, status: str):
        if status == "FAILED" and self.on_retry_chunk:
            self.on_retry_chunk(chunk_id)
        elif status == "READY" and chunk_id < len(self.chunks_data):
            c_dict = self.chunks_data[chunk_id]
            s_sec = c_dict.get("start_sec", 0.0) if isinstance(c_dict, dict) else c_dict.start_sec
            self.current_sec = s_sec
            self._update_playhead_pos()
            self.on_seek(s_sec)

    def show_buffering(self, is_buffering: bool, chunk_info: str = ""):
        if is_buffering:
            txt = f"⏳ Buffering... {chunk_info}" if chunk_info else "⏳ Buffering Chunk... Processing next segment"
            self.lbl_buffering_toast.configure(text=txt)
            self.lbl_buffering_toast.place(relx=0.5, rely=0.5, anchor="center")
            self.lbl_buffering_toast.lift()
        else:
            self.lbl_buffering_toast.place_forget()

    def _on_aspect_ratio_change(self, choice: str):
        self.active_aspect_ratio_key = choice
        if hasattr(self, "combo_ratio") and self.combo_ratio and self.combo_ratio.get() != choice:
            self.combo_ratio.set(choice)
        if hasattr(self, "combo_ratio_hdr") and self.combo_ratio_hdr and self.combo_ratio_hdr.get() != choice:
            self.combo_ratio_hdr.set(choice)
        if self.last_pil_img:
            self._render_scaled_image(self.last_pil_img)

    def _on_fps_change(self, choice: str):
        self.active_fps_key = choice
        try:
            val = float(choice.split()[0])
            self._video_fps = val
        except Exception:
            pass
        if hasattr(self, "_video_w") and hasattr(self, "_video_h"):
            self.set_resolution(self._video_w, self._video_h, self._video_fps)
        if hasattr(self, "on_fps_change") and self.on_fps_change and callable(self.on_fps_change):
            self.on_fps_change(choice)

    def _on_green_frame_toggle(self):
        self.show_green_frame = bool(self.check_green_frame.get()) if hasattr(self, "check_green_frame") else True
        if self.last_pil_img:
            self._render_scaled_image(self.last_pil_img)

    def _on_btn_add_cc_track(self):
        if self.on_add_cc_track:
            self.on_add_cc_track()
        else:
            nid = len(self.cc_tracks)
            palette = ["#db2777", "#8b5cf6", "#ec4899", "#f43f5e", "#a855f7", "#06b6d4"]
            self.cc_tracks.append({"id": nid, "name": f"CC {nid+1}", "color": palette[nid % len(palette)], "subtitles": []})
            self.redraw_timeline()

    def _on_btn_add_audio_track(self):
        if self.on_add_audio_track:
            self.on_add_audio_track()
        else:
            nid = len(self.audio_tracks)
            palette = ["#0d9488", "#14b8a6", "#d97706", "#7c3aed", "#2563eb", "#059669", "#dc2626"]
            self.audio_tracks.append({
                "id": nid,
                "name": f"Audio {nid+1}",
                "type": "custom",
                "volume": 0.8,
                "is_muted": False,
                "color": palette[nid % len(palette)]
            })
            self.redraw_timeline()

    def _split_at_playhead(self):
        if self.on_split_clip:
            self.on_split_clip(self.current_sec)

    @staticmethod
    def _compute_staggered_lanes(items):
        """
        Computes dynamic sub-lane index for each item (subtitle or voice)
        so overlapping timestamps drop down to a row below (Lane 0, Lane 1...)
        without colliding or hiding each other!
        """
        if not items:
            return {}, 1
        indexed = sorted(enumerate(items), key=lambda x: x[1].get("start", 0.0))
        lanes_end = []
        lane_map = {}
        for orig_idx, item in indexed:
            start = item.get("start", 0.0)
            end = item.get("end", 0.0)
            assigned = False
            for l_idx, l_end in enumerate(lanes_end):
                if l_end <= start + 0.05:
                    lanes_end[l_idx] = end
                    lane_map[orig_idx] = l_idx
                    assigned = True
                    break
            if not assigned:
                lane_map[orig_idx] = len(lanes_end)
                lanes_end.append(end)
        return lane_map, max(1, len(lanes_end))

    def redraw_timeline(self):
        """
        Draws CapCut Professional N-Track Timeline with Dynamic Staggered Multi-Lanes:
        - 0. Ruler: Y=0..20
        - 1. Dynamic CC Tracks (Overlapping CC blocks drop down to sub-lanes below)
        - 2. Video Track (Blue with Video A, B, C...)
        - 3. Dynamic Audio Tracks (Overlapping Voice blocks drop down to sub-lanes below)
        - 4. Red Playhead spanning continuously across all rows
        """
        self.timeline_canvas.delete("all")
        self._rendered_blocks = []
        total_width = max(900, int(self.duration_sec * self.zoom_px_per_sec) + 140)

        ruler_h = 24
        v_track_h = 56

        # 1. Compute dynamic lanes and heights for CC tracks
        cc_lane_maps = []
        cc_track_heights = []
        for idx, cc_trk in enumerate(self.cc_tracks):
            subs_to_draw = cc_trk.get("subtitles") or (self.subtitles_data if idx == 0 else [])
            l_map, num_l = self._compute_staggered_lanes(subs_to_draw)
            cc_lane_maps.append(l_map)
            cc_track_heights.append(max(28, num_l * 24 + 4))

        # 2. Compute dynamic lanes and heights for Audio tracks
        audio_lane_maps = []
        audio_track_heights = []
        for a_idx, a_trk in enumerate(self.audio_tracks):
            a_type = a_trk.get("type", "")
            if a_type == "dub" or a_idx == 1:
                l_map, num_l = self._compute_staggered_lanes(self.subtitles_data)
                audio_lane_maps.append(l_map)
                audio_track_heights.append(max(34, num_l * 28 + 4))
            else:
                audio_lane_maps.append({})
                audio_track_heights.append(34)

        # 0. Ruler: Y=0..24 with timestamps 00:00, 00:10, 00:20...
        self.timeline_canvas.create_rectangle(0, 0, total_width, ruler_h, fill="#0f172a", outline="#1e293b")
        # Adaptive Ruler step: for 1h - 3h long movies, use larger step intervals to prevent canvas lag
        if self.duration_sec >= 7200:      # >= 2 hours
            step_sec = 120 if self.zoom_px_per_sec < 20 else 60
        elif self.duration_sec >= 3600:    # >= 1 hour
            step_sec = 60 if self.zoom_px_per_sec < 30 else 30
        elif self.duration_sec >= 900:     # >= 15 mins
            step_sec = 30 if self.zoom_px_per_sec < 30 else 15
        else:
            step_sec = 2 if self.zoom_px_per_sec >= 45 else (5 if self.zoom_px_per_sec >= 20 else 10)

        for s in range(0, int(self.duration_sec) + step_sec, step_sec):
            x = int(s * self.zoom_px_per_sec)
            self.timeline_canvas.create_line(x, 10, x, ruler_h, fill="#64748b", width=1.5 if s % (step_sec * 2) == 0 else 1)
            time_str = time.strftime('%H:%M:%S' if self.duration_sec >= 3600 else '%M:%S', time.gmtime(s))
            self.timeline_canvas.create_text(x + 3, 7, text=time_str, fill="#94a3b8", anchor="w", font=("Consolas", 8, "bold" if s % (step_sec * 2) == 0 else "normal"))

        full_w = int(self.duration_sec * self.zoom_px_per_sec)
        curr_y = ruler_h + 3

        # 1. Draw Video Track (Filmstrip with thumbnails matching CapCut/Premiere)
        vy1 = curr_y
        vy2 = vy1 + v_track_h
        curr_y = vy2 + 4
        self.timeline_canvas.create_rectangle(0, vy1, full_w, vy2, fill="#020617", outline="#1e293b", width=1)
        self.timeline_canvas.create_text(8, vy1 + 12, text="🎬 Video Filmstrip", fill="#38bdf8", anchor="w", font=("Segoe UI", 7, "bold"))

        self._rendered_video_clips = []
        if self.video_clips:
            for c_idx, clip in enumerate(self.video_clips):
                c_start_x = int(clip.get("timeline_start", 0.0) * self.zoom_px_per_sec)
                c_end_x = c_start_x + int(clip["duration"] * self.zoom_px_per_sec)
                self._rendered_video_clips.append((c_start_x, vy1 + 2, c_end_x, vy2 - 2, c_idx))
                c_tag = f"clip_{c_idx}"
                is_clip_active = (getattr(self, "_selected_clip_idx", None) == c_idx)
                c_outline = "#fef08a" if is_clip_active else "#ffffff"
                c_bw = 3 if is_clip_active else 2

                clip_path = clip.get("path")
                if clip_path and clip_path not in self._clip_thumbnails:
                    self._request_clip_thumbnails(clip_path, clip.get("duration", 10.0))

                # Video Clip capsule with white border
                self.timeline_canvas.create_rectangle(
                    c_start_x, vy1 + 2, c_end_x, vy2 - 2,
                    fill="#0f172a", outline=c_outline, width=c_bw,
                    tags=(c_tag, "video_clip_block")
                )

                # Draw thumbnails sequence (filmstrip) covering 100% of the clip box
                tk_thumbs = self._clip_thumbnails.get(clip_path, [])
                if tk_thumbs:
                    clip_w = max(10, c_end_x - c_start_x - 6)
                    first_thumb_w = tk_thumbs[0][2] if tk_thumbs else 55
                    num_slots = max(1, int(math.ceil(clip_w / float(first_thumb_w))))

                    for i in range(num_slots):
                        cur_tx = c_start_x + 3 + i * first_thumb_w
                        if cur_tx >= c_end_x - 4:
                            break
                        # Map slot position evenly across full movie duration
                        prog = i / max(1.0, float(num_slots - 1))
                        thumb_idx = min(len(tk_thumbs) - 1, int(round(prog * (len(tk_thumbs) - 1))))
                        s_sec, tk_img, tw = tk_thumbs[thumb_idx]

                        self.timeline_canvas.create_image(
                            cur_tx, vy1 + 4,
                            image=tk_img, anchor="nw",
                            tags=(c_tag, "video_clip_block")
                        )
                        if cur_tx + tw < c_end_x - 4:
                            self.timeline_canvas.create_line(
                                cur_tx + tw, vy1 + 3, cur_tx + tw, vy2 - 3,
                                fill="#334155", width=1, tags=(c_tag, "video_clip_block")
                            )
                else:
                    # Filmstrip placeholder with perforation reel dots
                    for px in range(c_start_x + 8, c_end_x - 8, 22):
                        self.timeline_canvas.create_rectangle(px, vy1 + 6, px + 8, vy1 + 10, fill="#475569", outline="", tags=(c_tag, "video_clip_block"))
                        self.timeline_canvas.create_rectangle(px, vy2 - 10, px + 8, vy2 - 6, fill="#475569", outline="", tags=(c_tag, "video_clip_block"))

                # Video clip name badge
                badge_w = min(110, max(50, c_end_x - c_start_x - 8))
                self.timeline_canvas.create_rectangle(
                    c_start_x + 4, vy1 + 4, c_start_x + badge_w, vy1 + 20,
                    fill="#0284c7", outline="#ffffff", width=1,
                    tags=(c_tag, "video_clip_block")
                )
                self.timeline_canvas.create_text(
                    c_start_x + 8, vy1 + 12,
                    text=f"🎬 {clip['name']}",
                    fill="#ffffff",
                    anchor="w",
                    font=("Segoe UI", 7, "bold"),
                    tags=(c_tag, "video_clip_block")
                )
        else:
            self.timeline_canvas.create_rectangle(0, vy1 + 2, full_w, vy2 - 2, fill="#0f172a", outline="#ffffff", width=2)
            self.timeline_canvas.create_text(12, (vy1 + vy2) // 2, text="🎬 Video A (Drop / Open Movie to view filmstrip frames)", fill="#94a3b8", anchor="w", font=("Segoe UI", 8, "bold"))

        # 2. Draw Audio Tracks (Emerald green waveform with orange top tick markers)
        self._audio_track_y_ranges = []
        for a_idx, a_trk in enumerate(self.audio_tracks):
            a_h = audio_track_heights[a_idx]
            ay1 = curr_y
            ay2 = ay1 + max(34, a_h)
            curr_y = ay2 + 4
            self._audio_track_y_ranges.append((ay1, ay2, a_idx))

            a_col = a_trk.get("color", "#059669")
            is_muted = a_trk.get("is_muted", False)
            vol = a_trk.get("volume", 1.0)
            a_name = a_trk.get("name", f"Audio {a_idx+1}")
            a_type = a_trk.get("type", "")

            lane_bg = "#181a20" if is_muted else "#042f2e"
            outline_col = "#334155" if is_muted else "#0f766e"

            self.timeline_canvas.create_rectangle(0, ay1, full_w, ay2, fill=lane_bg, outline=outline_col, width=1)
            mute_icon = "🔇 Muted" if is_muted else "🔊 Active"
            vol_str = f"Vol: {int(vol*100)}%"

            mute_tag = f"mute_btn_{a_idx}"
            self.timeline_canvas.create_text(
                8, ay1 + 10,
                text=f"A{a_idx+1} {mute_icon} | {a_name} ({vol_str})",
                fill="#94a3b8" if is_muted else "#2dd4bf",
                anchor="w",
                font=("Segoe UI", 7, "bold"),
                tags=mute_tag
            )

            if (a_type == "dub" or a_idx == 1) and not is_muted:
                a_l_map = audio_lane_maps[a_idx]
                for s_idx, sub in enumerate(self.subtitles_data):
                    sub_id = sub.get("id", s_idx + 1)
                    s_start = sub.get("start", 0.0)
                    s_end = sub.get("end", 0.0)
                    dur = max(0.2, s_end - s_start)
                    vx1 = int(s_start * self.zoom_px_per_sec)
                    vx2 = max(vx1 + 28, int(s_end * self.zoom_px_per_sec))
                    v_lane = a_l_map.get(s_idx, 0)
                    v_sub_y1 = ay1 + 2 + v_lane * 28
                    v_sub_y2 = v_sub_y1 + 26

                    self._rendered_blocks.append((vx1, v_sub_y1, vx2, v_sub_y2, s_idx, "voice"))

                    is_active = (self._dragging_sub_idx == s_idx or getattr(self, "_selected_sub_idx", None) == s_idx)
                    v_tag = f"voice_sub_{s_idx}"

                    # Emerald/teal rounded container matching user's screenshot
                    self.timeline_canvas.create_rectangle(
                        vx1, v_sub_y1, vx2, v_sub_y2,
                        fill="#059669" if not is_active else "#0d9488",
                        outline="#ffffff" if is_active else "#34d399",
                        width=2 if is_active else 1.5,
                        tags=(v_tag, "voice_block", f"sub_{s_idx}")
                    )

                    # Top edge orange/amber accent tick marks & center waveform
                    if len(self.subtitles_data) < 200:
                        top_y = v_sub_y1 + 2
                        tick_step = 8
                        num_ticks = max(1, (vx2 - vx1 - 6) // tick_step)
                        for ti in range(num_ticks):
                            tx = vx1 + 4 + ti * tick_step
                            if tx >= vx2 - 3:
                                break
                            if ti % 2 == 0:
                                self.timeline_canvas.create_line(tx, top_y, tx, top_y + 4, fill="#f97316", width=1.5, tags=(v_tag, "voice_block"))

                        mid_y = (v_sub_y1 + v_sub_y2) // 2 + 2
                        bar_step = 5
                        bar_count = max(1, (vx2 - vx1 - 8) // bar_step)
                        for bi in range(bar_count):
                            bx = vx1 + 4 + bi * bar_step
                            if bx >= vx2 - 3:
                                break
                            norm_pos = bi / max(1, bar_count)
                            profile = math.sin(norm_pos * math.pi)
                            amp = int(2 + profile * 5)
                            self.timeline_canvas.create_line(
                                bx, mid_y - amp, bx, mid_y + amp,
                                fill="#6ee7b7", width=1.5,
                                tags=(v_tag, "voice_block")
                            )
                    else:
                        # High performance center stripe for long movies (>200 subs)
                        mid_y = (v_sub_y1 + v_sub_y2) // 2 + 2
                        self.timeline_canvas.create_line(
                            vx1 + 4, mid_y, vx2 - 4, mid_y,
                            fill="#34d399", width=2,
                            tags=(v_tag, "voice_block")
                        )

                    # Floating duration badge pill (e.g. 00:34:14 in user image)
                    pill_text = f"{format_timestamp(s_start)[3:8]}"
                    if vx2 - vx1 > 48:
                        badge_w = min(110, max(50, vx2 - vx1 - 8))
                        self.timeline_canvas.create_rectangle(
                            vx1 + 4, v_sub_y1 + 4, vx1 + badge_w, v_sub_y1 + 18,
                            fill="#064e3b", outline="#10b981", width=1,
                            tags=(v_tag, "voice_block")
                        )
                        self.timeline_canvas.create_text(
                            vx1 + 7, v_sub_y1 + 11,
                            text=f"🎙️ #{sub_id} {pill_text}",
                            fill="#ffffff",
                            anchor="w",
                            font=("Segoe UI", 6, "bold"),
                            tags=(v_tag, "voice_block")
                        )
            elif (a_type == "original" or a_idx == 0) and not is_muted:
                mid_y = (ay1 + ay2) // 2 + 2
                for wx in range(140, full_w, 4):
                    # Top orange ticks
                    if wx % 12 == 0:
                        self.timeline_canvas.create_line(wx, ay1 + 3, wx, ay1 + 7, fill="#f97316", width=1.5)
                    amp = int(3 + math.sin(wx * 0.08) * 5 + math.sin(wx * 0.23) * 3)
                    self.timeline_canvas.create_line(wx, mid_y - amp, wx, mid_y + amp, fill="#10b981", width=1.5)
            elif not is_muted:
                mid_y = (ay1 + ay2) // 2
                for wx in range(140, full_w, 5):
                    amp = int(3 + math.sin(wx * 0.12 + a_idx) * 3)
                    self.timeline_canvas.create_line(wx, mid_y - amp, wx, mid_y + amp, fill=a_col, width=1)

        # 3. Draw Dynamic CC Tracks (Khmer subtitle blocks)
        self._cc_track_y_ranges = []
        for idx, cc_trk in enumerate(self.cc_tracks):
            t_h = cc_track_heights[idx]
            ty1 = curr_y
            ty2 = ty1 + t_h - 2
            curr_y = ty2 + 4
            self._cc_track_y_ranges.append((ty1, ty2, idx))

            trk_color = cc_trk.get("color", "#db2777")
            trk_name = cc_trk.get("name", f"CC {idx+1}")

            self.timeline_canvas.create_rectangle(0, ty1, full_w, ty2, fill="#22101b", outline="#831843", width=1)
            self.timeline_canvas.create_text(8, ty1 + 12, text=f"T{idx+1} {trk_name}", fill="#f472b6", anchor="w", font=("Segoe UI", 7, "bold"))

            subs_to_draw = cc_trk.get("subtitles") or (self.subtitles_data if idx == 0 else [])
            l_map = cc_lane_maps[idx]

            for s_idx, sub in enumerate(subs_to_draw):
                x1 = int(sub["start"] * self.zoom_px_per_sec)
                x2 = max(x1 + 18, int(sub["end"] * self.zoom_px_per_sec))
                lane = l_map.get(s_idx, 0)
                sub_y1 = ty1 + 2 + lane * 24
                sub_y2 = sub_y1 + 21

                self._rendered_blocks.append((x1, sub_y1, x2, sub_y2, s_idx, "cc"))

                sub_tag = f"sub_{s_idx}"
                is_active = (self._dragging_sub_idx == s_idx or getattr(self, "_selected_sub_idx", None) == s_idx)
                cc_fill = "#f43f5e" if is_active else trk_color
                cc_border = "#fef08a" if is_active else "#f43f5e"
                cc_bw = 2 if is_active else 1

                self.timeline_canvas.create_rectangle(
                    x1, sub_y1, x2, sub_y2,
                    fill=cc_fill, outline=cc_border, width=cc_bw,
                    tags=(sub_tag, "cc_block")
                )
                txt = sub.get("translated", "")[:14]
                self.timeline_canvas.create_text(
                    x1 + 4, (sub_y1 + sub_y2) // 2,
                    text=txt,
                    fill="#ffffff",
                    anchor="w",
                    font=(self.cc_font_family, 7),
                    tags=(sub_tag, "cc_block")
                )

        # 4. Red Playhead spanning continuously across all rows
        self._timeline_total_h = max(200, curr_y + 16)
        self.timeline_canvas.config(scrollregion=(0, 0, total_width, self._timeline_total_h))

        head_x = int(self.current_sec * self.zoom_px_per_sec)
        self.timeline_canvas.create_line(head_x, 0, head_x, self._timeline_total_h, fill="#ef4444", width=2, tags="playhead")
        self.timeline_canvas.create_oval(
            head_x - 7, 1,
            head_x + 7, 15,
            fill="#0f172a", outline="#ef4444", width=2, tags="playhead_top"
        )
        self.timeline_canvas.create_text(
            head_x, 8,
            text=f"{int(self.current_sec)}",
            fill="#ffffff", font=("Segoe UI", 7, "bold"), tags="playhead_top"
        )

    def _update_playhead_pos(self):
        head_x = int(self.current_sec * self.zoom_px_per_sec)
        max_h = getattr(self, "_timeline_total_h", 180)
        self.timeline_canvas.coords("playhead", head_x, 0, head_x, max_h)
        self.timeline_canvas.delete("playhead_top")
        self.timeline_canvas.create_polygon(
            head_x - 6, 0,
            head_x + 6, 0,
            head_x, 10,
            fill="#ef4444", outline="", tags="playhead_top"
        )

    def _find_sub_at_coords(self, x: float, y: float = None):
        """2D box hit test with fallback to 1D range for accurate click/drag on staggered lanes"""
        if y is not None and hasattr(self, "_rendered_blocks") and self._rendered_blocks:
            for rx1, ry1, rx2, ry2, s_idx, b_type in reversed(self._rendered_blocks):
                if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                    return s_idx
        for idx, sub in enumerate(self.subtitles_data):
            x1 = int(sub["start"] * self.zoom_px_per_sec)
            x2 = max(x1 + 18, int(sub["end"] * self.zoom_px_per_sec))
            if x1 <= x <= x2:
                return idx
        return None

    def _apply_magnetic_snap(self, target_time: float, exclude_sub_idx: int = None, snap_px: float = 10.0) -> float:
        """
        Magnetic Snap Engine:
        Snaps candidate timestamp to playhead, clip start, or clip end within snap_px threshold (~0.15s - 0.25s)
        """
        snap_thresh = snap_px / max(1.0, float(self.zoom_px_per_sec))
        best_t = target_time
        min_dist = snap_thresh

        # 1. Snap to current Playhead
        dist_playhead = abs(target_time - self.current_sec)
        if dist_playhead < min_dist:
            best_t = self.current_sec
            min_dist = dist_playhead

        # 2. Snap to neighbor Subtitles & Audio Voice blocks
        for idx, sub in enumerate(self.subtitles_data):
            if idx == exclude_sub_idx:
                continue
            for boundary_t in (sub.get("start", 0.0), sub.get("end", 0.0)):
                d = abs(target_time - boundary_t)
                if d < min_dist:
                    best_t = boundary_t
                    min_dist = d

        # 3. Snap to Video Clips
        for clip in self.video_clips:
            c_start = clip.get("timeline_start", 0.0)
            c_end = c_start + clip.get("duration", 0.0)
            for boundary_t in (c_start, c_end):
                d = abs(target_time - boundary_t)
                if d < min_dist:
                    best_t = boundary_t
                    min_dist = d

        return best_t

    def _on_canvas_motion(self, event):
        """
        Detects hover over clip edges to show Trim Double Arrow Cursor (sb_h_double_arrow)
        """
        if getattr(self, "_trim_active", None) or getattr(self, "_dragging_sub_idx", None):
            return

        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)

        # Check edge hover on CC / Voice rendered blocks (within 7 pixels of left/right border)
        if hasattr(self, "_rendered_blocks") and self._rendered_blocks:
            for rx1, ry1, rx2, ry2, s_idx, b_type in reversed(self._rendered_blocks):
                if ry1 <= canvas_y <= ry2:
                    if abs(canvas_x - rx1) <= 7:
                        self.timeline_canvas.configure(cursor="sb_h_double_arrow")
                        self._hover_trim = ("start", s_idx, b_type)
                        return
                    elif abs(canvas_x - rx2) <= 7:
                        self.timeline_canvas.configure(cursor="sb_h_double_arrow")
                        self._hover_trim = ("end", s_idx, b_type)
                        return

        # Check edge hover on Video clips
        if hasattr(self, "_rendered_video_clips") and self._rendered_video_clips:
            for vx1, vy1, vx2, vy2, c_idx in self._rendered_video_clips:
                if vy1 <= canvas_y <= vy2:
                    if abs(canvas_x - vx1) <= 7:
                        self.timeline_canvas.configure(cursor="sb_h_double_arrow")
                        self._hover_trim = ("v_start", c_idx, "video")
                        return
                    elif abs(canvas_x - vx2) <= 7:
                        self.timeline_canvas.configure(cursor="sb_h_double_arrow")
                        self._hover_trim = ("v_end", c_idx, "video")
                        return

        self._hover_trim = None
        # Hand cursor over ruler
        if canvas_y <= 24:
            self.timeline_canvas.configure(cursor="hand2")
        else:
            self.timeline_canvas.configure(cursor="")

    def _on_canvas_click(self, event):
        self.timeline_canvas.focus_set()
        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)

        # 1. Edge Trim Initiation (Drag Clip Edge to Trim start or end)
        if getattr(self, "_hover_trim", None):
            t_edge, s_idx, b_type = self._hover_trim
            if b_type in ("cc", "voice") and 0 <= s_idx < len(self.subtitles_data):
                sub = self.subtitles_data[s_idx]
                self._trim_active = {
                    "edge": t_edge,
                    "idx": s_idx,
                    "orig_start": sub["start"],
                    "orig_end": sub["end"],
                    "start_x": canvas_x
                }
                self._selected_sub_idx = s_idx
                self._selected_clip_idx = None
                self.redraw_timeline()
                return

        # 2. Check if clicking on Audio Track Mute toggle
        if hasattr(self, "_audio_track_y_ranges") and canvas_x < 140:
            for ay1, ay2, a_idx in self._audio_track_y_ranges:
                if ay1 <= canvas_y <= ay2:
                    if self.on_toggle_audio_mute:
                        self.on_toggle_audio_mute(a_idx)
                    elif 0 <= a_idx < len(self.audio_tracks):
                        self.audio_tracks[a_idx]["is_muted"] = not self.audio_tracks[a_idx]["is_muted"]
                        self.redraw_timeline()
                    return

        # 3. Check if clicking on Video Clip (Select Clip)
        if hasattr(self, "_rendered_video_clips"):
            for vx1, vy1, vx2, vy2, c_idx in self._rendered_video_clips:
                if vx1 <= canvas_x <= vx2 and vy1 <= canvas_y <= vy2:
                    self._selected_clip_idx = c_idx
                    self._selected_sub_idx = None
                    self._dragging_sub_idx = None
                    self.redraw_timeline()
                    if c_idx < len(self.video_clips):
                        t_start = self.video_clips[c_idx].get("timeline_start", 0.0)
                        self.current_sec = t_start
                        self._update_playhead_pos()
                        self.on_seek(t_start)
                    return

        # 4. Accurate 2D hit test on CC and Voice blocks (Select Clip & Prepare Move Drag)
        clicked_idx = self._find_sub_at_coords(canvas_x, canvas_y)
        if clicked_idx is not None and 0 <= clicked_idx < len(self.subtitles_data):
            self._selected_sub_idx = clicked_idx
            self._selected_clip_idx = None
            self._dragging_sub_idx = clicked_idx
            self._drag_sub_start_x = canvas_x
            sub = self.subtitles_data[clicked_idx]
            self._drag_sub_orig_start = sub["start"]
            self._drag_sub_orig_end = sub["end"]
            self.redraw_timeline()
            if self.on_select_sub:
                self.on_select_sub(clicked_idx, sub["start"])
            return

        # 5. Clicking on Timeline Ruler or empty workspace: Seek Playhead & Clear Clip Selection
        self._dragging_sub_idx = None
        self._selected_clip_idx = None
        self._selected_sub_idx = None
        sec = max(0.0, min(self.duration_sec, canvas_x / self.zoom_px_per_sec))
        self.current_sec = sec
        self._update_playhead_pos()
        self.redraw_timeline()
        self.on_seek(sec)

    def _on_canvas_drag(self, event):
        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)

        # 1. Trimming Clip Edge with Magnetic Snapping
        if getattr(self, "_trim_active", None):
            edge = self._trim_active["edge"]
            s_idx = self._trim_active["idx"]
            sub = self.subtitles_data[s_idx]
            dx = canvas_x - self._trim_active["start_x"]
            dt = dx / self.zoom_px_per_sec

            if edge == "start":
                candidate = max(0.0, self._trim_active["orig_start"] + dt)
                candidate = self._apply_magnetic_snap(candidate, exclude_sub_idx=s_idx)
                if candidate < sub["end"] - 0.2:
                    sub["start"] = round(candidate, 2)
                    self.redraw_timeline()
                    if self.on_move_sub_timing:
                        self.on_move_sub_timing(s_idx, sub["start"], sub["end"])
            elif edge == "end":
                candidate = max(0.2, self._trim_active["orig_end"] + dt)
                candidate = self._apply_magnetic_snap(candidate, exclude_sub_idx=s_idx)
                if candidate > sub["start"] + 0.2:
                    sub["end"] = round(candidate, 2)
                    self.redraw_timeline()
                    if self.on_move_sub_timing:
                        self.on_move_sub_timing(s_idx, sub["start"], sub["end"])
            return

        # 2. Moving Clip across time with Magnetic Snap and Multi-Track Drop
        if self._dragging_sub_idx is not None and 0 <= self._dragging_sub_idx < len(self.subtitles_data):
            dx = canvas_x - self._drag_sub_start_x
            dt = dx / self.zoom_px_per_sec
            sub = self.subtitles_data[self._dragging_sub_idx]
            dur = max(0.2, self._drag_sub_orig_end - self._drag_sub_orig_start)
            raw_start = max(0.0, self._drag_sub_orig_start + dt)

            # Magnetic Snap to Playhead or neighbor clip boundaries
            new_start = self._apply_magnetic_snap(raw_start, exclude_sub_idx=self._dragging_sub_idx)
            new_end = round(new_start + dur, 2)
            sub["start"] = round(new_start, 2)
            sub["end"] = new_end

            # Drag Clip to Another Track (Vertical detection on CC tracks)
            if hasattr(self, "_cc_track_y_ranges") and self._cc_track_y_ranges:
                for ty1, ty2, trk_idx in self._cc_track_y_ranges:
                    if ty1 <= canvas_y <= ty2:
                        sub["track_id"] = trk_idx
                        break

            self.redraw_timeline()
            if self.on_move_sub_timing:
                self.on_move_sub_timing(self._dragging_sub_idx, new_start, new_end)
            return

        # 3. Dragging Playhead / Ruler Scrubbing
        sec = max(0.0, min(self.duration_sec, canvas_x / self.zoom_px_per_sec))
        self.current_sec = sec
        self._update_playhead_pos()
        self.on_seek(sec)

    def _on_canvas_release(self, event):
        # Commit edge trim
        if getattr(self, "_trim_active", None):
            s_idx = self._trim_active["idx"]
            if 0 <= s_idx < len(self.subtitles_data):
                sub = self.subtitles_data[s_idx]
                if self.on_commit_sub_timing:
                    self.on_commit_sub_timing(s_idx, sub["start"], sub["end"])
            self._trim_active = None
            self.redraw_timeline()
            return

        # Commit move clip
        if self._dragging_sub_idx is not None:
            if 0 <= self._dragging_sub_idx < len(self.subtitles_data):
                sub = self.subtitles_data[self._dragging_sub_idx]
                if self.on_commit_sub_timing:
                    self.on_commit_sub_timing(self._dragging_sub_idx, sub["start"], sub["end"])
            self._dragging_sub_idx = None
            self.redraw_timeline()

    def _on_canvas_double_click(self, event):
        """Double Click: Open Edit Dialog for clicked Clip"""
        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)
        clicked_idx = self._find_sub_at_coords(canvas_x, canvas_y)
        if clicked_idx is not None and 0 <= clicked_idx < len(self.subtitles_data):
            self._selected_sub_idx = clicked_idx
            self.redraw_timeline()
            self._show_properties_dialog(clicked_idx)

    def _on_canvas_middle_press(self, event):
        """Middle Click + Drag: Smooth Pan Timeline Horizontal View"""
        self._pan_start_x = event.x
        self.timeline_canvas.configure(cursor="fleur")

    def _on_canvas_middle_drag(self, event):
        dx = event.x - self._pan_start_x
        self.timeline_canvas.xview_scroll(int(-dx / 2), "units")
        self._pan_start_x = event.x

    def _on_canvas_middle_release(self, event):
        self.timeline_canvas.configure(cursor="")

    def _on_canvas_mousewheel(self, event):
        """
        Timeline Mouse Wheel Controls:
        - Ctrl + Wheel: Zoom In / Out Timeline
        - Shift + Wheel: Horizontal Scroll
        - Normal Wheel: Vertical Scroll
        """
        if event.state & 0x0004:
            # Ctrl + Mouse Wheel: Zoom
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        elif event.state & 0x0001:
            # Shift + Mouse Wheel: Horizontal Scroll
            self.timeline_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            # Normal Mouse Wheel: Vertical Scroll
            self.timeline_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_timeline_delete(self, event):
        """Delete / Backspace Shortcut: Remove selected clip"""
        if self._selected_sub_idx is not None:
            self._delete_sub(self._selected_sub_idx)
        elif self._selected_clip_idx is not None:
            if self.on_delete_clip:
                self.on_delete_clip()

    def _on_timeline_escape(self, event):
        """Escape Shortcut: Deselect active clip and overlay objects"""
        self._selected_sub_idx = None
        self._selected_clip_idx = None
        self._deselect_all_objects()
        self.redraw_timeline()

    # ------------------ TIMELINE SELECTION & RIGHT-CLICK PROPERTIES ------------------
    def _on_canvas_right_click(self, event):
        """Right click context menu for timeline clips and properties"""
        canvas_x = self.timeline_canvas.canvasx(event.x)
        canvas_y = self.timeline_canvas.canvasy(event.y)
        clicked_idx = self._find_sub_at_coords(canvas_x, canvas_y)

        if clicked_idx is not None and 0 <= clicked_idx < len(self.subtitles_data):
            self._selected_sub_idx = clicked_idx
            self.redraw_timeline()
            sub = self.subtitles_data[clicked_idx]
            if self.on_select_sub:
                self.on_select_sub(clicked_idx, sub["start"])
            self._show_context_menu(event, clicked_idx)
        else:
            # General timeline background menu
            gen_menu = tk.Menu(self, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
            gen_menu.add_command(label="✂️ Split at Playhead", command=self._split_at_playhead)
            gen_menu.add_command(label="🔍 Zoom In (Ctrl +)", command=self.zoom_in)
            gen_menu.add_command(label="🔍 Zoom Out (Ctrl -)", command=self.zoom_out)
            gen_menu.tk_popup(event.x_root, event.y_root)

    def _show_context_menu(self, event, sub_idx: int):
        sub = self.subtitles_data[sub_idx]
        sub_id = sub.get("id", sub_idx + 1)
        txt_preview = sub.get("translated", "")[:24]

        menu = tk.Menu(self, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        menu.add_command(label=f"🎬 #{sub_id}: \"{txt_preview}...\"", state="disabled")
        menu.add_separator()
        menu.add_command(label="✂️ Split Clip at Playhead (បំបែក)", command=self._split_at_playhead)
        menu.add_command(label="⚡ Auto-Sync Speed to Video (លៃល្បឿនអោយទាន់)", command=lambda: self._auto_sync_speed(sub_idx))

        # Speed rate submenu
        speed_menu = tk.Menu(menu, tearoff=0, bg="#181a20", fg="#f1f5f9", activebackground="#2563eb", activeforeground="#ffffff", font=("Segoe UI", 9))
        for rate_lbl, rate_val in [("Normal (+0%)", "+0%"), ("Fast (+15%)", "+15%"), ("Faster (+25%)", "+25%"), ("Ultra (+35%)", "+35%"), ("High (+50%)", "+50%")]:
            speed_menu.add_command(label=rate_lbl, command=lambda r=rate_val: self._change_sub_speed(sub_idx, r))
        menu.add_cascade(label="🚀 Change Speed Rate (ប្ដូរល្បឿន)", menu=speed_menu)

        menu.add_command(label="✏️ Quick Edit Text (កែអត្ថបទ)...", command=lambda: self._show_properties_dialog(sub_idx))
        menu.add_command(label="🔊 Audition / Listen (ស្ដាប់សំឡេង)", command=lambda: self._audition_voice(sub_idx))
        menu.add_command(label="📋 Duplicate Clip (ចម្លង)", command=lambda: self._duplicate_sub(sub_idx))
        menu.add_command(label="🗑️ Delete Clip (លុបចោល)", command=lambda: self._delete_sub(sub_idx))
        menu.add_separator()
        menu.add_command(label="⚙️ Properties (លក្ខណៈសម្បត្តិ)...", command=lambda: self._show_properties_dialog(sub_idx))

        menu.tk_popup(event.x_root, event.y_root)

    def _show_properties_dialog(self, sub_idx: int):
        if not (0 <= sub_idx < len(self.subtitles_data)):
            return
        sub = self.subtitles_data[sub_idx]
        sub_id = sub.get("id", sub_idx + 1)

        win = ctk.CTkToplevel(self)
        win.title(f"⚙️ Subtitle & Voice Properties (#{sub_id})")
        win.geometry("520x440")
        win.configure(fg_color="#0e1014")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        lbl_title = ctk.CTkLabel(
            win,
            text=f"⚙️ Properties & Audio Sync: Line #{sub_id}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_title.pack(padx=16, pady=(16, 8), anchor="w")

        form = ctk.CTkFrame(win, fg_color="#181a20", corner_radius=6)
        form.pack(fill="both", expand=True, padx=16, pady=8)
        form.grid_columnconfigure(1, weight=1)

        # 1. Timing
        ctk.CTkLabel(form, text="⏱️ Start Time (sec):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").grid(row=0, column=0, padx=10, pady=6, sticky="w")
        ent_start = ctk.CTkEntry(form, height=26, font=ctk.CTkFont(size=11))
        ent_start.insert(0, str(sub.get("start", 0.0)))
        ent_start.grid(row=0, column=1, padx=10, pady=6, sticky="ew")

        ctk.CTkLabel(form, text="⏱️ End Time (sec):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").grid(row=1, column=0, padx=10, pady=6, sticky="w")
        ent_end = ctk.CTkEntry(form, height=26, font=ctk.CTkFont(size=11))
        ent_end.insert(0, str(sub.get("end", 0.0)))
        ent_end.grid(row=1, column=1, padx=10, pady=6, sticky="ew")

        dur_val = round(sub.get("end", 0.0) - sub.get("start", 0.0), 2)
        lbl_dur = ctk.CTkLabel(form, text=f"⏳ Slot: {dur_val}s", font=ctk.CTkFont(size=10, weight="bold"), text_color="#34d399")
        lbl_dur.grid(row=1, column=2, padx=10, pady=6, sticky="w")

        # 2. Text & Font
        f_pick_row = ctk.CTkFrame(form, fg_color="transparent")
        f_pick_row.grid(row=2, column=0, columnspan=3, padx=10, pady=(6, 2), sticky="ew")
        ctk.CTkLabel(f_pick_row, text="🇰🇭 Khmer Subtitle Text:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(side="left")

        all_khmer_fonts = get_installed_khmer_fonts()
        combo_prop_font = ctk.CTkComboBox(
            f_pick_row,
            values=all_khmer_fonts,
            width=150,
            height=22,
            font=ctk.CTkFont(size=10),
            dropdown_font=ctk.CTkFont(size=10),
            command=lambda f: txt_km.configure(font=ctk.CTkFont(family=f, size=13))
        )
        combo_prop_font.set(self.cc_font_family)
        combo_prop_font.pack(side="right")
        ctk.CTkLabel(f_pick_row, text="Font:", font=ctk.CTkFont(size=10), text_color="#94a3b8").pack(side="right", padx=(0, 4))

        txt_km = ctk.CTkTextbox(form, height=65, font=ctk.CTkFont(family=self.cc_font_family, size=13), wrap="word")
        txt_km.insert("1.0", sub.get("translated", ""))
        txt_km.grid(row=3, column=0, columnspan=3, padx=10, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="🌐 Original:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").grid(row=4, column=0, padx=10, pady=6, sticky="w")
        lbl_orig = ctk.CTkLabel(form, text=sub.get("original", "")[:35], font=ctk.CTkFont(size=10), text_color="#cbd5e1", anchor="w")
        lbl_orig.grid(row=4, column=1, columnspan=2, padx=10, pady=6, sticky="w")

        # 3. Speed Rate
        ctk.CTkLabel(form, text="🚀 Speed Rate:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").grid(row=5, column=0, padx=10, pady=6, sticky="w")
        combo_rate = ctk.CTkComboBox(form, values=["+0%", "+10%", "+15%", "+20%", "+25%", "+30%", "+40%", "+50%"], width=120, height=26)
        combo_rate.set(sub.get("rate", "+0%"))
        combo_rate.grid(row=5, column=1, padx=10, pady=6, sticky="w")

        # 4. Audio status
        a_file = sub.get("audio_file")
        has_audio = bool(a_file and os.path.exists(a_file))
        st_txt = "✅ Audio Ready" if has_audio else "⚠️ Voice Not Generated"
        st_col = "#34d399" if has_audio else "#f59e0b"
        lbl_astatus = ctk.CTkLabel(form, text=st_txt, font=ctk.CTkFont(size=10, weight="bold"), text_color=st_col)
        lbl_astatus.grid(row=5, column=2, padx=10, pady=6, sticky="w")

        # Buttons
        btn_box = ctk.CTkFrame(win, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(4, 16))

        def _do_audition():
            if self.on_audition_sub:
                self.on_audition_sub(sub)

        def _do_auto_fit():
            try:
                s_t = float(ent_start.get())
                e_t = float(ent_end.get())
                t_dur = max(0.4, e_t - s_t)
                km_val = txt_km.get("1.0", "end-1c").strip()
                from services.dubbing import DubbingEngine
                calc_rate = DubbingEngine.calculate_auto_rate(km_val, t_dur)
                combo_rate.set(calc_rate)
                if self.on_auto_sync_speed:
                    self.on_auto_sync_speed(sub_idx, t_dur, km_val)
                lbl_astatus.configure(text=f"⚡ Auto-Synced: {calc_rate}", text_color="#38bdf8")
            except Exception as ex:
                messagebox.showerror("Error", f"Auto sync failed: {ex}")

        def _do_save():
            try:
                s_t = round(float(ent_start.get()), 2)
                e_t = round(float(ent_end.get()), 2)
                km_val = txt_km.get("1.0", "end-1c").strip()
                rate_val = combo_rate.get()
                sub["start"] = s_t
                sub["end"] = e_t
                sub["translated"] = km_val
                sub["rate"] = rate_val

                if self.on_apply_edit:
                    self.on_apply_edit(sub_idx, km_val, s_t, e_t, rate_val)
                elif self.on_commit_sub_timing:
                    self.on_commit_sub_timing(sub_idx, s_t, e_t)

                self.redraw_timeline()
                win.destroy()
            except Exception as ex:
                messagebox.showerror("Error", f"Invalid values: {ex}")

        btn_fit = ctk.CTkButton(btn_box, text="⚡ Auto-Fit Speed", fg_color="#0d9488", hover_color="#0f766e", width=120, command=_do_auto_fit)
        btn_fit.pack(side="left", padx=4)

        btn_play = ctk.CTkButton(btn_box, text="🔊 Listen", fg_color="#334155", hover_color="#475569", width=80, command=_do_audition)
        btn_play.pack(side="left", padx=4)

        btn_save = ctk.CTkButton(btn_box, text="💾 Save Changes", fg_color="#2563eb", hover_color="#1d4ed8", width=110, command=_do_save)
        btn_save.pack(side="right", padx=4)

        btn_cancel = ctk.CTkButton(btn_box, text="Close", fg_color="#1e293b", hover_color="#334155", width=70, command=win.destroy)
        btn_cancel.pack(side="right", padx=4)

    def _auto_sync_speed(self, sub_idx: int):
        if 0 <= sub_idx < len(self.subtitles_data):
            sub = self.subtitles_data[sub_idx]
            dur = max(0.4, sub["end"] - sub["start"])
            km = sub.get("translated", "")
            if self.on_auto_sync_speed:
                self.on_auto_sync_speed(sub_idx, dur, km)

    def _change_sub_speed(self, sub_idx: int, rate: str):
        if 0 <= sub_idx < len(self.subtitles_data):
            sub = self.subtitles_data[sub_idx]
            sub["rate"] = rate
            if self.on_apply_edit:
                self.on_apply_edit(sub_idx, sub.get("translated", ""), sub["start"], sub["end"], rate)

    def _audition_voice(self, sub_idx: int):
        if 0 <= sub_idx < len(self.subtitles_data):
            sub = self.subtitles_data[sub_idx]
            if self.on_audition_sub:
                self.on_audition_sub(sub)

    def _duplicate_sub(self, sub_idx: int):
        if self.on_duplicate_sub:
            self.on_duplicate_sub(sub_idx)

    def _delete_sub(self, sub_idx: int):
        if self.on_delete_sub:
            self.on_delete_sub(sub_idx)

    def set_time_pos(self, sec: float):
        self.current_sec = sec
        self._update_playhead_pos()

    def update_frame(self, pil_image: Image.Image, current_sec: float, total_sec: float):
        self.last_pil_img = pil_image
        if pil_image:
            self._render_scaled_image(pil_image)

        self.current_sec = current_sec
        self._update_playhead_pos()

        cur_str = time.strftime('%H:%M:%S', time.gmtime(current_sec))
        dur_str = time.strftime('%H:%M:%S', time.gmtime(total_sec))
        self.lbl_timecode.configure(text=f"{cur_str} / {dur_str}")

    def _render_scaled_image(self, pil_image: Image.Image):
        try:
            cont_w = max(320, self.video_container.winfo_width())
            cont_h = max(200, self.video_container.winfo_height())

            img_w, img_h = pil_image.size
            if img_w <= 0 or img_h <= 0:
                return

            ratio_val = PREVIEW_ASPECT_RATIOS.get(self.active_aspect_ratio_key)

            if ratio_val is not None:
                # Aspect Ratio Framing (e.g. 9:16 Portrait for TikTok / Reels, 16:9 Landscape)
                if cont_w / cont_h > ratio_val:
                    vp_h = cont_h
                    vp_w = max(20, int(vp_h * ratio_val))
                else:
                    vp_w = cont_w
                    vp_h = max(20, int(vp_w / ratio_val))

                scale = min(vp_w / img_w, vp_h / img_h)
                target_w = max(10, int(img_w * scale))
                target_h = max(10, int(img_h * scale))

                resized = pil_image.resize((target_w, target_h), Image.Resampling.BILINEAR)

                frame_bg = Image.new("RGB", (vp_w, vp_h), (12, 14, 18))
                paste_x = (vp_w - target_w) // 2
                paste_y = (vp_h - target_h) // 2
                frame_bg.paste(resized, (paste_x, paste_y))

                full_canvas = Image.new("RGB", (cont_w, cont_h), (0, 0, 0))
                vx1 = (cont_w - vp_w) // 2
                vy1 = (cont_h - vp_h) // 2
                full_canvas.paste(frame_bg, (vx1, vy1))

                origin_x = vx1 + paste_x
                origin_y = vy1 + paste_y
                self._last_video_rect = (origin_x, origin_y, target_w, target_h)

                # Draw Green Frame Guide on the Canvas
                if getattr(self, "show_green_frame", True):
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(full_canvas)
                    vx2 = vx1 + vp_w - 1
                    vy2 = vy1 + vp_h - 1
                    # Bright emerald green border around the selected aspect ratio frame (ខ្នាតវីដេអូ)
                    draw.rectangle([vx1, vy1, vx2, vy2], outline="#10b981", width=2)
                    # Precision corner accents
                    c_len = max(6, min(16, vp_w // 8, vp_h // 8))
                    draw.line([(vx1, vy1), (vx1 + c_len, vy1)], fill="#34d399", width=3)
                    draw.line([(vx1, vy1), (vx1, vy1 + c_len)], fill="#34d399", width=3)
                    draw.line([(vx2, vy1), (vx2 - c_len, vy1)], fill="#34d399", width=3)
                    draw.line([(vx2, vy1), (vx2, vy1 + c_len)], fill="#34d399", width=3)
                    draw.line([(vx1, vy2), (vx1 + c_len, vy2)], fill="#34d399", width=3)
                    draw.line([(vx1, vy2), (vx1, vy2 - c_len)], fill="#34d399", width=3)
                    draw.line([(vx2, vy2), (vx2 - c_len, vy2)], fill="#34d399", width=3)
                    draw.line([(vx2, vy2), (vx2, vy2 - c_len)], fill="#34d399", width=3)

                b = self.color_grading.get("brightness", 0.0)
                c = self.color_grading.get("contrast", 1.0)
                if b != 0.0 or c != 1.0:
                    import numpy as np
                    arr = np.array(full_canvas)
                    arr = cv2.convertScaleAbs(arr, alpha=c, beta=int(b * 100))
                    full_canvas = Image.fromarray(arr)

                self.current_tk_photo = ImageTk.PhotoImage(image=full_canvas)
            else:
                # Auto - Fit Original Video
                scale = min(cont_w / img_w, cont_h / img_h)
                target_w = max(10, int(img_w * scale))
                target_h = max(10, int(img_h * scale))

                origin_x = (cont_w - target_w) // 2
                origin_y = (cont_h - target_h) // 2
                self._last_video_rect = (origin_x, origin_y, target_w, target_h)

                resized = pil_image.resize((target_w, target_h), Image.Resampling.BILINEAR)

                full_canvas = Image.new("RGB", (cont_w, cont_h), (0, 0, 0))
                full_canvas.paste(resized, (origin_x, origin_y))

                # Draw Green Frame Guide on the Canvas
                if getattr(self, "show_green_frame", True):
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(full_canvas)
                    rx2 = origin_x + target_w - 1
                    ry2 = origin_y + target_h - 1
                    draw.rectangle([origin_x, origin_y, rx2, ry2], outline="#10b981", width=2)
                    # Precision corner accents
                    c_len = max(6, min(16, target_w // 8, target_h // 8))
                    draw.line([(origin_x, origin_y), (origin_x + c_len, origin_y)], fill="#34d399", width=3)
                    draw.line([(origin_x, origin_y), (origin_x, origin_y + c_len)], fill="#34d399", width=3)
                    draw.line([(rx2, origin_y), (rx2 - c_len, origin_y)], fill="#34d399", width=3)
                    draw.line([(rx2, origin_y), (rx2, origin_y + c_len)], fill="#34d399", width=3)
                    draw.line([(origin_x, ry2), (origin_x + c_len, ry2)], fill="#34d399", width=3)
                    draw.line([(origin_x, ry2), (origin_x, ry2 - c_len)], fill="#34d399", width=3)
                    draw.line([(rx2, ry2), (rx2 - c_len, ry2)], fill="#34d399", width=3)
                    draw.line([(rx2, ry2), (rx2, ry2 - c_len)], fill="#34d399", width=3)

                b = self.color_grading.get("brightness", 0.0)
                c = self.color_grading.get("contrast", 1.0)
                if b != 0.0 or c != 1.0:
                    import numpy as np
                    arr = np.array(full_canvas)
                    arr = cv2.convertScaleAbs(arr, alpha=c, beta=int(b * 100))
                    full_canvas = Image.fromarray(arr)

                self.current_tk_photo = ImageTk.PhotoImage(image=full_canvas)

            self.lbl_screen.configure(image=self.current_tk_photo, text="")
            self.lbl_screen.image = self.current_tk_photo
            self._reposition_cc_overlay()
            self._reposition_watermark()
            self.lbl_cc_overlay.lift()
            if self.watermark_config and self.watermark_config.get("path"):
                self.lbl_watermark.lift()
        except Exception:
            pass

    def toggle_collapse_preview(self):
        self.is_preview_collapsed = not self.is_preview_collapsed
        if self.is_preview_collapsed:
            self.video_container.grid_remove()
            self.grid_rowconfigure(0, weight=0)
            self.grid_rowconfigure(4, weight=1)
            self.timeline_card.configure(height=380)
            self.timeline_canvas.configure(height=280)
            self.btn_collapse.configure(text="👁️ Expand Preview", fg_color="#2563eb")
        else:
            self.video_container.grid(row=0, column=0, padx=6, pady=(6, 2), sticky="nsew")
            self.grid_rowconfigure(0, weight=1)
            self.grid_rowconfigure(4, weight=0)
            self.timeline_card.configure(height=220)
            self.timeline_canvas.configure(height=165)
            self.btn_collapse.configure(text="👁️ Collapse Preview", fg_color="#334155")
            if self.last_pil_img:
                self._render_scaled_image(self.last_pil_img)
        self.redraw_timeline()

    def set_cc_effects(self, animation: str = None, bg_style: str = None, highlight_color: str = None, text_color: str = None, border_width: int = None):
        if animation is not None:
            self.cc_animation = animation
        if bg_style is not None:
            self.cc_bg_style = bg_style
        if highlight_color is not None:
            self.cc_highlight_color = highlight_color
        if text_color is not None:
            self.cc_text_color = text_color
        if border_width is not None:
            self.cc_border_width = border_width

        bg_info = CC_BG_STYLES.get(self.cc_bg_style, {})
        bg_col = bg_info.get("color", "#090a0f")
        if bg_col == "transparent":
            self.lbl_cc_overlay.configure(fg_color="transparent")
        else:
            self.lbl_cc_overlay.configure(fg_color=bg_col)

    def update_active_subtitle(
        self,
        sub_text: str,
        is_active: bool,
        time_info: str = "",
        current_sec: float = 0.0,
        sub_start: float = 0.0,
        sub_end: float = 0.0,
        sub_id = None
    ):
        self.is_cc_active = is_active
        if is_active and sub_text:
            # 1. Background box style
            bg_info = CC_BG_STYLES.get(self.cc_bg_style, {})
            bg_col = bg_info.get("color", "#090a0f")
            is_yellow_box = bg_info.get("type") == "yellow_box"

            # 2. Text color & Karaoke Word Highlighting
            display_text = sub_text
            display_color = "#000000" if is_yellow_box else self.cc_text_color

            if "Karaoke" in self.cc_animation:
                dur = max(0.1, sub_end - sub_start)
                elapsed = max(0.0, min(dur, current_sec - sub_start))
                progress = elapsed / dur

                # Word segmentation
                if " " in sub_text:
                    tokens = sub_text.split(" ")
                else:
                    step = 4
                    tokens = [sub_text[i:i+step] for i in range(0, len(sub_text), step)] if len(sub_text) > 4 else [sub_text]

                num_tokens = max(1, len(tokens))
                active_idx = min(num_tokens - 1, int(progress * num_tokens))

                spoken = " ".join(tokens[:active_idx])
                curr_word = tokens[active_idx]
                upcoming = " ".join(tokens[active_idx+1:])

                if spoken and upcoming:
                    display_text = f"{spoken}  ▶ {curr_word} ◀  {upcoming}"
                elif spoken:
                    display_text = f"{spoken}  ▶ {curr_word} ◀"
                elif upcoming:
                    display_text = f"▶ {curr_word} ◀  {upcoming}"
                else:
                    display_text = f"▶ {curr_word} ◀"

                display_color = self.cc_highlight_color

            # 3. Popup / Bounce Animation on segment enter
            if ("Popup" in self.cc_animation or "Bounce" in self.cc_animation) and sub_id != self._last_popup_sub_id:
                self._last_popup_sub_id = sub_id
                pop_sz = min(44, self.cc_font_size + 4)
                self.lbl_cc_overlay.configure(
                    font=ctk.CTkFont(family=self.cc_font_family, size=pop_sz, weight="bold")
                )
                self.after(180, lambda: self.lbl_cc_overlay.configure(
                    font=ctk.CTkFont(family=self.cc_font_family, size=self.cc_font_size, weight="bold")
                ))

            self.lbl_cc_overlay.configure(
                text=display_text,
                text_color=display_color,
                fg_color=bg_col if bg_col != "transparent" else "transparent"
            )
            self.lbl_cc_overlay.lift()
            self.lbl_active_time.configure(text=f"⏱️ {time_info}", text_color="#38bdf8")
            self.lbl_active_text.configure(text=f"CC: {sub_text}", text_color="#f8fafc")
        else:
            self._last_popup_sub_id = None
            self.lbl_cc_overlay.configure(
                text="[ 💬 អូសរំកិលទីតាំង CC / Drag CC Overlay ]",
                text_color="#64748b",
                fg_color="#090a0f"
            )
            self.lbl_cc_overlay.lift()
            self.lbl_active_time.configure(text="⏱️ CC: [--:-- -> --:--]", text_color="#64748b")
            self.lbl_active_text.configure(text="CC: No subtitle at current timestamp (Drag CC box to move)", text_color="#64748b")

    def set_play_state(self, is_playing: bool):
        self.btn_play.configure(text="⏸ Pause" if is_playing else "▶ Play")

    def select_subtitle(self, idx: int):
        """Highlights the subtitle block on the CapCut multi-track timeline"""
        self._selected_sub_idx = idx
        self.redraw_timeline()
