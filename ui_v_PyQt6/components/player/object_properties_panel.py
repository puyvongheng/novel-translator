"""
Object Properties Panel / Inspector Component
Provides an adaptive studio inspector panel for the currently selected object:
- Image / Sticker / GIF: dimensions, rotation, opacity, sharpness, blur, timestamps
- Frosted Glass / Blur / Mosaic / Blackout Box: blur strength, corner radius, style mode, glass tint
- Subtitle / Text: text editor, font family, font size, bold/italic, color, background, timing
- Vector Shape: shape type (rect, rounded, circle, star, badge), fill, border, width
- Voice Dub / Audio Clip: speaker voice profile, speech rate, pitch, volume, timing
"""

import os
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QCheckBox, QSlider,
    QFrame, QGroupBox, QScrollArea, QStackedWidget, QGridLayout,
    QDoubleSpinBox, QSpinBox, QColorDialog, QColor, QFont, Qt, Signal,
    QPixmap, QPainter, QPen, QBrush, QRectF, QMenu, QCursor, QPainterPath,
    QLinearGradient
)
from ui_v_PyQt6.icons import (
    get_export_icon, get_speed_icon, get_sync_icon, get_qta_icon
)
from utils import format_timestamp
from config import VOICE_PROFILES, KHMER_VOICES
from services.dubbing.audio_effects import (
    CAPCUT_VOICE_EFFECTS, apply_voice_effect_to_file, preview_voice_effect
)


