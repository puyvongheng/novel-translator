"""
SRT Splitter & AI Dialogue Chunker View Component for PyQt6 / PySide6 Studio
Splits large SRT subtitle files (e.g. 6,000 cues) into balanced chunks (e.g. 2,000 cues each)
for easy translation with AI models (Gemini, ChatGPT, Claude), and merges them back seamlessly.
"""

import os
import sys
import subprocess
from typing import List, Dict, Optional, Callable

from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QProgressBar, QGroupBox, QFileDialog, QMessageBox, Qt, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QComboBox, QSpinBox,
    QApplication, QTabWidget, QFrame, QCursor
)
from utils.srt_utils import (
    parse_raw_srt_blocks,
    split_srt_file,
    merge_srt_files,
    parse_srt_file,
    generate_srt_content,
    format_timestamp
)


class SrtSplitterView(QWidget):
    """
    SRT Splitter & Merger Tool for AI Movie Translation:
    - Splits large SRT files (e.g. 6,000 cues) into 2,000-cue parts for AI prompts
    - Preserves exact millisecond timestamps and multi-line dialogue
    - Real-time chunk preview & calculation
    - One-click AI prompt generator for ChatGPT / Gemini
    - Built-in multi-part SRT merger to assemble translated chunks back together
    - Direct integration with Movie Studio timeline
    """

    def __init__(
        self,
        parent=None,
        on_load_to_studio: Optional[Callable[[str], None]] = None,
        get_studio_subtitles: Optional[Callable[[], List[Dict]]] = None,
        log_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__(parent)
        self.on_load_to_studio = on_load_to_studio
        self.get_studio_subtitles = get_studio_subtitles
        self.log_callback = log_callback

        self.current_srt_path: Optional[str] = None
        self.current_cues: List[Dict] = []
        self.generated_split_files: List[Dict] = []
        self.merge_file_list: List[str] = []

        self._init_ui()

    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # Header Title
        title_box = QHBoxLayout()
        title_box.setSpacing(10)

        lbl_icon = QLabel("✂️")
        lbl_icon.setStyleSheet("font-size: 22px;")
        title_box.addWidget(lbl_icon)

        title_info = QVBoxLayout()
        title_info.setSpacing(2)
        lbl_title = QLabel("ឧបករណ៍បំបែក និងបញ្ចូល SRT សម្រាប់ AI (SRT Splitter & Merger)")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        lbl_desc = QLabel("បំបែកឯកសារ SRT ធំៗ (ឧ. 6,000 CC ➔ 2,000 ក្នុង ១ file) ងាយស្រួលផ្ញើឲ្យ AI (Gemini / ChatGPT) បកប្រែ ហើយអាចបញ្ចូលមកវិញបានភ្លាមៗ")
        lbl_desc.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_info.addWidget(lbl_title)
        title_info.addWidget(lbl_desc)

        title_box.addLayout(title_info)
        title_box.addStretch()
        main_layout.addLayout(title_box)

        # Main Sub-Tabs (Splitter vs Merger)
        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #1e222b;
                border-radius: 6px;
                padding: 10px;
            }
            QTabBar::tab {
                background: #252c38;
                color: #94a3b8;
                padding: 7px 18px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 3px;
                font-weight: bold;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #0284c7;
                color: #ffffff;
            }
            QTabBar::tab:hover:!selected {
                background: #334155;
                color: #f1f5f9;
            }
        """)

        tab_split = self._create_split_tab()
        self.sub_tabs.addTab(tab_split, "✂️ បំបែក SRT ជាចំណែកៗ (Split SRT)")

        tab_merge = self._create_merge_tab()
        self.sub_tabs.addTab(tab_merge, "🔗 បញ្ចូល SRT ចូលគ្នាវិញ (Merge SRTs)")

        main_layout.addWidget(self.sub_tabs, 1)

    # =========================================================================
    # TAB 1: SPLIT SRT
    # =========================================================================
    def _create_split_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        # 1. Source SRT File Selection Card
        grp_source = QGroupBox("📁 ជ្រើសរើសឯកសារ SRT ដើម (Source Subtitle File)")
        grp_source.setStyleSheet(self._group_box_style())
        g_layout = QVBoxLayout(grp_source)
        g_layout.setContentsMargins(10, 12, 10, 10)
        g_layout.setSpacing(8)

        file_row = QHBoxLayout()
        file_row.setSpacing(8)

        self.edit_source_path = QLineEdit()
        self.edit_source_path.setPlaceholderText("ជ្រើសរើសឯកសារ .srt ដែលមានឃ្លាច្រើន (ឧ. 6000 CC)...")
        self.edit_source_path.setReadOnly(True)
        self.edit_source_path.setStyleSheet(self._input_style())
        file_row.addWidget(self.edit_source_path, 1)

        btn_browse = QPushButton("📂 ជ្រើសរើស SRT...")
        btn_browse.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse.setStyleSheet(self._btn_primary_style())
        btn_browse.clicked.connect(self._on_browse_source_srt)
        file_row.addWidget(btn_browse)

        btn_load_studio = QPushButton("📥 យកពី Movie Studio")
        btn_load_studio.setToolTip("យក Subtitles ដែលកំពុងបើកក្នុងផ្ទាំង Movie Studio មកបំបែកភ្លាមៗ")
        btn_load_studio.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_load_studio.setStyleSheet(self._btn_secondary_style())
        btn_load_studio.clicked.connect(self._on_load_from_studio)
        file_row.addWidget(btn_load_studio)

        g_layout.addLayout(file_row)

        # File Stats Row (Cues count, Duration, etc.)
        self.stats_row = QHBoxLayout()
        self.stats_row.setSpacing(12)

        self.badge_count = QLabel("🔢 ចំនួនឃ្លាសរុប: --")
        self.badge_count.setStyleSheet(self._badge_style("#38bdf8"))
        self.stats_row.addWidget(self.badge_count)

        self.badge_duration = QLabel("⏱️ រយៈពេល: -- ➔ --")
        self.badge_duration.setStyleSheet(self._badge_style("#a78bfa"))
        self.stats_row.addWidget(self.badge_duration)

        self.badge_size = QLabel("💾 ទំហំឯកសារ: --")
        self.badge_size.setStyleSheet(self._badge_style("#34d399"))
        self.stats_row.addWidget(self.badge_size)

        self.stats_row.addStretch()
        g_layout.addLayout(self.stats_row)
        layout.addWidget(grp_source)

        # 2. Splitting Configuration Card
        grp_settings = QGroupBox("⚙️ ការកំណត់បំបែកឯកសារ (Split Settings)")
        grp_settings.setStyleSheet(self._group_box_style())
        s_layout = QVBoxLayout(grp_settings)
        s_layout.setContentsMargins(10, 12, 10, 10)
        s_layout.setSpacing(10)

        # Mode row: Presets + Custom Spinbox
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        lbl_chunk = QLabel("ចំនួនឃ្លាក្នុង ១ file (CC per file):")
        lbl_chunk.setStyleSheet("font-weight: bold; color: #f1f5f9;")
        ctrl_row.addWidget(lbl_chunk)

        # Quick Preset buttons
        presets = [500, 1000, 1500, 2000, 3000]
        for p in presets:
            btn_p = QPushButton(f"{p:,} CC")
            btn_p.setFixedHeight(26)
            btn_p.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_p.setStyleSheet(self._preset_btn_style())
            btn_p.clicked.connect(lambda ch=False, val=p: self._set_preset_chunk(val))
            ctrl_row.addWidget(btn_p)

        self.spin_chunk = QSpinBox()
        self.spin_chunk.setRange(1, 100000)
        self.spin_chunk.setValue(2000)
        self.spin_chunk.setSuffix(" CC")
        self.spin_chunk.setFixedWidth(110)
        self.spin_chunk.setStyleSheet(self._spinbox_style())
        self.spin_chunk.valueChanged.connect(self._update_calculation_preview)
        ctrl_row.addWidget(self.spin_chunk)

        ctrl_row.addStretch()
        s_layout.addLayout(ctrl_row)

        # Advanced options (Renumbering & Target folder)
        opt_row = QHBoxLayout()
        opt_row.setSpacing(12)

        self.chk_renumber = QCheckBox("ចាប់ផ្ដើមលេខរៀងពី 1 ឡើងវិញក្នុង file នីមួយៗ (1..N - ណែនាំសម្រាប់ AI)")
        self.chk_renumber.setChecked(True)
        self.chk_renumber.setToolTip("ពេលជ្រើសរើស ឯកសារនីមួយៗនឹងចាប់ផ្ដើមលេខរៀងឃ្លាពីលេខ 1 ដែលជួយឲ្យ ChatGPT/Gemini មិនច្រឡំ ឬរំលង")
        self.chk_renumber.setStyleSheet("color: #e2e8f0; font-weight: 500;")
        opt_row.addWidget(self.chk_renumber)

        opt_row.addStretch()
        s_layout.addLayout(opt_row)

        # Output folder row
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)

        lbl_out = QLabel("រក្សាទុកទៅក្នុង Folder:")
        lbl_out.setStyleSheet("color: #cbd5e1;")
        folder_row.addWidget(lbl_out)

        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("រក្សាទុកដោយស្វ័យប្រវត្តិក្នុង Folder ឈ្មោះ [ឈ្មោះឯកសារ]_split_parts/...")
        self.edit_output_dir.setStyleSheet(self._input_style())
        folder_row.addWidget(self.edit_output_dir, 1)

        btn_browse_out = QPushButton("📁 ជ្រើសរើស Folder...")
        btn_browse_out.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse_out.setStyleSheet(self._btn_secondary_style())
        btn_browse_out.clicked.connect(self._on_browse_output_dir)
        folder_row.addWidget(btn_browse_out)

        s_layout.addLayout(folder_row)
        layout.addWidget(grp_settings)

        # 3. Dynamic Calculation & Real-time Plan Preview Banner
        self.card_plan = QFrame()
        self.card_plan.setStyleSheet("""
            QFrame {
                background-color: #171b22;
                border: 1px solid #283141;
                border-radius: 6px;
                padding: 8px 12px;
            }
        """)
        plan_layout = QVBoxLayout(self.card_plan)
        plan_layout.setContentsMargins(6, 4, 6, 4)
        plan_layout.setSpacing(4)

        self.lbl_plan_summary = QLabel("📊 គម្រោងបំបែក: សូមជ្រើសរើសឯកសារ SRT ដើម្បីពិនិត្យមើល")
        self.lbl_plan_summary.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 12px;")
        plan_layout.addWidget(self.lbl_plan_summary)

        self.lbl_plan_detail = QLabel("ឯកសារនឹងត្រូវចែកចេញជាផ្នែកស្មើៗគ្នា ស្របតាមចំនួនឃ្លាដែលបានកំណត់")
        self.lbl_plan_detail.setStyleSheet("color: #94a3b8; font-size: 11px;")
        plan_layout.addWidget(self.lbl_plan_detail)

        layout.addWidget(self.card_plan)

        # 4. Action Buttons (Execute Split + Copy AI Prompt)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.btn_split = QPushButton("✂️ ចាប់ផ្ដើមបំបែកឯកសារ SRT ឥឡូវនេះ (Split Now)")
        self.btn_split.setFixedHeight(34)
        self.btn_split.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_split.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 6px 18px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:pressed {
                background-color: #0c4a6e;
            }
        """)
        self.btn_split.clicked.connect(self._on_execute_split)
        action_row.addWidget(self.btn_split)

        btn_copy_prompt = QPushButton("📋 ចម្លង AI Translation Prompt")
        btn_copy_prompt.setFixedHeight(34)
        btn_copy_prompt.setToolTip("ចម្លង Prompt គំរូសម្រាប់ដាក់ទៅកាន់ ChatGPT / Gemini ដើម្បីបកប្រែឯកសារ SRT នេះ")
        btn_copy_prompt.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_copy_prompt.setStyleSheet(self._btn_secondary_style())
        btn_copy_prompt.clicked.connect(self._copy_ai_translation_prompt)
        action_row.addWidget(btn_copy_prompt)

        btn_open_folder = QPushButton("📂 បើក Folder លទ្ធផល")
        btn_open_folder.setFixedHeight(34)
        btn_open_folder.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_open_folder.setStyleSheet(self._btn_secondary_style())
        btn_open_folder.clicked.connect(self._open_current_output_dir)
        action_row.addWidget(btn_open_folder)

        action_row.addStretch()
        layout.addLayout(action_row)

        # 5. Generated Split Files Result Table
        grp_results = QGroupBox("📋 បញ្ជីឯកសារដែលបានបំបែករួច (Generated Split Parts)")
        grp_results.setStyleSheet(self._group_box_style())
        res_layout = QVBoxLayout(grp_results)
        res_layout.setContentsMargins(6, 8, 6, 6)

        self.table_split = QTableWidget(0, 6)
        self.table_split.setHorizontalHeaderLabels([
            "ផ្នែក #", "ឈ្មោះឯកសារ", "លំដាប់ឃ្លា (CC)", "ចន្លោះពេលវេលា (Time)", "ទំហំ (Size)", "សកម្មភាព (Actions)"
        ])
        self.table_split.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_split.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_split.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_split.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_split.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table_split.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table_split.setStyleSheet(self._table_style())
        res_layout.addWidget(self.table_split)

        layout.addWidget(grp_results, 1)
        return widget

    # =========================================================================
    # TAB 2: MERGE SRT
    # =========================================================================
    def _create_merge_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(10)

        # Merge Header Actions Card
        grp_actions = QGroupBox("➕ ជ្រើសរើសឯកសារ SRT ដែលត្រូវបញ្ចូលគ្នា (Select SRT Parts to Merge)")
        grp_actions.setStyleSheet(self._group_box_style())
        a_layout = QVBoxLayout(grp_actions)
        a_layout.setContentsMargins(10, 10, 10, 10)
        a_layout.setSpacing(8)

        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        btn_add_files = QPushButton("➕ បន្ថែមឯកសារ SRT...")
        btn_add_files.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add_files.setStyleSheet(self._btn_primary_style())
        btn_add_files.clicked.connect(self._on_add_merge_files)
        btn_bar.addWidget(btn_add_files)

        btn_add_folder = QPushButton("📁 បន្ថែម Folder ទាំងមូល...")
        btn_add_folder.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_add_folder.setStyleSheet(self._btn_secondary_style())
        btn_add_folder.clicked.connect(self._on_add_merge_folder)
        btn_bar.addWidget(btn_add_folder)

        btn_move_up = QPushButton("⬆️ រំកិលឡើងលើ")
        btn_move_up.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_move_up.setStyleSheet(self._preset_btn_style())
        btn_move_up.clicked.connect(self._on_move_merge_item_up)
        btn_bar.addWidget(btn_move_up)

        btn_move_down = QPushButton("⬇️ រំកិលចុះក្រោម")
        btn_move_down.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_move_down.setStyleSheet(self._preset_btn_style())
        btn_move_down.clicked.connect(self._on_move_merge_item_down)
        btn_bar.addWidget(btn_move_down)

        btn_remove = QPushButton("🗑️ លុបចេញ")
        btn_remove.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_remove.setStyleSheet(self._btn_danger_style())
        btn_remove.clicked.connect(self._on_remove_merge_item)
        btn_bar.addWidget(btn_remove)

        btn_clear = QPushButton("🧹 សម្អាតបញ្ជី")
        btn_clear.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_clear.setStyleSheet(self._preset_btn_style())
        btn_clear.clicked.connect(self._on_clear_merge_list)
        btn_bar.addWidget(btn_clear)

        btn_bar.addStretch()
        a_layout.addLayout(btn_bar)

        layout.addWidget(grp_actions)

        # Merge File List Table
        self.table_merge = QTableWidget(0, 5)
        self.table_merge.setHorizontalHeaderLabels([
            "លំដាប់ #", "ឈ្មោះឯកសារ", "ចំនួនឃ្លា (CC)", "ចន្លោះពេល (Time)", "ផ្លូវពេញលេញ (Path)"
        ])
        self.table_merge.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_merge.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_merge.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_merge.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_merge.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table_merge.setStyleSheet(self._table_style())
        layout.addWidget(self.table_merge, 1)

        # Destination & Execute Merge Card
        grp_dest = QGroupBox("💾 រក្សាទុកឯកសារច្របាច់បញ្ចូលគ្នា (Merged Destination)")
        grp_dest.setStyleSheet(self._group_box_style())
        d_layout = QVBoxLayout(grp_dest)
        d_layout.setContentsMargins(10, 10, 10, 10)
        d_layout.setSpacing(8)

        dest_row = QHBoxLayout()
        dest_row.setSpacing(8)

        self.edit_merge_dest = QLineEdit()
        self.edit_merge_dest.setPlaceholderText("ជ្រើសរើសផ្លូវ និងឈ្មោះឯកសារដែលត្រូវរក្សាទុក (ឧ. master_translated.srt)...")
        self.edit_merge_dest.setStyleSheet(self._input_style())
        dest_row.addWidget(self.edit_merge_dest, 1)

        btn_browse_dest = QPushButton("📁 រក្សាទុកជា...")
        btn_browse_dest.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_browse_dest.setStyleSheet(self._btn_secondary_style())
        btn_browse_dest.clicked.connect(self._on_browse_merge_destination)
        dest_row.addWidget(btn_browse_dest)
        d_layout.addLayout(dest_row)

        m_opt_row = QHBoxLayout()
        m_opt_row.setSpacing(10)

        self.chk_merge_renumber = QCheckBox("រៀបចំលេខរៀងឃ្លាឡើងវិញជាបន្តបន្ទាប់ (1..Total Cues)")
        self.chk_merge_renumber.setChecked(True)
        self.chk_merge_renumber.setStyleSheet("color: #e2e8f0; font-weight: 500;")
        m_opt_row.addWidget(self.chk_merge_renumber)

        m_opt_row.addStretch()

        self.btn_execute_merge = QPushButton("🔗 ច្របាច់បញ្ចូលឯកសារ (Merge & Save)")
        self.btn_execute_merge.setFixedHeight(32)
        self.btn_execute_merge.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_execute_merge.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border-radius: 5px;
                padding: 4px 16px;
            }
            QPushButton:hover {
                background-color: #047857;
            }
        """)
        self.btn_execute_merge.clicked.connect(self._on_execute_merge)
        m_opt_row.addWidget(self.btn_execute_merge)

        self.btn_merge_to_studio = QPushButton("🚀 បញ្ចូលទៅ Movie Studio")
        self.btn_merge_to_studio.setFixedHeight(32)
        self.btn_merge_to_studio.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_merge_to_studio.setStyleSheet(self._btn_primary_style())
        self.btn_merge_to_studio.clicked.connect(self._on_load_merged_to_studio)
        m_opt_row.addWidget(self.btn_merge_to_studio)

        d_layout.addLayout(m_opt_row)
        layout.addWidget(grp_dest)

        return widget

    # =========================================================================
    # EVENT HANDLERS & LOGIC: SPLITTER
    # =========================================================================
    def _set_preset_chunk(self, val: int):
        self.spin_chunk.setValue(val)

    def _on_browse_source_srt(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "ជ្រើសរើសឯកសារ SRT ដើម",
            "",
            "Subtitles (*.srt *.vtt);;All Files (*.*)"
        )
        if f:
            self.load_srt_file(f)

    def _on_load_from_studio(self):
        """Pulls the currently loaded subtitles from the Movie Studio editor."""
        if not self.get_studio_subtitles:
            QMessageBox.information(self, "ជូនដំណឹង", "មិនអាចទាញយកទិន្នន័យពី Studio បានទេ")
            return
        subs = self.get_studio_subtitles()
        if not subs:
            QMessageBox.warning(self, "ទទេ", "បច្ចុប្បន្នគ្មាន Subtitles ណាមួយត្រូវបានបើកក្នុង Movie Studio ទេ!")
            return

        # Write to a temporary file or virtual buffer
        temp_dir = os.path.abspath("temp_studio_srt")
        os.makedirs(temp_dir, exist_ok=True)
        temp_srt = os.path.join(temp_dir, "current_studio_subtitles.srt")
        content = generate_srt_content(subs)
        with open(temp_srt, "w", encoding="utf-8") as fp:
            fp.write(content)

        self.load_srt_file(temp_srt)
        self._log(f"📥 [SRT Tool] បានទាញយក {len(subs)} ឃ្លាពី Movie Studio មកដាក់ក្នុង SRT Splitter")

    def load_srt_file(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.critical(self, "កំហុស", f"រកមិនឃើញឯកសារ: {file_path}")
            return

        try:
            content = ""
            for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "cp1252"]:
                try:
                    with open(file_path, "r", encoding=enc) as fp:
                        content = fp.read()
                    if content:
                        break
                except Exception:
                    continue

            self.current_cues = parse_raw_srt_blocks(content)
            if not self.current_cues:
                # Fallback to general parser
                alt = parse_srt_file(file_path)
                self.current_cues = []
                for idx, c in enumerate(alt, 1):
                    self.current_cues.append({
                        "id": idx,
                        "start_str": format_timestamp(c.get("start", 0.0)),
                        "end_str": format_timestamp(c.get("end", 0.0)),
                        "start": c.get("start", 0.0),
                        "end": c.get("end", 0.0),
                        "text": c.get("khmer_text") or c.get("orig_text") or c.get("text") or ""
                    })

            if not self.current_cues:
                QMessageBox.warning(self, "ទទេ", "ឯកសារនេះមិនមានឃ្លា Subtitles ត្រឹមត្រូវទេ!")
                return

            self.current_srt_path = file_path
            self.edit_source_path.setText(file_path)

            # Update stats badges
            total_cc = len(self.current_cues)
            self.badge_count.setText(f"🔢 ចំនួនឃ្លាសរុប: {total_cc:,} CC")
            start_t = self.current_cues[0]["start_str"]
            end_t = self.current_cues[-1]["end_str"]
            self.badge_duration.setText(f"⏱️ រយៈពេល: {start_t} ➔ {end_t}")
            size_kb = os.path.getsize(file_path) / 1024
            self.badge_size.setText(f"💾 ទំហំ: {size_kb:.1f} KB")

            # Default output directory next to file
            base_dir = os.path.dirname(os.path.abspath(file_path))
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            def_out = os.path.join(base_dir, f"{base_name}_split_parts")
            self.edit_output_dir.setText(def_out)

            self._update_calculation_preview()
            self._log(f"📄 [SRT Tool] បានផ្ទុកឯកសារ SRT: {os.path.basename(file_path)} ({total_cc:,} ឃ្លា)")

        except Exception as e:
            QMessageBox.critical(self, "កំហុស", f"បរាជ័យក្នុងការបើកឯកសារ SRT:\n{e}")

    def _update_calculation_preview(self):
        if not self.current_cues:
            self.lbl_plan_summary.setText("📊 គម្រោងបំបែក: សូមជ្រើសរើសឯកសារ SRT ដើម្បីពិនិត្យមើល")
            self.lbl_plan_detail.setText("ឯកសារនឹងត្រូវចែកចេញជាផ្នែកស្មើៗគ្នា ស្របតាមចំនួនឃ្លាដែលបានកំណត់")
            return

        total_cc = len(self.current_cues)
        chunk_size = self.spin_chunk.value()
        if chunk_size <= 0:
            chunk_size = 2000

        num_parts = (total_cc + chunk_size - 1) // chunk_size
        self.lbl_plan_summary.setText(
            f"📊 គម្រោងបំបែក: សរុប {total_cc:,} CC ÷ {chunk_size:,} ក្នុង ១ file ➔ នឹងបំបែកជា {num_parts} ឯកសារ (Files)"
        )

        parts_desc = []
        for i in range(min(num_parts, 4)):
            s_idx = i * chunk_size
            e_idx = min(s_idx + chunk_size, total_cc)
            st = self.current_cues[s_idx]["start_str"]
            et = self.current_cues[e_idx - 1]["end_str"]
            parts_desc.append(f"• File {i+1}: ឃ្លា #{s_idx+1:,} - #{e_idx:,} ({st} ➔ {et})")

        if num_parts > 4:
            parts_desc.append(f"... និងនៅសល់ {num_parts - 4} ផ្នែកទៀត")

        self.lbl_plan_detail.setText(" | ".join(parts_desc))

    def _on_browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(self, "ជ្រើសរើស Folder សម្រាប់រក្សាទុកឯកសារបំបែក")
        if d:
            self.edit_output_dir.setText(d)

    def _open_current_output_dir(self):
        out_dir = self.edit_output_dir.text().strip()
        if not out_dir or not os.path.exists(out_dir):
            QMessageBox.information(self, "Folder មិនទាន់មាន", "Folder លទ្ធផលមិនទាន់ត្រូវបានបង្កើតនៅឡើយទេ")
            return
        self._open_file_folder(out_dir)

    def _open_file_folder(self, folder_path: str):
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as e:
            QMessageBox.warning(self, "កំហុស", f"មិនអាចបើក Folder បានទេ:\n{e}")

    def _copy_ai_translation_prompt(self):
        """Copies an optimal AI prompt to clipboard for ChatGPT / Gemini."""
        prompt = (
            "You are a professional movie dialogue translator.\n"
            "Translate the following SRT subtitle file into natural, engaging, and culturally authentic Khmer dialogue.\n\n"
            "CRITICAL RULES:\n"
            "1. KEEP THE EXACT SRT FORMAT: preserve all subtitle sequence numbers (1, 2, 3...) and exact timestamps (00:00:00,000 --> 00:00:00,000).\n"
            "2. DO NOT delete, merge, or re-order any timestamp lines.\n"
            "3. Only translate the text lines under each timestamp into Khmer (ភាសាខ្មែរ).\n"
            "4. Match the tone of a movie dubbing script (conversational, expressive, and concise so it fits the audio timing).\n"
            "5. Return ONLY the translated SRT text without extra commentary or markdown blocks."
        )
        QApplication.clipboard().setText(prompt)
        QMessageBox.information(
            self,
            "បានចម្លងរួចរាល់ (Copied!)",
            "បានចម្លង AI Translation Prompt ទៅកាន់ Clipboard ដោយជោគជ័យ!\n\n"
            "អ្នកអាចយកទៅ Paste ក្នុង ChatGPT, Gemini, ឬ Claude រួមជាមួយឯកសារ SRT ដែលបានបំបែក។"
        )
        self._log("📋 [SRT Tool] បានចម្លង AI Translation Prompt ទៅកាន់ Clipboard")

    def _on_execute_split(self):
        if not self.current_srt_path or not os.path.exists(self.current_srt_path):
            QMessageBox.warning(self, "ខ្វះឯកសារ", "សូមជ្រើសរើសឯកសារ SRT ជាមុនសិន!")
            return

        chunk_size = self.spin_chunk.value()
        out_dir = self.edit_output_dir.text().strip()
        renumber = self.chk_renumber.isChecked()

        try:
            self._log(f"✂️ [SRT Tool] កំពុងបំបែកឯកសារ {os.path.basename(self.current_srt_path)} (ទំហំ {chunk_size} ឃ្លា/file)...")
            generated = split_srt_file(
                file_path=self.current_srt_path,
                chunk_size=chunk_size,
                output_dir=out_dir if out_dir else None,
                renumber=renumber
            )
            self.generated_split_files = generated
            self._populate_split_table(generated)

            # Auto set output dir in field if generated
            if generated:
                self.edit_output_dir.setText(os.path.dirname(generated[0]["file_path"]))

            msg = f"បានបំបែកជា {len(generated)} ឯកសារដោយជោគជ័យ!\nទីតាំង: {os.path.dirname(generated[0]['file_path'])}"
            self._log(f"✅ [SRT Tool] {msg}")
            QMessageBox.information(self, "ជោគជ័យ", msg)

        except Exception as e:
            self._log(f"❌ [SRT Tool] បរាជ័យក្នុងការបំបែក: {e}")
            QMessageBox.critical(self, "កំហុស", f"បរាជ័យក្នុងការបំបែកឯកសារ:\n{e}")

    def _populate_split_table(self, files: List[Dict]):
        self.table_split.setRowCount(0)
        for row_idx, item in enumerate(files):
            self.table_split.insertRow(row_idx)

            # Part #
            it_part = QTableWidgetItem(f"Part {item['part']}")
            it_part.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_split.setItem(row_idx, 0, it_part)

            # File name
            it_name = QTableWidgetItem(item["filename"])
            it_name.setToolTip(item["file_path"])
            self.table_split.setItem(row_idx, 1, it_name)

            # Range
            it_range = QTableWidgetItem(f"#{item['start_cue']:,} - #{item['end_cue']:,} ({item['count']:,} CC)")
            it_range.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_split.setItem(row_idx, 2, it_range)

            # Timing
            it_time = QTableWidgetItem(f"{item['start_time']} ➔ {item['end_time']}")
            it_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_split.setItem(row_idx, 3, it_time)

            # Size
            size_kb = item["file_size"] / 1024
            it_size = QTableWidgetItem(f"{size_kb:.1f} KB")
            it_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_split.setItem(row_idx, 4, it_size)

            # Actions Cell
            actions_widget = QWidget()
            act_l = QHBoxLayout(actions_widget)
            act_l.setContentsMargins(4, 2, 4, 2)
            act_l.setSpacing(4)

            btn_open = QPushButton("📂 Open")
            btn_open.setFixedHeight(22)
            btn_open.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_open.setStyleSheet(self._mini_btn_style("#0284c7"))
            btn_open.clicked.connect(lambda ch=False, p=item["file_path"]: self._open_single_file(p))
            act_l.addWidget(btn_open)

            btn_copy = QPushButton("📋 Copy")
            btn_copy.setFixedHeight(22)
            btn_copy.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_copy.setStyleSheet(self._mini_btn_style("#475569"))
            btn_copy.clicked.connect(lambda ch=False, p=item["file_path"]: self._copy_path(p))
            act_l.addWidget(btn_copy)

            btn_studio = QPushButton("🚀 Studio")
            btn_studio.setFixedHeight(22)
            btn_studio.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn_studio.setStyleSheet(self._mini_btn_style("#10b981"))
            btn_studio.clicked.connect(lambda ch=False, p=item["file_path"]: self._load_file_to_studio(p))
            act_l.addWidget(btn_studio)

            self.table_split.setCellWidget(row_idx, 5, actions_widget)

    def _open_single_file(self, file_path: str):
        if not os.path.exists(file_path):
            return
        folder = os.path.dirname(os.path.abspath(file_path))
        self._open_file_folder(folder)

    def _copy_path(self, file_path: str):
        QApplication.clipboard().setText(file_path)
        self._log(f"📋 បានចម្លងផ្លូវឯកសារ: {file_path}")

    def _load_file_to_studio(self, file_path: str):
        if self.on_load_to_studio:
            self.on_load_to_studio(file_path)
            QMessageBox.information(self, "ផ្ទុកជោគជ័យ", f"បានផ្ទុក {os.path.basename(file_path)} ទៅក្នុង Movie Studio រួចរាល់!")

    # =========================================================================
    # EVENT HANDLERS & LOGIC: MERGER
    # =========================================================================
    def _on_add_merge_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "ជ្រើសរើសឯកសារ SRT ដែលត្រូវបញ្ចូលគ្នា",
            "",
            "Subtitles (*.srt *.vtt);;All Files (*.*)"
        )
        if files:
            for f in files:
                if f not in self.merge_file_list:
                    self.merge_file_list.append(f)
            self._refresh_merge_table()

    def _on_add_merge_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "ជ្រើសរើស Folder ដែលមានឯកសារ SRT ច្រើន")
        if folder:
            srt_files = [
                os.path.join(folder, f) for f in sorted(os.listdir(folder))
                if f.lower().endswith(".srt")
            ]
            if not srt_files:
                QMessageBox.information(self, "ទទេ", "គ្មានឯកសារ .srt ក្នុង Folder នេះទេ!")
                return
            for f in srt_files:
                if f not in self.merge_file_list:
                    self.merge_file_list.append(f)
            self._refresh_merge_table()

    def _on_move_merge_item_up(self):
        row = self.table_merge.currentRow()
        if row > 0 and row < len(self.merge_file_list):
            self.merge_file_list[row], self.merge_file_list[row - 1] = self.merge_file_list[row - 1], self.merge_file_list[row]
            self._refresh_merge_table()
            self.table_merge.selectRow(row - 1)

    def _on_move_merge_item_down(self):
        row = self.table_merge.currentRow()
        if row >= 0 and row < len(self.merge_file_list) - 1:
            self.merge_file_list[row], self.merge_file_list[row + 1] = self.merge_file_list[row + 1], self.merge_file_list[row]
            self._refresh_merge_table()
            self.table_merge.selectRow(row + 1)

    def _on_remove_merge_item(self):
        row = self.table_merge.currentRow()
        if 0 <= row < len(self.merge_file_list):
            del self.merge_file_list[row]
            self._refresh_merge_table()

    def _on_clear_merge_list(self):
        self.merge_file_list.clear()
        self._refresh_merge_table()

    def _refresh_merge_table(self):
        self.table_merge.setRowCount(0)
        for idx, fp in enumerate(self.merge_file_list, 1):
            row = self.table_merge.rowCount()
            self.table_merge.insertRow(row)

            # Index
            it_idx = QTableWidgetItem(str(idx))
            it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_merge.setItem(row, 0, it_idx)

            # Filename
            it_fn = QTableWidgetItem(os.path.basename(fp))
            it_fn.setToolTip(fp)
            self.table_merge.setItem(row, 1, it_fn)

            # Parse quick preview
            count_str = "--"
            time_str = "--"
            try:
                cues = parse_raw_srt_blocks(open(fp, "r", encoding="utf-8", errors="ignore").read())
                if cues:
                    count_str = f"{len(cues):,} CC"
                    time_str = f"{cues[0]['start_str']} ➔ {cues[-1]['end_str']}"
            except Exception:
                pass

            it_cnt = QTableWidgetItem(count_str)
            it_cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_merge.setItem(row, 2, it_cnt)

            it_tm = QTableWidgetItem(time_str)
            it_tm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table_merge.setItem(row, 3, it_tm)

            # Full Path
            it_p = QTableWidgetItem(fp)
            self.table_merge.setItem(row, 4, it_p)

        # Suggest destination file if not already set
        if self.merge_file_list and not self.edit_merge_dest.text():
            first_dir = os.path.dirname(os.path.abspath(self.merge_file_list[0]))
            self.edit_merge_dest.setText(os.path.join(first_dir, "master_merged_subtitles.srt"))

    def _on_browse_merge_destination(self):
        f, _ = QFileDialog.getSaveFileName(
            self,
            "ជ្រើសរើសទីតាំងរក្សាទុកឯកសារច្របាច់បញ្ចូលគ្នា",
            self.edit_merge_dest.text() or "master_merged.srt",
            "Subtitles (*.srt)"
        )
        if f:
            self.edit_merge_dest.setText(f)

    def _on_execute_merge(self):
        if not self.merge_file_list:
            QMessageBox.warning(self, "ទទេ", "សូមបន្ថែមឯកសារ SRT យ៉ាងហោចណាស់ ២ ឡើងទៅដើម្បីបញ្ចូលគ្នា!")
            return

        dest = self.edit_merge_dest.text().strip()
        if not dest:
            QMessageBox.warning(self, "ខ្វះទិន្នន័យ", "សូមជ្រើសរើសទីតាំងរក្សាទុកឯកសារ!")
            return

        renumber = self.chk_merge_renumber.isChecked()
        try:
            self._log(f"🔗 [SRT Tool] កំពុងច្របាច់បញ្ចូល {len(self.merge_file_list)} ឯកសារទៅជា: {os.path.basename(dest)}...")
            res = merge_srt_files(self.merge_file_list, dest, renumber=renumber)
            self._log(f"✅ [SRT Tool] បានបញ្ចូលជោគជ័យ! សរុប {res['total_cues']:,} ឃ្លា (ទំហំ {res['file_size']/1024:.1f} KB)")
            QMessageBox.information(
                self,
                "ជោគជ័យ",
                f"បានច្របាច់បញ្ចូលឯកសារចំនួន {len(self.merge_file_list)} ដោយជោគជ័យ!\n"
                f"ចំនួនឃ្លាសរុប: {res['total_cues']:,} CC\n"
                f"រយៈពេល: {res['start_time']} ➔ {res['end_time']}\n\n"
                f"រក្សាទុកនៅ: {dest}"
            )
        except Exception as e:
            self._log(f"❌ [SRT Tool] បរាជ័យក្នុងការបញ្ចូល: {e}")
            QMessageBox.critical(self, "កំហុស", f"បរាជ័យក្នុងការបញ្ចូលឯកសារ:\n{e}")

    def _on_load_merged_to_studio(self):
        dest = self.edit_merge_dest.text().strip()
        if not dest or not os.path.exists(dest):
            # Try merging first if list exists
            if self.merge_file_list:
                self._on_execute_merge()
                dest = self.edit_merge_dest.text().strip()
            else:
                QMessageBox.warning(self, "ទទេ", "សូមបញ្ចូលឯកសារជាមុនសិន!")
                return

        if os.path.exists(dest) and self.on_load_to_studio:
            self.on_load_to_studio(dest)
            QMessageBox.information(self, "ជោគជ័យ", f"បានផ្ទុកឯកសារច្របាច់បញ្ចូលរួច ({os.path.basename(dest)}) ទៅក្នុង Movie Studio!")

    # =========================================================================
    # STYLES & THEMING HELPERS
    # =========================================================================
    def _group_box_style(self) -> str:
        return """
            QGroupBox {
                background-color: #1e222b;
                border: 1px solid #334155;
                border-radius: 6px;
                margin-top: 10px;
                font-weight: bold;
                color: #38bdf8;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """

    def _input_style(self) -> str:
        return """
            QLineEdit {
                background-color: #171b22;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 11px;
            }
            QLineEdit:focus {
                border: 1px solid #0284c7;
            }
        """

    def _spinbox_style(self) -> str:
        return """
            QSpinBox {
                background-color: #171b22;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-weight: bold;
                font-size: 12px;
            }
            QSpinBox:focus {
                border-color: #0284c7;
            }
        """

    def _btn_primary_style(self) -> str:
        return """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:pressed {
                background-color: #0c4a6e;
            }
        """

    def _btn_secondary_style(self) -> str:
        return """
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 5px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #475569;
                color: #ffffff;
            }
        """

    def _btn_danger_style(self) -> str:
        return """
            QPushButton {
                background-color: #7f1d1d;
                color: #fecaca;
                border: 1px solid #991b1b;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #b91c1c;
                color: #ffffff;
            }
        """

    def _preset_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #272f3d;
                color: #94a3b8;
                border: 1px solid #3b4556;
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38bdf8;
                color: #0f172a;
                border-color: #38bdf8;
            }
        """

    def _mini_btn_style(self, bg_color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: #ffffff;
                border: none;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
        """

    def _badge_style(self, color: str) -> str:
        return f"""
            QLabel {{
                background-color: #171b22;
                color: {color};
                border: 1px solid #283141;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }}
        """

    def _table_style(self) -> str:
        return """
            QTableWidget {
                background-color: #171b22;
                color: #e2e8f0;
                gridline-color: #283141;
                border: 1px solid #283141;
                border-radius: 4px;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #212631;
                color: #38bdf8;
                font-weight: bold;
                padding: 5px;
                border: 1px solid #283141;
            }
            QTableWidget::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """
