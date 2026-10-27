"""
AI Face Mesh, AR Stickers & Auto Face Blur Panel Component
Provides a state-of-the-art interactive inspector for:
1. Sticker Follow Face: Sunglasses, Hats, Crowns, Mustaches, Masks & Custom Uploads auto-tracking on faces
2. Auto Face Blur: Real-time Gaussian blur, Mosaic, Frosted glass, and Blackout face censoring
3. Face Mesh Tracking: 478-landmark AR wireframe preview
"""

import os
from typing import Optional
from ui_v_PyQt6.qt_compat import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QCheckBox, QFrame, QGroupBox, QTabWidget,
    QFileDialog, Qt, Signal, QColor, QFont, QPixmap, QProgressBar, QMessageBox,
    QLineEdit, QScrollArea, QImage
)
from ui_v_PyQt6.icons import get_qta_icon
from services.video.face_tracking_service import (
    FaceMeshDetector, AutoFaceBlurProcessor, FaceARPropsEngine, VideoFaceScannerWorker
)


class FaceARStudioPanel(QWidget):
    """
    Dedicated AI Face Tracking & AR Filter Studio Component.
    Controls live face tracking on the video monitor canvas.
    """
    settings_changed = Signal()
    request_canvas_update = Signal()

    def __init__(self, canvas=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas

        # State Attributes
        self.ar_enabled = False
        self.ar_prop_type = "glasses"   # "glasses", "crown", "mustache", "mask", "bunny", "custom"
        self.ar_anchor = "eyes"         # "eyes", "head", "mouth", "face"
        self.ar_scale = 1.0
        self.ar_offset_y = 0.0
        self.custom_sticker_path = None
        self.custom_sticker_pixmap = None

        self.auto_blur_enabled = False
        self.blur_mode = "blur"         # "blur", "mosaic", "glass", "blackout"
        self.blur_strength = 25
        self.blur_shape = "ellipse"     # "ellipse", "rect"
        self.blur_feather = True

        self.mesh_wireframe_enabled = False

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # 1. Header Card
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:1 #0f172a);
                border: 1px solid #4338ca;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(4, 4, 4, 4)
        h_layout.setSpacing(8)

        lbl_icon = QLabel("🎭")
        lbl_icon.setStyleSheet("font-size: 16px;")
        h_layout.addWidget(lbl_icon)

        lbl_title = QLabel("AI Face & AR Studio (ចាប់ផ្ទៃមុខ AI)")
        lbl_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #a5b4fc;")
        h_layout.addWidget(lbl_title, 1)

        lbl_badge = QLabel("MediaPipe")
        lbl_badge.setStyleSheet("""
            background-color: #3730a3;
            color: #c7d2fe;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        h_layout.addWidget(lbl_badge)
        main_layout.addWidget(header)

        # 2. Main Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0f172a;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 6px 10px;
                font-size: 10px;
                font-weight: bold;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #4338ca;
                color: #ffffff;
            }
        """)

        # Tab 1: Sticker Follow Face
        self.tab_stickers = self._create_stickers_tab()
        self.tabs.addTab(self.tab_stickers, "🎭 AR Stickers")

        # Tab 2: Auto Face Blur
        self.tab_blur = self._create_blur_tab()
        self.tabs.addTab(self.tab_blur, "🌫️ Auto Blur")

        # Tab 3: Face Mesh Wireframe
        self.tab_mesh = self._create_mesh_tab()
        self.tabs.addTab(self.tab_mesh, "🕸️ Face Mesh")

        # Tab 4: AI Auto Reframe (16:9 ➔ 9:16 Short Video Face Tracking)
        self.tab_reframe = self._create_reframe_tab()
        self.tabs.addTab(self.tab_reframe, "🎬 Reframe 9:16")

        # Tab 5: AI Face & Cast Recognition Suite (ស្កេនចាប់មុខមនុស្សទាំងអស់ក្នុងវីដេអូ)
        self.tab_scanner = self._create_scanner_tab()
        self.tabs.addTab(self.tab_scanner, "👥 Cast Scan (ស្កេនមុខ)")

        main_layout.addWidget(self.tabs, 1)

    def _create_stickers_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Master Toggle
        self.btn_toggle_ar = QPushButton("🎭 Enable Sticker Follow Face (បើកស្ទីគ័រតាមមុខ)")
        self.btn_toggle_ar.setCheckable(True)
        self.btn_toggle_ar.setChecked(False)
        self.btn_toggle_ar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_ar.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #4f46e5;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        self.btn_toggle_ar.toggled.connect(self._on_ar_toggled)
        layout.addWidget(self.btn_toggle_ar)

        # Preset Accessories Selector
        group_props = QGroupBox("Select Accessory (ជ្រើសរើសស្ទីគ័រ ឬវត្ថុ)")
        group_props.setStyleSheet(self._group_style())
        g_layout = QVBoxLayout(group_props)
        g_layout.setSpacing(6)

        self.combo_prop = QComboBox()
        self.combo_prop.addItem("🕶️ Cool Sunglasses (វ៉ែនតាខ្មៅ Cinema)", "glasses")
        self.combo_prop.addItem("👑 Royal Golden Crown (ម្កុដរាជវង្សមាស)", "crown")
        self.combo_prop.addItem("🥸 Gentleman Mustache (ពុកមាត់បុរាណ)", "mustache")
        self.combo_prop.addItem("😷 Protective Face Mask (ម៉ាសការពារ)", "mask")
        self.combo_prop.addItem("🐰 Cute Bunny Ears (ត្រចៀកទន្សាយ)", "bunny")
        self.combo_prop.addItem("📁 Custom Sticker / Logo (រូបភាពផ្ទាល់ខ្លួន)", "custom")
        self.combo_prop.setStyleSheet(self._input_style())
        self.combo_prop.currentIndexChanged.connect(self._on_prop_changed)
        g_layout.addWidget(self.combo_prop)

        # Custom image upload button
        self.btn_upload_sticker = QPushButton("📁 Upload Custom PNG / Sticker...")
        self.btn_upload_sticker.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            border: 1px dashed #0284c7;
            border-radius: 4px;
            padding: 6px;
            font-size: 11px;
            font-weight: bold;
        """)
        self.btn_upload_sticker.clicked.connect(self._on_upload_sticker)
        self.btn_upload_sticker.hide()
        g_layout.addWidget(self.btn_upload_sticker)

        self.lbl_sticker_preview = QLabel("")
        self.lbl_sticker_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_sticker_preview.hide()
        g_layout.addWidget(self.lbl_sticker_preview)

        layout.addWidget(group_props)

        # Anchor & Scale Group
        group_adjust = QGroupBox("Tracking Geometry (ទីតាំង និងទំហំ)")
        group_adjust.setStyleSheet(self._group_style())
        adj_layout = QVBoxLayout(group_adjust)
        adj_layout.setSpacing(6)

        row_anchor = QHBoxLayout()
        row_anchor.addWidget(QLabel("Anchor:"))
        self.combo_anchor = QComboBox()
        self.combo_anchor.addItem("👀 Eyes (ភ្នែក)", "eyes")
        self.combo_anchor.addItem("👑 Forehead / Head (ថ្ងាស/ក្បាល)", "head")
        self.combo_anchor.addItem("👄 Nose / Mouth (ច្រមុះ/មាត់)", "mouth")
        self.combo_anchor.addItem("🎯 Face Center (កណ្តាលមុខ)", "face")
        self.combo_anchor.setStyleSheet(self._input_style())
        self.combo_anchor.currentIndexChanged.connect(self._on_geometry_changed)
        row_anchor.addWidget(self.combo_anchor, 1)
        adj_layout.addLayout(row_anchor)

        # Scale slider
        adj_layout.addWidget(QLabel("Scale Factor (ទំហំ %):"))
        self.slider_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_scale.setRange(50, 250)
        self.slider_scale.setValue(100)
        self.slider_scale.valueChanged.connect(self._on_geometry_changed)
        adj_layout.addWidget(self.slider_scale)

        # Offset Y slider
        adj_layout.addWidget(QLabel("Offset Height Y (លើ / ក្រោម):"))
        self.slider_offset_y = QSlider(Qt.Orientation.Horizontal)
        self.slider_offset_y.setRange(-50, 50)
        self.slider_offset_y.setValue(0)
        self.slider_offset_y.valueChanged.connect(self._on_geometry_changed)
        adj_layout.addWidget(self.slider_offset_y)

        layout.addWidget(group_adjust)
        layout.addStretch()
        return widget

    def _create_blur_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Master Toggle
        self.btn_toggle_blur = QPushButton("🛡️ Enable Auto Face Blur (ធ្វើឱ្យមុខព្រាលស្វ័យប្រវត្តិ)")
        self.btn_toggle_blur.setCheckable(True)
        self.btn_toggle_blur.setChecked(False)
        self.btn_toggle_blur.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_blur.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #dc2626;
                color: #ffffff;
                border-color: #ef4444;
            }
        """)
        self.btn_toggle_blur.toggled.connect(self._on_blur_toggled)
        layout.addWidget(self.btn_toggle_blur)

        # Blur Mode Group
        group_bmode = QGroupBox("Blur & Censor Style (របៀបបិទបាំង)")
        group_bmode.setStyleSheet(self._group_style())
        b_layout = QVBoxLayout(group_bmode)
        b_layout.setSpacing(6)

        self.combo_bmode = QComboBox()
        self.combo_bmode.addItem("🌫️ Smooth Blur (ព្រិលរលូនបែប Gaussian)", "blur")
        self.combo_bmode.addItem("🔲 Mosaic Pixelate (ការ៉ូ Censor ភាពយន្ត)", "mosaic")
        self.combo_bmode.addItem("✨ Frosted Glass (កញ្ចក់បែកផ្សែង Glassmorphism)", "glass")
        self.combo_bmode.addItem("⬛ Blackout Oval (បិទខ្មៅទម្រង់មុខ)", "blackout")
        self.combo_bmode.setStyleSheet(self._input_style())
        self.combo_bmode.currentIndexChanged.connect(self._on_blur_props_changed)
        b_layout.addWidget(self.combo_bmode)

        b_layout.addWidget(QLabel("Blur Intensity (កម្រិតព្រិល):"))
        self.slider_b_strength = QSlider(Qt.Orientation.Horizontal)
        self.slider_b_strength.setRange(5, 60)
        self.slider_b_strength.setValue(25)
        self.slider_b_strength.valueChanged.connect(self._on_blur_props_changed)
        b_layout.addWidget(self.slider_b_strength)

        # Mask Shape
        row_shape = QHBoxLayout()
        row_shape.addWidget(QLabel("Mask Shape:"))
        self.combo_bshape = QComboBox()
        self.combo_bshape.addItem("🥚 Natural Face Ellipse (រាងពងក្រពើ)", "ellipse")
        self.combo_bshape.addItem("⬛ Box Rectangle (ប្រអប់បួនជ្រុង)", "rect")
        self.combo_bshape.setStyleSheet(self._input_style())
        self.combo_bshape.currentIndexChanged.connect(self._on_blur_props_changed)
        row_shape.addWidget(self.combo_bshape, 1)
        b_layout.addLayout(row_shape)

        self.chk_b_feather = QCheckBox("Smooth Feathering Edge (គែមរលូនទន់)")
        self.chk_b_feather.setChecked(True)
        self.chk_b_feather.setStyleSheet("color: #38bdf8; font-size: 11px;")
        self.chk_b_feather.toggled.connect(self._on_blur_props_changed)
        b_layout.addWidget(self.chk_b_feather)

        layout.addWidget(group_bmode)
        layout.addStretch()
        return widget

    def _create_mesh_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Wireframe Toggle
        self.btn_toggle_mesh = QPushButton("🕸️ Show AI Face Mesh Wireframe (បង្ហាញក្រឡាមុខ)")
        self.btn_toggle_mesh.setCheckable(True)
        self.btn_toggle_mesh.setChecked(False)
        self.btn_toggle_mesh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_mesh.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #0284c7;
                color: #ffffff;
                border-color: #38bdf8;
            }
        """)
        self.btn_toggle_mesh.toggled.connect(self._on_mesh_toggled)
        layout.addWidget(self.btn_toggle_mesh)

        card_info = QFrame()
        card_info.setStyleSheet("background-color: #171d2b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        ci_layout = QVBoxLayout(card_info)
        ci_layout.setSpacing(4)
        lbl_m1 = QLabel("🔍 MediaPipe 478 Landmarks")
        lbl_m1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        ci_layout.addWidget(lbl_m1)
        lbl_m2 = QLabel("• ចាប់ទីតាំងភ្នែកឆ្វេង / ភ្នែកស្តាំ (Left / Right Eye)\n• ច្រមុះ, បបូរមាត់លើ-ក្រោម (Nose, Lips)\n• ថ្ងាស, ចង្កា, និងទម្រង់មុខ (Contour)\n• គណនាមុំក្បាលរលូន 60fps (Roll Angle)")
        lbl_m2.setStyleSheet("color: #94a3b8; font-size: 10px;")
        ci_layout.addWidget(lbl_m2)
        layout.addWidget(card_info)

        layout.addStretch()
        return widget

    def _input_style(self) -> str:
        return """
            QComboBox, QSpinBox {
                background-color: #1e293b;
                color: #ffffff;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:focus, QSpinBox:focus {
                border-color: #6366f1;
            }
        """

    def _group_style(self) -> str:
        return """
            QGroupBox {
                border: 1px solid #1e293b;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-size: 10px;
                font-weight: bold;
                color: #818cf8;
            }
        """

    # ------------------ EVENT LISTENERS ------------------
    def _on_ar_toggled(self, checked: bool):
        self.ar_enabled = checked
        if self.canvas:
            setattr(self.canvas, "face_ar_enabled", checked)
            self._sync_canvas_face_settings()
            self.canvas.update()

    def _on_prop_changed(self):
        self.ar_prop_type = self.combo_prop.currentData()
        is_custom = (self.ar_prop_type == "custom")
        self.btn_upload_sticker.setVisible(is_custom)
        self.lbl_sticker_preview.setVisible(is_custom and self.custom_sticker_pixmap is not None)

        # Auto-suggest anchor
        if self.ar_prop_type in ("glasses", "bunny"):
            idx = self.combo_anchor.findData("head" if self.ar_prop_type == "bunny" else "eyes")
            if idx >= 0:
                self.combo_anchor.setCurrentIndex(idx)
        elif self.ar_prop_type == "crown":
            idx = self.combo_anchor.findData("head")
            if idx >= 0:
                self.combo_anchor.setCurrentIndex(idx)
        elif self.ar_prop_type in ("mustache", "mask"):
            idx = self.combo_anchor.findData("mouth")
            if idx >= 0:
                self.combo_anchor.setCurrentIndex(idx)

        self._sync_canvas_face_settings()
        if self.canvas:
            self.canvas.update()

    def _on_upload_sticker(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "ជ្រើសរើសរូបភាព Sticker / PNG", "",
            "Images (*.png *.webp *.jpg *.jpeg)"
        )
        if f:
            self.custom_sticker_path = f
            pm = QPixmap(f)
            if not pm.isNull():
                self.custom_sticker_pixmap = pm
                scaled = pm.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.lbl_sticker_preview.setPixmap(scaled)
                self.lbl_sticker_preview.show()
                self._sync_canvas_face_settings()
                if self.canvas:
                    self.canvas.update()

    def _on_geometry_changed(self):
        self.ar_anchor = self.combo_anchor.currentData()
        self.ar_scale = self.slider_scale.value() / 100.0
        self.ar_offset_y = (self.slider_offset_y.value() / 50.0) * 0.08  # up to +-8% canvas height
        self._sync_canvas_face_settings()
        if self.canvas:
            self.canvas.update()

    def _on_blur_toggled(self, checked: bool):
        self.auto_blur_enabled = checked
        if self.canvas:
            setattr(self.canvas, "auto_face_blur_enabled", checked)
            self._sync_canvas_face_settings()
            self.canvas.update()

    def _on_blur_props_changed(self):
        self.blur_mode = self.combo_bmode.currentData()
        self.blur_strength = self.slider_b_strength.value()
        self.blur_shape = self.combo_bshape.currentData()
        self.blur_feather = self.chk_b_feather.isChecked()
        self._sync_canvas_face_settings()
        if self.canvas:
            self.canvas.update()

    def _on_mesh_toggled(self, checked: bool):
        self.mesh_wireframe_enabled = checked
        if self.canvas:
            setattr(self.canvas, "face_mesh_overlay_enabled", checked)
            self.canvas.update()

    def _sync_canvas_face_settings(self):
        if not self.canvas:
            return
        setattr(self.canvas, "face_ar_enabled", self.ar_enabled)
        setattr(self.canvas, "face_ar_prop", self.ar_prop_type)
        setattr(self.canvas, "face_ar_anchor", self.ar_anchor)
        setattr(self.canvas, "face_ar_scale", self.ar_scale)
        setattr(self.canvas, "face_ar_offset_y", self.ar_offset_y)
        setattr(self.canvas, "face_ar_custom_pixmap", self.custom_sticker_pixmap)

        setattr(self.canvas, "auto_face_blur_enabled", self.auto_blur_enabled)
        setattr(self.canvas, "auto_face_blur_mode", self.blur_mode)
        setattr(self.canvas, "auto_face_blur_strength", self.blur_strength)
        setattr(self.canvas, "auto_face_blur_shape", self.blur_shape)
        setattr(self.canvas, "auto_face_blur_feather", self.blur_feather)
        setattr(self.canvas, "face_mesh_overlay_enabled", self.mesh_wireframe_enabled)

    # ------------------ TAB 4: AUTO REFRAME 9:16 ------------------
    def _create_reframe_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Info Card
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0c4a6e, stop:1 #0f172a);
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setContentsMargins(4, 4, 4, 4)
        ic_layout.setSpacing(3)
        lbl_h1 = QLabel("🎬 AI Auto Reframe (16:9 ➔ 9:16)")
        lbl_h1.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        ic_layout.addWidget(lbl_h1)
        lbl_h2 = QLabel("បម្លែង Long Video ទៅជា 9:16 Short Video (TikTok / Reels) ដោយកាមេរ៉ារត់តាមចាប់មុខតួអង្គស្វ័យប្រវត្តិកណ្តាលប្លង់។")
        lbl_h2.setWordWrap(True)
        lbl_h2.setStyleSheet("color: #94a3b8; font-size: 10px; line-height: 1.3;")
        ic_layout.addWidget(lbl_h2)
        layout.addWidget(info_card)

        # Settings Group
        group_set = QGroupBox("Reframe Tracking Settings (ការកំណត់)")
        group_set.setStyleSheet(self._group_style())
        s_layout = QVBoxLayout(group_set)
        s_layout.setContentsMargins(6, 12, 6, 6)
        s_layout.setSpacing(6)

        # Mode
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Tracking Mode:"))
        self.combo_reframe_mode = QComboBox()
        self.combo_reframe_mode.addItem("🎯 Single Face (មុខតួអង្គកណ្តាល)", "single")
        self.combo_reframe_mode.addItem("👥 Group / Multi-Person (តាមក្រុមមនុស្ស)", "group")
        self.combo_reframe_mode.addItem("🗣️ Active Speaker (តាមអ្នកនិយាយ)", "speaker")
        self.combo_reframe_mode.setStyleSheet(self._input_style())
        row_mode.addWidget(self.combo_reframe_mode, 1)
        s_layout.addLayout(row_mode)

        # Smoothness Slider
        s_layout.addWidget(QLabel("Camera Smoothness (កម្រិតរលូនកាមេរ៉ា):"))
        row_smooth = QHBoxLayout()
        self.slider_reframe_smooth = QSlider(Qt.Orientation.Horizontal)
        self.slider_reframe_smooth.setRange(40, 95)
        self.slider_reframe_smooth.setValue(80)
        row_smooth.addWidget(self.slider_reframe_smooth, 1)
        self.lbl_reframe_smooth_val = QLabel("80%")
        self.lbl_reframe_smooth_val.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 10px;")
        self.slider_reframe_smooth.valueChanged.connect(lambda v: self.lbl_reframe_smooth_val.setText(f"{v}%"))
        row_smooth.addWidget(self.lbl_reframe_smooth_val)
        s_layout.addLayout(row_smooth)

        layout.addWidget(group_set)

        # Analyze Button
        self.btn_reframe_analyze = QPushButton("⚡ Analyze & Track Face (ចាប់ប្លង់តាមមុខ)")
        self.btn_reframe_analyze.setIcon(get_qta_icon("fa5s.magic", color="#ffffff"))
        self.btn_reframe_analyze.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reframe_analyze.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #38bdf8;
                border-radius: 6px;
                padding: 9px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
                border-color: #475569;
            }
        """)
        self.btn_reframe_analyze.clicked.connect(self._start_inline_reframe_analysis)
        layout.addWidget(self.btn_reframe_analyze)

        # Progress bar
        self.reframe_progress = QProgressBar()
        self.reframe_progress.setRange(0, 100)
        self.reframe_progress.setValue(0)
        self.reframe_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #0f172a;
                text-align: center;
                height: 14px;
                font-size: 9px;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #0284c7;
                border-radius: 3px;
            }
        """)
        self.reframe_progress.hide()
        layout.addWidget(self.reframe_progress)

        # Status Label
        self.lbl_reframe_status = QLabel("")
        self.lbl_reframe_status.setWordWrap(True)
        self.lbl_reframe_status.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
        self.lbl_reframe_status.hide()
        layout.addWidget(self.lbl_reframe_status)

        # Dialog Launcher Button
        btn_full_suite = QPushButton("🎬 Open Full Reframe Suite (នាំចេញ Export MP4)...")
        btn_full_suite.setIcon(get_qta_icon("fa5s.expand", color="#38bdf8"))
        btn_full_suite.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_full_suite.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px;
                font-size: 10px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #273549;
                border-color: #38bdf8;
                color: #38bdf8;
            }
        """)
        btn_full_suite.clicked.connect(self._open_auto_reframe_dialog)
        layout.addWidget(btn_full_suite)

        # Reset button
        btn_reset_aspect = QPushButton("🔄 Reset to Original 16:9 (កំណត់ទៅ 16:9 ដើមវិញ)")
        btn_reset_aspect.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset_aspect.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: 1px dashed #334155;
                border-radius: 4px;
                padding: 5px;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #f43f5e;
                border-color: #f43f5e;
            }
        """)
        btn_reset_aspect.clicked.connect(self._on_reset_reframe)
        layout.addWidget(btn_reset_aspect)

        layout.addStretch()
        return widget

    def _get_current_video_path(self) -> Optional[str]:
        if self.canvas:
            if hasattr(self.canvas, "video_path") and self.canvas.video_path:
                return self.canvas.video_path
            p = self.canvas.parent()
            while p:
                if hasattr(p, "video_path") and p.video_path:
                    return p.video_path
                p = p.parent()
        p = self.parent()
        while p:
            if hasattr(p, "video_path") and p.video_path:
                return p.video_path
            p = p.parent()
        return None

    def _open_auto_reframe_dialog(self):
        v_path = self._get_current_video_path()
        p = self.parent()
        while p:
            if hasattr(p, "open_auto_reframe_dialog"):
                p.open_auto_reframe_dialog()
                return
            if hasattr(p, "player_view") and hasattr(p.player_view, "open_auto_reframe_dialog"):
                p.player_view.open_auto_reframe_dialog()
                return
            p = p.parent()

        from ui_v_PyQt6.components.player.auto_reframe_dialog import AutoReframeDialog
        dlg = AutoReframeDialog(parent=self, video_path=v_path)
        dlg.reframe_applied.connect(self._on_reframe_finished)
        dlg.exec()

    def _start_inline_reframe_analysis(self):
        v_path = self._get_current_video_path()
        if not v_path or not os.path.exists(v_path):
            QMessageBox.warning(self, "គ្មានវីដេអូ", "សូមបញ្ចូល Video ជាមុនសិន មុនពេលដំណើរការ AI Auto Reframe!")
            return

        mode = self.combo_reframe_mode.currentData() or "single"
        smoothness = self.slider_reframe_smooth.value() / 100.0

        self.btn_reframe_analyze.setEnabled(False)
        self.reframe_progress.setValue(0)
        self.reframe_progress.show()
        self.lbl_reframe_status.setText("⏳ កំពុងវិភាគមុខតួអង្គ (AI Face Tracking)...")
        self.lbl_reframe_status.show()

        from ui_v_PyQt6.components.player.auto_reframe_dialog import AutoReframeWorker
        self.reframe_worker = AutoReframeWorker(v_path, mode=mode, smoothness=smoothness)
        self.reframe_worker.progress.connect(self._on_reframe_progress)
        self.reframe_worker.finished.connect(self._on_reframe_finished)
        self.reframe_worker.error.connect(self._on_reframe_error)
        self.reframe_worker.start()

    def _on_reframe_progress(self, pct: float, msg: str):
        self.reframe_progress.setValue(int(pct * 100))
        self.lbl_reframe_status.setText(msg)

    def _on_reframe_finished(self, data: dict):
        self.btn_reframe_analyze.setEnabled(True)
        self.reframe_progress.setValue(100)
        self.lbl_reframe_status.setText("✅ វិភាគជោគជ័យ! ប្លង់កាមេរ៉ារត់តាមមុខតួអង្គ 9:16 រួចរាល់។")
        if self.canvas:
            self.canvas.set_reframe_data(data)
            self.canvas.set_aspect_ratio("9:16")
            self.canvas.update()
            p = self.canvas.parent()
            while p:
                if hasattr(p, "btn_quick_aspect"):
                    p.btn_quick_aspect.setText("9:16 ∨")
                if hasattr(p, "monitor_header") and p.monitor_header and hasattr(p.monitor_header, "combo_ratio"):
                    p.monitor_header.combo_ratio.blockSignals(True)
                    p.monitor_header.combo_ratio.setCurrentText("9:16 TikTok / Shorts")
                    p.monitor_header.combo_ratio.blockSignals(False)
                p = p.parent()

    def _on_reframe_error(self, err: str):
        self.btn_reframe_analyze.setEnabled(True)
        self.lbl_reframe_status.setText(f"❌ កំហុស: {err}")

    def _on_reset_reframe(self):
        if self.canvas:
            self.canvas.set_reframe_data(None)
            self.canvas.set_aspect_ratio("16:9")
            self.canvas.update()
            p = self.canvas.parent()
            while p:
                if hasattr(p, "btn_quick_aspect"):
                    p.btn_quick_aspect.setText("16:9 ∨")
                if hasattr(p, "monitor_header") and p.monitor_header and hasattr(p.monitor_header, "combo_ratio"):
                    p.monitor_header.combo_ratio.blockSignals(True)
                    p.monitor_header.combo_ratio.setCurrentText("16:9 Long Video (YouTube / Cinema)")
                    p.monitor_header.combo_ratio.blockSignals(False)
                p = p.parent()
        self.lbl_reframe_status.setText("🔄 បានកំណត់ទំហំ 16:9 ដើមវិញ។")
        self.lbl_reframe_status.show()

    # =========================================================================
    # TAB 5: AI FULL-VIDEO FACE & CAST SCANNER (ស្កេនចាប់មុខមនុស្សទាំងអស់ក្នុងវីដេអូ)
    # =========================================================================
    def _create_scanner_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 1. Info Card
        info_card = QFrame()
        info_card.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:1 #0f172a);
                border: 1px solid #6366f1;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        ic_layout = QVBoxLayout(info_card)
        ic_layout.setContentsMargins(4, 4, 4, 4)
        ic_layout.setSpacing(3)
        lbl_h1 = QLabel("👥 AI Video Face & Cast Scanner (ស្កេនចាប់មុខមនុស្សទាំងអស់)")
        lbl_h1.setStyleSheet("color: #818cf8; font-weight: bold; font-size: 11px;")
        ic_layout.addWidget(lbl_h1)
        lbl_h2 = QLabel("ស្កេនវីដេអូទាំងមូលដើម្បីសម្គាល់រាល់មុខតួអង្គទាំងអស់ (Cast / People Recognition) បង្ហាញរូប Avatar ម៉ោងបង្ហាញខ្លួន និងចុច Jump ទៅមើលប្លង់ភ្លាមៗ។")
        lbl_h2.setWordWrap(True)
        lbl_h2.setStyleSheet("color: #94a3b8; font-size: 10px; line-height: 1.3;")
        ic_layout.addWidget(lbl_h2)
        layout.addWidget(info_card)

        # 2. Settings Group
        group_set = QGroupBox("Scan Settings (ការកំណត់ស្កេន)")
        group_set.setStyleSheet(self._group_style())
        s_layout = QVBoxLayout(group_set)
        s_layout.setContentsMargins(6, 12, 6, 6)
        s_layout.setSpacing(6)

        # Sampling Frequency
        row_freq = QHBoxLayout()
        row_freq.addWidget(QLabel("Scan Interval:"))
        self.combo_scan_interval = QComboBox()
        self.combo_scan_interval.addItem("⚡ Fast (Every 2.0s - ស្កេនលឿន)", 2.0)
        self.combo_scan_interval.addItem("⚖️ Balanced (Every 1.0s - មធ្យម)", 1.0)
        self.combo_scan_interval.addItem("🔍 Detailed (Every 0.5s - លម្អិត)", 0.5)
        self.combo_scan_interval.setCurrentIndex(1)
        self.combo_scan_interval.setStyleSheet(self._input_style())
        row_freq.addWidget(self.combo_scan_interval, 1)
        s_layout.addLayout(row_freq)

        # Similarity Sensitivity
        row_sim = QHBoxLayout()
        row_sim.addWidget(QLabel("Grouping Match:"))
        self.slider_similarity = QSlider(Qt.Orientation.Horizontal)
        self.slider_similarity.setRange(50, 85)
        self.slider_similarity.setValue(65)
        row_sim.addWidget(self.slider_similarity, 1)
        self.lbl_sim_val = QLabel("65%")
        self.lbl_sim_val.setStyleSheet("color: #818cf8; font-weight: bold; font-size: 10px;")
        self.slider_similarity.valueChanged.connect(lambda v: self.lbl_sim_val.setText(f"{v}%"))
        row_sim.addWidget(self.lbl_sim_val)
        s_layout.addLayout(row_sim)

        layout.addWidget(group_set)

        # 3. Action Buttons
        row_act = QHBoxLayout()
        row_act.setSpacing(6)

        self.btn_start_scan = QPushButton("🔍 Scan All Faces (ចាប់ផ្តើមស្កេន)")
        self.btn_start_scan.setIcon(get_qta_icon("fa5s.search", color="#ffffff"))
        self.btn_start_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start_scan.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #818cf8;
                border-radius: 6px;
                padding: 8px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #4f46e5;
            }
            QPushButton:disabled {
                background-color: #334155;
                color: #94a3b8;
                border-color: #475569;
            }
        """)
        self.btn_start_scan.clicked.connect(self._start_face_scan)
        row_act.addWidget(self.btn_start_scan, 1)

        self.btn_cancel_scan = QPushButton("✖ Cancel")
        self.btn_cancel_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel_scan.setEnabled(False)
        self.btn_cancel_scan.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f87171;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
            }
            QPushButton:hover:enabled {
                background-color: #7f1d1d;
                color: #ffffff;
            }
            QPushButton:disabled {
                color: #475569;
            }
        """)
        self.btn_cancel_scan.clicked.connect(self._cancel_face_scan)
        row_act.addWidget(self.btn_cancel_scan)

        layout.addLayout(row_act)

        # 4. Progress bar & Status
        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                background-color: #0f172a;
                text-align: center;
                height: 14px;
                font-size: 9px;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #6366f1;
                border-radius: 3px;
            }
        """)
        self.scan_progress.hide()
        layout.addWidget(self.scan_progress)

        self.lbl_scan_status = QLabel("")
        self.lbl_scan_status.setWordWrap(True)
        self.lbl_scan_status.setStyleSheet("color: #818cf8; font-size: 10px; font-weight: bold;")
        self.lbl_scan_status.hide()
        layout.addWidget(self.lbl_scan_status)

        # 5. Results Section Header
        hdr_res = QHBoxLayout()
        self.lbl_cast_count = QLabel("👥 Detected Characters & Cast:")
        self.lbl_cast_count.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px;")
        hdr_res.addWidget(self.lbl_cast_count, 1)

        self.btn_export_cast = QPushButton("💾 Save Crops")
        self.btn_export_cast.setIcon(get_qta_icon("fa5s.save", color="#38bdf8"))
        self.btn_export_cast.setToolTip("Export HD PNG Face crops of all detected characters to folder")
        self.btn_export_cast.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2e384d;
            }
        """)
        self.btn_export_cast.clicked.connect(self._export_cast_crops)
        self.btn_export_cast.hide()
        hdr_res.addWidget(self.btn_export_cast)
        layout.addLayout(hdr_res)

        # 6. Scrollable Cast List Container
        self.cast_scroll = QScrollArea()
        self.cast_scroll.setWidgetResizable(True)
        self.cast_scroll.setStyleSheet("border: none; background: transparent;")
        self.cast_container = QWidget()
        self.cast_layout = QVBoxLayout(self.cast_container)
        self.cast_layout.setContentsMargins(0, 0, 0, 0)
        self.cast_layout.setSpacing(6)

        # Empty state placeholder
        self.lbl_cast_empty = QLabel("👉 ចុច 'Scan All Faces' ដើម្បីឱ្យ AI ចាប់រាប់មុខមនុស្ស និងតួអង្គទាំងអស់ក្នុងវីដេអូ។")
        self.lbl_cast_empty.setWordWrap(True)
        self.lbl_cast_empty.setStyleSheet("color: #64748b; font-size: 10px; padding: 10px 4px; line-height: 1.4;")
        self.cast_layout.addWidget(self.lbl_cast_empty)
        self.cast_layout.addStretch(1)

        self.cast_scroll.setWidget(self.cast_container)
        layout.addWidget(self.cast_scroll, 1)

        self._scanned_cast_clusters = []
        return widget

    def _start_face_scan(self):
        v_path = self._get_current_video_path()
        if not v_path or not os.path.exists(v_path):
            QMessageBox.warning(self, "គ្មានវីដេអូ", "សូមបើក Video ជាមុនសិន មុនពេលដំណើរការ AI Face & Cast Scan!")
            return

        interval = self.combo_scan_interval.currentData() or 1.0
        similarity = self.slider_similarity.value() / 100.0

        self.btn_start_scan.setEnabled(False)
        self.btn_cancel_scan.setEnabled(True)
        self.scan_progress.setValue(0)
        self.scan_progress.show()
        self.lbl_scan_status.setText("⏳ កំពុងស្កេនចាប់មុខមនុស្សក្នុងវីដេអូ (AI Face Recognition)...")
        self.lbl_scan_status.show()

        self.scan_worker = VideoFaceScannerWorker(v_path, sample_interval=interval, similarity_thresh=similarity)
        self.scan_worker.progress.connect(self._on_scan_progress)
        self.scan_worker.finished.connect(self._on_scan_finished)
        self.scan_worker.error.connect(self._on_scan_error)
        self.scan_worker.start()

    def _cancel_face_scan(self):
        if hasattr(self, "scan_worker") and self.scan_worker.isRunning():
            self.scan_worker.cancel()
            self.scan_worker.wait(1000)
            self.lbl_scan_status.setText("⏹️ បានបញ្ឈប់ការស្កេន។")
            self.btn_start_scan.setEnabled(True)
            self.btn_cancel_scan.setEnabled(False)
            self.scan_progress.hide()

    def _on_scan_progress(self, pct: int, sec: float, count: int):
        self.scan_progress.setValue(pct)
        m = int(sec // 60)
        s = int(sec % 60)
        self.lbl_scan_status.setText(f"⏳ ស្កេនដល់ {m:02d}:{s:02d} ({pct}%) • រកឃើញមនុស្ស {count} នាក់...")

    def _on_scan_error(self, err_msg: str):
        self.btn_start_scan.setEnabled(True)
        self.btn_cancel_scan.setEnabled(False)
        self.scan_progress.hide()
        self.lbl_scan_status.setText(f"❌ បរាជ័យ: {err_msg}")
        QMessageBox.critical(self, "Face Scan Error", f"មានបញ្ហាក្នុងការស្កេន: {err_msg}")

    def _on_scan_finished(self, clusters: list):
        self._scanned_cast_clusters = clusters
        self.btn_start_scan.setEnabled(True)
        self.btn_cancel_scan.setEnabled(False)
        self.scan_progress.hide()

        count = len(clusters)
        self.lbl_scan_status.setText(f"✅ ស្កេនរួចរាល់! បានរកឃើញតួអង្គចំនួន {count} នាក់។")
        self.lbl_scan_status.show()
        self.lbl_cast_count.setText(f"👥 Characters Detected ({count}):")
        if count > 0:
            self.btn_export_cast.show()

        # Clear existing widgets from cast_layout
        while self.cast_layout.count():
            item = self.cast_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if count == 0:
            lbl = QLabel("រកមិនឃើញផ្ទៃមុខមនុស្សនៅក្នុងវីដេអូនេះឡើយ។")
            lbl.setStyleSheet("color: #94a3b8; font-size: 10px; padding: 10px;")
            self.cast_layout.addWidget(lbl)
            self.cast_layout.addStretch(1)
            return

        for person in clusters:
            card = self._create_person_card(person)
            self.cast_layout.addWidget(card)

        self.cast_layout.addStretch(1)

    def _create_person_card(self, person: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #171c26;
                border: 1px solid #232b3b;
                border-radius: 8px;
            }
            QFrame:hover {
                border: 1px solid #6366f1;
                background-color: #1c2230;
            }
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(8, 8, 8, 8)
        c_layout.setSpacing(6)

        # Top row: Avatar + Name + Count
        row_top = QHBoxLayout()
        row_top.setSpacing(8)

        # Avatar thumbnail
        lbl_avatar = QLabel()
        lbl_avatar.setFixedSize(52, 52)
        lbl_avatar.setStyleSheet("border-radius: 6px; border: 1px solid #4338ca; background-color: #0b0f19;")
        lbl_avatar.setScaledContents(True)

        thumb_bgr = person.get("thumb_bgr")
        if thumb_bgr is not None and thumb_bgr.size > 0:
            import cv2
            h, w = thumb_bgr.shape[:2]
            rgb = cv2.cvtColor(thumb_bgr, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg)
            lbl_avatar.setPixmap(pix)
        row_top.addWidget(lbl_avatar)

        # Details
        v_info = QVBoxLayout()
        v_info.setSpacing(3)

        # Editable name
        txt_name = QLineEdit(person.get("name", "Person"))
        txt_name.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                color: #f8fafc;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QLineEdit:focus {
                border-color: #6366f1;
            }
        """)
        txt_name.textChanged.connect(lambda val, p=person: p.update({"name": val}))
        v_info.addWidget(txt_name)

        # Stats
        appearances = person.get("appearances", [])
        total_scenes = len(appearances)
        lbl_stats = QLabel(f"🎬 បង្ហាញខ្លួន {total_scenes} ប្លង់ ({total_scenes} scenes)")
        lbl_stats.setStyleSheet("color: #94a3b8; font-size: 10px;")
        v_info.addWidget(lbl_stats)

        row_top.addLayout(v_info, 1)
        c_layout.addLayout(row_top)

        # Timestamps Chips Row (First 4 key moments + jump)
        if appearances:
            row_times = QHBoxLayout()
            row_times.setSpacing(4)
            lbl_t_tag = QLabel("ម៉ោង:")
            lbl_t_tag.setStyleSheet("color: #64748b; font-size: 9px; font-weight: bold;")
            row_times.addWidget(lbl_t_tag)

            sample_apps = appearances[:4]
            for app_item in sample_apps:
                t_sec = float(app_item.get("time", 0.0))
                m = int(t_sec // 60)
                s = int(t_sec % 60)
                t_str = f"{m:02d}:{s:02d}"

                btn_t = QPushButton(t_str)
                btn_t.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_t.setToolTip(f"Jump to {t_str} in video")
                btn_t.setStyleSheet("""
                    QPushButton {
                        background-color: #1e293b;
                        color: #38bdf8;
                        border: 1px solid #334155;
                        border-radius: 4px;
                        padding: 1px 5px;
                        font-size: 9px;
                        font-family: 'Consolas', monospace;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #0284c7;
                        color: #ffffff;
                    }
                """)
                btn_t.clicked.connect(lambda _, ts=t_sec: self._seek_to_time(ts))
                row_times.addWidget(btn_t)

            row_times.addStretch(1)
            c_layout.addLayout(row_times)

        # Action Buttons Row: [ 🎯 Jump First ] [ 🌫️ Blur Face ] [ 💾 Save PNG ]
        row_btns = QHBoxLayout()
        row_btns.setSpacing(4)

        first_t = float(appearances[0].get("time", 0.0)) if appearances else 0.0
        btn_jump = QPushButton("🎯 Jump to Scene")
        btn_jump.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_jump.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #38bdf8;
            }
        """)
        btn_jump.clicked.connect(lambda _, ts=first_t: self._seek_to_time(ts))
        row_btns.addWidget(btn_jump)

        btn_blur = QPushButton("🌫️ Auto-Blur")
        btn_blur.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_blur.setToolTip("Enable real-time face blur for this character")
        btn_blur.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #fbbf24;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #78350f;
                color: #ffffff;
            }
        """)
        btn_blur.clicked.connect(lambda _, ts=first_t: self._blur_person(ts))
        row_btns.addWidget(btn_blur)

        btn_save = QPushButton("💾 Save")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #10b981;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 9px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #065f46;
                color: #ffffff;
            }
        """)
        btn_save.clicked.connect(lambda _, p=person: self._export_single_crop(p))
        row_btns.addWidget(btn_save)

        c_layout.addLayout(row_btns)
        return card

    def _seek_to_time(self, t: float):
        if self.canvas and hasattr(self.canvas, "seek"):
            self.canvas.seek(t)
        p = self.canvas.parent() if self.canvas else None
        while p:
            if hasattr(p, "seek"):
                p.seek(t)
                return
            p = p.parent()

    def _blur_person(self, t: float):
        self._seek_to_time(t)
        self.auto_blur_enabled = True
        if hasattr(self, "chk_auto_blur"):
            self.chk_auto_blur.blockSignals(True)
            self.chk_auto_blur.setChecked(True)
            self.chk_auto_blur.blockSignals(False)
        self.settings_changed.emit()
        self.request_canvas_update.emit()

    def _export_single_crop(self, person: dict):
        thumb_bgr = person.get("thumb_bgr")
        if thumb_bgr is None or thumb_bgr.size == 0:
            return
        name = person.get("name", "person").replace(" ", "_").lower()
        fpath, _ = QFileDialog.getSaveFileName(self, "Save Face Crop", f"{name}.png", "Images (*.png *.jpg)")
        if fpath:
            import cv2
            cv2.imwrite(fpath, thumb_bgr)
            QMessageBox.information(self, "Saved", f"បានរក្សាទុករូបភាព Face Crop ជោគជ័យ:\n{fpath}")

    def _export_cast_crops(self):
        if not getattr(self, "_scanned_cast_clusters", []):
            return
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Save All Face Crops")
        if folder:
            import cv2
            count = 0
            for p in self._scanned_cast_clusters:
                thumb = p.get("thumb_bgr")
                if thumb is not None and thumb.size > 0:
                    name = p.get("name", f"person_{p.get('id', 1)}").replace(" ", "_")
                    save_path = os.path.join(folder, f"{name}.png")
                    cv2.imwrite(save_path, thumb)
                    count += 1
            QMessageBox.information(self, "Export Finished", f"បាន Export រូបភាពតួអង្គចំនួន {count} នាក់ ទៅកាន់:\n{folder}")

