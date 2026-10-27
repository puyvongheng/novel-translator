# -*- coding: utf-8 -*-
"""
Custom Video Size & Crop Framing Dialog for AI Khmer Movie Studio.
Allows users to choose standard presets (16:9 Long Video, 9:16 TikTok / Reels, 1:1 Square, 4:5 Portrait)
or configure custom Width x Height resolutions with undistorted Crop / Fill or Fit / Blur framing.
"""

from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QSlider, QRadioButton, QButtonGroup, QFrame,
    QGridLayout, Qt, QIcon, QSize, QFont
)
from ui_v_PyQt6.icons import get_qta_icon


class CustomResolutionDialog(QDialog):
    """
    Modern Dark Studio Dialog for configuring Canvas Aspect Ratio,
    Custom Resolution (Width x Height), and Crop/Fit Framing Mode.
    """
    def __init__(self, current_w: int = 1080, current_h: int = 1920, current_mode: str = "fill", parent=None):
        super().__init__(parent)
        self.setWindowTitle("កំណត់ទំហំ និងកាត់តម្រឹមវីដេអូ (Video Canvas & Crop Size)")
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QDialog {
                background-color: #0e1218;
                color: #e2e8f0;
                font-family: 'Kantumruy Pro', 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
            }
            QFrame.card {
                background-color: #151a24;
                border: 1px solid #232c3d;
                border-radius: 8px;
                padding: 10px;
            }
            QSpinBox {
                background-color: #1e2636;
                color: #38bdf8;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QSpinBox:focus {
                border: 1px solid #38bdf8;
            }
            QRadioButton {
                color: #e2e8f0;
                font-size: 12px;
                spacing: 6px;
            }
            QRadioButton:hover {
                color: #38bdf8;
            }
            QPushButton.preset_btn {
                background-color: #1b2230;
                color: #e2e8f0;
                border: 1px solid #283347;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                text-align: left;
            }
            QPushButton.preset_btn:hover {
                background-color: #263147;
                border: 1px solid #38bdf8;
                color: #38bdf8;
            }
        """)

        self.selected_w = max(100, int(current_w))
        self.selected_h = max(100, int(current_h))
        self.selected_fit_mode = current_mode or "fill"

        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        # Header Title
        title_box = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setPixmap(get_qta_icon("fa5s.crop-alt", color="#38bdf8").pixmap(24, 24))
        title_box.addWidget(icon_lbl)

        lbl_header = QLabel("ទំហំវីដេអូ និងការកាត់តម្រឹម (Video Size & Crop Mode)")
        lbl_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc;")
        title_box.addWidget(lbl_header, 1)
        root.addLayout(title_box)

        # ---------------- 1. QUICK PRESET PILLS ----------------
        card_presets = QFrame()
        card_presets.setProperty("class", "card")
        p_layout = QVBoxLayout(card_presets)
        p_layout.setContentsMargins(10, 10, 10, 10)
        p_layout.setSpacing(6)

        lbl_presets = QLabel("⭐ ជ្រើសរើសទំហំពេញនិយម (Standard Presets):")
        lbl_presets.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 11px;")
        p_layout.addWidget(lbl_presets)

        grid = QGridLayout()
        grid.setSpacing(6)

        presets = [
            ("📱 TikTok / Reels / Shorts (1080 x 1920)", 1080, 1920, "9:16"),
            ("🎬 YouTube / Cinema 1080p (1920 x 1080)", 1920, 1080, "16:9"),
            ("📱 TikTok / Mobile 720p (720 x 1280)", 720, 1280, "9:16"),
            ("📺 YouTube / HD 720p (1280 x 720)", 1280, 720, "16:9"),
            ("⏹️ Instagram Square (1080 x 1080)", 1080, 1080, "1:1"),
            ("📸 Instagram Portrait 4:5 (1080 x 1350)", 1080, 1350, "4:5"),
            ("🎞️ Cinema Scope 21:9 (2560 x 1080)", 2560, 1080, "21:9"),
            ("🖥️ 4K Ultra HD (3840 x 2160)", 3840, 2160, "16:9")
        ]

        for i, (name, w, h, ar) in enumerate(presets):
            btn = QPushButton(name)
            btn.setProperty("class", "preset_btn")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, pw=w, ph=h: self._apply_preset(pw, ph))
            row = i // 2
            col = i % 2
            grid.addWidget(btn, row, col)

        p_layout.addLayout(grid)
        root.addWidget(card_presets)

        # ---------------- 2. CUSTOM WIDTH X HEIGHT INPUTS ----------------
        card_custom = QFrame()
        card_custom.setProperty("class", "card")
        c_layout = QVBoxLayout(card_custom)
        c_layout.setContentsMargins(10, 10, 10, 10)
        c_layout.setSpacing(8)

        lbl_c_title = QLabel("⚙️ កំណត់ទំហំតាមចិត្ត (Custom Width x Height in Pixels):")
        lbl_c_title.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 11px;")
        c_layout.addWidget(lbl_c_title)

        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(10)

        # Width
        v_w = QVBoxLayout()
        v_w.setSpacing(2)
        v_w.addWidget(QLabel("ទទឹង (Width px):"))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(100, 7680)
        self.spin_w.setSingleStep(2)
        self.spin_w.setValue(self.selected_w)
        self.spin_w.valueChanged.connect(self._on_dims_changed)
        v_w.addWidget(self.spin_w)
        inputs_row.addLayout(v_w)

        lbl_x = QLabel("✖")
        lbl_x.setStyleSheet("font-size: 16px; color: #64748b; font-weight: bold; padding-top: 14px;")
        inputs_row.addWidget(lbl_x)

        # Height
        v_h = QVBoxLayout()
        v_h.setSpacing(2)
        v_h.addWidget(QLabel("កម្ពស់ (Height px):"))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(100, 7680)
        self.spin_h.setSingleStep(2)
        self.spin_h.setValue(self.selected_h)
        self.spin_h.valueChanged.connect(self._on_dims_changed)
        v_h.addWidget(self.spin_h)
        inputs_row.addLayout(v_h)

        c_layout.addLayout(inputs_row)

        # Calculated Aspect Ratio Tag
        self.lbl_ar_info = QLabel()
        self.lbl_ar_info.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 12px; padding: 2px 0;")
        c_layout.addWidget(self.lbl_ar_info)
        root.addWidget(card_custom)

        # ---------------- 3. FRAMING & CROP MODE ----------------
        card_mode = QFrame()
        card_mode.setProperty("class", "card")
        m_layout = QVBoxLayout(card_mode)
        m_layout.setContentsMargins(10, 10, 10, 10)
        m_layout.setSpacing(8)

        lbl_mode = QLabel("✂️ របៀបកាត់តម្រឹមរូបភាព (Framing & Crop Style):")
        lbl_mode.setStyleSheet("font-weight: bold; color: #94a3b8; font-size: 11px;")
        m_layout.addWidget(lbl_mode)

        self.btn_group_mode = QButtonGroup(self)

        self.radio_fill = QRadioButton("✂️ Fill & Center Crop (កាត់តម្រឹមពេញអេក្រង់ - No Stretch, TikTok Best)")
        self.radio_fill.setToolTip("Scales video to completely fill the vertical canvas without any stretching or distortion.")
        self.btn_group_mode.addButton(self.radio_fill)
        m_layout.addWidget(self.radio_fill)

        self.radio_fit_blur = QRadioButton("📐 Fit with Blurred Background (ដាក់ព្រាលផ្ទៃខាងក្រោយ - CapCut / Reels)")
        self.radio_fit_blur.setToolTip("Centers original video and blurs background video to fill vertical canvas.")
        self.btn_group_mode.addButton(self.radio_fit_blur)
        m_layout.addWidget(self.radio_fit_blur)

        self.radio_black = QRadioButton("⬛ Fit with Black Bars (ដាក់គែមខ្មៅសងខាង - Letterbox)")
        self.radio_black.setToolTip("Centers original video with clean black bars.")
        self.btn_group_mode.addButton(self.radio_black)
        m_layout.addWidget(self.radio_black)

        if self.selected_fit_mode == "fit":
            self.radio_fit_blur.setChecked(True)
        elif self.selected_fit_mode == "black":
            self.radio_black.setChecked(True)
        else:
            self.radio_fill.setChecked(True)

        root.addWidget(card_mode)

        # ---------------- 4. ACTION BUTTONS ----------------
        btns_row = QHBoxLayout()
        btns_row.setSpacing(10)

        btn_cancel = QPushButton("បោះបង់ (Cancel)")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e2636;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #283347;
                color: #f1f5f9;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        btns_row.addWidget(btn_cancel)

        btn_apply = QPushButton("✓ អនុវត្តទំហំវីដេអូ (Apply Size)")
        btn_apply.setFixedHeight(34)
        btn_apply.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0369a1, stop:1 #0284c7);
            }
        """)
        btn_apply.clicked.connect(self._on_apply)
        btns_row.addWidget(btn_apply, 1)

        root.addLayout(btns_row)

        self._on_dims_changed()

    def _apply_preset(self, w: int, h: int):
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)

    def _on_dims_changed(self):
        w = self.spin_w.value()
        h = self.spin_h.value()
        ratio = w / max(1, h)

        if abs(ratio - (9.0 / 16.0)) < 0.02:
            tag = "📱 9:16 Vertical (Shorts / TikTok / Reels)"
        elif abs(ratio - (16.0 / 9.0)) < 0.02:
            tag = "🎬 16:9 Landscape (YouTube / Cinema Long Video)"
        elif abs(ratio - 1.0) < 0.02:
            tag = "⏹️ 1:1 Square (Instagram / Facebook)"
        elif abs(ratio - (4.0 / 5.0)) < 0.02:
            tag = "📸 4:5 Portrait (Instagram Feed)"
        elif abs(ratio - (21.0 / 9.0)) < 0.05:
            tag = "🎞️ 21:9 Ultrawide Cinema"
        else:
            tag = f"Custom Ratio: {ratio:.2f}:1"

        self.lbl_ar_info.setText(f"📐 ទម្រង់សមាមាត្រ: {tag} ({w} x {h} px)")

    def _on_apply(self):
        self.selected_w = self.spin_w.value()
        self.selected_h = self.spin_h.value()
        if self.radio_fit_blur.isChecked():
            self.selected_fit_mode = "fit"
        elif self.radio_black.isChecked():
            self.selected_fit_mode = "black"
        else:
            self.selected_fit_mode = "fill"
        self.accept()

    def get_result(self) -> tuple:
        """Returns (width, height, fit_mode)"""
        return (self.selected_w, self.selected_h, self.selected_fit_mode)
