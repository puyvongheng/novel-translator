"""
Professional Detachable & Floating Panel Wrapper for NLE Studio
Supports:
- Move cursor (SizeAllCursor / 4-way arrows) on header hover
- Drag-to-float or Double-click or Button to open independent Floating Window
- 1-Click Dock Back from both Floating Window and Main Studio placeholder
- Multi-Monitor Screen 2 support
- State preservation: child widget is never recreated
"""

from ui_v_PyQt6.qt_compat import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    Qt, QPoint, QCursor, QApplication
)
from ui_v_PyQt6.icons import get_qta_icon


class FloatingStudioWindow(QWidget):
    """
    Independent Floating Window for Detached Panels (Second Monitor friendly).
    """
    def __init__(self, wrapper, title: str, icon_name: str = "fa5s.columns", parent=None):
        super().__init__(None, Qt.WindowType.Window)  # Independent top-level window
        self.wrapper = wrapper
        self.setWindowTitle(f"{title} - AI Khmer Movie Studio")
        self.setStyleSheet("""
            QWidget {
                background-color: #171a21;
                color: #e2e8f0;
                font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;
            }
        """)
        if icon_name and get_qta_icon:
            try:
                self.setWindowIcon(get_qta_icon(icon_name, color="#38bdf8"))
            except Exception:
                pass
        
        self.layout_win = QVBoxLayout(self)
        self.layout_win.setContentsMargins(0, 0, 0, 0)
        self.layout_win.setSpacing(0)

    def closeEvent(self, event):
        # When user clicks the 'X' button on the floating window, dock it back!
        if self.wrapper and not getattr(self.wrapper, "_is_docking_back", False):
            self.wrapper.dock_back()
        event.accept()