class CCDialogueDensityChart(QWidget):
    """
    High-performance custom QPainter visual chart displaying:
    1. Speech Density Heatmap across timeline (10 time buckets: 0-10% -> 90-100%)
    2. Subtitle Length Distribution (Short, Medium, Long) with colorful segmented bar
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(125)
        self.buckets = [0] * 10
        self.max_bucket = 1
        self.short_pct = 0.0
        self.med_pct = 0.0
        self.long_pct = 0.0
        self.total_lines = 0

    def set_data(self, buckets: list, short_pct: float, med_pct: float, long_pct: float, total_lines: int):
        self.buckets = buckets if (buckets and len(buckets) == 10) else [0] * 10
        self.max_bucket = max(1, max(self.buckets))
        self.short_pct = max(0.0, float(short_pct))
        self.med_pct = max(0.0, float(med_pct))
        self.long_pct = max(0.0, float(long_pct))
        self.total_lines = int(total_lines)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        # Background card
        painter.setBrush(QColor("#11141c"))
        painter.setPen(QPen(QColor("#232b3b"), 1))
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 6, 6)

        # Title: Timeline Speech Density
        painter.setPen(QColor("#94a3b8"))
        f = painter.font()
        f.setPointSize(8)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRectF(10, 6, w - 20, 16), Qt.AlignmentFlag.AlignLeft, "📈 TIMELINE DIALOGUE DENSITY (ប្លង់សន្ទនាតាមម៉ោង)")

        # Bar chart area: y = 24 to y = 74
        chart_top = 24.0
        chart_bottom = 74.0
        chart_h = chart_bottom - chart_top
        margin_x = 10.0
        avail_w = w - (margin_x * 2)
        n_bars = 10
        gap = 3.0
        bar_w = max(4.0, (avail_w - (gap * (n_bars - 1))) / n_bars)

        for i, val in enumerate(self.buckets):
            x = margin_x + i * (bar_w + gap)
            ratio = val / float(self.max_bucket) if self.max_bucket > 0 else 0.0
            bh = max(3.0, ratio * (chart_h - 10))
            by = chart_bottom - bh

            # Gradient bar
            grad = QLinearGradient(x, by, x, chart_bottom)
            if ratio > 0.6:
                grad.setColorAt(0, QColor("#38bdf8"))
                grad.setColorAt(1, QColor("#6366f1"))
            elif ratio > 0.2:
                grad.setColorAt(0, QColor("#0284c7"))
                grad.setColorAt(1, QColor("#4338ca"))
            else:
                grad.setColorAt(0, QColor("#334155"))
                grad.setColorAt(1, QColor("#1e293b"))

            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, by, bar_w, bh), 2, 2)

            # Label interval 0%, 50%, 100%
            if i in (0, 5, 9):
                txt = "0%" if i == 0 else ("50%" if i == 5 else "100%")
                painter.setPen(QColor("#64748b"))
                f_sub = painter.font()
                f_sub.setPointSize(7)
                painter.setFont(f_sub)
                painter.drawText(QRectF(x - 10, chart_bottom + 1, bar_w + 20, 12), Qt.AlignmentFlag.AlignCenter, txt)

        # Bottom Segmented Bar: Line Length Breakdown
        seg_y = 88.0
        seg_h = 7.0
        seg_w = avail_w

        sw = seg_w * (self.short_pct / 100.0) if self.total_lines > 0 else 0
        mw = seg_w * (self.med_pct / 100.0) if self.total_lines > 0 else 0
        lw = max(0.0, seg_w - sw - mw) if self.total_lines > 0 else 0

        cur_x = margin_x
        painter.setBrush(QColor("#1e293b"))
        painter.drawRoundedRect(QRectF(cur_x, seg_y, seg_w, seg_h), 3, 3)

        if self.total_lines > 0:
            if sw > 0:
                painter.setBrush(QColor("#10b981"))
                painter.drawRoundedRect(QRectF(cur_x, seg_y, sw, seg_h), 2, 2)
                cur_x += sw
            if mw > 0:
                painter.setBrush(QColor("#f59e0b"))
                painter.drawRoundedRect(QRectF(cur_x, seg_y, mw, seg_h), 2, 2)
                cur_x += mw
            if lw > 0:
                painter.setBrush(QColor("#ef4444"))
                painter.drawRoundedRect(QRectF(cur_x, seg_y, lw, seg_h), 2, 2)

        # Legend under segmented bar:
        legend_y = seg_y + seg_h + 3.0
        f_leg = painter.font()
        f_leg.setPointSize(7)
        painter.setFont(f_leg)

        # Dot 1: Short (<20)
        painter.setBrush(QColor("#10b981"))
        painter.drawEllipse(QRectF(margin_x, legend_y + 2, 6, 6))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRectF(margin_x + 9, legend_y, 65, 12), Qt.AlignmentFlag.AlignLeft, f"ខ្លី: {int(self.short_pct)}%")

        # Dot 2: Medium (20-45)
        m_x = margin_x + 72
        painter.setBrush(QColor("#f59e0b"))
        painter.drawEllipse(QRectF(m_x, legend_y + 2, 6, 6))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRectF(m_x + 9, legend_y, 75, 12), Qt.AlignmentFlag.AlignLeft, f"មធ្យម: {int(self.med_pct)}%")

        # Dot 3: Long (>45)
        l_x = margin_x + 152
        painter.setBrush(QColor("#ef4444"))
        painter.drawEllipse(QRectF(l_x, legend_y + 2, 6, 6))
        painter.setPen(QColor("#94a3b8"))
        painter.drawText(QRectF(l_x + 9, legend_y, 65, 12), Qt.AlignmentFlag.AlignLeft, f"វែង: {int(self.long_pct)}%")


class ObjectPropertiesPanel(QWidget):
    """
    Dynamic properties inspector that adapts its controls to the selected item type.
    Emits item_modified(item) whenever any property is changed by the user.
    """
    item_modified = Signal(object)
    sub_text_modified = Signal(int, str)  # (sub_index, new_khmer_text)
    sub_time_modified = Signal(int, float, float)  # (sub_index, start, end)
    audio_modified = Signal(object)  # (audio_dict)
    voice_effect_applied = Signal(object, str)  # (target_obj, effect_name)
    batch_voice_effect_applied = Signal(str, str, str)  # (effect_name, scope, character_name)
    request_canvas_refresh = Signal()
    request_fix_overlaps = Signal()
    request_jump_first_sub = Signal()
    request_export_srt = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_object = None
        self.target_type = None  # "image", "video", "blur_box", "text", "subtitle", "shape", "audio", "cc_analytics"
        self.target_sub_idx = -1
        self._updating_ui = False

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Header Badge
        self.header_card = QFrame()
        self.header_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        h_layout = QHBoxLayout(self.header_card)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(8)

        self.lbl_icon = QLabel("🛠️")
        self.lbl_icon.setStyleSheet("font-size: 16px;")
        h_layout.addWidget(self.lbl_icon)

        self.lbl_title = QLabel("Properties Inspector (ផ្ទាំងកែវត្ថុ)")
        self.lbl_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #38bdf8;")
        h_layout.addWidget(self.lbl_title, 1)

        self.lbl_badge = QLabel("None")
        self.lbl_badge.setStyleSheet("""
            background-color: #334155;
            color: #94a3b8;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        h_layout.addWidget(self.lbl_badge)
        main_layout.addWidget(self.header_card)

        # Scrollable Properties Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        self.container_widget = QWidget()
        self.container_layout = QVBoxLayout(self.container_widget)
        self.container_layout.setContentsMargins(2, 2, 2, 2)
        self.container_layout.setSpacing(8)

        # ---------------- 1. EMPTY PLACEHOLDER ----------------
        self.empty_card = QFrame()
        self.empty_card.setStyleSheet("""
            QFrame {
                background-color: #1e2530;
                border: 1px dashed #334155;
                border-radius: 6px;
                padding: 24px 12px;
            }
        """)
        e_layout = QVBoxLayout(self.empty_card)
        e_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        e_layout.setSpacing(6)
        lbl_e1 = QLabel("👆 មិនទាន់ជ្រើសរើសវត្ថុណាមួយទេ")
        lbl_e1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_e1.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 12px;")
        lbl_e2 = QLabel("សូមចុចលើ Image, Text, Frosted Blur Box\nឬ Subtitle / Audio Clip លើ Timeline ដើម្បីកែប្រែ Properties។")
        lbl_e2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_e2.setStyleSheet("color: #64748b; font-size: 11px;")
        e_layout.addWidget(lbl_e1)
        e_layout.addWidget(lbl_e2)
        self.container_layout.addWidget(self.empty_card)

        # ---------------- 2. TIME & LIFESPAN GROUP ----------------
        self.group_timing = QGroupBox("⏱️ Timestamps & Duration (ពេលវេលា)")
        self._style_groupbox(self.group_timing)
        g_time_layout = QVBoxLayout(self.group_timing)
        g_time_layout.setContentsMargins(8, 12, 8, 8)
        g_time_layout.setSpacing(6)

        row_t1 = QHBoxLayout()
        row_t1.addWidget(QLabel("Start Time (s):"))
        self.spin_start_time = QDoubleSpinBox()
        self.spin_start_time.setRange(0.0, 99999.0)
        self.spin_start_time.setSingleStep(0.1)
        self.spin_start_time.setDecimals(2)
        self.spin_start_time.setStyleSheet(self._input_style())
        self.spin_start_time.valueChanged.connect(self._on_timing_changed)
        row_t1.addWidget(self.spin_start_time, 1)

        row_t1.addWidget(QLabel("End Time (s):"))
        self.spin_end_time = QDoubleSpinBox()
        self.spin_end_time.setRange(0.0, 99999.0)
        self.spin_end_time.setSingleStep(0.1)
        self.spin_end_time.setDecimals(2)
        self.spin_end_time.setStyleSheet(self._input_style())
        self.spin_end_time.valueChanged.connect(self._on_timing_changed)
        row_t1.addWidget(self.spin_end_time, 1)
        g_time_layout.addLayout(row_t1)

        row_dur = QHBoxLayout()
        self.lbl_time_formatted = QLabel("00:00:00,000 ➔ 00:00:05,000")
        self.lbl_time_formatted.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: bold;")
        row_dur.addWidget(self.lbl_time_formatted)
        row_dur.addStretch()
        self.lbl_dur_badge = QLabel("Dur: 5.00s")
        self.lbl_dur_badge.setStyleSheet("background-color: #0369a1; color: #ffffff; border-radius: 3px; padding: 1px 6px; font-size: 10px;")
        row_dur.addWidget(self.lbl_dur_badge)
        g_time_layout.addLayout(row_dur)

        self.container_layout.addWidget(self.group_timing)

        # ---------------- 3. GEOMETRY / TRANSFORM GROUP (for Visual Canvas Items) ----------------
        self.group_transform = QGroupBox("📐 Transform & Position (ទំហំ និងទីតាំង)")
        self._style_groupbox(self.group_transform)
        g_trans_layout = QVBoxLayout(self.group_transform)
        g_trans_layout.setContentsMargins(8, 12, 8, 8)
        g_trans_layout.setSpacing(6)

        # Pos X / Y
        row_pos = QHBoxLayout()
        row_pos.addWidget(QLabel("Position X (%):"))
        self.spin_pos_x = QDoubleSpinBox()
        self.spin_pos_x.setRange(0.0, 100.0)
        self.spin_pos_x.setSingleStep(1.0)
        self.spin_pos_x.setDecimals(1)
        self.spin_pos_x.setStyleSheet(self._input_style())
        self.spin_pos_x.valueChanged.connect(self._on_transform_changed)
        row_pos.addWidget(self.spin_pos_x, 1)

        row_pos.addWidget(QLabel("Position Y (%):"))
        self.spin_pos_y = QDoubleSpinBox()
        self.spin_pos_y.setRange(0.0, 100.0)
        self.spin_pos_y.setSingleStep(1.0)
        self.spin_pos_y.setDecimals(1)
        self.spin_pos_y.setStyleSheet(self._input_style())
        self.spin_pos_y.valueChanged.connect(self._on_transform_changed)
        row_pos.addWidget(self.spin_pos_y, 1)
        g_trans_layout.addLayout(row_pos)

        # Size W / H
        row_size = QHBoxLayout()
        row_size.addWidget(QLabel("Width (%):"))
        self.spin_size_w = QDoubleSpinBox()
        self.spin_size_w.setRange(1.0, 200.0)
        self.spin_size_w.setSingleStep(1.0)
        self.spin_size_w.setDecimals(1)
        self.spin_size_w.setStyleSheet(self._input_style())
        self.spin_size_w.valueChanged.connect(self._on_transform_changed)
        row_size.addWidget(self.spin_size_w, 1)

        row_size.addWidget(QLabel("Height (%):"))
        self.spin_size_h = QDoubleSpinBox()
        self.spin_size_h.setRange(1.0, 200.0)
        self.spin_size_h.setSingleStep(1.0)
        self.spin_size_h.setDecimals(1)
        self.spin_size_h.setStyleSheet(self._input_style())
        self.spin_size_h.valueChanged.connect(self._on_transform_changed)
        row_size.addWidget(self.spin_size_h, 1)
        g_trans_layout.addLayout(row_size)

        # Rotation & Opacity
        row_rot = QHBoxLayout()
        row_rot.addWidget(QLabel("Rotation (°):"))
        self.spin_rotation = QDoubleSpinBox()
        self.spin_rotation.setRange(-360.0, 360.0)
        self.spin_rotation.setSingleStep(5.0)
        self.spin_rotation.setStyleSheet(self._input_style())
        self.spin_rotation.valueChanged.connect(self._on_transform_changed)
        row_rot.addWidget(self.spin_rotation, 1)

        row_rot.addWidget(QLabel("Opacity (%):"))
        self.spin_opacity = QSpinBox()
        self.spin_opacity.setRange(0, 100)
        self.spin_opacity.setSingleStep(5)
        self.spin_opacity.setStyleSheet(self._input_style())
        self.spin_opacity.valueChanged.connect(self._on_transform_changed)
        row_rot.addWidget(self.spin_opacity, 1)
        g_trans_layout.addLayout(row_rot)

        self.container_layout.addWidget(self.group_transform)

        # ---------------- 4. BLUR & FROSTED GLASS GROUP ----------------
        self.group_blur = QGroupBox("🌫️ Frosted Glass & Blur Style (បិទបាំងវីដេអូ)")
        self._style_groupbox(self.group_blur)
        b_layout = QVBoxLayout(self.group_blur)
        b_layout.setContentsMargins(8, 12, 8, 8)
        b_layout.setSpacing(6)

        row_bmode = QHBoxLayout()
        row_bmode.addWidget(QLabel("Censor Mode:"))
        self.combo_blur_mode = QComboBox()
        self.combo_blur_mode.addItem("✨ Frosted Glass (កញ្ចក់បែកផ្សែង)", "glass")
        self.combo_blur_mode.addItem("🌫️ Smooth Blur (ព្រិលរលូន)", "blur")
        self.combo_blur_mode.addItem("🔲 Mosaic Pixelate (ការ៉ូៗ)", "mosaic")
        self.combo_blur_mode.addItem("⬛ Blackout Bar (បិទខ្មៅ)", "blackout")
        self.combo_blur_mode.setStyleSheet(self._input_style())
        self.combo_blur_mode.currentIndexChanged.connect(self._on_blur_props_changed)
        row_bmode.addWidget(self.combo_blur_mode, 1)
        b_layout.addLayout(row_bmode)

        # Blur Intensity Slider
        b_layout.addWidget(QLabel("Blur Intensity (កម្រិតព្រិល):"))
        self.slider_blur_strength = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur_strength.setRange(5, 60)
        self.slider_blur_strength.setValue(25)
        self.slider_blur_strength.valueChanged.connect(self._on_blur_props_changed)
        b_layout.addWidget(self.slider_blur_strength)

        # Corner Radius
        row_rad = QHBoxLayout()
        row_rad.addWidget(QLabel("Corner Radius (គែមមូល):"))
        self.spin_blur_radius = QSpinBox()
        self.spin_blur_radius.setRange(0, 50)
        self.spin_blur_radius.setValue(0)
        self.spin_blur_radius.setStyleSheet(self._input_style())
        self.spin_blur_radius.valueChanged.connect(self._on_blur_props_changed)
        row_rad.addWidget(self.spin_blur_radius, 1)
        b_layout.addLayout(row_rad)

        # Glass Tint Color
        row_tint = QHBoxLayout()
        row_tint.addWidget(QLabel("Glass Tint Color:"))
        self.btn_tint_color = QPushButton(" Color")
        self.btn_tint_color.setStyleSheet("background-color: #0f172a; color: #ffffff; border: 1px solid #475569; border-radius: 4px; padding: 4px 8px;")
        self.btn_tint_color.clicked.connect(self._pick_tint_color)
        row_tint.addWidget(self.btn_tint_color, 1)
        b_layout.addLayout(row_tint)

        self.container_layout.addWidget(self.group_blur)

        # ---------------- 5. TEXT & SUBTITLES GROUP ----------------
        self.group_text = QGroupBox("📝 Typography & Subtitle (អត្ថបទ)")
        self._style_groupbox(self.group_text)
        t_layout = QVBoxLayout(self.group_text)
        t_layout.setContentsMargins(8, 12, 8, 8)
        t_layout.setSpacing(6)

        t_layout.addWidget(QLabel("Dialogue / Text Content:"))
        self.txt_editor = QTextEdit()
        self.txt_editor.setMaximumHeight(70)
        self.txt_editor.setStyleSheet(self._input_style())
        self.txt_editor.textChanged.connect(self._on_text_content_changed)
        t_layout.addWidget(self.txt_editor)

        row_font = QHBoxLayout()
        row_font.addWidget(QLabel("Font:"))
        self.combo_font = QComboBox()
        self.combo_font.addItems(["Kantumruy Pro", "Battambang", "Moul", "Bokor", "Siemreap", "Arial", "Segoe UI"])
        self.combo_font.setStyleSheet(self._input_style())
        self.combo_font.currentIndexChanged.connect(self._on_text_props_changed)
        row_font.addWidget(self.combo_font, 1)

        row_font.addWidget(QLabel("Size:"))
        self.spin_font_size = QSpinBox()
        self.spin_font_size.setRange(10, 120)
        self.spin_font_size.setValue(28)
        self.spin_font_size.setStyleSheet(self._input_style())
        self.spin_font_size.valueChanged.connect(self._on_text_props_changed)
        row_font.addWidget(self.spin_font_size)
        t_layout.addLayout(row_font)

        row_styles = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold (ដិត)")
        self.chk_bold.setStyleSheet("color: #f1f5f9; font-weight: bold;")
        self.chk_bold.toggled.connect(self._on_text_props_changed)
        row_styles.addWidget(self.chk_bold)

        self.chk_italic = QCheckBox("Italic (ទ្រេត)")
        self.chk_italic.setStyleSheet("color: #f1f5f9; font-style: italic;")
        self.chk_italic.toggled.connect(self._on_text_props_changed)
        row_styles.addWidget(self.chk_italic)

        self.btn_text_color = QPushButton(" Text Color")
        self.btn_text_color.setStyleSheet("background-color: #facc15; color: #000000; font-weight: bold; border-radius: 4px; padding: 4px 8px;")
        self.btn_text_color.clicked.connect(self._pick_text_color)
        row_styles.addWidget(self.btn_text_color)
        t_layout.addLayout(row_styles)

        # Text & CC Animation Selector (ចលនាអក្សរ & Karaoke)
        row_anim = QHBoxLayout()
        row_anim.addWidget(QLabel("🎭 Animation:"))
        self.combo_anim = QComboBox()
        self.combo_anim.addItem("🚫 None (គ្មានចលនា)", "none")
        self.combo_anim.addItem("⚡ Karaoke Highlight (រត់ពណ៌)", "karaoke")
        self.combo_anim.addItem("💥 Pop-up Zoom (ពង្រីក)", "popup")
        self.combo_anim.addItem("🌫️ Fade In / Out (ស្រាល)", "fade")
        self.combo_anim.addItem("⬆️ Slide Up (រុញឡើង)", "slide")
        self.combo_anim.addItem("🏀 Bounce (លោត)", "bounce")
        self.combo_anim.addItem("⌨️ Typewriter (វាយអក្សរ)", "typewriter")
        self.combo_anim.addItem("📰 News Ticker (រត់ដូចព័ត៌មាន)", "marquee")
        self.combo_anim.setStyleSheet(self._input_style())
        self.combo_anim.currentIndexChanged.connect(self._on_text_props_changed)
        row_anim.addWidget(self.combo_anim, 1)

        self.btn_hi_color = QPushButton(" Hi Color")
        self.btn_hi_color.setToolTip("Karaoke Highlight Color (ពណ៌អក្សររត់)")
        self.btn_hi_color.setStyleSheet("background-color: #00e5ff; color: #000000; font-weight: bold; border-radius: 4px; padding: 4px 6px;")
        self.btn_hi_color.clicked.connect(self._pick_highlight_color)
        row_anim.addWidget(self.btn_hi_color)
        t_layout.addLayout(row_anim)

        # News Ticker Marquee Direction, Loop & Speed Sub-Controls
        self.group_marquee_opts = QWidget()
        m_layout = QVBoxLayout(self.group_marquee_opts)
        m_layout.setContentsMargins(4, 4, 4, 4)
        m_layout.setSpacing(4)
        self.group_marquee_opts.setStyleSheet("background-color: #171d2b; border: 1px dashed #38bdf8; border-radius: 6px; padding: 4px;")

        m_row1 = QHBoxLayout()
        m_row1.addWidget(QLabel("🧭 Direction:"))
        self.combo_marquee_dir = QComboBox()
        self.combo_marquee_dir.addItem("⬅️ ស្តាំទៅឆ្វេង (Right to Left)", "right_to_left")
        self.combo_marquee_dir.addItem("➡️ ឆ្វេងទៅស្តាំ (Left to Right)", "left_to_right")
        self.combo_marquee_dir.addItem("⬆️ ពីក្រោមឡើងលើ (Bottom to Up)", "bottom_to_top")
        self.combo_marquee_dir.addItem("⬇️ ពីលើចុះក្រោម (Top to Down)", "top_to_bottom")
        self.combo_marquee_dir.setStyleSheet(self._input_style())
        self.combo_marquee_dir.currentIndexChanged.connect(self._on_text_props_changed)
        m_row1.addWidget(self.combo_marquee_dir, 1)
        m_layout.addLayout(m_row1)

        m_row2 = QHBoxLayout()
        self.chk_marquee_loop = QCheckBox("🔁 Loop (រត់វិលជុំវិញមិនចេះចប់)")
        self.chk_marquee_loop.setChecked(True)
        self.chk_marquee_loop.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.chk_marquee_loop.toggled.connect(self._on_text_props_changed)
        m_row2.addWidget(self.chk_marquee_loop)

        m_row2.addWidget(QLabel("Speed:"))
        self.spin_marquee_speed = QDoubleSpinBox()
        self.spin_marquee_speed.setRange(0.2, 5.0)
        self.spin_marquee_speed.setSingleStep(0.2)
        self.spin_marquee_speed.setValue(1.0)
        self.spin_marquee_speed.setStyleSheet(self._input_style())
        self.spin_marquee_speed.valueChanged.connect(self._on_text_props_changed)
        m_row2.addWidget(self.spin_marquee_speed)
        m_layout.addLayout(m_row2)

        self.group_marquee_opts.hide()
        t_layout.addWidget(self.group_marquee_opts)

        self.container_layout.addWidget(self.group_text)

        # ---------------- 6. IMAGE / GIF FX GROUP ----------------
        self.group_image_fx = QGroupBox("🎨 Image Effects & Filters (រូបភាព)")
        self._style_groupbox(self.group_image_fx)
        i_layout = QVBoxLayout(self.group_image_fx)
        i_layout.setContentsMargins(8, 12, 8, 8)
        i_layout.setSpacing(6)

        i_layout.addWidget(QLabel("Sharpness (ធ្វើឱ្យរូបច្បាស់):"))
        self.slider_sharpness = QSlider(Qt.Orientation.Horizontal)
        self.slider_sharpness.setRange(0, 100)
        self.slider_sharpness.setValue(0)
        self.slider_sharpness.valueChanged.connect(self._on_image_fx_changed)
        i_layout.addWidget(self.slider_sharpness)

        i_layout.addWidget(QLabel("Image Blur (ព្រិលរូបភាព):"))
        self.slider_img_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_img_blur.setRange(0, 100)
        self.slider_img_blur.setValue(0)
        self.slider_img_blur.valueChanged.connect(self._on_image_fx_changed)
        i_layout.addWidget(self.slider_img_blur)

        btn_open_lut = QPushButton("🎨 Video Color Presets (Cinematic LUTs)...")
        btn_open_lut.setStyleSheet("background-color: #272f3f; color: #f97316; font-weight: bold; border: 1px solid #f97316; border-radius: 4px; padding: 6px; margin-top: 4px;")
        btn_open_lut.clicked.connect(self._open_color_presets)
        i_layout.addWidget(btn_open_lut)

        self.container_layout.addWidget(self.group_image_fx)

        # ---------------- 7. MODERN STUDIO SHAPE & LINE PROPERTIES PANEL ----------------
        self.group_shape = self._build_studio_shape_group()
        self.container_layout.addWidget(self.group_shape)
        self.group_shape.hide()

        # ---------------- 7b. ADVANCED PHOTOSHOP-GRADE SHAPE PANEL ----------------
        self.group_ps_shape = self._create_photoshop_shape_panel()
        self.container_layout.addWidget(self.group_ps_shape)
        self.group_ps_shape.hide()

        # ---------------- 8. AUDIO / VOICE DUBBING GROUP ----------------
        self.group_audio = QGroupBox("🎙️ Voice Dub & Audio Tuning (សំឡេង)")
        self._style_groupbox(self.group_audio)
        a_layout = QVBoxLayout(self.group_audio)
        a_layout.setContentsMargins(8, 12, 8, 8)
        a_layout.setSpacing(6)

        # Voice Profile
        self.lbl_voice_profile = QLabel("Speaker Voice Profile:")
        a_layout.addWidget(self.lbl_voice_profile)
        self.combo_voice_profile = QComboBox()
        for vname in VOICE_PROFILES.keys():
            self.combo_voice_profile.addItem(vname)
        self.combo_voice_profile.setStyleSheet(self._input_style())
        self.combo_voice_profile.currentIndexChanged.connect(self._on_audio_props_changed)
        a_layout.addWidget(self.combo_voice_profile)

        # Volume & Speed
        row_vol_spd = QHBoxLayout()
        row_vol_spd.addWidget(QLabel("Vol (%):"))
        self.spin_audio_vol = QSpinBox()
        self.spin_audio_vol.setRange(0, 300)
        self.spin_audio_vol.setValue(100)
        self.spin_audio_vol.setStyleSheet(self._input_style())
        self.spin_audio_vol.valueChanged.connect(self._on_audio_props_changed)
        row_vol_spd.addWidget(self.spin_audio_vol, 1)

        row_vol_spd.addWidget(QLabel("Spd (x):"))
        self.spin_audio_speed = QDoubleSpinBox()
        self.spin_audio_speed.setRange(0.25, 4.0)
        self.spin_audio_speed.setSingleStep(0.05)
        self.spin_audio_speed.setValue(1.0)
        self.spin_audio_speed.setStyleSheet(self._input_style())
        self.spin_audio_speed.valueChanged.connect(self._on_audio_props_changed)
        row_vol_spd.addWidget(self.spin_audio_speed, 1)
        a_layout.addLayout(row_vol_spd)

        # Rate & Pitch Adjustments
        self.row_rates = QHBoxLayout()
        self.row_rates.addWidget(QLabel("Rate (%):"))
        self.spin_audio_rate = QSpinBox()
        self.spin_audio_rate.setRange(-50, 100)
        self.spin_audio_rate.setValue(0)
        self.spin_audio_rate.setStyleSheet(self._input_style())
        self.spin_audio_rate.valueChanged.connect(self._on_audio_props_changed)
        self.row_rates.addWidget(self.spin_audio_rate, 1)

        self.row_rates.addWidget(QLabel("Pitch (%):"))
        self.spin_audio_pitch = QSpinBox()
        self.spin_audio_pitch.setRange(-50, 50)
        self.spin_audio_pitch.setValue(0)
        self.spin_audio_pitch.setStyleSheet(self._input_style())
        self.spin_audio_pitch.valueChanged.connect(self._on_audio_props_changed)
        self.row_rates.addWidget(self.spin_audio_pitch, 1)
        a_layout.addLayout(self.row_rates)

        # CapCut-Style Voice Effects (Voice Changers)
        row_fx_head = QHBoxLayout()
        row_fx_head.addWidget(QLabel("✨ CapCut Voice Effects (កែសំឡេង):"))
        self.btn_open_capcut_studio = QPushButton("🎛️ Full Studio...")
        self.btn_open_capcut_studio.setToolTip("បើកផ្ទាំង CapCut Voice Effects Studio ពេញលេញ")
        self.btn_open_capcut_studio.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_capcut_studio.setStyleSheet("""
            QPushButton {
                background-color: #4338ca;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
                border: 1px solid #6366f1;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton:hover { background-color: #4f46e5; }
        """)
        self.btn_open_capcut_studio.clicked.connect(self._on_open_capcut_dialog_from_panel)
        row_fx_head.addWidget(self.btn_open_capcut_studio)
        a_layout.addLayout(row_fx_head)

        self.combo_voice_effect = QComboBox()
        for fx_key, fx_label, _ in CAPCUT_VOICE_EFFECTS:
            self.combo_voice_effect.addItem(fx_label, fx_key)
        self.combo_voice_effect.setStyleSheet(self._input_style())
        self.combo_voice_effect.currentIndexChanged.connect(self._on_audio_props_changed)
        a_layout.addWidget(self.combo_voice_effect)

        # Quick Preset Chips Row for Top CapCut Voice Effects
        row_chips = QHBoxLayout()
        row_chips.setSpacing(4)
        chips_data = [
            ("👶 កូនក្មេង", "kid"),
            ("🤖 Robot", "robot"),
            ("🐿️ កំប្រុក", "chipmunk"),
            ("🐻 សំឡេងធំ", "deep_male"),
            ("🏛️ អេកូ", "echo_hall"),
            ("🔄 ដើម", "none")
        ]
        chip_style = """
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 3px 4px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """
        for c_label, c_key in chips_data:
            btn_chip = QPushButton(c_label)
            btn_chip.setStyleSheet(chip_style)
            btn_chip.setCursor(Qt.CursorShape.PointingHandCursor)
            def _apply_chip(k=c_key):
                idx = self.combo_voice_effect.findData(k)
                if idx >= 0:
                    self.combo_voice_effect.setCurrentIndex(idx)
                    self._on_preview_voice_effect()
            btn_chip.clicked.connect(_apply_chip)
            row_chips.addWidget(btn_chip)
        a_layout.addLayout(row_chips)

        # Scope Selector (Clip vs Character vs Full Project)
        row_scope = QHBoxLayout()
        row_scope.setSpacing(6)
        lbl_sc = QLabel("🎯 Scope:")
        lbl_sc.setStyleSheet("font-size: 10px; color: #94a3b8; font-weight: bold;")
        row_scope.addWidget(lbl_sc)

        self.combo_fx_scope = QComboBox()
        self.combo_fx_scope.addItem("🎯 Clip នេះ (Only Clip)", "clip")
        self.combo_fx_scope.addItem("🎭 តួអង្គនេះ (Character)", "character")
        self.combo_fx_scope.addItem("🌐 គ្រប់បន្ទាត់ (Full All)", "all")
        self.combo_fx_scope.setStyleSheet(self._input_style())
        row_scope.addWidget(self.combo_fx_scope, 1)
        a_layout.addLayout(row_scope)

        # Preview & Apply Buttons
        row_fx_btns = QHBoxLayout()
        self.btn_preview_fx = QPushButton(" ▶️ ស្តាប់ (Preview)")
        self.btn_preview_fx.setStyleSheet("""
            QPushButton {
                background-color: #0369a1;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        self.btn_preview_fx.clicked.connect(self._on_preview_voice_effect)
        row_fx_btns.addWidget(self.btn_preview_fx, 1)

        self.btn_apply_fx = QPushButton(" ✨ អនុវត្ត Effect")
        self.btn_apply_fx.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #10b981;
            }
        """)
        self.btn_apply_fx.clicked.connect(self._on_apply_voice_effect)
        row_fx_btns.addWidget(self.btn_apply_fx, 1)
        a_layout.addLayout(row_fx_btns)

        self.lbl_fx_status = QLabel("")
        self.container_layout.addWidget(self.group_audio)

        # ---------------- 9. CLOSED CAPTIONS & SUBTITLE ANALYTICS GROUP ----------------
        self.group_cc_stats = self._build_cc_analytics_group()
        self.container_layout.addWidget(self.group_cc_stats)
        self.group_cc_stats.hide()

        self.container_layout.addStretch()
        scroll.setWidget(self.container_widget)
        main_layout.addWidget(scroll, 1)

        # Set initial empty view
        self._show_empty_state()

    def _style_groupbox(self, gbox: QGroupBox):
        gbox.setStyleSheet("""
            QGroupBox {
                margin: 0px;
                padding-top: 14px;
                border: 1px solid #334155;
                border-radius: 6px;
                background-color: #1e2530;
                font-size: 11px;
                font-weight: bold;
                color: #38bdf8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                top: 2px;
                color: #38bdf8;
            }
            QLabel {
                color: #94a3b8;
                font-size: 11px;
            }
        """)

    def _input_style(self) -> str:
        return """
            QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #38bdf8;
            }
        """

    def _ps_section_header_style(self) -> str:
        return """
            QPushButton {
                background-color: transparent;
                color: #e0e0e0;
                font-size: 11px;
                font-weight: bold;
                text-align: left;
                border: none;
                padding: 4px 0px;
            }
            QPushButton:hover {
                color: #38bdf8;
            }
        """

    def _ps_input_style(self) -> str:
        return """
            QSpinBox, QDoubleSpinBox, QLineEdit {
                background-color: #1e1e1e;
                color: #f0f0f0;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 11px;
                min-height: 20px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {
                border-color: #007acc;
                background-color: #242424;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 10px;
                background-color: #2b2b2b;
            }
        """

    def _ps_link_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #242424;
                color: #888888;
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                font-size: 11px;
                max-width: 22px;
                max-height: 20px;
            }
            QPushButton:checked {
                background-color: #007acc;
                color: #ffffff;
                border-color: #007acc;
            }
            QPushButton:hover {
                border-color: #555555;
            }
        """

    def _create_sep_line(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Plain)
        line.setStyleSheet("background-color: #383838; max-height: 1px; border: none; margin: 4px 0px;")
        return line

    def _get_canvas_base_size(self):
        parent_w = self.parent()
        while parent_w:
            if hasattr(parent_w, "player_view") and hasattr(parent_w.player_view, "canvas"):
                c = parent_w.player_view.canvas
                vw = getattr(c, "video_w", 0) or 1920
                vh = getattr(c, "video_h", 0) or 1080
                return (vw, vh)
            parent_w = parent_w.parent()
        return (1920, 1080)

    def _toggle_ps_section(self, btn: QPushButton, container: QWidget, title: str):
        is_vis = container.isVisible()
        container.setVisible(not is_vis)
        btn.setText(f"{'›' if is_vis else '⌵'}  {title}")

    def _build_studio_shape_group(self) -> QGroupBox:
        """
        Creates a modern, responsive Shape & Line Design Properties Group matching
        the studio aesthetic (Timestamps & Transform & Shape Properties):
        - Shape / Line Type dropdown (Line, Arrow, Double Arrow, Rect, Rounded, Circle, Triangle, Star, Heart, Badge)
        - Fill Color picker + No Fill / Transparent toggle
        - Stroke / Line Color picker
        - Line / Border Thickness slider & spinbox (0 - 100px)
        - Stroke Style (Solid, Dashed, Dotted, None)
        - Arrowhead Size (8 - 50px, automatically shown for lines/arrows)
        - Corner Radius (0 - 100px, automatically shown for rectangles)
        - Neon Glow / Shadow toggle + glow color picker
        """
        gbox = QGroupBox("🔷 Shape & Line Style (ម៉ូតរាង និងបន្ទាត់)")
        self._style_groupbox(gbox)
        layout = QVBoxLayout(gbox)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(6)

        # 1. Type Selector
        row_type = QHBoxLayout()
        row_type.addWidget(QLabel("Shape / Line Type:"))
        self.combo_shape_type = QComboBox()
        self.combo_shape_type.addItem("➖ Straight Line (បន្ទាត់ត្រង់)", "line")
        self.combo_shape_type.addItem("➡️ Arrow (បន្ទាត់ព្រួញ)", "arrow")
        self.combo_shape_type.addItem("↔️ Double Arrow (ព្រួញសងខាង)", "double_arrow")
        self.combo_shape_type.addItem("🟦 Sharp Rectangle (ចតុកោណកែង)", "rect")
        self.combo_shape_type.addItem("🔲 Rounded Rectangle (ចតុកោណគែមមូល)", "rounded_rect")
        self.combo_shape_type.addItem("⚪ Circle / Ellipse (រង្វង់មូល)", "circle")
        self.combo_shape_type.addItem("🔺 Triangle (ត្រីកោណ)", "triangle")
        self.combo_shape_type.addItem("⭐ 5-Point Star (ផ្កាយ)", "star")
        self.combo_shape_type.addItem("❤️ Heart (បេះដូង)", "heart")
        self.combo_shape_type.addItem("🏷️ Capsule Badge (ផ្លាកសញ្ញា)", "badge")
        self.combo_shape_type.setStyleSheet(self._input_style())
        self.combo_shape_type.currentIndexChanged.connect(self._on_studio_shape_changed)
        row_type.addWidget(self.combo_shape_type, 1)
        layout.addLayout(row_type)

        # 2. Colors Row (Fill & Stroke)
        row_colors = QHBoxLayout()
        row_colors.addWidget(QLabel("Fill (ពណ៌ផ្ទៃ):"))
        self.btn_shape_fill = QPushButton(" Color")
        self.btn_shape_fill.setStyleSheet("background-color: #0ea5e9; color: #ffffff; border: 1px solid #38bdf8; border-radius: 4px; padding: 4px 8px; font-weight: bold;")
        self.btn_shape_fill.clicked.connect(self._pick_shape_fill_color)
        row_colors.addWidget(self.btn_shape_fill, 1)

        self.chk_shape_no_fill = QCheckBox("No Fill")
        self.chk_shape_no_fill.setToolTip("Transparent Fill (គ្មានពណ៌ផ្ទៃ)")
        self.chk_shape_no_fill.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.chk_shape_no_fill.toggled.connect(self._on_studio_shape_changed)
        row_colors.addWidget(self.chk_shape_no_fill)

        row_colors.addWidget(QLabel("Stroke (បន្ទាត់):"))
        self.btn_shape_stroke = QPushButton(" Color")
        self.btn_shape_stroke.setStyleSheet("background-color: #38bdf8; color: #000000; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px; font-weight: bold;")
        self.btn_shape_stroke.clicked.connect(self._pick_shape_stroke_color)
        row_colors.addWidget(self.btn_shape_stroke, 1)
        layout.addLayout(row_colors)

        # 3. Line / Stroke Thickness Slider & SpinBox
        row_thick = QHBoxLayout()
        row_thick.addWidget(QLabel("Line Thickness (កម្រាស់):"))
        self.spin_shape_stroke_w = QSpinBox()
        self.spin_shape_stroke_w.setRange(0, 100)
        self.spin_shape_stroke_w.setValue(4)
        self.spin_shape_stroke_w.setSuffix(" px")
        self.spin_shape_stroke_w.setStyleSheet(self._input_style())
        self.spin_shape_stroke_w.valueChanged.connect(self._on_studio_shape_changed)
        row_thick.addWidget(self.spin_shape_stroke_w)
        layout.addLayout(row_thick)

        self.slider_shape_stroke_w = QSlider(Qt.Orientation.Horizontal)
        self.slider_shape_stroke_w.setRange(0, 60)
        self.slider_shape_stroke_w.setValue(4)
        self.slider_shape_stroke_w.valueChanged.connect(lambda v: self.spin_shape_stroke_w.setValue(v))
        self.spin_shape_stroke_w.valueChanged.connect(lambda v: self.slider_shape_stroke_w.setValue(min(60, v)))
        layout.addWidget(self.slider_shape_stroke_w)

        # 4. Stroke Style Dropdown (Solid, Dashed, Dotted, None)
        row_s_style = QHBoxLayout()
        row_s_style.addWidget(QLabel("Stroke Style (ម៉ូតបន្ទាត់):"))
        self.combo_shape_stroke_style = QComboBox()
        self.combo_shape_stroke_style.addItem("────── Solid Line (បន្ទាត់ជាប់)", "solid")
        self.combo_shape_stroke_style.addItem("- - - - Dashed Line (បន្ទាត់ដាច់ៗ)", "dashed")
        self.combo_shape_stroke_style.addItem("· · · · Dotted Line (បន្ទាត់ចុចៗ)", "dotted")
        self.combo_shape_stroke_style.addItem("──/── None (គ្មានបន្ទាត់)", "none")
        self.combo_shape_stroke_style.setStyleSheet(self._input_style())
        self.combo_shape_stroke_style.currentIndexChanged.connect(self._on_studio_shape_changed)
        row_s_style.addWidget(self.combo_shape_stroke_style, 1)
        layout.addLayout(row_s_style)

        # 5. Context-Adaptive Controls: Corner Radius & Arrow Size
        self.row_adaptive = QHBoxLayout()
        self.lbl_shape_radius = QLabel("Corner Radius (គែមមូល):")
        self.row_adaptive.addWidget(self.lbl_shape_radius)
        self.spin_shape_corner_radius = QSpinBox()
        self.spin_shape_corner_radius.setRange(0, 100)
        self.spin_shape_corner_radius.setValue(0)
        self.spin_shape_corner_radius.setSuffix(" px")
        self.spin_shape_corner_radius.setStyleSheet(self._input_style())
        self.spin_shape_corner_radius.valueChanged.connect(self._on_studio_shape_changed)
        self.row_adaptive.addWidget(self.spin_shape_corner_radius, 1)

        self.lbl_shape_arrow = QLabel("Arrow Size (ទំហំក្បាលព្រួញ):")
        self.row_adaptive.addWidget(self.lbl_shape_arrow)
        self.spin_shape_arrow_size = QSpinBox()
        self.spin_shape_arrow_size.setRange(6, 60)
        self.spin_shape_arrow_size.setValue(16)
        self.spin_shape_arrow_size.setSuffix(" px")
        self.spin_shape_arrow_size.setStyleSheet(self._input_style())
        self.spin_shape_arrow_size.valueChanged.connect(self._on_studio_shape_changed)
        self.row_adaptive.addWidget(self.spin_shape_arrow_size, 1)
        layout.addLayout(self.row_adaptive)

        # 6. Neon Glow / Outer Shadow
        row_glow = QHBoxLayout()
        self.chk_shape_glow = QCheckBox("✨ Neon Glow (ពន្លឺជះ)")
        self.chk_shape_glow.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        self.chk_shape_glow.toggled.connect(self._on_studio_shape_changed)
        row_glow.addWidget(self.chk_shape_glow)

        self.btn_shape_glow_color = QPushButton(" Glow Color")
        self.btn_shape_glow_color.setStyleSheet("background-color: #38bdf8; color: #000000; border-radius: 4px; padding: 3px 6px; font-weight: bold; font-size: 10px;")
        self.btn_shape_glow_color.clicked.connect(self._pick_shape_glow_color)
        row_glow.addWidget(self.btn_shape_glow_color)
        layout.addLayout(row_glow)

        return gbox

    def _on_studio_shape_changed(self):
        if self._updating_ui or not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        stype = self.combo_shape_type.currentData() or "rect"
        item.shape_type = stype

        is_line = stype in ("line", "arrow", "double_arrow")
        self.lbl_shape_arrow.setVisible(is_line)
        self.spin_shape_arrow_size.setVisible(is_line)
        is_rect = stype in ("rect", "rounded_rect")
        self.lbl_shape_radius.setVisible(is_rect)
        self.spin_shape_corner_radius.setVisible(is_rect)

        # Fill color
        if self.chk_shape_no_fill.isChecked() or is_line:
            item.fill_color = QColor(0, 0, 0, 0)
        else:
            if getattr(item, "fill_color", None) is None or item.fill_color.alpha() == 0:
                item.fill_color = QColor("#0ea5e9")

        # Stroke properties
        item.border_width = self.spin_shape_stroke_w.value()
        item.stroke_style = self.combo_shape_stroke_style.currentData() or "solid"
        item.corner_radius = float(self.spin_shape_corner_radius.value())
        item.arrowhead_size = float(self.spin_shape_arrow_size.value())

        # Glow
        item.glow_enabled = self.chk_shape_glow.isChecked()

        self.item_modified.emit(item)

    def _pick_shape_fill_color(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "fill_color", QColor("#0ea5e9"))
        if not cur_col or cur_col.alpha() == 0:
            cur_col = QColor("#0ea5e9")
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ផ្ទៃ Fill")
        if col.isValid():
            self.target_object.fill_color = col
            self.chk_shape_no_fill.setChecked(False)
            self.btn_shape_fill.setStyleSheet(f"background-color: {col.name()}; color: {'#000000' if col.lightness() > 128 else '#ffffff'}; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px; font-weight: bold;")
            self.item_modified.emit(self.target_object)

    def _pick_shape_stroke_color(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "border_color", QColor("#38bdf8"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌បន្ទាត់ Line / Stroke")
        if col.isValid():
            self.target_object.border_color = col
            if getattr(self.target_object, "border_width", 0) == 0:
                self.target_object.border_width = 3
                self.spin_shape_stroke_w.setValue(3)
            self.btn_shape_stroke.setStyleSheet(f"background-color: {col.name()}; color: {'#000000' if col.lightness() > 128 else '#ffffff'}; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px; font-weight: bold;")
            self.item_modified.emit(self.target_object)

    def _pick_shape_glow_color(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "glow_color", QColor("#38bdf8"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ Neon Glow")
        if col.isValid():
            self.target_object.glow_color = col
            self.chk_shape_glow.setChecked(True)
            self.btn_shape_glow_color.setStyleSheet(f"background-color: {col.name()}; color: {'#000000' if col.lightness() > 128 else '#ffffff'}; border-radius: 4px; padding: 3px 6px; font-weight: bold; font-size: 10px;")
            self.item_modified.emit(self.target_object)

    def _populate_studio_shape_fields(self, item):
        stype = getattr(item, "shape_type", "rect")
        idx = self.combo_shape_type.findData(stype)
        if idx >= 0:
            self.combo_shape_type.setCurrentIndex(idx)

        # Fill color
        fc = getattr(item, "fill_color", QColor("#0ea5e9"))
        if fc and fc.alpha() > 0 and stype not in ("line", "arrow", "double_arrow"):
            self.chk_shape_no_fill.setChecked(False)
            self.btn_shape_fill.setStyleSheet(f"background-color: {fc.name()}; color: {'#000000' if fc.lightness() > 128 else '#ffffff'}; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px; font-weight: bold;")
        else:
            self.chk_shape_no_fill.setChecked(True)
            self.btn_shape_fill.setStyleSheet("background-color: #1e293b; color: #64748b; border: 1px dashed #475569; border-radius: 4px; padding: 4px 8px;")

        # Stroke color
        sc = getattr(item, "border_color", QColor("#38bdf8"))
        self.btn_shape_stroke.setStyleSheet(f"background-color: {sc.name()}; color: {'#000000' if sc.lightness() > 128 else '#ffffff'}; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px; font-weight: bold;")

        # Stroke width
        sw = int(getattr(item, "border_width", 4 if stype in ("line", "arrow", "double_arrow") else 0))
        self.spin_shape_stroke_w.setValue(sw)
        self.slider_shape_stroke_w.setValue(min(60, sw))

        # Stroke style
        s_style = getattr(item, "stroke_style", "solid")
        s_idx = self.combo_shape_stroke_style.findData(s_style)
        if s_idx >= 0:
            self.combo_shape_stroke_style.setCurrentIndex(s_idx)

        # Adaptive visibility
        is_line = stype in ("line", "arrow", "double_arrow")
        self.lbl_shape_arrow.setVisible(is_line)
        self.spin_shape_arrow_size.setVisible(is_line)
        self.spin_shape_arrow_size.setValue(int(getattr(item, "arrowhead_size", 16)))

        is_rect = stype in ("rect", "rounded_rect")
        self.lbl_shape_radius.setVisible(is_rect)
        self.spin_shape_corner_radius.setVisible(is_rect)
        self.spin_shape_corner_radius.setValue(int(getattr(item, "corner_radius", 0)))

        # Glow
        self.chk_shape_glow.setChecked(bool(getattr(item, "glow_enabled", False)))
        gc = getattr(item, "glow_color", QColor("#38bdf8"))
        self.btn_shape_glow_color.setStyleSheet(f"background-color: {gc.name()}; color: {'#000000' if gc.lightness() > 128 else '#ffffff'}; border-radius: 4px; padding: 3px 6px; font-weight: bold; font-size: 10px;")

    def _create_photoshop_shape_panel(self) -> QFrame:
        """
        Creates an authentic Adobe Photoshop CC Properties Inspector Panel for Shape Layers:
        - Layer Header (Icon ⬠, Name, Shape Layer badge, Menu ···)
        - Transform (W, Link, H, X, Y in px)
        - Align and Distribute (6 alignment icon buttons + 2 distribute buttons)
        - Appearance (Fill Swatch, Stroke Swatch, Stroke Width px, Stroke Style dropdown)
        - Shape (W, H px, Master Corner radius px, Link, 4 Individual Corners TL/TR/BL/BR)
        - Quick Actions (Rasterize Shape, Convert to Smart Object pill buttons)
        """
        panel = QFrame()
        panel.setObjectName("group_ps_shape")
        panel.setStyleSheet("""
            QFrame#group_ps_shape {
                background-color: #2b2b2b;
                border: 1px solid #1e1e1e;
                border-radius: 4px;
                padding: 6px;
            }
            QLabel {
                color: #9c9c9c;
                font-size: 10px;
                font-weight: 500;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # 1. Identity Header: ⬠ Rectangle 1 | Shape Layer | ···
        row_id = QHBoxLayout()
        row_id.setContentsMargins(0, 0, 0, 2)
        row_id.setSpacing(6)

        lbl_sh_icon = QLabel("⬠")
        lbl_sh_icon.setStyleSheet("color: #b0b0b0; font-size: 14px; font-weight: bold;")
        row_id.addWidget(lbl_sh_icon)

        self.ps_edit_name = QLineEdit("Rectangle 1")
        self.ps_edit_name.setStyleSheet("""
            QLineEdit {
                background: transparent;
                color: #f5f5f5;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid transparent;
                border-radius: 2px;
                padding: 1px 4px;
            }
            QLineEdit:hover, QLineEdit:focus {
                background: #1e1e1e;
                border-color: #007acc;
            }
        """)
        self.ps_edit_name.editingFinished.connect(self._on_ps_name_changed)
        row_id.addWidget(self.ps_edit_name, 1)

        self.ps_lbl_layer_type = QLabel("Shape Layer")
        self.ps_lbl_layer_type.setStyleSheet("color: #7a7a7a; font-size: 10px;")
        row_id.addWidget(self.ps_lbl_layer_type)

        btn_ps_menu = QPushButton("···")
        btn_ps_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ps_menu.setFixedWidth(20)
        btn_ps_menu.setStyleSheet("background: transparent; color: #888888; font-size: 13px; font-weight: bold; border: none;")
        btn_ps_menu.clicked.connect(self._show_ps_header_menu)
        row_id.addWidget(btn_ps_menu)
        layout.addLayout(row_id)
        layout.addWidget(self._create_sep_line())

        # 2. Section: Transform
        self.ps_btn_sec_transform = QPushButton("⌵  Transform")
        self.ps_btn_sec_transform.setStyleSheet(self._ps_section_header_style())
        layout.addWidget(self.ps_btn_sec_transform)

        self.ps_cont_transform = QWidget()
        l_trans = QVBoxLayout(self.ps_cont_transform)
        l_trans.setContentsMargins(4, 2, 4, 4)
        l_trans.setSpacing(4)

        # W & H
        row_wh = QHBoxLayout()
        row_wh.setSpacing(4)
        lbl_w = QLabel("W")
        lbl_w.setFixedWidth(14)
        row_wh.addWidget(lbl_w)
        self.ps_spin_w = QSpinBox()
        self.ps_spin_w.setRange(1, 99999)
        self.ps_spin_w.setValue(779)
        self.ps_spin_w.setSuffix(" px")
        self.ps_spin_w.setStyleSheet(self._ps_input_style())
        self.ps_spin_w.valueChanged.connect(self._on_ps_wh_changed)
        row_wh.addWidget(self.ps_spin_w, 1)

        self.ps_btn_link_wh = QPushButton("🔗")
        self.ps_btn_link_wh.setCheckable(True)
        self.ps_btn_link_wh.setChecked(True)
        self.ps_btn_link_wh.setToolTip("Maintain Aspect Ratio (ចាក់សោរសមាមាត្រ)")
        self.ps_btn_link_wh.setStyleSheet(self._ps_link_btn_style())
        row_wh.addWidget(self.ps_btn_link_wh)

        lbl_h = QLabel("H")
        lbl_h.setFixedWidth(14)
        row_wh.addWidget(lbl_h)
        self.ps_spin_h = QSpinBox()
        self.ps_spin_h.setRange(1, 99999)
        self.ps_spin_h.setValue(388)
        self.ps_spin_h.setSuffix(" px")
        self.ps_spin_h.setStyleSheet(self._ps_input_style())
        self.ps_spin_h.valueChanged.connect(self._on_ps_wh_changed)
        row_wh.addWidget(self.ps_spin_h, 1)
        l_trans.addLayout(row_wh)

        # X & Y
        row_xy = QHBoxLayout()
        row_xy.setSpacing(4)
        lbl_x = QLabel("X")
        lbl_x.setFixedWidth(14)
        row_xy.addWidget(lbl_x)
        self.ps_spin_x = QSpinBox()
        self.ps_spin_x.setRange(-99999, 99999)
        self.ps_spin_x.setValue(215)
        self.ps_spin_x.setSuffix(" px")
        self.ps_spin_x.setStyleSheet(self._ps_input_style())
        self.ps_spin_x.valueChanged.connect(self._on_ps_xy_changed)
        row_xy.addWidget(self.ps_spin_x, 1)

        sp = QLabel("")
        sp.setFixedWidth(22)
        row_xy.addWidget(sp)

        lbl_y = QLabel("Y")
        lbl_y.setFixedWidth(14)
        row_xy.addWidget(lbl_y)
        self.ps_spin_y = QSpinBox()
        self.ps_spin_y.setRange(-99999, 99999)
        self.ps_spin_y.setValue(387)
        self.ps_spin_y.setSuffix(" px")
        self.ps_spin_y.setStyleSheet(self._ps_input_style())
        self.ps_spin_y.valueChanged.connect(self._on_ps_xy_changed)
        row_xy.addWidget(self.ps_spin_y, 1)
        l_trans.addLayout(row_xy)

        layout.addWidget(self.ps_cont_transform)
        self.ps_btn_sec_transform.clicked.connect(lambda: self._toggle_ps_section(self.ps_btn_sec_transform, self.ps_cont_transform, "Transform"))
        layout.addWidget(self._create_sep_line())

        # 3. Section: Align and Distribute
        self.ps_btn_sec_align = QPushButton("⌵  Align and Distribute")
        self.ps_btn_sec_align.setStyleSheet(self._ps_section_header_style())
        layout.addWidget(self.ps_btn_sec_align)

        self.ps_cont_align = QWidget()
        l_align = QVBoxLayout(self.ps_cont_align)
        l_align.setContentsMargins(4, 2, 4, 4)
        l_align.setSpacing(4)

        row_al_icons = QHBoxLayout()
        row_al_icons.setSpacing(3)
        align_defs = [
            ("|▊", "left", "Align Left Edges"),
            ("⇥⇤", "hcenter", "Align Horizontal Centers"),
            ("▊|", "right", "Align Right Edges"),
            ("▔", "top", "Align Top Edges"),
            ("-|-", "vcenter", "Align Vertical Centers"),
            (" ", "bottom", "Align Bottom Edges")
        ]
        btn_al_style = """
            QPushButton {
                background-color: #333333;
                color: #d0d0d0;
                border: 1px solid #444444;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
                height: 22px;
            }
            QPushButton:hover {
                background-color: #444444;
                color: #ffffff;
                border-color: #666666;
            }
        """
        for symbol, mode, tip in align_defs:
            b = QPushButton(symbol)
            b.setToolTip(tip)
            b.setStyleSheet(btn_al_style)
            b.clicked.connect(lambda chk=False, m=mode: self._on_ps_align(m))
            row_al_icons.addWidget(b, 1)
        l_align.addLayout(row_al_icons)

        row_dist = QHBoxLayout()
        row_dist.setSpacing(6)
        btn_dist_style = """
            QPushButton {
                background-color: #333333;
                color: #c0c0c0;
                border: 1px solid #444444;
                border-radius: 3px;
                font-size: 10px;
                padding: 3px 6px;
                height: 22px;
            }
            QPushButton:hover {
                background-color: #444444;
                color: #ffffff;
            }
        """
        btn_dist_h = QPushButton("Horizontally")
        btn_dist_h.setStyleSheet(btn_dist_style)
        btn_dist_h.clicked.connect(lambda: self._on_ps_distribute("h"))
        row_dist.addWidget(btn_dist_h, 1)

        btn_dist_v = QPushButton("Vertically")
        btn_dist_v.setStyleSheet(btn_dist_style)
        btn_dist_v.clicked.connect(lambda: self._on_ps_distribute("v"))
        row_dist.addWidget(btn_dist_v, 1)
        l_align.addLayout(row_dist)

        layout.addWidget(self.ps_cont_align)
        self.ps_btn_sec_align.clicked.connect(lambda: self._toggle_ps_section(self.ps_btn_sec_align, self.ps_cont_align, "Align and Distribute"))
        layout.addWidget(self._create_sep_line())

        # 4. Section: Appearance
        self.ps_btn_sec_appear = QPushButton("⌵  Appearance")
        self.ps_btn_sec_appear.setStyleSheet(self._ps_section_header_style())
        layout.addWidget(self.ps_btn_sec_appear)

        self.ps_cont_appear = QWidget()
        l_appear = QVBoxLayout(self.ps_cont_appear)
        l_appear.setContentsMargins(4, 2, 4, 4)
        l_appear.setSpacing(4)

        row_app1 = QHBoxLayout()
        row_app1.setSpacing(6)

        lbl_fill = QLabel("Fill")
        row_app1.addWidget(lbl_fill)
        self.ps_btn_fill = QPushButton()
        self.ps_btn_fill.setFixedSize(24, 20)
        self.ps_btn_fill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ps_btn_fill.setStyleSheet("background-color: #000000; border: 1px solid #555555; border-radius: 2px;")
        self.ps_btn_fill.clicked.connect(self._on_ps_fill_clicked)
        row_app1.addWidget(self.ps_btn_fill)

        lbl_stroke = QLabel("Stroke")
        row_app1.addWidget(lbl_stroke)
        self.ps_btn_stroke = QPushButton("／")
        self.ps_btn_stroke.setFixedSize(24, 20)
        self.ps_btn_stroke.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ps_btn_stroke.setStyleSheet("background-color: #1e1e1e; border: 1px solid #555555; color: #ef4444; font-weight: bold; font-size: 13px; border-radius: 2px;")
        self.ps_btn_stroke.clicked.connect(self._on_ps_stroke_clicked)
        row_app1.addWidget(self.ps_btn_stroke)

        self.ps_spin_stroke_w = QSpinBox()
        self.ps_spin_stroke_w.setRange(0, 100)
        self.ps_spin_stroke_w.setValue(0)
        self.ps_spin_stroke_w.setSuffix(" px")
        self.ps_spin_stroke_w.setStyleSheet(self._ps_input_style())
        self.ps_spin_stroke_w.valueChanged.connect(self._on_ps_stroke_style_changed)
        row_app1.addWidget(self.ps_spin_stroke_w, 1)
        l_appear.addLayout(row_app1)

        row_app2 = QHBoxLayout()
        self.ps_combo_stroke_style = QComboBox()
        self.ps_combo_stroke_style.addItem("No Color   ──/──", "none")
        self.ps_combo_stroke_style.addItem("Solid Line  ───────", "solid")
        self.ps_combo_stroke_style.addItem("Dashed Line - - - -", "dashed")
        self.ps_combo_stroke_style.addItem("Dotted Line · · · ·", "dotted")
        self.ps_combo_stroke_style.setStyleSheet(self._ps_input_style())
        self.ps_combo_stroke_style.currentIndexChanged.connect(self._on_ps_stroke_style_changed)
        row_app2.addWidget(self.ps_combo_stroke_style, 1)
        l_appear.addLayout(row_app2)

        layout.addWidget(self.ps_cont_appear)
        self.ps_btn_sec_appear.clicked.connect(lambda: self._toggle_ps_section(self.ps_btn_sec_appear, self.ps_cont_appear, "Appearance"))
        layout.addWidget(self._create_sep_line())

        # 5. Section: Shape
        self.ps_btn_sec_shape = QPushButton("⌵  Shape")
        self.ps_btn_sec_shape.setStyleSheet(self._ps_section_header_style())
        layout.addWidget(self.ps_btn_sec_shape)

        self.ps_cont_shape = QWidget()
        l_shape = QVBoxLayout(self.ps_cont_shape)
        l_shape.setContentsMargins(4, 2, 4, 4)
        l_shape.setSpacing(4)

        # W & H in Shape
        row_sh_wh = QHBoxLayout()
        row_sh_wh.setSpacing(4)
        lbl_sh_w = QLabel("W")
        lbl_sh_w.setFixedWidth(14)
        row_sh_wh.addWidget(lbl_sh_w)
        self.ps_shape_w = QSpinBox()
        self.ps_shape_w.setRange(1, 99999)
        self.ps_shape_w.setValue(779)
        self.ps_shape_w.setSuffix(" px")
        self.ps_shape_w.setStyleSheet(self._ps_input_style())
        self.ps_shape_w.valueChanged.connect(self._on_ps_shape_wh_changed)
        row_sh_wh.addWidget(self.ps_shape_w, 1)

        lbl_sh_h = QLabel("H")
        lbl_sh_h.setFixedWidth(14)
        row_sh_wh.addWidget(lbl_sh_h)
        self.ps_shape_h = QSpinBox()
        self.ps_shape_h.setRange(1, 99999)
        self.ps_shape_h.setValue(388)
        self.ps_shape_h.setSuffix(" px")
        self.ps_shape_h.setStyleSheet(self._ps_input_style())
        self.ps_shape_h.valueChanged.connect(self._on_ps_shape_wh_changed)
        row_sh_wh.addWidget(self.ps_shape_h, 1)
        l_shape.addLayout(row_sh_wh)

        # Corner radius Master + Link
        row_c_all = QHBoxLayout()
        row_c_all.setSpacing(4)
        lbl_c_rad = QLabel("Corner radius")
        row_c_all.addWidget(lbl_c_rad)
        self.ps_spin_radius_all = QSpinBox()
        self.ps_spin_radius_all.setRange(0, 500)
        self.ps_spin_radius_all.setValue(0)
        self.ps_spin_radius_all.setSuffix(" px")
        self.ps_spin_radius_all.setStyleSheet(self._ps_input_style())
        self.ps_spin_radius_all.valueChanged.connect(self._on_ps_radius_all_changed)
        row_c_all.addWidget(self.ps_spin_radius_all, 1)

        self.ps_btn_link_corners = QPushButton("🔗")
        self.ps_btn_link_corners.setCheckable(True)
        self.ps_btn_link_corners.setChecked(True)
        self.ps_btn_link_corners.setToolTip("Link all 4 corner radii (ភ្ជាប់ជ្រុងទាំង ៤ ស្មើគ្នា)")
        self.ps_btn_link_corners.setStyleSheet(self._ps_link_btn_style())
        row_c_all.addWidget(self.ps_btn_link_corners)
        l_shape.addLayout(row_c_all)

        # Individual Corners: Top Left & Top Right
        row_c_top = QHBoxLayout()
        row_c_top.setSpacing(4)
        lbl_tl = QLabel("Top Left")
        lbl_tl.setFixedWidth(52)
        row_c_top.addWidget(lbl_tl)
        self.ps_spin_radius_tl = QSpinBox()
        self.ps_spin_radius_tl.setRange(0, 500)
        self.ps_spin_radius_tl.setValue(0)
        self.ps_spin_radius_tl.setSuffix(" px")
        self.ps_spin_radius_tl.setStyleSheet(self._ps_input_style())
        self.ps_spin_radius_tl.valueChanged.connect(self._on_ps_corners_changed)
        row_c_top.addWidget(self.ps_spin_radius_tl, 1)

        lbl_tr = QLabel("Top Right")
        lbl_tr.setFixedWidth(52)
        row_c_top.addWidget(lbl_tr)
        self.ps_spin_radius_tr = QSpinBox()
        self.ps_spin_radius_tr.setRange(0, 500)
        self.ps_spin_radius_tr.setValue(0)
        self.ps_spin_radius_tr.setSuffix(" px")
        self.ps_spin_radius_tr.setStyleSheet(self._ps_input_style())
        self.ps_spin_radius_tr.valueChanged.connect(self._on_ps_corners_changed)
        row_c_top.addWidget(self.ps_spin_radius_tr, 1)
        l_shape.addLayout(row_c_top)

        # Individual Corners: Bottom Left & Bottom Right
        row_c_bot = QHBoxLayout()
        row_c_bot.setSpacing(4)
        lbl_bl = QLabel("Bottom Left")
        lbl_bl.setFixedWidth(52)
        row_c_bot.addWidget(lbl_bl)
        self.ps_spin_radius_bl = QSpinBox()
        self.ps_spin_radius_bl.setRange(0, 500)
        self.ps_spin_radius_bl.setValue(0)
        self.ps_spin_radius_bl.setSuffix(" px")
        self.ps_spin_radius_bl.setStyleSheet(self._ps_input_style())
        self.ps_spin_radius_bl.valueChanged.connect(self._on_ps_corners_changed)
        row_c_bot.addWidget(self.ps_spin_radius_bl, 1)

        lbl_br = QLabel("Bottom Right")
        lbl_br.setFixedWidth(52)
        row_c_bot.addWidget(lbl_br)
        self.ps_spin_radius_br = QSpinBox()
        self.ps_spin_radius_br.setRange(0, 500)
        self.ps_spin_radius_br.setValue(0)
        self.ps_spin_radius_br.setSuffix(" px")
        self.ps_spin_radius_br.setStyleSheet(self._ps_input_style())
        self.ps_spin_radius_br.valueChanged.connect(self._on_ps_corners_changed)
        row_c_bot.addWidget(self.ps_spin_radius_br, 1)
        l_shape.addLayout(row_c_bot)

        layout.addWidget(self.ps_cont_shape)
        self.ps_btn_sec_shape.clicked.connect(lambda: self._toggle_ps_section(self.ps_btn_sec_shape, self.ps_cont_shape, "Shape"))
        layout.addWidget(self._create_sep_line())

        # 6. Section: Quick Actions
        self.ps_btn_sec_actions = QPushButton("⌵  Quick Actions")
        self.ps_btn_sec_actions.setStyleSheet(self._ps_section_header_style())
        layout.addWidget(self.ps_btn_sec_actions)

        self.ps_cont_actions = QWidget()
        l_act = QHBoxLayout(self.ps_cont_actions)
        l_act.setContentsMargins(4, 4, 4, 6)
        l_act.setSpacing(8)

        btn_pill_style = """
            QPushButton {
                background-color: #383838;
                color: #e0e0e0;
                border: 1px solid #5a5a5a;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #484848;
                border-color: #777777;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        self.ps_btn_rasterize = QPushButton("Rasterize Shape")
        self.ps_btn_rasterize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ps_btn_rasterize.setStyleSheet(btn_pill_style)
        self.ps_btn_rasterize.clicked.connect(self._on_ps_rasterize)
        l_act.addWidget(self.ps_btn_rasterize, 1)

        self.ps_btn_smart_obj = QPushButton("Convert to Smart Object")
        self.ps_btn_smart_obj.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ps_btn_smart_obj.setStyleSheet(btn_pill_style)
        self.ps_btn_smart_obj.clicked.connect(self._on_ps_smart_object)
        l_act.addWidget(self.ps_btn_smart_obj, 1)

        layout.addWidget(self.ps_cont_actions)
        self.ps_btn_sec_actions.clicked.connect(lambda: self._toggle_ps_section(self.ps_btn_sec_actions, self.ps_cont_actions, "Quick Actions"))

        return panel

    def _show_ps_header_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2b2b2b;
                color: #f0f0f0;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 4px 18px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #007acc;
                color: #ffffff;
            }
        """)
        menu.addAction("Center Horizontally & Vertically", lambda: (self._on_ps_align("hcenter"), self._on_ps_align("vcenter")))
        menu.addSeparator()
        menu.addAction("Rasterize Layer", self._on_ps_rasterize)
        menu.addAction("Convert to Smart Object", self._on_ps_smart_object)
        menu.exec(QCursor.pos())

    def _on_ps_name_changed(self):
        if self._updating_ui or not self.target_object:
            return
        self.target_object.name = self.ps_edit_name.text()
        self.item_modified.emit(self.target_object)

    def _populate_ps_shape_fields(self, item):
        base_w, base_h = self._get_canvas_base_size()
        pw = max(1, int(item.w * base_w))
        ph = max(1, int(item.h * base_h))
        px = int(item.x * base_w)
        py = int(item.y * base_h)

        self.ps_edit_name.setText(getattr(item, "name", "Rectangle 1"))
        self.ps_spin_w.blockSignals(True)
        self.ps_spin_w.setValue(pw)
        self.ps_spin_w.blockSignals(False)

        self.ps_spin_h.blockSignals(True)
        self.ps_spin_h.setValue(ph)
        self.ps_spin_h.blockSignals(False)

        self.ps_spin_x.blockSignals(True)
        self.ps_spin_x.setValue(px)
        self.ps_spin_x.blockSignals(False)

        self.ps_spin_y.blockSignals(True)
        self.ps_spin_y.setValue(py)
        self.ps_spin_y.blockSignals(False)

        self.ps_shape_w.blockSignals(True)
        self.ps_shape_w.setValue(pw)
        self.ps_shape_w.blockSignals(False)

        self.ps_shape_h.blockSignals(True)
        self.ps_shape_h.setValue(ph)
        self.ps_shape_h.blockSignals(False)

        # Fill
        fill_c = getattr(item, "fill_color", QColor("#000000"))
        self.ps_btn_fill.setStyleSheet(f"background-color: {fill_c.name()}; border: 1px solid #555555; border-radius: 2px;")

        # Stroke
        b_width = int(getattr(item, "border_width", 0))
        self.ps_spin_stroke_w.blockSignals(True)
        self.ps_spin_stroke_w.setValue(b_width)
        self.ps_spin_stroke_w.blockSignals(False)

        s_style = getattr(item, "stroke_style", "none" if b_width == 0 else "solid")
        idx = self.ps_combo_stroke_style.findData(s_style)
        if idx >= 0:
            self.ps_combo_stroke_style.blockSignals(True)
            self.ps_combo_stroke_style.setCurrentIndex(idx)
            self.ps_combo_stroke_style.blockSignals(False)

        bord_c = getattr(item, "border_color", QColor("#e11d48"))
        if b_width == 0 or s_style == "none":
            self.ps_btn_stroke.setText("／")
            self.ps_btn_stroke.setStyleSheet("background-color: #1e1e1e; border: 1px solid #555555; color: #ef4444; font-weight: bold; font-size: 13px; border-radius: 2px;")
        else:
            self.ps_btn_stroke.setText("")
            self.ps_btn_stroke.setStyleSheet(f"background-color: {bord_c.name()}; border: 1px solid #ffffff; border-radius: 2px;")

        # Corners
        c_all = int(getattr(item, "corner_radius", 0))
        self.ps_spin_radius_all.blockSignals(True)
        self.ps_spin_radius_all.setValue(c_all)
        self.ps_spin_radius_all.blockSignals(False)

        self.ps_spin_radius_tl.blockSignals(True)
        self.ps_spin_radius_tl.setValue(int(getattr(item, "radius_tl", c_all)))
        self.ps_spin_radius_tl.blockSignals(False)

        self.ps_spin_radius_tr.blockSignals(True)
        self.ps_spin_radius_tr.setValue(int(getattr(item, "radius_tr", c_all)))
        self.ps_spin_radius_tr.blockSignals(False)

        self.ps_spin_radius_bl.blockSignals(True)
        self.ps_spin_radius_bl.setValue(int(getattr(item, "radius_bl", c_all)))
        self.ps_spin_radius_bl.blockSignals(False)

        self.ps_spin_radius_br.blockSignals(True)
        self.ps_spin_radius_br.setValue(int(getattr(item, "radius_br", c_all)))
        self.ps_spin_radius_br.blockSignals(False)

    def _on_ps_wh_changed(self):
        if self._updating_ui or not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        base_w, base_h = self._get_canvas_base_size()
        new_w = self.ps_spin_w.value()
        new_h = self.ps_spin_h.value()

        if self.ps_btn_link_wh.isChecked() and getattr(item, "w", 0) > 0 and getattr(item, "h", 0) > 0:
            cur_pw = int(item.w * base_w)
            cur_ph = int(item.h * base_h)
            if new_w != cur_pw and cur_pw > 0:
                ratio = new_w / float(cur_pw)
                new_h = max(1, int(cur_ph * ratio))
                self.ps_spin_h.blockSignals(True)
                self.ps_spin_h.setValue(new_h)
                self.ps_spin_h.blockSignals(False)
            elif new_h != cur_ph and cur_ph > 0:
                ratio = new_h / float(cur_ph)
                new_w = max(1, int(cur_pw * ratio))
                self.ps_spin_w.blockSignals(True)
                self.ps_spin_w.setValue(new_w)
                self.ps_spin_w.blockSignals(False)

        item.w = max(0.01, new_w / float(base_w))
        item.h = max(0.01, new_h / float(base_h))

        self.ps_shape_w.blockSignals(True)
        self.ps_shape_w.setValue(new_w)
        self.ps_shape_w.blockSignals(False)

        self.ps_shape_h.blockSignals(True)
        self.ps_shape_h.setValue(new_h)
        self.ps_shape_h.blockSignals(False)

        self.item_modified.emit(item)

    def _on_ps_shape_wh_changed(self):
        if self._updating_ui or not self.target_object:
            return
        self.ps_spin_w.blockSignals(True)
        self.ps_spin_w.setValue(self.ps_shape_w.value())
        self.ps_spin_w.blockSignals(False)

        self.ps_spin_h.blockSignals(True)
        self.ps_spin_h.setValue(self.ps_shape_h.value())
        self.ps_spin_h.blockSignals(False)
        self._on_ps_wh_changed()

    def _on_ps_xy_changed(self):
        if self._updating_ui or not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        base_w, base_h = self._get_canvas_base_size()
        item.x = self.ps_spin_x.value() / float(base_w)
        item.y = self.ps_spin_y.value() / float(base_h)
        self.item_modified.emit(item)

    def _on_ps_align(self, mode: str):
        if not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        if mode == "left":
            item.x = item.w / 2.0
        elif mode == "hcenter":
            item.x = 0.5
        elif mode == "right":
            item.x = 1.0 - (item.w / 2.0)
        elif mode == "top":
            item.y = item.h / 2.0
        elif mode == "vcenter":
            item.y = 0.5
        elif mode == "bottom":
            item.y = 1.0 - (item.h / 2.0)

        base_w, base_h = self._get_canvas_base_size()
        self._updating_ui = True
        self.ps_spin_x.setValue(int(item.x * base_w))
        self.ps_spin_y.setValue(int(item.y * base_h))
        self._updating_ui = False
        self.item_modified.emit(item)

    def _on_ps_distribute(self, orientation: str):
        if not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        if orientation == "h":
            item.x = 0.5
        else:
            item.y = 0.5
        base_w, base_h = self._get_canvas_base_size()
        self._updating_ui = True
        self.ps_spin_x.setValue(int(item.x * base_w))
        self.ps_spin_y.setValue(int(item.y * base_h))
        self._updating_ui = False
        self.item_modified.emit(item)

    def _on_ps_fill_clicked(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "fill_color", QColor("#000000"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ផ្ទៃ Fill")
        if col.isValid():
            self.target_object.fill_color = col
            self.ps_btn_fill.setStyleSheet(f"background-color: {col.name()}; border: 1px solid #555555; border-radius: 2px;")
            self.item_modified.emit(self.target_object)

    def _on_ps_stroke_clicked(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "border_color", QColor("#e11d48"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌បន្ទាត់ Stroke")
        if col.isValid():
            self.target_object.border_color = col
            if getattr(self.target_object, "border_width", 0) == 0:
                self.target_object.border_width = 2
                self.ps_spin_stroke_w.setValue(2)
            if getattr(self.target_object, "stroke_style", "none") == "none":
                self.target_object.stroke_style = "solid"
                self.ps_combo_stroke_style.setCurrentIndex(1)
            self.ps_btn_stroke.setText("")
            self.ps_btn_stroke.setStyleSheet(f"background-color: {col.name()}; border: 1px solid #ffffff; border-radius: 2px;")
            self.item_modified.emit(self.target_object)

    def _on_ps_stroke_style_changed(self):
        if self._updating_ui or not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        b_w = self.ps_spin_stroke_w.value()
        s_style = self.ps_combo_stroke_style.currentData() or "none"
        item.border_width = b_w
        item.stroke_style = s_style

        bord_c = getattr(item, "border_color", QColor("#e11d48"))
        if b_w == 0 or s_style == "none":
            self.ps_btn_stroke.setText("／")
            self.ps_btn_stroke.setStyleSheet("background-color: #1e1e1e; border: 1px solid #555555; color: #ef4444; font-weight: bold; font-size: 13px; border-radius: 2px;")
        else:
            self.ps_btn_stroke.setText("")
            self.ps_btn_stroke.setStyleSheet(f"background-color: {bord_c.name()}; border: 1px solid #ffffff; border-radius: 2px;")

        self.item_modified.emit(item)

    def _on_ps_radius_all_changed(self):
        if self._updating_ui or not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        val = self.ps_spin_radius_all.value()
        item.corner_radius = float(val)

        if self.ps_btn_link_corners.isChecked():
            item.radius_tl = float(val)
            item.radius_tr = float(val)
            item.radius_bl = float(val)
            item.radius_br = float(val)

            self.ps_spin_radius_tl.blockSignals(True)
            self.ps_spin_radius_tl.setValue(val)
            self.ps_spin_radius_tl.blockSignals(False)

            self.ps_spin_radius_tr.blockSignals(True)
            self.ps_spin_radius_tr.setValue(val)
            self.ps_spin_radius_tr.blockSignals(False)

            self.ps_spin_radius_bl.blockSignals(True)
            self.ps_spin_radius_bl.setValue(val)
            self.ps_spin_radius_bl.blockSignals(False)

            self.ps_spin_radius_br.blockSignals(True)
            self.ps_spin_radius_br.setValue(val)
            self.ps_spin_radius_br.blockSignals(False)

        self.item_modified.emit(item)

    def _on_ps_corners_changed(self):
        if self._updating_ui or not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        item.radius_tl = float(self.ps_spin_radius_tl.value())
        item.radius_tr = float(self.ps_spin_radius_tr.value())
        item.radius_bl = float(self.ps_spin_radius_bl.value())
        item.radius_br = float(self.ps_spin_radius_br.value())
        self.item_modified.emit(item)

    def _on_ps_rasterize(self):
        if not self.target_object or self.target_type != "shape":
            return
        item = self.target_object
        base_w, base_h = self._get_canvas_base_size()
        pw = max(16, int(item.w * base_w))
        ph = max(16, int(item.h * base_h))

        pixmap = QPixmap(pw, ph)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, pw, ph)

        if getattr(item, "fill_color", None) and item.fill_color.alpha() > 0:
            painter.setBrush(QBrush(item.fill_color))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        b_w = getattr(item, "border_width", 0)
        s_st = getattr(item, "stroke_style", "solid")
        if b_w > 0 and s_st != "none" and getattr(item, "border_color", None):
            pen = QPen(item.border_color, b_w)
            if s_st == "dashed":
                pen.setStyle(Qt.PenStyle.DashLine)
            elif s_st == "dotted":
                pen.setStyle(Qt.PenStyle.DotLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(pen)
        else:
            painter.setPen(Qt.PenStyle.NoPen)

        r_tl = getattr(item, "radius_tl", getattr(item, "corner_radius", 0.0))
        r_tr = getattr(item, "radius_tr", getattr(item, "corner_radius", 0.0))
        r_bl = getattr(item, "radius_bl", getattr(item, "corner_radius", 0.0))
        r_br = getattr(item, "radius_br", getattr(item, "corner_radius", 0.0))

        if max(r_tl, r_tr, r_bl, r_br) > 0.5 and hasattr(item, "_draw_rounded_rect_complex"):
            item._draw_rounded_rect_complex(painter, rect, r_tl, r_tr, r_bl, r_br)
        else:
            painter.drawRect(rect)
        painter.end()

        item.item_type = "image"
        item._raw_image = pixmap.toImage()
        item._processed_pixmap = pixmap
        item.name = f"{item.name} (Rasterized)"
        self.item_modified.emit(item)
        self.set_target_canvas_item(item)

    def _on_ps_smart_object(self):
        if not self.target_object:
            return
        item = self.target_object
        item.is_smart_object = True
        item.name = f"{item.name} (Smart Object)"
        self.ps_lbl_layer_type.setText("Smart Object Layer")
        self.ps_lbl_layer_type.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
        self.item_modified.emit(item)

    # ------------------ TARGET DISPATCH & UI POPULATION ------------------
    def set_target_canvas_item(self, item):
        """Sets an active visual overlay CanvasItem from video player canvas or timeline."""
        if item is None:
            self._show_empty_state()
            return

        self._updating_ui = True
        self.target_object = item
        self.target_type = getattr(item, "item_type", "image")
        self.target_sub_idx = -1
        itype = self.target_type

        self.empty_card.hide()
        is_shape = (itype == "shape")
        self.group_timing.setVisible(True)
        self.group_transform.setVisible(True)

        # Update header badge
        if is_shape:
            stype = getattr(item, "shape_type", "rect")
            is_ln = stype in ("line", "arrow", "double_arrow")
            self.lbl_icon.setText("➡️" if is_ln else "🔷")
            self.lbl_title.setText(item.name or ("Vector Line" if is_ln else "Vector Shape"))
            self.lbl_badge.setText("Line FX" if is_ln else "Shape FX")
            self.lbl_badge.setStyleSheet("background-color: #8b5cf6; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")
        elif itype in ("blur_box", "blur", "mosaic", "glass", "blackout"):
            self.lbl_icon.setText("🌫️")
            self.lbl_title.setText("Frosted Glass / Blur Box")
            self.lbl_badge.setText("Blur FX")
            self.lbl_badge.setStyleSheet("background-color: #0284c7; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")
        elif itype in ("text", "subtitle"):
            self.lbl_icon.setText("💬" if itype == "subtitle" else "📝")
            self.lbl_title.setText("CC Subtitle Dialogue" if itype == "subtitle" else "Typography Text")
            self.lbl_badge.setText("CC Subtitle" if itype == "subtitle" else "Text")
            self.lbl_badge.setStyleSheet("background-color: #f59e0b; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")
        elif itype == "video":
            self.lbl_icon.setText("🎬")
            self.lbl_title.setText("Video PiP Clip")
            self.lbl_badge.setText("Video")
            self.lbl_badge.setStyleSheet("background-color: #10b981; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")
        else:
            self.lbl_icon.setText("🖼️")
            self.lbl_title.setText("Image / Sticker Overlay")
            self.lbl_badge.setText("Image")
            self.lbl_badge.setStyleSheet("background-color: #3b82f6; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")

        # Populate Timing & Transform for ALL visual canvas items
        st = float(getattr(item, "start_time", 0.0))
        et = float(getattr(item, "end_time", 0.0))
        if et <= st:
            et = st + 5.0
        self.spin_start_time.setValue(st)
        self.spin_end_time.setValue(et)
        self._update_time_label(st, et)

        self.spin_pos_x.setValue(round(item.x * 100.0, 1))
        self.spin_pos_y.setValue(round(item.y * 100.0, 1))
        self.spin_size_w.setValue(round(item.w * 100.0, 1))
        self.spin_size_h.setValue(round(item.h * 100.0, 1))
        self.spin_rotation.setValue(round(item.rotation, 1))
        self.spin_opacity.setValue(int(item.opacity * 100.0))

        # Show/Hide specific groups
        self.group_blur.setVisible(itype in ("blur_box", "blur", "mosaic", "glass", "blackout"))
        self.group_text.setVisible(itype in ("text", "subtitle"))
        self.group_image_fx.setVisible(itype in ("image", "sticker", "video"))
        self.group_shape.setVisible(is_shape)
        self.group_ps_shape.hide()
        self.group_audio.hide()

        # Populate Type-Specific values
        if is_shape:
            self._populate_studio_shape_fields(item)
        elif itype in ("blur_box", "blur", "mosaic", "glass", "blackout"):
            bmode = getattr(item, "blur_mode", "blur")
            idx = self.combo_blur_mode.findData(bmode)
            if idx >= 0:
                self.combo_blur_mode.setCurrentIndex(idx)
            self.slider_blur_strength.setValue(int(getattr(item, "blur_strength", 25)))
            self.spin_blur_radius.setValue(int(getattr(item, "corner_radius", 0)))
            t_col = getattr(item, "glass_tint_color", QColor(15, 23, 42))
            self.btn_tint_color.setStyleSheet(f"background-color: {t_col.name()}; color: #ffffff; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px;")

        elif itype in ("text", "subtitle"):
            self.txt_editor.setPlainText(getattr(item, "text", ""))
            f_idx = self.combo_font.findText(getattr(item, "font_family", "Kantumruy Pro"))
            if f_idx >= 0:
                self.combo_font.setCurrentIndex(f_idx)
            self.spin_font_size.setValue(max(10, int(getattr(item, "font_size", 28) or 28)))
            self.chk_bold.setChecked(bool(getattr(item, "is_bold", True)))
            self.chk_italic.setChecked(bool(getattr(item, "is_italic", False)))
            f_col = getattr(item, "font_color", QColor("#ffffff"))
            self.btn_text_color.setStyleSheet(f"background-color: {f_col.name()}; color: {'#000000' if f_col.lightness() > 128 else '#ffffff'}; border-radius: 4px; padding: 4px 8px;")
            cur_anim = getattr(item, "animation", "karaoke" if itype == "subtitle" else "none") or "none"
            a_idx = self.combo_anim.findData(cur_anim)
            if a_idx >= 0:
                self.combo_anim.setCurrentIndex(a_idx)
            hi_c = getattr(item, "highlight_color", QColor("#00E5FF"))
            self.btn_hi_color.setStyleSheet(f"background-color: {hi_c.name()}; color: #000000; font-weight: bold; border-radius: 4px; padding: 4px 6px;")

            # Marquee settings
            m_dir = getattr(item, "marquee_direction", "right_to_left") or "right_to_left"
            md_idx = self.combo_marquee_dir.findData(m_dir)
            if md_idx >= 0:
                self.combo_marquee_dir.setCurrentIndex(md_idx)
            self.chk_marquee_loop.setChecked(bool(getattr(item, "marquee_loop", True)))
            self.spin_marquee_speed.setValue(float(getattr(item, "marquee_speed", 1.0) or 1.0))
            self.group_marquee_opts.setVisible(cur_anim in ("marquee", "news_ticker", "ticker"))

        elif itype in ("image", "sticker"):
            self.slider_sharpness.setValue(int(getattr(item, "sharpness", 0)))
            self.slider_img_blur.setValue(int(getattr(item, "blur", 0)))

        self._updating_ui = False

        self._updating_ui = False

    def set_target_subtitle(self, sub_data: dict, sub_idx: int):
        """Sets an active Subtitle / Audio Clip from the Subtitles table or timeline track."""
        if not sub_data:
            self._show_empty_state()
            return

        self._updating_ui = True
        self.target_object = sub_data
        self.target_sub_idx = sub_idx
        self.target_type = "subtitle"

        self.empty_card.hide()
        self.group_timing.show()
        self.group_transform.hide()
        self.group_blur.hide()
        self.group_image_fx.hide()
        self.group_ps_shape.hide()
        self.group_text.show()
        self.group_audio.show()
        self.lbl_voice_profile.show()
        self.combo_voice_profile.show()
        if hasattr(self, "row_rates"):
            self.spin_audio_rate.show()
            self.spin_audio_pitch.show()

        # Update Header
        self.lbl_icon.setText("💬")
        self.lbl_title.setText(f"Subtitle Dialogue Line #{sub_idx + 1}")
        self.lbl_badge.setText("Subtitle & Audio")
        self.lbl_badge.setStyleSheet("background-color: #10b981; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")

        # Populate Timing
        st = float(sub_data.get("start", 0.0))
        et = float(sub_data.get("end", 0.0))
        self.spin_start_time.setValue(st)
        self.spin_end_time.setValue(et)
        self._update_time_label(st, et)

        # Populate Text
        km_txt = sub_data.get("khmer_text") or sub_data.get("orig_text") or sub_data.get("text", "")
        self.txt_editor.setPlainText(km_txt)

        # Populate Audio Profile
        v_speaker = sub_data.get("speaker") or sub_data.get("voice") or "Piseth - ធម្មជាតិ (Natural Male)"
        v_idx = self.combo_voice_profile.findText(v_speaker)
        if v_idx >= 0:
            self.combo_voice_profile.setCurrentIndex(v_idx)

        # Rate & Pitch
        self.spin_audio_rate.setValue(int(sub_data.get("rate_adj", 0) or 0))
        self.spin_audio_pitch.setValue(int(sub_data.get("pitch_adj", 0) or 0))

        # Volume & Speed
        raw_vol = sub_data.get("volume", 1.0)
        try:
            vol_val = int(round(float(raw_vol) * 100)) if not isinstance(raw_vol, str) else int(raw_vol.replace("%", "").replace("+", ""))
        except Exception:
            vol_val = 100
        self.spin_audio_vol.setValue(vol_val)
        self.spin_audio_speed.setValue(float(sub_data.get("speed", 1.0) or 1.0))

        # CapCut Voice Effect
        cur_fx = sub_data.get("voice_effect", "none") or "none"
        fx_idx = self.combo_voice_effect.findData(cur_fx)
        if fx_idx >= 0:
            self.combo_voice_effect.setCurrentIndex(fx_idx)
        else:
            self.combo_voice_effect.setCurrentIndex(0)

        self._updating_ui = False

    def set_target_audio(self, audio_data: dict):
        """Sets an active Soundtrack MP3 or Audio Clip from the Timeline track."""
        if not audio_data:
            self._show_empty_state()
            return

        self._updating_ui = True
        self.target_object = audio_data
        self.target_type = "audio"
        self.target_sub_idx = audio_data.get("sub_idx", -1)

        self.empty_card.hide()
        self.group_timing.show()
        self.group_transform.hide()
        self.group_blur.hide()
        self.group_image_fx.hide()
        self.group_ps_shape.hide()
        self.group_text.hide()
        self.group_audio.show()

        # Update Header
        name_str = audio_data.get("name", "Audio Track")
        is_track = audio_data.get("is_track", False)
        self.lbl_icon.setText("🎵" if is_track else "🎙️")
        self.lbl_title.setText(f"{name_str[:26]}")
        self.lbl_badge.setText("Soundtrack" if is_track else "Voice Dub")
        badge_bg = "#065f46" if is_track else "#0c4a6e"
        self.lbl_badge.setStyleSheet(f"background-color: {badge_bg}; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")

        # Populate Timing
        st = float(audio_data.get("start", 0.0))
        et = float(audio_data.get("end", 0.0))
        self.spin_start_time.setValue(st)
        self.spin_end_time.setValue(et)
        self._update_time_label(st, et)

        # Hide speaker profile for raw music tracks, show for dialogue
        self.lbl_voice_profile.setVisible(not is_track)
        self.combo_voice_profile.setVisible(not is_track)

        # Volume & Speed
        raw_vol = audio_data.get("volume", 1.0)
        try:
            vol_val = int(round(float(raw_vol) * 100))
        except Exception:
            vol_val = 100
        self.spin_audio_vol.setValue(vol_val)
        self.spin_audio_speed.setValue(float(audio_data.get("speed", 1.0) or 1.0))

        # CapCut Voice Effect
        raw_dict = audio_data.get("raw") if isinstance(audio_data.get("raw"), dict) else audio_data
        cur_fx = raw_dict.get("voice_effect", "none") or "none"
        fx_idx = self.combo_voice_effect.findData(cur_fx)
        if fx_idx >= 0:
            self.combo_voice_effect.setCurrentIndex(fx_idx)
        else:
            self.combo_voice_effect.setCurrentIndex(0)

        self._updating_ui = False

    def _show_empty_state(self):
        """Displays friendly prompt when no object is selected."""
        self.target_object = None
        self.target_type = None
        self.target_sub_idx = -1
        self.lbl_icon.setText("🛠️")
        self.lbl_title.setText("Properties Inspector (ផ្ទាំងកែវត្ថុ)")
        self.lbl_badge.setText("None")
        self.lbl_badge.setStyleSheet("background-color: #334155; color: #94a3b8; padding: 2px 8px; border-radius: 4px;")
        self.empty_card.show()
        self.group_timing.hide()
        self.group_transform.hide()
        self.group_blur.hide()
        self.group_text.hide()
        self.group_image_fx.hide()
        self.group_shape.hide()
        self.group_ps_shape.hide()
        self.group_audio.hide()
        self.group_cc_stats.hide()

    def _build_cc_analytics_group(self) -> QGroupBox:
        """
        Creates a high-end Subtitle Analytics & CC Properties Inspector Group:
        - 4 KPI Tiles: Total Lines, Speech Time, Words & Chars, Reading Speed CPS
        - Format & Type Details: Format, Source Language, Translated Type, Coverage
        - CCDialogueDensityChart: Interactive 10-bucket speech heatmap + length breakdown
        - Quick CC Maintenance: Auto-Fix Overlaps, Jump to 1st Line, Export SRT
        """
        grp = QGroupBox("📊 Subtitle Analytics & CC Properties (ស្ថិតិអក្សររត់)")
        self._style_groupbox(grp)
        layout = QVBoxLayout(grp)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(8)

        # 1. 2x2 Metric Cards Grid
        grid_metrics = QGridLayout()
        grid_metrics.setSpacing(6)

        def make_tile(title_txt, default_val, default_sub, color_hex):
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background-color: #141822;
                    border: 1px solid #232b3b;
                    border-left: 3px solid {color_hex};
                    border-radius: 6px;
                    padding: 4px 6px;
                }}
            """)
            flay = QVBoxLayout(frame)
            flay.setContentsMargins(4, 4, 4, 4)
            flay.setSpacing(1)

            lbl_t = QLabel(title_txt)
            lbl_t.setStyleSheet("color: #94a3b8; font-size: 10px; font-weight: bold;")
            lbl_v = QLabel(default_val)
            lbl_v.setStyleSheet(f"color: {color_hex}; font-size: 13px; font-weight: 800;")
            lbl_s = QLabel(default_sub)
            lbl_s.setStyleSheet("color: #64748b; font-size: 9px;")

            flay.addWidget(lbl_t)
            flay.addWidget(lbl_v)
            flay.addWidget(lbl_s)
            return frame, lbl_v, lbl_s

        f1, self.lbl_cc_lines_val, self.lbl_cc_lines_sub = make_tile("🔢 Total Lines", "0", "បន្ទាត់អក្សររត់", "#38bdf8")
        f2, self.lbl_cc_dur_val, self.lbl_cc_dur_sub = make_tile("⏱️ Speech Time", "00:00", "ម៉ោងសន្ទនាសរុប", "#10b981")
        f3, self.lbl_cc_words_val, self.lbl_cc_words_sub = make_tile("🔤 Words & Chars", "0 w / 0 c", "ចំនួនពាក្យ & អក្សរ", "#c084fc")
        f4, self.lbl_cc_cps_val, self.lbl_cc_cps_sub = make_tile("⚡ Reading Speed", "0.0 CPS", "ល្បឿនអានជាមធ្យម", "#f59e0b")

        grid_metrics.addWidget(f1, 0, 0)
        grid_metrics.addWidget(f2, 0, 1)
        grid_metrics.addWidget(f3, 1, 0)
        grid_metrics.addWidget(f4, 1, 1)
        layout.addLayout(grid_metrics)

        # 2. Type & Format Info Box
        frame_type = QFrame()
        frame_type.setStyleSheet("""
            QFrame {
                background-color: #121620;
                border: 1px solid #1e2638;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        ft_layout = QVBoxLayout(frame_type)
        ft_layout.setContentsMargins(6, 6, 6, 6)
        ft_layout.setSpacing(4)

        lbl_spec_title = QLabel("📝 Subtitle Format & Language Type:")
        lbl_spec_title.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px;")
        ft_layout.addWidget(lbl_spec_title)

        def make_row(lbl_left, lbl_right, color_val="#cbd5e1"):
            row = QHBoxLayout()
            l = QLabel(lbl_left)
            l.setStyleSheet("color: #64748b; font-size: 10px;")
            r = QLabel(lbl_right)
            r.setStyleSheet(f"color: {color_val}; font-size: 10px; font-weight: bold;")
            row.addWidget(l)
            row.addStretch()
            row.addWidget(r)
            return row, r

        r1, self.lbl_cc_fmt_val = make_row("• File Specification:", "SRT (SubRip) • UTF-8", "#38bdf8")
        r2, self.lbl_cc_src_lang = make_row("• Source Dialogue:", "Foreign / Original", "#e2e8f0")
        r3, self.lbl_cc_tgt_lang = make_row("• Target Language:", "Khmer (ភាសាខ្មែរ)", "#10b981")
        r4, self.lbl_cc_coverage_val = make_row("• Speech Coverage:", "0.0% of video", "#c084fc")

        ft_layout.addLayout(r1)
        ft_layout.addLayout(r2)
        ft_layout.addLayout(r3)
        ft_layout.addLayout(r4)
        layout.addWidget(frame_type)

        # 3. CCDialogueDensityChart (Visual chart widget!)
        self.chart_cc_density = CCDialogueDensityChart()
        layout.addWidget(self.chart_cc_density)

        # 4. Status & Action Buttons
        self.lbl_cc_overlap_status = QLabel("✅ គ្មានបន្ទាត់ជាន់គ្នាទេ")
        self.lbl_cc_overlap_status.setStyleSheet("color: #10b981; font-size: 11px;")
        layout.addWidget(self.lbl_cc_overlap_status)

        row_acts = QHBoxLayout()
        row_acts.setSpacing(6)

        self.btn_fix_overlaps = QPushButton("⚡ Auto-Fix Overlaps")
        self.btn_fix_overlaps.setStyleSheet("background-color: #854d0e; color: #fef08a; font-weight: bold; border-radius: 4px; padding: 5px; font-size: 10px;")
        self.btn_fix_overlaps.clicked.connect(self.request_fix_overlaps.emit)
        self.btn_fix_overlaps.setVisible(False)
        row_acts.addWidget(self.btn_fix_overlaps)

        btn_jump_first = QPushButton("🔍 Jump to 1st Line")
        btn_jump_first.setStyleSheet("background-color: #1e2532; color: #38bdf8; border: 1px solid #334155; border-radius: 4px; padding: 5px; font-size: 10px;")
        btn_jump_first.clicked.connect(self.request_jump_first_sub.emit)
        row_acts.addWidget(btn_jump_first)

        btn_exp_srt = QPushButton("💾 Export SRT")
        btn_exp_srt.setStyleSheet("background-color: #0c4a6e; color: #ffffff; font-weight: bold; border-radius: 4px; padding: 5px; font-size: 10px;")
        btn_exp_srt.clicked.connect(self.request_export_srt.emit)
        row_acts.addWidget(btn_exp_srt)

        layout.addLayout(row_acts)
        return grp

    def set_target_cc_analytics(self, subtitles: list, video_duration: float = 0.0):
        """Displays rich Closed Caption & Subtitle Analytics in the Properties Inspector."""
        self._updating_ui = True
        self.target_object = subtitles
        self.target_type = "cc_analytics"
        self.target_sub_idx = -1

        self.empty_card.hide()
        self.group_timing.hide()
        self.group_transform.hide()
        self.group_blur.hide()
        self.group_text.hide()
        self.group_image_fx.hide()
        self.group_shape.hide()
        self.group_ps_shape.hide()
        self.group_audio.hide()
        self.group_cc_stats.show()

        # Update Header Inspector Bar
        self.lbl_icon.setText("💬")
        self.lbl_title.setText("CC & Subtitle Analytics")
        self.lbl_badge.setText("CC Pro")
        self.lbl_badge.setStyleSheet("background-color: #0284c7; color: #ffffff; padding: 2px 8px; border-radius: 4px; font-weight: bold;")

        # Metrics computation
        subs = subtitles or []
        total_lines = len(subs)

        # Total duration
        total_speech_sec = sum(max(0.0, float(s.get("end", 0.0)) - float(s.get("start", 0.0))) for s in subs)
        max_end_time = max([float(s.get("end", 0.0)) for s in subs] + [float(video_duration or 0.0), 1.0])
        coverage_pct = (total_speech_sec / max_end_time * 100.0) if max_end_time > 0 else 0.0

        # Word & Char counts
        total_chars = 0
        total_words = 0
        short_count = 0
        med_count = 0
        long_count = 0
        overlaps_count = 0

        buckets = [0] * 10
        prev_end = -1.0

        for s in subs:
            st = float(s.get("start", 0.0))
            et = float(s.get("end", 0.0))
            txt = s.get("khmer_text") or s.get("orig_text") or s.get("text") or ""
            chars = len(txt)
            words = len(txt.split()) if txt else 0
            total_chars += chars
            total_words += words

            if chars < 20:
                short_count += 1
            elif chars <= 45:
                med_count += 1
            else:
                long_count += 1

            if prev_end > st + 0.05:
                overlaps_count += 1
            prev_end = max(prev_end, et)

            # Density bucket (0-9)
            mid = (st + et) / 2.0
            b_idx = min(9, max(0, int((mid / max_end_time) * 10))) if max_end_time > 0 else 0
            buckets[b_idx] += 1

        cps = (total_chars / total_speech_sec) if total_speech_sec > 0 else 0.0

        # Update KPI Labels
        self.lbl_cc_lines_val.setText(str(total_lines))
        self.lbl_cc_lines_sub.setText(f"{total_lines} Cues ក្នុងវីដេអូ")
        dur_mins = int(total_speech_sec // 60)
        dur_secs = int(total_speech_sec % 60)
        self.lbl_cc_dur_val.setText(f"{dur_mins:02d}:{dur_secs:02d}")
        self.lbl_cc_dur_sub.setText(f"សរុប {total_speech_sec:.1f}s")
        self.lbl_cc_words_val.setText(f"{total_words:,} w / {total_chars:,} c")
        self.lbl_cc_words_sub.setText(f"~{round(total_words / max(1, total_lines), 1)} ពាក្យ/បន្ទាត់")
        self.lbl_cc_cps_val.setText(f"{cps:.1f} CPS")
        self.lbl_cc_cps_sub.setText("តួអក្សរក្នុង ១ វិនាទី")

        # Speed badge color
        if cps <= 16.0:
            self.lbl_cc_cps_val.setStyleSheet("color: #10b981; font-weight: bold; font-size: 13px;")
        elif cps <= 22.0:
            self.lbl_cc_cps_val.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 13px;")
        else:
            self.lbl_cc_cps_val.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 13px;")

        # Update Overlap notice
        if overlaps_count > 0:
            self.lbl_cc_overlap_status.setText(f"⚠️ {overlaps_count} បន្ទាត់ជាន់គ្នា (Overlaps)")
            self.lbl_cc_overlap_status.setStyleSheet("color: #f59e0b; font-size: 11px; font-weight: bold;")
            self.btn_fix_overlaps.setVisible(True)
        else:
            self.lbl_cc_overlap_status.setText("✅ គ្មានបន្ទាត់ជាន់គ្នាទេ (No Overlaps)")
            self.lbl_cc_overlap_status.setStyleSheet("color: #10b981; font-size: 11px;")
            self.btn_fix_overlaps.setVisible(False)

        # Update Coverage & Format info
        self.lbl_cc_coverage_val.setText(f"{coverage_pct:.1f}% នៃវីដេអូ ({total_lines} Cues)")

        # Update Chart
        short_pct = (short_count / total_lines * 100.0) if total_lines > 0 else 0.0
        med_pct = (med_count / total_lines * 100.0) if total_lines > 0 else 0.0
        long_pct = (long_count / total_lines * 100.0) if total_lines > 0 else 0.0
        self.chart_cc_density.set_data(buckets, short_pct, med_pct, long_pct, total_lines)

        self._updating_ui = False

    def _update_time_label(self, st: float, et: float):
        dur = max(0.0, et - st)
        self.lbl_time_formatted.setText(f"{format_timestamp(st).split(',')[0]} ➔ {format_timestamp(et).split(',')[0]}")
        self.lbl_dur_badge.setText(f"Dur: {dur:.2f}s")

    # ------------------ CHANGE LISTENERS ------------------
    def _on_timing_changed(self):
        if self._updating_ui or not self.target_object:
            return
        st = self.spin_start_time.value()
        et = self.spin_end_time.value()
        if et < st:
            et = st + 0.1
            self.spin_end_time.blockSignals(True)
            self.spin_end_time.setValue(et)
            self.spin_end_time.blockSignals(False)

        self._update_time_label(st, et)

        if self.target_type == "subtitle" and isinstance(self.target_object, dict):
            self.target_object["start"] = st
            self.target_object["end"] = et
            if self.target_sub_idx >= 0:
                self.sub_time_modified.emit(self.target_sub_idx, st, et)
        else:
            setattr(self.target_object, "start_time", st)
            setattr(self.target_object, "end_time", et)
            self.item_modified.emit(self.target_object)

    def _on_transform_changed(self):
        if self._updating_ui or not self.target_object:
            return
        item = self.target_object
        item.x = self.spin_pos_x.value() / 100.0
        item.y = self.spin_pos_y.value() / 100.0
        item.w = self.spin_size_w.value() / 100.0
        item.h = self.spin_size_h.value() / 100.0
        item.rotation = self.spin_rotation.value()
        item.opacity = self.spin_opacity.value() / 100.0
        self.item_modified.emit(item)

    def _on_blur_props_changed(self):
        if self._updating_ui or not self.target_object:
            return
        item = self.target_object
        item.blur_mode = self.combo_blur_mode.currentData()
        item.blur_strength = self.slider_blur_strength.value()
        item.corner_radius = self.spin_blur_radius.value()
        self.item_modified.emit(item)

    def _pick_tint_color(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "glass_tint_color", QColor(15, 23, 42))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ Glass Tint")
        if col.isValid():
            self.target_object.glass_tint_color = col
            self.btn_tint_color.setStyleSheet(f"background-color: {col.name()}; color: #ffffff; border: 1px solid #ffffff; border-radius: 4px; padding: 4px 8px;")
            self.item_modified.emit(self.target_object)

    def _on_text_content_changed(self):
        if self._updating_ui or not self.target_object:
            return
        new_text = self.txt_editor.toPlainText().strip()
        if self.target_type == "subtitle" and isinstance(self.target_object, dict):
            self.target_object["khmer_text"] = new_text
            self.target_object["status"] = "edited"
            if self.target_sub_idx >= 0:
                self.sub_text_modified.emit(self.target_sub_idx, new_text)
        else:
            self.target_object.text = new_text
            self.item_modified.emit(self.target_object)

    def _on_text_props_changed(self):
        if self._updating_ui or not self.target_object:
            return
        item = self.target_object
        if hasattr(item, "font_family"):
            item.font_family = self.combo_font.currentText()
        if hasattr(item, "font_size"):
            item.font_size = self.spin_font_size.value()
        if hasattr(item, "is_bold"):
            item.is_bold = self.chk_bold.isChecked()
        if hasattr(item, "is_italic"):
            item.is_italic = self.chk_italic.isChecked()
        if hasattr(item, "animation"):
            item.animation = self.combo_anim.currentData() or "none"
            self.group_marquee_opts.setVisible(item.animation in ("marquee", "news_ticker", "ticker"))
        if hasattr(item, "marquee_direction"):
            item.marquee_direction = self.combo_marquee_dir.currentData() or "right_to_left"
        if hasattr(item, "marquee_loop"):
            item.marquee_loop = self.chk_marquee_loop.isChecked()
        if hasattr(item, "marquee_speed"):
            item.marquee_speed = self.spin_marquee_speed.value()
        self.item_modified.emit(item)

    def _pick_text_color(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "font_color", QColor("#ffffff"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ Font Text")
        if col.isValid():
            self.target_object.font_color = col
            self.btn_text_color.setStyleSheet(f"background-color: {col.name()}; color: {'#000000' if col.lightness() > 128 else '#ffffff'}; border-radius: 4px; padding: 4px 8px;")
            self.item_modified.emit(self.target_object)

    def _pick_highlight_color(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "highlight_color", QColor("#00E5FF"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ Karaoke Highlight")
        if col.isValid():
            self.target_object.highlight_color = col
            self.btn_hi_color.setStyleSheet(f"background-color: {col.name()}; color: #000000; font-weight: bold; border-radius: 4px; padding: 4px 6px;")
            self.item_modified.emit(self.target_object)

    def _open_color_presets(self):
        if self.canvas and hasattr(self.canvas, "open_color_presets_dialog"):
            self.canvas.open_color_presets_dialog()

    def _on_image_fx_changed(self):
        if self._updating_ui or not self.target_object:
            return
        item = self.target_object
        item.sharpness = self.slider_sharpness.value()
        item.blur = self.slider_img_blur.value()
        if hasattr(item, "update_effects"):
            item.update_effects()
        self.item_modified.emit(item)

    def _on_shape_props_changed(self):
        if self._updating_ui or not self.target_object:
            return
        item = self.target_object
        item.shape_type = self.combo_shape_type.currentData()
        item.border_width = self.spin_border_width.value()
        self.item_modified.emit(item)

    def _pick_shape_fill(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "fill_color", QColor("#0ea5e9"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌ផ្ទៃ Fill")
        if col.isValid():
            self.target_object.fill_color = col
            self.btn_shape_fill.setStyleSheet(f"background-color: {col.name()}; color: #ffffff; border-radius: 4px; padding: 4px 8px;")
            self.item_modified.emit(self.target_object)

    def _pick_shape_border(self):
        if not self.target_object:
            return
        cur_col = getattr(self.target_object, "border_color", QColor("#38bdf8"))
        col = QColorDialog.getColor(cur_col, self, "ជ្រើសរើសពណ៌បន្ទាត់ Border")
        if col.isValid():
            self.target_object.border_color = col
            self.btn_shape_border.setStyleSheet(f"background-color: {col.name()}; color: #000000; border-radius: 4px; padding: 4px 8px;")
            self.item_modified.emit(self.target_object)

    def _on_audio_props_changed(self):
        if self._updating_ui or not self.target_object:
            return
        fx_key = self.combo_voice_effect.currentData() or "none"
        vol_pct = self.spin_audio_vol.value()
        spd_val = self.spin_audio_speed.value()

        if self.target_type == "subtitle" and isinstance(self.target_object, dict):
            self.target_object["speaker"] = self.combo_voice_profile.currentText()
            self.target_object["rate_adj"] = self.spin_audio_rate.value()
            self.target_object["pitch_adj"] = self.spin_audio_pitch.value()
            self.target_object["volume"] = f"+{vol_pct-100}%" if vol_pct != 100 else "+0%"
            self.target_object["speed"] = spd_val
            self.target_object["voice_effect"] = fx_key
            self.item_modified.emit(self.target_object)
        elif self.target_type == "audio" and isinstance(self.target_object, dict):
            raw = self.target_object.get("raw") if isinstance(self.target_object.get("raw"), dict) else self.target_object
            self.target_object["volume"] = vol_pct / 100.0
            self.target_object["speed"] = spd_val
            self.target_object["voice_effect"] = fx_key
            if raw:
                raw["volume"] = vol_pct / 100.0
                raw["speed"] = spd_val
                raw["voice_effect"] = fx_key
            self.audio_modified.emit(self.target_object)

    def _on_open_capcut_dialog_from_panel(self):
        """Opens the full CapCut Voice Effects Studio Dialog from properties panel."""
        if not self.target_object:
            return
        from ui_v_PyQt6.components.timeline.capcut_voice_dialog import CapCutVoiceDialog
        dlg = CapCutVoiceDialog(self.target_object, parent=self.window() or self)
        if dlg.exec():
            cur_fx = self.target_object.get("voice_effect", "none")
            idx = self.combo_voice_effect.findData(cur_fx)
            if idx >= 0:
                self.combo_voice_effect.setCurrentIndex(idx)
            if hasattr(self, "lbl_fx_status"):
                self.lbl_fx_status.setText(f"✅ បានអនុវត្ត Effect: {cur_fx}")
                self.lbl_fx_status.show()
            self.voice_effect_applied.emit(self.target_object, cur_fx)
            self.audio_modified.emit(self.target_object)

    def _on_preview_voice_effect(self):
        """Previews the selected CapCut voice effect on current audio file."""
        if not self.target_object:
            return
        fx_key = self.combo_voice_effect.currentData() or "none"
        aud_path = None
        if self.target_type == "subtitle" and isinstance(self.target_object, dict):
            aud_path = self.target_object.get("orig_audio") or self.target_object.get("audio_file") or self.target_object.get("audio_path")
        elif self.target_type == "audio" and isinstance(self.target_object, dict):
            raw = self.target_object.get("raw") if isinstance(self.target_object.get("raw"), dict) else self.target_object
            aud_path = (
                raw.get("orig_path")
                or raw.get("path")
                or raw.get("orig_audio")
                or raw.get("audio_file")
                or raw.get("audio_path")
                or self.target_object.get("path")
            )

        if aud_path and os.path.exists(aud_path):
            self.btn_preview_fx.setText(" 🔊 កំពុងចាក់...")
            self.btn_preview_fx.setEnabled(False)
            if hasattr(self, "lbl_fx_status"):
                self.lbl_fx_status.setText(f"🔊 Previewing: {fx_key}...")
                self.lbl_fx_status.show()
            from ui_v_PyQt6.qt_compat import QTimer
            preview_voice_effect(aud_path, fx_key)
            QTimer.singleShot(1800, lambda: (self.btn_preview_fx.setText(" ▶️ ស្តាប់ (Preview)"), self.btn_preview_fx.setEnabled(True)))
        else:
            if hasattr(self, "lbl_fx_status"):
                self.lbl_fx_status.setText("⚠️ រកមិនឃើញ File សំឡេងដើមសម្រាប់ស្តាប់!")
                self.lbl_fx_status.show()

    def _on_apply_voice_effect(self):
        """Applies the selected CapCut voice effect directly to the audio file or batch."""
        if not self.target_object:
            return
        fx_key = self.combo_voice_effect.currentData() or "none"
        scope = self.combo_fx_scope.currentData() if hasattr(self, "combo_fx_scope") else "clip"

        if self.target_type == "subtitle" and isinstance(self.target_object, dict):
            orig_aud = self.target_object.get("orig_audio") or self.target_object.get("audio_file") or self.target_object.get("audio_path")
            if orig_aud and os.path.exists(orig_aud):
                if not self.target_object.get("orig_audio"):
                    self.target_object["orig_audio"] = orig_aud
                self.target_object["voice_effect"] = fx_key
                if fx_key != "none":
                    new_path = apply_voice_effect_to_file(self.target_object["orig_audio"], fx_key)
                    self.target_object["audio_file"] = new_path
                    self.target_object["audio_path"] = new_path
                else:
                    self.target_object["audio_file"] = self.target_object["orig_audio"]
                    self.target_object["audio_path"] = self.target_object["orig_audio"]
                if hasattr(self, "lbl_fx_status"):
                    self.lbl_fx_status.setText(f"✅ បានអនុវត្ត Effect: {fx_key}")
                    self.lbl_fx_status.show()
                self.voice_effect_applied.emit(self.target_object, fx_key)
                self.item_modified.emit(self.target_object)
        elif self.target_type == "audio" and isinstance(self.target_object, dict):
            raw = self.target_object.get("raw") if isinstance(self.target_object.get("raw"), dict) else self.target_object
            orig_aud = (
                raw.get("orig_path")
                or raw.get("orig_audio")
                or raw.get("path")
                or raw.get("audio_file")
                or raw.get("audio_path")
                or self.target_object.get("path")
            )
            if orig_aud and os.path.exists(orig_aud):
                is_trk = self.target_object.get("is_track", False)
                if not raw.get("orig_path") and not raw.get("orig_audio"):
                    if is_trk:
                        raw["orig_path"] = orig_aud
                    else:
                        raw["orig_audio"] = orig_aud
                raw["voice_effect"] = fx_key
                self.target_object["voice_effect"] = fx_key
                src_aud = raw.get("orig_path") or raw.get("orig_audio") or orig_aud
                if fx_key != "none":
                    new_path = apply_voice_effect_to_file(src_aud, fx_key)
                    if is_trk:
                        raw["path"] = new_path
                        self.target_object["path"] = new_path
                    else:
                        raw["audio_file"] = new_path
                        raw["audio_path"] = new_path
                        self.target_object["audio_file"] = new_path
                        self.target_object["audio_path"] = new_path
                else:
                    if is_trk:
                        raw["path"] = src_aud
                        self.target_object["path"] = src_aud
                    else:
                        raw["audio_file"] = src_aud
                        raw["audio_path"] = src_aud
                        self.target_object["audio_file"] = src_aud
                        self.target_object["audio_path"] = src_aud
                if hasattr(self, "lbl_fx_status"):
                    self.lbl_fx_status.setText(f"✅ បានអនុវត្ត Effect: {fx_key}")
                    self.lbl_fx_status.show()
                self.voice_effect_applied.emit(self.target_object, fx_key)
                self.audio_modified.emit(self.target_object)

        # Batch application to all lines or character
        if scope in ("character", "all"):
            char_name = ""
            if isinstance(self.target_object, dict):
                raw = self.target_object.get("raw") if isinstance(self.target_object.get("raw"), dict) else self.target_object
                char_name = raw.get("speaker") or raw.get("actor") or raw.get("character") or ""
                if not char_name and raw.get("gender"):
                    g = raw.get("gender")
                    char_name = "តួស្រី (Female)" if g == "female" else ("តួប្រុស (Male)" if g == "male" else "")
            self.batch_voice_effect_applied.emit(fx_key, scope, char_name)
