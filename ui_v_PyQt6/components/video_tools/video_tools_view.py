"""
Video Tools & Shorts Studio Component for PyQt6 / PySide6 Desktop Studio
Features:
1. Video to Shorts Splitter (បំបែក Video ទៅជា Shorts):
   - By segment duration (30s, 60s, 90s, custom) or equal number of parts
   - Formatting options: Original aspect, 9:16 Vertical Crop (TikTok/Reels/Shorts), 9:16 Blurred Background
   - Lossless stream copy (-c copy) or hardware accelerated re-encode
2. Shorts to Long Video Merger (ផ្គុំ Shorts ទៅជា Long Video):
   - Add multiple clips, re-order, preview duration & size
   - Fast lossless concat demuxer or standardized 1080p re-encode
3. Audio & Video Splitter / Extractor (បំបែក MP3 ឬ MP4):
   - Extract MP3 (320k/192k/Copy) from MP4 video
   - Split MP3 audio into segments
   - Precision start-to-end trim/cut for video and audio
"""

import os
import sys
import re
import time
import subprocess
import threading
from typing import List, Dict, Optional, Callable

from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QProgressBar, QGroupBox, QFileDialog, QMessageBox, Qt, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QComboBox, QSpinBox,
    QTabWidget, QFrame, QCursor, QFont, QColor
)
from utils.media_utils import get_video_info
from utils.time_utils import format_timestamp, parse_timestamp_to_seconds
from ui_v_PyQt6.icons import get_play_icon, get_film_icon, get_folder_icon



def sanitize_filename(name: str) -> str:
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return clean[:60] if clean else "output"


