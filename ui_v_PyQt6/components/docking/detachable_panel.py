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
    Qt, QPoint, QCursor, QApplication, QMenu, QAction, QTabWidget, QSize
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

        # 3. Swap Panel Layout Button
        self.btn_swap = QPushButton()
        self.btn_swap.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_swap.setFixedSize(22, 22)
        if get_qta_icon:
            self.btn_swap.setIcon(get_qta_icon("fa5s.exchange-alt", color="#38bdf8"))
        self.btn_swap.setToolTip("ប្តូរទីតាំង Panel (Swap Layout with other panels)")
        self.btn_swap.clicked.connect(self._open_swap_menu)
        layout.addWidget(self.btn_swap)

        # 4. Multi-Monitor Button (If > 1 monitor)
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

        # 5. Float / Dock button
        self.btn_float = QPushButton()
        self.btn_float.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_float.setFixedSize(22, 22)
        self._update_float_btn(False)
        self.btn_float.clicked.connect(self.wrapper.toggle_floating)
        layout.addWidget(self.btn_float)

        self._drag_start_pos = None

    def _open_swap_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #171a22;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
                border-radius: 4px;
                font-size: 11px;
                font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #232b38;
                margin: 4px 6px;
            }
        """)

        my_key = getattr(self.wrapper, "panel_key", "")
        cb = getattr(self.wrapper, "swap_callback", None)

        targets = [
            ("monitor", "🎬 Video Preview Monitor"),
            ("timeline", "⏱️ Multi-Track Timeline"),
            ("subtitles", "📝 Subtitles Dialogue Table"),
            ("inspector", "🛠️ Inspector (Mixer & Properties)"),
            ("logs", "📋 Diagnostic Logs"),
        ]

        has_items = False
        for t_key, t_title in targets:
            if t_key != my_key and cb:
                act = menu.addAction(f"⇄ ប្តូរទីតាំងជាមួយ {t_title}")
                act.triggered.connect(lambda checked=False, k=t_key: cb(my_key, k))
                has_items = True

        if has_items:
            menu.addSeparator()

        if cb:
            act_pt = menu.addAction("🔄 Swap Preview ⇄ Timeline (1-Click)")
            act_pt.triggered.connect(lambda: cb("monitor", "timeline"))

            act_ps = menu.addAction("🔄 Swap Preview ⇄ Subtitles")
            act_ps.triggered.connect(lambda: cb("monitor", "subtitles"))

            act_flip = menu.addAction("🔄 Flip Horizontal (ឆ្វេង ⇄ ស្តាំ)")
            act_flip.triggered.connect(lambda: cb("__flip__", ""))

            act_pre = menu.addAction("🎬 Premiere Full Bottom Timeline")
            act_pre.triggered.connect(lambda: cb("__premiere_bottom__", ""))

            menu.addSeparator()
            act_reset = menu.addAction("↩️ Reset Default Layout (កំណត់ទីតាំងដើម)")
            act_reset.triggered.connect(lambda: cb("__reset__", ""))

        menu.exec(QCursor.pos())

    def contextMenuEvent(self, event):
        self._open_swap_menu()
        event.accept()

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

    def set_swap_info(self, panel_key: str, swap_callback):
        """Sets the panel key identifier and swap callback for dynamic NLE workspace swapping."""
        self.panel_key = panel_key
        self.swap_callback = swap_callback


class PhotoshopTabWidget(QTabWidget):
    """
    Photoshop / Premiere Pro Style Dockable & Movable Tabbed Workspace:
    - Freely drag tabs to reorder with mouse (setMovable(True))
    - Document mode styling for sleek dark borderless NLE look
    - Double click tab to float into independent window
    - Right-click context menu on tabs: Float Tab, Move Left, Move Right
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setDocumentMode(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        if hasattr(self, "tabBar") and self.tabBar():
            self.tabBar().setMovable(True)
            self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)
            self.tabBar().tabBarDoubleClicked.connect(self._on_tab_double_clicked)

        self.setStyleSheet("""
            QTabWidget::pane {
                border-top: 1px solid #1e2638;
                border-left: 1px solid #1e2638;
                border-right: none;
                border-bottom: none;
                background-color: #12151c;
                margin: 0px;
                padding: 0px;
            }
            QTabBar::tab {
                background-color: #0f1218;
                color: #94a3b8;
                font-size: 11px;
                font-weight: 600;
                padding: 6px 12px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                background-color: #161b25;
                color: #38bdf8;
                font-weight: bold;
                border-bottom: 2px solid #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1a202c;
                color: #f1f5f9;
            }
        """)

    def _on_tab_double_clicked(self, index: int):
        if 0 <= index < self.count():
            self.float_tab(index)

    def _on_tab_context_menu(self, pos: QPoint):
        tab_idx = self.tabBar().tabAt(pos)
        if tab_idx < 0:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #171a22;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)

        title = self.tabText(tab_idx)
        act_float = menu.addAction(f"🪟 Float '{title}' Tab into Window (ទាញចេញជាផ្ទាំងអណ្ដែត)")
        act_float.triggered.connect(lambda: self.float_tab(tab_idx))

        if tab_idx > 0:
            act_left = menu.addAction("◀️ Move Tab Left (រំកិលទៅឆ្វេង)")
            act_left.triggered.connect(lambda: self._move_tab(tab_idx, tab_idx - 1))

        if tab_idx < self.count() - 1:
            act_right = menu.addAction("▶️ Move Tab Right (រំកិលទៅស្តាំ)")
            act_right.triggered.connect(lambda: self._move_tab(tab_idx, tab_idx + 1))

        menu.exec(self.tabBar().mapToGlobal(pos))

    def _move_tab(self, from_idx: int, to_idx: int):
        if 0 <= from_idx < self.count() and 0 <= to_idx < self.count():
            w = self.widget(from_idx)
            text = self.tabText(from_idx)
            icon = self.tabIcon(from_idx)
            self.removeTab(from_idx)
            self.insertTab(to_idx, w, icon, text)
            self.setCurrentIndex(to_idx)

    def float_tab(self, tab_idx: int):
        if tab_idx < 0 or tab_idx >= self.count():
            return
        w = self.widget(tab_idx)
        title = self.tabText(tab_idx)
        icon = self.tabIcon(tab_idx)

        # Create floating window for this tab
        win = QWidget(None, Qt.WindowType.Window)
        win.setWindowTitle(f"{title} - AI Studio Workspace")
        win.setStyleSheet("background-color: #171a21; color: #e2e8f0; font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;")
        win.resize(380, 520)
        v_box = QVBoxLayout(win)
        v_box.setContentsMargins(0, 0, 0, 0)
        v_box.setSpacing(0)

        # Header bar with Dock Back button
        hdr = QFrame()
        hdr.setFixedHeight(28)
        hdr.setStyleSheet("background-color: #141720; border-bottom: 1px solid #283344;")
        h_layout = QHBoxLayout(hdr)
        h_layout.setContentsMargins(8, 0, 8, 0)
        lbl = QLabel(title)
        lbl.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px;")
        btn_dock = QPushButton("📥 Dock Back")
        btn_dock.setStyleSheet("""
            QPushButton {
                background: #1e2430;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 3px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #0284c7;
                color: #ffffff;
            }
        """)
        h_layout.addWidget(lbl)
        h_layout.addStretch()
        h_layout.addWidget(btn_dock)
        v_box.addWidget(hdr)

        self.removeTab(tab_idx)
        v_box.addWidget(w, 1)

        def _dock_back():
            v_box.removeWidget(w)
            win.hide()
            self.insertTab(tab_idx, w, icon, title)
            self.setCurrentWidget(w)

        btn_dock.clicked.connect(_dock_back)
        win.closeEvent = lambda event: (_dock_back(), event.accept())
        win.show()
