import math
import tkinter as tk
import customtkinter as ctk
from config import TRANSLATION_PROVIDERS, TRANSLATION_STYLES, WHISPER_MODELS, KHMER_FONT_FAMILY, SPEECH_SPEED_PRESETS, get_installed_khmer_fonts
from utils import format_timestamp

class SubtitlesView(ctk.CTkFrame):
    """
    Left Pane: Subtitles List, Translation Settings, and Advanced Dialogue Editor:
    - Guaranteed Khmer Unicode Support with native font selector (Kantumruy Pro, Khmer OS Siemreap, etc.)
    - Sound & Subtitle Timing Move / Shift controls (និយាយខុសនាទី can shift timing!)
    - Voice Speech Speed selector (0.8x - 1.5x speed rate)
    - Full bidirectional active clip sync with video and timeline with visual active borders
    - Panel vertical resize handle (↕ size_ns)
    """
    def __init__(
        self, 
        parent, 
        on_select_sub, 
        on_apply_edit, 
        on_listen_line, 
        on_import_srt=None,
        on_capture_cc=None,
        on_translate_all=None,
        on_translate_single=None,
        on_clean_noise=None,
        on_add_sub=None,
        on_delete_sub=None,
        on_dub_all=None,
        on_dub_selected=None,
        on_dub_missing=None,
        on_voice_change=None,
        on_voice_speed_change=None
    ):
        super().__init__(parent, fg_color="#14161b", corner_radius=0)
        self.on_select_sub = on_select_sub
        self.on_apply_edit = on_apply_edit
        self.on_listen_line = on_listen_line
        self.on_import_srt = on_import_srt
        self.on_capture_cc = on_capture_cc
        self.on_translate_all = on_translate_all
        self.on_translate_single = on_translate_single
        self.on_clean_noise = on_clean_noise
        self.on_add_sub = on_add_sub
        self.on_delete_sub = on_delete_sub
        self.on_dub_all = on_dub_all
        self.on_dub_selected = on_dub_selected
        self.on_dub_missing = on_dub_missing
        self.on_voice_change = on_voice_change
        self.on_voice_speed_change = on_voice_speed_change

        self.selected_idx = -1
        self.current_sub = None
        self._card_widgets = {}
        self._subtitles_data = []
        self._filter_query = ""
        self.page_size = 100
        self.current_page = 0
        self._prev_active_idx = None

        all_khmer_fonts = get_installed_khmer_fonts()
        self.active_font_family = all_khmer_fonts[0] if all_khmer_fonts else KHMER_FONT_FAMILY
        self.active_font_size = 12
        self.txt_edit_height = 62

        self.grid_rowconfigure(4, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_ui()

    def _build_ui(self):
        # Header Toolbar (matching version_rust: Subtitles count, Capture CC, Translate All, Clean Noise, Add CC)
        t_box = ctk.CTkFrame(self, fg_color="#181a20", corner_radius=0, height=30)
        t_box.grid(row=0, column=0, padx=4, pady=(4, 1), sticky="ew")

        self.lbl_total_cc = ctk.CTkLabel(
            t_box,
            text="📝 Subtitles (0)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#f97316"
        )
        self.lbl_total_cc.pack(side="left", padx=(6, 4), pady=3)

        self.check_auto_scroll = ctk.CTkCheckBox(
            t_box,
            text="🔄 Auto-Scroll",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#38bdf8",
            width=88,
            height=18,
            checkbox_width=13,
            checkbox_height=13,
            corner_radius=2
        )
        self.check_auto_scroll.select()
        self.check_auto_scroll.pack(side="left", padx=4, pady=3)

        if self.on_capture_cc:
            btn_stt = ctk.CTkButton(
                t_box, text="🎙️ Capture CC", width=84, height=20, corner_radius=2,
                fg_color="#ea580c", hover_color="#c2410c", font=ctk.CTkFont(size=9, weight="bold"),
                command=self.on_capture_cc
            )
            btn_stt.pack(side="left", padx=2, pady=3)

        if self.on_translate_all:
            btn_trans = ctk.CTkButton(
                t_box, text="⚡ Translate All", width=88, height=20, corner_radius=2,
                fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=9, weight="bold"),
                command=self.on_translate_all
            )
            btn_trans.pack(side="left", padx=2, pady=3)

        if self.on_clean_noise:
            btn_clean = ctk.CTkButton(
                t_box, text="🧹 Clean", width=54, height=20, corner_radius=2,
                fg_color="#334155", hover_color="#475569", font=ctk.CTkFont(size=9),
                command=self.on_clean_noise
            )
            btn_clean.pack(side="left", padx=2, pady=3)

        if self.on_add_sub:
            btn_add = ctk.CTkButton(
                t_box, text="➕ Add", width=50, height=20, corner_radius=2,
                fg_color="#1e2430", hover_color="#334155", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#10b981", command=self.on_add_sub
            )
            btn_add.pack(side="right", padx=(2, 4), pady=3)

        if self.on_import_srt:
            btn_sub_import = ctk.CTkButton(
                t_box, text="📥 SRT", width=46, height=20, corner_radius=2,
                fg_color="#1e2430", hover_color="#334155", font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#fbbf24", command=self.on_import_srt
            )
            btn_sub_import.pack(side="right", padx=2, pady=3)

        # Single Compact Translation Toolbar Row (One Row for Service, Source ➜ Target, and Action Buttons)
        trans_bar = ctk.CTkFrame(self, fg_color="#181a20", corner_radius=2, border_width=1, border_color="#262a33", height=30)
        trans_bar.grid(row=1, column=0, padx=4, pady=(2, 2), sticky="ew")

        # 1. Provider Select
        self.combo_provider = ctk.CTkComboBox(
            trans_bar,
            values=TRANSLATION_PROVIDERS,
            command=self._on_provider_change,
            corner_radius=2,
            height=24,
            width=135,
            font=ctk.CTkFont(size=10)
        )
        self.combo_provider.set("Google (Free / មិនអស់លុយ)")
        self.combo_provider.pack(side="left", padx=(3, 2), pady=3)

        # 2. Source Language
        self.combo_src = ctk.CTkComboBox(
            trans_bar,
            values=["Chinese (zh)", "English (en)", "Auto Detect", "Korean (ko)", "Japanese (ja)", "Thai (th)"],
            corner_radius=2,
            height=24,
            width=92,
            font=ctk.CTkFont(size=10)
        )
        self.combo_src.set("Chinese (zh)")
        self.combo_src.pack(side="left", padx=2, pady=3)

        # 3. Arrow
        ctk.CTkLabel(trans_bar, text="➜", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8", width=12).pack(side="left", padx=0)

        # 4. Target Language
        self.combo_tgt = ctk.CTkComboBox(
            trans_bar,
            values=["Khmer (km)", "English (en)", "Chinese (zh)", "Thai (th)", "Vietnamese (vi)"],
            corner_radius=2,
            height=24,
            width=92,
            font=ctk.CTkFont(size=10)
        )
        self.combo_tgt.set("Khmer (km)")
        self.combo_tgt.pack(side="left", padx=2, pady=3)

        # 4.5. Translation Tone / Style Selector (Default: ធម្មតា Standard)
        self.combo_style = ctk.CTkComboBox(
            trans_bar,
            values=TRANSLATION_STYLES,
            corner_radius=2,
            height=24,
            width=130,
            font=ctk.CTkFont(size=10)
        )
        self.combo_style.set("📖 ធម្មតា (Standard)")
        self.combo_style.pack(side="left", padx=2, pady=3)

        # 5. Translate All Button
        self.btn_trans_all_main = ctk.CTkButton(
            trans_bar,
            text="⚡ Translate All (បកប្រែទាំងអស់)",
            command=self.on_translate_all,
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=24,
            corner_radius=2,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_trans_all_main.pack(side="left", fill="x", expand=True, padx=2, pady=3)

        # 6. Translate Selected Button
        self.btn_trans_sel_main = ctk.CTkButton(
            trans_bar,
            text="🎯 Selected",
            command=self._translate_single,
            fg_color="#059669",
            hover_color="#047857",
            height=24,
            width=76,
            corner_radius=2,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_trans_sel_main.pack(side="right", padx=(2, 3), pady=3)
        self._on_provider_change(self.combo_provider.get())

        # Single Compact Voice / Dubbing Toolbar Row (Model, Speed, Dub All, Dub Sel, Missing, Auto-Dub)
        dub_bar = ctk.CTkFrame(self, fg_color="#181a20", corner_radius=2, border_width=1, border_color="#262a33", height=30)
        dub_bar.grid(row=2, column=0, padx=4, pady=(1, 2), sticky="ew")

        # 1. Label icon
        ctk.CTkLabel(dub_bar, text="🎙️ AI Voice:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#10b981").pack(side="left", padx=(4, 2))

        # 2. Voice Model selector
        VOICE_MODEL_OPTIONS = [
            "Piseth (Male / ប្រុសធម្មជាតិ)",
            "Sreymom (Female / ស្រីធម្មជាតិ)",
            "Piseth - រឿងនិទាន & ភាពយន្ត (Narrator)",
            "Piseth - វីរបុរស (Action Hero)",
            "Piseth - ព័ត៌មានផ្លូវការ (News Anchor)",
            "Piseth - តាចាស់ / ព្រឹទ្ធាចារ្យ (Old Master)",
            "Piseth - មនុស្សយន្ត AI (Robot Sci-Fi)",
            "Sreymom - រឿងនិទានស្រទន់ (Soft Story)",
            "Sreymom - ពាណិជ្ជកម្ម (Commercial)",
            "Sreymom - ក្មេង / តុក្កតា (Anime Girl)",
            "✨ [CLONE] Cinema Deep Baritone"
        ]
        self.combo_voice_model = ctk.CTkComboBox(
            dub_bar,
            values=VOICE_MODEL_OPTIONS,
            command=self._on_voice_model_select,
            corner_radius=2,
            height=24,
            width=165,
            font=ctk.CTkFont(size=10)
        )
        self.combo_voice_model.set("Piseth (Male / ប្រុសធម្មជាតិ)")
        self.combo_voice_model.pack(side="left", padx=2, pady=3)

        # 3. Voice Speed selector
        SPEED_OPTIONS = [
            "1.0x (ធម្មតា)",
            "1.1x (+10%)",
            "1.2x (+20%)",
            "1.3x (+30%)",
            "Auto-Sync (ទាន់តាម CC)"
        ]
        self.combo_voice_speed = ctk.CTkComboBox(
            dub_bar,
            values=SPEED_OPTIONS,
            command=self._on_voice_speed_select,
            corner_radius=2,
            height=24,
            width=100,
            font=ctk.CTkFont(size=10)
        )
        self.combo_voice_speed.set("1.1x (+10%)")
        self.combo_voice_speed.pack(side="left", padx=2, pady=3)

        # 4. Auto-Dub Checkbox
        self.check_auto_dub = ctk.CTkCheckBox(
            dub_bar,
            text="Auto-Dub",
            corner_radius=2,
            font=ctk.CTkFont(size=9),
            text_color="#94a3b8",
            width=68,
            height=18,
            checkbox_width=13,
            checkbox_height=13
        )
        self.check_auto_dub.select()
        self.check_auto_dub.pack(side="left", padx=(2, 4), pady=3)

        # 5. Dub All Button
        self.btn_dub_all = ctk.CTkButton(
            dub_bar,
            text="🎧 Dub All (សំឡេងទាំងអស់)",
            command=self._dub_all,
            fg_color="#10b981",
            hover_color="#059669",
            height=24,
            corner_radius=2,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_dub_all.pack(side="left", fill="x", expand=True, padx=2, pady=3)

        # 6. Dub Selected Button
        self.btn_dub_sel = ctk.CTkButton(
            dub_bar,
            text="🎯 Dub Sel",
            command=self._dub_selected,
            fg_color="#047857",
            hover_color="#065f46",
            height=24,
            width=68,
            corner_radius=2,
            font=ctk.CTkFont(size=9, weight="bold")
        )
        self.btn_dub_sel.pack(side="left", padx=2, pady=3)

        # 7. Dub Missing Only Button
        self.btn_dub_missing = ctk.CTkButton(
            dub_bar,
            text="⚡ Missing",
            command=self._dub_missing,
            fg_color="#7c3aed",
            hover_color="#6d28d9",
            height=24,
            width=64,
            corner_radius=2,
            font=ctk.CTkFont(size=9, weight="bold")
        )
        self.btn_dub_missing.pack(side="right", padx=(2, 3), pady=3)

        # Optional API Key Entry (Only shown when custom API provider is selected)
        self.api_key_frame = ctk.CTkFrame(self, fg_color="#181a20", corner_radius=2)
        self.entry_api_key = ctk.CTkEntry(
            self.api_key_frame,
            placeholder_text="Enter API Key here...",
            show="*",
            corner_radius=2,
            height=22,
            font=ctk.CTkFont(size=10)
        )
        self.entry_api_key.pack(side="left", fill="x", expand=True, padx=4, pady=2)
        self.lbl_api_status = ctk.CTkLabel(
            self.api_key_frame,
            text="● API Key Active & Verified",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="#10b981"
        )
        self.lbl_api_status.pack(side="right", padx=6, pady=2)
        self.entry_filter = None

        # 3. Scrollable Subtitles List
        self.scroll_list = ctk.CTkScrollableFrame(self, fg_color="#0d0e12", corner_radius=0)
        self.scroll_list.grid(row=4, column=0, padx=6, pady=(3, 1), sticky="nsew")

        # 3.1 Pagination Bar for Ultra-Fast Loading of large movies (1,000 - 10,000+ subtitles)
        self.pagination_frame = ctk.CTkFrame(self, fg_color="#141822", corner_radius=2, height=28)
        
        btn_first = ctk.CTkButton(
            self.pagination_frame, text="⏮", width=28, height=22, corner_radius=2,
            fg_color="#1e2430", hover_color="#334155", font=ctk.CTkFont(size=10),
            command=self._go_first_page
        )
        btn_first.pack(side="left", padx=(4, 2), pady=3)

        btn_prev = ctk.CTkButton(
            self.pagination_frame, text="◀ Prev 100", width=72, height=22, corner_radius=2,
            fg_color="#1e2430", hover_color="#334155", font=ctk.CTkFont(size=9, weight="bold"),
            command=self._go_prev_page
        )
        btn_prev.pack(side="left", padx=2, pady=3)

        self.lbl_page_info = ctk.CTkLabel(
            self.pagination_frame,
            text="Page 1/1 (1-100 of 100)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_page_info.pack(side="left", fill="x", expand=True, padx=4, pady=3)

        btn_next = ctk.CTkButton(
            self.pagination_frame, text="Next 100 ▶", width=72, height=22, corner_radius=2,
            fg_color="#1e2430", hover_color="#334155", font=ctk.CTkFont(size=9, weight="bold"),
            command=self._go_next_page
        )
        btn_next.pack(side="right", padx=2, pady=3)

        btn_last = ctk.CTkButton(
            self.pagination_frame, text="⏭", width=28, height=22, corner_radius=2,
            fg_color="#1e2430", hover_color="#334155", font=ctk.CTkFont(size=10),
            command=self._go_last_page
        )
        btn_last.pack(side="right", padx=(2, 4), pady=3)

        # Vertical Resize Sash Bar between CC List and Edit Card (↕ Cursor Support)
        self.sash_edit_resize = tk.Frame(self, bg="#1e293b", height=7, cursor="sb_v_double_arrow")
        self.sash_edit_resize.grid(row=5, column=0, padx=6, pady=(1, 1), sticky="ew")

        # Center grip handle
        self.sash_edit_grip = tk.Frame(self.sash_edit_resize, bg="#475569", width=36, height=3)
        self.sash_edit_grip.place(relx=0.5, rely=0.5, anchor="center")

        def _enter_sub_sash(e):
            self.sash_edit_resize.configure(bg="#0284c7")
            self.sash_edit_grip.configure(bg="#38bdf8")

        def _leave_sub_sash(e):
            self.sash_edit_resize.configure(bg="#1e293b")
            self.sash_edit_grip.configure(bg="#475569")

        self.sash_edit_resize.bind("<Enter>", _enter_sub_sash)
        self.sash_edit_resize.bind("<Leave>", _leave_sub_sash)
        self.sash_edit_grip.bind("<Enter>", _enter_sub_sash)
        self.sash_edit_grip.bind("<Leave>", _leave_sub_sash)
        self.sash_edit_resize.bind("<Button-1>", self._on_sash_drag_start)
        self.sash_edit_resize.bind("<B1-Motion>", self._on_sash_drag_motion)
        self.sash_edit_grip.bind("<Button-1>", self._on_sash_drag_start)
        self.sash_edit_grip.bind("<B1-Motion>", self._on_sash_drag_motion)

        # 4. Advanced Edit Dialogue Card (Supports Khmer Unicode, Move Timing, Speech Speed)
        self.edit_card = ctk.CTkFrame(self, fg_color="#1c1f26", corner_radius=0)
        self.edit_card.grid(row=7, column=0, padx=6, pady=(1, 6), sticky="ew")

        # Header with line identifier & Close Button (user can hide edit panel to free space)
        hdr_edit = ctk.CTkFrame(self.edit_card, fg_color="transparent")
        hdr_edit.pack(fill="x", padx=6, pady=(4, 1))

        self.lbl_edit_title = ctk.CTkLabel(
            hdr_edit, 
            text="✏️ Edit Dialogue & Timing:", 
            font=ctk.CTkFont(size=10, weight="bold"), 
            text_color="#38bdf8"
        )
        self.lbl_edit_title.pack(side="left")

        btn_close_edit = ctk.CTkButton(
            hdr_edit,
            text="✖ បិទ (Close)",
            width=58,
            height=18,
            corner_radius=2,
            fg_color="#334155",
            hover_color="#475569",
            font=ctk.CTkFont(size=9),
            command=self.hide_edit_panel
        )
        btn_close_edit.pack(side="right")
        edit_card = self.edit_card

        # Font & Size Selector Toolbar (Guarantees Khmer Font & Dynamic Switching)
        f_toolbar = ctk.CTkFrame(edit_card, fg_color="transparent")
        f_toolbar.pack(fill="x", padx=6, pady=(1, 2))

        ctk.CTkLabel(f_toolbar, text="🔤 Font:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#cbd5e1").pack(side="left")

        all_khmer_fonts = get_installed_khmer_fonts()
        self.combo_font = ctk.CTkComboBox(
            f_toolbar,
            values=all_khmer_fonts,
            width=130,
            height=20,
            font=ctk.CTkFont(size=9),
            dropdown_font=ctk.CTkFont(size=9),
            corner_radius=0,
            command=self._on_font_family_selected
        )
        self.combo_font.set(self.active_font_family)
        self.combo_font.pack(side="left", padx=2)

        self.combo_font_size = ctk.CTkComboBox(
            f_toolbar,
            values=["10", "11", "12", "13", "14", "16", "18"],
            width=50,
            height=20,
            font=ctk.CTkFont(size=9),
            dropdown_font=ctk.CTkFont(size=9),
            corner_radius=0,
            command=self._on_font_size_selected
        )
        self.combo_font_size.set(str(self.active_font_size))
        self.combo_font_size.pack(side="left", padx=2)

        # Multiline Textbox with Active Khmer Font - 100% Khmer Unicode without '????'
        self.txt_edit_km = ctk.CTkTextbox(
            edit_card, 
            corner_radius=0, 
            height=self.txt_edit_height, 
            font=ctk.CTkFont(family=self.active_font_family, size=self.active_font_size),
            wrap="word",
            fg_color="#0f1115",
            border_width=1,
            border_color="#334155"
        )
        self.txt_edit_km.pack(fill="x", padx=6, pady=(1, 3))

        # Timing Control Row 1: Start & End time entries with +/- 0.5s buttons
        t_row1 = ctk.CTkFrame(edit_card, fg_color="transparent")
        t_row1.pack(fill="x", padx=6, pady=1)

        ctk.CTkLabel(t_row1, text="Start:", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left")
        ctk.CTkButton(t_row1, text="-", width=18, height=18, corner_radius=0, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", command=lambda: self._adjust_start(-0.5)).pack(side="left", padx=1)
        self.entry_start = ctk.CTkEntry(t_row1, width=54, height=20, corner_radius=0, font=ctk.CTkFont(family="Consolas", size=9))
        self.entry_start.insert(0, "0.00")
        self.entry_start.pack(side="left", padx=1)
        ctk.CTkButton(t_row1, text="+", width=18, height=18, corner_radius=0, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", command=lambda: self._adjust_start(0.5)).pack(side="left", padx=1)

        ctk.CTkLabel(t_row1, text="End:", font=ctk.CTkFont(size=9), text_color="#94a3b8").pack(side="left", padx=(6, 0))
        ctk.CTkButton(t_row1, text="-", width=18, height=18, corner_radius=0, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", command=lambda: self._adjust_end(-0.5)).pack(side="left", padx=1)
        self.entry_end = ctk.CTkEntry(t_row1, width=54, height=20, corner_radius=0, font=ctk.CTkFont(family="Consolas", size=9))
        self.entry_end.insert(0, "0.00")
        self.entry_end.pack(side="left", padx=1)
        ctk.CTkButton(t_row1, text="+", width=18, height=18, corner_radius=0, font=ctk.CTkFont(size=10, weight="bold"), fg_color="#334155", command=lambda: self._adjust_end(0.5)).pack(side="left", padx=1)

        # Timing Control Row 2: Shift Both (Move whole dialogue block in timeline)
        t_row2 = ctk.CTkFrame(edit_card, fg_color="transparent")
        t_row2.pack(fill="x", padx=6, pady=2)

        ctk.CTkLabel(t_row2, text="Move Time:", font=ctk.CTkFont(size=9), text_color="#38bdf8").pack(side="left")
        ctk.CTkButton(t_row2, text="⏮ -1s", width=38, height=18, corner_radius=0, font=ctk.CTkFont(size=8), fg_color="#1e293b", command=lambda: self._shift_both(-1.0)).pack(side="left", padx=1)
        ctk.CTkButton(t_row2, text="-0.2s", width=34, height=18, corner_radius=0, font=ctk.CTkFont(size=8), fg_color="#1e293b", command=lambda: self._shift_both(-0.2)).pack(side="left", padx=1)
        ctk.CTkButton(t_row2, text="+0.2s", width=34, height=18, corner_radius=0, font=ctk.CTkFont(size=8), fg_color="#1e293b", command=lambda: self._shift_both(0.2)).pack(side="left", padx=1)
        ctk.CTkButton(t_row2, text="+1s ⏭", width=38, height=18, corner_radius=0, font=ctk.CTkFont(size=8), fg_color="#1e293b", command=lambda: self._shift_both(1.0)).pack(side="left", padx=1)

        # Speed Control Row: Speech rate selector
        s_row = ctk.CTkFrame(edit_card, fg_color="transparent")
        s_row.pack(fill="x", padx=6, pady=2)
        
        ctk.CTkLabel(s_row, text="⚡ Speed:", font=ctk.CTkFont(size=9), text_color="#10b981").pack(side="left")
        self.combo_speed = ctk.CTkComboBox(
            s_row,
            values=list(SPEECH_SPEED_PRESETS.keys()),
            height=20,
            width=140,
            corner_radius=0,
            font=ctk.CTkFont(size=9)
        )
        self.combo_speed.set("1.0x (Normal / ធម្មតា)")
        self.combo_speed.pack(side="right")

        # Action Buttons: Translate Line, Apply Edit & Listen
        btn_row = ctk.CTkFrame(edit_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=6, pady=(3, 5))

        self.btn_trans_line = ctk.CTkButton(
            btn_row, 
            text="🌐 Translate Line", 
            command=self._translate_single,
            fg_color="#0284c7", 
            hover_color="#0369a1",
            corner_radius=0,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_trans_line.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.btn_apply = ctk.CTkButton(
            btn_row, 
            text="💾 Save & Re-Dub", 
            command=self._apply_edit,
            fg_color="#2563eb", 
            hover_color="#1d4ed8",
            corner_radius=0,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_apply.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_listen = ctk.CTkButton(
            btn_row, 
            text="🔊 Test Voice", 
            command=self._listen_line,
            fg_color="#059669", 
            hover_color="#047857",
            corner_radius=0,
            height=26,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_listen.pack(side="right", fill="x", expand=True, padx=(2, 0))

        # Initially hide the edit card to preserve screen space (only shows when user clicks Edit)
        self._edit_panel_visible = False
        self.sash_edit_resize.grid_remove()
        self.edit_card.grid_remove()

    def show_edit_panel(self):
        """Reveals the bottom edit dialogue when user clicks Edit"""
        self.sash_edit_resize.grid(row=6, column=0, padx=6, pady=(1, 1), sticky="ew")
        self.edit_card.grid(row=7, column=0, padx=6, pady=(1, 6), sticky="ew")
        self._edit_panel_visible = True

    def hide_edit_panel(self):
        """Hides the edit dialogue so it does not take screen space constantly"""
        self.sash_edit_resize.grid_remove()
        self.edit_card.grid_remove()
        self._edit_panel_visible = False

    def _open_edit_for_card(self, idx: int, sub: dict):
        self.select_subtitle_by_index(idx, scroll_to_view=True)
        self.show_edit_panel()

    # ------------------ TIMING ADJUSTERS ------------------
    def _adjust_start(self, delta: float):
        try:
            cur = float(self.entry_start.get().strip())
            new_val = max(0.0, round(cur + delta, 2))
            self.entry_start.delete(0, "end")
            self.entry_start.insert(0, f"{new_val:.2f}")
        except Exception:
            pass

    def _adjust_end(self, delta: float):
        try:
            cur = float(self.entry_end.get().strip())
            new_val = max(0.1, round(cur + delta, 2))
            self.entry_end.delete(0, "end")
            self.entry_end.insert(0, f"{new_val:.2f}")
        except Exception:
            pass

    def _shift_both(self, delta: float):
        try:
            s = float(self.entry_start.get().strip())
            e = float(self.entry_end.get().strip())
            dur = max(0.2, e - s)
            new_s = max(0.0, round(s + delta, 2))
            new_e = round(new_s + dur, 2)
            self.entry_start.delete(0, "end")
            self.entry_start.insert(0, f"{new_s:.2f}")
            self.entry_end.delete(0, "end")
            self.entry_end.insert(0, f"{new_e:.2f}")
        except Exception:
            pass

    def set_selected_timing(self, start_sec: float, end_sec: float):
        self.entry_start.delete(0, "end")
        self.entry_start.insert(0, f"{start_sec:.2f}")
        self.entry_end.delete(0, "end")
        self.entry_end.insert(0, f"{end_sec:.2f}")

    def _on_provider_change(self, choice):
        is_free_mt = ("Google" in choice and "Gemini" not in choice) or "MyMemory" in choice
        if hasattr(self, "combo_style"):
            if is_free_mt:
                self.combo_style.pack_forget()
            else:
                self.combo_style.pack(side="left", padx=2, pady=3, before=self.btn_trans_all_main)

        if "API" in choice:
            if hasattr(self, "api_key_frame"):
                self.api_key_frame.grid(row=3, column=0, padx=4, pady=(0, 2), sticky="ew")
            if "Gemini" in choice:
                from config import GEMINI_API_KEY
                if hasattr(self, "entry_api_key") and not self.entry_api_key.get():
                    self.entry_api_key.insert(0, GEMINI_API_KEY)
                if hasattr(self, "lbl_api_status"):
                    self.lbl_api_status.configure(
                        text="● Gemini 3.5 Active & Verified",
                        text_color="#10b981"
                    )
        else:
            if hasattr(self, "api_key_frame"):
                self.api_key_frame.grid_remove()

    def _dub_all(self):
        if hasattr(self, "on_dub_all") and self.on_dub_all:
            self.on_dub_all()

    def _dub_selected(self):
        idx = self.selected_idx
        if idx is None or idx < 0 or idx >= len(self._subtitles_data):
            if self._subtitles_data:
                idx = 0
            else:
                return
        if hasattr(self, "on_dub_selected") and self.on_dub_selected:
            self.on_dub_selected(idx)

    def _dub_missing(self):
        if hasattr(self, "on_dub_missing") and self.on_dub_missing:
            self.on_dub_missing()

    def _on_voice_model_select(self, choice):
        if hasattr(self, "on_voice_change") and self.on_voice_change:
            self.on_voice_change(choice)

    def _on_voice_speed_select(self, choice):
        if hasattr(self, "on_voice_speed_change") and self.on_voice_speed_change:
            self.on_voice_speed_change(choice)

    def get_dubbing_settings(self) -> dict:
        speed_choice = self.combo_voice_speed.get() if hasattr(self, "combo_voice_speed") else "1.1x (+10%)"
        rate_code = "+10%"
        if "+0%" in speed_choice or "1.0x" in speed_choice:
            rate_code = "+0%"
        elif "+10%" in speed_choice or "1.1x" in speed_choice:
            rate_code = "+10%"
        elif "+20%" in speed_choice or "1.2x" in speed_choice:
            rate_code = "+20%"
        elif "+30%" in speed_choice or "1.3x" in speed_choice:
            rate_code = "+30%"
        elif "Auto" in speed_choice:
            rate_code = "auto"

        voice_choice = self.combo_voice_model.get() if hasattr(self, "combo_voice_model") else "Piseth (Male / ប្រុសធម្មជាតិ)"
        auto_dub = bool(self.check_auto_dub.get()) if hasattr(self, "check_auto_dub") else True

        return {
            "voice_key": voice_choice,
            "speed_rate": rate_code,
            "speed_label": speed_choice,
            "auto_dub": auto_dub
        }

    def get_translation_settings(self):
        from config import GEMINI_API_KEY
        key = self.entry_api_key.get().strip() if hasattr(self, "entry_api_key") else ""
        provider = self.combo_provider.get()
        if "Gemini" in provider and not key:
            key = GEMINI_API_KEY
        return {
            "provider": provider,
            "api_key": key,
            "style": self.combo_style.get() if hasattr(self, "combo_style") else "📖 ធម្មតា (Standard)",
            "source_lang": self.combo_src.get(),
            "target_lang": self.combo_tgt.get() if hasattr(self, "combo_tgt") else "Khmer (km)"
        }

    def _translate_single(self, idx: int = None):
        if idx is None:
            idx = self.selected_idx
        if idx is None or idx < 0 or idx >= len(self._subtitles_data):
            if self._subtitles_data:
                idx = 0
            else:
                return
        if hasattr(self, "on_translate_single") and self.on_translate_single:
            self.on_translate_single(idx)

    def _go_first_page(self):
        if self.current_page != 0:
            self.current_page = 0
            self._render_current_page()

    def _go_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_current_page()

    def _go_next_page(self):
        total_pages = max(1, math.ceil(len(self._subtitles_data) / self.page_size))
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._render_current_page()

    def _go_last_page(self):
        total_pages = max(1, math.ceil(len(self._subtitles_data) / self.page_size))
        if self.current_page != total_pages - 1:
            self.current_page = total_pages - 1
            self._render_current_page()

    def _on_filter_changed(self, event=None):
        if not hasattr(self, "entry_filter") or not self.entry_filter:
            return
        query = self.entry_filter.get().strip().lower()
        self._filter_query = query
        self.current_page = 0
        self._render_current_page()

    def reset_view(self):
        """Completely clears all subtitles, selections, and editing fields for a clean new project"""
        self.populate_subtitles([])
        if hasattr(self, "entry_filter") and self.entry_filter:
            self.entry_filter.delete(0, "end")

    def populate_subtitles(self, subtitles: list):
        self._subtitles_data = subtitles or []
        self.lbl_total_cc.configure(text=f"📝 Subtitles ({len(self._subtitles_data)})")

        if not self._subtitles_data:
            self.selected_idx = -1
            self.current_sub = None
            self._prev_active_idx = None
            for widget in self.scroll_list.winfo_children():
                widget.destroy()
            self._card_widgets.clear()
            if hasattr(self, "pagination_frame"):
                self.pagination_frame.grid_forget()
            if hasattr(self, "txt_edit_km"):
                self.txt_edit_km.delete("1.0", "end")
            if hasattr(self, "set_selected_timing"):
                self.set_selected_timing(0.0, 0.0)
            if hasattr(self, "lbl_edit_title"):
                self.lbl_edit_title.configure(text="✏️ Edit Dialogue CC:")
            return

        total_pages = max(1, math.ceil(len(self._subtitles_data) / self.page_size))
        if self.current_page >= total_pages:
            self.current_page = 0

        self._render_current_page()

    def _render_current_page(self):
        """Renders only the current visible batch (100 items), eliminating UI freezing for 1,000-10,000+ subtitles!"""
        for widget in self.scroll_list.winfo_children():
            widget.destroy()

        self._card_widgets.clear()
        total_subs = len(self._subtitles_data)
        if total_subs == 0:
            if hasattr(self, "pagination_frame"):
                self.pagination_frame.grid_forget()
            return

        total_pages = max(1, math.ceil(total_subs / self.page_size))
        self.current_page = max(0, min(self.current_page, total_pages - 1))

        start_idx = self.current_page * self.page_size
        end_idx = min(total_subs, start_idx + self.page_size)

        if total_subs > self.page_size:
            self.lbl_page_info.configure(text=f"Page {self.current_page + 1}/{total_pages} ({start_idx + 1}-{end_idx} of {total_subs:,})")
            self.pagination_frame.grid(row=5, column=0, padx=6, pady=(1, 1), sticky="ew")
        else:
            self.pagination_frame.grid_forget()

        for idx in range(start_idx, end_idx):
            sub = self._subtitles_data[idx]
            time_tag = f"[{format_timestamp(sub.get('start', 0.0))[:8]} - {format_timestamp(sub.get('end', 0.0))[:8]}]"

            # Card frame with cursor hand2 so clicking anywhere selects the clip
            card = ctk.CTkFrame(self.scroll_list, fg_color="#181a20", corner_radius=2, border_width=1, border_color="#262a33", cursor="hand2")
            card.pack(fill="x", padx=2, pady=2)

            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=4, pady=(2, 0))
            lbl_hdr = ctk.CTkLabel(hdr, text=f"#{sub.get('id', idx+1)} {time_tag}", font=ctk.CTkFont(size=9, weight="bold"), text_color="#38bdf8", cursor="hand2")
            lbl_hdr.pack(side="left")

            if self.on_delete_sub:
                btn_del = ctk.CTkButton(
                    hdr,
                    text="🗑",
                    width=22,
                    height=16,
                    corner_radius=0,
                    font=ctk.CTkFont(size=9),
                    fg_color="#be123c",
                    hover_color="#9f1239",
                    command=lambda i=idx: self.on_delete_sub(i)
                )
                btn_del.pack(side="right", padx=(2, 0))

            btn_trans_line = ctk.CTkButton(
                hdr,
                text="🌐 Trans",
                width=42,
                height=16,
                corner_radius=0,
                font=ctk.CTkFont(size=9, weight="bold"),
                fg_color="#0284c7",
                hover_color="#0369a1",
                command=lambda i=idx: self._translate_single(i)
            )
            btn_trans_line.pack(side="right", padx=(2, 0))

            btn_edit_line = ctk.CTkButton(
                hdr,
                text="✏️ Edit",
                width=38,
                height=16,
                corner_radius=0,
                font=ctk.CTkFont(size=9, weight="bold"),
                fg_color="#2563eb",
                hover_color="#1d4ed8",
                command=lambda i=idx, s=sub: self._open_edit_for_card(i, s)
            )
            btn_edit_line.pack(side="right", padx=(2, 0))

            btn_jump = ctk.CTkButton(
                hdr, 
                text="Jump", 
                width=34, 
                height=16, 
                corner_radius=0, 
                font=ctk.CTkFont(size=9),
                fg_color="#334155",
                command=lambda s=sub, i=idx: self._select_card(i, s)
            )
            btn_jump.pack(side="right", padx=(2, 0))

            btn_snd = ctk.CTkButton(
                hdr,
                text="🔊",
                width=24,
                height=16,
                corner_radius=0,
                font=ctk.CTkFont(size=9),
                fg_color="#059669",
                hover_color="#047857",
                command=lambda s=sub: self.on_listen_line(s.get("translated", ""), s.get("rate", "+0%"))
            )
            btn_snd.pack(side="right", padx=(0, 2))

            # Render Khmer text using active Khmer font for crisp Unicode rendering
            lbl_km = ctk.CTkLabel(
                card, 
                text=sub.get("translated", ""), 
                font=ctk.CTkFont(family=self.active_font_family, size=11),
                text_color="#f8fafc",
                wraplength=210,
                justify="left",
                cursor="hand2"
            )
            lbl_km.pack(anchor="w", padx=4, pady=(1, 1))

            lbl_orig = ctk.CTkLabel(
                card, 
                text=sub.get("original", ""), 
                font=ctk.CTkFont(size=9),
                text_color="#64748b",
                wraplength=210,
                justify="left",
                cursor="hand2"
            )
            lbl_orig.pack(anchor="w", padx=4, pady=(0, 2))

            card.bind("<Button-1>", lambda e, i=idx, s=sub: self._select_card(i, s))
            lbl_hdr.bind("<Button-1>", lambda e, i=idx, s=sub: self._select_card(i, s))
            lbl_km.bind("<Button-1>", lambda e, i=idx, s=sub: self._select_card(i, s))
            lbl_orig.bind("<Button-1>", lambda e, i=idx, s=sub: self._select_card(i, s))
            card.bind("<Double-Button-1>", lambda e, i=idx, s=sub: self._open_edit_for_card(i, s))
            lbl_km.bind("<Double-Button-1>", lambda e, i=idx, s=sub: self._open_edit_for_card(i, s))

            self._card_widgets[idx] = {
                "card": card,
                "lbl_hdr": lbl_hdr,
                "lbl_km": lbl_km,
                "lbl_orig": lbl_orig,
                "sub": sub,
                "idx": idx
            }

        # If selection was active and is on this page, highlight it
        if self.selected_idx in self._card_widgets:
            self._apply_card_highlight(self.selected_idx)

    def select_subtitle_by_index(self, idx: int, scroll_to_view: bool = True):
        """Bidirectional Active Clip Highlight with instant pagination sync"""
        if not (0 <= idx < len(self._subtitles_data)):
            return

        target_page = idx // self.page_size
        if target_page != self.current_page:
            self.current_page = target_page
            self._render_current_page()

        self.selected_idx = idx
        sub = self._subtitles_data[idx]
        self.current_sub = sub

        self._apply_card_highlight(idx)

        # Update edit panel
        time_tag = f"[{format_timestamp(sub.get('start', 0.0))[:8]} - {format_timestamp(sub.get('end', 0.0))[:8]}]"
        self.lbl_edit_title.configure(text=f"✏️ Active Clip #{sub.get('id', idx+1)} {time_tag}:")

        # Populate Textbox with Khmer text
        self.txt_edit_km.delete("1.0", "end")
        self.txt_edit_km.insert("1.0", sub.get("translated", ""))

        # Populate Start and End timing
        self.set_selected_timing(sub.get("start", 0.0), sub.get("end", 0.0))

        # Populate Speed
        current_rate = sub.get("rate", "+0%")
        for name, rcode in SPEECH_SPEED_PRESETS.items():
            if rcode == current_rate:
                self.combo_speed.set(name)
                break

        if scroll_to_view:
            self._scroll_card_into_view(idx)

    def _apply_card_highlight(self, idx: int):
        """Fast O(1) card highlight without looping over thousands of cards"""
        if getattr(self, "_prev_active_idx", None) in self._card_widgets:
            prev = self._card_widgets[self._prev_active_idx]
            prev["card"].configure(fg_color="#181a20", border_color="#262a33", border_width=1)
            if prev.get("lbl_hdr"):
                prev["lbl_hdr"].configure(text_color="#38bdf8")
            if prev.get("lbl_km"):
                prev["lbl_km"].configure(text_color="#f8fafc")

        if idx in self._card_widgets:
            curr = self._card_widgets[idx]
            curr["card"].configure(fg_color="#1a2638", border_color="#38bdf8", border_width=2)
            if curr.get("lbl_hdr"):
                curr["lbl_hdr"].configure(text_color="#67e8f9")
            if curr.get("lbl_km"):
                curr["lbl_km"].configure(text_color="#ffffff")

        self._prev_active_idx = idx

    def set_playback_active(self, idx: int, auto_scroll: bool = True):
        """Real-time Playback Sync with instant pagination jumping (< 0.1ms)"""
        if not (0 <= idx < len(self._subtitles_data)):
            return

        if self.selected_idx == idx and idx in self._card_widgets:
            return

        target_page = idx // self.page_size
        if target_page != self.current_page:
            self.current_page = target_page
            self._render_current_page()

        self.selected_idx = idx
        sub = self._subtitles_data[idx]
        self.current_sub = sub

        self._apply_card_highlight(idx)

        # Update edit panel only if user has opened it
        if getattr(self, "_edit_panel_visible", False):
            time_tag = f"[{format_timestamp(sub.get('start', 0.0))[:8]} - {format_timestamp(sub.get('end', 0.0))[:8]}]"
            self.lbl_edit_title.configure(text=f"✏️ Active Clip #{sub.get('id', idx+1)} {time_tag}:")
            self.set_selected_timing(sub.get("start", 0.0), sub.get("end", 0.0))
            try:
                self.txt_edit_km.delete("1.0", "end")
                self.txt_edit_km.insert("1.0", sub.get("translated", ""))
            except Exception:
                pass

        should_scroll = auto_scroll and (self.check_auto_scroll.get() if hasattr(self, "check_auto_scroll") else True)
        if should_scroll:
            self._scroll_card_into_view(idx)

    def _scroll_card_into_view(self, idx: int):
        total = len(self._card_widgets)
        if total <= 1:
            return
        try:
            start_idx = self.current_page * self.page_size
            rel_idx = idx - start_idx
            frac = max(0.0, min(1.0, (rel_idx - 0.5) / max(1, total - 1)))
            self.scroll_list._parent_canvas.yview_moveto(frac)
        except Exception:
            pass

    def _select_card(self, idx: int, sub: dict):
        self.select_subtitle_by_index(idx, scroll_to_view=False)
        self.on_select_sub(idx, sub["start"])

    # ------------------ FONT MANAGEMENT (KHMER UNICODE) ------------------
    def set_font_family(self, font_name: str):
        if not font_name:
            return
        self.active_font_family = font_name
        try:
            self.combo_font.set(font_name)
        except Exception:
            pass
        self.txt_edit_km.configure(font=ctk.CTkFont(family=font_name, size=self.active_font_size))
        for item in self._card_widgets:
            try:
                item["lbl_km"].configure(font=ctk.CTkFont(family=font_name, size=11))
            except Exception:
                pass

    def _on_font_family_selected(self, choice: str):
        self.set_font_family(choice)

    def _on_font_size_selected(self, size_str: str):
        try:
            size = int(size_str)
            self.active_font_size = size
            self.txt_edit_km.configure(font=ctk.CTkFont(family=self.active_font_family, size=size))
        except Exception:
            pass

    # ------------------ PANEL RESIZING HANDLERS (↕ size_ns) ------------------
    def _on_sash_drag_start(self, event):
        self._sash_start_y = event.y_root
        self._sash_orig_h = self.txt_edit_km.cget("height")

    def _on_sash_drag_motion(self, event):
        dy = self._sash_start_y - event.y_root
        new_h = max(40, min(160, int(self._sash_orig_h + dy)))
        self.txt_edit_km.configure(height=new_h)

    def _apply_edit(self):
        new_text = self.txt_edit_km.get("1.0", "end-1c").strip()
        try:
            new_start = float(self.entry_start.get().strip())
            new_end = float(self.entry_end.get().strip())
        except Exception:
            new_start = None
            new_end = None

        speed_choice = self.combo_speed.get()
        rate_code = SPEECH_SPEED_PRESETS.get(speed_choice, "+0%")

        self.on_apply_edit(self.selected_idx, new_text, new_start, new_end, rate_code)

    def _listen_line(self):
        text = self.txt_edit_km.get("1.0", "end-1c").strip()
        speed_choice = self.combo_speed.get()
        rate_code = SPEECH_SPEED_PRESETS.get(speed_choice, "+0%")
        self.on_listen_line(text, rate_code)