class VideoToolsView(QWidget):
    """
    Video Tools & Shorts Studio:
    - Tab 1: Video to Shorts Splitter
    - Tab 2: Shorts to Long Video Merger
    - Tab 3: MP3 / MP4 Splitter & Audio Extractor
    """

    def __init__(
        self,
        parent=None,
        on_load_to_studio: Optional[Callable[[str], None]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__(parent)
        self.on_load_to_studio = on_load_to_studio
        self.log_callback = log_callback

        self.current_video_path: Optional[str] = None
        self.current_video_info: dict = {}
        self.is_processing = False
        self._cancel_flag = False
        self._current_process: Optional[subprocess.Popen] = None

        # Tab 2 Clips
        self.merge_clips: List[dict] = []

        self._init_ui()

    def _log(self, text: str):
        if self.log_callback:
            self.log_callback(text)

    def run_on_main(self, func):
        from ui_v_PyQt6.qt_compat import QTimer
        QTimer.singleShot(0, func)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)

        # ---------------- 1. HEADER CARD ----------------
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e2430, stop:1 #131720);
                border: 1px solid #2f3644;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        h_layout = QHBoxLayout(hdr_frame)
        h_layout.setContentsMargins(12, 6, 12, 6)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_h1 = QLabel("🎬 Video Tools & Shorts Studio (ឧបករណ៍កាត់ត បំបែក និងផ្គុំ វីដេអូ/សំឡេង)")
        lbl_h1.setStyleSheet("font-size: 15px; font-weight: 700; color: #38bdf8;")
        title_box.addWidget(lbl_h1)

        lbl_desc = QLabel("បំបែក Video ទៅជា Shorts 📱 | ផ្គុំ Shorts ទៅជា Long Video 🎞️ | បំបែក MP3 ឬ MP4 🎵 (FFmpeg Turbo)")
        lbl_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(lbl_desc)
        h_layout.addLayout(title_box)
        h_layout.addStretch()

        main_layout.addWidget(hdr_frame)

        # ---------------- 2. WORKSPACE SUB-TABS ----------------
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #2f3644;
                border-radius: 6px;
                background-color: #171b22;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #1f2530;
                color: #94a3b8;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                border: 1px solid #2f3644;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background-color: #262e3d;
                color: #e2e8f0;
            }
        """)

        # Tab 1: Video to Shorts Splitter
        self.tab_split_shorts = self._create_split_shorts_tab()
        self.sub_tabs.addTab(self.tab_split_shorts, "✂️ បំបែក Video ជា Shorts (Video to Shorts)")

        # Tab 2: Shorts to Long Video Merger
        self.tab_merge_shorts = self._create_merge_shorts_tab()
        self.sub_tabs.addTab(self.tab_merge_shorts, "🎞️ ផ្គុំ Shorts ជា Long Video (Shorts to Long)")

        # Tab 3: MP3 / MP4 Splitter & Extractor
        self.tab_audio_tools = self._create_audio_tools_tab()
        self.sub_tabs.addTab(self.tab_audio_tools, "🎵 បំបែក MP3 / MP4 & ដកស្រង់សំឡេង")

        main_layout.addWidget(self.sub_tabs, 1)

    # =========================================================================
    # TAB 1: VIDEO TO SHORTS SPLITTER
    # =========================================================================
    def _create_split_shorts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Source Video Selection
        grp_src = QGroupBox("📁 1. ជ្រើសរើស Video ដើម (Source Video)")
        g1_layout = QVBoxLayout(grp_src)
        g1_layout.setSpacing(8)

        row_f = QHBoxLayout()
        self.entry_v_path = QLineEdit()
        self.entry_v_path.setPlaceholderText("សូមជ្រើសរើស Video file (.mp4, .mkv, .mov, .ts, .avi)...")
        self.entry_v_path.textChanged.connect(self._on_source_video_changed)
        row_f.addWidget(self.entry_v_path, 1)

        btn_browse = QPushButton("📂 Browse Video...")
        btn_browse.setFixedWidth(130)
        btn_browse.clicked.connect(self._browse_source_video)
        row_f.addWidget(btn_browse)
        g1_layout.addLayout(row_f)

        self.lbl_v_info = QLabel("ℹ️ មិនទាន់បានជ្រើសរើស Video នៅឡើយទេ")
        self.lbl_v_info.setStyleSheet("font-size: 11px; color: #38bdf8; font-weight: 600;")
        g1_layout.addWidget(self.lbl_v_info)
        layout.addWidget(grp_src)

        # 2. Split Options & Shorts Formatting
        grp_opt = QGroupBox("⚙️ 2. កំណត់ការបំបែកជា Shorts (Split & Formatting Options)")
        g2_layout = QVBoxLayout(grp_opt)
        g2_layout.setSpacing(10)

        # Split By Mode
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("វិធីបំបែក (Split Mode):"))

        self.combo_split_mode = QComboBox()
        self.combo_split_mode.addItems([
            "⏱️ តាមរយៈពេលកំណត់ (By Segment Duration)",
            "🔢 តាមចំនួនភាគស្មើៗគ្នា (By Equal Parts)",
            "🎯 កាត់តាមចន្លោះជាក់លាក់ (Custom Range: Start -> End)"
        ])
        self.combo_split_mode.currentIndexChanged.connect(self._on_split_mode_changed)
        row_mode.addWidget(self.combo_split_mode, 1)
        g2_layout.addLayout(row_mode)

        # Duration Quick Presets
        self.frame_dur_presets = QFrame()
        p_layout = QHBoxLayout(self.frame_dur_presets)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(6)

        p_layout.addWidget(QLabel("រយៈពេលក្នុង 1 Short:"))
        self.spin_seg_dur = QSpinBox()
        self.spin_seg_dur.setRange(5, 7200)
        self.spin_seg_dur.setValue(60)
        self.spin_seg_dur.setSuffix(" វិនាទី (s)")
        self.spin_seg_dur.setFixedWidth(120)
        p_layout.addWidget(self.spin_seg_dur)

        # Quick preset buttons
        for s_val, s_lbl in [(30, "30s"), (60, "60s (Shorts)"), (90, "90s (Reels)"), (120, "2m"), (180, "3m"), (300, "5m")]:
            b = QPushButton(s_lbl)
            b.setFixedHeight(26)
            b.setStyleSheet("background-color: #222936; color: #cbd5e1; font-size: 11px; border: 1px solid #333d4e;")
            b.clicked.connect(lambda checked=False, v=s_val: self.spin_seg_dur.setValue(v))
            p_layout.addWidget(b)
        p_layout.addStretch()
        g2_layout.addWidget(self.frame_dur_presets)

        # Number of Parts
        self.frame_parts = QFrame()
        self.frame_parts.setVisible(False)
        pts_layout = QHBoxLayout(self.frame_parts)
        pts_layout.setContentsMargins(0, 0, 0, 0)
        pts_layout.setSpacing(8)
        pts_layout.addWidget(QLabel("ចំនួនភាគដែលចង់បំបែក (Number of Parts):"))
        self.spin_parts = QSpinBox()
        self.spin_parts.setRange(2, 100)
        self.spin_parts.setValue(5)
        self.spin_parts.setFixedWidth(100)
        pts_layout.addWidget(self.spin_parts)
        pts_layout.addStretch()
        g2_layout.addWidget(self.frame_parts)

        # Custom Time Range
        self.frame_custom_range = QFrame()
        self.frame_custom_range.setVisible(False)
        cr_layout = QHBoxLayout(self.frame_custom_range)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(8)
        cr_layout.addWidget(QLabel("Start Time (hh:mm:ss):"))
        self.entry_start_t = QLineEdit("00:00:00")
        self.entry_start_t.setFixedWidth(90)
        cr_layout.addWidget(self.entry_start_t)
        cr_layout.addWidget(QLabel("End Time (hh:mm:ss):"))
        self.entry_end_t = QLineEdit("00:01:00")
        self.entry_end_t.setFixedWidth(90)
        cr_layout.addWidget(self.entry_end_t)
        cr_layout.addStretch()
        g2_layout.addWidget(self.frame_custom_range)

        # Video Formatting Aspect for Shorts
        row_fmt = QHBoxLayout()
        row_fmt.addWidget(QLabel("ទម្រង់ Video Shorts (Format):"))
        self.combo_shorts_fmt = QComboBox()
        self.combo_shorts_fmt.addItems([
            "📺 រក្សាទម្រង់ដើម (Original Aspect - Lossless Stream Copy លឿនបំផុត)",
            "📱 9:16 Vertical Center Crop (កាត់កណ្តាលសម្រាប់ TikTok/Reels/Shorts 1080x1920)",
            "🖼️ 9:16 Blurred Background (ដាក់ផ្ទៃព្រាលសងខាង - មិនដាច់រូបភាពដើម)"
        ])
        row_fmt.addWidget(self.combo_shorts_fmt, 1)
        g2_layout.addLayout(row_fmt)

        # Output Folder & Prefix
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Save Folder:"))
        self.entry_out_dir = QLineEdit()
        self.entry_out_dir.setPlaceholderText("Output Directory...")
        row_out.addWidget(self.entry_out_dir, 1)
        btn_out_browse = QPushButton("📁 Browse...")
        btn_out_browse.clicked.connect(self._browse_split_out_dir)
        row_out.addWidget(btn_out_browse)

        row_out.addWidget(QLabel("Prefix:"))
        self.entry_prefix = QLineEdit("Short_Part")
        self.entry_prefix.setFixedWidth(110)
        row_out.addWidget(self.entry_prefix)
        g2_layout.addLayout(row_out)

        layout.addWidget(grp_opt)

        # 3. Execution & Progress
        row_act = QHBoxLayout()
        self.btn_start_split = QPushButton("🚀 ចាប់ផ្ដើមបំបែកវីដេអូជា Shorts (Start Split)")
        self.btn_start_split.setFixedHeight(36)
        self.btn_start_split.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                border: 1px solid #38bdf8;
            }
            QPushButton:hover {
                background: #0ea5e9;
            }
            QPushButton:disabled {
                background-color: #272d3a;
                color: #64748b;
                border-color: #374151;
            }
        """)
        self.btn_start_split.clicked.connect(self._start_split_shorts)
        row_act.addWidget(self.btn_start_split, 2)

        self.btn_stop_split = QPushButton("🛑 Stop")
        self.btn_stop_split.setFixedHeight(36)
        self.btn_stop_split.setEnabled(False)
        self.btn_stop_split.clicked.connect(self._stop_current_process)
        row_act.addWidget(self.btn_stop_split, 1)

        layout.addLayout(row_act)

        self.prog_split = QProgressBar()
        self.prog_split.setValue(0)
        self.prog_split.setFixedHeight(14)
        self.prog_split.setTextVisible(True)
        layout.addWidget(self.prog_split)

        # 4. Results Table
        self.tbl_split_results = QTableWidget()
        self.tbl_split_results.setColumnCount(5)
        self.tbl_split_results.setHorizontalHeaderLabels(["# ភាគ", "ឈ្មោះ File", "រយៈពេល", "ទំហំ", "សកម្មភាព (Actions)"])
        self.tbl_split_results.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_split_results.setColumnWidth(0, 60)
        self.tbl_split_results.setColumnWidth(2, 90)
        self.tbl_split_results.setColumnWidth(3, 85)
        self.tbl_split_results.setColumnWidth(4, 180)
        layout.addWidget(self.tbl_split_results, 1)

        return widget

    # =========================================================================
    # TAB 2: SHORTS TO LONG VIDEO MERGER
    # =========================================================================
    def _create_merge_shorts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Toolbar for adding/removing clips
        tb_layout = QHBoxLayout()
        btn_add_files = QPushButton("➕ បន្ថែម Videos (Add Files)...")
        btn_add_files.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px;")
        btn_add_files.clicked.connect(self._merge_add_files)
        tb_layout.addWidget(btn_add_files)

        btn_add_dir = QPushButton("📁 បន្ថែម Folder...")
        btn_add_dir.clicked.connect(self._merge_add_folder)
        tb_layout.addWidget(btn_add_dir)

        tb_layout.addSpacing(10)

        btn_up = QPushButton("⬆ ឡើងលើ (Up)")
        btn_up.clicked.connect(self._merge_move_up)
        tb_layout.addWidget(btn_up)

        btn_down = QPushButton("⬇ ចុះក្រោម (Down)")
        btn_down.clicked.connect(self._merge_move_down)
        tb_layout.addWidget(btn_down)

        btn_del = QPushButton("🗑️ ដកចេញ (Remove)")
        btn_del.clicked.connect(self._merge_remove_selected)
        tb_layout.addWidget(btn_del)

        btn_clear = QPushButton("🧹 Clear All")
        btn_clear.clicked.connect(self._merge_clear_all)
        tb_layout.addWidget(btn_clear)

        tb_layout.addStretch()
        layout.addLayout(tb_layout)

        # Table of video clips to merge
        self.tbl_merge = QTableWidget()
        self.tbl_merge.setColumnCount(5)
        self.tbl_merge.setHorizontalHeaderLabels(["#", "ឈ្មោះ File", "កម្រិតច្បាស់ (Resolution)", "រយៈពេល (Duration)", "ទំហំ"])
        self.tbl_merge.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tbl_merge.setColumnWidth(0, 45)
        self.tbl_merge.setColumnWidth(2, 160)
        self.tbl_merge.setColumnWidth(3, 120)
        self.tbl_merge.setColumnWidth(4, 90)
        layout.addWidget(self.tbl_merge, 1)

        # Summary Bar
        self.lbl_merge_summary = QLabel("📊 ចំនួន Clips: 0 | រយៈពេលសរុប: 00:00:00 | ទំហំប៉ាន់ស្មាន: 0 MB")
        self.lbl_merge_summary.setStyleSheet("font-size: 12px; font-weight: bold; color: #34d399;")
        layout.addWidget(self.lbl_merge_summary)

        # Merge Mode & Output
        grp_m_cfg = QGroupBox("⚙️ ការកំណត់ផ្គុំវីដេអូ (Merge Settings)")
        m_cfg_layout = QVBoxLayout(grp_m_cfg)

        row_m_mode = QHBoxLayout()
        row_m_mode.addWidget(QLabel("Merge Method:"))
        self.combo_merge_mode = QComboBox()
        self.combo_merge_mode.addItems([
            "⚡ Lossless Fast Concat (រហ័សបំផុត 0ms មិនបាច់ Encode ឡើងវិញ - សមស្របទំហំដូចគ្នា)",
            "🎬 Standardize & Normalize (កែសម្រួលទំហំ 1080p 30fps ឱ្យត្រូវគ្នាស្វ័យប្រវត្ត - មិនគាំង)"
        ])
        row_m_mode.addWidget(self.combo_merge_mode, 1)
        m_cfg_layout.addLayout(row_m_mode)

        row_m_out = QHBoxLayout()
        row_m_out.addWidget(QLabel("Output Long Video File:"))
        self.entry_merge_out = QLineEdit()
        self.entry_merge_out.setPlaceholderText("ជ្រើសរើសទីតាំងរក្សាទុក Video វែង...")
        row_m_out.addWidget(self.entry_merge_out, 1)
        btn_m_browse = QPushButton("📁 Browse...")
        btn_m_browse.clicked.connect(self._browse_merge_output)
        row_m_out.addWidget(btn_m_browse)
        m_cfg_layout.addLayout(row_m_out)
        layout.addWidget(grp_m_cfg)

        # Action Buttons
        row_m_act = QHBoxLayout()
        self.btn_start_merge = QPushButton("🚀 ផ្គុំវីដេអូទាំងអស់ជា Long Video (Merge All Clips)")
        self.btn_start_merge.setFixedHeight(36)
        self.btn_start_merge.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                border: 1px solid #34d399;
            }
            QPushButton:hover {
                background: #059669;
            }
            QPushButton:disabled {
                background-color: #272d3a;
                color: #64748b;
                border-color: #374151;
            }
        """)
        self.btn_start_merge.clicked.connect(self._start_merge_shorts)
        row_m_act.addWidget(self.btn_start_merge, 2)

        self.btn_stop_merge = QPushButton("🛑 Stop")
        self.btn_stop_merge.setFixedHeight(36)
        self.btn_stop_merge.setEnabled(False)
        self.btn_stop_merge.clicked.connect(self._stop_current_process)
        row_m_act.addWidget(self.btn_stop_merge, 1)

        layout.addLayout(row_m_act)

        self.prog_merge = QProgressBar()
        self.prog_merge.setValue(0)
        self.prog_merge.setFixedHeight(14)
        layout.addWidget(self.prog_merge)

        return widget

    # =========================================================================
    # TAB 3: AUDIO & VIDEO SPLITTER / EXTRACTOR (MP3 / MP4)
    # =========================================================================
    def _create_audio_tools_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Source Media File
        grp_src = QGroupBox("📁 1. ជ្រើសរើស File Media (Video MP4 ឬ Audio MP3/WAV)")
        s_layout = QVBoxLayout(grp_src)

        row_f = QHBoxLayout()
        self.entry_a_path = QLineEdit()
        self.entry_a_path.setPlaceholderText("សូមជ្រើសរើស Video ឬ Audio (.mp4, .mkv, .mp3, .wav, .m4a)...")
        row_f.addWidget(self.entry_a_path, 1)

        btn_browse = QPushButton("📂 Browse File...")
        btn_browse.clicked.connect(self._browse_audio_src)
        row_f.addWidget(btn_browse)
        s_layout.addLayout(row_f)

        self.lbl_a_info = QLabel("ℹ️ មិនទាន់ជ្រើសរើស File នៅឡើយទេ")
        self.lbl_a_info.setStyleSheet("font-size: 11px; color: #a855f7; font-weight: 600;")
        s_layout.addWidget(self.lbl_a_info)
        layout.addWidget(grp_src)

        # 2. Select Operation
        grp_op = QGroupBox("⚙️ 2. ជ្រើសរើសសកម្មភាព (Choose Operation)")
        op_layout = QVBoxLayout(grp_op)
        op_layout.setSpacing(10)

        row_task = QHBoxLayout()
        row_task.addWidget(QLabel("សកម្មភាពដែលត្រូវធ្វើ (Task):"))
        self.combo_audio_task = QComboBox()
        self.combo_audio_task.addItems([
            "🔊 ដកស្រង់សំឡេង MP3 ចេញពី MP4 Video (Extract MP3 Audio)",
            "✂️ បំបែក MP3 ឬ MP4 ជាកង់ៗ (Split by Duration)",
            "🎯 កាត់យកតែវគ្គជាក់លាក់ (Trim / Cut Range)"
        ])
        self.combo_audio_task.currentIndexChanged.connect(self._on_audio_task_changed)
        row_task.addWidget(self.combo_audio_task, 1)
        op_layout.addLayout(row_task)

        # Audio Extract Settings
        self.frame_extract_opt = QFrame()
        ex_layout = QHBoxLayout(self.frame_extract_opt)
        ex_layout.setContentsMargins(0, 0, 0, 0)
        ex_layout.addWidget(QLabel("Audio Quality / Format:"))
        self.combo_audio_quality = QComboBox()
        self.combo_audio_quality.addItems([
            "MP3 320 kbps (High Quality Studio)",
            "MP3 192 kbps (Standard)",
            "WAV 48kHz (Lossless Studio)",
            "AAC / M4A (Original Stream Copy)"
        ])
        ex_layout.addWidget(self.combo_audio_quality, 1)
        op_layout.addWidget(self.frame_extract_opt)

        # Audio Split Settings
        self.frame_audio_split_opt = QFrame()
        self.frame_audio_split_opt.setVisible(False)
        as_layout = QHBoxLayout(self.frame_audio_split_opt)
        as_layout.setContentsMargins(0, 0, 0, 0)
        as_layout.addWidget(QLabel("បំបែករៀងរាល់ (Split every):"))
        self.spin_audio_seg_dur = QSpinBox()
        self.spin_audio_seg_dur.setRange(10, 7200)
        self.spin_audio_seg_dur.setValue(300)  # 5 mins
        self.spin_audio_seg_dur.setSuffix(" វិនាទី (s)")
        as_layout.addWidget(self.spin_audio_seg_dur)

        for s_val, s_lbl in [(60, "1m"), (180, "3m"), (300, "5m"), (600, "10m")]:
            b = QPushButton(s_lbl)
            b.setFixedHeight(24)
            b.clicked.connect(lambda checked=False, v=s_val: self.spin_audio_seg_dur.setValue(v))
            as_layout.addWidget(b)
        as_layout.addStretch()
        op_layout.addWidget(self.frame_audio_split_opt)

        # Audio Trim Settings
        self.frame_audio_trim_opt = QFrame()
        self.frame_audio_trim_opt.setVisible(False)
        at_layout = QHBoxLayout(self.frame_audio_trim_opt)
        at_layout.setContentsMargins(0, 0, 0, 0)
        at_layout.addWidget(QLabel("Start Time:"))
        self.entry_a_start = QLineEdit("00:00:00")
        self.entry_a_start.setFixedWidth(90)
        at_layout.addWidget(self.entry_a_start)
        at_layout.addWidget(QLabel("End Time:"))
        self.entry_a_end = QLineEdit("00:02:00")
        self.entry_a_end.setFixedWidth(90)
        at_layout.addWidget(self.entry_a_end)
        at_layout.addStretch()
        op_layout.addWidget(self.frame_audio_trim_opt)

        layout.addWidget(grp_op)

        # 3. Action Button & Progress
        row_act = QHBoxLayout()
        self.btn_start_audio_op = QPushButton("🚀 ចាប់ផ្ដើមដំណើរការ (Start Process)")
        self.btn_start_audio_op.setFixedHeight(36)
        self.btn_start_audio_op.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6d28d9);
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                border-radius: 6px;
                border: 1px solid #a78bfa;
            }
            QPushButton:hover {
                background: #7c3aed;
            }
        """)
        self.btn_start_audio_op.clicked.connect(self._start_audio_operation)
        row_act.addWidget(self.btn_start_audio_op, 2)

        self.btn_stop_audio_op = QPushButton("🛑 Stop")
        self.btn_stop_audio_op.setFixedHeight(36)
        self.btn_stop_audio_op.setEnabled(False)
        self.btn_stop_audio_op.clicked.connect(self._stop_current_process)
        row_act.addWidget(self.btn_stop_audio_op, 1)

        layout.addLayout(row_act)

        self.prog_audio = QProgressBar()
        self.prog_audio.setValue(0)
        self.prog_audio.setFixedHeight(14)
        layout.addWidget(self.prog_audio)

        # Output Results Label / View
        self.lbl_audio_res = QLabel("📋 លទ្ធផលនឹងបង្ហាញនៅទីនេះ...")
        self.lbl_audio_res.setStyleSheet("font-size: 12px; color: #94a3b8; padding: 6px; background-color: #1a202c; border: 1px solid #2d3748; border-radius: 4px;")
        layout.addWidget(self.lbl_audio_res)
        layout.addStretch()

        return widget

    # =========================================================================
    # TAB 1 LOGIC: VIDEO TO SHORTS
    # =========================================================================
    def _browse_source_video(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Video File", "", "Videos (*.mp4 *.mkv *.mov *.ts *.avi *.webm)")
        if f:
            self.entry_v_path.setText(f)

    def _browse_split_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.entry_out_dir.text() or "")
        if d:
            self.entry_out_dir.setText(d)

    def _on_source_video_changed(self, path: str):
        path = path.strip()
        if not path or not os.path.exists(path):
            self.current_video_path = None
            self.current_video_info = {}
            self.lbl_v_info.setText("ℹ️ មិនទាន់បានជ្រើសរើស Video នៅឡើយទេ")
            return

        self.current_video_path = path
        info = get_video_info(path)
        self.current_video_info = info
        dur = info.get("duration", 0.0)
        w = info.get("width", 0)
        h = info.get("height", 0)
        fps = info.get("fps", 0.0)
        sz_mb = (info.get("size", 0) or os.path.getsize(path)) / (1024 * 1024)

        dur_str = format_timestamp(dur)
        self.lbl_v_info.setText(
            f"🎬 Video: {os.path.basename(path)} | រយៈពេល: {dur_str} ({dur:.1f}s) | "
            f"ទំហំ: {w}x{h} ({fps:.1f} FPS) | {sz_mb:.1f} MB"
        )

        # Auto set output dir next to video if empty
        if not self.entry_out_dir.text().strip():
            v_dir = os.path.dirname(path)
            shorts_dir = os.path.join(v_dir, f"{os.path.splitext(os.path.basename(path))[0]}_shorts")
            self.entry_out_dir.setText(shorts_dir)

    def _on_split_mode_changed(self, idx: int):
        self.frame_dur_presets.setVisible(idx == 0)
        self.frame_parts.setVisible(idx == 1)
        self.frame_custom_range.setVisible(idx == 2)

    def _start_split_shorts(self):
        video_path = self.entry_v_path.text().strip()
        if not video_path or not os.path.exists(video_path):
            QMessageBox.warning(self, "No Video", "សូមជ្រើសរើស Video file ជាមុនសិន!")
            return

        out_dir = self.entry_out_dir.text().strip()
        if not out_dir:
            out_dir = os.path.join(os.path.dirname(video_path), "shorts_output")
            self.entry_out_dir.setText(out_dir)
        os.makedirs(out_dir, exist_ok=True)

        info = self.current_video_info or get_video_info(video_path)
        total_dur = info.get("duration", 0.0)
        if total_dur <= 0:
            QMessageBox.warning(self, "Invalid Video", "មិនអាចអានរយៈពេលរបស់ Video បានឡើយ!")
            return

        mode_idx = self.combo_split_mode.currentIndex()
        fmt_idx = self.combo_shorts_fmt.currentIndex()
        prefix = sanitize_filename(self.entry_prefix.text().strip()) or "Short_Part"

        # Calculate segments: [(start, dur, out_name)]
        segments = []
        if mode_idx == 0:
            seg_len = float(self.spin_seg_dur.value())
            curr = 0.0
            p = 1
            while curr < total_dur:
                d = min(seg_len, total_dur - curr)
                if d < 1.0:
                    break
                out_name = f"{prefix}_{p:02d}.mp4"
                segments.append((curr, d, out_name))
                curr += seg_len
                p += 1
        elif mode_idx == 1:
            num_parts = self.spin_parts.value()
            part_len = total_dur / num_parts
            for p in range(1, num_parts + 1):
                st = (p - 1) * part_len
                d = part_len if p < num_parts else (total_dur - st)
                out_name = f"{prefix}_{p:02d}.mp4"
                segments.append((st, d, out_name))
        else:
            st = parse_timestamp_to_seconds(self.entry_start_t.text().strip())
            et = parse_timestamp_to_seconds(self.entry_end_t.text().strip())
            if et <= st:
                QMessageBox.warning(self, "Time Error", "End Time ត្រូវតែធំជាង Start Time!")
                return
            segments.append((st, et - st, f"{prefix}_custom.mp4"))

        if not segments:
            QMessageBox.warning(self, "Error", "គ្មាន Segment ណាដែលត្រូវបំបែកឡើយ!")
            return

        self.is_processing = True
        self._cancel_flag = False
        self.btn_start_split.setEnabled(False)
        self.btn_stop_split.setEnabled(True)
        self.prog_split.setValue(0)
        self.tbl_split_results.setRowCount(0)

        self._log(f"✂️ [Shorts Splitter] ចាប់ផ្ដើមបំបែក {len(segments)} Shorts ចូលក្នុង: {out_dir}")

        def worker():
            created_files = []
            total_segs = len(segments)

            for idx, (st, seg_d, out_fn) in enumerate(segments):
                if self._cancel_flag:
                    break

                out_path = os.path.join(out_dir, out_fn)

                # Build ffmpeg command based on format mode
                # Mode 0: Original aspect (Fast -c copy)
                # Mode 1: 9:16 Vertical Center Crop
                # Mode 2: 9:16 Blurred Background
                if fmt_idx == 0:
                    cmd = [
                        "ffmpeg", "-y", "-ss", f"{st:.3f}", "-i", video_path,
                        "-t", f"{seg_d:.3f}", "-c", "copy", "-avoid_negative_ts", "make_zero",
                        out_path
                    ]
                elif fmt_idx == 1:
                    # 9:16 Center crop: crop=ih*9/16:ih:(iw-ih*9/16)/2:0, scale=1080:1920
                    crop_filter = "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920"
                    cmd = [
                        "ffmpeg", "-y", "-ss", f"{st:.3f}", "-i", video_path,
                        "-t", f"{seg_d:.3f}", "-vf", crop_filter,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                        "-c:a", "aac", "-b:a", "192k",
                        out_path
                    ]
                else:
                    # 9:16 Blurred background: scale background to 1080:1920 with boxblur, overlay scaled original
                    vf = (
                        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,boxblur=20:20[bg];"
                        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
                    )
                    cmd = [
                        "ffmpeg", "-y", "-ss", f"{st:.3f}", "-i", video_path,
                        "-t", f"{seg_d:.3f}", "-filter_complex", vf,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                        "-c:a", "aac", "-b:a", "192k",
                        out_path
                    ]

                try:
                    self._current_process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                    )
                    self._current_process.wait()

                    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                        sz_mb = os.path.getsize(out_path) / (1024 * 1024)
                        created_files.append((idx + 1, out_fn, seg_d, sz_mb, out_path))
                        self.run_on_main(lambda item=created_files[-1]: self._add_split_result_row(item))
                except Exception as ex:
                    self._log(f"⚠️ [Error] បរាជ័យក្នុងភាគ {out_fn}: {ex}")

                pct = int(((idx + 1) / total_segs) * 100)
                self.run_on_main(lambda p=pct: self.prog_split.setValue(p))

            self.run_on_main(lambda: self._finish_split(created_files, out_dir))

        threading.Thread(target=worker, daemon=True).start()

    def _add_split_result_row(self, item):
        part_no, out_fn, dur_s, sz_mb, out_path = item
        row = self.tbl_split_results.rowCount()
        self.tbl_split_results.insertRow(row)

        it_p = QTableWidgetItem(f"Part {part_no}")
        it_p.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tbl_split_results.setItem(row, 0, it_p)

        it_fn = QTableWidgetItem(out_fn)
        self.tbl_split_results.setItem(row, 1, it_fn)

        it_d = QTableWidgetItem(f"{dur_s:.1f}s")
        it_d.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tbl_split_results.setItem(row, 2, it_d)

        it_sz = QTableWidgetItem(f"{sz_mb:.1f} MB")
        it_sz.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tbl_split_results.setItem(row, 3, it_sz)

        # Action Buttons container
        act_widget = QWidget()
        act_layout = QHBoxLayout(act_widget)
        act_layout.setContentsMargins(2, 2, 2, 2)
        act_layout.setSpacing(4)

        btn_play = QPushButton(" Play")
        btn_play.setIcon(get_play_icon(size=12, color="#ffffff"))
        btn_play.setFixedHeight(22)
        btn_play.setStyleSheet("background-color: #0369a1; color: white; font-size: 10px; font-weight: bold; padding: 2px 6px;")
        btn_play.clicked.connect(lambda checked=False, p=out_path: os.startfile(p) if os.path.exists(p) else None)
        act_layout.addWidget(btn_play)

        btn_studio = QPushButton(" Studio")
        btn_studio.setIcon(get_film_icon(size=12, color="#ffffff"))
        btn_studio.setFixedHeight(22)
        btn_studio.setStyleSheet("background-color: #059669; color: white; font-size: 10px; font-weight: bold; padding: 2px 6px;")
        if self.on_load_to_studio:
            btn_studio.clicked.connect(lambda checked=False, p=out_path: self.on_load_to_studio(p))
        act_layout.addWidget(btn_studio)

        btn_dir = QPushButton(" Folder")
        btn_dir.setIcon(get_folder_icon(size=12, color="#fcd34d"))
        btn_dir.setFixedHeight(22)
        btn_dir.setStyleSheet("background-color: #374151; color: #cbd5e1; font-size: 10px; padding: 2px 6px;")
        btn_dir.clicked.connect(lambda checked=False, d=os.path.dirname(out_path): os.startfile(d))
        act_layout.addWidget(btn_dir)

        self.tbl_split_results.setCellWidget(row, 4, act_widget)

    def _finish_split(self, created_files, out_dir):
        self.is_processing = False
        self.btn_start_split.setEnabled(True)
        self.btn_stop_split.setEnabled(False)
        self.prog_split.setValue(100)

        if self._cancel_flag:
            self._log(f"🛑 [Shorts Splitter] ការបំបែកត្រូវបានបញ្ឈប់ដោយអ្នកប្រើប្រាស់! បានបង្កើត {len(created_files)} ភាគ។")
            QMessageBox.information(self, "Stopped", f"បានបញ្ឈប់! បង្កើតបាន {len(created_files)} Shorts។")
        else:
            self._log(f"🎉 [Shorts Splitter] បានបំបែកជោគជ័យសរុប {len(created_files)} Shorts ក្នុង: {out_dir}")
            QMessageBox.information(self, "Success", f"🎉 បានបំបែកជា Shorts ចំនួន {len(created_files)} ដោយជោគជ័យ!\n\nFolder: {out_dir}")

    # =========================================================================
    # TAB 2 LOGIC: SHORTS TO LONG VIDEO MERGER
    # =========================================================================
    def _merge_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Video Clips to Merge", "", "Videos (*.mp4 *.mkv *.mov *.ts *.avi)")
        if files:
            for f in files:
                self._add_merge_clip(f)
            self._refresh_merge_table()

    def _merge_add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select Folder with Videos")
        if d:
            valid_exts = {".mp4", ".mkv", ".mov", ".ts", ".avi"}
            f_list = sorted([
                os.path.join(d, fn) for fn in os.listdir(d)
                if os.path.splitext(fn)[1].lower() in valid_exts
            ])
            for f in f_list:
                self._add_merge_clip(f)
            self._refresh_merge_table()

    def _add_merge_clip(self, fpath: str):
        if not os.path.exists(fpath):
            return
        info = get_video_info(fpath)
        sz_mb = os.path.getsize(fpath) / (1024 * 1024)
        self.merge_clips.append({
            "path": fpath,
            "filename": os.path.basename(fpath),
            "duration": info.get("duration", 0.0),
            "width": info.get("width", 1920),
            "height": info.get("height", 1080),
            "fps": info.get("fps", 30.0),
            "size_mb": sz_mb
        })

    def _merge_move_up(self):
        row = self.tbl_merge.currentRow()
        if row > 0:
            self.merge_clips[row], self.merge_clips[row - 1] = self.merge_clips[row - 1], self.merge_clips[row]
            self._refresh_merge_table()
            self.tbl_merge.setCurrentCell(row - 1, 1)

    def _merge_move_down(self):
        row = self.tbl_merge.currentRow()
        if 0 <= row < len(self.merge_clips) - 1:
            self.merge_clips[row], self.merge_clips[row + 1] = self.merge_clips[row + 1], self.merge_clips[row]
            self._refresh_merge_table()
            self.tbl_merge.setCurrentCell(row + 1, 1)

    def _merge_remove_selected(self):
        row = self.tbl_merge.currentRow()
        if 0 <= row < len(self.merge_clips):
            del self.merge_clips[row]
            self._refresh_merge_table()

    def _merge_clear_all(self):
        self.merge_clips.clear()
        self._refresh_merge_table()

    def _refresh_merge_table(self):
        self.tbl_merge.setRowCount(0)
        tot_dur = 0.0
        tot_sz = 0.0

        for idx, clip in enumerate(self.merge_clips):
            row = self.tbl_merge.rowCount()
            self.tbl_merge.insertRow(row)

            tot_dur += clip["duration"]
            tot_sz += clip["size_mb"]

            it_idx = QTableWidgetItem(str(idx + 1))
            it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_merge.setItem(row, 0, it_idx)

            it_fn = QTableWidgetItem(clip["filename"])
            self.tbl_merge.setItem(row, 1, it_fn)

            res_str = f"{clip['width']}x{clip['height']} ({clip['fps']:.1f}fps)"
            it_res = QTableWidgetItem(res_str)
            it_res.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_merge.setItem(row, 2, it_res)

            it_dur = QTableWidgetItem(format_timestamp(clip["duration"]))
            it_dur.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_merge.setItem(row, 3, it_dur)

            it_sz = QTableWidgetItem(f"{clip['size_mb']:.1f} MB")
            it_sz.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tbl_merge.setItem(row, 4, it_sz)

        self.lbl_merge_summary.setText(
            f"📊 ចំនួន Clips: {len(self.merge_clips)} | រយៈពេលសរុប: {format_timestamp(tot_dur)} | ទំហំប៉ាន់ស្មាន: {tot_sz:.1f} MB"
        )

        # Suggest default output filename if empty
        if not self.entry_merge_out.text().strip() and self.merge_clips:
            first_dir = os.path.dirname(self.merge_clips[0]["path"])
            out_f = os.path.join(first_dir, "merged_long_video.mp4")
            self.entry_merge_out.setText(out_f)

    def _browse_merge_output(self):
        f, _ = QFileDialog.getSaveFileName(self, "Save Merged Long Video", self.entry_merge_out.text() or "merged_long_video.mp4", "Video (*.mp4)")
        if f:
            self.entry_merge_out.setText(f)

    def _start_merge_shorts(self):
        if len(self.merge_clips) < 2:
            QMessageBox.warning(self, "Not Enough Clips", "សូមបន្ថែមវីដេអូយ៉ាងហោចណាស់ ២ Clips ដើម្បីផ្គុំ!")
            return

        out_path = self.entry_merge_out.text().strip()
        if not out_path:
            QMessageBox.warning(self, "No Output", "សូមកំណត់ទីតាំងរក្សាទុក Video!")
            return
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        mode_idx = self.combo_merge_mode.currentIndex()
        self.is_processing = True
        self._cancel_flag = False
        self.btn_start_merge.setEnabled(False)
        self.btn_stop_merge.setEnabled(True)
        self.prog_merge.setValue(10)

        self._log(f"🎞️ [Merger] ចាប់ផ្ដើមផ្គុំ {len(self.merge_clips)} Clips ចូលទៅកាន់: {os.path.basename(out_path)}")

        def worker():
            try:
                # Mode 0: Fast Concat Demuxer
                if mode_idx == 0:
                    concat_txt = os.path.join(os.path.dirname(out_path), "_temp_concat_list.txt")
                    with open(concat_txt, "w", encoding="utf-8") as f:
                        for c in self.merge_clips:
                            # Escape single quotes in path for ffmpeg
                            p_clean = c["path"].replace("'", "'\\''")
                            f.write(f"file '{p_clean}'\n")

                    cmd = [
                        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                        "-i", concat_txt, "-c", "copy", out_path
                    ]
                    self._current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._current_process.wait()

                    try:
                        os.remove(concat_txt)
                    except Exception:
                        pass
                else:
                    # Mode 1: Standardize and Encode to 1080p 30fps
                    # Construct filter_complex with scale and pad
                    inputs = []
                    filter_parts = []
                    for i, c in enumerate(self.merge_clips):
                        inputs.extend(["-i", c["path"]])
                        filter_parts.append(
                            f"[{i}:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}];"
                            f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{i}];"
                        )
                    concat_v = "".join([f"[v{i}][a{i}]" for i in range(len(self.merge_clips))])
                    filter_complex = "".join(filter_parts) + f"{concat_v}concat=n={len(self.merge_clips)}:v=1:a=1[v][a]"

                    cmd = [
                        "ffmpeg", "-y", *inputs,
                        "-filter_complex", filter_complex,
                        "-map", "[v]", "-map", "[a]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                        "-c:a", "aac", "-b:a", "192k",
                        out_path
                    ]
                    self._current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._current_process.wait()

                ok = os.path.exists(out_path) and os.path.getsize(out_path) > 1000
                self.run_on_main(lambda: self._finish_merge(ok, out_path))

            except Exception as ex:
                self._log(f"❌ [Merger] ការផ្គុំបរាជ័យ: {ex}")
                self.run_on_main(lambda: self._finish_merge(False, out_path, str(ex)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_merge(self, success: bool, out_path: str, err_msg: str = ""):
        self.is_processing = False
        self.btn_start_merge.setEnabled(True)
        self.btn_stop_merge.setEnabled(False)
        self.prog_merge.setValue(100 if success else 0)

        if success:
            sz_mb = os.path.getsize(out_path) / (1024 * 1024)
            self._log(f"🎉 [Merger] ផ្គុំវីដេអូបានជោគជ័យ! -> {os.path.basename(out_path)} ({sz_mb:.1f} MB)")
            res = QMessageBox.question(
                self,
                "Merge Success",
                f"🎉 ផ្គុំវីដេអូជា Long Video បានជោគជ័យ!\n\nFile: {out_path} ({sz_mb:.1f} MB)\n\nតើអ្នកចង់បើកចូល Movie Studio ឥឡូវនេះទេ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if res == QMessageBox.StandardButton.Yes and self.on_load_to_studio:
                self.on_load_to_studio(out_path)
        else:
            self._log(f"❌ [Merger] ការផ្គុំវីដេអូបរាជ័យ {err_msg}")
            QMessageBox.critical(self, "Merge Failed", f"ការផ្គុំវីដេអូបរាជ័យ:\n{err_msg}\n\nសូមសាកល្បងជ្រើសរើស Method ទី 2 (Standardize & Normalize)!")

    # =========================================================================
    # TAB 3 LOGIC: AUDIO & VIDEO SPLITTER / EXTRACTOR
    # =========================================================================
    def _browse_audio_src(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Media File", "", "Media Files (*.mp4 *.mkv *.mov *.mp3 *.wav *.m4a *.aac *.flac *.ts)")
        if f:
            self.entry_a_path.setText(f)
            sz_mb = os.path.getsize(f) / (1024 * 1024)
            info = get_video_info(f)
            dur_str = format_timestamp(info.get("duration", 0.0))
            self.lbl_a_info.setText(f"🎵 Media: {os.path.basename(f)} | {dur_str} | {sz_mb:.1f} MB")

    def _on_audio_task_changed(self, idx: int):
        self.frame_extract_opt.setVisible(idx == 0)
        self.frame_audio_split_opt.setVisible(idx == 1)
        self.frame_audio_trim_opt.setVisible(idx == 2)

    def _start_audio_operation(self):
        src_path = self.entry_a_path.text().strip()
        if not src_path or not os.path.exists(src_path):
            QMessageBox.warning(self, "No File", "សូមជ្រើសរើស File Media ជាមុនសិន!")
            return

        task_idx = self.combo_audio_task.currentIndex()
        v_dir = os.path.dirname(src_path)
        base_name, _ = os.path.splitext(os.path.basename(src_path))

        self.is_processing = True
        self._cancel_flag = False
        self.btn_start_audio_op.setEnabled(False)
        self.btn_stop_audio_op.setEnabled(True)
        self.prog_audio.setValue(15)

        def worker():
            try:
                # Task 0: Extract Audio
                if task_idx == 0:
                    q_idx = self.combo_audio_quality.currentIndex()
                    if q_idx == 0:
                        out_path = os.path.join(v_dir, f"{base_name}_audio_320k.mp3")
                        cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-c:a", "libmp3lame", "-b:a", "320k", out_path]
                    elif q_idx == 1:
                        out_path = os.path.join(v_dir, f"{base_name}_audio_192k.mp3")
                        cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-c:a", "libmp3lame", "-b:a", "192k", out_path]
                    elif q_idx == 2:
                        out_path = os.path.join(v_dir, f"{base_name}_audio_48k.wav")
                        cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-c:a", "pcm_s16le", "-ar", "48000", out_path]
                    else:
                        out_path = os.path.join(v_dir, f"{base_name}_audio_stream.m4a")
                        cmd = ["ffmpeg", "-y", "-i", src_path, "-vn", "-c:a", "copy", out_path]

                    self._log(f"🔊 [Audio Tool] កំពុងដកស្រង់សំឡេងចេញពី: {os.path.basename(src_path)}...")
                    self._current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._current_process.wait()

                    ok = os.path.exists(out_path) and os.path.getsize(out_path) > 100
                    self.run_on_main(lambda: self._finish_audio_task(ok, out_path, "ដកស្រង់សំឡេងបានជោគជ័យ!"))

                # Task 1: Split Audio into Segments
                elif task_idx == 1:
                    seg_len = self.spin_audio_seg_dur.value()
                    out_sub_dir = os.path.join(v_dir, f"{base_name}_audio_parts")
                    os.makedirs(out_sub_dir, exist_ok=True)
                    out_pattern = os.path.join(out_sub_dir, f"{base_name}_part_%03d.mp3")

                    cmd = [
                        "ffmpeg", "-y", "-i", src_path, "-vn",
                        "-f", "segment", "-segment_time", str(seg_len),
                        "-c:a", "libmp3lame", "-b:a", "192k", out_pattern
                    ]
                    self._log(f"✂️ [Audio Tool] កំពុងបំបែកជាកង់ៗរៀងរាល់ {seg_len}s...")
                    self._current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._current_process.wait()

                    self.run_on_main(lambda: self._finish_audio_task(True, out_sub_dir, "បំបែក Audio ជាកង់ៗជោគជ័យ!"))

                # Task 2: Trim / Cut Range
                else:
                    st_str = self.entry_a_start.text().strip()
                    et_str = self.entry_a_end.text().strip()
                    st = parse_timestamp_to_seconds(st_str)
                    et = parse_timestamp_to_seconds(et_str)
                    dur = max(0.5, et - st)

                    _, ext = os.path.splitext(src_path)
                    out_path = os.path.join(v_dir, f"{base_name}_trim_{st_str.replace(':', '-')}_to_{et_str.replace(':', '-')}{ext}")

                    cmd = [
                        "ffmpeg", "-y", "-ss", f"{st:.3f}", "-i", src_path,
                        "-t", f"{dur:.3f}", "-c", "copy", out_path
                    ]
                    self._log(f"🎯 [Audio Tool] កំពុងកាត់យកចន្លោះ {st_str} -> {et_str}...")
                    self._current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    self._current_process.wait()

                    ok = os.path.exists(out_path) and os.path.getsize(out_path) > 100
                    self.run_on_main(lambda: self._finish_audio_task(ok, out_path, "កាត់យកវគ្គដែលចង់បានជោគជ័យ!"))

            except Exception as ex:
                self._log(f"❌ [Audio Tool] បរាជ័យ: {ex}")
                self.run_on_main(lambda: self._finish_audio_task(False, "", str(ex)))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_audio_task(self, success: bool, out_target: str, msg: str = ""):
        self.is_processing = False
        self.btn_start_audio_op.setEnabled(True)
        self.btn_stop_audio_op.setEnabled(False)
        self.prog_audio.setValue(100 if success else 0)

        if success:
            self.lbl_audio_res.setText(f"✅ {msg}\n📁 ទីតាំង: {out_target}")
            self._log(f"🎉 [Audio Tool] {msg} -> {out_target}")
            res = QMessageBox.question(
                self,
                "Success",
                f"🎉 {msg}\n\nទីតាំង: {out_target}\n\nតើអ្នកចង់បើកទីតាំង Folder ឥឡូវនេះទេ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if res == QMessageBox.StandardButton.Yes:
                d = out_target if os.path.isdir(out_target) else os.path.dirname(out_target)
                os.startfile(d)
        else:
            self.lbl_audio_res.setText(f"❌ បរាជ័យ: {msg}")
            QMessageBox.critical(self, "Error", f"ដំណើរការបរាជ័យ: {msg}")

    def _stop_current_process(self):
        self._cancel_flag = True
        if self._current_process and self._current_process.poll() is None:
            try:
                self._current_process.terminate()
                self._log("🛑 [Process] បានបញ្ជូនសញ្ញាបញ្ឈប់...")
            except Exception:
                pass
        self.btn_stop_split.setEnabled(False)
        self.btn_stop_merge.setEnabled(False)
        self.btn_stop_audio_op.setEnabled(False)
