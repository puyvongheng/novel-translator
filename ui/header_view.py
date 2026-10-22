import os
import tkinter as tk
import customtkinter as ctk

class ModernDropdownMenu:
    """
    Ultra-modern, sleek dark floating dropdown menu (VS Code, Photoshop & CapCut style)
    - Borderless floating card with 1px subtle dark border and rounded corners
    - Smooth hover highlight with pill style
    - Left-aligned item text with icons
    - Right-aligned keyboard shortcuts in muted gray
    - Clean divider lines
    - Auto-dismiss on click outside or Escape
    """
    def __init__(self, parent_widget, on_close=None):
        self.parent = parent_widget
        self.on_close = on_close
        self.top = None
        self.items = []
        self._is_posted = False
        self._global_bind_id = None

    def add_command(self, label: str, command=None, shortcut: str = None):
        if "\t" in label and not shortcut:
            parts = label.split("\t", 1)
            label = parts[0].strip()
            shortcut = parts[1].strip()
        self.items.append({
            "type": "command",
            "label": label,
            "shortcut": shortcut or "",
            "command": command
        })

    def add_separator(self):
        self.items.append({"type": "separator"})

    def post(self, x: int, y: int):
        self.unpost()
        top = tk.Toplevel(self.parent)
        top.wm_overrideredirect(True)
        top.attributes("-topmost", True)
        top.configure(bg="#12141a")
        self.top = top
        self._is_posted = True

        container = ctk.CTkFrame(
            top,
            fg_color="#181a20",
            border_color="#2d313c",
            border_width=1,
            corner_radius=6
        )
        container.pack(fill="both", expand=True, padx=1, pady=1)

        for item in self.items:
            if item["type"] == "separator":
                sep = ctk.CTkFrame(container, height=1, fg_color="#262933", corner_radius=0)
                sep.pack(fill="x", padx=6, pady=3)
            else:
                row = ctk.CTkFrame(container, height=26, fg_color="transparent", corner_radius=4)
                row.pack(fill="x", padx=4, pady=1)

                cmd = item.get("command")
                lbl_text = item.get("label", "")
                sc_text = item.get("shortcut", "")

                lbl = ctk.CTkLabel(
                    row,
                    text=lbl_text,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color="#e2e8f0"
                )
                lbl.pack(side="left", padx=(8, 4), pady=2)

                lbl_sc = None
                if sc_text:
                    lbl_sc = ctk.CTkLabel(
                        row,
                        text=sc_text,
                        font=ctk.CTkFont(family="Segoe UI", size=9),
                        text_color="#71717a"
                    )
                    lbl_sc.pack(side="right", padx=(12, 8), pady=2)

                # Smooth hover highlights (VS Code style subtle dark highlight)
                def _on_enter(e, r=row, l=lbl, s=lbl_sc):
                    r.configure(fg_color="#272a34")
                    l.configure(text_color="#ffffff")
                    if s:
                        s.configure(text_color="#a1a1aa")

                def _on_leave(e, r=row, l=lbl, s=lbl_sc):
                    r.configure(fg_color="transparent")
                    l.configure(text_color="#e2e8f0")
                    if s:
                        s.configure(text_color="#71717a")

                def _on_click(e, c=cmd):
                    self.unpost()
                    if c:
                        c()

                for w in [row, lbl] + ([lbl_sc] if lbl_sc else []):
                    w.bind("<Enter>", _on_enter)
                    w.bind("<Leave>", _on_leave)
                    w.bind("<Button-1>", _on_click)

        top.update_idletasks()
        req_w = max(240, top.winfo_reqwidth())
        req_h = top.winfo_reqheight()

        screen_w = top.winfo_screenwidth()
        screen_h = top.winfo_screenheight()
        if x + req_w > screen_w:
            x = screen_w - req_w - 8
        if y + req_h > screen_h:
            y = y - req_h - 26

        top.geometry(f"{req_w}x{req_h}+{x}+{y}")

        # Bind outside click to auto-dismiss
        def _check_dismiss(event):
            if not self.top or not self._is_posted:
                return
            try:
                rx = self.top.winfo_rootx()
                ry = self.top.winfo_rooty()
                rw = self.top.winfo_width()
                rh = self.top.winfo_height()
                if not (rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh):
                    self.unpost()
            except Exception:
                self.unpost()

        top.bind("<Escape>", lambda e: self.unpost())
        root_w = self.parent.winfo_toplevel()
        self._global_bind_id = root_w.bind("<Button-1>", _check_dismiss, add="+")

    def unpost(self):
        if self._global_bind_id:
            try:
                self.parent.winfo_toplevel().unbind("<Button-1>", self._global_bind_id)
            except Exception:
                pass
            self._global_bind_id = None
        if self.top:
            try:
                self.top.destroy()
            except Exception:
                pass
            self.top = None
        self._is_posted = False
        if self.on_close:
            self.on_close()

