"""
Photoshop CC-Grade Guide Dialogs for Video Monitor Canvas
Provides:
- NewGuideDialog: Precise single horizontal or vertical guide by px or %
- NewGuideLayoutDialog: Photoshop-identical Guide Layout generator (Columns, Rows, Margins, Gutters, Presets)
"""

from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QRadioButton, QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QComboBox, QFrame, Qt, Signal, QColor
)


class NewGuideDialog(QDialog):
    """
    Adobe Photoshop CC-Style 'New Guide...' Dialog
    Allows creating a single horizontal or vertical guide line at exact pixel or percentage position.
    """
    def __init__(self, parent=None, video_w: int = 1920, video_h: int = 1080):
        super().__init__(parent)
        self.video_w = max(100, video_w)
        self.video_h = max(100, video_h)
        self.orientation = "h"  # "h" or "v"
        self.norm_pos = 0.5     # 0.0 to 1.0

        self.setWindowTitle("New Guide (បន្ទាត់ Guide ថ្មី)")
        self.setFixedSize(320, 220)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Kantumruy Pro';
            }
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                font-size: 11px;
                font-weight: bold;
                color: #38bdf8;
            }
            QRadioButton {
                color: #e0e0e0;
                font-size: 11px;
                spacing: 6px;
            }
            QRadioButton::indicator {
                width: 13px;
                height: 13px;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #007acc;
            }
            QPushButton {
                background-color: #383838;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 14px;
                font-size: 11px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #484848;
                border-color: #777777;
            }
            QPushButton#btn_ok {
                background-color: #007acc;
                border-color: #007acc;
            }
            QPushButton#btn_ok:hover {
                background-color: #0098ff;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # 1. Orientation Group
        group_orient = QGroupBox("Orientation (ទិសដៅ)")
        l_orient = QVBoxLayout(group_orient)
        l_orient.setSpacing(6)
        self.radio_h = QRadioButton("Horizontal (បន្ទាត់ផ្ដេក — លើ/ក្រោម)")
        self.radio_v = QRadioButton("Vertical (បន្ទាត់បញ្ឈរ — ឆ្វេង/ស្តាំ)")
        self.radio_h.setChecked(True)
        self.radio_h.toggled.connect(self._on_orient_changed)
        l_orient.addWidget(self.radio_h)
        l_orient.addWidget(self.radio_v)
        layout.addWidget(group_orient)

        # 2. Position Row
        row_pos = QHBoxLayout()
        row_pos.addWidget(QLabel("Position (ទីតាំង):"))
        self.spin_px = QSpinBox()
        self.spin_px.setRange(0, self.video_h)
        self.spin_px.setValue(self.video_h // 2)
        self.spin_px.setSuffix(" px")
        self.spin_px.valueChanged.connect(self._on_px_changed)
        row_pos.addWidget(self.spin_px, 1)

        self.spin_pct = QDoubleSpinBox()
        self.spin_pct.setRange(0.0, 100.0)
        self.spin_pct.setValue(50.0)
        self.spin_pct.setSuffix(" %")
        self.spin_pct.setDecimals(1)
        self.spin_pct.valueChanged.connect(self._on_pct_changed)
        row_pos.addWidget(self.spin_pct, 1)
        layout.addLayout(row_pos)

        # 3. Dialog Buttons
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("btn_ok")
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    def _on_orient_changed(self):
        is_h = self.radio_h.isChecked()
        max_val = self.video_h if is_h else self.video_w
        self.spin_px.blockSignals(True)
        self.spin_px.setMaximum(max_val)
        cur_px = int(self.norm_pos * max_val)
        self.spin_px.setValue(cur_px)
        self.spin_px.blockSignals(False)

    def _on_px_changed(self, val):
        max_val = self.video_h if self.radio_h.isChecked() else self.video_w
        self.norm_pos = max(0.0, min(1.0, val / float(max_val)))
        self.spin_pct.blockSignals(True)
        self.spin_pct.setValue(self.norm_pos * 100.0)
        self.spin_pct.blockSignals(False)

    def _on_pct_changed(self, val):
        self.norm_pos = max(0.0, min(1.0, val / 100.0))
        max_val = self.video_h if self.radio_h.isChecked() else self.video_w
        self.spin_px.blockSignals(True)
        self.spin_px.setValue(int(self.norm_pos * max_val))
        self.spin_px.blockSignals(False)

    def _on_ok(self):
        self.orientation = "h" if self.radio_h.isChecked() else "v"
        self.accept()

    def get_guide_data(self):
        """Returns (orientation: 'h'|'v', norm_pos: float)"""
        return self.orientation, self.norm_pos


class NewGuideLayoutDialog(QDialog):
    """
    Adobe Photoshop CC-Style 'New Guide Layout...' Dialog
    Allows generating professional grid layouts (Columns, Rows, Margins, Gutters, Center Crosshairs, Rule of Thirds).
    """
    def __init__(self, parent=None, video_w: int = 1920, video_h: int = 1080):
        super().__init__(parent)
        self.video_w = max(100, video_w)
        self.video_h = max(100, video_h)

        self.setWindowTitle("New Guide Layout (ប្លង់ Guide ស្វ័យប្រវត្តិ)")
        self.setFixedSize(460, 460)
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #e0e0e0;
                font-family: 'Segoe UI', 'Kantumruy Pro';
            }
            QLabel {
                color: #cccccc;
                font-size: 11px;
            }
            QGroupBox {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                margin-top: 8px;
                padding: 10px 8px 8px 8px;
                font-size: 11px;
                font-weight: bold;
                color: #38bdf8;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 11px;
                font-weight: bold;
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
            }
            QSpinBox, QComboBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 3px 6px;
                font-size: 11px;
            }
            QSpinBox:focus, QComboBox:focus {
                border-color: #007acc;
            }
            QPushButton {
                background-color: #383838;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px 12px;
                font-size: 11px;
                min-width: 70px;
            }
            QPushButton:hover {
                background-color: #484848;
                border-color: #777777;
            }
            QPushButton#btn_ok {
                background-color: #007acc;
                border-color: #007acc;
            }
            QPushButton#btn_ok:hover {
                background-color: #0098ff;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # 1. Preset Selector
        row_preset = QHBoxLayout()
        row_preset.addWidget(QLabel("Preset:"))
        self.combo_preset = QComboBox()
        self.combo_preset.addItem("Custom (តាមការកំណត់)", "custom")
        self.combo_preset.addItem("🎬 Rule of Thirds (ប្លង់ 3x3 ស្តង់ដារភាពយន្ត)", "thirds")
        self.combo_preset.addItem("🎯 Center Crosshair (បន្ទាត់កណ្តាល X & Y)", "center")
        self.combo_preset.addItem("📐 4-Quadrant (ប្លង់ 2x2 កណ្តាល ៤ ផ្នែក)", "quad")
        self.combo_preset.addItem("🏛️ 12-Column Grid (ប្លង់រចនា 12 ជួរ)", "12col")
        self.combo_preset.addItem("✨ Golden Ratio (សមាមាត្រមាស)", "golden")
        self.combo_preset.addItem("📱 TikTok / Reels Safe Margins (គែមសុវត្ថិភាព)", "social")
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        row_preset.addWidget(self.combo_preset, 1)
        layout.addLayout(row_preset)

        # 2. Columns & Rows Group
        h_grid_group = QHBoxLayout()

        # Columns
        self.group_cols = QGroupBox("Columns (ជួរឈរ)")
        l_cols = QVBoxLayout(self.group_cols)
        self.chk_cols = QCheckBox("Enable Columns")
        self.chk_cols.setChecked(True)
        self.chk_cols.toggled.connect(self._update_controls_state)
        l_cols.addWidget(self.chk_cols)

        row_c_num = QHBoxLayout()
        row_c_num.addWidget(QLabel("Number:"))
        self.spin_col_num = QSpinBox()
        self.spin_col_num.setRange(1, 48)
        self.spin_col_num.setValue(3)
        row_c_num.addWidget(self.spin_col_num, 1)
        l_cols.addLayout(row_c_num)

        row_c_gut = QHBoxLayout()
        row_c_gut.addWidget(QLabel("Gutter:"))
        self.spin_col_gutter = QSpinBox()
        self.spin_col_gutter.setRange(0, 500)
        self.spin_col_gutter.setValue(0)
        self.spin_col_gutter.setSuffix(" px")
        row_c_gut.addWidget(self.spin_col_gutter, 1)
        l_cols.addLayout(row_c_gut)
        h_grid_group.addWidget(self.group_cols)

        # Rows
        self.group_rows = QGroupBox("Rows (ជួរដេក)")
        l_rows = QVBoxLayout(self.group_rows)
        self.chk_rows = QCheckBox("Enable Rows")
        self.chk_rows.setChecked(True)
        self.chk_rows.toggled.connect(self._update_controls_state)
        l_rows.addWidget(self.chk_rows)

        row_r_num = QHBoxLayout()
        row_r_num.addWidget(QLabel("Number:"))
        self.spin_row_num = QSpinBox()
        self.spin_row_num.setRange(1, 48)
        self.spin_row_num.setValue(3)
        row_r_num.addWidget(self.spin_row_num, 1)
        l_rows.addLayout(row_r_num)

        row_r_gut = QHBoxLayout()
        row_r_gut.addWidget(QLabel("Gutter:"))
        self.spin_row_gutter = QSpinBox()
        self.spin_row_gutter.setRange(0, 500)
        self.spin_row_gutter.setValue(0)
        self.spin_row_gutter.setSuffix(" px")
        row_r_gut.addWidget(self.spin_row_gutter, 1)
        l_rows.addLayout(row_r_gut)
        h_grid_group.addWidget(self.group_rows)

        layout.addLayout(h_grid_group)

        # 3. Margin Group
        self.group_margin = QGroupBox("Margin (គែមសងខាង)")
        l_margin = QVBoxLayout(self.group_margin)
        self.chk_margin = QCheckBox("Enable Margin")
        self.chk_margin.setChecked(False)
        self.chk_margin.toggled.connect(self._update_controls_state)
        l_margin.addWidget(self.chk_margin)

        m_grid = QHBoxLayout()
        # Top & Bottom
        v_tb = QVBoxLayout()
        row_top = QHBoxLayout()
        row_top.addWidget(QLabel("Top:"))
        self.spin_m_top = QSpinBox()
        self.spin_m_top.setRange(0, self.video_h // 2)
        self.spin_m_top.setValue(0)
        self.spin_m_top.setSuffix(" px")
        row_top.addWidget(self.spin_m_top)
        v_tb.addLayout(row_top)

        row_bot = QHBoxLayout()
        row_bot.addWidget(QLabel("Bottom:"))
        self.spin_m_bottom = QSpinBox()
        self.spin_m_bottom.setRange(0, self.video_h // 2)
        self.spin_m_bottom.setValue(0)
        self.spin_m_bottom.setSuffix(" px")
        row_bot.addWidget(self.spin_m_bottom)
        v_tb.addLayout(row_bot)
        m_grid.addLayout(v_tb)

        # Left & Right
        v_lr = QVBoxLayout()
        row_left = QHBoxLayout()
        row_left.addWidget(QLabel("Left:"))
        self.spin_m_left = QSpinBox()
        self.spin_m_left.setRange(0, self.video_w // 2)
        self.spin_m_left.setValue(0)
        self.spin_m_left.setSuffix(" px")
        row_left.addWidget(self.spin_m_left)
        v_lr.addLayout(row_left)

        row_right = QHBoxLayout()
        row_right.addWidget(QLabel("Right:"))
        self.spin_m_right = QSpinBox()
        self.spin_m_right.setRange(0, self.video_w // 2)
        self.spin_m_right.setValue(0)
        self.spin_m_right.setSuffix(" px")
        row_right.addWidget(self.spin_m_right)
        v_lr.addLayout(row_right)
        m_grid.addLayout(v_lr)

        l_margin.addLayout(m_grid)
        layout.addWidget(self.group_margin)

        # 4. Clear Existing Guides Checkbox
        self.chk_clear_existing = QCheckBox("Clear Existing Guides (លុបបន្ទាត់ចាស់ៗចេញមុនបង្កើត)")
        self.chk_clear_existing.setChecked(True)
        layout.addWidget(self.chk_clear_existing)

        # 5. Buttons
        layout.addStretch()
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton("OK")
        btn_ok.setObjectName("btn_ok")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        self._update_controls_state()

    def _update_controls_state(self):
        c_on = self.chk_cols.isChecked()
        self.spin_col_num.setEnabled(c_on)
        self.spin_col_gutter.setEnabled(c_on)

        r_on = self.chk_rows.isChecked()
        self.spin_row_num.setEnabled(r_on)
        self.spin_row_gutter.setEnabled(r_on)

        m_on = self.chk_margin.isChecked()
        self.spin_m_top.setEnabled(m_on)
        self.spin_m_bottom.setEnabled(m_on)
        self.spin_m_left.setEnabled(m_on)
        self.spin_m_right.setEnabled(m_on)

    def _on_preset_changed(self, idx):
        preset = self.combo_preset.currentData()
        if preset == "thirds":
            # 3x3 Rule of Thirds
            self.chk_cols.setChecked(True)
            self.spin_col_num.setValue(3)
            self.spin_col_gutter.setValue(0)
            self.chk_rows.setChecked(True)
            self.spin_row_num.setValue(3)
            self.spin_row_gutter.setValue(0)
            self.chk_margin.setChecked(False)

        elif preset == "center":
            # 2x2 Center Crosshair
            self.chk_cols.setChecked(True)
            self.spin_col_num.setValue(2)
            self.spin_col_gutter.setValue(0)
            self.chk_rows.setChecked(True)
            self.spin_row_num.setValue(2)
            self.spin_row_gutter.setValue(0)
            self.chk_margin.setChecked(False)

        elif preset == "quad":
            self.chk_cols.setChecked(True)
            self.spin_col_num.setValue(2)
            self.spin_col_gutter.setValue(0)
            self.chk_rows.setChecked(True)
            self.spin_row_num.setValue(2)
            self.spin_row_gutter.setValue(0)
            self.chk_margin.setChecked(False)

        elif preset == "12col":
            self.chk_cols.setChecked(True)
            self.spin_col_num.setValue(12)
            self.spin_col_gutter.setValue(16)
            self.chk_rows.setChecked(False)
            self.chk_margin.setChecked(True)
            self.spin_m_left.setValue(40)
            self.spin_m_right.setValue(40)

        elif preset == "golden":
            self.chk_cols.setChecked(True)
            self.spin_col_num.setValue(3)
            self.spin_col_gutter.setValue(0)
            self.chk_rows.setChecked(True)
            self.spin_row_num.setValue(3)
            self.spin_row_gutter.setValue(0)

        elif preset == "social":
            self.chk_cols.setChecked(True)
            self.spin_col_num.setValue(2)
            self.spin_col_gutter.setValue(0)
            self.chk_rows.setChecked(True)
            self.spin_row_num.setValue(2)
            self.chk_margin.setChecked(True)
            self.spin_m_top.setValue(int(self.video_h * 0.12))
            self.spin_m_bottom.setValue(int(self.video_h * 0.20))
            self.spin_m_left.setValue(int(self.video_w * 0.08))
            self.spin_m_right.setValue(int(self.video_w * 0.08))

        self._update_controls_state()

    def get_generated_guides(self):
        """
        Calculates and returns (h_guides: List[float], v_guides: List[float], clear_existing: bool)
        where guides are normalized 0.0 to 1.0 relative to canvas size.
        """
        h_guides = []
        v_guides = []

        m_top = (self.spin_m_top.value() / float(self.video_h)) if self.chk_margin.isChecked() else 0.0
        m_bottom = (self.spin_m_bottom.value() / float(self.video_h)) if self.chk_margin.isChecked() else 0.0
        m_left = (self.spin_m_left.value() / float(self.video_w)) if self.chk_margin.isChecked() else 0.0
        m_right = (self.spin_m_right.value() / float(self.video_w)) if self.chk_margin.isChecked() else 0.0

        if self.chk_margin.isChecked():
            if m_top > 0:
                h_guides.append(round(m_top, 4))
            if m_bottom > 0:
                h_guides.append(round(1.0 - m_bottom, 4))
            if m_left > 0:
                v_guides.append(round(m_left, 4))
            if m_right > 0:
                v_guides.append(round(1.0 - m_right, 4))

        # Effective area
        eff_w = max(0.01, 1.0 - m_left - m_right)
        eff_h = max(0.01, 1.0 - m_top - m_bottom)

        # Columns
        if self.chk_cols.isChecked():
            n_cols = self.spin_col_num.value()
            gutter_norm = (self.spin_col_gutter.value() / float(self.video_w))
            total_gutters = (n_cols - 1) * gutter_norm
            avail_w = max(0.01, eff_w - total_gutters)
            col_w = avail_w / float(n_cols)

            cur_x = m_left
            for i in range(n_cols - 1):
                cur_x += col_w
                v_guides.append(round(cur_x, 4))
                if gutter_norm > 0:
                    cur_x += gutter_norm
                    v_guides.append(round(cur_x, 4))

        # Rows
        if self.chk_rows.isChecked():
            n_rows = self.spin_row_num.value()
            gutter_norm = (self.spin_row_gutter.value() / float(self.video_h))
            total_gutters = (n_rows - 1) * gutter_norm
            avail_h = max(0.01, eff_h - total_gutters)
            row_h = avail_h / float(n_rows)

            cur_y = m_top
            for i in range(n_rows - 1):
                cur_y += row_h
                h_guides.append(round(cur_y, 4))
                if gutter_norm > 0:
                    cur_y += gutter_norm
                    h_guides.append(round(cur_y, 4))

        return sorted(list(set(h_guides))), sorted(list(set(v_guides))), self.chk_clear_existing.isChecked()
