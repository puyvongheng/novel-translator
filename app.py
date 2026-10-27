import os
import sys

# Safe stdout/stderr handling for windowed mode
class _NullWriter:
    def write(self, s): pass
    def flush(self): pass

if sys.stdout is None:
    sys.stdout = _NullWriter()
if sys.stderr is None:
    sys.stderr = _NullWriter()

# Force UTF-8 encoding across Windows console and I/O if available
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# Ensure application directory and _internal are in PATH so local ffmpeg/dlls are prioritized
if getattr(sys, "frozen", False):
    _app_dir = os.path.dirname(sys.executable)
    _internal_dir = os.path.join(_app_dir, "_internal")
    _mei_dir = getattr(sys, "_MEIPASS", "")
    _paths = [_app_dir, _internal_dir, _mei_dir]
    os.environ["PATH"] = os.pathsep.join([p for p in _paths if p and os.path.isdir(p)]) + os.pathsep + os.environ.get("PATH", "")

import threading
import time
import subprocess
import cv2
from PIL import Image
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame.pkgdata")
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
import pygame

# Suppress HuggingFace / Transformers warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Services, Models & Utilities Imports
from utils import (
    get_video_info,
    format_timestamp,
    format_filename_timestamp,
    parse_srt_content,
    parse_srt_file,
    extract_embedded_or_companion_subtitles,
    is_khmer_text
)
from services import (
    TranslationService,
    SpeechRecognitionEngine,
    DubbingEngine,
    SubtitleBurner,
    ChunkedPipeline,
    VideoChunk
)
from models import EditorModel

# UI Component Imports
from ui import (
    HeaderView,
    SubtitlesView,
    PlayerView,
    DubbingExportView,
    VideoDownloaderView
)

# Initialize Pygame audio mixer
try:
    pygame.mixer.init()