class StudioPanelHeader(QFrame):
    """
    Header bar on top of each studio panel:
    - Cursor is SizeAllCursor (move cursor) on hover
    - Grip handle ⋮⋮
    - Drag to float / Double click to float
    - Float and Screen 2 buttons
    """
    def __init__(self, wrapper, title: str, icon_name: str = "fa5s.columns", parent=None):
        super().__init__(parent)
        self.wrapper = wrapper
        self.title_text = title
        self.icon_name = icon_name
        self.setFixedHeight(28)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))  # 4-way move cursor on hover!
        self.setStyleSheet("""
            StudioPanelHeader {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1e2430, stop:1 #15181f);
                border-bottom: 1px solid #283344;
                border-top: 1px solid #2c384b;
            }
            StudioPanelHeader:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #252d3d, stop:1 #1a1f29);
                border-bottom: 1px solid #38bdf8;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 4px;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background-color: #2a3445;
            }
            QPushButton:pressed {
                background-color: #1e2532;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(6)

        # 1. Move Grip (⋮⋮)
        self.lbl_grip = QLabel("⋮⋮")
        self.lbl_grip.setStyleSheet("color: #64748b; font-size: 12px; font-weight: bold;")
        self.lbl_grip.setToolTip("ទាញ ឬចុចពីរដងដើម្បីបើក Window ដាច់ដោយឡែក (Drag / Double-Click to Detach)")
        layout.addWidget(self.lbl_grip)

        # 2. Icon + Title
        if icon_name and get_qta_icon:
            try:
                self.lbl_icon = QLabel()
                self.lbl_icon.setPixmap(get_qta_icon(icon_name, color="#38bdf8").pixmap(13, 13))
                layout.addWidget(self.lbl_icon)
            except Exception:
                pass

        self.lbl_title = QLabel(title)
        self.lbl_title.setToolTip("ទាញ ឬចុចពីរដងដើម្បីបើក Window ដាច់ដោយឡែក (Drag / Double-Click to Detach)")
        layout.addWidget(self.lbl_title)

        layout.addStretch()

        # 3. Multi-Monitor Button (If > 1 monitor)
        screens = QApplication.screens()
        if len(screens) > 1:
            self.btn_screen2 = QPushButton()
            self.btn_screen2.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            if get_qta_icon:
                self.btn_screen2.setIcon(get_qta_icon("fa5s.desktop", color="#38bdf8"))
            self.btn_screen2.setFixedSize(22, 22)
            self.btn_screen2.setToolTip("បញ្ជូនទៅ Monitor ទី ២ (Send to Screen 2)")
            self.btn_screen2.clicked.connect(self.wrapper.send_to_screen_2)
            layout.addWidget(self.btn_screen2)

        # 4. Float / Dock button
        self.btn_float = QPushButton()
        self.btn_float.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_float.setFixedSize(22, 22)
        self._update_float_btn(False)
        self.btn_float.clicked.connect(self.wrapper.toggle_floating)
        layout.addWidget(self.btn_float)

        self._drag_start_pos = None

    def _update_float_btn(self, is_floating: bool):
        if get_qta_icon:
            if is_floating:
                self.btn_float.setIcon(get_qta_icon("fa5s.compress-arrows-alt", color="#38bdf8"))
                self.btn_float.setToolTip("ភ្ជាប់ចូលក្នុង Studio វិញ (Dock Back to Studio)")
            else:
                self.btn_float.setIcon(get_qta_icon("fa5s.external-link-alt", color="#94a3b8"))
                self.btn_float.setToolTip("បើក Window ដាច់ដោយឡែក (Float / Detach Window)")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.wrapper.toggle_floating()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_start_pos and not self.wrapper.is_floating:
            diff = event.globalPosition().toPoint() - self._drag_start_pos
            if diff.manhattanLength() > 12:  # Drag threshold exceeded
                self._drag_start_pos = None
                self.wrapper.float_panel()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)


class DetachablePanelWrapper(QFrame):
    """
    Wraps any studio panel (Video Monitor, Subtitles, Timeline, Inspector) with a movable
    header bar and independent floating window support.
    """
    def __init__(self, inner_widget: QWidget, title: str, icon_name: str = "fa5s.columns", parent=None):
        super().__init__(parent)
        self.inner_widget = inner_widget
        self.title_text = title
        self.icon_name = icon_name
        self.is_floating = False
        self._is_docking_back = False
        self.floating_window = None

        self.setStyleSheet("""
            DetachablePanelWrapper {
                border: 1px solid #232b38;
                border-radius: 4px;
                background-color: #171a21;
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Header Bar with SizeAllCursor
        self.header = StudioPanelHeader(self, title, icon_name=icon_name, parent=self)
        self.main_layout.addWidget(self.header)

        # 2. Inner Widget Container
        self.main_layout.addWidget(self.inner_widget, 1)

        # 3. Placeholder when panel is detached
        self.placeholder = QFrame()
        self.placeholder.setStyleSheet("background-color: #12151c; border: 1px dashed #334155; border-radius: 6px; margin: 8px;")
        p_layout = QVBoxLayout(self.placeholder)
        p_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_layout.setSpacing(8)

        lbl_p_info = QLabel(f"🪟 {title}\nកំពុងបើកក្នុង Window ដាច់ដោយឡែក (Floating in Window)")
        lbl_p_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_p_info.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: 600;")
        p_layout.addWidget(lbl_p_info)

        btn_dock_back = QPushButton("📥 ភ្ជាប់ចូលក្នុង Studio វិញ (Dock Back)")
        btn_dock_back.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_dock_back.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                border: 1px solid #38bdf8;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        btn_dock_back.clicked.connect(self.dock_back)
        p_layout.addWidget(btn_dock_back)

        self.placeholder.setVisible(False)
        self.main_layout.addWidget(self.placeholder, 1)

    def toggle_floating(self):
        if self.is_floating:
            self.dock_back()
        else:
            self.float_panel()

    def float_panel(self):
        if self.is_floating:
            if self.floating_window:
                self.floating_window.activateWindow()
                self.floating_window.raise_()
            return

        self.is_floating = True
        self.header._update_float_btn(True)

        # Create floating window if not exists
        if not self.floating_window:
            self.floating_window = FloatingStudioWindow(self, self.title_text, self.icon_name, parent=self.window())

        # Determine geometry from inner widget or current screen
        global_pt = self.mapToGlobal(QPoint(0, 0))
        cur_w = max(450, self.width())
        cur_h = max(320, self.height())
        self.floating_window.setGeometry(global_pt.x() + 20, global_pt.y() + 20, cur_w, cur_h)

        # Reparent inner widget and header into floating window
        self.main_layout.removeWidget(self.inner_widget)
        self.main_layout.removeWidget(self.header)

        self.floating_window.layout_win.addWidget(self.header)
        self.floating_window.layout_win.addWidget(self.inner_widget, 1)

        # Show placeholder in original position
        self.placeholder.setVisible(True)

        self.floating_window.show()
        self.floating_window.activateWindow()
        self.floating_window.raise_()

    def dock_back(self):
        if not self.is_floating:
            return

        self._is_docking_back = True
        self.is_floating = False
        self.header._update_float_btn(False)

        # Hide placeholder
        self.placeholder.setVisible(False)

        # Reparent header and inner widget back to wrapper
        if self.floating_window:
            self.floating_window.layout_win.removeWidget(self.inner_widget)
            self.floating_window.layout_win.removeWidget(self.header)
            self.floating_window.hide()

        self.main_layout.insertWidget(0, self.header)
        self.main_layout.insertWidget(1, self.inner_widget, 1)
        self.inner_widget.setVisible(True)
        self.header.setVisible(True)

        self._is_docking_back = False

    def send_to_screen_2(self):
        screens = QApplication.screens()
        if len(screens) > 1:
            if not self.is_floating:
                self.float_panel()
            screen2 = screens[1]
            geom = screen2.availableGeometry()
            w = int(geom.width() * 0.85)
            h = int(geom.height() * 0.85)
            x = geom.x() + (geom.width() - w) // 2
            y = geom.y() + (geom.height() - h) // 2
            if self.floating_window:
                self.floating_window.setGeometry(x, y, w, h)
                self.floating_window.activateWindow()
                self.floating_window.raise_()
