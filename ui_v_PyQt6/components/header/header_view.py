"""
Header View Component for PyQt6 / PySide6 Desktop Studio
Professional NLE Navigation Bar (Photoshop / Premiere Pro / FilmCraft Studio style)
Features:
- FilmCraft app branding with gradient icon badge
- Workspace Tabs: [Home] [Import] [Edit] [Dubbing] [Splitter] [Export] with active underline indicator
- Full Desktop Menu Bar customized for AI Khmer Movie Studio:
  File | Edit | Subtitles | Dubbing | Timeline | Tools | View | Help
- Right-aligned quick action buttons (Open Video, Master Export)
"""

from ui_v_PyQt6.qt_compat import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame, 
    QFont, QCursor, Qt, QSizePolicy, QMenuBar, QMenu, QMessageBox, QApplication,
    QComboBox
)
from ui_v_PyQt6.icons import (
    get_dub_icon, get_edit_icon, get_clock_icon, get_copy_icon,
    get_listen_icon, get_translate_icon, get_speed_icon, get_sync_icon,
    get_folder_icon, get_export_icon, get_qta_icon
)


class HeaderView(QWidget):
    """
    Premiere Pro / Photoshop / FilmCraft style Studio Navigation Header:
    - Left: badge & branding
    - Center-left: Workspace tabs with active underline indicator
    - Center: Application Menu Bar wired to all Movie Studio features
    - Right: Quick Action triggers (Open Video, Master Export)
    """
    def __init__(
        self,
        parent=None,
        on_browse_video=None,
        on_import_srt=None,
        on_export_srt=None,
        on_start_translate=None,
        on_capture_cc=None,
        on_generate_dub=None,
        on_dub_missing=None,
        on_export_movie=None,
        on_switch_tab=None,
        on_add_sub=None,
        on_delete_sub=None,
        on_fix_overlaps=None,
        on_toggle_timeline=None,
        on_toggle_logs=None,
        on_zoom_in=None,
        on_zoom_out=None,
        on_zoom_reset=None,
        on_auto_sync=None,
        on_clear_logs=None,
        on_listen_selected=None,
        on_toggle_audio_mix=None,
        on_toggle_cc_style=None,
        on_toggle_monitor=None,
        on_toggle_subtitles=None,
        on_toggle_inspector=None,
        on_toggle_properties=None,
        on_reset_panels=None,
        is_audio_mix_visible=None,
        is_cc_style_visible=None,
        is_timeline_visible=None,
        is_logs_visible=None,
        is_monitor_visible=None,
        is_subtitles_visible=None,
        is_inspector_visible=None,
        is_properties_visible=None,
        **extra_callbacks
    ):
        super().__init__(parent)
        self.on_browse_video = on_browse_video
        self.on_import_srt = on_import_srt
        self.on_export_srt = on_export_srt
        self.on_start_translate = on_start_translate
        self.on_capture_cc = on_capture_cc
        self.on_generate_dub = on_generate_dub
        self.on_dub_missing = on_dub_missing
        self.on_export_movie = on_export_movie
        self.on_switch_tab = on_switch_tab
        self.on_add_sub = on_add_sub
        self.on_delete_sub = on_delete_sub
        self.on_fix_overlaps = on_fix_overlaps
        self.on_toggle_timeline = on_toggle_timeline
        self.on_toggle_logs = on_toggle_logs
        self.on_zoom_in = on_zoom_in
        self.on_zoom_out = on_zoom_out
        self.on_zoom_reset = on_zoom_reset
        self.on_auto_sync = on_auto_sync
        self.on_clear_logs = on_clear_logs
        self.on_listen_selected = on_listen_selected
        self.on_toggle_audio_mix = on_toggle_audio_mix
        self.on_toggle_cc_style = on_toggle_cc_style
        self.on_toggle_monitor = on_toggle_monitor
        self.on_toggle_subtitles = on_toggle_subtitles
        self.on_toggle_inspector = on_toggle_inspector
        self.on_toggle_properties = on_toggle_properties
        self.on_reset_panels = on_reset_panels
        self.is_audio_mix_visible = is_audio_mix_visible
        self.is_cc_style_visible = is_cc_style_visible
        self.is_timeline_visible = is_timeline_visible
        self.is_logs_visible = is_logs_visible
        self.is_monitor_visible = is_monitor_visible
        self.is_subtitles_visible = is_subtitles_visible
        self.is_inspector_visible = is_inspector_visible
        self.is_properties_visible = is_properties_visible
        self.extra_callbacks = extra_callbacks

        self._active_tab = "edit"
        self._tab_buttons = {}

        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(30)
        self.setStyleSheet("""
            HeaderView {
                background-color: #141822;
                border-bottom: 1px solid #242c3d;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        # App Branding Tag
        lbl_brand = QLabel("🎬 AI Studio")
        lbl_brand.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold; padding-right: 6px;")
        layout.addWidget(lbl_brand)

        # 1. Desktop Small Line Menu Bar: File | Edit | View | Studio | Timeline | Subtitle | Translation | Voice | Tools | Export | Window | Help
        self.menu_bar = QMenuBar()
        self.menu_bar.setStyleSheet("""
            QMenuBar {
                background: transparent;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 500;
                border: none;
                margin: 0px;
                padding: 0px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 3px 8px;
                border-radius: 4px;
                color: #cbd5e1;
            }
            QMenuBar::item:selected {
                background-color: #272e3f;
                color: #ffffff;
            }
            QMenuBar::item:pressed {
                background-color: #1e2433;
                color: #38bdf8;
            }
            QMenu {
                background-color: #171b26;
                color: #f1f5f9;
                border: 1px solid #2d3748;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 22px 5px 10px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: #2d3748;
                margin: 3px 2px;
            }
        """)

        self._build_menus()
        layout.addWidget(self.menu_bar)

        self.btn_new = None
        self.btn_open = None
        self.btn_save = None
        self.btn_ai_flow = None
        self.lbl_project_name = None
        self.lbl_task_status = None
        self.lbl_telemetry = None

        layout.addStretch()

        # Right: Sleek Minimal Workspace Selector & Compact Export
        right_box = QHBoxLayout()
        right_box.setSpacing(6)

        self.lbl_ws = QLabel("Workspace:")
        self.combo_workspace = QComboBox()
        self.workspaces_list = [
            ("video_editing", "🎬 Video Editing"),
            ("ai_translation", "🌐 AI Translation"),
            ("voice_dubbing", "🎙️ Voice Dubbing"),
            ("subtitle_editing", "📝 Subtitle Editing"),
            ("audio_mixing", "🎚️ Audio Mixing"),
            ("color_grading", "🎨 Color Grading"),
            ("content_automation", "⚡ Content Automation"),
            ("multi_monitor", "🖥️ Multi-Monitor"),
        ]
        for wid, wlabel in self.workspaces_list:
            self.combo_workspace.addItem(wlabel, wid)
        self.combo_workspace.currentIndexChanged.connect(self._on_workspace_combo_changed)
        self.lbl_ws.hide()
        self.combo_workspace.hide()

        # Master Export Compact Button
        btn_master_exp = QPushButton("🚀 Export")
        btn_master_exp.setFixedHeight(22)
        btn_master_exp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_master_exp.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #4f46e5, stop:1 #6366f1);
                color: #ffffff;
                border: 1px solid #6366f1;
                font-size: 10px;
                font-weight: 700;
                padding: 0 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #818cf8);
                border-color: #a5b4fc;
            }
        """)
        if self.on_export_movie:
            btn_master_exp.clicked.connect(self.on_export_movie)
        right_box.addWidget(btn_master_exp)

        layout.addLayout(right_box)
        self._update_tab_styles()

    def set_project_name(self, name: str):
        """Updates the project name badge on the header toolbar."""
        if hasattr(self, "lbl_project_name") and self.lbl_project_name:
            display = name if len(name) < 24 else name[:22] + ".."
            self.lbl_project_name.setText(f"📁 {display}")

    def set_processing_status(self, is_busy: bool, text: str = "Ready"):
        """Displays live background processing status indicator."""
        if hasattr(self, "lbl_task_status") and self.lbl_task_status:
            if is_busy:
                self.lbl_task_status.setText(f"⚡ {text}")
                self.lbl_task_status.setStyleSheet("background-color: #20242D; color: #F5B84B; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 1px solid #F5B84B;")
            else:
                self.lbl_task_status.setText("🟢 Ready")
                self.lbl_task_status.setStyleSheet("background-color: #20242D; color: #2BC48A; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; border: 1px solid #343A46;")

    def set_telemetry(self, cpu_pct: int, gpu_pct: int):
        """Updates live CPU / GPU telemetry usage badge."""
        if hasattr(self, "lbl_telemetry") and self.lbl_telemetry:
            self.lbl_telemetry.setText(f"💻 CPU {cpu_pct}% | 🎮 GPU {gpu_pct}%")

    def _on_workspace_combo_changed(self, index: int):
        wid = self.combo_workspace.currentData()
        if hasattr(self, "workspace_selected_callback") and self.workspace_selected_callback:
            self.workspace_selected_callback(wid)
        parent_win = self.parent()
        while parent_win:
            if hasattr(parent_win, "apply_workspace"):
                parent_win.apply_workspace(wid)
                break
            parent_win = parent_win.parent()

    def _build_menus(self):
        """Constructs full desktop menus tailored for AI Creator Studio."""
        # 1. FILE MENU
        m_file = self.menu_bar.addMenu("File")
        act_open_v = m_file.addAction("📂 Open Video... (បើកវីដេអូ)")
        act_open_v.setShortcut("Ctrl+O")
        if self.on_browse_video:
            act_open_v.triggered.connect(self.on_browse_video)

        act_dl_v = m_file.addAction("📥 Download Video from URL... (ទាញយកវីដេអូពីតំណភ្ជាប់)")
        act_dl_v.triggered.connect(lambda: self._select_tab("downloader"))

        act_imp_srt = m_file.addAction("📥 Import Subtitles... (បញ្ចូល SRT)")
        act_imp_srt.setShortcut("Ctrl+I")
        if self.on_import_srt:
            act_imp_srt.triggered.connect(self.on_import_srt)

        act_exp_srt = m_file.addAction("💾 Export Subtitles... (រក្សាទុក SRT)")
        act_exp_srt.setShortcut("Ctrl+S")
        if self.on_export_srt:
            act_exp_srt.triggered.connect(self.on_export_srt)

        m_file.addSeparator()
        act_split = m_file.addAction("✂️ Split Large SRT File (បំបែក SRT ធំៗ)")
        act_split.triggered.connect(lambda: self._select_tab("splitter"))

        m_file.addSeparator()
        act_exp_mov = m_file.addAction("🚀 Master Export Movie... (Export វីដេអូពេញ)")
        act_exp_mov.setShortcut("Ctrl+E")
        if self.on_export_movie:
            act_exp_mov.triggered.connect(self.on_export_movie)

        m_file.addSeparator()
        act_exit = m_file.addAction("🚪 Exit (ចាកចេញ)")
        act_exit.setShortcut("Alt+F4")
        act_exit.triggered.connect(QApplication.quit)

        # 2. EDIT MENU
        m_edit = self.menu_bar.addMenu("Edit")
        act_add_s = m_edit.addAction("➕ Add Subtitle Line (បន្ថែមបន្ទាត់)")
        act_add_s.setShortcut("Ctrl+N")
        if self.on_add_sub:
            act_add_s.triggered.connect(self.on_add_sub)

        act_del_s = m_edit.addAction("🗑️ Delete Selected Subtitles (លុบบន្ទាត់)")
        act_del_s.setShortcut("Del")
        if self.on_delete_sub:
            act_del_s.triggered.connect(self.on_delete_sub)

        m_edit.addSeparator()
        act_fix_ov = m_edit.addAction("⚡ Auto-Fix Overlaps (កែម៉ោងជាន់គ្នា)")
        if self.on_fix_overlaps:
            act_fix_ov.triggered.connect(self.on_fix_overlaps)

        act_sync_r = m_edit.addAction("🔄 Auto-Sync Speech Rates (គណនាល្បឿននិយាយ)")
        if self.on_auto_sync:
            act_sync_r.triggered.connect(self.on_auto_sync)

        m_edit.addSeparator()
        act_clr_l = m_edit.addAction("🧹 Clear Diagnostic Console Logs")
        if self.on_clear_logs:
            act_clr_l.triggered.connect(self.on_clear_logs)

        # 3. VIEW MENU (WORKSPACES & PANELS)
        m_view = self.menu_bar.addMenu("View")
        act_ws_edit = m_view.addAction("🎬 Video Editing Workspace")
        act_ws_edit.triggered.connect(lambda: self._select_tab("edit"))
        act_ws_dl = m_view.addAction("📥 Video Downloader Workspace (ទាញយកវីដេអូ)")
        act_ws_dl.triggered.connect(lambda: self._select_tab("downloader"))
        act_ws_trans = m_view.addAction("🌐 AI Translation Workspace")
        act_ws_trans.triggered.connect(lambda: self._select_tab("edit"))
        act_ws_dub = m_view.addAction("🎙️ Voice Dubbing Workspace")
        act_ws_dub.triggered.connect(lambda: self._select_tab("dubbing"))
        act_ws_spl = m_view.addAction("✂️ Subtitle Splitter Workspace")
        act_ws_spl.triggered.connect(lambda: self._select_tab("splitter"))
        act_ws_tools = m_view.addAction("🎬 Video Tools & Shorts Splitter")
        act_ws_tools.triggered.connect(lambda: self._select_tab("video_tools"))
        act_ws_brand = m_view.addAction("⭐ Templates & Branding Studio (ម៉ាកសញ្ញា & Sponsor Ads)")
        act_ws_brand.triggered.connect(lambda: self._select_tab("branding"))
        m_view.addSeparator()
        act_reset_layout = m_view.addAction("🔄 Reset Layout to Default (កំណត់ប្លង់ដើមឡើងវិញ)")
        if self.on_reset_panels:
            act_reset_layout.triggered.connect(self.on_reset_panels)
        act_dual_screen = m_view.addAction("🖥️ Dual Monitor Layout (បញ្ចាំងលើ Monitor 2)")
        if hasattr(self, "extra_callbacks") and self.extra_callbacks.get("on_dual_monitor_layout"):
            act_dual_screen.triggered.connect(self.extra_callbacks.get("on_dual_monitor_layout"))
        m_view.addSeparator()
        act_tog_logs = m_view.addAction("📜 Toggle Diagnostic Feed (Logs)")
        if self.on_toggle_logs:
            act_tog_logs.triggered.connect(self.on_toggle_logs)

        # 4. STUDIO MENU (Modules & Studios)
        m_studio = self.menu_bar.addMenu("Studio")
        self.act_mod_edit = m_studio.addAction("🎬 Studio Video Editor (កាត់តវីដេអូ)")
        self.act_mod_edit.setCheckable(True)
        self.act_mod_edit.setChecked(True)
        self.act_mod_edit.setShortcut("Ctrl+1")
        self.act_mod_edit.triggered.connect(lambda: self._select_tab("edit"))

        self.act_mod_dl = m_studio.addAction("📥 Video Downloader (ទាញយកវីដេអូ)")
        self.act_mod_dl.setCheckable(True)
        self.act_mod_dl.setShortcut("Ctrl+2")
        self.act_mod_dl.triggered.connect(lambda: self._select_tab("downloader"))

        self.act_mod_dub = m_studio.addAction("🎙️ Voice Dub Studio (បញ្ចូលសំឡេង AI)")
        self.act_mod_dub.setCheckable(True)
        self.act_mod_dub.setShortcut("Ctrl+3")
        self.act_mod_dub.triggered.connect(lambda: self._select_tab("dubbing"))

        self.act_mod_spl = m_studio.addAction("✂️ SRT Subtitle Splitter (បំបែក SRT ធំៗ)")
        self.act_mod_spl.setCheckable(True)
        self.act_mod_spl.setShortcut("Ctrl+4")
        self.act_mod_spl.triggered.connect(lambda: self._select_tab("splitter"))

        self.act_mod_tools = m_studio.addAction("🛠️ Video Tools & Shorts Splitter (ឧបករណ៍កាត់ត)")
        self.act_mod_tools.setCheckable(True)
        self.act_mod_tools.setShortcut("Ctrl+5")
        self.act_mod_tools.triggered.connect(lambda: self._select_tab("video_tools"))

        self.act_mod_brand = m_studio.addAction("⭐ Templates & Branding (ម៉ាកសញ្ញា & Sponsor Ads)")
        self.act_mod_brand.setCheckable(True)
        self.act_mod_brand.setShortcut("Ctrl+6")
        self.act_mod_brand.triggered.connect(lambda: self._select_tab("branding"))

        # 5. PROJECT MENU
        m_proj = self.menu_bar.addMenu("Project")
        m_proj.addAction("📐 Aspect Ratio: 16:9 Landscape (Cinema/YouTube)").triggered.connect(lambda: None)
        m_proj.addAction("📱 Aspect Ratio: 9:16 Vertical (TikTok/Shorts)").triggered.connect(lambda: None)
        m_proj.addAction("🔲 Aspect Ratio: 1:1 Square (Instagram)").triggered.connect(lambda: None)
        m_proj.addSeparator()
        m_proj.addAction("⚙️ Project Settings & Properties...").triggered.connect(lambda: None)

        # 5. TIMELINE MENU
        m_tl = self.menu_bar.addMenu("Timeline")
        act_tog_tl = m_tl.addAction("🎛️ Toggle Timeline Panel (បង្ហាញ/លាក់ Timeline)")
        if self.on_toggle_timeline:
            act_tog_tl.triggered.connect(self.on_toggle_timeline)
        m_tl.addSeparator()
        act_split_cut = m_tl.addAction("✂️ Razor Cut at Playhead (C / Ctrl+B)")
        act_split_cut.triggered.connect(lambda: None)
        act_zi = m_tl.addAction("🔍 Zoom In (Ctrl++)")
        if self.on_zoom_in:
            act_zi.triggered.connect(self.on_zoom_in)
        act_zo = m_tl.addAction("🔍 Zoom Out (Ctrl+-)")
        if self.on_zoom_out:
            act_zo.triggered.connect(self.on_zoom_out)
        act_zr = m_tl.addAction("🔄 Reset Zoom (Ctrl+0)")
        if self.on_zoom_reset:
            act_zr.triggered.connect(self.on_zoom_reset)

        # 6. SUBTITLE MENU
        m_subs = self.menu_bar.addMenu("Subtitle")
        m_asr = m_subs.addMenu("🎙️ Speech-to-Text / ចាប់យកអក្សរ (ASR)")
        act_wx = m_asr.addAction("🎯 WhisperX (AI Diarization - បំបែកសំឡេងតួអង្គ A/B + Word Timestamps)")
        if self.on_capture_cc:
            act_wx.triggered.connect(lambda: self.on_capture_cc("whisperx"))
        act_fw = m_asr.addAction("⚡ Faster-Whisper (Multi-Language / ភាសាចម្រុះ)")
        if self.on_capture_cc:
            act_fw.triggered.connect(lambda: self.on_capture_cc("whisper"))
        act_sv = m_asr.addAction("🇨🇳 SenseVoice-Small + CAM++ (Alibaba - ASR + Emotion SER + Events + Diarization)")
        if self.on_capture_cc:
            act_sv.triggered.connect(lambda: self.on_capture_cc("funasr"))
        act_fix_ov2 = m_subs.addAction("⚡ Fix Overlapping Timestamps (កែសម្រួលកុំឱ្យជាន់គ្នា)")
        if self.on_fix_overlaps:
            act_fix_ov2.triggered.connect(self.on_fix_overlaps)
        act_chunker = m_subs.addAction("✂️ SRT Splitter & AI Chunker (បំបែក SRT ជាកង់ៗ)")
        act_chunker.triggered.connect(lambda: self._select_tab("splitter"))

        # 7. TRANSLATION MENU
        m_trans = self.menu_bar.addMenu("Translation")
        act_trans_all = m_trans.addAction("🌐 Translate All Subtitles (បកប្រែទាំងអស់)")
        act_trans_all.setShortcut("Ctrl+T")
        if self.on_start_translate:
            act_trans_all.triggered.connect(self.on_start_translate)
        m_trans.addAction("🤖 Google GTX Free Multi-Client Engine").triggered.connect(lambda: None)
        m_trans.addAction("🧠 Google Gemini AI Dialogue Translation").triggered.connect(lambda: None)
        m_trans.addAction("💡 OpenAI ChatGPT Dubbing Translation").triggered.connect(lambda: None)

        # 8. VOICE MENU
        m_dub = self.menu_bar.addMenu("Voice")
        act_dub_all = m_dub.addAction("🎧 Dub All Lines (បញ្ចូលសំឡេង AI គ្រប់បន្ទាត់)")
        if self.on_generate_dub:
            act_dub_all.triggered.connect(self.on_generate_dub)
        act_dub_miss = m_dub.addAction("⚡ Dub Missing Lines Only (បពេញសំឡេងដែលខ្វះ)")
        if self.on_dub_missing:
            act_dub_miss.triggered.connect(self.on_dub_missing)
        m_dub.addSeparator()
        act_listen = m_dub.addAction("🔊 Listen Selected Line (ស្ដាប់សំឡេងបន្ទាត់ដែលជ្រើសរើស)")
        act_listen.setShortcut("L")
        if self.on_listen_selected:
            act_listen.triggered.connect(self.on_listen_selected)
        act_quick_tts = m_dub.addAction("🎙️ Quick Speech & MP3 Studio (បង្កើតសំឡេងផ្ទាល់ខ្លួន)")
        act_quick_tts.triggered.connect(lambda: self._select_tab("dubbing"))

        # 9. AUDIO MENU
        m_audio = self.menu_bar.addMenu("Audio")
        m_audio.addAction("🎚️ Multi-Track Audio Mixer Panel").triggered.connect(lambda: None)
        m_audio.addAction("🔇 Mute Chinese Dialogue by SRT").triggered.connect(lambda: None)
        m_audio.addAction("🦆 Auto-Audio Ducking for Background Music").triggered.connect(lambda: None)

        # 10. TOOLS MENU
        m_tools = self.menu_bar.addMenu("Tools")
        act_t_dl = m_tools.addAction("📥 Video Downloader (ទាញយកវីដេអូ YouTube / TikTok / Facebook / Douyin)")
        act_t_dl.triggered.connect(lambda: self._select_tab("downloader"))
        act_t_tools = m_tools.addAction("🎬 Video Tools & Shorts Splitter (ឧបករណ៍កាត់ត Shorts)")
        act_t_tools.triggered.connect(lambda: self._select_tab("video_tools"))
        act_t_spl = m_tools.addAction("✂️ SRT Subtitle Splitter & Chunker (បំបែក SRT ធំៗ)")
        act_t_spl.triggered.connect(lambda: self._select_tab("splitter"))
        act_t_dub = m_tools.addAction("🎙️ Quick Voice Dub Studio (ស្ទូឌីយោសំឡេង AI)")
        act_t_dub.triggered.connect(lambda: self._select_tab("dubbing"))

        # 11. AI TOOLS MENU
        m_ai = self.menu_bar.addMenu("AI Tools")
        m_ai.addAction("📱 Auto Reframe 9:16 (MediaPipe Face Tracking)").triggered.connect(lambda: None)
        m_ai.addAction("👥 Speaker Diarization (Actor A / Actor B Detection)").triggered.connect(lambda: None)
        m_ai.addAction("🧬 Voice Cloning Profile Manager").triggered.connect(lambda: None)
        m_ai.addAction("🎼 Vocal & Background Music Separation (Demucs)").triggered.connect(lambda: None)

        # 11. EXPORT MENU
        m_exp = self.menu_bar.addMenu("Export")
        act_m_exp = m_exp.addAction("🚀 Master Export Video (NVENC/QSV/CPU)")
        if self.on_export_movie:
            act_m_exp.triggered.connect(self.on_export_movie)
        m_exp.addAction("📄 Export Khmer Subtitles (.SRT)").triggered.connect(lambda: self.on_export_srt() if self.on_export_srt else None)
        m_exp.addAction("🎵 Export Dubbed Audio Mix (.MP3)").triggered.connect(lambda: None)

        # 12. SETTINGS MENU
        m_settings = self.menu_bar.addMenu("Settings")
        m_settings.addAction("⌨️ Keyboard Shortcuts Configuration...").triggered.connect(self._show_shortcuts_dialog)
        m_settings.addAction("🎨 Theme: Professional Dark Theme (Active)").triggered.connect(lambda: None)
        m_settings.addAction("🔑 AI Engine API Keys Setup...").triggered.connect(lambda: None)

        # 13. HELP MENU
        m_help = self.menu_bar.addMenu("Help")
        act_sc = m_help.addAction("⌨️ Keyboard Shortcuts Reference (Ctrl+/)")
        act_sc.triggered.connect(self._show_shortcuts_dialog)
        act_about = m_help.addAction("ℹ️ About AI Creator Studio (អំពីកម្មវិធី)")
        act_about.triggered.connect(self._show_about_dialog)

        # WINDOW SUBMENU FOR DOCKING CHECKS
        m_win = self.menu_bar.addMenu("Window")

        self.act_p_audio = m_win.addAction("Multi-Track Audio Mix (សំឡេងច្រើន Track)")
        self.act_p_audio.setIcon(get_dub_icon(16))
        self.act_p_audio.setCheckable(True)
        self.act_p_audio.setChecked(True)
        self.act_p_audio.triggered.connect(self._on_toggle_audio_mix_action)

        self.act_p_cc = m_win.addAction("Master Export Panel (ផ្ទាំង Export)")
        self.act_p_cc.setIcon(get_export_icon(16))
        self.act_p_cc.setCheckable(True)
        self.act_p_cc.setChecked(True)
        self.act_p_cc.triggered.connect(self._on_toggle_cc_style_action)

        self.act_p_tl = m_win.addAction("Timelines Panel (ផ្ទាំងពេលវេលា / កាត់ត)")
        self.act_p_tl.setIcon(get_clock_icon(16))
        self.act_p_tl.setCheckable(True)
        self.act_p_tl.triggered.connect(self._on_toggle_timeline_action)

        self.act_p_logs = m_win.addAction("Logs & Diagnostic Feed (ផ្ទាំងកំណត់ហេតុ)")
        self.act_p_logs.setIcon(get_copy_icon(16))
        self.act_p_logs.setCheckable(True)
        self.act_p_logs.setChecked(True)
        self.act_p_logs.triggered.connect(self._on_toggle_logs_action)

        m_win.addSeparator()

        self.act_p_mon = m_win.addAction("Video Monitor & Player (ផ្ទាំងមើលវីដេអូ)")
        self.act_p_mon.setIcon(get_listen_icon(16))
        self.act_p_mon.setCheckable(True)
        self.act_p_mon.setChecked(True)
        self.act_p_mon.triggered.connect(self._on_toggle_monitor_action)

        self.act_p_subs = m_win.addAction("Subtitles Dialogue Editor (ផ្ទាំងអត្ថបទរត់)")
        self.act_p_subs.setIcon(get_translate_icon(16))
        self.act_p_subs.setCheckable(True)
        self.act_p_subs.setChecked(True)
        self.act_p_subs.triggered.connect(self._on_toggle_subtitles_action)

        self.act_p_insp = m_win.addAction("Dubbing & Export Inspector (ផ្ទាំងខាងស្តាំ)")
        self.act_p_insp.setIcon(get_speed_icon(16))
        self.act_p_insp.setCheckable(True)
        self.act_p_insp.setChecked(True)
        self.act_p_insp.triggered.connect(self._on_toggle_inspector_action)

        self.act_p_props = m_win.addAction("Object Properties Inspector (ផ្ទាំង Properties កែវត្ថុ)")
        self.act_p_props.setIcon(get_qta_icon("fa5s.sliders-h", color="#38bdf8") if get_qta_icon else get_speed_icon(16))
        self.act_p_props.setCheckable(True)
        self.act_p_props.setChecked(True)
        self.act_p_props.triggered.connect(self._on_toggle_properties_action)

        m_win.addSeparator()

        act_dual = m_win.addAction("🖥️ Multi-Monitor / Float Monitor (ផ្ទាំងបញ្ចាំងលើ Monitor ទី២)")
        act_dual.setIcon(get_qta_icon("fa5s.desktop", color="#38bdf8") if get_qta_icon else get_sync_icon(16))
        act_dual.triggered.connect(lambda: getattr(self, "on_dual_monitor_layout", lambda: None)())

        act_sub_layout = m_win.addAction("📝 Subtitling Focus Layout (ប្លង់ផ្ដោតលើ Subtitle)")
        act_sub_layout.setIcon(get_qta_icon("fa5s.closed-captioning", color="#38bdf8") if get_qta_icon else get_sync_icon(16))
        act_sub_layout.triggered.connect(lambda: getattr(self, "on_subtitling_layout", lambda: None)())

        act_reset = m_win.addAction("Reset to Default Layout (កំណត់ប្លង់ដើម)")
        act_reset.setIcon(get_sync_icon(16))
        act_reset.triggered.connect(self._on_reset_panels_action)

        m_win.aboutToShow.connect(self._sync_window_menu_checks)

        # 8. HELP MENU
        m_help = self.menu_bar.addMenu("Help")

        act_sc = m_help.addAction("⌨️ Keyboard Shortcuts (គ្រាប់ចុចកាត់)")
        act_sc.triggered.connect(self._show_shortcuts_dialog)

        act_about = m_help.addAction("ℹ️ About FilmCraft Studio (អំពីកម្មវិធី)")
        act_about.triggered.connect(self._show_about_dialog)

    def _on_toggle_audio_mix_action(self):
        if self.on_toggle_audio_mix:
            self.on_toggle_audio_mix()
        self._sync_window_menu_checks()

    def _on_toggle_cc_style_action(self):
        if self.on_toggle_cc_style:
            self.on_toggle_cc_style()
        self._sync_window_menu_checks()

    def _on_toggle_timeline_action(self):
        if self.on_toggle_timeline:
            self.on_toggle_timeline()
        self._sync_window_menu_checks()

    def _on_toggle_logs_action(self):
        if self.on_toggle_logs:
            self.on_toggle_logs()
        self._sync_window_menu_checks()

    def _on_toggle_monitor_action(self):
        if self.on_toggle_monitor:
            self.on_toggle_monitor()
        self._sync_window_menu_checks()

    def _on_toggle_subtitles_action(self):
        if self.on_toggle_subtitles:
            self.on_toggle_subtitles()
        self._sync_window_menu_checks()

    def _on_toggle_inspector_action(self):
        if self.on_toggle_inspector:
            self.on_toggle_inspector()
        self._sync_window_menu_checks()

    def _on_toggle_properties_action(self):
        if self.on_toggle_properties:
            self.on_toggle_properties()
        self._sync_window_menu_checks()

    def _on_reset_panels_action(self):
        if self.on_reset_panels:
            self.on_reset_panels()
        self._sync_window_menu_checks()

    def _sync_window_menu_checks(self):
        if hasattr(self, "act_p_audio") and self.is_audio_mix_visible:
            try:
                self.act_p_audio.setChecked(bool(self.is_audio_mix_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_cc") and self.is_cc_style_visible:
            try:
                self.act_p_cc.setChecked(bool(self.is_cc_style_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_tl") and self.is_timeline_visible:
            try:
                self.act_p_tl.setChecked(bool(self.is_timeline_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_logs") and self.is_logs_visible:
            try:
                self.act_p_logs.setChecked(bool(self.is_logs_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_mon") and self.is_monitor_visible:
            try:
                self.act_p_mon.setChecked(bool(self.is_monitor_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_subs") and self.is_subtitles_visible:
            try:
                self.act_p_subs.setChecked(bool(self.is_subtitles_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_insp") and self.is_inspector_visible:
            try:
                self.act_p_insp.setChecked(bool(self.is_inspector_visible()))
            except Exception:
                pass
        if hasattr(self, "act_p_props") and self.is_properties_visible:
            try:
                self.act_p_props.setChecked(bool(self.is_properties_visible()))
            except Exception:
                pass

    def _show_shortcuts_dialog(self):
        try:
            from ui_v_PyQt6.components.shortcuts_dialog import KeyboardShortcutsDialog
            dlg = KeyboardShortcutsDialog(self)
            dlg.exec()
        except Exception:
            msg = (
                "<b>FilmCraft - Studio Keyboard Shortcuts:</b><br><br>"
                "• <b>Space:</b> Play / Pause Video<br>"
                "• <b>← / →:</b> Seek ±2s (Shift: ±5s, Ctrl: 1-frame)<br>"
                "• <b>↑ / ↓:</b> Volume ±5%<br>"
                "• <b>M:</b> Mute / Unmute<br>"
                "• <b>[ / ]:</b> Jump Prev / Next Subtitle<br>"
                "• <b>C / S:</b> Add / Split Subtitle at Playhead<br>"
                "• <b>Delete:</b> Delete selected Subtitle or Overlay<br>"
                "• <b>Ctrl + O:</b> Open Video file<br>"
                "• <b>Ctrl + I:</b> Import SRT Subtitles<br>"
                "• <b>Ctrl + S:</b> Export SRT Subtitles<br>"
                "• <b>Ctrl + E:</b> Master Export Movie<br>"
                "• <b>Ctrl + Z / Y:</b> Undo / Redo<br>"
                "• <b>F:</b> Fullscreen Monitor Mode<br>"
                "• <b>T:</b> Toggle Timeline Panel<br>"
                "• <b>Ctrl + +/-:</b> Zoom UI in/out<br>"
            )
            QMessageBox.information(self, "Keyboard Shortcuts", msg)

    def _show_about_dialog(self):
        msg = (
            "<h3>FilmCraft - AI Khmer Movie Studio</h3>"
            "<p>Professional Desktop Video Dubbing & Subtitle Translation Suite.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Hardware-accelerated 60fps rendering & video monitor</li>"
            "<li>Multi-Track Filmstrip, CC & Audio timeline</li>"
            "<li>Faster-Whisper CUDA speech recognition</li>"
            "<li>Edge-TTS Neural & Google Gemini 2.0 AI Audio</li>"
            "<li>Smart dialogue centering & anti-collision</li>"
            "<li>SRT Splitter & AI Chunker for 6,000+ cues</li>"
            "</ul>"
            "<p><i>Powered by Google DeepMind & AI Khmer Studio</i></p>"
        )
        QMessageBox.about(self, "About FilmCraft Studio", msg)

    def _create_vsep(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setStyleSheet("color: #272d3a; max-width: 1px; margin: 6px 3px;")
        return sep

    def _on_tab_click(self, tab_id: str):
        if tab_id == "export":
            if self.on_export_movie:
                self.on_export_movie()
            return
        self._select_tab(tab_id)

    def _select_tab(self, tab_id: str):
        alias_map = {
            "import": "downloader",
            "studio": "edit",
            "home": "edit",
            "tts": "dubbing",
            "srt_splitter": "splitter",
            "tools": "video_tools",
            "media_tools": "video_tools",
            "branding": "branding",
            "templates": "branding"
        }
        eff = alias_map.get(tab_id, tab_id)
        self._active_tab = eff
        self._update_tab_styles()
        if self.on_switch_tab:
            self.on_switch_tab(eff)

    def set_active_tab(self, tab_id: str):
        # Normalize tab_id aliases
        alias_map = {
            "import": "downloader",
            "studio": "edit",
            "home": "edit",
            "tts": "dubbing",
            "srt_splitter": "splitter",
            "tools": "video_tools",
            "media_tools": "video_tools",
            "branding": "branding",
            "templates": "branding"
        }
        self._active_tab = alias_map.get(tab_id, tab_id)
        self._update_tab_styles()

    def _update_tab_styles(self):
        mod_actions = {
            "edit": getattr(self, "act_mod_edit", None),
            "downloader": getattr(self, "act_mod_dl", None),
            "dubbing": getattr(self, "act_mod_dub", None),
            "splitter": getattr(self, "act_mod_spl", None),
            "video_tools": getattr(self, "act_mod_tools", None),
            "branding": getattr(self, "act_mod_brand", None),
        }
        for tid, act in mod_actions.items():
            if act:
                act.blockSignals(True)
                act.setChecked(tid == self._active_tab or (tid == "edit" and self._active_tab in ("home", "studio")))
                act.blockSignals(False)

        for tid, btn in self._tab_buttons.items():
            is_active = (tid == self._active_tab) or (tid == "home" and self._active_tab in ("home", "edit", "studio"))
            if tid != "home" and self._active_tab == "home":
                is_active = (tid == "edit")

            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background: rgba(102, 117, 255, 0.15);
                        color: #ffffff;
                        font-weight: 700;
                        font-size: 11px;
                        font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;
                        border: 1px solid #6675FF;
                        border-bottom: 2.5px solid #6675FF;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #94a3b8;
                        font-weight: 500;
                        font-size: 11px;
                        font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;
                        border: 1px solid transparent;
                        border-radius: 4px;
                        padding: 3px 8px;
                    }
                    QPushButton:hover {
                        background: #20242D;
                        color: #e2e8f0;
                        border: 1px solid #343A46;
                    }
                """)

    def resizeEvent(self, event):
        """
        Adaptive toolbar & responsive layout handler for HeaderView.
        Intelligently adapts text labels, telemetry meters, and badge visibility
        to eliminate overlapping, clipped buttons, and layout breaking.
        """
        super().resizeEvent(event)
        w = self.width()

        if hasattr(self, "btn_new") and self.btn_new:
            if w >= 1260:
                self.btn_new.setText("+ New")
                if self.btn_open: self.btn_open.setText("Open")
                if self.btn_save: self.btn_save.setText("Save")
                if self.btn_ai_flow: self.btn_ai_flow.setText("⚡ AI Workflow")
            elif w >= 980:
                self.btn_new.setText("")
                if self.btn_open: self.btn_open.setText("")
                if self.btn_save: self.btn_save.setText("")
                if self.btn_ai_flow: self.btn_ai_flow.setText("⚡ AI")
            else:
                self.btn_new.setText("")
                if self.btn_open: self.btn_open.setText("")
                if self.btn_save: self.btn_save.setText("")
                if self.btn_ai_flow: self.btn_ai_flow.setText("")

        if hasattr(self, "lbl_ws") and self.lbl_ws:
            if w < 750:
                self.lbl_ws.hide()
            else:
                self.lbl_ws.show()

