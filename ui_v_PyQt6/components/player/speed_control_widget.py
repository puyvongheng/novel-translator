"""
Modern Video Speed Controller & Popup Dialog for Video Editor & Player
Matches mobile/desktop YouTube & Pro Video Editor speed control panel:
- Large dynamic speed readout (e.g. 1.5x)
- Round [-] step down and [+] step up buttons
- Smooth horizontal slider with white circular thumb
- Preset pill buttons: 0.5x, 1x (Normal), 1.25x, 1.5x, 1.75x, 2x
"""

from ui_v_PyQt6.qt_compat import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, Qt, Signal, QFrame, QPoint, QCursor
)


class ModernSpeedControlWidget(QFrame):
    """
    Card-style Video Playback & Export Speed Control Widget.
    Emits speed_changed(float) whenever the value changes.
    """
    speed_changed = Signal(float)

    PRESETS = [0.5, 1.0, 1.25, 1.5, 1.75, 2.0]

    def __init__(self, current_speed: float = 1.0, parent=None, show_handle: bool = True):
        super().__init__(parent)
        self._speed = max(0.25, min(3.0, float(current_speed)))
        self._show_handle = show_handle
        self._preset_buttons = {}
        self._init_ui()
        self.set_speed(self._speed, emit=False)

    def _init_ui(self):
        self.setObjectName("ModernSpeedControlWidget")
        self.setStyleSheet("""
            QFrame#ModernSpeedControlWidget {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 16px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 18)
        layout.setSpacing(14)

        # 1. Top Drag Handle
        if self._show_handle:
            h_row = QHBoxLayout()
            h_row.addStretch()
            handle = QFrame()
            handle.setFixedSize(38, 4)
            handle.setStyleSheet("background-color: #52525b; border-radius: 2px;")
            h_row.addWidget(handle)
            h_row.addStretch()
            layout.addLayout(h_row)

        # 2. Large Speed Value Readout (e.g. "1.5x")
        self.lbl_value = QLabel(f"{self._speed:.1f}x")
        self.lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_value.setStyleSheet("""
            QLabel {
                background: transparent;
                color: #ffffff;
                font-size: 26px;
                font-weight: 800;
                letter-spacing: 0.5px;
                margin-top: 2px;
                margin-bottom: 2px;
            }
        """)
        layout.addWidget(self.lbl_value)

        # 3. Step [-] | Slider | Step [+] Row
        row_slider = QHBoxLayout()
        row_slider.setSpacing(12)

        # [-] Button
        self.btn_minus = QPushButton("−")
        self.btn_minus.setFixedSize(38, 38)
        self.btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minus.setToolTip("បន្ថយល្បឿន (-0.05x)")
        self.btn_minus.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border: none;
                border-radius: 19px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
            QPushButton:pressed {
                background-color: #18181b;
            }
        """)
        self.btn_minus.clicked.connect(self._on_minus_clicked)
        row_slider.addWidget(self.btn_minus)

        # Horizontal Slider
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(25, 200)  # 0.25x to 2.00x in increments of 0.01x
        self.slider.setValue(int(round(self._speed * 100)))
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slider.setStyleSheet("""
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #3f3f46;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #e4e4e7;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: none;
                width: 22px;
                height: 22px;
                margin: -9px 0;
                border-radius: 11px;
            }
            QSlider::handle:horizontal:hover {
                background: #f4f4f5;
            }
        """)
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        row_slider.addWidget(self.slider, 1)

        # [+] Button
        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(38, 38)
        self.btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_plus.setToolTip("បង្កើនល្បឿន (+0.05x)")
        self.btn_plus.setStyleSheet("""
            QPushButton {
                background-color: #27272a;
                color: #ffffff;
                font-size: 20px;
                font-weight: bold;
                border: none;
                border-radius: 19px;
            }
            QPushButton:hover {
                background-color: #3f3f46;
            }
            QPushButton:pressed {
                background-color: #18181b;
            }
        """)
        self.btn_plus.clicked.connect(self._on_plus_clicked)
        row_slider.addWidget(self.btn_plus)

        layout.addLayout(row_slider)

        # 4. Preset Pills Row (0.5x, 1x Normal, 1.25x, 1.5x, 1.75x, 2x)
        pills_layout = QHBoxLayout()
        pills_layout.setSpacing(8)

        for p in self.PRESETS:
            pill_col = QVBoxLayout()
            pill_col.setSpacing(2)
            pill_col.setContentsMargins(0, 0, 0, 0)

            label_text = f"{p}x" if p != 1.0 else "1x"
            btn_pill = QPushButton(label_text)
            btn_pill.setFixedHeight(34)
            btn_pill.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_pill.clicked.connect(lambda _, val=p: self.set_speed(val, emit=True))
            pill_col.addWidget(btn_pill)

            if abs(p - 1.0) < 0.01:
                lbl_normal = QLabel("Normal")
                lbl_normal.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_normal.setStyleSheet("background: transparent; color: #71717a; font-size: 10px; font-weight: 500;")
                pill_col.addWidget(lbl_normal)
            else:
                lbl_placeholder = QLabel("")
                lbl_placeholder.setFixedHeight(12)
                lbl_placeholder.setStyleSheet("background: transparent;")
                pill_col.addWidget(lbl_placeholder)

            self._preset_buttons[p] = btn_pill
            pills_layout.addLayout(pill_col)

        layout.addLayout(pills_layout)
        self._update_ui_state()

    def _format_speed_str(self, val: float) -> str:
        if abs(val - round(val)) < 0.01:
            return f"{int(round(val))}x"
        elif abs(val * 10 - round(val * 10)) < 0.01:
            return f"{val:.1f}x"
        else:
            return f"{val:.2f}x"

    def _on_slider_value_changed(self, val: int):
        new_speed = round(val / 100.0, 2)
        if abs(new_speed - self._speed) >= 0.01:
            self._speed = new_speed
            self._update_ui_state()
            self.speed_changed.emit(self._speed)

    def _on_minus_clicked(self):
        new_val = max(0.25, round(self._speed - 0.05, 2))
        self.set_speed(new_val, emit=True)

    def _on_plus_clicked(self):
        new_val = min(3.0, round(self._speed + 0.05, 2))
        self.set_speed(new_val, emit=True)

    def set_speed(self, speed: float, emit: bool = True):
        speed = max(0.25, min(3.0, round(float(speed), 2)))
        self._speed = speed

        self.slider.blockSignals(True)
        self.slider.setValue(int(round(speed * 100)))
        self.slider.blockSignals(False)

        self._update_ui_state()
        if emit:
            self.speed_changed.emit(self._speed)

    def get_speed(self) -> float:
        return self._speed

    def _update_ui_state(self):
        self.lbl_value.setText(self._format_speed_str(self._speed))

        # Update preset pill styles
        for p, btn in self._preset_buttons.items():
            is_active = abs(self._speed - p) < 0.02
            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        color: #09090b;
                        font-size: 13px;
                        font-weight: 700;
                        border: none;
                        border-radius: 17px;
                        padding: 4px 10px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #27272a;
                        color: #e4e4e7;
                        font-size: 13px;
                        font-weight: 600;
                        border: none;
                        border-radius: 17px;
                        padding: 4px 10px;
                    }
                    QPushButton:hover {
                        background-color: #3f3f46;
                        color: #ffffff;
                    }
                """)


class ModernSpeedDialog(QDialog):
    """
    Floating Modal/Popup Speed Control Dialog matching the requested design.
    """
    speed_changed = Signal(float)

    def __init__(self, current_speed: float = 1.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Speed (ល្បឿនវីដេអូ)")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(380)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        self.widget = ModernSpeedControlWidget(current_speed=current_speed, parent=self, show_handle=True)
        self.widget.speed_changed.connect(self._on_speed_changed)
        main_layout.addWidget(self.widget)

    def _on_speed_changed(self, spd: float):
        self.speed_changed.emit(spd)

    def set_speed(self, speed: float):
        self.widget.set_speed(speed, emit=False)

    def get_speed(self) -> float:
        return self.widget.get_speed()

    def popup_near(self, anchor_widget: QWidget):
        """Displays dialog right above or below the anchor button."""
        if not anchor_widget:
            self.exec()
            return

        pt = anchor_widget.mapToGlobal(QPoint(0, 0))
        x = pt.x() - (self.width() - anchor_widget.width()) // 2
        y = pt.y() - self.height() - 8  # Show above button by default

        # Adjust bounds to screen
        screen = anchor_widget.screen()
        if screen:
            geo = screen.availableGeometry()
            if y < geo.top():
                y = pt.y() + anchor_widget.height() + 8
            x = max(geo.left() + 10, min(x, geo.right() - self.width() - 10))

        self.move(x, y)
        self.exec()