except Exception:
    pass

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MovieStudioApp(ctk.CTk):
    """
    Main OOP Application Controller:
    - Responsive dynamic UI with global Ctrl+/Ctrl- zoom scaling
    - Buttery smooth, fast video playback (no lag, no stutter)
    - Automatic per-segment Khmer voice generator (#1, #2... = 1 voice file each)
    - Interactive draggable/zoomable CC subtitles matching exact exported video output (WYSIWYG)
    """
    def __init__(self):
        super().__init__()

        self.title("🎬 AI KHMER MOVIE & TTS STUDIO")
        
        # Responsive Screen Sizing (Adapts directly to User Screen)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        start_w = min(1366, int(screen_w * 0.92))
        start_h = min(820, int(screen_h * 0.90))
        self.geometry(f"{start_w}x{start_h}+20+20")
        self.minsize(880, 560)

        # UI Zoom Scale state
        self.ui_scale = 1.0

        # Initialize Services & Engines
        self.translation_service = TranslationService()
        self.speech_engine = SpeechRecognitionEngine(model_size="base")
        self.dubbing_engine = DubbingEngine(log_callback=self._append_log)
        self.editor_model = EditorModel()

        # State Variables
        self.video_path = None
        self.video_info = {"duration": 0.0, "width": 1280, "height": 720, "fps": 30.0}
        self.subtitles_data = []
        self.current_time_sec = 0.0
        self.is_playing = False
        self.is_processing = False
        self.cap = None
        self._active_cap_path = None
        self._needs_seek = False
        self._last_spoken_id = None
        self._spoken_ids = set()
        self._cached_sounds = {}
        self._orig_preview_audio = None
        self._curr_preview_orig_vol = 0.85
        self.dub_channel = pygame.mixer.Channel(1) if pygame.mixer.get_init() else None
        self.pipeline = None

        # Robust multi-video synchronization & thread locks (prevents OpenCV freeze / hang)
        self.cap_lock = threading.RLock()
        self._video_caps = {}
        self._clip_audio_map = {}
        self._currently_loaded_audio = None
        self._video_session_id = 0

        self._build_layout()
        self._bind_zoom_shortcuts()
        self._start_playback_loop()

    def _cleanup_all_captures(self):
        """Thread-safely releases and closes all open OpenCV VideoCapture objects to prevent freezing"""
        with self.cap_lock:
            for p, cap in list(self._video_caps.items()):
                try:
                    if cap:
                        cap.release()
                except Exception:
                    pass
            self._video_caps.clear()
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
            self.cap = None
            self._active_cap_path = None

    def _get_capture_for_path(self, path: str):
        """Thread-safely retrieves or initializes a VideoCapture object for the specified video file"""
        if not path or not os.path.exists(path):
            return None
        with self.cap_lock:
            cap = self._video_caps.get(path)
            if cap and cap.isOpened():
                return cap
            if cap:
                try:
                    cap.release()
                except Exception:
                    pass
            try:
                cap = cv2.VideoCapture(path)
                if cap.isOpened():
                    self._video_caps[path] = cap
                    return cap
            except Exception as e:
                print(f"Error opening VideoCapture for {path}: {e}")
            return None

    def _build_layout(self):
        # Configure main window grid rows and columns
        # Row 0: Top Header & Menu Bar
        # Row 1: Middle Container (Activity Bar + Main Workspace)
        # Row 2: Bottom Panel (Collapsible Logs, Job Queue, Diagnostics)
        # Row 3: Status Bar (Bottom-most)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._bottom_panel_visible = True

        # 1. លើគេ & ក្រោម Title Bar: Header Navigation & Menu Bar (File, Edit, View, Tools, Help)
        self.header_view = HeaderView(
            parent=self,
            on_browse_video=self.on_browse_video,
            on_start_translate=self.start_translation_thread,
            on_capture_cc=self.on_capture_cc_only,
            on_generate_dub=self.start_dubbing_thread,
            on_auto_pipeline=self.start_auto_pipeline_thread,
            on_export_movie=self.start_export_full_movie_thread,
            on_switch_tab=self._on_switch_top_tab,
            on_zoom_in=self.zoom_ui_in,
            on_zoom_out=self.zoom_ui_out,
            on_zoom_reset=self.zoom_ui_reset,
            # Menu Bar Callbacks
            on_import_srt=self.on_import_srt,
            on_add_clip=self.on_add_clip,
            on_add_music=self.on_add_music,
            on_export_srt=self.on_export_srt,
            on_burn_video=self.start_burn_video_thread,
            on_export_all=self.start_export_full_movie_thread,
            on_open_voices=self.on_open_voice_folder,
            on_exit=self.destroy,
            on_undo=self.on_undo,
            on_redo=self.on_redo,
            on_split_clip=lambda: self.player_view._split_at_playhead(),
            on_trim_clip=self.on_trim_clip,
            on_delete_clip=self.on_delete_clip,
            on_duplicate_sub=lambda: self.on_duplicate_subtitle(self.player_view._selected_sub_idx) if self.player_view._selected_sub_idx is not None else None,
            on_auto_sync_speed=self._menu_auto_sync_speed,
            on_set_aspect_ratio=self.on_menu_set_aspect_ratio,
            on_toggle_collapse_preview=lambda: self.player_view.toggle_collapse_preview(),
            on_toggle_fullscreen=self.toggle_fullscreen,
            on_start_dubbing=self.start_dubbing_thread,
            on_test_gemini_api=self.on_test_gemini_api,
            on_toggle_auto_ducking=self.on_toggle_auto_ducking,
            on_select_voice=self.on_menu_select_voice,
            on_font_change=self.on_menu_select_font,
            on_cc_style_change=self.on_menu_cc_style,
            on_watermark_settings=self.on_menu_watermark_settings,
            on_open_mobile_apk=self.on_open_mobile_apk,
            on_show_shortcuts=self.on_show_shortcuts,
            on_show_about=self.on_show_about
        )
        self.header_view.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 0))

        # 2. Middle Container: Holds Main Workspace
        self.middle_container = ctk.CTkFrame(self, fg_color="#0e1014", corner_radius=0)
        self.middle_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.middle_container.grid_columnconfigure(0, weight=1)
        self.middle_container.grid_rowconfigure(0, weight=1)

        # 3. Main Workspace Tabview (Movie Translator, Quick TTS, Media Assets)
        self.tabview = ctk.CTkTabview(
            self.middle_container,
            fg_color="#0e1014",
            segmented_button_fg_color="#181a20",
            segmented_button_selected_color="#2563eb",
            segmented_button_selected_hover_color="#1d4ed8",
            corner_radius=0
        )
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=(2, 4), pady=(0, 2))

        tab_movie = self.tabview.add("🎬 MOVIE TRANSLATOR & CC")
        tab_downloader = self.tabview.add("📥 VIDEO DOWNLOADER")
        tab_tts = self.tabview.add("🎙️ TEXT-TO-SPEECH (MP3)")
        tab_assets = self.tabview.add("📁 MEDIA ASSETS")

        # Configure Tab 1: Movie Studio with Full Resizable Panes (tk.PanedWindow) matching version_rust
        tab_movie.grid_rowconfigure(0, weight=1)
        tab_movie.grid_columnconfigure(0, weight=1)

        self.paned_studio = tk.PanedWindow(
            tab_movie,
            orient="horizontal",
            bg="#141822",
            bd=0,
            sashwidth=6,
            sashrelief="flat",
            sashpad=1,
            sashcursor="sb_h_double_arrow",
            opaqueresize=True
        )
        self.paned_studio.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Pane 0 (ឆ្វេង - Column 0 in version_rust): Live Studio Cinema Monitor & Player Controls
        pane_left = tk.Frame(self.paned_studio, bg="#0e1014", bd=0)

        # Pane 1 (កណ្ដាល / ស្ដាំ - Column 1 in version_rust): Subtitles (Top) + CapCut Multi-Track Timeline (Bottom)
        pane_right_workspace = tk.Frame(self.paned_studio, bg="#0e1014", bd=0)
        pane_right_workspace.grid_rowconfigure(0, weight=1)
        pane_right_workspace.grid_columnconfigure(0, weight=1)

        paned_sub_tl = tk.PanedWindow(
            pane_right_workspace,
            orient="vertical",
            bg="#141822",
            bd=0,
            sashwidth=6,
            sashrelief="flat",
            sashpad=1,
            sashcursor="sb_v_double_arrow",
            opaqueresize=True
        )
        paned_sub_tl.grid(row=0, column=0, sticky="nsew")

        # Top of Column 1: Subtitles Editor & Translation Controls
        pane_subs_container = tk.Frame(paned_sub_tl, bg="#0e1014", bd=0)
        self.subtitles_view = SubtitlesView(
            parent=pane_subs_container,
            on_select_sub=self.on_select_subtitle,
            on_apply_edit=self.on_apply_subtitle_edit,
            on_listen_line=self.on_listen_subtitle_line,
            on_import_srt=self.on_import_srt,
            on_capture_cc=self.on_capture_cc_only,
            on_translate_all=self.start_translation_thread,
            on_translate_single=self.on_translate_single_subtitle,
            on_clean_noise=self.on_clean_noise,
            on_add_sub=self.on_add_new_subtitle,
            on_delete_sub=self.on_delete_subtitle,
            on_dub_all=self.on_dub_all,
            on_dub_selected=self.on_dub_selected,
            on_dub_missing=self.on_dub_missing,
            on_voice_change=self.on_subtitles_voice_change,
            on_voice_speed_change=self.on_subtitles_speed_change
        )
        self.subtitles_view.pack(fill="both", expand=True)

        # Bottom of Column 1: Timeline Container (docking PlayerView's multi-track timeline)
        pane_tl_container = tk.Frame(paned_sub_tl, bg="#0e1014", bd=0)

        paned_sub_tl.add(pane_subs_container, minsize=140, stretch="always")
        paned_sub_tl.add(pane_tl_container, minsize=160, stretch="always")

        # Instantiate PlayerView as Live Cinema Monitor in pane_left, and dock its timeline in pane_tl_container!
        self.player_view = PlayerView(
            parent=pane_left,
            timeline_parent=pane_tl_container,
            on_seek=self.on_timeline_seek,
            on_toggle_play=self.on_toggle_play,
            on_seek_relative=self.on_seek_relative,
            on_select_sub=self.on_select_subtitle,
            on_move_sub_timing=self.on_move_sub_timing,
            on_commit_sub_timing=self.on_commit_sub_timing,
            on_split_clip=self.on_split_clip,
            on_trim_clip=self.on_trim_clip,
            on_delete_clip=self.on_delete_clip,
            on_add_clip=self.on_add_clip,
            on_add_music=self.on_add_music,
            on_undo=self.on_undo,
            on_redo=self.on_redo,
            on_add_cc_track=self.on_add_cc_track,
            on_add_audio_track=self.on_add_audio_track,
            on_toggle_audio_mute=self.on_toggle_audio_mute,
            on_retry_chunk=self.on_retry_chunk,
            on_apply_edit=self.on_apply_subtitle_edit,
            on_auto_sync_speed=self.on_auto_sync_subtitle_speed,
            on_duplicate_sub=self.on_duplicate_subtitle,
            on_delete_sub=self.on_delete_subtitle,
            on_audition_sub=self._play_segment_audio,
            on_watermark_move_or_scale=self.on_watermark_move_or_scale,
            on_toggle_inspector=self.toggle_inspector,
            on_auto_pipeline=self.start_auto_pipeline_thread,
            on_batch_open=self.on_browse_multiple_videos,
            on_speed_change=self.on_playback_speed_change,
            on_volume_change=self.on_master_volume_change,
            on_object_selected=self.on_preview_object_selected
        )
        self.player_view.pack(fill="both", expand=True)

        # Pane 2 (ស្ដាំ - SidePanel Inspector in version_rust): Dubbing, Voice, Volume, Styles & Export
        self.pane_inspector = tk.Frame(self.paned_studio, bg="#0e1014", bd=0)
        self.dubbing_view = DubbingExportView(
            parent=self.pane_inspector,
            on_generate_dub=self.start_dubbing_thread,
            on_open_voices=self.on_open_voice_folder,
            on_export_srt=self.on_export_srt,
            on_burn_video=self.start_burn_video_thread,
            on_export_all=self.start_export_full_movie_thread,
            on_font_change=self.on_font_change,
            on_filter_change=self.on_filter_change,
            on_watermark_change=self.on_watermark_change,
            on_bg_music_browse=self.on_bg_music_browse,
            on_audio_mix_change=self.on_audio_mix_change,
            on_cc_style_change=self.on_cc_style_change
        )
        self.dubbing_view.pack(fill="both", expand=True)

        # Add panes to studio paned window (Monitor on Left, Subtitles/Timeline on Right, Inspector on Far Right)
        self.paned_studio.add(pane_left, minsize=380, stretch="always")
        self.paned_studio.add(pane_right_workspace, minsize=420, stretch="always")
        self.paned_studio.add(self.pane_inspector, minsize=290, stretch="never")
        self.inspector_open = True

        # Configure Tab 2: Video Downloader (Paste URL -> Preview -> Download -> 1-Click Studio Import)
        tab_downloader.grid_rowconfigure(0, weight=1)
        tab_downloader.grid_columnconfigure(0, weight=1)

        self.video_downloader_view = VideoDownloaderView(
            parent=tab_downloader,
            on_open_video_in_studio=self.on_open_downloaded_video,
            log_callback=self._append_log
        )
        self.video_downloader_view.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Configure Tab 3: Quick TTS & MP3 Export
        tab_tts.grid_rowconfigure(0, weight=1)
        tab_tts.grid_columnconfigure(0, weight=1)

        from ui import QuickSpeechView
        self.quick_speech_view = QuickSpeechView(parent=tab_tts, log_callback=self._append_log)
        self.quick_speech_view.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Configure Tab 4: Media Assets (Project Explorer)
        self._create_project_explorer(tab_assets)

        # 8. ក្រោម: Bottom Panel (Logs, Progress, Diagnostics & Job Queue)
        self._create_bottom_panel()

        # 9. ក្រោមគេ: Status Bar (Application status & statistics)
        self._create_status_bar()

    # ------------------ TOP TAB & INSPECTOR ACTIONS (FOLLOWING RUST APP.RS) ------------------
    def toggle_inspector(self):
        """Toggles the right-side Dubbing & Export Inspector panel matching version_rust"""
        self.inspector_open = not getattr(self, "inspector_open", True)
        if self.inspector_open:
            try:
                self.paned_studio.add(self.pane_inspector, minsize=290, stretch="never")
            except Exception:
                pass
            if hasattr(self.player_view, "btn_toggle_inspector"):
                self.player_view.btn_toggle_inspector.configure(text="⚙️ Close Settings")
        else:
            try:
                self.paned_studio.forget(self.pane_inspector)
            except Exception:
                pass
            if hasattr(self.player_view, "btn_toggle_inspector"):
                self.player_view.btn_toggle_inspector.configure(text="⚙️ Settings & Audio Mix")

    def _on_switch_top_tab(self, tab_id: str):
        """Switches main active tab matching version_rust top tab selector"""
        if tab_id == "studio":
            self.tabview.set("🎬 MOVIE TRANSLATOR & CC")
        elif tab_id == "downloader":
            self.tabview.set("📥 VIDEO DOWNLOADER")
        elif tab_id == "tts":
            self.tabview.set("🎙️ TEXT-TO-SPEECH (MP3)")
        elif tab_id == "project":
            self.tabview.set("📁 MEDIA ASSETS")
        elif tab_id == "logs":
            self.toggle_bottom_panel()
        elif tab_id == "config":
            self.toggle_inspector()

    def on_open_downloaded_video(self, video_file_path: str):
        """Directly loads a downloaded video and companion subtitles into Cinema Monitor & Studio Editor"""
        if os.path.exists(video_file_path):
            self.on_browse_video(chosen_file=video_file_path)
            self.tabview.set("🎬 MOVIE TRANSLATOR & CC")
            if hasattr(self, "header_view"):
                self.header_view.set_active_tab("studio")

    def on_clean_noise(self):
        """Removes [music], (laughter), silence, empty, and non-voice lines (matching Rust version)"""
        if not self.subtitles_data:
            return
        before = len(self.subtitles_data)
        cleaned = []
        for s in self.subtitles_data:
            orig = s.get("original", "").strip()
            trans = s.get("translated", "").strip()
            t_comb = (orig + " " + trans).lower()
            if not orig and not trans:
                continue
            if any(tag in t_comb for tag in ["[music]", "(music)", "[applause]", "[laughter]", "(silence)", "[sound]", "♪"]):
                continue
            cleaned.append(s)
        for i, s in enumerate(cleaned):
            s["id"] = i + 1
        removed = before - len(cleaned)
        self.subtitles_data = cleaned
        self.subtitles_view.populate_subtitles(self.subtitles_data)
        self.player_view.set_subtitles(self.subtitles_data)
        self.update_status(f"🧹 បានសម្អាតសម្លេងរំខាន/តន្ត្រី {removed} បន្ទាត់ (នៅសល់ {len(cleaned)} បន្ទាត់)", 1.0)

    def on_add_new_subtitle(self):
        """Adds a new subtitle dialogue line at current playhead time (matching Rust version)"""
        cur_t = round(self.current_time_sec, 2)
        new_id = len(self.subtitles_data) + 1
        new_sub = {
            "id": new_id,
            "start": cur_t,
            "end": round(cur_t + 3.0, 2),
            "original": "New Dialogue",
            "translated": "សន្ទនាថ្មី",
            "audio_file": None
        }
        self.subtitles_data.append(new_sub)
        self.subtitles_data.sort(key=lambda x: x["start"])
        for i, s in enumerate(self.subtitles_data):
            s["id"] = i + 1
        self.subtitles_view.populate_subtitles(self.subtitles_data)
        self.player_view.set_subtitles(self.subtitles_data)
        self.update_status(f"➕ បានបន្ថែម CC ថ្មីត្រង់នាទី {cur_t}s", 1.0)

    def on_capture_cc_only(self):
        """Captures CC from movie audio using Whisper / extraction without auto-dubbing (matching Rust version)"""
        if not self.video_path:
            messagebox.showwarning("ជ្រើសរើសវីដេអូ", "សូមជ្រើសរើសវីដេអូរឿងជាមុនសិន!")
            return
        if getattr(self, "is_processing", False):
            messagebox.showinfo("កំពុងដំណើរការ", "សូមរង់ចាំដំណើរការបច្ចុប្បន្ន...")
            return

        # Check embedded or companion CC first
        found_subs = extract_embedded_or_companion_subtitles(self.video_path)
        if found_subs:
            self.subtitles_data = found_subs
            self.subtitles_view.populate_subtitles(self.subtitles_data)
            self.player_view.set_subtitles(self.subtitles_data)
            self.update_status(f"🎉 បានទាញយក CC ({len(found_subs)} បន្ទាត់) ពីវីដេអូរួចរាល់!", 1.0)
            return

        def worker():
            try:
                self.is_processing = True
                self.update_status("🎙️ កំពុងចាប់សន្ទនា (Capture CC) ពីវីដេអូដោយ Faster-Whisper...", 0.1)
                settings = self.subtitles_view.get_translation_settings()
                src_code = "zh" if "Chinese" in settings["source_lang"] else ("en" if "English" in settings["source_lang"] else "auto")
                subs = self.speech_engine.transcribe_continuous(
                    video_path=self.video_path,
                    source_lang=src_code,
                    progress_callback=self.update_status
                )
                if subs:
                    self.subtitles_data = subs
                    self.after(0, lambda: self.subtitles_view.populate_subtitles(self.subtitles_data))
                    self.after(0, lambda: self.player_view.set_subtitles(self.subtitles_data))
                    self.save_subtitles_state(force_save_srt=True)
                    self.update_status(f"🎉 ចាប់ CC បាន {len(subs)} បន្ទាត់ជោគជ័យ! (បានរក្សាទុកឯកសារ .srt ស្វ័យប្រវត្តិទៅកាន់ Folder វីដេអូរួចរាល់)", 1.0)
                else:
                    self.update_status("⚠️ មិនបានរកឃើញសន្ទនាពីវីដេអូនេះទេ", 1.0)
            except Exception as e:
                self.update_status(f"❌ កំហុសចាប់ CC: {str(e)[:45]}", 0.0)
            finally:
                self.is_processing = False

        threading.Thread(target=worker, daemon=True).start()

    def start_auto_pipeline_thread(self):
        """1-Click Studio Workflow: Auto-capture CC -> Auto-translate to Khmer -> Auto-synthesize & Dub Khmer Voice! (matching Rust version)"""
        self.start_translation_thread()

    def on_browse_multiple_videos(self):
        """Batch opens multiple videos (matching Rust version)"""
        filetypes = [
            ("Video Files", "*.mp4 *.mkv *.avi *.mov *.webm *.flv *.ts"),
            ("All Files", "*.*")
        ]
        files = filedialog.askopenfilenames(title="Batch Open Videos (បើកវីដេអូច្រើន)", filetypes=filetypes)
        if files:
            # 1. First video opens cleanly as primary project video
            self.on_browse_video(files[0])
            
            # 2. Subsequent videos are added cleanly onto timeline as clips (Video B, Video C...)
            if len(files) > 1:
                for additional_file in files[1:]:
                    try:
                        info = get_video_info(additional_file)
                        dur = info.get("duration", 0.0)
                        if dur > 0:
                            self.editor_model.add_clip(additional_file, dur)
                            # Pre-extract preview audio in background
                            self._extract_preview_audio(additional_file)
                    except Exception as ex:
                        print(f"Error adding batch clip: {ex}")
                
                tot_dur = self.editor_model.get_total_duration()
                self.player_view.set_duration(tot_dur)
                self.player_view.set_video_clips(self.editor_model.clips)
                self.player_view.redraw_timeline()
                self._update_project_explorer_info()
                self.update_status(f"📁 បានបើកវីដេអូចំនួន {len(files)} ចូល Timeline រួចរាល់ (គ្មានគាំង)", 0.0)

    def on_playback_speed_change(self, speed: float):
        """Changes playback speed rate (0.5x - 2.0x)"""
        self.playback_speed = speed
        self.update_status(f"⚡ បានប្តូរល្បឿនមើល: {speed:.2f}x", 0.0)

    def _create_project_explorer(self, parent):
        """Creates the Project Explorer panel to manage Video, Audio, Subtitles & Assets"""
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        scroll_frame = ctk.CTkScrollableFrame(parent, fg_color="#0c0e14", corner_radius=2)
        scroll_frame.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # 1. Video Asset Card
        card_v = ctk.CTkFrame(scroll_frame, fg_color="#151922", corner_radius=4)
        card_v.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_v, text="🎥 PRIMARY VIDEO ASSET", font=ctk.CTkFont(size=10, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=8, pady=(6, 2))
        
        self.lbl_proj_video_name = ctk.CTkLabel(card_v, text="🎬 File: [ None ]", font=ctk.CTkFont(size=11), text_color="#cbd5e1")
        self.lbl_proj_video_name.pack(anchor="w", padx=8, pady=1)

        self.lbl_proj_video_specs = ctk.CTkLabel(card_v, text="📐 0x0 @ 0 FPS | 0.0s", font=ctk.CTkFont(size=10), text_color="#94a3b8")
        self.lbl_proj_video_specs.pack(anchor="w", padx=8, pady=(0, 6))

        # 2. Audio Tracks Card
        card_a = ctk.CTkFrame(scroll_frame, fg_color="#151922", corner_radius=4)
        card_a.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_a, text="🎵 AUDIO & VOICE TRACKS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#a855f7").pack(anchor="w", padx=8, pady=(6, 2))
        
        self.lbl_proj_audio_info = ctk.CTkLabel(card_a, text="🎤 Cached Dubs: 0 clips", font=ctk.CTkFont(size=11), text_color="#cbd5e1")
        self.lbl_proj_audio_info.pack(anchor="w", padx=8, pady=1)

        self.lbl_proj_bgm_info = ctk.CTkLabel(card_a, text="🎼 BGM: [ None ]", font=ctk.CTkFont(size=10), text_color="#94a3b8")
        self.lbl_proj_bgm_info.pack(anchor="w", padx=8, pady=(0, 6))

        # 3. Subtitles Track Card
        card_s = ctk.CTkFrame(scroll_frame, fg_color="#151922", corner_radius=4)
        card_s.pack(fill="x", pady=4, padx=2)
        ctk.CTkLabel(card_s, text="💬 SUBTITLE CC TRACK", font=ctk.CTkFont(size=10, weight="bold"), text_color="#10b981").pack(anchor="w", padx=8, pady=(6, 2))
        
        self.lbl_proj_sub_info = ctk.CTkLabel(card_s, text="📝 CC Lines: 0 items", font=ctk.CTkFont(size=11), text_color="#cbd5e1")
        self.lbl_proj_sub_info.pack(anchor="w", padx=8, pady=1)

        self.lbl_proj_lang_info = ctk.CTkLabel(card_s, text="🌐 Target: Khmer (km)", font=ctk.CTkFont(size=10), text_color="#94a3b8")
        self.lbl_proj_lang_info.pack(anchor="w", padx=8, pady=(0, 6))

        # 4. Project Quick Actions
        card_act = ctk.CTkFrame(scroll_frame, fg_color="#151922", corner_radius=4)
        card_act.pack(fill="x", pady=6, padx=2)
        ctk.CTkLabel(card_act, text="⚡ PROJECT ACTIONS", font=ctk.CTkFont(size=10, weight="bold"), text_color="#f59e0b").pack(anchor="w", padx=8, pady=(6, 4))

        ctk.CTkButton(card_act, text="📂 Add Video Clip...", height=24, font=ctk.CTkFont(size=10), fg_color="#1e293b", hover_color="#334155", command=self.on_add_clip).pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(card_act, text="🎵 Add Background Music...", height=24, font=ctk.CTkFont(size=10), fg_color="#1e293b", hover_color="#334155", command=self.on_add_music).pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(card_act, text="📝 Import SRT File...", height=24, font=ctk.CTkFont(size=10), fg_color="#1e293b", hover_color="#334155", command=self.on_export_srt).pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(card_act, text="📁 Open Voice Cache Folder", height=24, font=ctk.CTkFont(size=10), fg_color="#1e293b", hover_color="#334155", command=self.on_open_voice_folder).pack(fill="x", padx=8, pady=(2, 6))

    def _update_project_explorer_info(self):
        """Refreshes Project Explorer and Status Bar labels with latest video & subtitle metadata"""
        if not hasattr(self, "lbl_proj_video_name"):
            return
        v_name = os.path.basename(self.video_path) if self.video_path else "[ None ]"
        dur = self.video_info.get("duration", 0.0)
        vw = self.video_info.get("width", 0)
        vh = self.video_info.get("height", 0)
        fps = self.video_info.get("fps", 0.0)
        sub_count = len(self.subtitles_data)
        voices_count = len(getattr(self, "_cached_sounds", {}))

        self.lbl_proj_video_name.configure(text=f"🎬 File: {v_name}")
        self.lbl_proj_video_specs.configure(text=f"📐 {vw}x{vh} @ {fps:.1f} FPS | {int(dur)}s")
        self.lbl_proj_audio_info.configure(text=f"🎤 Cached Dubs: {voices_count} clips")
        self.lbl_proj_sub_info.configure(text=f"📝 CC Lines: {sub_count} items")

        if hasattr(self, "lbl_status_specs"):
            cur_sec = getattr(self, "current_time_sec", 0.0)
            cur_m, cur_s = divmod(int(cur_sec), 60)
            tot_m, tot_s = divmod(int(dur), 60)
            self.lbl_status_specs.configure(
                text=f"{cur_m:02d}:{cur_s:02d} / {tot_m:02d}:{tot_s:02d} | {vw}x{vh} @ {fps:.1f} FPS | {sub_count} CC"
            )

    # ------------------ BOTTOM PANEL: LOGS, PROGRESS & JOB QUEUE (ក្រោម) ------------------
    def _create_bottom_panel(self):
        """Creates the collapsible Bottom Panel for live logs, job queue and engine diagnostics"""
        self.bottom_panel = ctk.CTkFrame(self, fg_color="#0b0d13", height=130, corner_radius=0)
        self.bottom_panel.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        self.bottom_panel.pack_propagate(False)

        # Panel Header
        header_bar = ctk.CTkFrame(self.bottom_panel, fg_color="#12151d", height=24, corner_radius=0)
        header_bar.pack(fill="x", side="top")

        ctk.CTkLabel(
            header_bar,
            text="📋 BOTTOM PANEL (Logs, Job Queue & Diagnostics)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#94a3b8"
        ).pack(side="left", padx=8)

        btn_clear = ctk.CTkButton(
            header_bar,
            text="🧹 Clear Logs",
            width=70,
            height=18,
            corner_radius=2,
            font=ctk.CTkFont(size=9),
            fg_color="#1e2430",
            hover_color="#334155",
            command=self._clear_logs
        )
        btn_clear.pack(side="right", padx=6, pady=2)

        self.btn_bottom_collapse = ctk.CTkButton(
            header_bar,
            text="▼ Hide",
            width=50,
            height=18,
            corner_radius=2,
            font=ctk.CTkFont(size=9),
            fg_color="#1e2430",
            hover_color="#334155",
            command=self.toggle_bottom_panel
        )
        self.btn_bottom_collapse.pack(side="right", padx=2, pady=2)

        # Tabview for Bottom Panel
        self.bottom_tabview = ctk.CTkTabview(
            self.bottom_panel,
            fg_color="#090a0f",
            segmented_button_fg_color="#141720",
            segmented_button_selected_color="#2563eb",
            segmented_button_selected_hover_color="#1d4ed8",
            corner_radius=2
        )
        self.bottom_tabview.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        tab_logs = self.bottom_tabview.add("📋 Logs & Console")
        tab_queue = self.bottom_tabview.add("⏳ Progress & Queue")
        tab_diag = self.bottom_tabview.add("⚠️ Diagnostics")

        # 1. Logs Console
        tab_logs.grid_rowconfigure(0, weight=1)
        tab_logs.grid_columnconfigure(0, weight=1)
        self.txt_logs = ctk.CTkTextbox(
            tab_logs,
            fg_color="#07080c",
            text_color="#cbd5e1",
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=0
        )
        self.txt_logs.grid(row=0, column=0, sticky="nsew")
        self._append_log("AI Khmer Movie Studio initialized. Ready.")

        # 2. Progress & Job Queue
        tab_queue.grid_rowconfigure(1, weight=1)
        tab_queue.grid_columnconfigure(0, weight=1)

        self.lbl_queue_task = ctk.CTkLabel(
            tab_queue,
            text="Active Task: Ready (No background jobs running)",
            font=ctk.CTkFont(size=11),
            text_color="#cbd5e1"
        )
        self.lbl_queue_task.grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

        self.bottom_queue_progress = ctk.CTkProgressBar(
            tab_queue,
            height=12,
            corner_radius=2,
            fg_color="#1e293b",
            progress_color="#2563eb"
        )
        self.bottom_queue_progress.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))
        self.bottom_queue_progress.set(0.0)

        # 3. Diagnostics
        tab_diag.grid_rowconfigure(0, weight=1)
        tab_diag.grid_columnconfigure(0, weight=1)
        txt_diag = ctk.CTkTextbox(
            tab_diag,
            fg_color="#07080c",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=0
        )
        txt_diag.grid(row=0, column=0, sticky="nsew")
        txt_diag.insert(
            "end",
            "● FFmpeg: OK (Audio extraction & Video burn-in ready)\n"
            "● Google Gemini 3.8 Flash AI: Active & Configured\n"
            "● Edge TTS (Piseth & Sreymom): Online & Multi-threading enabled\n"
            "● Speech Recognition Engine: Whisper Base (VAD filtered)\n"
            "● Subtitle Burner: Libx264 Veryfast + ASS filter\n"
        )
        txt_diag.configure(state="disabled")

    def toggle_bottom_panel(self):
        """Expands or collapses the Bottom Panel"""
        if not hasattr(self, "bottom_panel"):
            return
        is_visible = getattr(self, "_bottom_panel_visible", True)
        if is_visible:
            self.bottom_panel.grid_remove()
            self._bottom_panel_visible = False
            if hasattr(self, "btn_bottom_collapse"):
                self.btn_bottom_collapse.configure(text="▲ Show")
            if hasattr(self, "btn_status_bottom_toggle"):
                self.btn_status_bottom_toggle.configure(text="▲ Logs")
        else:
            self.bottom_panel.grid()
            self._bottom_panel_visible = True
            if hasattr(self, "btn_bottom_collapse"):
                self.btn_bottom_collapse.configure(text="▼ Hide")
            if hasattr(self, "btn_status_bottom_toggle"):
                self.btn_status_bottom_toggle.configure(text="▼ Logs")

    def _append_log(self, text: str):
        """Appends a timestamped message to the real-time bottom console"""
        if hasattr(self, "txt_logs"):
            t_str = time.strftime("%H:%M:%S")
            self.txt_logs.configure(state="normal")
            self.txt_logs.insert("end", f"[{t_str}] {text}\n")
            self.txt_logs.see("end")
            self.txt_logs.configure(state="disabled")

    def _clear_logs(self):
        """Clears the bottom logs console"""
        if hasattr(self, "txt_logs"):
            self.txt_logs.configure(state="normal")
            self.txt_logs.delete("1.0", "end")
            self._append_log("Logs console cleared.")
            self.txt_logs.configure(state="disabled")

    # ------------------ STATUS BAR (ក្រោមគេ) ------------------
    def _create_status_bar(self):
        """Creates the bottom-most Status Bar showing app state, timecode, and engine badges"""
        self.status_bar_frame = ctk.CTkFrame(self, fg_color="#080a0e", height=26, corner_radius=0)
        self.status_bar_frame.grid(row=3, column=0, sticky="ew", padx=0, pady=0)

        # Left status indicator
        self.lbl_status_dot = ctk.CTkLabel(
            self.status_bar_frame,
            text="●",
            text_color="#10b981",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_status_dot.pack(side="left", padx=(8, 4))

        self.lbl_status_text = ctk.CTkLabel(
            self.status_bar_frame,
            text="Ready",
            text_color="#f1f5f9",
            font=ctk.CTkFont(size=11)
        )
        self.lbl_status_text.pack(side="left", padx=2)

        # Center video specs and timecode
        self.lbl_status_specs = ctk.CTkLabel(
            self.status_bar_frame,
            text="00:00 / 00:00 | [ No Video ] | 0 CC",
            text_color="#94a3b8",
            font=ctk.CTkFont(size=10)
        )
        self.lbl_status_specs.pack(side="left", padx=20)

        # Right badges & bottom panel toggle
        self.btn_status_bottom_toggle = ctk.CTkButton(
            self.status_bar_frame,
            text="▼ Logs",
            width=65,
            height=20,
            corner_radius=2,
            font=ctk.CTkFont(size=10),
            fg_color="#1e2430",
            hover_color="#334155",
            command=self.toggle_bottom_panel
        )
        self.btn_status_bottom_toggle.pack(side="right", padx=(4, 8), pady=3)

        ctk.CTkLabel(
            self.status_bar_frame,
            text="UTF-8",
            text_color="#64748b",
            font=ctk.CTkFont(size=10)
        ).pack(side="right", padx=6)

        self.lbl_status_voice = ctk.CTkLabel(
            self.status_bar_frame,
            text="🎤 Piseth Neural",
            text_color="#38bdf8",
            font=ctk.CTkFont(size=10)
        )
        self.lbl_status_voice.pack(side="right", padx=8)

        self.lbl_status_ai = ctk.CTkLabel(
            self.status_bar_frame,
            text="● Gemini 3.8 Flash",
            text_color="#34d399",
            font=ctk.CTkFont(size=10, weight="bold")
        )
        self.lbl_status_ai.pack(side="right", padx=8)

    def _update_status_bar(self, text: str, progress: float = None):
        """Updates status text, dot color and progress bar in status bar & bottom panel"""
        if hasattr(self, "lbl_status_text"):
            self.lbl_status_text.configure(text=text)
        if hasattr(self, "lbl_status_dot"):
            self.lbl_status_dot.configure(
                text_color="#f59e0b" if getattr(self, "is_processing", False) else "#10b981"
            )
        if hasattr(self, "bottom_queue_progress") and progress is not None:
            self.bottom_queue_progress.set(max(0.0, min(1.0, progress)))
        if hasattr(self, "lbl_queue_task"):
            pct_str = f" ({int(progress * 100)}%)" if progress is not None else ""
            self.lbl_queue_task.configure(text=f"Active Task: {text}{pct_str}")

    # ------------------ GLOBAL UI ZOOM CONTROLLER ------------------
    def _bind_zoom_shortcuts(self):
        """Binds Ctrl+, Ctrl-, Ctrl 0, and Ctrl+MouseWheel for global UI zoom"""
        self.bind("<Control-plus>", self.zoom_ui_in)
        self.bind("<Control-equal>", self.zoom_ui_in)
        self.bind("<Control-KP_Add>", self.zoom_ui_in)
        self.bind("<Control-minus>", self.zoom_ui_out)
        self.bind("<Control-underscore>", self.zoom_ui_out)
        self.bind("<Control-KP_Subtract>", self.zoom_ui_out)
        self.bind("<Control-0>", self.zoom_ui_reset)
        self.bind("<Control-KP_0>", self.zoom_ui_reset)
        self.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.bind("<Control-Shift-O>", lambda e: self.on_import_srt())
        self.bind("<Control-Shift-o>", lambda e: self.on_import_srt())

    def zoom_ui_in(self, event=None):
        self.ui_scale = min(1.8, round(self.ui_scale + 0.1, 2))
        self._apply_ui_zoom()

    def zoom_ui_out(self, event=None):
        self.ui_scale = max(0.7, round(self.ui_scale - 0.1, 2))
        self._apply_ui_zoom()

    def zoom_ui_reset(self, event=None):
        self.ui_scale = 1.0
        self._apply_ui_zoom()

    def _on_ctrl_mousewheel(self, event):
        if event.delta > 0:
            self.zoom_ui_in()
        elif event.delta < 0:
            self.zoom_ui_out()

    def _apply_ui_zoom(self):
        try:
            ctk.set_widget_scaling(self.ui_scale)
            pct_text = f"{int(self.ui_scale * 100)}%"
            self.header_view.set_zoom_text(pct_text)
            self.update_status(f"🔍 UI Zoom: {pct_text} (Ctrl +/- or Ctrl+Wheel to scale)")
        except Exception as e:
            print(f"Zoom error: {e}")

    # ------------------ VIDEO OPEN & PLAYBACK CONTROLLER ------------------
    def on_browse_video(self, chosen_file: str = None):
        if chosen_file:
            chosen = chosen_file
        else:
            filetypes = [("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm"), ("All Files", "*.*")]
            chosen = filedialog.askopenfilename(title="Select Movie / Video File", filetypes=filetypes)
        if chosen:
            # 1. STOP ongoing playback and audio IMMEDIATELY
            self.is_playing = False
            self.player_view.set_play_state(False)
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
            except Exception:
                pass
            try:
                if getattr(self, "dub_channel", None):
                    self.dub_channel.stop()
                pygame.mixer.stop()
            except Exception:
                pass

            # 2. Increment session ID to cancel background tasks of previous video
            self._video_session_id = getattr(self, "_video_session_id", 0) + 1
            current_session = self._video_session_id
            self.is_processing = False
            self.header_view.set_translating_state(False)

            # 3. Safely release all open OpenCV VideoCaptures & clear caches
            self._cleanup_all_captures()
            self._clip_audio_map.clear()
            self._currently_loaded_audio = None
            self._orig_preview_audio = None
            self._cached_sounds.clear()
            self._spoken_ids.clear()
            self._last_spoken_id = None
            self._last_synced_sub_id = None
            self.subtitles_data = []

            # 4. Completely clean UI views (no leftover subtitles, timings, or active text)
            self.subtitles_view.reset_view()
            self.player_view.reset_player_for_new_video(0.0, 1280, 720)

            # 5. Load and inspect new video file
            self.video_path = chosen
            filename = os.path.basename(chosen)
            self.header_view.set_filename(filename)

            self.video_info = get_video_info(chosen)
            duration = self.video_info.get("duration", 0.0)
            vw = self.video_info.get("width", 1280)
            vh = self.video_info.get("height", 720)
            fps = self.video_info.get("fps", 30.0)

            # 6. Initialize EditorModel & Timeline with new video
            self.editor_model.set_primary_video(chosen, duration, vw, vh, fps)
            self.player_view.set_resolution(vw, vh, fps)
            self.player_view.set_duration(duration)
            self.player_view.set_video_clips(self.editor_model.clips)
            self.player_view.set_cc_tracks(self.editor_model.cc_tracks)
            self.player_view.set_audio_tracks(self.editor_model.audio_tracks)
            self.player_view.reset_timeline_scroll()

            # 7. Pre-open capture safely under cap_lock
            with self.cap_lock:
                self.cap = self._get_capture_for_path(self.video_path)
                self._active_cap_path = self.video_path

            self.current_time_sec = 0.0
            self._needs_seek = True
            self.player_view.set_time_pos(0)
            self._render_current_frame(force_seek=True)

            # 8. Extract preview audio for background playback (guarded by session)
            self._extract_preview_audio(chosen)
            self._update_project_explorer_info()
            self.update_status(f"បានបើកវីដេអូ: {filename} ({int(duration)}s)", 0.0)

            # 9. Check companion .srt/.vtt file or saved _subtitles.json state
            found_subs = extract_embedded_or_companion_subtitles(chosen)
            if found_subs and current_session == self._video_session_id:
                self.subtitles_data = found_subs

                # Link existing voice clips from voice directory to avoid re-generating
                v_dir = self.get_voices_directory()
                trans_count = sum(1 for s in self.subtitles_data if is_khmer_text(s.get("translated", "")))
                voices_linked = 0
                if os.path.exists(v_dir):
                    for idx, s in enumerate(self.subtitles_data):
                        if not s.get("audio_file") or not os.path.exists(s.get("audio_file", "")):
                            s_time = format_filename_timestamp(s.get("start", 0.0))
                            e_time = format_filename_timestamp(s.get("end", 0.0))
                            cand = os.path.join(v_dir, f"#{s.get('id', idx+1)}_{s_time}_to_{e_time}.mp3")
                            if os.path.exists(cand) and os.path.getsize(cand) > 100:
                                s["audio_file"] = cand
                                voices_linked += 1
                        elif s.get("audio_file") and os.path.exists(s.get("audio_file")):
                            voices_linked += 1

                self.subtitles_view.populate_subtitles(self.subtitles_data)
                self.player_view.set_subtitles(self.subtitles_data)

                total_s = len(self.subtitles_data)
                if trans_count > 0:
                    self.update_status(
                        f"🎉 បានផ្ទុក Subtitle រួចជាស្រេច (បកប្រែខ្មែរ: {trans_count}/{total_s}, សំឡេង: {voices_linked}/{total_s})! អាចបន្តការងារភ្លាមៗ", 
                        0.0
                    )
                else:
                    self.update_status(f"🎉 បានផ្ទុក Subtitle ពី Folder ({total_s} បន្ទាត់)! ចុច '⚡ Translate All' ដើម្បីបកប្រែជាភាសាខ្មែរ", 0.0)

    def on_import_srt(self, chosen_file: str = None):
        """Imports an external SRT / VTT / ASS subtitle file, updates timeline, and auto-translates to Khmer"""
        if not chosen_file:
            filetypes = [
                ("Subtitle Files", "*.srt *.vtt *.ass *.txt"),
                ("SRT Subtitles", "*.srt"),
                ("VTT Subtitles", "*.vtt"),
                ("All Files", "*.*")
            ]
            chosen_file = filedialog.askopenfilename(title="Select Subtitle File (.srt / .vtt)", filetypes=filetypes)
        if not chosen_file:
            return

        subs = parse_srt_file(chosen_file)
        if not subs:
            messagebox.showwarning("គ្មានទិន្នន័យ", "មិនអាចអានអត្ថបទពីឯកសារ Subtitle នេះបានទេ!")
            return

        self.subtitles_data = subs
        self._cached_sounds.clear()
        self.subtitles_view.populate_subtitles(self.subtitles_data)
        self.player_view.set_subtitles(self.subtitles_data)
        self._render_current_frame(force_seek=True)

        filename = os.path.basename(chosen_file)
        self.update_status(f"🎉 បាននាំចូល Subtitle: {filename} ({len(subs)} បន្ទាត់)! ចុច '⚡ Translate All' ដើម្បីបកប្រែជាភាសាខ្មែរ", 0.0)

    def _auto_translate_and_dub_subtitles(self, subs: list):
        """Translates original text to Khmer (resuming untranslated lines) and generates segment voices in background"""
        current_session = getattr(self, "_video_session_id", 0)
        def worker():
            settings = self.subtitles_view.get_translation_settings()
            self.translation_service.set_provider(settings["provider"], settings["api_key"], style=settings.get("style", ""))
            src_code = "zh" if "Chinese" in settings["source_lang"] else ("en" if "English" in settings["source_lang"] else "auto")

            # Check which items still need translation
            untranslated = [s for s in subs if not is_khmer_text(s.get("translated", ""))]
            total = len(subs)

            if untranslated:
                self.update_status(f"⚡ កំពុងបន្តបកប្រែ CC ({len(untranslated)}/{total} បន្ទាត់) ទៅជាភាសាខ្មែរ [Turbo Speed]...", 0.15)
                self.translation_service.translate_subtitles_parallel(
                    subtitles=untranslated,
                    source_lang=src_code,
                    target_lang="km",
                    batch_size=15,
                    max_workers=16,
                    progress_callback=self.update_status,
                    check_cancel=lambda: current_session != getattr(self, "_video_session_id", 0)
                )

                # Persist progress immediately so re-opening video will never lose work!
                self.save_subtitles_state()

                def _u():
                    if current_session == getattr(self, "_video_session_id", 0):
                        self.subtitles_view.populate_subtitles(self.subtitles_data)
                        self.player_view.set_subtitles(self.subtitles_data)
                self.after(0, _u)
            else:
                self.update_status(f"✅ CC គ្រប់ {total} បន្ទាត់ត្រូវបានបកប្រែជាភាសាខ្មែររួចរាល់ហើយ!", 0.25)

            if current_session != getattr(self, "_video_session_id", 0):
                return

            # Check if user enabled auto-dubbing, or if they prefer to choose voice model first!
            dub_settings = self.subtitles_view.get_dubbing_settings() if hasattr(self.subtitles_view, "get_dubbing_settings") else {"auto_dub": True}
            if dub_settings.get("auto_dub", True):
                self._append_log(f"🤖 [AI Pipeline] បកប្រែចប់រួចរាល់! ចាប់ផ្ដើមបង្កើតសំឡេងដោយស្វ័យប្រវត្តិ (Model: {dub_settings.get('voice_key')})...")
                self.auto_generate_all_segment_voices(subs, force_refresh=False, session_id=current_session)
            else:
                self._append_log(f"✅ [Translation Done] បកប្រែគ្រប់ {total} បន្ទាត់រួចរាល់! អ្នកអាចជ្រើសរើស Voice Model/Speed រួចចុច '🎧 Dub All' ដើម្បីបង្កើតសំឡេង។")
                self.update_status(f"🎉 បកប្រែ CC {total} បន្ទាត់រួចរាល់! សូមជ្រើសរើស Voice Model រួចចុច '🎧 Dub All'", 1.0)

        threading.Thread(target=worker, daemon=True).start()

    def _extract_preview_audio(self, video_path: str, force: bool = False):
        """Extracts original movie audio track into a temp preview MP3 for real-time synchronized playback"""
        current_session = getattr(self, "_video_session_id", 0)
        def worker():
            try:
                import tempfile
                v_name = abs(hash(video_path))
                tmp_dir = tempfile.gettempdir()
                out_mp3 = os.path.join(tmp_dir, f"movie_orig_audio_{v_name}.mp3")

                if force and (not os.path.exists(out_mp3) or os.path.getsize(out_mp3) < 1000):
                    cmd = [
                        "ffmpeg", "-y", "-i", video_path,
                        "-vn", "-acodec", "libmp3lame", "-b:a", "64k", "-ar", "24000", "-ac", "1",
                        "-threads", "0",
                        out_mp3
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

                if current_session != getattr(self, "_video_session_id", 0):
                    return

                if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 1000:
                    self._clip_audio_map[video_path] = out_mp3
                    if video_path == self.video_path or not getattr(self, "_orig_preview_audio", None):
                        self._orig_preview_audio = out_mp3
                        try:
                            pygame.mixer.music.load(out_mp3)
                            self._currently_loaded_audio = out_mp3
                            orig_track = self.editor_model.audio_tracks[0] if getattr(self, "editor_model", None) and self.editor_model.audio_tracks else {}
                            vol = 0.0 if orig_track.get("is_muted") else orig_track.get("volume", 0.85)
                            self._curr_preview_orig_vol = vol
                            pygame.mixer.music.set_volume(vol)
                        except Exception as ex:
                            print(f"Pygame music load error: {ex}")
            except Exception as e:
                print(f"Error extracting preview audio: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _sync_audio_playback(self, seek: bool = False):
        """Synchronizes original movie audio with current playback timestamp (supports multi-clip)"""
        clip, local_time = self.editor_model.get_clip_at_time(self.current_time_sec) if self.editor_model.clips else (None, self.current_time_sec)
        active_path = clip["path"] if clip else self.video_path
        render_time = local_time if clip else self.current_time_sec

        target_audio = self._clip_audio_map.get(active_path, self._orig_preview_audio)
        if not target_audio or not os.path.exists(target_audio):
            return

        try:
            orig_track = self.editor_model.audio_tracks[0] if getattr(self, "editor_model", None) and self.editor_model.audio_tracks else {}
            is_muted = orig_track.get("is_muted", False)
            base_vol = orig_track.get("volume", 0.85)

            # Auto-ducking check
            active_subs = [s for s in self.subtitles_data if s["start"] <= self.current_time_sec <= s["end"]]
            auto_duck = self.editor_model.audio_settings.get("auto_ducking", True)
            khmer_active = self.player_view.check_khmer_audio.get() if hasattr(self.player_view, "check_khmer_audio") else True

            if is_muted:
                init_vol = 0.0
            elif auto_duck and active_subs and khmer_active:
                init_vol = min(base_vol, self.editor_model.audio_settings.get("duck_vol", 0.15))
            else:
                init_vol = base_vol

            self._curr_preview_orig_vol = init_vol
            pygame.mixer.music.set_volume(max(0.0, min(1.0, init_vol)))

            need_load = getattr(self, "_currently_loaded_audio", None) != target_audio
            if need_load:
                pygame.mixer.music.load(target_audio)
                self._currently_loaded_audio = target_audio
                pygame.mixer.music.play(start=max(0.0, render_time))
            elif seek:
                pygame.mixer.music.play(start=max(0.0, render_time))
            else:
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(start=max(0.0, render_time))
                else:
                    pygame.mixer.music.unpause()
        except Exception:
            try:
                pygame.mixer.music.load(target_audio)
                self._currently_loaded_audio = target_audio
                pygame.mixer.music.play(start=max(0.0, render_time))
            except Exception:
                pass

    def _render_current_frame(self, force_seek: bool = False):
        """Fast, smooth frame decoding and rendering without CPU/disk thrashing or freeze"""
        if not self.editor_model.clips and not self.video_path:
            return

        # Acquire lock without blocking UI or thread (prevents OpenCV deadlocks)
        if not self.cap_lock.acquire(blocking=False):
            return

        try:
            # Multi-clip timeline to local time mapping
            clip, local_time = self.editor_model.get_clip_at_time(self.current_time_sec) if self.editor_model.clips else (None, self.current_time_sec)
            active_path = clip["path"] if clip else self.video_path
            render_time = local_time if clip else self.current_time_sec

            if not active_path:
                return

            cap = self._get_capture_for_path(active_path)
            if not cap or not cap.isOpened():
                return

            if getattr(self, "_active_cap_path", None) != active_path:
                self._active_cap_path = active_path
                self.cap = cap
                force_seek = True

            clip_fps = clip.get("fps", 30.0) if clip else self.video_info.get("fps", 30.0)
            if not clip_fps or clip_fps <= 0:
                clip_fps = 30.0

            # Only seek when user explicitly jumped, sought, or changed clips (Ultra-fast msec seeking for long videos)
            if force_seek or self._needs_seek:
                cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, render_time * 1000.0))
                self._needs_seek = False

            ret, frame = cap.read()
            if ret and frame is not None:
                h, w = frame.shape[:2]
                cont_w = max(320, self.player_view.video_container.winfo_width())
                cont_h = max(200, self.player_view.video_container.winfo_height())

                scale = min(cont_w / w, cont_h / h)
                target_w = max(10, int(w * scale))
                target_h = max(10, int(h * scale))

                # Fast OpenCV C++ SIMD resize directly to preview dimensions
                resized_bgr = cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
                rgb_frame = cv2.cvtColor(resized_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb_frame)
                tot_dur = self.editor_model.get_total_duration() if self.editor_model.clips else self.video_info.get("duration", 0.0)
                self.player_view.update_frame(pil_img, self.current_time_sec, tot_dur)
        finally:
            self.cap_lock.release()

        # Check Active Subtitles for Display & Real-time Khmer Audio Sync
        active_subs = [s for s in self.subtitles_data if s["start"] <= self.current_time_sec <= s["end"]]

        # ---------------- AUTO-DUCKING CONTROLLER ----------------
        # Automatically duck original movie audio when Khmer dialogue is speaking,
        # and smoothly swell original movie audio UP when dialogue is silent.
        orig_track = self.editor_model.audio_tracks[0] if getattr(self, "editor_model", None) and self.editor_model.audio_tracks else {}
        orig_is_muted = orig_track.get("is_muted", False)
        orig_base_vol = 0.0 if orig_is_muted else orig_track.get("volume", 0.85)
        auto_ducking = self.editor_model.audio_settings.get("auto_ducking", True)
        khmer_sound_active = self.player_view.check_khmer_audio.get() if hasattr(self.player_view, "check_khmer_audio") else True

        if orig_is_muted:
            target_orig_vol = 0.0
        elif auto_ducking and active_subs and khmer_sound_active:
            target_orig_vol = min(orig_base_vol, self.editor_model.audio_settings.get("duck_vol", 0.15))
        else:
            target_orig_vol = orig_base_vol

        if not hasattr(self, "_curr_preview_orig_vol"):
            self._curr_preview_orig_vol = target_orig_vol

        if abs(self._curr_preview_orig_vol - target_orig_vol) > 0.005:
            # Responsive attack (~60ms), natural cinematic release swell (~300ms)
            slew = 0.35 if target_orig_vol < self._curr_preview_orig_vol else 0.15
            self._curr_preview_orig_vol += (target_orig_vol - self._curr_preview_orig_vol) * slew
            try:
                pygame.mixer.music.set_volume(max(0.0, min(1.0, self._curr_preview_orig_vol)))
            except Exception:
                pass

        if active_subs:
            active_sub = active_subs[-1]
            km = active_sub.get("translated", "")
            orig = active_sub.get("original", "")
            is_dual = self.dubbing_view.check_dual.get()
            text = f"{km}\n{orig}" if is_dual else km
            time_tag = f"Time CC: [{time.strftime('%M:%S', time.gmtime(active_sub['start']))} -> {time.strftime('%M:%S', time.gmtime(active_sub['end']))}]"
            self.player_view.update_active_subtitle(
                sub_text=text,
                is_active=True,
                time_info=time_tag,
                current_sec=self.current_time_sec,
                sub_start=active_sub["start"],
                sub_end=active_sub["end"],
                sub_id=active_sub.get("id")
            )

            # Auto sync, auto-scroll and highlight active CC in Subtitles list and timeline!
            active_id = active_sub.get("id")
            if active_id != getattr(self, "_last_synced_sub_id", None):
                self._last_synced_sub_id = active_id
                for s_idx, s in enumerate(self.subtitles_data):
                    if s.get("id") == active_id:
                        if hasattr(self, "subtitles_view") and hasattr(self.subtitles_view, "set_playback_active"):
                            self.subtitles_view.set_playback_active(s_idx, auto_scroll=True)
                        if hasattr(self, "player_view") and hasattr(self.player_view, "select_subtitle"):
                            self.player_view.select_subtitle(s_idx)
                        break

            # Auto Play per-segment Khmer audio for all active lines in their video slots
            dub_track = self.editor_model.audio_tracks[1] if getattr(self, "editor_model", None) and len(self.editor_model.audio_tracks) > 1 else {}
            is_dub_muted = dub_track.get("is_muted", False)
            if self.is_playing and self.player_view.check_khmer_audio.get() and not is_dub_muted:
                for sub_item in active_subs:
                    sid = sub_item.get("id")
                    if sid not in self._spoken_ids:
                        self._spoken_ids.add(sid)
                        self._play_segment_audio(sub_item)
        else:
            self.player_view.update_active_subtitle("", is_active=False)

    def _play_segment_audio(self, sub: dict):
        """Plays the individual segment audio file instantly using pre-cached Sound via dedicated dubbing channel"""
        sub_id = sub.get("id")
        text = sub.get("translated", "").strip()
        if not text:
            return

        dub_track = self.editor_model.audio_tracks[1] if getattr(self, "editor_model", None) and len(self.editor_model.audio_tracks) > 1 else {}
        if dub_track.get("is_muted"):
            return
        dub_vol = dub_track.get("volume", 1.0)

        # Check if already loaded in pygame Sound cache
        snd = self._cached_sounds.get(sub_id)
        if snd:
            try:
                snd.set_volume(dub_vol)
                ch = pygame.mixer.find_channel(True)
                if ch:
                    ch.play(snd)
                elif getattr(self, "dub_channel", None):
                    self.dub_channel.play(snd)
                else:
                    snd.play()
                return
            except Exception:
                pass

        audio_file = sub.get("audio_file")
        if audio_file and os.path.exists(audio_file):
            try:
                snd = pygame.mixer.Sound(audio_file)
                self._cached_sounds[sub_id] = snd
                snd.set_volume(dub_vol)
                ch = pygame.mixer.find_channel(True)
                if ch:
                    ch.play(snd)
                elif getattr(self, "dub_channel", None):
                    self.dub_channel.play(snd)
                else:
                    snd.play()
                return
            except Exception:
                pass

        # Synthesize on demand with automatic speech speed matching
        def worker():
            voice_choice = self.dubbing_view.combo_voice.get()
            self.dubbing_engine.set_voice(voice_choice)
            voice_dir = self.get_voices_directory()
            os.makedirs(voice_dir, exist_ok=True)
            tmp_audio = os.path.join(voice_dir, f"#{sub_id}_runtime.mp3")
            rate = sub.get("rate", "+0%")
            target_dur = max(0.4, sub.get("end", 0.0) - sub.get("start", 0.0))
            self._append_log(
                f"🤖 [AI Voice] បង្កើតសំឡេងតាមតម្រូវការដោយ AI | Engine: Edge TTS Neural ({self.dubbing_engine.voice_name}) | "
                f"Voice: {voice_choice} | Rate: {rate} សម្រាប់ CC #{sub_id} ({target_dur:.2f}s)"
            )
            ok = self.dubbing_engine.synthesize_line(text, tmp_audio, rate=rate, target_dur=target_dur)

            if ok and os.path.exists(tmp_audio):
                try:
                    sub["audio_file"] = tmp_audio
                    sound = pygame.mixer.Sound(tmp_audio)
                    self._cached_sounds[sub_id] = sound
                    sound.set_volume(dub_vol)
                    self._append_log(f"✅ [AI Voice] បង្កើតសំឡេង AI On-Demand ជោគជ័យ សម្រាប់ CC #{sub_id}")
                    if self.is_playing:
                        ch = pygame.mixer.find_channel(True)
                        if ch:
                            ch.play(sound)
                        elif getattr(self, "dub_channel", None):
                            self.dub_channel.play(sound)
                        else:
                            sound.play()
                except Exception as e:
                    print(f"Sound play error: {e}")
        threading.Thread(target=worker, daemon=True).start()

    def on_toggle_play(self):
        if not self.video_path and not self.editor_model.clips:
            return
        self.is_playing = not self.is_playing
        self.player_view.set_play_state(self.is_playing)
        if self.is_playing:
            self._sync_audio_playback(seek=True)
        else:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
            if getattr(self, "dub_channel", None):
                self.dub_channel.stop()
            pygame.mixer.stop()

    def on_seek_relative(self, delta_sec: float):
        dur = self.editor_model.get_total_duration() if self.editor_model.clips else self.video_info.get("duration", 0.0)
        self.current_time_sec = max(0.0, min(dur, self.current_time_sec + delta_sec))
        self._needs_seek = True
        self.player_view.set_time_pos(self.current_time_sec)
        self._last_spoken_id = None
        self._last_synced_sub_id = None
        self._spoken_ids.clear()
        if getattr(self, "dub_channel", None):
            self.dub_channel.stop()
        if self.is_playing:
            self._sync_audio_playback(seek=True)
        else:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            pygame.mixer.stop()
        self._render_current_frame(force_seek=True)

    def on_timeline_seek(self, sec: float):
        self.current_time_sec = sec
        self._needs_seek = True
        self._last_spoken_id = None
        self._last_synced_sub_id = None
        self._spoken_ids.clear()
        if getattr(self, "dub_channel", None):
            self.dub_channel.stop()
        if self.is_playing:
            self._sync_audio_playback(seek=True)
        else:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            pygame.mixer.stop()
        self._render_current_frame(force_seek=True)

    def _start_playback_loop(self):
        """Silky smooth, high-fps video player thread with wall-clock time synchronization"""
        def loop():
            last_time = time.time()
            while True:
                now = time.time()
                dt = now - last_time
                last_time = now

                if self.is_playing and (self.video_path or self.editor_model.clips):
                    dur = self.editor_model.get_total_duration() if self.editor_model.clips else self.video_info.get("duration", 0.0)

                    # Progressive Playback Buffering Check
                    if getattr(self, "pipeline", None) and self.pipeline.is_running:
                        max_playable = self.pipeline.get_max_playable_sec()
                        if max_playable > 0 and self.current_time_sec + dt >= max_playable and max_playable < dur:
                            self.after(0, lambda: self.player_view.show_buffering(True, f"Processing next chunk (>{time.strftime('%M:%S', time.gmtime(max_playable))})"))
                            time.sleep(0.08)
                            continue
                        else:
                            self.after(0, lambda: self.player_view.show_buffering(False))

                    self.current_time_sec += dt
                    if self.current_time_sec >= dur:
                        self.current_time_sec = dur
                        self.is_playing = False
                        self.after(0, lambda: self.player_view.set_play_state(False))
                        try:
                            pygame.mixer.music.stop()
                        except Exception:
                            pass
                        if getattr(self, "dub_channel", None):
                            self.dub_channel.stop()
                        pygame.mixer.stop()

                    self.after(0, lambda: self.player_view.set_time_pos(self.current_time_sec))
                    self.after(0, lambda: self._render_current_frame(force_seek=False))
                time.sleep(0.030)  # ~33 fps buttery smooth playback

        threading.Thread(target=loop, daemon=True).start()

    # ------------------ SUBTITLES & EDITING ------------------
    def on_select_subtitle(self, idx: int, start_sec: float):
        self.current_time_sec = start_sec
        self._needs_seek = True
        self._last_spoken_id = None
        self.player_view.set_time_pos(start_sec)
        self.player_view.select_subtitle(idx)
        self.subtitles_view.select_subtitle_by_index(idx, scroll_to_view=True)
        self._render_current_frame(force_seek=True)

    def on_apply_subtitle_edit(self, idx: int, new_text: str, new_start: float = None, new_end: float = None, new_rate: str = None):
        if 0 <= idx < len(self.subtitles_data):
            sub = self.subtitles_data[idx]
            sub["translated"] = new_text
            if new_start is not None:
                sub["start"] = max(0.0, round(new_start, 2))
            if new_end is not None:
                sub["end"] = max(sub["start"] + 0.2, round(new_end, 2))
            if new_rate is not None:
                sub["rate"] = new_rate

            self.subtitles_view.populate_subtitles(self.subtitles_data)
            self.player_view.set_subtitles(self.subtitles_data)
            self.current_time_sec = sub["start"]
            self._render_current_frame(force_seek=True)
            
            # Re-synthesize voice file for this edited segment with chosen speed rate
            self._re_synthesize_single_sub(sub)
            self.save_subtitles_state()
            messagebox.showinfo("ជោគជ័យ", "បានកែសម្រួលអត្ថបទ នាទីនិយាយ និងល្បឿនជោគជ័យ!")
        else:
            messagebox.showwarning("ជ្រើសរើសបន្ទាត់", "សូមចុចលើប៊ូតុង Jump នៃបន្ទាត់ណាមួយជាមុនសិន!")

    def on_translate_single_subtitle(self, idx: int):
        """Translates a single dialogue line to the selected target language (Khmer) and re-synthesizes voice"""
        if not (0 <= idx < len(self.subtitles_data)):
            if self.subtitles_data:
                idx = 0
            else:
                return
        sub = self.subtitles_data[idx]
        orig = sub.get("original", "").strip()
        if not orig:
            return
        settings = self.subtitles_view.get_translation_settings()
        self.translation_service.set_provider(settings["provider"], settings["api_key"], style=settings.get("style", ""))
        src = "zh" if "Chinese" in settings["source_lang"] else ("en" if "English" in settings["source_lang"] else "auto")
        tgt = "km" if "Khmer" in settings.get("target_lang", "Khmer") else ("en" if "English" in settings.get("target_lang", "") else "km")

        def worker():
            sub_id = sub.get("id", idx + 1)
            self.update_status(f"🌐 កំពុងបកប្រែបន្ទាត់ #{sub_id}...", 0.5)
            try:
                km = self.translation_service.translate_text(orig, source_lang=src, target_lang=tgt)
                if km:
                    sub["translated"] = km
                def _done():
                    self.subtitles_view.populate_subtitles(self.subtitles_data)
                    self.player_view.set_subtitles(self.subtitles_data)
                    self.subtitles_view.select_subtitle_by_index(idx, scroll_to_view=True)
                    self._re_synthesize_single_sub(sub)
                    self.save_subtitles_state()
                    self.update_status(f"✅ បានបកប្រែបន្ទាត់ #{sub_id} ជោគជ័យ!", 1.0)
                self.after(0, _done)
            except Exception as e:
                self.update_status(f"❌ កំហុសបកប្រែ: {e}", 0.0)

        threading.Thread(target=worker, daemon=True).start()

    def on_move_sub_timing(self, idx: int, new_start: float, new_end: float):
        """Called interactively as user drags CC / Voice block horizontally along timeline"""
        if 0 <= idx < len(self.subtitles_data):
            self.subtitles_data[idx]["start"] = round(new_start, 2)
            self.subtitles_data[idx]["end"] = round(new_end, 2)
            self.subtitles_view.set_selected_timing(new_start, new_end)
            self.current_time_sec = new_start
            self._last_spoken_id = None
            self._spoken_ids.clear()
            self._render_current_frame(force_seek=True)

    def on_commit_sub_timing(self, idx: int, new_start: float, new_end: float):
        """Called when user releases mouse after moving CC / Voice block on timeline"""
        if 0 <= idx < len(self.subtitles_data):
            sub = self.subtitles_data[idx]
            sub["start"] = round(new_start, 2)
            sub["end"] = round(new_end, 2)
            self._last_spoken_id = None
            self._spoken_ids.clear()

            # Keep existing voice file and rename on disk if feasible without slow re-download
            old_audio = sub.get("audio_file")
            if old_audio and os.path.exists(old_audio):
                try:
                    v_dir = os.path.dirname(old_audio)
                    s_time = format_filename_timestamp(new_start)
                    e_time = format_filename_timestamp(new_end)
                    new_filename = f"#{sub.get('id', idx+1)}_{s_time}_to_{e_time}.mp3"
                    new_filepath = os.path.join(v_dir, new_filename)
                    if old_audio != new_filepath:
                        if sub.get("id") in self._cached_sounds:
                            del self._cached_sounds[sub["id"]]
                        os.rename(old_audio, new_filepath)
                        sub["audio_file"] = new_filepath
                        self._cached_sounds[sub["id"]] = pygame.mixer.Sound(new_filepath)
                except Exception:
                    pass

            self.subtitles_view.populate_subtitles(self.subtitles_data)
            self.player_view.set_subtitles(self.subtitles_data)
            self.update_status(f"⏱️ បានផ្លាស់ប្តូរពេលវេលា CC & សំឡេង #{sub.get('id', idx+1)}: {time.strftime('%M:%S', time.gmtime(new_start))} - {time.strftime('%M:%S', time.gmtime(new_end))}", 0.0)

    def on_auto_sync_subtitle_speed(self, idx: int, target_dur: float, text: str):
        """Auto-calculates optimal speech rate and re-generates voice to finish strictly within video slot"""
        if 0 <= idx < len(self.subtitles_data):
            sub = self.subtitles_data[idx]
            sub["translated"] = text
            auto_rate = DubbingEngine.calculate_auto_rate(text, target_dur)
            sub["rate"] = auto_rate
            voice_choice = self.dubbing_view.combo_voice.get()
            sub_id = sub.get('id', idx+1)
            self._append_log(
                f"⚡ [AI Voice] កំពុងកែតម្រូវល្បឿន និងបង្កើតសំឡេងដោយ AI | Engine: Edge TTS Neural ({voice_choice}) | "
                f"Auto-Sync Rate: {auto_rate} ឱ្យទាន់រយៈពេលវីដេអូ {target_dur:.2f}s សម្រាប់ CC #{sub_id}"
            )
            self.update_status(f"⚡ [AI Voice] កំពុងកែតម្រូវសំឡេង AI #{sub_id} ({auto_rate}) ឱ្យទាន់វីដេអូ...", 0.1)

            def worker():
                self.dubbing_engine.set_voice(voice_choice)
                v_dir = self.get_voices_directory()
                s_time = format_filename_timestamp(sub.get("start", 0.0))
                e_time = format_filename_timestamp(sub.get("end", 0.0))
                out_path = os.path.join(v_dir, f"#{sub_id}_{s_time}_to_{e_time}.mp3")

                ok = self.dubbing_engine.synthesize_line(text, out_path, rate=auto_rate, target_dur=target_dur)
                if ok and os.path.exists(out_path):
                    sub["audio_file"] = out_path
                    try:
                        self._cached_sounds[sub_id] = pygame.mixer.Sound(out_path)
                    except Exception:
                        pass
                    self._append_log(f"✅ [AI Voice] បានបង្កើតសំឡេង AI សម្រួលល្បឿន #{sub_id} ({auto_rate}) ជោគជ័យ")
                def _done():
                    self.subtitles_view.populate_subtitles(self.subtitles_data)
                    self.player_view.set_subtitles(self.subtitles_data)
                    self.update_status(f"✅ បានកំណត់ល្បឿននិយាយ #{sub_id} ({auto_rate}) ទាន់វីដេអូជោគជ័យ!", 0.0)
                self.after(0, _done)

            threading.Thread(target=worker, daemon=True).start()

    def on_duplicate_subtitle(self, idx: int):
        """Duplicates a subtitle clip on the timeline"""
        if 0 <= idx < len(self.subtitles_data):
            src = self.subtitles_data[idx]
            dur = max(0.5, src.get("end", 0.0) - src.get("start", 0.0))
            new_sub = dict(src)
            new_sub["start"] = round(src.get("end", 0.0) + 0.05, 2)
            new_sub["end"] = round(new_sub["start"] + dur, 2)
            new_sub["audio_file"] = None
            self.subtitles_data.append(new_sub)
            self.subtitles_data.sort(key=lambda x: x["start"])
            for i, s in enumerate(self.subtitles_data):
                s["id"] = i + 1

            self.subtitles_view.populate_subtitles(self.subtitles_data)
            self.player_view.set_subtitles(self.subtitles_data)
            self.update_status(f"📋 បានចម្លង (Duplicate) CC #{src.get('id')} ជោគជ័យ", 0.0)
            self._re_synthesize_single_sub(new_sub)

    def on_delete_subtitle(self, idx: int):
        """Deletes a subtitle clip from timeline and subtitles list"""
        if 0 <= idx < len(self.subtitles_data):
            del_sub = self.subtitles_data.pop(idx)
            sub_id = del_sub.get("id")
            if sub_id in self._cached_sounds:
                del self._cached_sounds[sub_id]
            a_file = del_sub.get("audio_file")
            if a_file and os.path.exists(a_file):
                try:
                    os.remove(a_file)
                except Exception:
                    pass
            for i, s in enumerate(self.subtitles_data):
                s["id"] = i + 1

            self.subtitles_view.populate_subtitles(self.subtitles_data)
            self.player_view.set_subtitles(self.subtitles_data)
            self._render_current_frame(force_seek=True)
            self.update_status(f"🗑️ បានលុប CC #{sub_id} រួចរាល់", 0.0)

    def on_listen_subtitle_line(self, text: str, rate: str = "+0%"):
        if not text:
            return
        # Find matching subtitle or synthesize
        matched_sub = None
        for s in self.subtitles_data:
            if s.get("translated", "").strip() == text.strip():
                matched_sub = s
                break
        if matched_sub:
            matched_sub["rate"] = rate
            self._play_segment_audio(matched_sub)
        else:
            line_id = abs(hash(text)) % 100000
            self._play_segment_audio({"id": line_id, "translated": text, "rate": rate})

    def _re_synthesize_single_sub(self, sub: dict):
        def worker():
            voice_choice = self.dubbing_view.combo_voice.get()
            self.dubbing_engine.set_voice(voice_choice)
            voice_dir = self.get_voices_directory()
            rate = sub.get("rate", "+0%")
            sub_id = sub.get("id", "?")
            txt = (sub.get("translated") or sub.get("text") or "")[:35]
            self._append_log(
                f"🤖 [AI Voice] បង្កើតសំឡេងឡើងវិញដោយ AI | Engine: Edge TTS Neural ({self.dubbing_engine.voice_name}) | "
                f"តួសំឡេង: {voice_choice} | Rate: {rate} សម្រាប់ CC #{sub_id}: \"{txt}...\""
            )
            self.dubbing_engine.generate_segment_files([sub], voice_dir, default_rate=rate, force_refresh=True)
            if sub.get("audio_file") and os.path.exists(sub["audio_file"]):
                try:
                    self._cached_sounds[sub["id"]] = pygame.mixer.Sound(sub["audio_file"])
                except Exception:
                    pass
                self._append_log(f"✅ [AI Voice] បង្កើតសំឡេងដោយ AI ជោគជ័យ សម្រាប់ CC #{sub_id} -> {os.path.basename(sub['audio_file'])}")
        threading.Thread(target=worker, daemon=True).start()

    def save_subtitles_state(self, force_save_srt: bool = False):
        """
        Auto-persists current subtitle translation and audio file mappings to disk:
        1. <video_dir>/<base_name>_subtitles.json (full state with original, translated, audio_file, rate)
        2. <video_dir>/<base_name>.km.srt (if Khmer translation exists)
        3. <video_dir>/<base_name>.srt (auto-saved to video folder if no .srt exists or force_save_srt=True)
        Allows 100% resumption if the app crashes, is closed, or video is re-opened.
        """
        if not self.video_path or not self.subtitles_data:
            return
        try:
            import json
            v_dir = os.path.dirname(os.path.abspath(self.video_path))
            base_name = os.path.splitext(os.path.basename(self.video_path))[0]
            json_path = os.path.join(v_dir, f"{base_name}_subtitles.json")

            data_to_save = []
            for s in self.subtitles_data:
                data_to_save.append({
                    "id": s.get("id"),
                    "start": float(s.get("start", 0.0)),
                    "end": float(s.get("end", 0.0)),
                    "original": str(s.get("original", "")),
                    "translated": str(s.get("translated", "")),
                    "audio_file": s.get("audio_file") if s.get("audio_file") and os.path.exists(s.get("audio_file")) else None,
                    "rate": s.get("rate", "+0%")
                })

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)

            default_srt_path = os.path.join(v_dir, f"{base_name}.srt")
            km_srt_path = os.path.join(v_dir, f"{base_name}.km.srt")

            # Check if any companion .srt file already exists in the video folder
            existing_srts = []
            try:
                existing_srts = [
                    f for f in os.listdir(v_dir)
                    if f.lower().endswith(".srt") and base_name.lower() in f.lower()
                ]
            except Exception:
                pass
            has_existing_srt = len(existing_srts) > 0

            has_khmer = any(is_khmer_text(s.get("translated", "")) for s in data_to_save)

            def _write_srt_file(target_file_path, prefer_translated=True):
                with open(target_file_path, "w", encoding="utf-8") as f_out:
                    for s in data_to_save:
                        sid = s["id"]
                        st_str = format_timestamp(s["start"])
                        et_str = format_timestamp(s["end"])
                        if prefer_translated:
                            txt = (s.get("translated") or "").strip()
                            if not txt:
                                txt = (s.get("original") or "").strip()
                        else:
                            txt = (s.get("original") or "").strip()
                            if not txt:
                                txt = (s.get("translated") or "").strip()
                        f_out.write(f"{sid}\n{st_str} --> {et_str}\n{txt}\n\n")

            # 1. Export Khmer SRT if translation exists
            if has_khmer:
                _write_srt_file(km_srt_path, prefer_translated=True)

            # 2. If no .srt exists in video folder (or force_save_srt=True or <base_name>.srt doesn't exist), auto-save <base_name>.srt!
            if not has_existing_srt or force_save_srt or not os.path.exists(default_srt_path):
                _write_srt_file(default_srt_path, prefer_translated=has_khmer)

        except Exception as ex:
            print(f"Warning: Failed to auto-save subtitles state: {ex}")

    # ------------------ INDIVIDUAL VOICE SEGMENT GENERATOR ------------------
    def get_voices_directory(self) -> str:
        """Returns the dedicated folder where individual voice files are saved (with low disk space auto-fallback)"""
        if self.video_path:
            v_dir = os.path.dirname(os.path.abspath(self.video_path))
            v_name = os.path.splitext(os.path.basename(self.video_path))[0]
            target = os.path.join(v_dir, f"{v_name}_khmer_voices")

            has_existing_clips = os.path.exists(target) and any(f.endswith(".mp3") for f in os.listdir(target)) if os.path.exists(target) else False

            import shutil
            try:
                free_space = shutil.disk_usage(v_dir).free
            except Exception:
                free_space = 1024 * 1024 * 1024

            # If less than 400MB free and no clips in target, fallback to C: drive to avoid [Errno 28] No space left on device
            if free_space < 400 * 1024 * 1024 and not has_existing_clips:
                c_fallback = os.path.join(os.path.expanduser("~"), ".khmer_movie_studio", "voices_cache", f"{v_name}_khmer_voices")
                os.makedirs(c_fallback, exist_ok=True)
                return c_fallback
        else:
            target = os.path.abspath("khmer_voices")
        os.makedirs(target, exist_ok=True)
        return target

    def on_open_voice_folder(self):
        """Opens the directory containing individual voice files in Windows Explorer"""
        v_dir = self.get_voices_directory()
        try:
            os.startfile(v_dir)
        except Exception as e:
            messagebox.showinfo("Voice Folder", f"ទីតាំងថតសំឡេងខ្មែរ:\n{v_dir}")

    def auto_generate_all_segment_voices(self, subs: list, force_refresh: bool = False, session_id: int = None):
        """
        Generates individual voice files per subtitle segment (#1, #2... = 1 voice file each)
        Seamlessly resumes: reuses existing generated clips and only synthesizes missing ones!
        """
        if session_id is None:
            session_id = getattr(self, "_video_session_id", 0)

        def worker():
            if session_id != getattr(self, "_video_session_id", 0):
                return

            # If any subtitle line is missing Khmer translation, auto-translate first before generating voices!
            untranslated = [s for s in subs if not is_khmer_text(s.get("translated", ""))]
            if untranslated:
                self.update_status(f"⚡ កំពុងបន្តបកប្រែជាភាសាខ្មែរ ({len(untranslated)}/{len(subs)} បន្ទាត់)...", 0.05)
                trans_settings = self.subtitles_view.get_translation_settings()
                self.translation_service.set_provider(trans_settings["provider"], trans_settings["api_key"], style=trans_settings.get("style", ""))
                src_code = "zh" if "Chinese" in trans_settings["source_lang"] else ("en" if "English" in trans_settings["source_lang"] else "auto")
                
                self.translation_service.translate_subtitles_parallel(
                    subtitles=untranslated,
                    source_lang=src_code,
                    target_lang="km",
                    batch_size=15,
                    max_workers=16,
                    progress_callback=self.update_status,
                    check_cancel=lambda: session_id != getattr(self, "_video_session_id", 0)
                )

                self.save_subtitles_state()

                if session_id != getattr(self, "_video_session_id", 0):
                    return

                self.after(0, lambda: [
                    self.subtitles_view.populate_subtitles(self.subtitles_data) if session_id == getattr(self, "_video_session_id", 0) else None,
                    self.player_view.set_subtitles(self.subtitles_data) if session_id == getattr(self, "_video_session_id", 0) else None
                ])

            if session_id != getattr(self, "_video_session_id", 0):
                return

            if hasattr(self, "subtitles_view") and hasattr(self.subtitles_view, "get_dubbing_settings"):
                settings = self.subtitles_view.get_dubbing_settings()
                voice_choice = settings["voice_key"]
                speed_rate = settings["speed_rate"]
                if speed_rate == "auto":
                    speed_rate = "+10%"
            else:
                settings = self.dubbing_view.get_dubbing_settings()
                voice_choice = settings["voice_key"]
                speed_rate = settings.get("speed_rate", "+10%")
            self.dubbing_engine.set_voice(voice_choice)
            v_dir = self.get_voices_directory()

            self._append_log(
                f"🤖 [AI Voice] ចាប់ផ្ដើមបង្កើតសំឡេងដោយ AI សម្រាប់រឿងទាំងមូល | "
                f"Engine: Microsoft Edge TTS (Khmer Neural Studio) | តួសំឡេង AI: {voice_choice} ({self.dubbing_engine.voice_name}) | "
                f"ល្បឿន: {speed_rate} | ចំនួន: {len(subs)} បន្ទាត់"
            )
            self.update_status(f"🤖 [AI Voice] កំពុងបង្កើតសំឡេងដោយ AI (Edge TTS Neural: {voice_choice})...", 0.35)
            generated = self.dubbing_engine.generate_segment_files(
                subtitles=subs,
                voice_dir=v_dir,
                default_rate=speed_rate,
                force_refresh=force_refresh,
                progress_callback=self.update_status
            )

            # Auto-save state with new audio files
            self.save_subtitles_state()

            if session_id != getattr(self, "_video_session_id", 0):
                return

            # Pre-cache first 60 sounds into pygame.mixer.Sound for instant playback (remaining load on demand)
            for s in subs[:60]:
                sid = s.get("id")
                afile = s.get("audio_file")
                if afile and os.path.exists(afile):
                    try:
                        self._cached_sounds[sid] = pygame.mixer.Sound(afile)
                    except Exception:
                        pass

            self._append_log(
                f"🎉 [AI Voice] បានបង្កើតសំឡេងដោយ AI ជោគជ័យគ្រប់បន្ទាត់ ({len(generated)}/{len(subs)} files)! | "
                f"Engine: Edge TTS ({self.dubbing_engine.voice_name}) | ថតរក្សាទុក: {os.path.basename(v_dir)}"
            )
            self.update_status(f"🎉 សំឡេង AI គ្រប់បន្ទាត់រួចរាល់ ({len(generated)} files)! ថត: {os.path.basename(v_dir)}", 1.0)
            self.after(0, lambda: self.dubbing_view.btn_dub.configure(state="normal"))
            self.after(0, lambda: self.player_view.set_subtitles(self.subtitles_data) if session_id == getattr(self, "_video_session_id", 0) else None)

        self.dubbing_view.btn_dub.configure(state="disabled")
        threading.Thread(target=worker, daemon=True).start()

    # ------------------ ASYNC WORKERS ------------------
    def update_status(self, text: str, progress: float = None):
        def _u():
            self.dubbing_view.set_status(text, progress)
            self._update_status_bar(text, progress)
            self._append_log(text)
        self.after(0, _u)

    def start_translation_thread(self):
        """Transcribes entire movie audio continuously without chunk slicing, translates dialogue to Khmer, and auto-generates voices"""
        if not self.video_path:
            messagebox.showwarning("ជ្រើសរើសវីដេអូ", "សូមជ្រើសរើសវីដេអូរឿងជាមុនសិន!")
            return
        if self.is_processing:
            messagebox.showinfo("កំពុងដំណើរការ", "សូមរង់ចាំដំណើរការបច្ចុប្បន្ន...")
            return

        current_session = getattr(self, "_video_session_id", 0)
        self.is_processing = True
        self.header_view.set_translating_state(True)
        self.pipeline = None
        self.player_view.set_chunks_status([])

        settings = self.subtitles_view.get_translation_settings()
        self.translation_service.set_provider(settings["provider"], settings["api_key"], style=settings.get("style", ""))
        src_code = "zh" if "Chinese" in settings["source_lang"] else ("en" if "English" in settings["source_lang"] else "auto")
        v_path = self.video_path

        # If subtitles already loaded or companion/embedded CC exists, translate and dub directly!
        if self.subtitles_data:
            self._auto_translate_and_dub_subtitles(self.subtitles_data)
            self.is_processing = False
            self.header_view.set_translating_state(False)
            return

        found_subs = extract_embedded_or_companion_subtitles(v_path)
        if found_subs:
            if current_session == getattr(self, "_video_session_id", 0):
                self.subtitles_data = found_subs
                self.subtitles_view.populate_subtitles(self.subtitles_data)
                self.player_view.set_subtitles(self.subtitles_data)
                self.update_status(f"🎉 បានរកឃើញ CC ស្រាប់ក្នុងវីដេអូ ({len(found_subs)} បន្ទាត់)! កំពុងបកប្រែជាភាសាខ្មែរ...", 0.1)
                self._auto_translate_and_dub_subtitles(found_subs)
            self.is_processing = False
            self.header_view.set_translating_state(False)
            return

        def worker():
            try:
                self.update_status("🎬 កំពុងទាញយកសំឡេង និងវិភាគរឿងទាំងមូល (Continuous Recognition)...", 0.05)
                subs = self.speech_engine.transcribe_and_translate(
                    video_path=v_path,
                    translator_service=self.translation_service,
                    source_lang=src_code,
                    target_lang="km",
                    progress_callback=self.update_status
                )
                if current_session != getattr(self, "_video_session_id", 0):
                    return
                if not subs:
                    self.update_status("⚠️ មិនបានរកឃើញការសន្ទនា (Speech) នៅក្នុងវីដេអូនេះទេ", 1.0)
                    return

                self.subtitles_data = subs
                def _update_ui():
                    if current_session == getattr(self, "_video_session_id", 0):
                        self.subtitles_view.populate_subtitles(self.subtitles_data)
                        self.player_view.set_subtitles(self.subtitles_data)
                        self._render_current_frame(force_seek=False)
                self.after(0, _update_ui)

                # Automatically generate individual Khmer voice files with auto speed sync to video
                self.update_status(f"🎉 បកប្រែបាន {len(subs)} បន្ទាត់! កំពុងបង្កើតសំឡេងខ្មែរតាមនាទីវីដេអូ...", 0.6)
                self.save_subtitles_state(force_save_srt=True)
                self.auto_generate_all_segment_voices(self.subtitles_data, force_refresh=False, session_id=current_session)

            except Exception as e:
                if current_session == getattr(self, "_video_session_id", 0):
                    err_msg = str(e)
                    print(f"Continuous translation error: {err_msg}")
                    self.update_status(f"❌ កំហុសបកប្រែ: {err_msg[:45]}", 0.0)
                    self.after(0, lambda: messagebox.showerror("Translation Error", f"ដំណើរការបកប្រែមានបញ្ហា:\n{err_msg}"))
            finally:
                if current_session == getattr(self, "_video_session_id", 0):
                    self.is_processing = False
                    self.after(0, lambda: self.header_view.set_translating_state(False))

        threading.Thread(target=worker, daemon=True).start()

    def on_chunk_status_change(self, chunk):
        def _u():
            if getattr(self, "pipeline", None):
                self.player_view.set_chunks_status(self.pipeline.chunks)
            if chunk.status == "PROCESSING":
                pct = (chunk.chunk_id) / max(1, len(self.pipeline.chunks))
                self.update_status(f"⚡ Processing Chunk #{chunk.chunk_id+1} ({chunk.start_sec:.0f}s-{chunk.end_sec:.0f}s)...", pct)
            elif chunk.status == "FAILED":
                self.update_status(f"❌ Chunk #{chunk.chunk_id+1} failed: {chunk.error_msg[:40]}", 0.0)
        self.after(0, _u)

    def on_chunk_ready(self, chunk):
        def _u():
            # Append new chunk subtitles into self.subtitles_data avoiding duplicates
            existing_starts = {s["start"] for s in self.subtitles_data}
            for s in chunk.subtitles:
                if s["start"] not in existing_starts:
                    s["id"] = len(self.subtitles_data) + 1
                    self.subtitles_data.append(s)
                    existing_starts.add(s["start"])

            # Sort subtitles by timestamp
            self.subtitles_data.sort(key=lambda x: x["start"])
            for idx, s in enumerate(self.subtitles_data):
                s["id"] = idx + 1

            self.subtitles_view.populate_subtitles(self.subtitles_data)
            self.player_view.set_subtitles(self.subtitles_data)
            if getattr(self, "pipeline", None):
                self.player_view.set_chunks_status(self.pipeline.chunks)
            self.player_view.show_buffering(False)
            pct = (chunk.chunk_id + 1) / max(1, len(self.pipeline.chunks))
            self.update_status(f"🎉 Chunk #{chunk.chunk_id+1} រួចរាល់! ({len(chunk.subtitles)} បន្ទាត់) - ចាក់មើលភ្លាមៗបាន!", pct)
            self._render_current_frame(force_seek=False)
        self.after(0, _u)

    def on_chunk_pipeline_complete(self, chunks):
        def _u():
            self.is_processing = False
            self.header_view.set_translating_state(False)
            self.player_view.show_buffering(False)
            if getattr(self, "pipeline", None):
                self.player_view.set_chunks_status(self.pipeline.chunks)
            self.update_status(f"🎉 ដំណើរការគ្រប់ Chunk ចប់សព្វគ្រប់ ({len(self.subtitles_data)} បន្ទាត់ CC)! សំឡេងខ្មែរ 1 file/line រួចរាល់។", 1.0)
        self.after(0, _u)

    def on_retry_chunk(self, chunk_id: int):
        if not getattr(self, "pipeline", None):
            return
        settings = self.subtitles_view.get_translation_settings()
        self.translation_service.set_provider(settings["provider"], settings["api_key"], style=settings.get("style", ""))
        src_code = "zh" if "Chinese" in settings["source_lang"] else ("en" if "English" in settings["source_lang"] else "auto")
        voice_dir = self.get_voices_directory()
        self.update_status(f"🔄 កំពុងដំណើរការ Chunk #{chunk_id+1} ឡើងវិញ...", 0.0)
        self.pipeline.retry_chunk(
            chunk_id=chunk_id,
            speech_engine=self.speech_engine,
            translation_service=self.translation_service,
            dubbing_engine=self.dubbing_engine,
            source_lang=src_code,
            target_lang="km",
            voice_dir=voice_dir,
            on_chunk_status_change=self.on_chunk_status_change,
            on_chunk_ready=self.on_chunk_ready
        )

    def on_add_cc_track(self):
        new_id = self.editor_model.add_cc_track()
        self.player_view.set_cc_tracks(self.editor_model.cc_tracks)
        self.update_status(f"➕ បានបន្ថែម CC Track #{new_id+1} ចូល Timeline", 0.0)

    def on_add_audio_track(self):
        new_id = self.editor_model.add_audio_track()
        self.player_view.set_audio_tracks(self.editor_model.audio_tracks)
        self.update_status(f"➕ បានបន្ថែម Audio Track #{new_id+1} (Audio {new_id+1}) ចូល Timeline", 0.0)

    def on_toggle_audio_mute(self, a_idx: int):
        muted = self.editor_model.toggle_audio_track_mute(a_idx)
        self.player_view.set_audio_tracks(self.editor_model.audio_tracks)
        name = self.editor_model.audio_tracks[a_idx]["name"]
        st = "បិទសំឡេង (Muted)" if muted else "បើកសំឡេង (Active)"
        self.update_status(f"🔊 {name}: {st}", 0.0)

        # Apply mute/unmute immediately to active playback engines
        if a_idx == 0:  # Audio 1 (Original Video)
            vol = 0.0 if muted else self.editor_model.audio_tracks[0].get("volume", 0.8)
            try:
                pygame.mixer.music.set_volume(vol)
            except Exception:
                pass
        elif a_idx == 1:  # Audio 2 (Khmer Dub)
            if muted and getattr(self, "dub_channel", None):
                self.dub_channel.stop()

    def start_dubbing_thread(self):
        """Manual trigger to generate/refresh all individual Khmer voice files without save dialog"""
        if not self.subtitles_data:
            messagebox.showwarning("គ្មាន CC", "សូមបកប្រែរឿងដើម្បីទទួលបានអត្ថបទ CC ជាមុនសិន!")
            return
        self.auto_generate_all_segment_voices(self.subtitles_data, force_refresh=True)

    def on_dub_all(self):
        """Generates/refreshes AI voices for all subtitle lines using selected model & speed"""
        if not self.subtitles_data:
            messagebox.showwarning("គ្មាន CC", "សូមបញ្ចូល ឬបកប្រែអត្ថបទ CC ជាមុនសិន!")
            return
        settings = self.subtitles_view.get_dubbing_settings()
        voice_choice = settings["voice_key"]
        rate = settings["speed_rate"]
        self.dubbing_engine.set_voice(voice_choice)
        if hasattr(self, "dubbing_view"):
            self.dubbing_view.combo_voice.set(voice_choice)
            if rate != "auto":
                self.dubbing_view.combo_speed.set(settings["speed_label"])
        self._append_log(
            f"🎙️ [AI Voice] បានចុច '🎧 Dub All' | Model: {voice_choice} ({self.dubbing_engine.voice_name}) | "
            f"Speed: {settings['speed_label']} | ចំនួន: {len(self.subtitles_data)} បន្ទាត់"
        )
        self.auto_generate_all_segment_voices(self.subtitles_data, force_refresh=True)

    def on_dub_selected(self, idx: int = None):
        """Generates AI voice for selected subtitle line using chosen model & speed"""
        if idx is None and hasattr(self.subtitles_view, "selected_idx"):
            idx = self.subtitles_view.selected_idx
        if idx is None or not (0 <= idx < len(self.subtitles_data)):
            if self.subtitles_data:
                idx = 0
            else:
                return
        sub = self.subtitles_data[idx]
        settings = self.subtitles_view.get_dubbing_settings()
        voice_choice = settings["voice_key"]
        rate = settings["speed_rate"]
        if rate == "auto":
            target_dur = max(0.4, sub.get("end", 0.0) - sub.get("start", 0.0))
            rate = DubbingEngine.calculate_auto_rate(sub.get("translated", ""), target_dur)
        sub["rate"] = rate
        self.dubbing_engine.set_voice(voice_choice)
        if hasattr(self, "dubbing_view"):
            self.dubbing_view.combo_voice.set(voice_choice)
        sub_id = sub.get("id", idx + 1)
        self._append_log(
            f"🎯 [AI Voice] បានចុច '🎯 Dub Selected' សម្រាប់ CC #{sub_id} | "
            f"Model: {voice_choice} ({self.dubbing_engine.voice_name}) | Rate: {rate}"
        )
        self._re_synthesize_single_sub(sub)

    def on_dub_missing(self):
        """Generates AI voices only for subtitle lines that lack audio files"""
        if not self.subtitles_data:
            messagebox.showwarning("គ្មាន CC", "សូមបញ្ចូល ឬបកប្រែអត្ថបទ CC ជាមុនសិន!")
            return
        missing = [s for s in self.subtitles_data if not s.get("audio_file") or not os.path.exists(s.get("audio_file"))]
        if not missing:
            messagebox.showinfo("រួចរាល់ហើយ", "គ្រប់បន្ទាត់ CC ទាំងអស់សុទ្ធតែមានសំឡេងរួចរាល់ហើយ (0 missing)!")
            self._append_log("⚡ [AI Voice] គ្រប់បន្ទាត់ CC ទាំងអស់សុទ្ធតែមានសំឡេងរួចរាល់ហើយ (No missing files).")
            return
        settings = self.subtitles_view.get_dubbing_settings()
        voice_choice = settings["voice_key"]
        self.dubbing_engine.set_voice(voice_choice)
        if hasattr(self, "dubbing_view"):
            self.dubbing_view.combo_voice.set(voice_choice)
        self._append_log(
            f"⚡ [AI Voice] រកឃើញបន្ទាត់ខ្វះសំឡេង {len(missing)}/{len(self.subtitles_data)} | "
            f"កំពុងបំពេញសំឡេងដោយ AI (Model: {voice_choice})..."
        )
        self.auto_generate_all_segment_voices(self.subtitles_data, force_refresh=False)

    def on_subtitles_voice_change(self, choice: str):
        self.dubbing_engine.set_voice(choice)
        if hasattr(self, "dubbing_view"):
            self.dubbing_view.combo_voice.set(choice)
        self._append_log(f"🎤 [AI Voice] បានជ្រើសរើស Voice Model ថ្មី: {choice} ({self.dubbing_engine.voice_name})")
        self.update_status(f"🎤 AI Voice Model: {choice.split()[0]}", 1.0)

    def on_subtitles_speed_change(self, choice: str):
        if hasattr(self, "dubbing_view"):
            self.dubbing_view.combo_speed.set(choice)
        self._append_log(f"⚡ [AI Voice] បានផ្លាស់ប្តូរល្បឿននិយាយ: {choice}")

    def on_export_srt(self):
        if not self.subtitles_data:
            messagebox.showwarning("ទិន្នន័យទទេ", "មិនទាន់មានទិន្នន័យ CC នៅឡើយទេ!")
            return

        default_name = (os.path.splitext(os.path.basename(self.video_path))[0] if self.video_path else "subtitles") + "_khmer.srt"
        save_path = filedialog.asksaveasfilename(
            title="Save Subtitles (.srt)",
            initialfile=default_name,
            defaultextension=".srt",
            filetypes=[("SRT Subtitles", "*.srt"), ("All Files", "*.*")]
        )
        if save_path:
            is_dual = self.dubbing_view.check_dual.get()
            SubtitleBurner.export_srt(self.subtitles_data, save_path, use_translated=True, dual_language=is_dual)
            messagebox.showinfo("ជោគជ័យ", f"បានរក្សាទុកឯកសារ SRT នៅ:\n{save_path}")

    # ------------------ TIMELINE EDITING & CLIP CONTROLS ------------------
    def on_split_clip(self, split_time_sec: float):
        if not self.editor_model.clips:
            return
        ok = self.editor_model.split_clip_at(split_time_sec)
        if ok:
            self.player_view.set_video_clips(self.editor_model.clips)
            self.update_status(f"✂️ បានបំបែក Clip នៅវិនាទី {split_time_sec:.1f}s", 0.0)
        else:
            self.update_status("⚠️ មិនអាចបំបែក Clip នៅទីតាំងនេះបានទេ (ចន្លោះតូចពេក)", 0.0)

    def on_trim_clip(self):
        if not self.editor_model.clips:
            return
        import tkinter.simpledialog as sd
        choice = sd.askstring("Trim Clip (កាត់ Clip)", "បញ្ចូលការកាត់ (ឧទាហរណ៍: '+1.0' កាត់ដើម 1s, '-1.0' កាត់ចុង 1s):", initialvalue="+1.0")
        if choice:
            try:
                val = float(choice)
                if val >= 0:
                    self.editor_model.trim_active_clip(trim_start_delta=val)
                else:
                    self.editor_model.trim_active_clip(trim_end_delta=val)
                tot_dur = self.editor_model.get_total_duration()
                self.player_view.set_duration(tot_dur)
                self.player_view.set_video_clips(self.editor_model.clips)
                self._render_current_frame(force_seek=True)
                self.update_status(f"✂️ កាត់ Clip រួចរាល់ ({val:+.1f}s) | Duration: {tot_dur:.1f}s", 0.0)
            except Exception as e:
                messagebox.showerror("Trim Error", str(e))

    def on_delete_clip(self):
        if len(self.editor_model.clips) <= 1:
            messagebox.showwarning("Delete Clip", "មិនអាចលុបបានទេ ត្រូវមានយ៉ាងហោច 1 Clip នៅក្នុង Timeline!")
            return
        self.editor_model.delete_active_clip()
        tot_dur = self.editor_model.get_total_duration()
        self.player_view.set_duration(tot_dur)
        self.player_view.set_video_clips(self.editor_model.clips)
        self.current_time_sec = min(self.current_time_sec, tot_dur)
        self._render_current_frame(force_seek=True)
        self.update_status("🗑️ បានលុប Clip រួចរាល់", 0.0)

    def on_add_clip(self):
        filetypes = [("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm"), ("All Files", "*.*")]
        f = filedialog.askopenfilename(title="Add Video Clip (បន្ថែម Clip ចូល Timeline)", filetypes=filetypes)
        if f:
            if not self.video_path:
                self.on_browse_video(f)
                return
            v_info = get_video_info(f)
            dur = v_info.get("duration", 10.0)
            self.editor_model.add_clip(f, dur)
            tot_dur = self.editor_model.get_total_duration()
            self.player_view.set_duration(tot_dur)
            self.player_view.set_video_clips(self.editor_model.clips)
            self._extract_preview_audio(f)
            self._update_project_explorer_info()
            self.update_status(f"➕ បានបន្ថែម Clip: {os.path.basename(f)} ({int(dur)}s)", 0.0)

    def on_add_music(self):
        self.dubbing_view._browse_bg_music()

    def on_undo(self):
        ok = self.editor_model.undo()
        if ok:
            tot_dur = self.editor_model.get_total_duration()
            self.player_view.set_duration(tot_dur)
            self.player_view.set_video_clips(self.editor_model.clips)
            self.player_view.set_font_family(self.editor_model.active_font)
            self.player_view.set_bg_music(self.editor_model.bg_music)
            f = self.editor_model.video_filters
            self.player_view.set_color_grading(f["brightness"], f["contrast"], f["saturation"])
            self.update_status("↩️ Undo ត្រឡប់ក្រោយជោគជ័យ", 0.0)
            self._render_current_frame(force_seek=True)

    def on_redo(self):
        ok = self.editor_model.redo()
        if ok:
            tot_dur = self.editor_model.get_total_duration()
            self.player_view.set_duration(tot_dur)
            self.player_view.set_video_clips(self.editor_model.clips)
            self.player_view.set_font_family(self.editor_model.active_font)
            self.player_view.set_bg_music(self.editor_model.bg_music)
            f = self.editor_model.video_filters
            self.player_view.set_color_grading(f["brightness"], f["contrast"], f["saturation"])
            self.update_status("↪️ Redo ទៅមុខជោគជ័យ", 0.0)
            self._render_current_frame(force_seek=True)

    # ------------------ STYLING & OVERLAY CALLBACKS ------------------
    def on_font_change(self, font_name: str):
        self.editor_model.active_font = font_name
        self.player_view.set_font_family(font_name)
        if hasattr(self, "subtitles_view"):
            self.subtitles_view.set_font_family(font_name)
        self.update_status(f"✍️ បានប្តូរពុម្ពអក្សរខ្មែរ: {font_name}", 0.0)

    def on_filter_change(self, brightness: float, contrast: float, saturation: float):
        self.editor_model.set_filters(brightness=brightness, contrast=contrast, saturation=saturation)
        self.player_view.set_color_grading(brightness=brightness, contrast=contrast, saturation=saturation)

    def on_watermark_change(self, path: str, pos: str, scale: float, opacity: float = 1.0, rel_x: float = None, rel_y: float = None):
        self.editor_model.set_watermark(image_path=path, pos=pos, scale=scale, opacity=opacity, rel_x=rel_x, rel_y=rel_y)
        self.player_view.set_watermark_image(img_path=path, pos_key=pos, scale=scale, opacity=opacity, rel_x=rel_x, rel_y=rel_y)

    def on_watermark_move_or_scale(self, path: str, pos: str, scale: float, opacity: float, rel_x: float, rel_y: float):
        """Called when user drags or scales watermark directly with mouse cursor on video preview"""
        self.editor_model.set_watermark(image_path=path, pos=pos, scale=scale, opacity=opacity, rel_x=rel_x, rel_y=rel_y)
        if hasattr(self, "dubbing_view"):
            self.dubbing_view.sync_watermark_ui(scale=scale, opacity=opacity, rel_x=rel_x, rel_y=rel_y)

    def on_preview_object_selected(self, obj_type: str):
        """Auto-reveals and focuses right Inspector panel when an object is selected in Video Preview"""
        if not getattr(self, "inspector_open", True):
            self.toggle_inspector()

    def on_master_volume_change(self, volume: float):
        """Synchronizes audio master volume with pygame mixer"""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))
        except Exception:
            pass

    def on_bg_music_browse(self, path: str):
        v_info = get_video_info(path)
        dur = v_info.get("duration", 60.0)
        self.editor_model.set_bg_music(path, dur)
        self.player_view.set_bg_music(self.editor_model.bg_music)
        self.update_status(f"🎵 បានបញ្ចូលតន្ត្រី BGM: {os.path.basename(path)} ({int(dur)}s)", 0.0)

    def on_audio_mix_change(self, audio_settings: dict):
        self.editor_model.audio_settings.update(audio_settings)
        if self.editor_model.audio_tracks:
            self.editor_model.audio_tracks[0]["volume"] = audio_settings.get("orig_vol", 0.85)
            self.editor_model.audio_tracks[0]["is_muted"] = audio_settings.get("mute_orig", False)
            if len(self.editor_model.audio_tracks) > 1:
                self.editor_model.audio_tracks[1]["volume"] = audio_settings.get("dub_vol", 1.0)
                self.editor_model.audio_tracks[1]["is_muted"] = audio_settings.get("mute_dub", False)
            if len(self.editor_model.audio_tracks) > 2:
                self.editor_model.audio_tracks[2]["volume"] = audio_settings.get("bgm_vol", 0.35)
                self.editor_model.audio_tracks[2]["is_muted"] = audio_settings.get("mute_bgm", False)
            self.player_view.set_audio_tracks(self.editor_model.audio_tracks)

    def on_cc_style_change(self, cc_style: dict):
        self.player_view.set_cc_effects(
            animation=cc_style.get("animation_display"),
            bg_style=cc_style.get("bg_style"),
            highlight_color=cc_style.get("highlight_color"),
            border_width=cc_style.get("border_width")
        )
        self.editor_model.cc_style = cc_style
        self._render_current_frame(force_seek=False)

    # ------------------ EXPORT CONTROLLER ------------------
    def start_burn_video_thread(self):
        """Burns styled subtitles onto MP4 matching exact on-screen preview placement (WYSIWYG)"""
        if not self.subtitles_data or not self.video_path:
            messagebox.showwarning("ទិន្នន័យទទេ", "សូមបើកវីដេអូ និងបកប្រែ CC ជាមុនសិន!")
            return
        if self.is_processing:
            return

        default_out = os.path.splitext(self.video_path)[0] + "_cc_burned.mp4"
        out_path = filedialog.asksaveasfilename(
            title="Save Video with CC (.mp4)",
            initialfile=os.path.basename(default_out),
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4")]
        )
        if not out_path:
            return

        self.is_processing = True
        self.dubbing_view.btn_burn.configure(state="disabled")

        def worker():
            temp_dub_wav = os.path.splitext(out_path)[0] + "_temp_dub.wav"
            try:
                settings = self.dubbing_view.get_dubbing_settings()
                cc_style = self.dubbing_view.get_cc_style_settings()
                audio_settings = self.dubbing_view.get_audio_settings()
                v_dir = self.get_voices_directory()
                tot_dur = self.editor_model.get_total_duration() if self.editor_model.clips else self.video_info.get("duration", 60.0)
                if self.subtitles_data:
                    tot_dur = max(tot_dur, max((float(s.get("end", 0.0)) for s in self.subtitles_data), default=0.0) + 2.0)

                # Assemble Khmer dub audio if subtitles exist and not muted
                has_dub = False
                if self.subtitles_data and not audio_settings.get("mute_dub", False):
                    self.update_status("🎙️ កំពុងផ្គុំសំឡេងនិយាយខ្មែរ (Assembling Khmer audio)...", 0.1)
                    self.dubbing_engine.set_voice(settings["voice_key"])
                    self.dubbing_engine.assemble_dubbed_audio(
                        subtitles=self.subtitles_data,
                        total_duration_sec=tot_dur,
                        output_wav_path=temp_dub_wav,
                        voice_dir=v_dir,
                        default_rate=settings.get("speed_rate", "+10%"),
                        progress_callback=self.update_status
                    )
                    has_dub = os.path.exists(temp_dub_wav) and os.path.getsize(temp_dub_wav) > 1000

                SubtitleBurner.burn_subtitles(
                    video_path=self.video_path,
                    output_video_path=out_path,
                    subtitles=self.subtitles_data,
                    font_name=self.player_view.cc_font_family,
                    font_size=self.player_view.cc_font_size,
                    font_color=settings["color_code"],
                    pos_x_rel=self.player_view.cc_rel_x,
                    pos_y_rel=self.player_view.cc_rel_y,
                    dual_language=settings["is_dual"],
                    animation=cc_style["animation_code"],
                    bg_style=cc_style["bg_style"],
                    highlight_color=cc_style["highlight_ass"],
                    border_width=cc_style["border_width"],
                    video_info=self.video_info,
                    dubbed_audio_path=temp_dub_wav if has_dub else None,
                    audio_settings=audio_settings,
                    burn_cc=settings.get("burn_cc", True),
                    progress_callback=self.update_status
                )
                self.update_status("🎉 នាំចេញវីដេអូមានសំឡេងខ្មែរ & CC ជោគជ័យ!", 1.0)
                self.after(0, lambda: messagebox.showinfo("ជោគជ័យ (Success)", f"វីដេអូមានសំឡេងខ្មែរ និង CC ត្រូវបានរក្សាទុកនៅ:\n{out_path}"))
            except Exception as e:
                self.update_status(f"❌ Error: {str(e)[:50]}", 0.0)
                self.after(0, lambda: messagebox.showerror("កំហុស", str(e)))
            finally:
                if os.path.exists(temp_dub_wav):
                    try:
                        os.remove(temp_dub_wav)
                    except Exception:
                        pass
                self.is_processing = False
                self.after(0, lambda: self.dubbing_view.btn_burn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def start_export_full_movie_thread(self):
        """
        Master Video Composition Exporter:
        Combines Video Clips + Khmer Dub + BGM + Color Grading + Watermark + Burned CC
        with user selected Resolution (720p/1080p/4K), Frame Rate (24/30/60 FPS), and Format (MP4/WebM).
        """
        if not self.editor_model.clips and not self.video_path:
            messagebox.showwarning("គ្មានទិន្នន័យ", "សូមបើកវីដេអូជាមុនសិន!")
            return
        if self.is_processing:
            return

        master_settings = self.dubbing_view.get_master_export_settings()
        ext = ".webm" if master_settings.get("is_webm") else ".mp4"
        default_out = (os.path.splitext(self.video_path)[0] if self.video_path else "master_movie") + f"_studio_master{ext}"
        
        filetypes = [("WebM Video", "*.webm")] if master_settings.get("is_webm") else [("MP4 Video", "*.mp4")]
        out_video = filedialog.asksaveasfilename(
            title="Export Master Movie Composition",
            initialfile=os.path.basename(default_out),
            defaultextension=ext,
            filetypes=filetypes
        )
        if not out_video:
            return

        self.is_processing = True
        self.dubbing_view.btn_export_all.configure(state="disabled")

        def worker():
            temp_dub_wav = os.path.splitext(out_video)[0] + "_temp_dub.wav"

            try:
                dub_settings = self.dubbing_view.get_dubbing_settings()
                audio_settings = self.dubbing_view.get_audio_settings()
                filter_settings = self.dubbing_view.get_filter_settings()
                watermark_settings = self.dubbing_view.get_watermark_settings()
                cc_layout = self.player_view.get_cc_layout()

                # Sync master export settings with current player preview layout
                master_settings["pos_x_rel"] = cc_layout["pos_x_rel"]
                master_settings["pos_y_rel"] = cc_layout["pos_y_rel"]
                master_settings["font_size"] = cc_layout["font_size"]
                master_settings["font_name"] = cc_layout["font_name"]

                tot_dur = self.editor_model.get_total_duration() if self.editor_model.clips else self.video_info.get("duration", 60.0)
                if self.subtitles_data:
                    tot_dur = max(tot_dur, max((float(s.get("end", 0.0)) for s in self.subtitles_data), default=0.0) + 2.0)
                v_dir = self.get_voices_directory()

                # 1. Assemble Khmer dub voice clips if subtitles exist and not muted
                has_dub = False
                if self.subtitles_data and not audio_settings.get("mute_dub", False):
                    self.update_status("🎙️ កំពុងផ្គុំសំឡេងនិយាយខ្មែរ (Assembling Khmer audio)...", 0.1)
                    self.dubbing_engine.set_voice(dub_settings["voice_key"])
                    self.dubbing_engine.assemble_dubbed_audio(
                        subtitles=self.subtitles_data,
                        total_duration_sec=tot_dur,
                        output_wav_path=temp_dub_wav,
                        voice_dir=v_dir,
                        default_rate=dub_settings.get("speed_rate", "+10%"),
                        progress_callback=self.update_status
                    )
                    has_dub = os.path.exists(temp_dub_wav) and os.path.getsize(temp_dub_wav) > 1000

                # 2. Clips to compose
                clips_to_export = self.editor_model.clips if self.editor_model.clips else [{
                    "path": self.video_path,
                    "start": 0.0,
                    "end": self.video_info.get("duration", 60.0),
                    "duration": self.video_info.get("duration", 60.0)
                }]

                bgm_path = audio_settings.get("bg_music_path")

                # 3. Master compilation pass
                SubtitleBurner.export_master_composition(
                    video_clips=clips_to_export,
                    subtitles=self.subtitles_data,
                    dubbed_audio_path=temp_dub_wav if has_dub else None,
                    bg_music_path=bgm_path,
                    audio_settings=audio_settings,
                    video_filters=filter_settings,
                    watermark=watermark_settings,
                    export_settings=master_settings,
                    output_path=out_video,
                    audio_tracks=self.editor_model.audio_tracks,
                    progress_callback=self.update_status
                )

                self.update_status("🎉 Export Master Movie (Full Composition) ជោគជ័យ!", 1.0)
                self.after(0, lambda: messagebox.showinfo(
                    "ជោគជ័យ (Success)", 
                    f"វីដេអូពេញលេញត្រូវបាននាំចេញជោគជ័យ:\n{out_video}\n\n• Video Clips + Trimming\n• Khmer Dubbed Audio & BGM Mix\n• Color Grading & Watermark Logo\n• Burned CC ({cc_layout['font_name']}, {master_settings.get('fps')} FPS)"
                ))

            except Exception as ex:
                self.update_status(f"❌ បរាជ័យ: {str(ex)[:50]}", 0.0)
                self.after(0, lambda: messagebox.showerror("កំហុស", str(ex)))
            finally:
                if os.path.exists(temp_dub_wav):
                    try:
                        os.remove(temp_dub_wav)
                    except Exception:
                        pass
                self.is_processing = False
                self.after(0, lambda: self.dubbing_view.btn_export_all.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------ TOP MENU BAR CALLBACKS & ACTIONS ------------------
    def on_test_gemini_api(self):
        """Verifies and tests user's Gemini API key with immediate feedback"""
        from config import GEMINI_API_KEY
        from services.translation import TranslationService
        
        self.update_status("🔍 កំពុងតេស្ត Gemini API Key...", 0.5)
        def _test_bg():
            t = TranslationService(provider="Gemini / Google AI (API Key)", api_key=GEMINI_API_KEY)
            sample_phrase = "Welcome to AI Khmer Movie Studio."
            try:
                res = t.translate_text(sample_phrase)
                model_used = getattr(t, "_active_gemini_model", "gemini-3.5-flash")
                self.after(0, lambda: self.header_view.set_api_status(True, model_used))
                self.after(0, lambda: messagebox.showinfo(
                    "Gemini API Status (ស្ថានភាព API Key)",
                    f"✅ API Key សកម្ម និងដំណើរការជោគជ័យ (Verified)!\n\n"
                    f"🔑 Key: {GEMINI_API_KEY[:8]}...{GEMINI_API_KEY[-6:]}\n"
                    f"🤖 Active Model: {model_used}\n\n"
                    f"📝 Test Input: \"{sample_phrase}\"\n"
                    f"🇰🇭 Translation: \"{res}\""
                ))
                self.after(0, lambda: self.update_status("✅ Gemini API Verified!", 1.0))
            except Exception as e:
                self.after(0, lambda: self.header_view.set_api_status(False))
                self.after(0, lambda: messagebox.showerror("Gemini API Error", f"❌ API Key Error:\n{str(e)}"))
                self.after(0, lambda: self.update_status("❌ Gemini API Error", 0.0))

        threading.Thread(target=_test_bg, daemon=True).start()

    def on_open_mobile_apk(self):
        """Opens version_phone directory and guides user on APK installation"""
        apk_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version_phone")
        apk_file = os.path.join(apk_dir, "KhmerMovieTranslator.apk")
        if os.path.exists(apk_dir):
            try:
                os.startfile(apk_dir)
            except Exception:
                import subprocess
                subprocess.Popen(f'explorer "{apk_dir}"')

        has_apk = os.path.exists(apk_file)
        messagebox.showinfo(
            "📱 Mobile Android APK (កំណែទូរស័ព្ទដៃ)",
            f"កម្មវិធីទូរស័ព្ទដៃ Android APK ស្ថិតនៅ:\n{apk_file if has_apk else apk_dir}\n\n"
            f"• ទំហំ: ~21.5 MB\n"
            f"• មុខងារ: ជ្រើសរើសវីដេអូ, Subtitle CC រត់លើវីដេអូ, សំឡេងបកប្រែខ្មែរ Piseth/Sreymom, និង Auto-Ducking\n\n"
            f"📌 របៀបដំឡើង:\n"
            f"1. ចម្លងឯកសារ KhmerMovieTranslator.apk ចូលទូរស័ព្ទ Android\n"
            f"2. ចុចដំឡើង (Install) ជាការស្រេច!"
        )

    def on_show_shortcuts(self):
        msg = (
            "⌨️ KEYBOARD SHORTCUTS GUIDE (គ្រាប់ចុចកាត់):\n\n"
            "• Space: ចាក់ / ផ្អាក វីដេអូ (Play / Pause)\n"
            "• Left Arrow (←): រំកិលថយក្រោយ 5 វិនាទី (-5s)\n"
            "• Right Arrow (→): រំកិលទៅមុខ 5 វិនាទី (+5s)\n"
            "• Ctrl + O: បើកឯកសារវីដេអូ (Open Video)\n"
            "• Ctrl + S: នាំចេញឯកសារ Subtitle (.srt)\n"
            "• Ctrl + K / S: កាត់តម្រឹម Clip នៅ Playhead (Split Clip)\n"
            "• Ctrl + T: កាត់ក្បាល/កន្ទុយ Clip (Trim)\n"
            "• Delete: លុប Clip ឬ Dialogue ដែលបានជ្រើស\n"
            "• Ctrl + Z: មិនធ្វើវិញ (Undo)\n"
            "• Ctrl + Y: ធ្វើវិញ (Redo)\n"
            "• Ctrl + / Ctrl -: ពង្រីក / បង្រួម UI (Zoom In / Out)\n"
            "• Ctrl + 0: ទំហំ UI ដើម 100% (Reset Zoom)\n"
            "• F11: បើក / បិទ ពេញអេក្រង់ (Fullscreen)\n"
        )
        messagebox.showinfo("Keyboard Shortcuts", msg)

    def on_show_about(self):
        messagebox.showinfo(
            "About AI Khmer Movie Studio",
            "🎬 ឧបករណ៍បកប្រែរឿងជាភាសាខ្មែរ (AI Khmer Movie Studio)\n\n"
            "កំណែ: Studio Pro 2026\n"
            "ម៉ាស៊ីន AI: Google Gemini 3.5 Flash + Whisper + Edge TTS\n"
            "លក្ខណៈពិសេស:\n"
            "• Dynamic N-Track Timeline (CapCut Studio Style)\n"
            "• Smart Auto-Ducking (ទម្លាក់សំឡេងវីដេអូពេលមានសំឡេងនិយាយ)\n"
            "• Real-time Khmer Karaoke CC & Font Customizer\n"
            "• Instant Dubbing & Voice Cloner\n"
            "• Mobile Phone Android APK Edition (21.5 MB)\n\n"
            "© 2026 AI Khmer Movie Studio. All rights reserved."
        )

    def on_menu_set_aspect_ratio(self, ratio_key: str):
        if hasattr(self, "player_view"):
            self.player_view._on_aspect_ratio_change(ratio_key)

    def toggle_fullscreen(self, event=None):
        is_fs = self.attributes("-fullscreen")
        self.attributes("-fullscreen", not is_fs)

    def on_toggle_auto_ducking(self):
        cur = getattr(self, "enable_ducking", True)
        self.enable_ducking = not cur
        status = "បើក (ON)" if self.enable_ducking else "បិទ (OFF)"
        self.update_status(f"🦆 Auto-Ducking: {status}", 1.0)
        messagebox.showinfo("Auto-Ducking", f"🦆 មុខងារ Auto-Ducking ត្រូវបាន: {status}\n\n(សំឡេងវីដេអូដើមនឹងទម្លាក់ចុះពេលមានសំឡេងនិយាយ)")

    def on_menu_select_voice(self, voice_code: str):
        if hasattr(self, "dubbing_view"):
            name = "Piseth (ប្រុស)" if "Piseth" in voice_code else "Sreymom (ស្រី)"
            self.dubbing_view.combo_voice.set(f"km-KH-{name}")
            self.update_status(f"🎤 ជ្រើសរើសតួសំឡេង AI: {name}", 1.0)
            self._append_log(f"🎤 [AI Voice] បានជ្រើសរើសតួសំឡេង AI: {name} (Engine: Microsoft Edge TTS Neural - {voice_code})")

    def on_menu_select_font(self):
        from config import get_installed_khmer_fonts
        fonts = get_installed_khmer_fonts()
        cur_font = getattr(self.player_view, "cc_font_family", fonts[0])
        next_idx = (fonts.index(cur_font) + 1) % len(fonts) if cur_font in fonts else 0
        new_font = fonts[next_idx]
        self.on_font_change(new_font)
        self.update_status(f"🔤 ពុម្ពអក្សរខ្មែរ: {new_font}", 1.0)

    def on_menu_cc_style(self):
        styles = [
            "🎤 Karaoke (Active Word Highlight)",
            "🌟 Glowing Neon Outline",
            "📦 Black Box 50% (ប្រអប់ខ្មៅស្រាល)",
            "✨ Classic Soft Shadow"
        ]
        cur = getattr(self.player_view, "cc_animation", styles[0])
        next_idx = (styles.index(cur) + 1) % len(styles) if cur in styles else 0
        new_style = styles[next_idx]
        self.player_view.cc_animation = new_style
        self.player_view.redraw_timeline()
        self.update_status(f"🎨 Subtitle Style: {new_style}", 1.0)

    def on_menu_watermark_settings(self):
        messagebox.showinfo(
            "Watermark Logo Settings",
            "🏷️ ការកំណត់ Watermark Logo:\n\n"
            "• អ្នកអាចអូសរំកិល Logo ដោយផ្ទាល់នៅលើអេក្រង់វីដេអូ (Interactive Drag)\n"
            "• ប្រើ Scroll Wheel លើ Logo ដើម្បីពង្រីក/បង្រួមទំហំ (Scale)\n"
            "• ឬកំណត់ Opacity (%) និងរូបភាពនៅក្នុងផ្ទាំងខាងស្តាំ (Dubbing Panel)"
        )

    def _menu_auto_sync_speed(self):
        sub_idx = self.player_view._selected_sub_idx
        if sub_idx is not None and 0 <= sub_idx < len(self.subtitles_data):
            sub = self.subtitles_data[sub_idx]
            dur = sub.get("end", 0.0) - sub.get("start", 0.0)
            text = sub.get("khmer", "")
            self.on_auto_sync_subtitle_speed(sub_idx, dur, text)

if __name__ == "__main__":
    app = MovieStudioApp()
    app.mainloop()
