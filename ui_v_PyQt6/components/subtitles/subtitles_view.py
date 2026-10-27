"""
Subtitles View Component for PyQt6 / PySide6 Desktop Studio
Virtualized dialogue table, AI translation settings, dubbing bar, and line timing editor.
"""

import os
import math
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, 
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QCheckBox, QFrame, QGroupBox, Qt, QMenu, QInputDialog, QApplication,
    QPoint, QCursor, QColor, QFont, QIcon, QPainter, QPen, QBrush, QRect,
    QStyledItemDelegate, QStyle
)
from ui_v_PyQt6.icons import (
    get_male_icon, get_female_icon, get_users_icon, get_swap_icon,
    get_speed_icon, get_mic_icon, get_dub_icon, get_listen_icon,
    get_translate_icon, get_copy_icon, get_plus_icon, get_trash_icon,
    get_clock_icon, get_edit_icon, get_sync_icon, get_ai_icon, get_bot_icon,
    get_rewind_icon, get_forward_icon, get_minus_icon, get_folder_icon, get_stop_icon
)
from utils import format_timestamp, parse_timestamp_to_seconds
from config import (
    TRANSLATION_PROVIDERS, TRANSLATION_STYLES, WHISPER_MODELS, 
    KHMER_FONT_FAMILY, SPEECH_SPEED_PRESETS, get_installed_khmer_fonts
)

VOICE_MODEL_OPTIONS = [
    "Edge-TTS: Piseth Neural (ប្រុស / Male)",
    "Edge-TTS: Sreymom Neural (ស្រី / Female)"
]

SPEED_OPTIONS = [
    "0.85x (យឺតបន្តិច - សមស្របពាក្យពិបាក)",
    "0.90x (យឺតស្រាល)",
    "0.95x (ធម្មជាតិស្រាល)",
    "1.00x (ល្បឿនដើម - Standard Normal)",
    "1.05x (រហ័សបន្តិច)",
    "1.10x (រហ័ស - ភាពយន្តកំប្លែង)",
    "1.15x (លឿន - Action/ក្បាច់គុន)",
    "1.20x (លឿនខ្លាំង)"
]