class HeaderView(ctk.CTkFrame):
    """
    Professional Modern Desktop App Navigation Bar
    Features:
    - Industry standard Menu Bar: File, Edit, View, Dubbing & AI, Tools, Help
    - Smooth hover-to-open and hover-to-switch across dropdown menus
    - Quick-access Action Bar (Open, AI Translate, Quick Export)
    - Real-time API Status Badge (Gemini 3.5 Flash Active)
    - UI Zoom & Mobile APK Quick Access
    """
    def __init__(
        self, 
        parent, 
        on_browse_video, 
        on_start_translate,
        on_capture_cc=None,
        on_generate_dub=None,
        on_auto_pipeline=None,
        on_export_movie=None,
        on_switch_tab=None,
        on_zoom_in=None, 
        on_zoom_out=None, 
        on_zoom_reset=None,
        **menu_callbacks
    ):
        super().__init__(parent, fg_color="#0e1015", height=72, corner_radius=0)
        self.on_browse_video = on_browse_video
        self.on_start_translate = on_start_translate
        self.on_capture_cc = on_capture_cc
        self.on_generate_dub = on_generate_dub
        self.on_auto_pipeline = on_auto_pipeline
        self.on_export_movie = on_export_movie
        self.on_switch_tab = on_switch_tab
        self.on_zoom_in = on_zoom_in
        self.on_zoom_out = on_zoom_out
        self.on_zoom_reset = on_zoom_reset
        self.callbacks = menu_callbacks

        self._active_open_menu = None
        self._menus = {}
        self._menu_buttons = {}
        self._tab_buttons = {}
        self._active_tab_name = "studio"

        self._build_ui()

    def _build_ui(self):
        # ================= ROW 1: BRANDING & QUICK ACTION BUTTONS (FOLLOWING RUST APP.RS) =================
        row_top = ctk.CTkFrame(self, fg_color="#0e1015", height=34, corner_radius=0)
        row_top.pack(fill="x", side="top", padx=6, pady=(3, 1))

        # Title / Branding
        brand_frame = ctk.CTkFrame(row_top, fg_color="transparent")
        brand_frame.pack(side="left", padx=4, pady=2)

        lbl_logo = ctk.CTkLabel(
            brand_frame,
            text="🎬 AI KHMER MOVIE & TTS STUDIO",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#f97316"
        )
        lbl_logo.pack(side="left", padx=(2, 6))

        lbl_sub = ctk.CTkLabel(
            brand_frame,
            text="|  Professional Native CapCut Edition",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color="#94a3b8"
        )
        lbl_sub.pack(side="left")

        # Loaded Filename Label (Integrated cleanly in top bar)
        self.lbl_filename = ctk.CTkLabel(
            brand_frame,
            text="",
            text_color="#10b981",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold")
        )
        self.lbl_filename.pack(side="left", padx=(10, 4))

        # Right Action Buttons (Pack right-to-left like version_rust)
        # 1. Export Master Movie
        self.btn_export_master = ctk.CTkButton(
            row_top,
            text="🚀 Export Master Movie",
            command=self.on_export_movie or self._cmd("on_export_all"),
            fg_color="#059669",
            hover_color="#047857",
            corner_radius=3,
            height=26,
            width=145,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_export_master.pack(side="right", padx=(3, 4), pady=2)

        # 2. ⚡ 1-Click Auto Pipeline
        self.btn_auto_pipeline = ctk.CTkButton(
            row_top,
            text="⚡ 1-Click Auto បកប្រែ & TTS",
            command=self.on_auto_pipeline or self.on_start_translate,
            fg_color="#9333ea",
            hover_color="#7e22ce",
            corner_radius=3,
            height=26,
            width=165,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_auto_pipeline.pack(side="right", padx=3, pady=2)

        # 3. Generate Dub
        self.btn_dub = ctk.CTkButton(
            row_top,
            text="🎧 Generate Dub",
            command=self.on_generate_dub or self._cmd("on_start_dubbing"),
            fg_color="#10b981",
            hover_color="#059669",
            corner_radius=3,
            height=26,
            width=110,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_dub.pack(side="right", padx=3, pady=2)

        # 4. Auto-Translate
        self.btn_translate = ctk.CTkButton(
            row_top,
            text="⚡ Auto-Translate",
            command=self.on_start_translate,
            fg_color="#0284c7",
            hover_color="#0369a1",
            corner_radius=3,
            height=26,
            width=115,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_translate.pack(side="right", padx=3, pady=2)

        # 5. Capture CC from Movie
        self.btn_capture_cc = ctk.CTkButton(
            row_top,
            text="🎙️ Capture CC from Movie",
            command=self.on_capture_cc or self.on_start_translate,
            fg_color="#ea580c",
            hover_color="#c2410c",
            corner_radius=3,
            height=26,
            width=150,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_capture_cc.pack(side="right", padx=3, pady=2)

        # 6. Open Video
        self.btn_browse = ctk.CTkButton(
            row_top,
            text="📂 Open Video",
            command=self.on_browse_video,
            fg_color="#1e293b",
            hover_color="#334155",
            corner_radius=3,
            border_width=1,
            border_color="#3b82f6",
            height=26,
            width=95,
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.btn_browse.pack(side="right", padx=3, pady=2)

        self.lbl_zoom = None
        self.lbl_api_badge = None
        self._tab_buttons = {}

    def _select_tab(self, tab_id: str):
        self._active_tab_name = tab_id
        if self.on_switch_tab:
            self.on_switch_tab(tab_id)
        self._active_tab_name = tab_id
        for tid, btn in self._tab_buttons.items():
            if tid == tab_id:
                btn.configure(fg_color="#2563eb", text_color="#ffffff", font=ctk.CTkFont(size=10, weight="bold"))
            else:
                btn.configure(fg_color="transparent", text_color="#94a3b8", font=ctk.CTkFont(size=10, weight="normal"))
        if self.on_switch_tab:
            self.on_switch_tab(tab_id)

    def set_active_tab(self, tab_id: str):
        self._select_tab(tab_id)

    # ------------------ MENU BAR CREATION & HOVER CONTROLLER ------------------
    def _create_menu_bar(self, parent_row):
        """Creates professional menus with hover detection and clean dark styling"""
        menu_defs = [
            ("File", self._build_file_menu()),
            ("Edit", self._build_edit_menu()),
            ("View", self._build_view_menu()),
            ("Dubbing & AI", self._build_dubbing_menu()),
            ("Tools", self._build_tools_menu()),
            ("Help", self._build_help_menu())
        ]

        for title, menu in menu_defs:
            self._menus[title] = menu
            btn = ctk.CTkButton(
                parent_row,
                text=title,
                width=len(title) * 8 + 18,
                height=22,
                corner_radius=4,
                fg_color="transparent",
                hover_color="#1e222a",
                text_color="#cbd5e1",
                font=ctk.CTkFont(family="Segoe UI", size=11)
            )
            btn.pack(side="left", padx=2, pady=4)
            self._menu_buttons[title] = btn

            # Bind click to open/toggle
            btn.configure(command=lambda b=btn, m=menu: self._toggle_menu(b, m))

            # Bind hover events for ultra-smooth menu switching
            btn.bind("<Enter>", lambda e, b=btn, m=menu: self._on_menu_hover_enter(b, m))

    def _create_tk_menu(self):
        """Returns ultra-modern dark dropdown menu matching VS Code / Photoshop / CapCut"""
        return ModernDropdownMenu(self, on_close=self._close_active_menu)

    def _toggle_menu(self, btn, menu):
        if self._active_open_menu == menu:
            self._close_active_menu()
            return
        self._open_menu(btn, menu)

    def _open_menu(self, btn, menu):
        if self._active_open_menu and self._active_open_menu != menu:
            try:
                self._active_open_menu.unpost()
            except Exception:
                pass

        # Reset all menu button highlights
        for b in self._menu_buttons.values():
            b.configure(fg_color="transparent", text_color="#cbd5e1")

        try:
            btn.configure(fg_color="#272a34", text_color="#ffffff")
            x = btn.winfo_rootx()
            y = btn.winfo_rooty() + btn.winfo_height() + 2
            menu.post(x, y)
            self._active_open_menu = menu
        except Exception:
            pass

    def _on_menu_hover_enter(self, btn, menu):
        # If any menu is already opened, hover instantly switches to this menu (VS Code behavior)
        if self._active_open_menu is not None and self._active_open_menu != menu:
            self._open_menu(btn, menu)

    def _close_active_menu(self):
        for b in self._menu_buttons.values():
            b.configure(fg_color="transparent", text_color="#cbd5e1")
        if self._active_open_menu:
            try:
                self._active_open_menu.unpost()
            except Exception:
                pass
            self._active_open_menu = None

    def _cmd(self, callback_name, *args):
        """Safe wrapper to execute a callback if defined"""
        def wrapper():
            self._close_active_menu()
            cb = self.callbacks.get(callback_name)
            if cb:
                cb(*args)
        return wrapper

    # ------------------ MENU BUILDERS ------------------
    def _build_file_menu(self):
        m = self._create_tk_menu()
        m.add_command(label="📂  Open Video... \tCtrl+O", command=lambda: [self._close_active_menu(), self.on_browse_video()])
        m.add_command(label="📑  Import Subtitles (.srt / .vtt)... \tCtrl+Shift+O", command=self._cmd("on_import_srt"))
        m.add_command(label="➕  Import Media Clip... \tCtrl+I", command=self._cmd("on_add_clip"))
        m.add_command(label="🎵  Import Background Music...", command=self._cmd("on_add_music"))
        m.add_separator()
        m.add_command(label="💾  Export Khmer SRT Subtitles... \tCtrl+S", command=self._cmd("on_export_srt"))
        m.add_command(label="🎬  Burn Subtitles to Video (MP4)...", command=self._cmd("on_burn_video"))
        m.add_command(label="🚀  Export Full Dubbed Movie (MP4)...", command=self._cmd("on_export_all"))
        m.add_separator()
        m.add_command(label="📁  Open Cloned Voices Directory...", command=self._cmd("on_open_voices"))
        m.add_command(label="📱  Open Mobile Phone APK Folder...", command=self._cmd("on_open_mobile_apk"))
        m.add_separator()
        m.add_command(label="🚪  Exit Studio \tAlt+F4", command=self._cmd("on_exit"))
        return m

    def _build_edit_menu(self):
        m = self._create_tk_menu()
        m.add_command(label="↩️  Undo \tCtrl+Z", command=self._cmd("on_undo"))
        m.add_command(label="↪️  Redo \tCtrl+Y", command=self._cmd("on_redo"))
        m.add_separator()
        m.add_command(label="✂️  Split Clip at Playhead \tCtrl+K", command=self._cmd("on_split_clip"))
        m.add_command(label="✂️  Trim Selected Clip \tCtrl+T", command=self._cmd("on_trim_clip"))
        m.add_command(label="🗑️  Delete Selected Clip \tDel", command=self._cmd("on_delete_clip"))
        m.add_separator()
        m.add_command(label="📑  Duplicate Active Dialogue", command=self._cmd("on_duplicate_sub"))
        m.add_command(label="🔄  Auto-Sync Speech Speed to Video", command=self._cmd("on_auto_sync_speed"))
        return m

    def _build_view_menu(self):
        m = self._create_tk_menu()
        m.add_command(label="🔍  Zoom UI In \tCtrl +", command=lambda: [self._close_active_menu(), self.on_zoom_in and self.on_zoom_in()])
        m.add_command(label="🔍  Zoom UI Out \tCtrl -", command=lambda: [self._close_active_menu(), self.on_zoom_out and self.on_zoom_out()])
        m.add_command(label="🔍  Reset UI Zoom (100%) \tCtrl 0", command=lambda: [self._close_active_menu(), self.on_zoom_reset and self.on_zoom_reset()])
        m.add_separator()
        m.add_command(label="📐  Format: Auto (Fit Original)", command=self._cmd("on_set_aspect_ratio", "Auto (Fit Original)"))
        m.add_command(label="📐  Format: 16:9 Cinema Landscape", command=self._cmd("on_set_aspect_ratio", "16:9 Landscape (YouTube/TV)"))
        m.add_command(label="📐  Format: 9:16 Mobile / TikTok", command=self._cmd("on_set_aspect_ratio", "9:16 Portrait (TikTok/Reels)"))
        m.add_command(label="📐  Format: 1:1 Instagram Square", command=self._cmd("on_set_aspect_ratio", "1:1 Square (Instagram)"))
        m.add_separator()
        m.add_command(label="👁️  Toggle Collapse Preview", command=self._cmd("on_toggle_collapse_preview"))
        m.add_command(label="🖥️  Toggle Fullscreen \tF11", command=self._cmd("on_toggle_fullscreen"))
        return m

    def _build_dubbing_menu(self):
        m = self._create_tk_menu()
        m.add_command(label="⚡  Start AI Movie Translation", command=lambda: [self._close_active_menu(), self.on_start_translate()])
        m.add_command(label="🎙️  Re-Dub All Dialogues", command=self._cmd("on_start_dubbing"))
        m.add_command(label="🦆  Toggle Auto-Ducking (duck sound on speech)", command=self._cmd("on_toggle_auto_ducking"))
        m.add_separator()
        m.add_command(label="🎤  Voice Actor: Piseth (ពិសិដ្ឋ - Male)", command=self._cmd("on_select_voice", "km-KH-PisethNeural"))
        m.add_command(label="🎤  Voice Actor: Sreymom (ស្រីមុំ - Female)", command=self._cmd("on_select_voice", "km-KH-SreymomNeural"))
        m.add_separator()
        m.add_command(label="🔑  Test & Verify Gemini API Key...", command=self._cmd("on_test_gemini_api"))
        return m

    def _build_tools_menu(self):
        m = self._create_tk_menu()
        m.add_command(label="🔤  Change Khmer Font...", command=self._cmd("on_font_change"))
        m.add_command(label="🎨  Subtitle Style Presets (Karaoke/Box/Glow)", command=self._cmd("on_cc_style_change"))
        m.add_command(label="🏷️  Watermark & Logo Positioning", command=self._cmd("on_watermark_settings"))
        m.add_separator()
        m.add_command(label="📱  Open Mobile Phone APK Version", command=self._cmd("on_open_mobile_apk"))
        return m

    def _build_help_menu(self):
        m = self._create_tk_menu()
        m.add_command(label="⌨️  Keyboard Shortcuts Guide...", command=self._cmd("on_show_shortcuts"))
        m.add_command(label="📱  Mobile Android APK Instructions...", command=self._cmd("on_open_mobile_apk"))
        m.add_separator()
        m.add_command(label="ℹ️  About AI Khmer Movie Studio...", command=self._cmd("on_show_about"))
        return m

    # ------------------ STATUS UPDATERS ------------------
    def set_filename(self, filename: str):
        if hasattr(self, "lbl_filename") and self.lbl_filename:
            display_name = os.path.basename(filename) if filename else ""
            self.lbl_filename.configure(text=f"🎬 {display_name}" if display_name else "", text_color="#10b981" if filename else "#64748b")

    def set_translating_state(self, is_translating: bool):
        if hasattr(self, "btn_translate") and self.btn_translate:
            self.btn_translate.configure(state="disabled" if is_translating else "normal")
        if hasattr(self, "btn_browse") and self.btn_browse:
            self.btn_browse.configure(state="disabled" if is_translating else "normal")

    def set_zoom_text(self, text: str):
        if hasattr(self, "lbl_zoom") and self.lbl_zoom:
            self.lbl_zoom.configure(text=text)

    def set_api_status(self, is_active: bool, model_name: str = "Gemini 3.5"):
        if hasattr(self, "lbl_api_badge") and self.lbl_api_badge:
            if is_active:
                self.lbl_api_badge.configure(
                    text=f"● {model_name}: Active",
                    text_color="#34d399"
                )
            else:
                self.lbl_api_badge.configure(
                    text="● API: Offline",
                    text_color="#f87171"
                )
