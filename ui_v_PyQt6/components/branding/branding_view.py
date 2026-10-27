"""
AI Khmer Movie Studio - Templates & Branding Suite
Professional desktop workspace for:
- 1. Global Branding: Logo Watermark, Auto Intro/Outro, Lower-Third Banner
- 2. Sponsor Ads System: Scheduled timestamp ads, safe area checking, dynamic rotation
- 3. Animated Ads & Motion Path Engine: Keyframe editor, loops, ping-pong, easing, JSON export
- 4. Responsive Templates: 16:9 Cinema, 9:16 TikTok/Shorts, 1:1 Square, Media Swap
"""

import os
import json
from typing import List, Dict, Optional

from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QCheckBox, QComboBox, QSlider, QFrame, QScrollArea, QTabWidget,
    QFileDialog, QMessageBox, QColor, QFont, Qt, Signal, QGridLayout,
    QPlainTextEdit, QPainter, QPen, QBrush, QPointF, QRectF
)
from models.branding_model import (
    GlobalBrandingProfile, SponsorAdItem, MotionPathAnimation,
    KeyframePoint, create_animation_preset
)


# ---------------------------------------------------------------------------
# MOTION PATH MINI PREVIEW CANVAS (VISUAL TRAJECTORY)
# ---------------------------------------------------------------------------
class MotionPathCanvas(QFrame):
    """Visual 16:9 interactive mini canvas displaying the motion path trajectory."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 160)
        self.setStyleSheet("background-color: #0b0f17; border: 1px solid #28303f; border-radius: 6px;")
        self.animation: Optional[MotionPathAnimation] = None

    def set_animation(self, anim: MotionPathAnimation):
        self.animation = anim
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w, h = self.width(), self.height()

        # Grid lines
        painter.setPen(QPen(QColor("#1e293b"), 1, Qt.PenStyle.DotLine))
        painter.drawLine(0, h // 2, w, h // 2)
        painter.drawLine(w // 2, 0, w // 2, h)

        # Safe area boundary (dashed yellow)
        painter.setPen(QPen(QColor(234, 179, 8, 80), 1, Qt.PenStyle.DashLine))
        painter.drawRect(int(w * 0.08), int(h * 0.08), int(w * 0.84), int(h * 0.72))

        if not self.animation or not self.animation.keyframes:
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Keyframes Defined")
            return

        kfs = sorted(self.animation.keyframes, key=lambda k: k.time)

        # 1. Draw Trajectory Path (Cyan Glowing Line)
        path_pen = QPen(QColor("#06b6d4"), 2, Qt.PenStyle.SolidLine)
        painter.setPen(path_pen)
        pts = [QPointF(k.x * w, k.y * h) for k in kfs]

        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])

        # 2. Draw Keyframe Nodes
        for idx, k in enumerate(kfs):
            px, py = k.x * w, k.y * h
            # Glowing outer circle
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(6, 182, 212, 100))
            painter.drawEllipse(QPointF(px, py), 7, 7)

            # Solid inner core
            painter.setBrush(QColor("#38bdf8") if idx == 0 else QColor("#f43f5e"))
            painter.drawEllipse(QPointF(px, py), 4, 4)

            # Node timestamp badge
            painter.setPen(QColor("#f1f5f9"))
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.drawText(int(px + 8), int(py - 4), f"{k.time:.1f}s")


# ---------------------------------------------------------------------------
# MAIN TEMPLATES & BRANDING VIEW
# ---------------------------------------------------------------------------
class BrandingView(QWidget):
    """
    Dedicated Templates & Branding Studio:
    - Global Branding: Logo Watermark, Auto Intro/Outro, Lower-Third Footer
    - Sponsor Ads System: Timed Ads, Rotation, Safe Areas
    - Animated Ads & Motion Path Engine: Keyframe controls, loops, ping-pong, easing, JSON
    - Responsive Templates: 16:9, 9:16, 1:1, One-Click Media Swap
    """
    apply_branding_requested = Signal(object)      # (GlobalBrandingProfile)
    sponsor_ads_generated = Signal(list)           # List[SponsorAdItem]
    template_applied = Signal(str)                 # ("16:9", "9:16", "1:1")
    aspect_ratio_changed = Signal(str)

    def __init__(self, parent=None, on_apply_branding=None, on_apply_template=None, log_callback=None):
        super().__init__(parent)
        self.on_apply_branding = on_apply_branding
        self.on_apply_template = on_apply_template
        self.log_callback = log_callback

        self.profile = GlobalBrandingProfile()
        self.current_anim = create_animation_preset("slide_left_right")

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # 1. Top Header Bar
        hdr = QHBoxLayout()
        hdr_box = QVBoxLayout()
        hdr_box.setSpacing(2)

        lbl_title = QLabel("🎨 Templates & Branding Studio")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8;")
        lbl_sub = QLabel("One-click Global Branding, Animated Sponsor Ads, Motion Paths & Responsive Layout Templates.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        hdr_box.addWidget(lbl_title)
        hdr_box.addWidget(lbl_sub)
        hdr.addLayout(hdr_box)
        hdr.addStretch()

        btn_apply_all = QPushButton(" 🚀 Apply Branding to Current Project ")
        btn_apply_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply_all.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 7px 18px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #0ea5e9;
            }
        """)
        btn_apply_all.clicked.connect(self._on_apply_all_clicked)
        hdr.addWidget(btn_apply_all)
        main_layout.addLayout(hdr)

        # 2. Main Studio Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #28303f;
                background-color: #141824;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1a202c;
                color: #94a3b8;
                padding: 8px 18px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected {
                background-color: #141824;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                background-color: #242c3d;
                color: #f1f5f9;
            }
        """)

        # Tab 1: Global Branding
        tab_global = self._build_global_branding_tab()
        self.tabs.addTab(tab_global, "⭐ Global Branding (ម៉ាកសញ្ញាទូទៅ)")

        # Tab 2: Sponsor Ads System
        tab_sponsors = self._build_sponsor_ads_tab()
        self.tabs.addTab(tab_sponsors, "📢 Sponsor Ads & Rotations (ពាណិជ្ជកម្ម)")

        # Tab 3: Motion Path & Animated Ads Engine
        tab_motion = self._build_motion_path_tab()
        self.tabs.addTab(tab_motion, "🚀 Animated Ads & Motion Path (ផ្លូវរត់ Ads)")

        # Tab 4: Responsive Templates
        tab_templates = self._build_templates_tab()
        self.tabs.addTab(tab_templates, "📐 Video Templates (ប្លង់ 16:9 / 9:16 / 1:1)")

        main_layout.addWidget(self.tabs, 1)

    # =========================================================================
    # TAB 1: GLOBAL BRANDING (LOGO, INTRO/OUTRO, FOOTER)
    # =========================================================================
    def _build_global_branding_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # 1. Logo Watermark Card
        card_logo = self._create_card_frame("🏷️ Logo Watermark (ឡូហ្គោលើវីដេអូ)")
        cl_layout = QVBoxLayout(card_logo)
        cl_layout.setContentsMargins(14, 14, 14, 14)
        cl_layout.setSpacing(10)

        self.chk_enable_logo = QCheckBox("Enable Logo Watermark (ដាក់ Logo លើវីដេអូពេញ)")
        self.chk_enable_logo.setChecked(self.profile.enable_logo)
        self.chk_enable_logo.setStyleSheet("color: #f1f5f9; font-weight: bold; font-size: 12px;")
        cl_layout.addWidget(self.chk_enable_logo)

        # Logo Picker Row
        row_logo = QHBoxLayout()
        row_logo.addWidget(QLabel("Logo Image Path:"))
        self.txt_logo_path = QLineEdit(self.profile.logo_path)
        self.txt_logo_path.setPlaceholderText("Select transparent PNG/SVG/WEBP logo image...")
        self.txt_logo_path.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_logo.addWidget(self.txt_logo_path, 1)

        btn_browse_logo = QPushButton("📁 Browse...")
        btn_browse_logo.setStyleSheet("background-color: #334155; color: #f1f5f9; padding: 5px 12px; border-radius: 4px;")
        btn_browse_logo.clicked.connect(self._on_browse_logo)
        row_logo.addWidget(btn_browse_logo)
        cl_layout.addLayout(row_logo)

        # Settings Grid (Position, Size, Opacity, Animation)
        grid_logo = QGridLayout()
        grid_logo.setSpacing(10)

        # Position Preset
        grid_logo.addWidget(QLabel("Position Preset:"), 0, 0)
        self.cmb_logo_pos = QComboBox()
        self.cmb_logo_pos.addItems(["Top-Right ↗ (ជ្រុងស្តាំលើ)", "Top-Left ↖ (ជ្រុងឆ្វេងលើ)", "Bottom-Right ↘ (ជ្រុងស្តាំក្រោម)", "Bottom-Left ↙ (ជ្រុងឆ្វេងក្រោម)", "Center 🎯 (ចំកណ្តាល)"])
        self.cmb_logo_pos.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        grid_logo.addWidget(self.cmb_logo_pos, 0, 1)

        # Animation Mode
        grid_logo.addWidget(QLabel("Animated Logo Mode:"), 0, 2)
        self.cmb_logo_anim = QComboBox()
        self.cmb_logo_anim.addItems(["Static (ធម្មតា គ្មានចលនា)", "Zoom Pulse (ដកដង្ហើម)", "Smooth Fade In/Out", "Continuous Slow Rotate", "Corner Float / Bounce"])
        self.cmb_logo_anim.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        grid_logo.addWidget(self.cmb_logo_anim, 0, 3)

        # Size Slider
        grid_logo.addWidget(QLabel("Size (ទំហំ Logo):"), 1, 0)
        self.sld_logo_size = QSlider(Qt.Orientation.Horizontal)
        self.sld_logo_size.setRange(5, 35)
        self.sld_logo_size.setValue(int(self.profile.logo_size * 100))
        self.lbl_logo_size_val = QLabel(f"{int(self.profile.logo_size * 100)}%")
        self.lbl_logo_size_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.sld_logo_size.valueChanged.connect(lambda v: self.lbl_logo_size_val.setText(f"{v}%"))
        box_sz = QHBoxLayout()
        box_sz.addWidget(self.sld_logo_size, 1)
        box_sz.addWidget(self.lbl_logo_size_val)
        grid_logo.addLayout(box_sz, 1, 1)

        # Opacity Slider
        grid_logo.addWidget(QLabel("Opacity (កម្រិតថ្លា):"), 1, 2)
        self.sld_logo_op = QSlider(Qt.Orientation.Horizontal)
        self.sld_logo_op.setRange(10, 100)
        self.sld_logo_op.setValue(int(self.profile.logo_opacity * 100))
        self.lbl_logo_op_val = QLabel(f"{int(self.profile.logo_opacity * 100)}%")
        self.lbl_logo_op_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.sld_logo_op.valueChanged.connect(lambda v: self.lbl_logo_op_val.setText(f"{v}%"))
        box_op = QHBoxLayout()
        box_op.addWidget(self.sld_logo_op, 1)
        box_op.addWidget(self.lbl_logo_op_val)
        grid_logo.addLayout(box_op, 1, 3)

        cl_layout.addLayout(grid_logo)
        layout.addWidget(card_logo)

        # 2. Auto Intro & Outro Card
        card_intro = self._create_card_frame("🎬 Auto Intro & Outro Video (វីដេអូចាប់ផ្តើម និងបញ្ចប់)")
        ci_layout = QVBoxLayout(card_intro)
        ci_layout.setContentsMargins(14, 14, 14, 14)
        ci_layout.setSpacing(10)

        # Intro Row
        row_in = QHBoxLayout()
        self.chk_enable_intro = QCheckBox("Auto Intro:")
        self.chk_enable_intro.setStyleSheet("color: #f1f5f9; font-weight: 600;")
        row_in.addWidget(self.chk_enable_intro)
        self.txt_intro_path = QLineEdit()
        self.txt_intro_path.setPlaceholderText("Select intro video clip (MP4 / MOV)...")
        self.txt_intro_path.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_in.addWidget(self.txt_intro_path, 1)
        btn_in = QPushButton("📁 Browse...")
        btn_in.setStyleSheet("background-color: #334155; color: #f1f5f9; padding: 5px 12px; border-radius: 4px;")
        btn_in.clicked.connect(self._on_browse_intro)
        row_in.addWidget(btn_in)
        ci_layout.addLayout(row_in)

        # Outro Row
        row_out = QHBoxLayout()
        self.chk_enable_outro = QCheckBox("Auto Outro:")
        self.chk_enable_outro.setStyleSheet("color: #f1f5f9; font-weight: 600;")
        row_out.addWidget(self.chk_enable_outro)
        self.txt_outro_path = QLineEdit()
        self.txt_outro_path.setPlaceholderText("Select outro video clip (MP4 / MOV)...")
        self.txt_outro_path.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_out.addWidget(self.txt_outro_path, 1)
        btn_out = QPushButton("📁 Browse...")
        btn_out.setStyleSheet("background-color: #334155; color: #f1f5f9; padding: 5px 12px; border-radius: 4px;")
        btn_out.clicked.connect(self._on_browse_outro)
        row_out.addWidget(btn_out)
        ci_layout.addLayout(row_out)
        layout.addWidget(card_intro)

        # 3. Lower Third Banner Card
        card_footer = self._create_card_frame("📜 Lower-Third & Social Handle Banner (របារព័ត៌មានខាងក្រោម)")
        cf_layout = QVBoxLayout(card_footer)
        cf_layout.setContentsMargins(14, 14, 14, 14)
        cf_layout.setSpacing(10)

        self.chk_enable_footer = QCheckBox("Enable Lower-Third Banner (បង្ហាញ Channel Name & Social ID)")
        self.chk_enable_footer.setStyleSheet("color: #f1f5f9; font-weight: bold; font-size: 12px;")
        cf_layout.addWidget(self.chk_enable_footer)

        row_f_text = QHBoxLayout()
        row_f_text.addWidget(QLabel("Primary Title:"))
        self.txt_footer_title = QLineEdit("🎬 Subscribe: AI Khmer Movie Studio")
        self.txt_footer_title.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_f_text.addWidget(self.txt_footer_title, 1)

        row_f_text.addWidget(QLabel("Social Handle:"))
        self.txt_footer_sub = QLineEdit("Telegram / Facebook: @AIKhmerMovie")
        self.txt_footer_sub.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_f_text.addWidget(self.txt_footer_sub, 1)
        cf_layout.addLayout(row_f_text)
        layout.addWidget(card_footer)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # TAB 2: SPONSOR ADS SYSTEM & ROTATION
    # =========================================================================
    def _build_sponsor_ads_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Card 1: Add / Edit Sponsor Ad
        card_sponsor_edit = self._create_card_frame("📢 Add / Manage Sponsor Preset (កំណត់ព័ត៌មាន Sponsor)")
        cse_layout = QVBoxLayout(card_sponsor_edit)
        cse_layout.setContentsMargins(14, 14, 14, 14)
        cse_layout.setSpacing(10)

        row_sp1 = QHBoxLayout()
        row_sp1.addWidget(QLabel("Sponsor Brand Name:"))
        self.txt_sp_name = QLineEdit("1xBet / Wing Bank")
        self.txt_sp_name.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_sp1.addWidget(self.txt_sp_name, 1)

        row_sp1.addWidget(QLabel("Website / Text:"))
        self.txt_sp_web = QLineEdit("www.sponsorbrand.com")
        self.txt_sp_web.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_sp1.addWidget(self.txt_sp_web, 1)
        cse_layout.addLayout(row_sp1)

        row_sp2 = QHBoxLayout()
        row_sp2.addWidget(QLabel("Sponsor Logo Image:"))
        self.txt_sp_logo = QLineEdit()
        self.txt_sp_logo.setPlaceholderText("PNG/JPG logo image...")
        self.txt_sp_logo.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_sp2.addWidget(self.txt_sp_logo, 1)

        btn_sp_logo = QPushButton("📁 Browse...")
        btn_sp_logo.setStyleSheet("background-color: #334155; color: #f1f5f9; padding: 5px 12px; border-radius: 4px;")
        btn_sp_logo.clicked.connect(self._on_browse_sponsor_logo)
        row_sp2.addWidget(btn_sp_logo)

        row_sp2.addWidget(QLabel("QR Code (Optional):"))
        self.txt_sp_qr = QLineEdit()
        self.txt_sp_qr.setPlaceholderText("QR Code image...")
        self.txt_sp_qr.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_sp2.addWidget(self.txt_sp_qr, 1)

        btn_sp_qr = QPushButton("📁 Browse...")
        btn_sp_qr.setStyleSheet("background-color: #334155; color: #f1f5f9; padding: 5px 12px; border-radius: 4px;")
        btn_sp_qr.clicked.connect(self._on_browse_sponsor_qr)
        row_sp2.addWidget(btn_sp_qr)
        cse_layout.addLayout(row_sp2)

        # Timing Schedule Row
        row_sched = QHBoxLayout()
        row_sched.addWidget(QLabel("Schedule Show At:"))
        self.txt_sp_times = QLineEdit("02:00, 05:00, 10:00")
        self.txt_sp_times.setToolTip("Timestamps when ad will pop up (e.g. 02:00, 05:00, 10:00)")
        self.txt_sp_times.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px 8px; border-radius: 4px; color: #f1f5f9;")
        row_sched.addWidget(self.txt_sp_times, 1)

        row_sched.addWidget(QLabel("Display Duration:"))
        self.cmb_sp_dur = QComboBox()
        self.cmb_sp_dur.addItems(["8 Seconds (ល្មម)", "12 Seconds", "15 Seconds", "20 Seconds"])
        self.cmb_sp_dur.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        row_sched.addWidget(self.cmb_sp_dur)

        self.chk_safe_area = QCheckBox("Safe Area Protection (កុំឱ្យបាំង Subtitle)")
        self.chk_safe_area.setChecked(True)
        self.chk_safe_area.setStyleSheet("color: #38bdf8; font-weight: bold;")
        row_sched.addWidget(self.chk_safe_area)
        cse_layout.addLayout(row_sched)

        # Buttons
        btn_box = QHBoxLayout()
        btn_add_sp = QPushButton("➕ Save & Add Sponsor to Campaign")
        btn_add_sp.setStyleSheet("background-color: #0284c7; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_add_sp.clicked.connect(self._on_add_sponsor_clicked)
        btn_box.addWidget(btn_add_sp)

        self.chk_rotation = QCheckBox("Enable Dynamic Sponsor Rotation (ប្តូរ Sponsor ជាបន្តបន្ទាប់)")
        self.chk_rotation.setChecked(True)
        self.chk_rotation.setStyleSheet("color: #f59e0b; font-weight: bold;")
        btn_box.addWidget(self.chk_rotation)
        btn_box.addStretch()
        cse_layout.addLayout(btn_box)

        layout.addWidget(card_sponsor_edit)

        # Card 2: Generate onto Timeline
        card_gen = self._create_card_frame("⚡ Automatic Timeline Placement (ដាក់លើ Timeline ដោយស្វ័យប្រវត្តិ)")
        cg_layout = QVBoxLayout(card_gen)
        cg_layout.setContentsMargins(14, 14, 14, 14)
        cg_layout.setSpacing(10)

        lbl_desc = QLabel("ប្រព័ន្ធនឹងរៀបចំ Sponsor Ads ទាំងអស់ចូលទៅក្នុង Timeline នៅត្រង់នាទី 02:00, 05:00... ដោយភ្ជាប់មកជាមួយចលនា Animation ស្វ័យប្រវត្តិ។")
        lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        cg_layout.addWidget(lbl_desc)

        btn_auto_place = QPushButton(" 🎬 Generate Sponsor Ads Across Whole Movie Timeline ")
        btn_auto_place.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 18px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #10b981;
            }
        """)
        btn_auto_place.clicked.connect(self._on_auto_generate_sponsors)
        cg_layout.addWidget(btn_auto_place)
        layout.addWidget(card_gen)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # TAB 3: ANIMATED ADS & MOTION PATH ENGINE
    # =========================================================================
    def _build_motion_path_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Top Row: Preset selector + Visual mini canvas
        row_top = QHBoxLayout()
        row_top.setSpacing(14)

        # Left Controls Box
        ctrl_box = QVBoxLayout()
        ctrl_box.setSpacing(8)

        lbl_m_title = QLabel("🚀 Motion Path & Animated Ads Engine")
        lbl_m_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")
        ctrl_box.addWidget(lbl_m_title)

        # Preset Selector
        row_p = QHBoxLayout()
        row_p.addWidget(QLabel("Animation Trajectory Preset:"))
        self.cmb_anim_preset = QComboBox()
        self.cmb_anim_preset.addItems([
            "↔ Slide In & Out (Left to Right / Bottom Pop)",
            "🔲 Corner Orbit (Glides through all 4 corners)",
            "🏓 Ping-Pong Banner (Bounces across bottom)",
            "🌟 Floating Pulse & Breathing",
            "↗ Diagonal Glide (Corner to Corner)",
            "✍️ Custom Motion Path (User Keyframes)"
        ])
        self.cmb_anim_preset.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 5px; border-radius: 4px; color: #f1f5f9;")
        self.cmb_anim_preset.currentIndexChanged.connect(self._on_anim_preset_changed)
        row_p.addWidget(self.cmb_anim_preset, 1)
        ctrl_box.addLayout(row_p)

        # Settings Grid (Loop, Direction, Speed, Easing, Pause)
        grid_m = QGridLayout()
        grid_m.setSpacing(8)

        # Loop Mode
        grid_m.addWidget(QLabel("Loop Mode:"), 0, 0)
        self.cmb_loop_mode = QComboBox()
        self.cmb_loop_mode.addItems(["Loop Infinite (រត់រហូតដល់ចប់ Clip)", "Loop 2 Times", "Loop 3 Times", "Loop 5 Times", "Play Once (រត់ 1 ដង)"])
        self.cmb_loop_mode.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        self.cmb_loop_mode.currentIndexChanged.connect(self._sync_animation_settings)
        grid_m.addWidget(self.cmb_loop_mode, 0, 1)

        # Direction
        grid_m.addWidget(QLabel("Direction:"), 0, 2)
        self.cmb_direction = QComboBox()
        self.cmb_direction.addItems(["Normal (ទៅមុខ)", "Reverse (ថយក្រោយ)", "Ping Pong (ទៅហើយត្រឡប់)"])
        self.cmb_direction.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        self.cmb_direction.currentIndexChanged.connect(self._sync_animation_settings)
        grid_m.addWidget(self.cmb_direction, 0, 3)

        # Speed Control (Duration)
        grid_m.addWidget(QLabel("Speed (Loop Duration):"), 1, 0)
        self.sld_anim_dur = QSlider(Qt.Orientation.Horizontal)
        self.sld_anim_dur.setRange(2, 25)
        self.sld_anim_dur.setValue(8)
        self.lbl_anim_dur_val = QLabel("8.0s")
        self.lbl_anim_dur_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.sld_anim_dur.valueChanged.connect(self._on_speed_slider_changed)
        b_spd = QHBoxLayout()
        b_spd.addWidget(self.sld_anim_dur, 1)
        b_spd.addWidget(self.lbl_anim_dur_val)
        grid_m.addLayout(b_spd, 1, 1)

        # Easing Function
        grid_m.addWidget(QLabel("Easing Function:"), 1, 2)
        self.cmb_easing = QComboBox()
        self.cmb_easing.addItems(["Linear (ល្បឿនស្មើ)", "Ease In (យឺតហើយលឿន)", "Ease Out (លឿនហើយយឺត)", "Ease In-Out (រលូនបំផុត)", "Sine Curve"])
        self.cmb_easing.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        self.cmb_easing.currentIndexChanged.connect(self._sync_animation_settings)
        grid_m.addWidget(self.cmb_easing, 1, 3)

        # Delay & Pause Between Loops
        grid_m.addWidget(QLabel("Delay Before Start:"), 2, 0)
        self.cmb_delay = QComboBox()
        self.cmb_delay.addItems(["0 Seconds (ភ្លាមៗ)", "2 Seconds", "5 Seconds", "10 Seconds"])
        self.cmb_delay.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        self.cmb_delay.currentIndexChanged.connect(self._sync_animation_settings)
        grid_m.addWidget(self.cmb_delay, 2, 1)

        grid_m.addWidget(QLabel("Pause Between Loops:"), 2, 2)
        self.cmb_pause = QComboBox()
        self.cmb_pause.addItems(["0 Seconds (បន្តជាប់)", "1 Second", "2 Seconds (ផ្អាក)", "3 Seconds", "5 Seconds"])
        self.cmb_pause.setStyleSheet("background-color: #1e2533; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f1f5f9;")
        self.cmb_pause.currentIndexChanged.connect(self._sync_animation_settings)
        grid_m.addWidget(self.cmb_pause, 2, 3)

        ctrl_box.addLayout(grid_m)
        row_top.addLayout(ctrl_box, 1)

        # Right: Mini Motion Canvas
        canvas_box = QVBoxLayout()
        canvas_box.setSpacing(4)
        lbl_c_hint = QLabel("👁 Live Motion Path Trajectory:")
        lbl_c_hint.setStyleSheet("font-size: 11px; color: #94a3b8; font-weight: bold;")
        canvas_box.addWidget(lbl_c_hint)

        self.motion_canvas = MotionPathCanvas()
        self.motion_canvas.set_animation(self.current_anim)
        canvas_box.addWidget(self.motion_canvas)
        row_top.addLayout(canvas_box)

        layout.addLayout(row_top)

        # Card 2: JSON Motion Path Spec (Matching User's format)
        card_json = self._create_card_frame("📄 Motion Path Animation JSON (ទិន្នន័យ JSON សម្រាប់ Video Editor)")
        cj_layout = QVBoxLayout(card_json)
        cj_layout.setContentsMargins(12, 10, 12, 10)
        cj_layout.setSpacing(8)

        self.txt_json = QPlainTextEdit()
        self.txt_json.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0b0f17;
                color: #38bdf8;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #28303f;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        self.txt_json.setMaximumHeight(140)
        self._update_json_view()
        cj_layout.addWidget(self.txt_json)

        btn_row_j = QHBoxLayout()
        btn_copy_j = QPushButton("📋 Copy JSON to Clipboard")
        btn_copy_j.setStyleSheet("background-color: #272c38; color: #cbd5e1; padding: 5px 14px; border-radius: 4px;")
        btn_copy_j.clicked.connect(self._copy_json)
        btn_row_j.addWidget(btn_copy_j)

        btn_load_j = QPushButton("📥 Load from Custom JSON")
        btn_load_j.setStyleSheet("background-color: #272c38; color: #cbd5e1; padding: 5px 14px; border-radius: 4px;")
        btn_load_j.clicked.connect(self._load_json)
        btn_row_j.addWidget(btn_load_j)
        btn_row_j.addStretch()
        cj_layout.addLayout(btn_row_j)

        layout.addWidget(card_json)
        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # TAB 4: RESPONSIVE TEMPLATES & ONE-CLICK MEDIA SWAP
    # =========================================================================
    def _build_templates_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        lbl_t_hint = QLabel("Select a responsive template to re-target your movie for YouTube, TikTok, or Instagram:")
        lbl_t_hint.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(lbl_t_hint)

        # Template Cards Grid
        grid_tpl = QGridLayout()
        grid_tpl.setSpacing(14)

        templates_info = [
            ("16:9", "🎬 16:9 Cinema & YouTube", "Standard widescreen layout with Top-Right Logo and Lower-Third Footer", "#0284c7"),
            ("9:16", "📱 9:16 TikTok / Shorts / Reels", "Vertical portrait layout with Auto-Reframe, Floating Logo & Center Sponsor Ad", "#ec4899"),
            ("1:1",  "🔲 1:1 Square (Instagram & Facebook)", "Square frame with Top Banner Header, Center Video & Bottom Subtitles", "#8b5cf6"),
            ("pip",  "🎙️ React & Commentary Show", "Picture-in-Picture layout with Facecam box, Ticker Tape & Sponsor Loop", "#f59e0b")
        ]

        for idx, (aspect_id, title, desc, col) in enumerate(templates_info):
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: #181d28;
                    border: 1px solid #28303f;
                    border-radius: 8px;
                    padding: 12px;
                }}
                QFrame:hover {{
                    border: 1px solid {col};
                    background-color: #1e2533;
                }}
            """)
            c_vbox = QVBoxLayout(card)
            c_vbox.setSpacing(6)

            lbl_ct = QLabel(title)
            lbl_ct.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {col};")
            c_vbox.addWidget(lbl_ct)

            lbl_cd = QLabel(desc)
            lbl_cd.setWordWrap(True)
            lbl_cd.setStyleSheet("color: #94a3b8; font-size: 11px;")
            c_vbox.addWidget(lbl_cd)

            btn_apply_t = QPushButton(f"Apply {aspect_id} Template")
            btn_apply_t.setStyleSheet(f"background-color: {col}; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
            btn_apply_t.clicked.connect(lambda _, a=aspect_id: self._on_apply_template_clicked(a))
            c_vbox.addWidget(btn_apply_t)

            row = idx // 2
            col_idx = idx % 2
            grid_tpl.addWidget(card, row, col_idx)

        layout.addLayout(grid_tpl)

        # Media Swap Box
        card_swap = self._create_card_frame("🔄 One-Click Media Swap (ប្តូរវីដេអូ ឬរូបភាពដោយរក្សាទម្រង់ដើម)")
        cs_layout = QVBoxLayout(card_swap)
        cs_layout.setContentsMargins(14, 14, 14, 14)
        cs_layout.setSpacing(8)

        lbl_s_info = QLabel("លោកអ្នកអាចប្តូរ Background Video ឬ Logo ដោយរក្សាទុក Keyframe Animation និង Motion Path ទាំងអស់ដូចដើម ១០០% ដោយមិនបាច់កាត់តពីដំបូងឡើយ។")
        lbl_s_info.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        cs_layout.addWidget(lbl_s_info)

        row_swap_btns = QHBoxLayout()
        btn_swap_vid = QPushButton("🎬 Swap Background Video Only...")
        btn_swap_vid.setStyleSheet("background-color: #272c38; color: #38bdf8; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_swap_vid.clicked.connect(self._on_swap_video)
        row_swap_btns.addWidget(btn_swap_vid)

        btn_swap_logo = QPushButton("🏷️ Swap Logo Asset Only...")
        btn_swap_logo.setStyleSheet("background-color: #272c38; color: #38bdf8; font-weight: bold; padding: 6px 14px; border-radius: 4px;")
        btn_swap_logo.clicked.connect(self._on_browse_logo)
        row_swap_btns.addWidget(btn_swap_logo)
        row_swap_btns.addStretch()
        cs_layout.addLayout(row_swap_btns)
        layout.addWidget(card_swap)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    # =========================================================================
    # HELPERS & SLOTS
    # =========================================================================
    def _create_card_frame(self, title: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #181d28;
                border: 1px solid #28303f;
                border-radius: 8px;
            }
        """)
        return frame

    def _on_browse_logo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Logo Image", "", "Image Files (*.png *.jpg *.jpeg *.webp *.svg)")
        if f:
            self.txt_logo_path.setText(f)
            self.profile.logo_path = f

    def _on_browse_intro(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Intro Video Clip", "", "Video Files (*.mp4 *.mov *.mkv *.webm)")
        if f:
            self.txt_intro_path.setText(f)
            self.profile.intro_video_path = f

    def _on_browse_outro(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Outro Video Clip", "", "Video Files (*.mp4 *.mov *.mkv *.webm)")
        if f:
            self.txt_outro_path.setText(f)
            self.profile.outro_video_path = f

    def _on_browse_sponsor_logo(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Sponsor Logo", "", "Image Files (*.png *.jpg *.jpeg *.webp)")
        if f:
            self.txt_sp_logo.setText(f)

    def _on_browse_sponsor_qr(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select QR Code Image", "", "Image Files (*.png *.jpg *.jpeg *.webp)")
        if f:
            self.txt_sp_qr.setText(f)

    def _on_anim_preset_changed(self, idx: int):
        preset_keys = [
            "slide_left_right",
            "corner_orbit",
            "bottom_banner_pop",
            "bounce_pulse",
            "diagonal",
            "custom"
        ]
        key = preset_keys[min(idx, len(preset_keys) - 1)]
        dur = float(self.sld_anim_dur.value())
        self.current_anim = create_animation_preset(key, duration=dur)
        self.motion_canvas.set_animation(self.current_anim)
        self._update_json_view()

    def _on_speed_slider_changed(self, val: int):
        self.lbl_anim_dur_val.setText(f"{val:.1f}s")
        if self.current_anim:
            self.current_anim.duration = float(val)
            self.motion_canvas.set_animation(self.current_anim)
            self._update_json_view()

    def _sync_animation_settings(self):
        if not self.current_anim:
            return

        # Loop mode
        l_idx = self.cmb_loop_mode.currentIndex()
        if l_idx == 0:
            self.current_anim.loop = True
            self.current_anim.loop_count = 0
        elif l_idx == 1:
            self.current_anim.loop = True
            self.current_anim.loop_count = 2
        elif l_idx == 2:
            self.current_anim.loop = True
            self.current_anim.loop_count = 3
        elif l_idx == 3:
            self.current_anim.loop = True
            self.current_anim.loop_count = 5
        else:
            self.current_anim.loop = False
            self.current_anim.loop_count = 1

        # Direction
        d_idx = self.cmb_direction.currentIndex()
        self.current_anim.direction = "normal" if d_idx == 0 else ("reverse" if d_idx == 1 else "ping_pong")

        # Easing
        e_map = ["linear", "ease_in", "ease_out", "ease_in_out", "sine"]
        self.current_anim.easing = e_map[self.cmb_easing.currentIndex()]

        # Delays
        d_map = [0.0, 2.0, 5.0, 10.0]
        self.current_anim.delay = d_map[self.cmb_delay.currentIndex()]

        p_map = [0.0, 1.0, 2.0, 3.0, 5.0]
        self.current_anim.pause_between_loops = p_map[self.cmb_pause.currentIndex()]

        self.motion_canvas.set_animation(self.current_anim)
        self._update_json_view()

    def _update_json_view(self):
        if not self.current_anim:
            return
        sample_spec = {
            "type": "sponsor_ad",
            "asset": os.path.basename(self.txt_sp_logo.text()) if self.txt_sp_logo.text() else "sponsor_logo.png",
            "start": 10,
            "end": 120,
            "animation": self.current_anim.to_dict()
        }
        self.txt_json.setPlainText(json.dumps(sample_spec, indent=2, ensure_ascii=False))

    def _copy_json(self):
        from ui_v_PyQt6.qt_compat import QApplication
        QApplication.clipboard().setText(self.txt_json.toPlainText())
        QMessageBox.information(self, "Copied", "Motion Path JSON copied to clipboard!")

    def _load_json(self):
        try:
            data = json.loads(self.txt_json.toPlainText())
            anim_data = data.get("animation", data)
            self.current_anim = MotionPathAnimation.from_dict(anim_data)
            self.motion_canvas.set_animation(self.current_anim)
            QMessageBox.information(self, "Loaded", "Custom Motion Path successfully loaded!")
        except Exception as e:
            QMessageBox.warning(self, "Invalid JSON", f"Could not parse JSON:\n{e}")

    def _on_add_sponsor_clicked(self):
        name = self.txt_sp_name.text().strip() or "Sponsor"
        logo = self.txt_sp_logo.text().strip()
        qr = self.txt_sp_qr.text().strip()
        web = self.txt_sp_web.text().strip()
        times_str = self.txt_sp_times.text().strip()

        # Parse duration
        dur_map = [8.0, 12.0, 15.0, 20.0]
        dur = dur_map[self.cmb_sp_dur.currentIndex()]

        # Parse timestamps (e.g. 02:00, 05:00)
        times_secs = []
        for p in times_str.split(","):
            p = p.strip()
            if ":" in p:
                parts = p.split(":")
                try:
                    s = int(parts[0]) * 60 + int(parts[1])
                    times_secs.append(float(s))
                except Exception:
                    pass
            elif p.isdigit():
                times_secs.append(float(p))

        if not times_secs:
            times_secs = [120.0, 300.0, 600.0]

        for t in times_secs:
            ad = SponsorAdItem(
                name=name,
                asset=logo,
                qr_code_path=qr,
                website_text=web,
                start_time=t,
                end_time=t + dur,
                animation=self.current_anim if self.current_anim else create_animation_preset("slide_left_right")
            )
            self.profile.sponsors.append(ad)

        QMessageBox.information(self, "Sponsor Added", f"Added '{name}' at {len(times_secs)} scheduled timestamps across movie!")

    def _on_auto_generate_sponsors(self):
        if not self.profile.sponsors:
            self._on_add_sponsor_clicked()

        self.sponsor_ads_generated.emit(self.profile.sponsors)
        QMessageBox.information(self, "Sponsors Generated", f"Generated {len(self.profile.sponsors)} Sponsor Ads onto Timeline successfully!")

    def _on_apply_all_clicked(self):
        # Update profile values from UI controls
        self.profile.enable_logo = self.chk_enable_logo.isChecked()
        self.profile.logo_path = self.txt_logo_path.text().strip()
        self.profile.logo_size = self.sld_logo_size.value() / 100.0
        self.profile.logo_opacity = self.sld_logo_op.value() / 100.0

        pos_map = ["top_right", "top_left", "bottom_right", "bottom_left", "center"]
        self.profile.logo_position = pos_map[self.cmb_logo_pos.currentIndex()]
        if self.profile.logo_position == "top_right":
            self.profile.logo_x = 0.88
            self.profile.logo_y = 0.10
        elif self.profile.logo_position == "top_left":
            self.profile.logo_x = 0.12
            self.profile.logo_y = 0.10
        elif self.profile.logo_position == "bottom_right":
            self.profile.logo_x = 0.88
            self.profile.logo_y = 0.85
        elif self.profile.logo_position == "bottom_left":
            self.profile.logo_x = 0.12
            self.profile.logo_y = 0.85
        else:
            self.profile.logo_x = 0.50
            self.profile.logo_y = 0.50

        anim_map = ["none", "pulse", "fade", "rotate", "bounce"]
        self.profile.logo_animation = anim_map[self.cmb_logo_anim.currentIndex()]

        self.profile.enable_intro = self.chk_enable_intro.isChecked()
        self.profile.intro_video_path = self.txt_intro_path.text().strip()
        self.profile.enable_outro = self.chk_enable_outro.isChecked()
        self.profile.outro_video_path = self.txt_outro_path.text().strip()

        self.profile.enable_footer = self.chk_enable_footer.isChecked()
        self.profile.footer_text = self.txt_footer_title.text().strip()
        self.profile.footer_subtext = self.txt_footer_sub.text().strip()

        self.apply_branding_requested.emit(self.profile)
        if self.on_apply_branding:
            self.on_apply_branding(self.profile)

        QMessageBox.information(self, "Branding Applied", "Global Branding applied to project successfully!")

    def _on_apply_template_clicked(self, aspect_id: str):
        self.template_applied.emit(aspect_id)
        if self.on_apply_template:
            self.on_apply_template(aspect_id)
        QMessageBox.information(self, "Template Applied", f"Layout re-targeted to {aspect_id} format!")

    def _on_swap_video(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Background Video to Swap", "", "Video Files (*.mp4 *.mkv *.mov *.webm *.avi)")
        if f:
            if hasattr(self, "on_video_swap") and self.on_video_swap:
                self.on_video_swap(f)
            QMessageBox.information(self, "Video Swapped", f"Background Video swapped while preserving all branding & overlays!")
