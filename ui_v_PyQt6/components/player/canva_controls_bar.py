"""
Canva-Style Interactive Toolbar & Real-Time Sharpness / Blur Control Bar
Provides aspect ratio switching, canvas zooming, quick object insertion,
and professional real-time image/video Sharpness and Blur controls.
"""

from ui_v_PyQt6.qt_compat import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSlider,
    QComboBox, QFrame, QFileDialog, Qt, QMenu, QPoint
)
from ui_v_PyQt6.icons import get_qta_icon



class CanvaControlsBar(QFrame):
    """
    Top Floating Designer Bar for Canva Video Preview Editor:
    - Aspect Ratio (16:9, 9:16, 1:1, 4:5, Fit)
    - Canvas Zoom & Fit
    - Real-Time Sharpness (0 to 100) Slider with Reset
    - Real-Time Blur (0 to 100) Slider with Reset
    - Quick Canva Inserts (Text, Image, Shapes)
    - Grid & Snapping toggles
    """
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setStyleSheet("""
            QFrame {
                background-color: #171d26;
                border: 1px solid #28313e;
                border-radius: 6px;
                padding: 2px;
            }
            QLabel {
                color: #94a3b8;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #1e2633;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
            }
            QComboBox {
                background-color: #1e2633;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        # 1. Aspect Ratio Selector
        layout.addWidget(QLabel("Aspect:"))
        self.combo_ratio = QComboBox()
        self.combo_ratio.addItems(["16:9 (Landscape)", "9:16 (TikTok/Reels)", "1:1 (Square)", "4:5 (Instagram)", "Fit Video"])
        self.combo_ratio.currentIndexChanged.connect(self._on_aspect_changed)
        layout.addWidget(self.combo_ratio)

        # 2. Canvas Zoom Selector
        layout.addWidget(QLabel("Zoom:"))
        self.combo_zoom = QComboBox()
        self.combo_zoom.addItems(["Fit to Preview", "50%", "75%", "100%", "125%", "150%"])
        self.combo_zoom.currentIndexChanged.connect(self._on_zoom_changed)
        layout.addWidget(self.combo_zoom)

        # Separator
        layout.addWidget(self._create_separator())

        # 3. Quick Canvas Add Buttons (Canva Style)
        btn_text = QPushButton(" Text")
        btn_text.setIcon(get_qta_icon("fa5s.font", color="#38bdf8"))
        btn_text.clicked.connect(lambda: self.canvas.add_text_item("Heading Title"))
        layout.addWidget(btn_text)

        btn_img = QPushButton(" Media / GIF")
        btn_img.setIcon(get_qta_icon("fa5s.image", color="#10b981"))
        btn_img.clicked.connect(self._browse_image)
        layout.addWidget(btn_img)

        btn_video = QPushButton(" Overlay Video")
        btn_video.setIcon(get_qta_icon("fa5s.video", color="#06b6d4"))
        btn_video.setToolTip("Add Picture-in-Picture (PiP) Video Overlay Clip")
        btn_video.clicked.connect(self._browse_video)
        layout.addWidget(btn_video)

        btn_shape = QPushButton(" Shape")
        btn_shape.setIcon(get_qta_icon("fa5s.shapes", color="#f59e0b"))
        btn_shape.clicked.connect(self._show_shape_menu)
        layout.addWidget(btn_shape)

        # 3b. Cinematic Color Presets & Filter Button (None, Mono, Cinematic, Bright, Film, Night Scene, Past)
        btn_presets = QPushButton(" 🎨 Color Presets")
        btn_presets.setIcon(get_qta_icon("fa5s.magic", color="#f97316"))
        btn_presets.setStyleSheet("background-color: #272f3f; color: #f97316; font-weight: bold; border: 1px solid #f97316;")
        btn_presets.setToolTip("Open Cinematic Color Presets & LUT Filters Gallery")
        btn_presets.clicked.connect(self.canvas.open_color_presets_dialog)
        layout.addWidget(btn_presets)

        # 3c. Show CC in Video Toggle Button (Live Preview & Auto-Burn on Export)
        self.btn_toggle_cc = QPushButton("💬 Show CC")
        self.btn_toggle_cc.setCheckable(True)
        is_cc_on = getattr(self.canvas, "is_subtitle_layer_visible", True)
        self.btn_toggle_cc.setChecked(is_cc_on)
        self.btn_toggle_cc.setToolTip("Show CC in Video (បង្ហាញ CC លើវីដេអូ & Export ជាប់ CC ដូច Crop/Blur/Text)")
        self._update_cc_button_style(is_cc_on)
        self.btn_toggle_cc.toggled.connect(self._on_toggle_cc_clicked)
        if hasattr(self.canvas, "subtitle_visibility_changed"):
            self.canvas.subtitle_visibility_changed.connect(self._sync_cc_button)
        layout.addWidget(self.btn_toggle_cc)

        # Separator
        layout.addWidget(self._create_separator())

        # 4. Real-Time Sharpness Slider (0 to 100)
        layout.addWidget(QLabel("Sharpness:"))
        self.lbl_sharp_val = QLabel("0%")
        self.lbl_sharp_val.setFixedWidth(28)

        self.slider_sharp = QSlider(Qt.Orientation.Horizontal)
        self.slider_sharp.setRange(0, 100)
        self.slider_sharp.setValue(0)
        self.slider_sharp.setFixedWidth(70)
        self.slider_sharp.valueChanged.connect(self._on_sharpness_changed)
        layout.addWidget(self.slider_sharp)
        layout.addWidget(self.lbl_sharp_val)

        # 5. Real-Time Blur Slider (0 to 100)
        layout.addWidget(QLabel("Blur:"))
        self.lbl_blur_val = QLabel("0%")
        self.lbl_blur_val.setFixedWidth(28)

        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setRange(0, 100)
        self.slider_blur.setValue(0)
        self.slider_blur.setFixedWidth(70)
        self.slider_blur.valueChanged.connect(self._on_blur_changed)
        layout.addWidget(self.slider_blur)
        layout.addWidget(self.lbl_blur_val)

        # Reset Effects Button
        btn_reset_fx = QPushButton("↺ Reset")
        btn_reset_fx.setToolTip("Reset Sharpness and Blur to 0")
        btn_reset_fx.clicked.connect(self._on_reset_effects)
        layout.addWidget(btn_reset_fx)

        # Separator
        layout.addWidget(self._create_separator())

        # Quick Video Transform & Pan mode toggle
        self.btn_transform = QPushButton("✥ Transform")
        self.btn_transform.setCheckable(True)
        self.btn_transform.setChecked(getattr(self.canvas, "is_transform_mode", False))
        self.btn_transform.setToolTip("Transform & Pan Mode (ចុចដើម្បីទាញប្លង់វីដេអូ ឆ្វេង-ស្តាំ/លើ-ក្រោម)")
        self.btn_transform.setStyleSheet("""
            QPushButton:checked {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #38bdf8;
                font-weight: bold;
            }
        """)
        self.btn_transform.toggled.connect(lambda c: self.canvas.set_transform_mode(c) if hasattr(self.canvas, "set_transform_mode") else None)
        if hasattr(self.canvas, "transform_mode_changed"):
            self.canvas.transform_mode_changed.connect(self._sync_transform_button)
        layout.addWidget(self.btn_transform)

        # Quick Video Flip & Keyframe tools
        btn_flip_h = QPushButton("↔ Flip H")
        btn_flip_h.setToolTip("Flip Video Horizontally (ឆ្លុះឆ្វេង-ស្តាំ)")
        btn_flip_h.clicked.connect(self.canvas.toggle_flip_horizontal)
        layout.addWidget(btn_flip_h)

        btn_flip_v = QPushButton("↕ Flip V")
        btn_flip_v.setToolTip("Flip Video Vertically (ឆ្លុះលើ-ក្រោម)")
        btn_flip_v.clicked.connect(self.canvas.toggle_flip_vertical)
        layout.addWidget(btn_flip_v)

        btn_rot = QPushButton("🔄 Rotate")
        btn_rot.setToolTip("Rotate Video 90° (បង្វិល 90 ដឺក្រេ)")
        btn_rot.clicked.connect(self.canvas.rotate_video_90)
        layout.addWidget(btn_rot)

        btn_kf = QPushButton("◆+ KF")
        btn_kf.setToolTip("Add Video Keyframe at Current Time (បន្ថែម Keyframe)")
        btn_kf.setStyleSheet("background-color: #0c4a6e; color: #38bdf8; border: 1px solid #0284c7; font-weight: bold;")
        btn_kf.clicked.connect(self.canvas.add_keyframe_at_current_time)
        layout.addWidget(btn_kf)

        # Separator
        layout.addWidget(self._create_separator())

        # 6. Grid & Guide Toggles
        btn_grid = QPushButton("▦ Grid")
        btn_grid.setCheckable(True)
        btn_grid.toggled.connect(lambda: self.canvas.toggle_grid())
        layout.addWidget(btn_grid)

        btn_snap = QPushButton("🧲 Snap")
        btn_snap.setCheckable(True)
        btn_snap.setChecked(True)
        btn_snap.toggled.connect(lambda c: setattr(self.canvas, "enable_snapping", c))
        layout.addWidget(btn_snap)

        btn_guides = QPushButton("📐 Guides ⌵")
        btn_guides.setToolTip("Photoshop Guides & Rulers (បន្ទាត់ខ្នាត)")
        btn_guides.clicked.connect(self._show_guides_menu)
        layout.addWidget(btn_guides)

        layout.addStretch()

    def _create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #28313e; max-width: 1px;")
        return line

    def _on_aspect_changed(self, idx: int):
        mapping = {
            0: "16:9",
            1: "9:16",
            2: "1:1",
            3: "4:5",
            4: "fit"
        }
        self.canvas.set_aspect_ratio(mapping.get(idx, "16:9"))

    def _on_zoom_changed(self, idx: int):
        mapping = {
            0: 1.0,  # Fit
            1: 0.50,
            2: 0.75,
            3: 1.00,
            4: 1.25,
            5: 1.50
        }
        self.canvas.zoom_level = mapping.get(idx, 1.0)
        self.canvas.update()

    def _browse_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Overlay Image / Sticker / GIF", "",
            "Media Files (*.png *.jpg *.jpeg *.webp *.svg *.bmp *.gif)"
        )
        if f:
            self.canvas.add_image_item(f)

    def _browse_video(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Overlay Video Clip (PiP)", "",
            "Video Files (*.mp4 *.mkv *.mov *.avi *.webm *.flv *.ts)"
        )
        if f:
            self.canvas.add_video_item(f)

    def _show_shape_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e2633;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
            }
        """)
        menu.addAction("🟦 Rounded Rectangle").triggered.connect(lambda: self.canvas.add_shape_item("rounded_rect", "#0ea5e9"))
        menu.addAction("⚪ Circle").triggered.connect(lambda: self.canvas.add_shape_item("circle", "#38bdf8"))
        menu.addAction("⭐ 5-Point Star").triggered.connect(lambda: self.canvas.add_shape_item("star", "#f59e0b"))
        menu.addAction("🏷️ Capsule Badge").triggered.connect(lambda: self.canvas.add_shape_item("badge", "#ec4899"))
        menu.exec(self.mapToGlobal(self.sender().pos()))

    def _show_guides_menu(self):
        btn = self.sender()
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e2633;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
            }
        """)
        menu.addAction("New Guide...").triggered.connect(self.canvas.open_new_guide_dialog)
        menu.addAction("New Guide Layout...").triggered.connect(self.canvas.open_new_guide_layout_dialog)
        act_shape = menu.addAction("New Guides From Shape")
        has_sel = len(self.canvas.selected_items) > 0
        act_shape.setEnabled(has_sel)
        if has_sel:
            act_shape.triggered.connect(self.canvas.create_guides_from_selected_shape)

        menu.addSeparator()
        act_lock = menu.addAction("Lock Guides")
        act_lock.setCheckable(True)
        act_lock.setChecked(getattr(self.canvas, "guides_locked", False))
        act_lock.triggered.connect(self.canvas.toggle_lock_guides)

        act_show = menu.addAction("Show Guides (Ctrl+;)")
        act_show.setCheckable(True)
        act_show.setChecked(getattr(self.canvas, "show_guides", True))
        act_show.triggered.connect(self.canvas.toggle_guides)

        menu.addAction("Clear All Guides").triggered.connect(self.canvas.clear_guides)
        menu.exec(btn.mapToGlobal(QPoint(0, btn.height())))


    def _on_sharpness_changed(self, val: int):
        self.lbl_sharp_val.setText(f"{val}%")
        # Apply to selected item if one is selected, else to canvas background
        if self.canvas.selected_items:
            for it in self.canvas.selected_items:
                it.sharpness = val
                it.update_effects()
            self.canvas.update()
        else:
            self.canvas.set_canvas_sharpness(val)

    def _on_blur_changed(self, val: int):
        self.lbl_blur_val.setText(f"{val}%")
        # Apply to selected item if one is selected, else to canvas background
        if self.canvas.selected_items:
            for it in self.canvas.selected_items:
                it.blur = val
                it.update_effects()
            self.canvas.update()
        else:
            self.canvas.set_canvas_blur(val)

    def _on_reset_effects(self):
        self.slider_sharp.setValue(0)
        self.slider_blur.setValue(0)
        self.lbl_sharp_val.setText("0%")
        self.lbl_blur_val.setText("0%")
        self.canvas.reset_effects()

    def _sync_transform_button(self, active: bool):
        if hasattr(self, "btn_transform") and self.btn_transform.isChecked() != active:
            self.btn_transform.blockSignals(True)
            self.btn_transform.setChecked(active)
            self.btn_transform.blockSignals(False)

    def _update_cc_button_style(self, checked: bool):
        if checked:
            self.btn_toggle_cc.setText("💬 Show CC (ON)")
            self.btn_toggle_cc.setStyleSheet("""
                QPushButton {
                    background-color: #064e3b;
                    color: #34d399;
                    border: 1px solid #10b981;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #047857;
                    border-color: #6ee7b7;
                }
            """)
        else:
            self.btn_toggle_cc.setText("💬 Show CC (OFF)")
            self.btn_toggle_cc.setStyleSheet("""
                QPushButton {
                    background-color: #1e2633;
                    color: #94a3b8;
                    border: 1px solid #334155;
                    font-weight: 500;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #273344;
                    color: #cbd5e1;
                }
            """)

    def _on_toggle_cc_clicked(self, checked: bool):
        self._update_cc_button_style(checked)
        if hasattr(self.canvas, "set_subtitle_visibility"):
            self.canvas.set_subtitle_visibility(checked)
        player = getattr(self.canvas, "player", None)
        if player and hasattr(player, "set_subtitle_visibility"):
            player.set_subtitle_visibility(checked)

    def _sync_cc_button(self, visible: bool):
        if hasattr(self, "btn_toggle_cc") and self.btn_toggle_cc.isChecked() != visible:
            self.btn_toggle_cc.blockSignals(True)
            self.btn_toggle_cc.setChecked(visible)
            self._update_cc_button_style(visible)
            self.btn_toggle_cc.blockSignals(False)
