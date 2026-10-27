"""
Frosted Glass, Blur Intensity, Opacity, and Corner Radius Customizer Dialog
Allows interactive, live styling of blur/censor boxes with studio aesthetics.
"""

from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QColor, QFrame, QColorDialog, Qt, QGroupBox
)


class BlurBoxStyleDialog(QDialog):
    def __init__(self, item, canvas, parent=None):
        super().__init__(parent)
        self.item = item
        self.canvas = canvas
        self.setWindowTitle("🎨 Blur & Frosted Glass Style Customizer")
        self.setFixedSize(420, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #1e293b;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                color: #38bdf8;
                font-size: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #0284c7;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }
            QPushButton {
                background-color: #1e293b;
                color: #f1f5f9;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
            }
            QPushButton:checked {
                background-color: #0369a1;
                border: 1px solid #38bdf8;
                color: #ffffff;
            }
        """)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 14, 16, 14)

        # 1. Preset Styles
        grp_style = QGroupBox("✨ Style Mode")
        l_style = QHBoxLayout(grp_style)
        l_style.setSpacing(6)

        self.btn_glass = QPushButton("✨ Glass")
        self.btn_glass.setCheckable(True)
        self.btn_glass.setToolTip("Modern Frosted Glassmorphism with specular shimmer")
        self.btn_glass.clicked.connect(lambda: self._set_mode("glass"))

        self.btn_blur = QPushButton("🌫️ Smooth Blur")
        self.btn_blur.setCheckable(True)
        self.btn_blur.setToolTip("Gaussian smooth blur privacy shield")
        self.btn_blur.clicked.connect(lambda: self._set_mode("blur"))

        self.btn_mosaic = QPushButton("🔲 Mosaic")
        self.btn_mosaic.setCheckable(True)
        self.btn_mosaic.setToolTip("Pixelated mosaic censor")
        self.btn_mosaic.clicked.connect(lambda: self._set_mode("mosaic"))

        self.btn_blackout = QPushButton("⬛ Blackout")
        self.btn_blackout.setCheckable(True)
        self.btn_blackout.setToolTip("Solid or tinted blackout bar")
        self.btn_blackout.clicked.connect(lambda: self._set_mode("blackout"))

        l_style.addWidget(self.btn_glass)
        l_style.addWidget(self.btn_blur)
        l_style.addWidget(self.btn_mosaic)
        l_style.addWidget(self.btn_blackout)
        layout.addWidget(grp_style)

        # 2. Sliders Group (Blur, Opacity, Rounded Corners)
        grp_sliders = QGroupBox("🎛️ Adjustments")
        l_sliders = QVBoxLayout(grp_sliders)
        l_sliders.setSpacing(10)

        # (a) Opacity Slider
        r_op = QHBoxLayout()
        r_op.addWidget(QLabel("💧 Opacity (កម្រិតថ្លា/ស្រអាប់):"))
        self.lbl_op_val = QLabel(f"{int(self.item.opacity * 100)}%")
        self.lbl_op_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        r_op.addStretch()
        r_op.addWidget(self.lbl_op_val)
        l_sliders.addLayout(r_op)

        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(10, 100)
        self.slider_op.setValue(int(self.item.opacity * 100))
        self.slider_op.valueChanged.connect(self._on_opacity_changed)
        l_sliders.addWidget(self.slider_op)

        # (b) Blur Intensity Slider
        r_blur = QHBoxLayout()
        r_blur.addWidget(QLabel("🌫️ Blur Intensity (កម្រិតព្រិល):"))
        self.lbl_blur_val = QLabel(f"{getattr(self.item, 'blur_strength', 30)}%")
        self.lbl_blur_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        r_blur.addStretch()
        r_blur.addWidget(self.lbl_blur_val)
        l_sliders.addLayout(r_blur)

        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setRange(5, 100)
        self.slider_blur.setValue(getattr(self.item, "blur_strength", 30))
        self.slider_blur.valueChanged.connect(self._on_blur_changed)
        l_sliders.addWidget(self.slider_blur)

        # (c) Corner Radius Slider
        r_rad = QHBoxLayout()
        r_rad.addWidget(QLabel("🔲 Corner Radius (ជ្រុងមូល):"))
        self.lbl_rad_val = QLabel(f"{getattr(self.item, 'corner_radius', 0)}px")
        self.lbl_rad_val.setStyleSheet("color: #38bdf8; font-weight: bold;")
        r_rad.addStretch()
        r_rad.addWidget(self.lbl_rad_val)
        l_sliders.addLayout(r_rad)

        self.slider_rad = QSlider(Qt.Orientation.Horizontal)
        self.slider_rad.setRange(0, 40)
        self.slider_rad.setValue(getattr(self.item, "corner_radius", 0))
        self.slider_rad.valueChanged.connect(self._on_radius_changed)
        l_sliders.addWidget(self.slider_rad)

        layout.addWidget(grp_sliders)

        # 3. Tint Colors
        grp_tint = QGroupBox("🎨 Glass Tint Color")
        l_tint = QHBoxLayout(grp_tint)
        l_tint.setSpacing(6)

        colors = [
            ("Frost White", "#ffffff"),
            ("Dark Navy", "#0f172a"),
            ("Pure Black", "#000000"),
            ("Cyan Glow", "#06b6d4"),
            ("Amber Gold", "#f59e0b")
        ]
        for name, col_hex in colors:
            btn_col = QPushButton(name)
            btn_col.setStyleSheet(f"""
                QPushButton {{
                    background-color: {col_hex};
                    color: {'#000000' if col_hex in ('#ffffff', '#06b6d4', '#f59e0b') else '#ffffff'};
                    border: 1px solid #475569;
                    font-size: 10px;
                    padding: 4px 6px;
                }}
                QPushButton:hover {{
                    border: 2px solid #38bdf8;
                }}
            """)
            btn_col.clicked.connect(lambda checked=False, c=col_hex: self._set_tint(c))
            l_tint.addWidget(btn_col)

        btn_custom_col = QPushButton("🎨 More...")
        btn_custom_col.clicked.connect(self._pick_custom_color)
        l_tint.addWidget(btn_custom_col)

        layout.addWidget(grp_tint)

        # 4. Done Button
        btn_done = QPushButton("✅ Done (រួចរាល់)")
        btn_done.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                font-size: 13px;
                padding: 8px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #0284c7;
                border: 1px solid #38bdf8;
            }
        """)
        btn_done.clicked.connect(self.accept)
        layout.addWidget(btn_done)

        self._update_button_states()

    def _update_button_states(self):
        curr_mode = getattr(self.item, "blur_mode", "blur")
        self.btn_glass.setChecked(curr_mode == "glass")
        self.btn_blur.setChecked(curr_mode == "blur")
        self.btn_mosaic.setChecked(curr_mode == "mosaic")
        self.btn_blackout.setChecked(curr_mode == "blackout")

    def _set_mode(self, mode: str):
        self.item.blur_mode = mode
        if mode == "glass":
            self.item.name = "Frosted Glass Box"
            if getattr(self.item, "corner_radius", 0) == 0:
                self.item.corner_radius = 12
                self.slider_rad.setValue(12)
        elif mode == "mosaic":
            self.item.name = "Mosaic Censor Box"
        elif mode == "blackout":
            self.item.name = "Blackout Bar"
        else:
            self.item.name = "Blur Censor Box"
        self._update_button_states()
        self._notify_change()

    def _on_opacity_changed(self, val: int):
        self.item.opacity = round(val / 100.0, 2)
        self.lbl_op_val.setText(f"{val}%")
        self._notify_change()

    def _on_blur_changed(self, val: int):
        self.item.blur_strength = val
        self.lbl_blur_val.setText(f"{val}%")
        self._notify_change()

    def _on_radius_changed(self, val: int):
        self.item.corner_radius = val
        self.lbl_rad_val.setText(f"{val}px")
        self._notify_change()

    def _set_tint(self, hex_color: str):
        self.item.glass_tint_color = QColor(hex_color)
        self._notify_change()

    def _pick_custom_color(self):
        init_col = getattr(self.item, "glass_tint_color", QColor(15, 23, 42))
        col = QColorDialog.getColor(init_col, self, "Pick Glass Tint Color")
        if col.isValid():
            self.item.glass_tint_color = col
            self._notify_change()

    def _notify_change(self):
        if self.canvas:
            self.canvas.canvas_modified.emit()
            self.canvas.update()