class TimelineVoicePillDelegate(QStyledItemDelegate):
    """
    Renders the exact Timeline Voice Pill inside the Subtitles Table 'Voice & Speed' column:
    - Signature rounded pill with role-based colors (Pink for Female, Cyan for Male, Amber for Kid, Violet for Speaker)
    - Real-time animated/static audio waveform peaks
    - Signature white trim handles [ 0 ] on left and right matching timeline screenshot
    - Audio icon (🔊 dubbed / 🎙️ pending) with character voice name, duration, and speed rate
    """
    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        sub_info = index.data(Qt.ItemDataRole.UserRole + 1)
        if not sub_info or not isinstance(sub_info, dict):
            # Fallback: synthesize sub_info from display text or row data so it always renders the timeline pill
            disp_txt = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            actor = "តួអង្គ (Dialogue)"
            try:
                table = option.widget
                if table:
                    c4 = table.item(index.row(), 4)
                    if c4:
                        actor = c4.text()
            except Exception:
                pass
            sub_info = {
                "actor": actor,
                "gender": "female" if ("ស្រី" in actor or "Female" in actor) else ("male" if ("ប្រុស" in actor or "Male" in actor) else "dialogue"),
                "voice": "",
                "has_audio": False,
                "rate": "+0%",
                "dur_str": disp_txt if disp_txt and ("s" in disp_txt or ":" in disp_txt) else "2.0s"
            }

        rect = option.rect
        px = rect.x() + 4
        py = rect.y() + 2
        pw = max(24, rect.width() - 8)
        ph = max(14, rect.height() - 4)

        actor = sub_info.get("actor", "")
        gender = sub_info.get("gender", "")
        has_audio = sub_info.get("has_audio", False)
        rate_val = sub_info.get("rate", "+0%")
        dur_str = sub_info.get("dur_str", "0.0s")
        is_selected = bool(option.state & QStyle.StateFlag.State_Selected)

        is_female = ("ស្រី" in actor or "Female" in actor or gender == "female" or "Sreymom" in str(sub_info.get("voice", "")))
        is_kid = ("កូនក្មេង" in actor or "Kid" in actor or "Child" in actor)
        is_spk = ("តួអង្គ" in actor or "Speaker" in actor)

        # Palette matching timeline track 3 exactly
        if is_selected:
            bg_col = QColor("#0c3f6e") if not is_female else QColor("#500724")
            border_col = QColor("#facc15")
            border_w = 2.0
        elif is_female:
            bg_col = QColor("#4c0519")
            border_col = QColor("#be185d")
            border_w = 1.5
        elif is_kid:
            bg_col = QColor("#451a03")
            border_col = QColor("#b45309")
            border_w = 1.5
        elif is_spk:
            bg_col = QColor("#3b0764")
            border_col = QColor("#7e22ce")
            border_w = 1.5
        elif "ប្រុស" in actor or "Male" in actor:
            bg_col = QColor("#082f49")
            border_col = QColor("#0284c7")
            border_w = 1.5
        else:
            bg_col = QColor("#0f172a")
            border_col = QColor("#38bdf8" if is_selected else "#2563eb")
            border_w = 1.4

        # 1. Pill Background
        painter.setPen(QPen(border_col, border_w))
        painter.setBrush(QBrush(bg_col))
        painter.drawRoundedRect(px, py, pw, ph, 7, 7)

        # 2. Audio Waveform Peaks in background
        wave_step = 3
        center_y = py + ph // 2
        wave_col = QColor("#facc15" if is_selected else ("#fbcfe8" if is_female else ("#fed7aa" if is_kid else ("#e9d5ff" if is_spk else "#bae6fd"))))
        painter.setPen(QPen(wave_col, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        start_w_x = px + 15
        end_w_x = px + pw - 15
        if end_w_x > start_w_x:
            b_cnt = max(1, (end_w_x - start_w_x) // wave_step)
            for b_i in range(b_cnt):
                sin_v = math.sin((b_i / float(max(1, b_cnt))) * math.pi)
                amp = int(sin_v * (ph * 0.40) * (0.35 + 0.65 * ((b_i * 17 + 5) % 11) / 11.0))
                amp = max(2, amp)
                bx = start_w_x + b_i * wave_step
                painter.drawLine(bx, center_y - amp, bx, center_y + amp)

        # 3. Signature White Trim Handles [ 0 ] on left and right (matching screenshot)
        if pw >= 38:
            self._draw_white_handle(painter, px + 2, py, ph)
            self._draw_white_handle(painter, px + pw - 12, py, ph)

        # 4. Pill Text Badge
        aud_ico = "🔊" if has_audio else "🎙️"
        disp_name = actor
        if not disp_name or "Dialogue" in disp_name:
            v_name = sub_info.get("voice", "")
            if "Sreymom" in v_name:
                disp_name = "ស្រីមុំ"
            elif "Piseth" in v_name:
                disp_name = "ពិសិដ្ឋ"
            else:
                disp_name = "Voice"
        elif "ស្រី" in disp_name:
            disp_name = "ស្រីមុំ"
        elif "ប្រុស" in disp_name:
            disp_name = "ពិសិដ្ឋ"
        elif len(disp_name) > 10:
            disp_name = disp_name[:8] + ".."

        badge_txt = f"{aud_ico} [{disp_name}] {dur_str} ({rate_val})"
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        fm = painter.fontMetrics()
        tbw = min(pw - 26, fm.horizontalAdvance(badge_txt) + 12)
        tbx = px + (pw - tbw) // 2
        tby = py + 2
        tbh = max(8, ph - 4)

        # Badge translucent backing so text is ultra-clear over waveforms
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(10, 15, 30, 185)))
        painter.drawRoundedRect(tbx, tby, tbw, tbh, 4, 4)

        # Badge text
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRect(tbx, tby, tbw, tbh), Qt.AlignmentFlag.AlignCenter, badge_txt)

        painter.restore()

    def _draw_white_handle(self, painter: QPainter, x: int, y: int, h: int):
        """Draws the signature white rounded pill handle [ 0 ] matching timeline clips"""
        w = 10
        handle_h = min(18, max(12, h - 6))
        hy = y + (h - handle_h) // 2
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor("#ffffff")))
        painter.drawRoundedRect(x, hy, w, handle_h, 3, 3)
        painter.setPen(QPen(QColor("#0f172a"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        slit_h = max(5, handle_h - 7)
        slit_y = hy + (handle_h - slit_h) // 2
        painter.drawLine(x + w // 2, slit_y, x + w // 2, slit_y + slit_h)
        painter.restore()


class SubtitlesView(QWidget):
    """
    Ultra-Fast Virtual Subtitle Editor & AI Translation Manager:
    - Zero-lag 60fps scrolling with Qt's native C++ Table rendering
    - Instant search and filtering across thousands of lines
    - Integrated AI translation and multi-model Dubbing controllers
    - Precise millisecond timing controls
    """
    def __init__(
        self,
        parent=None,
        on_select_sub=None,
        on_apply_edit=None,
        on_listen_line=None,
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
        on_voice_speed_change=None,
        on_auto_sync_all=None,
        on_auto_sync_single=None,
        on_toggle_timeline=None,
        on_toggle_logs=None,
        on_toggle_inspector=None,
        on_fix_overlaps=None,
        on_select_multiple_subs=None,
        on_stop_task=None,
        on_detect_genders=None
    ):
        super().__init__(parent)
        self.on_select_sub = on_select_sub
        self.on_select_multiple_subs = on_select_multiple_subs
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
        self.on_auto_sync_all = on_auto_sync_all
        self.on_auto_sync_single = on_auto_sync_single
        self.on_toggle_timeline = on_toggle_timeline
        self.on_toggle_logs = on_toggle_logs
        self.on_toggle_inspector = on_toggle_inspector
        self.on_fix_overlaps = on_fix_overlaps
        self.on_stop_task = on_stop_task
        self.on_detect_genders = on_detect_genders

        self._subtitles_data = []
        self._selected_idx = -1
        self._selected_indices = []
        self._filter_text = ""
        self._idx_to_row = {}
        self._current_voice = VOICE_MODEL_OPTIONS[0]
        self._auto_dub = True

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # ---------------- TOP ACTION BAR: AI TRANSLATION & DUBBING ----------------
        top_bar = QFrame()
        top_bar.setStyleSheet("""
            QFrame {
                background-color: #171b24;
                border: 1px solid #232b38;
                border-radius: 6px;
                padding: 2px 4px;
            }
        """)
        r1_layout = QHBoxLayout(top_bar)
        r1_layout.setContentsMargins(6, 4, 6, 4)
        r1_layout.setSpacing(6)

        # Provider & style selectors are preserved internally with Google Free as default
        self.combo_provider = QComboBox()
        self.combo_provider.addItems(TRANSLATION_PROVIDERS)
        self.combo_provider.setVisible(False)
        self.combo_provider.currentTextChanged.connect(self._on_provider_changed)

        self.lbl_style = QLabel("🎭 Style:")
        self.lbl_style.setVisible(False)
        self.combo_style = QComboBox()
        self.combo_style.addItems(TRANSLATION_STYLES)
        self.combo_style.setVisible(False)

        btn_import = QPushButton(" SRT file")
        btn_import.setIcon(get_folder_icon(14, color="#38bdf8"))
        btn_import.clicked.connect(self._on_import_srt_clicked)
        r1_layout.addWidget(btn_import)

        btn_cc = QPushButton(" ចាប់ CC")
        btn_cc.setObjectName("btn_primary")
        btn_cc.setIcon(get_mic_icon(14, color="#ffffff"))
        btn_cc.clicked.connect(self._on_capture_cc_clicked)
        r1_layout.addWidget(btn_cc)

        btn_trans_all = QPushButton(" បកប្រែ")
        btn_trans_all.setObjectName("btn_success")
        btn_trans_all.setIcon(get_translate_icon(14, color="#ffffff"))
        btn_trans_all.clicked.connect(self._on_trans_all_clicked)
        r1_layout.addWidget(btn_trans_all)

        btn_dub_all = QPushButton(" បញ្ចូលសំលេង")
        btn_dub_all.setObjectName("btn_primary")
        btn_dub_all.setIcon(get_dub_icon(14, color="#ffffff"))
        btn_dub_all.clicked.connect(self._on_dub_all_clicked)
        r1_layout.addWidget(btn_dub_all)

        self.btn_stop_process = QPushButton(" Stop")
        self.btn_stop_process.setIcon(get_stop_icon(14, color="#ffffff"))
        self.btn_stop_process.setToolTip("បញ្ឈប់ដំណើរការភ្លាមៗ (Stop current running process)")
        self.btn_stop_process.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #ef4444;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #b91c1c;
            }
        """)
        self.btn_stop_process.clicked.connect(self._on_stop_clicked)
        self.btn_stop_process.setVisible(False)
        r1_layout.addWidget(self.btn_stop_process)

        main_layout.addWidget(top_bar)

        # ---------------- MAIN CONTAINER: SUBTITLES TABLE & SEARCH ----------------
        table_container = QFrame()
        table_container.setStyleSheet("""
            QFrame {
                background-color: #11141c;
                border: 1px solid #232b38;
                border-radius: 6px;
            }
        """)
        tbl_layout = QVBoxLayout(table_container)
        tbl_layout.setContentsMargins(6, 6, 6, 6)
        tbl_layout.setSpacing(6)

        # Subtitles Action Toolbar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(6)

        self.lbl_sub_count = QLabel("0 Subtitles")
        self.lbl_sub_count.setStyleSheet("color: #38bdf8; font-weight: bold;")
        search_layout.addWidget(self.lbl_sub_count)
        search_layout.addStretch()

        btn_listen = QPushButton(" ស្តាប់")
        btn_listen.setIcon(get_listen_icon(14, color="#38bdf8"))
        btn_listen.setToolTip("Listen to selected line audio")
        btn_listen.clicked.connect(self._on_listen_clicked)
        search_layout.addWidget(btn_listen)

        btn_trans = QPushButton(" បកប្រែ")
        btn_trans.setIcon(get_translate_icon(14, color="#38bdf8"))
        btn_trans.setToolTip("Translate selected line")
        btn_trans.clicked.connect(self._on_trans_single_clicked)
        search_layout.addWidget(btn_trans)

        btn_add = QPushButton(" add sub")
        btn_add.setIcon(get_plus_icon(14, color="#10b981"))
        btn_add.clicked.connect(self._on_add_sub_clicked)
        search_layout.addWidget(btn_add)

        btn_del = QPushButton(" លុប sub")
        btn_del.setIcon(get_trash_icon(14, color="#ef4444"))
        btn_del.clicked.connect(self._on_delete_sub_clicked)
        search_layout.addWidget(btn_del)

        btn_fit_duration = QPushButton(" តម្រឹមតាមសំឡេង")
        btn_fit_duration.setIcon(get_clock_icon(14, color="#ffffff"))
        btn_fit_duration.setToolTip("ពង្រីកពេលវេលា Subtitle ឱ្យត្រូវគ្នានឹងប្រវែងសំឡេងពិតប្រាកដ (Fit Duration to Voice Audio)")
        btn_fit_duration.setStyleSheet("background-color: #047857; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        btn_fit_duration.clicked.connect(self._on_fit_duration_clicked)
        search_layout.addWidget(btn_fit_duration)

        btn_fix_overlaps = QPushButton(" កែជាន់គ្នា")
        btn_fix_overlaps.setIcon(get_ai_icon(14, color="#ffffff"))
        btn_fix_overlaps.setToolTip("កែសម្រួលពេលវេលា Subtitles ដែលជាន់គ្នា ឱ្យរត់បន្តគ្នាដោយស្វ័យប្រវត្តិ មិនជាន់សំឡេងគ្នា (Fix Overlapping Subtitles)")
        btn_fix_overlaps.setStyleSheet("background-color: #0369a1; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        btn_fix_overlaps.clicked.connect(self._on_fix_overlaps_clicked)
        search_layout.addWidget(btn_fix_overlaps)

        btn_detect_sex = QPushButton(" 🎭 ចាប់ភេទ (Sex)")
        btn_detect_sex.setIcon(get_users_icon(14, color="#ffffff"))
        btn_detect_sex.setToolTip("វិភាគសំឡេងវីដេអូដើម្បីចាប់ភេទតួអង្គ (ប្រុស/ស្រី) និងបែងចែកតួអង្គស្វ័យប្រវត្តិតាមសំឡេងពិត (Detect Character Sex & Diarization from Audio)")
        btn_detect_sex.setStyleSheet("background-color: #6366f1; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 4px 10px;")
        btn_detect_sex.clicked.connect(self._on_detect_gender_clicked)
        search_layout.addWidget(btn_detect_sex)

        self.btn_toggle_inspector = QPushButton(" ⚙️ Inspector")
        self.btn_toggle_inspector.setIcon(get_speed_icon(14, color="#38bdf8"))
        self.btn_toggle_inspector.setToolTip("បង្ហាញ / លាក់ ផ្ទាំងខាងស្តាំ (Toggle Right Inspector)")
        self.btn_toggle_inspector.setStyleSheet("""
            QPushButton {
                background-color: #272c36;
                color: #cbd5e1;
                border: 1px solid #3e4756;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """)
        if self.on_toggle_inspector:
            self.btn_toggle_inspector.clicked.connect(self.on_toggle_inspector)
        search_layout.addWidget(self.btn_toggle_inspector)

        tbl_layout.addLayout(search_layout)

        # Virtualized Table with dedicated Sex & Character Columns
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "#", "Timing", "Original Text", "Khmer Translation",
            "ភេទ (Sex)", "តួអង្គ (Character)", "Voice & Speed", "Status"
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 44)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 145)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 98)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 138)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 185)
        self.table.setItemDelegateForColumn(6, TimelineVoicePillDelegate(self.table))
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 85)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        self.table.cellDoubleClicked.connect(self._on_table_cell_double_clicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.setStyleSheet("font-size: 11px;")
        tbl_layout.addWidget(self.table, 1)

        main_layout.addWidget(table_container, 1)

    # ------------------ DATA BINDING & POPULATION ------------------
    def set_subtitles(self, subtitles: list):
        """Populates subtitles list cleanly with virtualized rows"""
        self._subtitles_data = subtitles or []
        self._refresh_table()

    def update_subtitles(self, subtitles: list):
        self.set_subtitles(subtitles)

    def _on_table_cell_clicked(self, row: int, col: int):
        it = self.table.item(row, 0)
        if not it:
            return
        orig_idx = it.data(Qt.ItemDataRole.UserRole)
        if orig_idx is None or not (0 <= orig_idx < len(self._subtitles_data)):
            return

        if col == 4:
            # Click on Sex Column: Quick toggle Male <-> Female!
            self._toggle_line_gender(orig_idx)
        elif col == 5:
            # Click on Character Column: Show Character selection popup
            self._show_character_popup(orig_idx)
        elif col == 6:
            # Click on Voice & Speed: Play audio
            self._on_play_voice_line(orig_idx)

    def _on_table_cell_double_clicked(self, row: int, col: int):
        it = self.table.item(row, 0)
        if not it:
            return
        orig_idx = it.data(Qt.ItemDataRole.UserRole)
        if orig_idx is None or not (0 <= orig_idx < len(self._subtitles_data)):
            return

        if col == 4:
            # Double click on Sex: Quick toggle Male <-> Female
            self._toggle_line_gender(orig_idx)
        elif col == 5:
            # Double click on Character: Show Character selection popup
            self._show_character_popup(orig_idx)
        elif col == 6:
            # Double click: Show speed selection popup
            self._show_speed_popup(orig_idx)

    def _get_sub_character_info(self, sub: dict):
        """Returns (actor_name, icon, color) matching exactly the Character Voice Cast dropdown."""
        actor_name = sub.get("actor") or sub.get("speaker") or sub.get("character")
        if not actor_name:
            g = sub.get("gender")
            if g == "female":
                actor_name = "តួស្រី (Female)"
            elif g == "male":
                actor_name = "តួប្រុស (Male)"
            else:
                actor_name = "តួទូទៅ (Dialogue)"

        is_female = ("ស្រី" in actor_name or "Female" in actor_name) or (sub.get("gender") == "female") or ("Sreymom" in str(sub.get("voice", "") or sub.get("voice_name", "")))
        is_kid = "កូនក្មេង" in actor_name or "Kid" in actor_name or "Child" in actor_name
        is_spk = "តួអង្គ" in actor_name or "Speaker" in actor_name

        if is_female:
            icon = get_female_icon(16)
            color = QColor("#f472b6")
        elif is_kid:
            icon = get_users_icon(16, color="#f59e0b")
            color = QColor("#f59e0b")
        elif is_spk:
            icon = get_users_icon(16, color="#a855f7")
            color = QColor("#c084fc")
        elif "ប្រុស" in actor_name or "Male" in actor_name:
            icon = get_male_icon(16)
            color = QColor("#38bdf8")
        else:
            # "តួទូទៅ (Dialogue)"
            icon = get_users_icon(16, color="#94a3b8")
            color = QColor("#cbd5e1")

        return actor_name, icon, color

    def _refresh_table(self):
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)

            query = self._filter_text.lower().strip()
            filtered = []
            for idx, sub in enumerate(self._subtitles_data):
                orig = str(sub.get("orig_text", "") or sub.get("text", "")).lower()
                km = str(sub.get("khmer_text", "")).lower()
                if not query or query in orig or query in km:
                    filtered.append((idx, sub))

            self._idx_to_row = {}
            self.table.setRowCount(len(filtered))
            for row_idx, (orig_idx, sub) in enumerate(filtered):
                self._idx_to_row[orig_idx] = row_idx
                start_val = float(sub.get("start", 0.0))
                end_val = float(sub.get("end", 0.0))
                start_str = format_timestamp(start_val)
                end_str = format_timestamp(end_val)
                timing = f"{start_str} -> {end_str}"
                orig_text = str(sub.get("orig_text", "") or sub.get("text", ""))
                km_text = str(sub.get("khmer_text", ""))
                has_audio = bool(sub.get("audio_file") or sub.get("audio_path"))
                rate_val = str(sub.get("rate") or "+0%")
                if not rate_val.startswith(("+", "-")):
                    rate_val = f"+{rate_val}"
                if not rate_val.endswith("%"):
                    rate_val = f"{rate_val}%"

                # Compute voice duration (actual audio_dur if available, else cue timing duration)
                dur = max(0.0, end_val - start_val)
                if sub.get("audio_dur"):
                    try:
                        dur = float(sub["audio_dur"])
                    except Exception:
                        pass
                dur_str = f"{dur:.1f}s" if dur < 60 else f"{int(dur//60)}:{dur%60:04.1f}"

                is_translating = bool(km_text and ("កំពុងបកប្រែ" in km_text or "Translating" in km_text))
                if has_audio:
                    dubbed = "Dubbed"
                elif is_translating:
                    dubbed = "Translating..."
                elif km_text:
                    dubbed = "Trans"
                else:
                    dubbed = "Raw"

                it_idx = QTableWidgetItem(str(orig_idx + 1))
                it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_idx.setData(Qt.ItemDataRole.UserRole, orig_idx)
                it_idx.setFlags(it_idx.flags() & ~Qt.ItemFlag.ItemIsEditable)

                it_time = QTableWidgetItem(timing)
                it_orig = QTableWidgetItem(orig_text)
                it_km = QTableWidgetItem(km_text)
                if is_translating:
                    it_km.setForeground(QColor("#f59e0b"))

                # Column 4: Sex (ភេទ: 👨 ប្រុស / 👩 ស្រី / 🧒 ក្មេង)
                actor_name, char_icon, char_color = self._get_sub_character_info(sub)
                g_raw = str(sub.get("gender", "")).lower()
                is_female = (g_raw == "female") or ("ស្រី" in actor_name or "Female" in actor_name) or ("Sreymom" in str(sub.get("voice", "") or sub.get("voice_name", "")))
                is_kid = "កូនក្មេង" in actor_name or "kid" in g_raw

                if is_female:
                    sex_label = "👩 ស្រី"
                    sex_color = QColor("#f472b6")
                elif is_kid:
                    sex_label = "🧒 ក្មេង"
                    sex_color = QColor("#f59e0b")
                else:
                    sex_label = "👨 ប្រុស"
                    sex_color = QColor("#38bdf8")

                it_sex = QTableWidgetItem(sex_label)
                it_sex.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_sex.setData(Qt.ItemDataRole.UserRole, orig_idx)
                it_sex.setFlags(it_sex.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it_sex.setForeground(sex_color)
                it_sex.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                it_sex.setToolTip("ភេទ (Sex):\n• ចុច ១ ដង: ប្តូរ 👨 ប្រុស <-> 👩 ស្រី")

                # Column 5: Character (តួអង្គ)
                it_char = QTableWidgetItem(actor_name)
                it_char.setIcon(char_icon)
                it_char.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_char.setData(Qt.ItemDataRole.UserRole, orig_idx)
                it_char.setFlags(it_char.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it_char.setForeground(char_color)
                it_char.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                it_char.setToolTip(f"តួអង្គ: {actor_name}\n• ចុចដើម្បីរើស ឬបញ្ចូលឈ្មោះតួអង្គថ្មី (Diarization)")

                # Column 6: Voice & Speed Item (Timeline Voice Pill Delegate)
                sub_info = {
                    "actor": actor_name,
                    "gender": "female" if is_female else "male",
                    "voice": sub.get("voice_name") or sub.get("voice") or "",
                    "has_audio": has_audio,
                    "rate": rate_val,
                    "dur_str": dur_str
                }
                it_voice = QTableWidgetItem(f"{dur_str}  [{rate_val}]")
                it_voice.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_voice.setData(Qt.ItemDataRole.UserRole, orig_idx)
                it_voice.setData(Qt.ItemDataRole.UserRole + 1, sub_info)
                it_voice.setFlags(it_voice.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Column 7: Status
                it_status = QTableWidgetItem(dubbed)
                it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                it_status.setFlags(it_status.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if is_translating:
                    it_status.setForeground(QColor("#f59e0b"))
                elif has_audio:
                    it_status.setForeground(QColor("#34d399"))
                elif km_text:
                    it_status.setForeground(QColor("#38bdf8"))

                self.table.setItem(row_idx, 0, it_idx)
                self.table.setItem(row_idx, 1, it_time)
                self.table.setItem(row_idx, 2, it_orig)
                self.table.setItem(row_idx, 3, it_km)
                self.table.setItem(row_idx, 4, it_sex)
                self.table.setItem(row_idx, 5, it_char)
                self.table.setItem(row_idx, 6, it_voice)
                self.table.setItem(row_idx, 7, it_status)

        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        self.lbl_sub_count.setText(f"{len(self._subtitles_data)} Subtitles")

    def update_single_row_translation(self, orig_idx: int, km_text: str, status: str = "translated"):
        """Directly updates Khmer text and Status for a single row without rebuilding the table (zero lag)"""
        if 0 <= orig_idx < len(self._subtitles_data):
            self._subtitles_data[orig_idx]["khmer_text"] = km_text
            self._subtitles_data[orig_idx]["translated"] = km_text
            self._subtitles_data[orig_idx]["status"] = status

        row = self._idx_to_row.get(orig_idx)
        if row is None or row < 0 or row >= self.table.rowCount():
            return

        self.table.blockSignals(True)
        it_km = self.table.item(row, 3)
        if it_km:
            it_km.setText(km_text)
            if "កំពុងបកប្រែ" in km_text or "Translating" in km_text:
                it_km.setForeground(QColor("#f59e0b"))
            else:
                it_km.setForeground(QColor("#e2e8f0"))

        it_status = self.table.item(row, 7)
        if it_status:
            if "កំពុងបកប្រែ" in km_text or "Translating" in km_text or status == "translating":
                it_status.setText("Translating...")
                it_status.setForeground(QColor("#f59e0b"))
            elif status == "translated" or km_text:
                it_status.setText("Trans")
                it_status.setForeground(QColor("#38bdf8"))
            else:
                it_status.setText("Raw")
                it_status.setForeground(QColor("#94a3b8"))
        self.table.blockSignals(False)

    def mark_rows_translating(self, indices: list):
        """Fast in-place batch update to mark rows as translating without rebuilding table widgets (0ms lag)"""
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            for orig_idx in indices:
                if 0 <= orig_idx < len(self._subtitles_data):
                    self._subtitles_data[orig_idx]["khmer_text"] = "កំពុងបកប្រែ..."
                    self._subtitles_data[orig_idx]["status"] = "translating"

                row = self._idx_to_row.get(orig_idx)
                if row is not None and 0 <= row < self.table.rowCount():
                    it_km = self.table.item(row, 3)
                    if it_km:
                        it_km.setText("កំពុងបកប្រែ...")
                        it_km.setForeground(QColor("#f59e0b"))
                    it_status = self.table.item(row, 7)
                    if it_status:
                        it_status.setText("Translating...")
                        it_status.setForeground(QColor("#f59e0b"))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

    def update_rows_batch(self, items: list):
        """Fast in-place batch update for completed translated items: [(orig_idx, km_text, status), ...]"""
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            for orig_idx, km_text, status in items:
                if 0 <= orig_idx < len(self._subtitles_data):
                    self._subtitles_data[orig_idx]["khmer_text"] = km_text
                    self._subtitles_data[orig_idx]["translated"] = km_text
                    self._subtitles_data[orig_idx]["status"] = status

                row = self._idx_to_row.get(orig_idx)
                if row is not None and 0 <= row < self.table.rowCount():
                    it_km = self.table.item(row, 3)
                    if it_km:
                        it_km.setText(km_text)
                        if "កំពុងបកប្រែ" in km_text or "Translating" in km_text:
                            it_km.setForeground(QColor("#f59e0b"))
                        else:
                            it_km.setForeground(QColor("#e2e8f0"))

                    it_status = self.table.item(row, 7)
                    if it_status:
                        if "កំពុងបកប្រែ" in km_text or "Translating" in km_text or status == "translating":
                            it_status.setText("Translating...")
                            it_status.setForeground(QColor("#f59e0b"))
                        elif status == "translated" or km_text:
                            it_status.setText("Trans")
                            it_status.setForeground(QColor("#38bdf8"))
                        else:
                            it_status.setText("Raw")
                            it_status.setForeground(QColor("#94a3b8"))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

    def update_single_row_gender(self, orig_idx: int, is_female: bool = False):
        """Updates sex (Col 4) and character role (Col 5) cells for a single row without rebuilding table"""
        row = self._idx_to_row.get(orig_idx)
        if row is None or row < 0 or row >= self.table.rowCount():
            return
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return

        sub = self._subtitles_data[orig_idx]
        actor_name, char_icon, char_color = self._get_sub_character_info(sub)

        # Col 4: Sex (ភេទ)
        it_sex = self.table.item(row, 4)
        if it_sex:
            if is_female:
                it_sex.setText("👩 ស្រី")
                it_sex.setForeground(QColor("#f472b6"))
            else:
                it_sex.setText("👨 ប្រុស")
                it_sex.setForeground(QColor("#38bdf8"))

        # Col 5: Character (តួអង្គ)
        it_char = self.table.item(row, 5)
        if it_char:
            it_char.setText(actor_name)
            it_char.setIcon(char_icon)
            it_char.setForeground(char_color)
            it_char.setToolTip(f"តួអង្គ: {actor_name}\n• ចុចដើម្បីរើស ឬបញ្ចូលឈ្មោះតួអង្គថ្មី (Diarization)")

    def update_single_row_voice(self, orig_idx: int, has_audio: bool, dur_str: str = "", rate_val: str = ""):
        """Updates voice cell (Col 6) and status (Col 7) for a single row without rebuilding table"""
        if 0 <= orig_idx < len(self._subtitles_data):
            sub = self._subtitles_data[orig_idx]
            if not dur_str:
                dur = max(0.0, float(sub.get("end", 0.0)) - float(sub.get("start", 0.0)))
                dur_str = f"{dur:.1f}s"
            if not rate_val:
                rate_val = sub.get("rate", "+0%")

        row = self._idx_to_row.get(orig_idx)
        if row is None or row < 0 or row >= self.table.rowCount():
            return

        self.table.blockSignals(True)
        it_voice = self.table.item(row, 6)
        if it_voice:
            actor_name, _, _ = self._get_sub_character_info(sub)
            sub_info = {
                "actor": actor_name,
                "gender": sub.get("gender") or ("female" if ("ស្រី" in actor_name or "Female" in actor_name) else ("male" if ("ប្រុស" in actor_name or "Male" in actor_name) else "dialogue")),
                "voice": sub.get("voice_name") or sub.get("voice") or "",
                "has_audio": has_audio,
                "rate": rate_val,
                "dur_str": dur_str
            }
            it_voice.setText(f"{dur_str}  [{rate_val}]")
            it_voice.setData(Qt.ItemDataRole.UserRole + 1, sub_info)

        it_status = self.table.item(row, 7)
        if it_status:
            if has_audio:
                it_status.setText("Dubbed")
                it_status.setForeground(QColor("#34d399"))
            else:
                it_status.setText("Trans")
                it_status.setForeground(QColor("#38bdf8"))
        self.table.blockSignals(False)
        self.table.viewport().update()

    def _create_voice_cell_widget(self, orig_idx: int, dur_str: str, rate_val: str, has_audio: bool) -> QWidget:
        """Legacy helper kept for backwards compatibility"""
        widget = QWidget()
        return widget

    def _on_play_voice_line(self, orig_idx: int):
        """Triggers audio playback for the clicked subtitle line"""
        self._selected_idx = orig_idx
        self.highlight_active_subtitle(orig_idx)
        if self.on_listen_line:
            self.on_listen_line(orig_idx)

    def _toggle_line_gender(self, orig_idx: int):
        """Toggles character between Male and Female and refreshes voice cell"""
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return
        sub = self._subtitles_data[orig_idx]
        current_female = sub.get("gender") == "female" or "Sreymom" in str(sub.get("voice", "") or sub.get("voice_name", ""))
        new_female = not current_female
        sub["gender"] = "female" if new_female else "male"
        sub["voice_name"] = "km-KH-SreymomNeural" if new_female else "km-KH-PisethNeural"
        sub["voice"] = sub["voice_name"]
        # Invalidate audio cache so it gets synthesized with the new gender voice
        sub.pop("audio_file", None)
        sub.pop("audio_path", None)
        self.update_single_row_gender(orig_idx, new_female)
        self.update_single_row_voice(orig_idx, has_audio=False)
        if self.on_apply_edit:
            self.on_apply_edit(orig_idx, sub)

    def _set_line_gender(self, orig_idx: int, is_female: bool):
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return
        sub = self._subtitles_data[orig_idx]
        sub["gender"] = "female" if is_female else "male"
        sub["voice_name"] = "km-KH-SreymomNeural" if is_female else "km-KH-PisethNeural"
        sub["voice"] = sub["voice_name"]
        sub.pop("audio_file", None)
        sub.pop("audio_path", None)
        self.update_single_row_gender(orig_idx, is_female)
        self.update_single_row_voice(orig_idx, has_audio=False)
        if self.on_apply_edit:
            self.on_apply_edit(orig_idx, sub)

    def _set_line_actor(self, orig_idx: int, actor_name: str, is_female: bool = False):
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return
        sub = self._subtitles_data[orig_idx]
        sub["actor"] = actor_name
        sub["speaker"] = actor_name
        sub["gender"] = "female" if is_female else "male"
        sub["voice_name"] = "km-KH-SreymomNeural" if is_female else "km-KH-PisethNeural"
        sub["voice"] = sub["voice_name"]
        sub.pop("audio_file", None)
        sub.pop("audio_path", None)
        self.update_single_row_gender(orig_idx, is_female)
        self.update_single_row_voice(orig_idx, has_audio=False)
        if self.on_apply_edit:
            self.on_apply_edit(orig_idx, sub)

    def _set_selected_actor(self, actor_name: str, is_female: bool = False):
        for idx in self._selected_indices:
            self._set_line_actor(idx, actor_name, is_female)
        self._refresh_table()

    def _set_all_gender(self, is_female: bool):
        for idx, sub in enumerate(self._subtitles_data):
            sub["gender"] = "female" if is_female else "male"
            sub["voice_name"] = "km-KH-SreymomNeural" if is_female else "km-KH-PisethNeural"
            sub["voice"] = sub["voice_name"]
            sub.pop("audio_file", None)
            sub.pop("audio_path", None)
            if self.on_apply_edit:
                self.on_apply_edit(idx, sub)
        self._refresh_table()

    def _show_character_popup(self, orig_idx: int, btn: QWidget = None):
        """Displays quick Character selection popup menu"""
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return
        self._selected_idx = orig_idx
        sub = self._subtitles_data[orig_idx]
        is_female = sub.get("gender") == "female" or "Sreymom" in str(sub.get("voice", "") or sub.get("voice_name", ""))
        current_actor = sub.get("actor") or sub.get("speaker") or ("តួស្រី" if is_female else "តួប្រុស")

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e222b;
                border: 1px solid #363d4a;
                color: #f1f5f9;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        act_default = menu.addAction(f"{'✓ ' if 'តួទូទៅ' in current_actor else '   '}តួទូទៅ (Dialogue)")
        act_default.setIcon(get_users_icon(16, color="#94a3b8"))
        act_default.triggered.connect(lambda: self._set_line_actor(orig_idx, "តួទូទៅ (Dialogue)", False))

        act_m = menu.addAction(f"{'✓ ' if not is_female and current_actor in ('តួប្រុស', 'តួប្រុស (Male)') else '   '}តួអង្គប្រុស (Male - Piseth)")
        act_m.setIcon(get_male_icon(16))
        act_m.triggered.connect(lambda: self._set_line_actor(orig_idx, "តួប្រុស (Male)", False))

        act_f = menu.addAction(f"{'✓ ' if is_female and current_actor in ('តួស្រី', 'តួស្រី (Female)') else '   '}តួអង្គស្រី (Female - Sreymom)")
        act_f.setIcon(get_female_icon(16))
        act_f.triggered.connect(lambda: self._set_line_actor(orig_idx, "តួស្រី (Female)", True))

        menu.addSeparator()
        act_kid = menu.addAction(f"{'✓ ' if 'កូនក្មេង' in current_actor else '   '}តួកូនក្មេង (Child / Kid)")
        act_kid.setIcon(get_user_icon(16, color="#f59e0b"))
        act_kid.triggered.connect(lambda: self._set_line_actor(orig_idx, "តួកូនក្មេង (Kid)", False))

        act_spk_a = menu.addAction(f"{'✓ ' if current_actor == 'តួអង្គ A' else '   '}តួអង្គ A (Speaker A)")
        act_spk_a.setIcon(get_user_icon(16, color="#38bdf8"))
        act_spk_a.triggered.connect(lambda: self._set_line_actor(orig_idx, "តួអង្គ A", False))

        act_spk_b = menu.addAction(f"{'✓ ' if current_actor == 'តួអង្គ B' else '   '}តួអង្គ B (Speaker B)")
        act_spk_b.setIcon(get_user_icon(16, color="#f472b6"))
        act_spk_b.triggered.connect(lambda: self._set_line_actor(orig_idx, "តួអង្គ B", True))

        act_custom = menu.addAction("✏️ បញ្ចូលឈ្មោះតួអង្គថ្មី... (Custom Actor)")
        act_custom.setIcon(get_edit_icon(16))
        def _prompt_custom():
            val, ok = QInputDialog.getText(self, "ឈ្មោះតួអង្គ", "បញ្ចូលឈ្មោះតួអង្គថ្មី (ឧ. តួឯកប្រុស, តួឯកស្រី, តួអង្គ C):")
            if ok and val.strip():
                self._set_line_actor(orig_idx, val.strip(), False)
        act_custom.triggered.connect(_prompt_custom)

        menu.addSeparator()
        act_all_m = menu.addAction("កំណត់បន្ទាត់ទាំងអស់ជា 'ប្រុស'")
        act_all_m.setIcon(get_users_icon(16, color="#38bdf8"))
        act_all_m.triggered.connect(lambda: self._set_all_gender(False))

        act_all_f = menu.addAction("កំណត់បន្ទាត់ទាំងអស់ជា 'ស្រី'")
        act_all_f.setIcon(get_users_icon(16, color="#f472b6"))
        act_all_f.triggered.connect(lambda: self._set_all_gender(True))

        pos = btn.mapToGlobal(QPoint(0, btn.height())) if btn else QCursor.pos()
        menu.exec(pos)

    def _show_speed_popup(self, orig_idx: int, btn: QWidget = None):
        """Displays a quick speed rate selection popup menu anchored to the speed button or cursor"""
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return
        self._selected_idx = orig_idx
        sub = self._subtitles_data[orig_idx]
        current_rate = str(sub.get("rate") or "+0%")

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e222b;
                border: 1px solid #363d4a;
                color: #f1f5f9;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 20px 5px 12px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        act_auto = menu.addAction("គណនាតាមវិនាទី (Auto Sync)")
        act_auto.setIcon(get_sync_icon(16))
        act_auto.triggered.connect(lambda: self._apply_auto_sync_line(orig_idx))
        menu.addSeparator()

        speeds = [
            ("+0%", "Normal (ធម្មតា +0%)"),
            ("+10%", "Fast (+10%)"),
            ("+15%", "Fast (+15%)"),
            ("+20%", "Fast (+20%)"),
            ("+25%", "Fast (+25%)"),
            ("+30%", "Fast (+30%)"),
            ("-10%", "Slow (-10%)"),
            ("-20%", "Very Slow (-20%)")
        ]

        for r_val, r_lbl in speeds:
            prefix = "✓ " if r_val == current_rate else "   "
            act = menu.addAction(f"{prefix}{r_lbl}")
            act.setIcon(get_speed_icon(15, color="#38bdf8" if r_val == "+0%" else "#f59e0b"))
            act.triggered.connect(lambda checked=False, r=r_val: self._set_line_speed(orig_idx, r))

        menu.addSeparator()
        act_custom = menu.addAction("បញ្ចូលផ្ទាល់ខ្លួន (Custom Speed)")
        act_custom.setIcon(get_edit_icon(16))
        act_custom.triggered.connect(lambda: self._prompt_custom_speed(orig_idx))

        pos = btn.mapToGlobal(QPoint(0, btn.height())) if btn else QCursor.pos()
        menu.exec(pos)

    def _on_filter_changed(self, text: str):
        self._filter_text = text
        self._refresh_table()

    def highlight_active_subtitle(self, idx: int):
        """Highlights the currently playing subtitle line smoothly"""
        if idx < 0 or idx >= len(self._subtitles_data):
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == idx:
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                self.table.blockSignals(False)
                break

    def _on_table_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            self._selected_idx = -1
            self._selected_indices = []
            if self.on_select_multiple_subs:
                self.on_select_multiple_subs([])
            return

        selected_indices = []
        for r in selected_rows:
            it = self.table.item(r.row(), 0)
            if it:
                idx = it.data(Qt.ItemDataRole.UserRole)
                if idx is not None:
                    selected_indices.append(idx)

        if selected_indices:
            self._selected_idx = selected_indices[0]
            self._selected_indices = selected_indices
            if self.on_select_sub:
                self.on_select_sub(self._selected_idx)
            if self.on_select_multiple_subs:
                self.on_select_multiple_subs(selected_indices)

    def select_indices(self, indices: list):
        """Programmatically select multiple rows without feedback loops"""
        if not self._idx_to_row:
            return
        self.table.blockSignals(True)
        try:
            self.table.clearSelection()
            first_row = None
            for idx in indices:
                row = self._idx_to_row.get(idx)
                if row is not None and 0 <= row < self.table.rowCount():
                    if first_row is None:
                        first_row = row
                    self.table.selectRow(row)
            if first_row is not None:
                item = self.table.item(first_row, 0)
                if item:
                    self.table.scrollToItem(item)
            self._selected_indices = list(indices)
            if indices:
                self._selected_idx = indices[0]
            else:
                self._selected_idx = -1
        finally:
            self.table.blockSignals(False)

    def get_selected_indices(self) -> list:
        return list(self._selected_indices)

    def _on_item_changed(self, item):
        row = item.row()
        col = item.column()
        it_idx = self.table.item(row, 0)
        if not it_idx:
            return
        orig_idx = it_idx.data(Qt.ItemDataRole.UserRole)
        if orig_idx is None or not (0 <= orig_idx < len(self._subtitles_data)):
            return
        sub = self._subtitles_data[orig_idx]
        if col == 2:  # Original Text
            sub["orig_text"] = item.text().strip()
            if self.on_apply_edit:
                self.on_apply_edit(orig_idx, sub)
        elif col == 3:  # Khmer Translation
            new_text = item.text().strip()
            old_text = (sub.get("khmer_text") or "").strip()
            if new_text != old_text:
                sub["khmer_text"] = new_text
                # Reset old audio so editing translation guarantees new audio file is generated
                sub.pop("audio_file", None)
                sub.pop("audio_path", None)
                sub["status"] = "translated"
                self.update_single_row_voice(orig_idx, has_audio=False)
            if self.on_apply_edit:
                self.on_apply_edit(orig_idx, sub)

    def _load_into_editor(self, idx: int):
        pass

    def _shift_timing(self, delta_s: float):
        if self._selected_idx < 0 or self._selected_idx >= len(self._subtitles_data):
            return
        sub = self._subtitles_data[self._selected_idx]
        sub["start"] = max(0.0, sub.get("start", 0) + delta_s)
        sub["end"] = max(sub["start"] + 0.1, sub.get("end", 0) + delta_s)
        self._refresh_table()
        if self.on_apply_edit:
            self.on_apply_edit(self._selected_idx, sub)

    # ------------------ CONTEXT MENU (RIGHT-CLICK ACTIONS) ------------------
    def show_context_menu_for_index(self, orig_idx: int, global_pos: QPoint):
        """Pops up the rich studio context menu for a specific line at global_pos (called from Timeline)"""
        if not (0 <= orig_idx < len(self._subtitles_data)):
            return
        if orig_idx not in self._selected_indices:
            self.select_indices([orig_idx])
        self._popup_context_menu(orig_idx, global_pos)

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        it_idx = self.table.item(row, 0)
        if not it_idx:
            return
        orig_idx = it_idx.data(Qt.ItemDataRole.UserRole)
        if orig_idx is None or not (0 <= orig_idx < len(self._subtitles_data)):
            return

        if orig_idx not in self._selected_indices:
            self.select_indices([orig_idx])

        global_pos = self.table.viewport().mapToGlobal(pos)
        self._popup_context_menu(orig_idx, global_pos)

    def _popup_context_menu(self, orig_idx: int, global_pos: QPoint):
        self._selected_idx = orig_idx
        sub = self._subtitles_data[orig_idx]
        current_rate = sub.get("rate", "+0%")

        menu = QMenu(self)

        # Batch Actions when multiple rows are selected
        if len(self._selected_indices) > 1:
            n_sel = len(self._selected_indices)
            menu_batch = menu.addMenu(f"✨ Batch Actions ({n_sel} Lines Selected)")
            menu_batch.setIcon(get_users_icon(16, color="#facc15"))

            act_b_dub = menu_batch.addAction(f"🎙️ Dub Selected ({n_sel} Lines)")
            act_b_dub.setIcon(get_dub_icon(16))
            act_b_dub.triggered.connect(self._dub_batch_selected)

            act_b_fit = menu_batch.addAction(f"⏱️ Fit Duration to Voice ({n_sel} Lines)")
            act_b_fit.setIcon(get_sync_icon(16, color="#34d399"))
            act_b_fit.triggered.connect(self._on_fit_duration_clicked)

            act_b_male = menu_batch.addAction(f"👨 Set All Selected to Male (ប្រុស)")
            act_b_male.setIcon(get_male_icon(16))
            act_b_male.triggered.connect(lambda: self._set_selected_gender(False))

            act_b_female = menu_batch.addAction(f"👩 Set All Selected to Female (ស្រី)")
            act_b_female.setIcon(get_female_icon(16))
            act_b_female.triggered.connect(lambda: self._set_selected_gender(True))

            act_b_del = menu_batch.addAction(f"🗑️ Delete All Selected ({n_sel} Lines)")
            act_b_del.setIcon(get_trash_icon(16))
            act_b_del.triggered.connect(self._delete_batch_selected)

            menu_b_actor = menu_batch.addMenu("🎭 កំណត់តួអង្គលើជួរដែលបានជ្រើស (Assign Character)...")
            menu_b_actor.setIcon(get_user_icon(16, color="#facc15"))
            act_b_a = menu_b_actor.addAction("តួអង្គ A (Speaker A)")
            act_b_a.triggered.connect(lambda: self._set_selected_actor("តួអង្គ A", False))
            act_b_b = menu_b_actor.addAction("តួអង្គ B (Speaker B)")
            act_b_b.triggered.connect(lambda: self._set_selected_actor("តួអង្គ B", True))
            act_b_kid = menu_b_actor.addAction("តួកូនក្មេង (Kid)")
            act_b_kid.triggered.connect(lambda: self._set_selected_actor("តួកូនក្មេង (Kid)", False))
            act_b_custom = menu_b_actor.addAction("✏️ ឈ្មោះតួអង្គថ្មី... (Custom Actor)")
            def _prompt_batch_actor():
                val, ok = QInputDialog.getText(self, "ឈ្មោះតួអង្គ", f"បញ្ចូលឈ្មោះតួអង្គសម្រាប់ {len(self._selected_indices)} បន្ទាត់:")
                if ok and val.strip():
                    self._set_selected_actor(val.strip(), False)
            act_b_custom.triggered.connect(_prompt_batch_actor)

            menu.addSeparator()

        # Direct sync to timeline voice line
        act_focus_tl = menu.addAction("📍 Show Line Voice in Timeline (បង្ហាញលើបន្ទាត់សំឡេង Timeline)")
        act_focus_tl.setIcon(get_mic_icon(16))
        def _focus_tl():
            if self.on_select_sub:
                self.on_select_sub(orig_idx)
        act_focus_tl.triggered.connect(_focus_tl)
        menu.addSeparator()

        # 0. Character Role Submenu (តួអង្គ ប្រុស / ស្រី)
        curr_is_female = sub.get("gender") == "female" or "Sreymom" in str(sub.get("voice", "") or sub.get("voice_name", ""))
        menu_role = menu.addMenu(f"តួអង្គ: {'ស្រី (Sreymom)' if curr_is_female else 'ប្រុស (Piseth)'}")
        menu_role.setIcon(get_female_icon(16) if curr_is_female else get_male_icon(16))
        
        act_set_male = menu_role.addAction("កំណត់ជា: តួអង្គប្រុស (Male - Piseth)")
        act_set_male.setIcon(get_male_icon(16))
        act_set_male.triggered.connect(lambda: self._set_line_gender(orig_idx, False))

        act_set_female = menu_role.addAction("កំណត់ជា: តួអង្គស្រី (Female - Sreymom)")
        act_set_female.setIcon(get_female_icon(16))
        act_set_female.triggered.connect(lambda: self._set_line_gender(orig_idx, True))

        menu_role.addSeparator()
        act_all_male = menu_role.addAction("កំណត់បន្ទាត់ទាំងអស់ជា 'ប្រុស'")
        act_all_male.setIcon(get_users_icon(16, color="#38bdf8"))
        act_all_male.triggered.connect(lambda: self._set_all_gender(False))

        act_all_female = menu_role.addAction("កំណត់បន្ទាត់ទាំងអស់ជា 'ស្រី'")
        act_all_female.setIcon(get_users_icon(16, color="#f472b6"))
        act_all_female.triggered.connect(lambda: self._set_all_gender(True))

        menu_role.addSeparator()
        act_toggle = menu_role.addAction("ប្តូរ ប្រុស <-> ស្រី (Toggle)")
        act_toggle.setIcon(get_swap_icon(16))
        act_toggle.triggered.connect(lambda: self._toggle_line_gender(orig_idx))

        menu.addSeparator()

        # 1. Edit Speed Voice (ល្បឿនសំឡេង) Submenu
        menu_speed = menu.addMenu(f"Edit Speed Voice (ល្បឿនបច្ចុប្បន្ន: {current_rate})")
        menu_speed.setIcon(get_speed_icon(16))
        
        act_auto = menu_speed.addAction("Auto-Sync Rate (គណនាល្បឿនស្វ័យប្រវត្តិតាមវិនាទី)")
        act_auto.setIcon(get_sync_icon(16))
        act_auto.triggered.connect(lambda: self._apply_auto_sync_line(orig_idx))
        menu_speed.addSeparator()

        speeds = [
            ("+0%", "1.0x (ធម្មតា / Normal +0%)"),
            ("+10%", "1.1x (+10% រហ័សបន្តិច)"),
            ("+15%", "1.15x (+15%)"),
            ("+20%", "1.2x (+20% លឿនល្មម)"),
            ("+25%", "1.25x (+25%)"),
            ("-10%", "0.9x (-10% យឺតបន្តិច)"),
            ("-20%", "0.8x (-20% យឺត)"),
        ]
        for rate_val, rate_label in speeds:
            prefix = "✓ " if rate_val == current_rate else ""
            act = menu_speed.addAction(f"{prefix}{rate_label}")
            act.setIcon(get_speed_icon(15, color="#38bdf8" if rate_val == "+0%" else "#f59e0b"))
            act.triggered.connect(lambda checked=False, r=rate_val: self._set_line_speed(orig_idx, r))

        menu_speed.addSeparator()
        act_custom_speed = menu_speed.addAction("Custom Speed %... (បញ្ចូលផ្ទាល់ខ្លួន)")
        act_custom_speed.setIcon(get_edit_icon(16))
        act_custom_speed.triggered.connect(lambda: self._prompt_custom_speed(orig_idx))

        # 2. Change Voice Model Submenu
        menu_voice = menu.addMenu("Change Voice Model (ប្ដូរសំឡេងតួអង្គ)")
        menu_voice.setIcon(get_mic_icon(16))
        voices = [
            ("km-KH-PisethNeural", "km-KH-PisethNeural (ប្រុស - ពិសិដ្ឋ)", False),
            ("km-KH-SreymomNeural", "km-KH-SreymomNeural (ស្រី - ស្រីមុំ)", True),
            ("Google Cloud: km-KH-Standard-A (ស្រី)", "Google Cloud km-KH-Standard-A (ស្រី)", True),
            ("Google Cloud: km-KH-Standard-B (ប្រុស)", "Google Cloud km-KH-Standard-B (ប្រុស)", False),
            ("Gemini-Voice", "Gemini 2.0 AI Audio Voice", False),
        ]
        curr_v = sub.get("voice", "")
        for v_code, v_label, is_fem in voices:
            prefix = "✓ " if v_code == curr_v else ""
            act_v = menu_voice.addAction(f"{prefix}{v_label}")
            act_v.setIcon(get_female_icon(16) if is_fem else get_male_icon(16))
            act_v.triggered.connect(lambda checked=False, v=v_code: self._set_line_voice(orig_idx, v))

        menu.addSeparator()

        # 3. Dub This Line
        act_dub = menu.addAction("Dub This Line (បញ្ចូលសំឡេងបន្ទាត់នេះ)")
        act_dub.setIcon(get_dub_icon(16))
        act_dub.triggered.connect(lambda: self._on_dub_sel_clicked())

        # 4. Listen Audio
        act_listen = menu.addAction("Listen Audio (ស្ដាប់សំឡេង)")
        act_listen.setIcon(get_listen_icon(16))
        act_listen.triggered.connect(lambda: self._on_listen_clicked())

        # 5. Translate to Khmer Submenu
        menu_trans = menu.addMenu("Translate to Khmer (បកប្រែជាភាសាខ្មែរ)")
        menu_trans.setIcon(get_translate_icon(16))

        act_t_google = menu_trans.addAction("Google Translate (Free / មិនអស់លុយ - លឿន)")
        act_t_google.setIcon(get_translate_icon(16, color="#38bdf8"))
        act_t_google.triggered.connect(lambda: self._on_trans_single_clicked("Google (Free / មិនអស់លុយ)"))

        menu_gemini = menu_trans.addMenu("Google Gemini AI (បកប្រែតាមបែបតួអង្គ)")
        menu_gemini.setIcon(get_ai_icon(16))
        act_gem_std = menu_gemini.addAction("ធម្មតា (Standard Drama)")
        act_gem_std.triggered.connect(lambda: self._on_trans_single_clicked("Gemini / Google AI (API Key)", "ធម្មតា (Standard)"))
        act_gem_com = menu_gemini.addAction("កំប្លែង រស់រវើក (Comedy Dubbing)")
        act_gem_com.triggered.connect(lambda: self._on_trans_single_clicked("Gemini / Google AI (API Key)", "កំប្លែង រស់រវើក (Comedy)"))
        act_gem_wux = menu_gemini.addAction("រឿងបុរាណ / ក្បាច់គុន (Ancient Wuxia)")
        act_gem_wux.triggered.connect(lambda: self._on_trans_single_clicked("Gemini / Google AI (API Key)", "រឿងបុរាណ / ក្បាច់គុន (Wuxia)"))
        act_gem_nat = menu_gemini.addAction("ភាពយន្តធម្មជាតិ (Natural Conversational)")
        act_gem_nat.triggered.connect(lambda: self._on_trans_single_clicked("Gemini / Google AI (API Key)", "ភាពយន្តធម្មជាតិ (Natural Drama)"))

        act_t_gpt = menu_trans.addAction("OpenAI ChatGPT (GPT-4o Mini / API Key)")
        act_t_gpt.setIcon(get_bot_icon(16, color="#10b981"))
        act_t_gpt.triggered.connect(lambda: self._on_trans_single_clicked("OpenAI ChatGPT (API Key)"))

        menu_trans.addSeparator()

        # --- Groq ---
        menu_groq = menu_trans.addMenu("Groq (LLaMA 3.3 / Ultra Fast)")
        menu_groq.setIcon(get_bot_icon(16, color="#f59e0b"))
        act_groq_std = menu_groq.addAction("ធម្មតា (Standard)")
        act_groq_std.triggered.connect(lambda: self._on_trans_single_clicked("Groq (LLaMA Fast)", "ធម្មតា (Standard)"))
        act_groq_com = menu_groq.addAction("កំប្លែង រស់រវើក (Comedy)")
        act_groq_com.triggered.connect(lambda: self._on_trans_single_clicked("Groq (LLaMA Fast)", "កំប្លែង រស់រវើក (Comedy)"))
        act_groq_wux = menu_groq.addAction("រឿងបុរាណ / ក្បាច់គុន (Wuxia)")
        act_groq_wux.triggered.connect(lambda: self._on_trans_single_clicked("Groq (LLaMA Fast)", "រឿងបុរាណ / ក្បាច់គុន (Wuxia)"))

        # --- OpenRouter ---
        menu_router = menu_trans.addMenu("OpenRouter (Claude / GPT-4o / Llama)")
        menu_router.setIcon(get_ai_icon(16, color="#a855f7"))
        act_router_std = menu_router.addAction("ធម្មតា (Standard)")
        act_router_std.triggered.connect(lambda: self._on_trans_single_clicked("OpenRouter (Multi-Model)", "ធម្មតា (Standard)"))
        act_router_com = menu_router.addAction("កំប្លែង រស់រវើក (Comedy)")
        act_router_com.triggered.connect(lambda: self._on_trans_single_clicked("OpenRouter (Multi-Model)", "កំប្លែង រស់រវើក (Comedy)"))
        act_router_wux = menu_router.addAction("រឿងបុរាណ / ក្បាច់គុន (Wuxia)")
        act_router_wux.triggered.connect(lambda: self._on_trans_single_clicked("OpenRouter (Multi-Model)", "រឿងបុរាណ / ក្បាច់គុន (Wuxia)"))

        # --- NVIDIA NIM ---
        menu_nvidia = menu_trans.addMenu("NVIDIA NIM (LLaMA 3.1 GPU)")
        menu_nvidia.setIcon(get_bot_icon(16, color="#34d399"))
        act_nv_std = menu_nvidia.addAction("ធម្មតា (Standard)")
        act_nv_std.triggered.connect(lambda: self._on_trans_single_clicked("NVIDIA NIM (LLaMA GPU)", "ធម្មតា (Standard)"))
        act_nv_com = menu_nvidia.addAction("កំប្លែង រស់រវើក (Comedy)")
        act_nv_com.triggered.connect(lambda: self._on_trans_single_clicked("NVIDIA NIM (LLaMA GPU)", "កំប្លែង រស់រវើក (Comedy)"))
        act_nv_wux = menu_nvidia.addAction("រឿងបុរាណ / ក្បាច់គុន (Wuxia)")
        act_nv_wux.triggered.connect(lambda: self._on_trans_single_clicked("NVIDIA NIM (LLaMA GPU)", "រឿងបុរាណ / ក្បាច់គុន (Wuxia)"))

        menu_trans.addSeparator()
        act_t_mymem = menu_trans.addAction("MyMemory Free (បម្រុងទុក Failover)")
        act_t_mymem.setIcon(get_translate_icon(16, color="#94a3b8"))
        act_t_mymem.triggered.connect(lambda: self._on_trans_single_clicked("MyMemory (Free / មិនអស់លុយ)"))

        menu_trans.addSeparator()
        act_t_curr = menu_trans.addAction("Translate with Current Toolbar Setting (តាមរបារខាងលើ)")
        act_t_curr.setIcon(get_translate_icon(16, color="#06b6d4"))
        act_t_curr.triggered.connect(lambda: self._on_trans_single_clicked())

        menu.addSeparator()

        # 6. Timing Adjustment Submenu
        menu_timing = menu.addMenu("Adjust Timing / Offset (កែសម្រួលពេលវេលា)")
        menu_timing.setIcon(get_clock_icon(16))
        act_m05 = menu_timing.addAction("Shift -0.5s (រំកិលថយក្រោយ)")
        act_m05.setIcon(get_rewind_icon(16))
        act_m05.triggered.connect(lambda: self._shift_timing_line(orig_idx, -0.5))
        act_p05 = menu_timing.addAction("Shift +0.5s (រំកិលទៅមុខ)")
        act_p05.setIcon(get_forward_icon(16))
        act_p05.triggered.connect(lambda: self._shift_timing_line(orig_idx, 0.5))
        act_ext = menu_timing.addAction("Extend Duration +0.5s (ពន្យារពេល)")
        act_ext.setIcon(get_plus_icon(16))
        act_ext.triggered.connect(lambda: self._extend_timing_line(orig_idx, 0.5))
        act_trim = menu_timing.addAction("Shorten Duration -0.5s (បន្ថយពេល)")
        act_trim.setIcon(get_minus_icon(16))
        act_trim.triggered.connect(lambda: self._extend_timing_line(orig_idx, -0.5))
        act_fit_v = menu_timing.addAction("⏱️ ពង្រីកពេលវេលាឱ្យល្មមសំឡេង (Fit Duration to Voice)")
        act_fit_v.setIcon(get_sync_icon(16, color="#34d399"))
        act_fit_v.triggered.connect(lambda: self._fit_duration_to_voice(orig_idx))
        menu_timing.addSeparator()
        act_fix_all = menu_timing.addAction("កែសម្រួលបន្ទាត់ជាន់គ្នាទាំងអស់ (Fix All Overlaps)")
        act_fix_all.setIcon(get_sync_icon(16))
        act_fix_all.triggered.connect(self._on_fix_overlaps_clicked)
        menu_timing.addSeparator()
        act_custom_t = menu_timing.addAction("Edit Timing... (កែម៉ោង Start / End)")
        act_custom_t.setIcon(get_edit_icon(16))
        act_custom_t.triggered.connect(lambda: self._prompt_custom_timing(orig_idx))

        menu.addSeparator()

        # 7. Copy Text
        act_cp_km = menu.addAction("Copy Khmer Text (ចម្លងអត្ថបទខ្មែរ)")
        act_cp_km.setIcon(get_copy_icon(16))
        act_cp_km.triggered.connect(lambda: self._copy_to_clipboard(sub.get("khmer_text", "")))

        act_cp_orig = menu.addAction("Copy Original Text (ចម្លងអត្ថបទដើម)")
        act_cp_orig.setIcon(get_copy_icon(16))
        act_cp_orig.triggered.connect(lambda: self._copy_to_clipboard(sub.get("orig_text", "") or sub.get("text", "")))

        menu.addSeparator()

        # 8. Insert / Delete
        act_ins_above = menu.addAction("Insert Line Above (បញ្ចូលបន្ទាត់ពីលើ)")
        act_ins_above.setIcon(get_plus_icon(16, color="#34d399"))
        act_ins_above.triggered.connect(lambda: self._insert_line_at(orig_idx, above=True))

        act_ins_below = menu.addAction("Insert Line Below (បញ្ចូលបន្ទាត់ពីក្រោម)")
        act_ins_below.setIcon(get_plus_icon(16, color="#38bdf8"))
        act_ins_below.triggered.connect(lambda: self._insert_line_at(orig_idx, above=False))

        act_del = menu.addAction("Delete Subtitle Line (លុบบន្ទាត់នេះ)")
        act_del.setIcon(get_trash_icon(16))
        act_del.triggered.connect(lambda: self._delete_line_at(orig_idx))

        menu.exec(global_pos)

    def _set_selected_gender(self, is_female: bool):
        for idx in list(self._selected_indices):
            self._set_line_gender(idx, is_female)

    def _dub_batch_selected(self):
        if self.on_dub_selected:
            for idx in list(self._selected_indices):
                self.on_dub_selected(idx)

    def _delete_batch_selected(self):
        if not self._selected_indices:
            return
        ans = QMessageBox.question(
            self,
            "Delete Selected Subtitles",
            f"Are you sure you want to delete {len(self._selected_indices)} selected subtitle lines?\n(តើអ្នកពិតជាចង់លុប {len(self._selected_indices)} បន្ទាត់ដែលបានជ្រើសរើសមែនទេ?)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            for idx in sorted(self._selected_indices, reverse=True):
                if self.on_delete_sub:
                    self.on_delete_sub(idx)
            self._selected_indices = []

    def _set_line_speed(self, idx: int, rate: str):
        if 0 <= idx < len(self._subtitles_data):
            self._subtitles_data[idx]["rate"] = rate
            self._refresh_table()
            if self.on_apply_edit:
                self.on_apply_edit(idx, self._subtitles_data[idx])

    def _apply_auto_sync_line(self, idx: int):
        if self.on_auto_sync_single and 0 <= idx < len(self._subtitles_data):
            self.on_auto_sync_single(idx)

    def _prompt_custom_speed(self, idx: int):
        if not (0 <= idx < len(self._subtitles_data)):
            return
        curr = self._subtitles_data[idx].get("rate", "+0%")
        text, ok = QInputDialog.getText(
            self,
            "Custom Speech Speed",
            f"Enter speed rate percentage for Line #{idx+1} (e.g. +15%, +35%, -10%):",
            text=curr
        )
        if ok and text.strip():
            r = text.strip()
            if not r.startswith(("+", "-")):
                r = f"+{r}"
            if not r.endswith("%"):
                r = f"{r}%"
            self._set_line_speed(idx, r)

    def _set_line_voice(self, idx: int, voice: str):
        if 0 <= idx < len(self._subtitles_data):
            self._subtitles_data[idx]["voice"] = voice
            if "Sreymom" in voice or "Standard-A" in voice or "ស្រី" in voice:
                self._subtitles_data[idx]["gender"] = "female"
                self._subtitles_data[idx]["voice_name"] = "km-KH-SreymomNeural"
            else:
                self._subtitles_data[idx]["gender"] = "male"
                self._subtitles_data[idx]["voice_name"] = "km-KH-PisethNeural"
            self._subtitles_data[idx].pop("audio_file", None)
            self._subtitles_data[idx].pop("audio_path", None)
            self._refresh_table()
            if self.on_apply_edit:
                self.on_apply_edit(idx, self._subtitles_data[idx])

    def _shift_timing_line(self, idx: int, delta: float):
        if 0 <= idx < len(self._subtitles_data):
            sub = self._subtitles_data[idx]
            sub["start"] = max(0.0, sub.get("start", 0.0) + delta)
            sub["end"] = max(sub["start"] + 0.1, sub.get("end", 0.0) + delta)
            self._refresh_table()
            if self.on_apply_edit:
                self.on_apply_edit(idx, sub)

    def _extend_timing_line(self, idx: int, delta: float):
        if 0 <= idx < len(self._subtitles_data):
            sub = self._subtitles_data[idx]
            sub["end"] = max(sub.get("start", 0.0) + 0.2, sub.get("end", 0.0) + delta)
            self._refresh_table()
            if self.on_apply_edit:
                self.on_apply_edit(idx, sub)

    def _fit_duration_to_voice(self, idx: int):
        if not (0 <= idx < len(self._subtitles_data)):
            return
        from services.dubbing.timing_ducking import get_audio_duration
        sub = self._subtitles_data[idx]
        audio_file = sub.get("audio_file") or sub.get("audio_path")
        dur = 0.0
        if audio_file and os.path.exists(audio_file):
            dur = get_audio_duration(audio_file)
        elif sub.get("audio_dur"):
            try:
                dur = float(sub["audio_dur"])
            except Exception:
                pass
        else:
            km_text = sub.get("khmer_text") or sub.get("translated") or ""
            if km_text:
                char_count = len(km_text.replace(" ", "").replace("\n", ""))
                dur = max(1.2, char_count / 10.5)

        if dur > 0.3:
            st = float(sub.get("start", 0.0))
            sub["end"] = round(st + dur + 0.1, 2)
            self._refresh_table()
            if self.on_apply_edit:
                self.on_apply_edit(idx, sub)

    def _on_fit_duration_clicked(self):
        """Fits subtitle duration to match voice audio for selected lines (or all lines)"""
        if not self._subtitles_data:
            return
        from services.dubbing.timing_ducking import get_audio_duration
        targets = self._selected_indices if self._selected_indices else list(range(len(self._subtitles_data)))
        count = 0
        for idx in targets:
            if not (0 <= idx < len(self._subtitles_data)):
                continue
            sub = self._subtitles_data[idx]
            audio_file = sub.get("audio_file") or sub.get("audio_path")
            dur = 0.0
            if audio_file and os.path.exists(audio_file):
                dur = get_audio_duration(audio_file)
            elif sub.get("audio_dur"):
                try:
                    dur = float(sub["audio_dur"])
                except Exception:
                    pass
            else:
                km_text = sub.get("khmer_text") or sub.get("translated") or ""
                if km_text:
                    char_count = len(km_text.replace(" ", "").replace("\n", ""))
                    dur = max(1.2, char_count / 10.5)

            if dur > 0.3:
                st = float(sub.get("start", 0.0))
                curr_end = float(sub.get("end", st + 1.0))
                new_end = round(st + dur + 0.1, 2)
                if new_end > curr_end:
                    sub["end"] = new_end
                    count += 1
                    if self.on_apply_edit:
                        self.on_apply_edit(idx, sub)

        if count > 0:
            self._refresh_table()

    def _prompt_custom_timing(self, idx: int):
        if not (0 <= idx < len(self._subtitles_data)):
            return
        sub = self._subtitles_data[idx]
        st_str = format_timestamp(sub.get("start", 0.0))
        en_str = format_timestamp(sub.get("end", 0.0))
        curr_val = f"{st_str} -> {en_str}"
        val, ok = QInputDialog.getText(
            self,
            "Edit Subtitle Timing",
            f"Enter timing for Line #{idx+1} (Format: 00:00:02,200 -> 00:00:04,400):",
            text=curr_val
        )
        if ok and "->" in val:
            parts = val.split("->")
            try:
                s = parse_timestamp_to_seconds(parts[0].strip())
                e = parse_timestamp_to_seconds(parts[1].strip())
                if e > s:
                    sub["start"] = s
                    sub["end"] = e
                    self._refresh_table()
                    if self.on_apply_edit:
                        self.on_apply_edit(idx, sub)
            except Exception:
                pass

    def _copy_to_clipboard(self, text: str):
        if text:
            QApplication.clipboard().setText(text)

    def _insert_line_at(self, idx: int, above: bool = False):
        if not (0 <= idx < len(self._subtitles_data)):
            return
        ref_sub = self._subtitles_data[idx]
        insert_pos = idx if above else idx + 1
        new_start = max(0.0, ref_sub.get("start", 0.0) - 1.0) if above else ref_sub.get("end", 0.0)
        new_end = new_start + 2.0
        new_sub = {
            "start": round(new_start, 3),
            "end": round(new_end, 3),
            "orig_text": "New dialogue line",
            "khmer_text": "",
            "rate": "+0%",
            "status": "raw"
        }
        self._subtitles_data.insert(insert_pos, new_sub)
        self._refresh_table()
        if self.on_apply_edit:
            self.on_apply_edit(insert_pos, new_sub)

    def _delete_line_at(self, idx: int):
        if 0 <= idx < len(self._subtitles_data):
            del self._subtitles_data[idx]
            self._refresh_table()
            if self.on_delete_sub:
                self.on_delete_sub(idx)

    # ------------------ PANEL VISIBILITY CONTROLLERS ------------------
    def _on_toggle_tl_clicked(self):
        if self.on_toggle_timeline:
            self.on_toggle_timeline()

    def _on_toggle_logs_clicked(self):
        if self.on_toggle_logs:
            self.on_toggle_logs()

    def set_timeline_visible_state(self, visible: bool):
        if getattr(self, "btn_toggle_tl", None):
            self.btn_toggle_tl.setChecked(visible)

    def set_logs_visible_state(self, visible: bool):
        if getattr(self, "btn_toggle_logs", None):
            self.btn_toggle_logs.setChecked(visible)

    # ------------------ CALLBACK TRIGGERS ------------------
    def _on_sync_all_clicked(self):
        if self.on_auto_sync_all:
            self.on_auto_sync_all()

    def _on_sync_single_clicked(self):
        if self.on_auto_sync_single and self._selected_idx >= 0:
            self.on_auto_sync_single(self._selected_idx)

    def _on_import_srt_clicked(self):
        if self.on_import_srt:
            self.on_import_srt()

    def _on_capture_cc_clicked(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e222b;
                border: 1px solid #363d4a;
                color: #f1f5f9;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        act_whisperx = menu.addAction("🎯 WhisperX (AI Diarization - បំបែកសំឡេងតួអង្គ A/B + Word Timestamps)")
        act_whisperx.triggered.connect(lambda: self.on_capture_cc("whisperx") if self.on_capture_cc else None)
        act_whisper = menu.addAction("⚡ Faster-Whisper (Multi-Language / ភាសាចម្រុះ)")
        act_whisper.triggered.connect(lambda: self.on_capture_cc("whisper") if self.on_capture_cc else None)
        act_funasr = menu.addAction("🇨🇳 SenseVoice-Small + CAM++ (Alibaba - ASR + Emotion SER + Events + Diarization)")
        act_funasr.triggered.connect(lambda: self.on_capture_cc("funasr") if self.on_capture_cc else None)
        btn = self.sender()
        if btn and hasattr(btn, "mapToGlobal"):
            pos = btn.mapToGlobal(QPoint(0, btn.height()))
        else:
            pos = QCursor.pos()
        menu.exec(pos)

    def _on_trans_all_clicked(self):
        if self.on_translate_all:
            self.on_translate_all()

    def _on_trans_single_clicked(self, provider: str = None, style: str = None):
        if self.on_translate_single and self._selected_idx >= 0:
            self.on_translate_single(self._selected_idx, provider=provider, style=style)

    def _on_listen_clicked(self):
        if self.on_listen_line and self._selected_idx >= 0:
            self.on_listen_line(self._selected_idx)

    def _on_add_sub_clicked(self):
        if self.on_add_sub:
            self.on_add_sub()

    def _on_delete_sub_clicked(self):
        if self.on_delete_sub and self._selected_idx >= 0:
            self.on_delete_sub(self._selected_idx)

    def _on_fix_overlaps_clicked(self):
        if self.on_fix_overlaps:
            self.on_fix_overlaps()

    def _on_dub_all_clicked(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e222b;
                border: 1px solid #363d4a;
                color: #f1f5f9;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        # 1. Primary Dubbing Actions (Uses Voice Cast configuration)
        act_all = menu.addAction("🚀 បញ្ចូលសំឡេងទាំងអស់ (Dub All Lines - តាម Voice Cast)")
        act_all.triggered.connect(lambda: self.on_dub_all() if self.on_dub_all else None)

        act_miss = menu.addAction("🎙️ បំពេញសំឡេងដែលខ្វះ (Dub Missing Lines)")
        act_miss.triggered.connect(self._on_dub_missing_clicked)

        menu.addSeparator()

        # 2. Edge-TTS Fallback Voices Only (Piseth & Sreymom)
        current_v = getattr(self, "_current_voice", VOICE_MODEL_OPTIONS[0])
        for opt in VOICE_MODEL_OPTIONS:
            prefix = "✓ " if opt == current_v else "   "
            act = menu.addAction(f"{prefix}{opt}")
            act.triggered.connect(lambda checked=False, v=opt: self._select_voice_and_dub(v))

        menu.addSeparator()

        act_sync = menu.addAction("🔄 Auto-Sync All Duration (តម្រឹមល្បឿនស្វ័យប្រវត្តិ)")
        act_sync.triggered.connect(self._on_sync_all_clicked)

        act_clear = menu.addAction("🗑️ លុបសំឡេងចេញទាំងអស់ (Clear Dubbing)")
        act_clear.triggered.connect(self._on_dub_sel_clicked)

        menu.addSeparator()

        auto_dub_active = getattr(self, "_auto_dub", True)
        ad_prefix = "✓ " if auto_dub_active else "   "
        act_autodub = menu.addAction(f"{ad_prefix}Auto-Dub (បញ្ចូលសំឡេងស្វ័យប្រវត្តិពេលបកប្រែ)")
        act_autodub.triggered.connect(self._toggle_auto_dub)

        btn = self.sender()
        if btn and hasattr(btn, "mapToGlobal"):
            pos = btn.mapToGlobal(QPoint(0, btn.height()))
        else:
            pos = QCursor.pos()
        menu.exec(pos)

    def _select_voice_and_dub(self, voice_name: str):
        self._current_voice = voice_name
        self._on_voice_changed()
        if self.on_dub_all:
            self.on_dub_all()

    def _toggle_auto_dub(self):
        self._auto_dub = not getattr(self, "_auto_dub", True)

    def _on_dub_sel_clicked(self):
        if self.on_dub_selected and self._selected_idx >= 0:
            self.on_dub_selected(self._selected_idx)

    def _on_dub_missing_clicked(self):
        if self.on_dub_missing:
            self.on_dub_missing()

    def _on_voice_changed(self, idx: int = 0):
        val = getattr(self, "_current_voice", VOICE_MODEL_OPTIONS[0])
        if self.on_voice_change:
            self.on_voice_change(val)

    @property
    def combo_voice(self):
        class _VoiceProxy:
            def __init__(self, parent):
                self._p = parent
            def currentText(self):
                return getattr(self._p, "_current_voice", VOICE_MODEL_OPTIONS[0])
            def setCurrentText(self, val):
                self._p._current_voice = val
        return _VoiceProxy(self)

    @property
    def check_auto_dub(self):
        class _AutoDubProxy:
            def __init__(self, parent):
                self._p = parent
            def isChecked(self):
                return getattr(self._p, "_auto_dub", True)
            def setChecked(self, val):
                self._p._auto_dub = bool(val)
        return _AutoDubProxy(self)

    def _on_speed_changed(self, idx: int = 0):
        val = self.combo_speed.currentText() if hasattr(self, "combo_speed") else "1.00x (ល្បឿនដើម - Standard Normal)"
        if self.on_voice_speed_change:
            self.on_voice_speed_change(val)

    def _on_provider_changed(self, provider_text: str = None):
        """Hides style selector when Google Translate or MyMemory is selected to save UI space"""
        provider = provider_text or (self.combo_provider.currentText() if hasattr(self, "combo_provider") else "")
        is_free_mt = ("Google" in provider and "Gemini" not in provider) or "MyMemory" in provider
        show_style = not is_free_mt
        if hasattr(self, "lbl_style"):
            self.lbl_style.setVisible(show_style)
        if hasattr(self, "combo_style"):
            self.combo_style.setVisible(show_style)

    def get_dubbing_settings(self) -> dict:
        return {
            "voice_model": getattr(self, "_current_voice", VOICE_MODEL_OPTIONS[0]),
            "speed": self.combo_speed.currentText() if hasattr(self, "combo_speed") else "1.00x (ល្បឿនដើម - Standard Normal)",
            "auto_dub": getattr(self, "_auto_dub", True)
        }

    def get_translation_settings(self) -> dict:
        provider = self.combo_provider.currentText()
        is_free_mt = ("Google" in provider and "Gemini" not in provider) or "MyMemory" in provider
        if is_free_mt or not (hasattr(self, "combo_style") and self.combo_style.isVisible()):
            style = "ធម្មតា (Standard)"
        else:
            style = self.combo_style.currentText()
        return {
            "provider": provider,
            "style": style
        }

    def _on_stop_clicked(self):
        if self.on_stop_task:
            self.on_stop_task()

    def _on_detect_gender_clicked(self):
        if hasattr(self, "on_detect_genders") and self.on_detect_genders:
            self.on_detect_genders()

    def set_processing_state(self, is_running: bool):
        if hasattr(self, "btn_stop_process"):
            self.btn_stop_process.setVisible(is_running)


