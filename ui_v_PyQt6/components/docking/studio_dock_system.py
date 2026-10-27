"""
Studio Professional Advanced Docking System (Premiere Pro / DaVinci Resolve Style)
Features:
- Resizable Split Panels: Smooth dividers with zero flicker, live resizing, and safe minimum sizes
- Drag & Drop Docking: Full 4-direction docking (Left, Right, Top, Bottom) + Tabbed docking + Grouped dragging
- Floating Windows + Multi-Monitor: Float any panel, drag to Monitor 2, or 1-click "Send to Screen 2" via QScreen
- QSettings Layout Persistence: Saves & restores floating states, dock positions, and custom workspace layouts
- No Reinitialization: Child widgets, video player engine, and timeline canvas are 100% preserved intact
- Workspaces: Default NLE Editing, Subtitling Focus, Voice Dubbing, Color Grading, Dual Monitor
"""

from typing import Optional, Dict, List
from ui_v_PyQt6.qt_compat import (
    QMainWindow, QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, Qt, QIcon, QSize, QSettings, QApplication,
    QMenu, QAction
)
from ui_v_PyQt6.icons import get_qta_icon


class StudioDockTitleBar(QWidget):
    """
    Sleek Dark NLE Studio Title Bar for QDockWidget.
    Supports Drag to undock, Double-Click to maximize/restore, Float, and Close.
    Includes Multi-Monitor 'Send to Screen 2' and Context Menu.
    """
    def __init__(self, dock: QDockWidget, title: str, icon_name: str = "fa5s.th-large", parent=None):
        super().__init__(parent or dock)
        self.dock = dock
        self.title_text = title
        self.icon_name = icon_name
        self.setFixedHeight(28)
        self.setStyleSheet("""
            StudioDockTitleBar {
                background-color: #141720;
                border-bottom: 1px solid #232b38;
            }
            QLabel {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 700;
                font-family: 'Segoe UI', 'Kantumruy Pro', sans-serif;
            }
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 3px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #242c3b;
            }
            QPushButton:pressed {
                background-color: #1e2430;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(4)

        # 1. Drag Grip Handle
        self.lbl_grip = QLabel("⋮⋮")
        self.lbl_grip.setStyleSheet("color: #64748b; font-size: 11px; font-weight: bold; padding-right: 2px;")
        self.lbl_grip.setToolTip("Drag here to undock or dock to another panel (ទាញដើម្បីផ្លាស់ទី)")
        layout.addWidget(self.lbl_grip)

        # 2. Panel Icon & Title
        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(get_qta_icon(icon_name, color="#38bdf8").pixmap(13, 13))
        layout.addWidget(self.lbl_icon)

        self.lbl_title = QLabel(title)
        layout.addWidget(self.lbl_title)

        layout.addStretch()

        # 3. Multi-Monitor Send to Screen 2 button (Visible if > 1 monitor)
        screens = QApplication.screens()
        if len(screens) > 1:
            self.btn_send_screen = QPushButton()
            self.btn_send_screen.setIcon(get_qta_icon("fa5s.desktop", color="#38bdf8"))
            self.btn_send_screen.setIconSize(QSize(11, 11))
            self.btn_send_screen.setFixedSize(22, 22)
            self.btn_send_screen.setToolTip("Send Panel to Secondary Monitor 2 (បញ្ជូនទៅ Monitor ទី 2)")
            self.btn_send_screen.clicked.connect(self._send_to_screen_2)
            layout.addWidget(self.btn_send_screen)

        # 4. Float / Undock button
        self.btn_float = QPushButton()
        self.btn_float.setIcon(get_qta_icon("fa5s.external-link-alt", color="#94a3b8"))
        self.btn_float.setIconSize(QSize(11, 11))
        self.btn_float.setFixedSize(22, 22)
        self.btn_float.setToolTip("Float / Detach Panel (ទាញចេញជាផ្ទាំងអណ្ដែត)")
        self.btn_float.clicked.connect(self._toggle_float)
        layout.addWidget(self.btn_float)

        # 5. Close / Hide button
        self.btn_close = QPushButton()
        self.btn_close.setIcon(get_qta_icon("fa5s.times", color="#94a3b8"))
        self.btn_close.setIconSize(QSize(11, 11))
        self.btn_close.setFixedSize(22, 22)
        self.btn_close.setToolTip("Hide Panel (លាក់ផ្ទាំង)")
        self.btn_close.clicked.connect(self.dock.close)
        layout.addWidget(self.btn_close)

    def _toggle_float(self):
        is_floating = self.dock.isFloating()
        self.dock.setFloating(not is_floating)
        self._update_float_icon(not is_floating)

    def _update_float_icon(self, is_floating: bool):
        icon_name = "fa5s.compress-arrows-alt" if is_floating else "fa5s.external-link-alt"
        tip = "Dock Back into Studio (ភ្ជាប់ចូលក្នុង Studio វិញ)" if is_floating else "Undock / Float Window (ទាញចេញជាផ្ទាំងអណ្ដែត)"
        self.btn_float.setIcon(get_qta_icon(icon_name, color="#38bdf8" if is_floating else "#94a3b8"))
        self.btn_float.setToolTip(tip)

    def _send_to_screen_2(self):
        screens = QApplication.screens()
        if len(screens) > 1:
            self.dock.setFloating(True)
            screen2 = screens[1]
            geom = screen2.availableGeometry()
            # Position at 80% of screen 2
            w = int(geom.width() * 0.85)
            h = int(geom.height() * 0.85)
            x = geom.x() + (geom.width() - w) // 2
            y = geom.y() + (geom.height() - h) // 2
            self.dock.setGeometry(x, y, w, h)
            self._update_float_icon(True)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_float()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1e2430;
                color: #e2e8f0;
                border: 1px solid #334155;
                padding: 4px;
            }
            QMenu::item {
                padding: 4px 16px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
        """)
        
        act_float = menu.addAction("🪟 Float / Detach Window" if not self.dock.isFloating() else "📥 Dock Back to Studio")
        act_float.triggered.connect(self._toggle_float)

        screens = QApplication.screens()
        if len(screens) > 1:
            act_screen2 = menu.addAction("🖥️ Send to Monitor 2")
            act_screen2.triggered.connect(self._send_to_screen_2)

        menu.addSeparator()
        act_close = menu.addAction("✕ Hide Panel")
        act_close.triggered.connect(self.dock.close)

        menu.exec(event.globalPos())


class StudioDockWidget(QDockWidget):
    """
    High-Performance Dock Widget for AI Studio:
    - Custom Studio Title Bar with Float / Dock Controls
    - Never destroys child widget during undock / dock cycles
    - Clamps to monitor screens on multi-monitor setups
    """
    def __init__(self, title: str, parent=None, icon_name: str = "fa5s.columns"):
        super().__init__(title, parent)
        self.setObjectName(title.replace(" ", "_").lower())
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.custom_title_bar = StudioDockTitleBar(self, title, icon_name=icon_name)
        self.setTitleBarWidget(self.custom_title_bar)
        self.topLevelChanged.connect(self._on_top_level_changed)

    def _on_top_level_changed(self, is_floating: bool):
        self.custom_title_bar._update_float_icon(is_floating)
        if is_floating:
            # Multi-Monitor DPI & screen boundary safe clamp
            screen = self.screen() or QApplication.primaryScreen()
            if screen:
                geom = screen.availableGeometry()
                cur_pos = self.pos()
                if not geom.contains(cur_pos):
                    self.move(geom.center() - self.rect().center())
        # Notify child responsive panel of state change
        child = self.widget()
        if child and hasattr(child, "on_docked_state_changed"):
            try:
                child.on_docked_state_changed(is_floating)
            except Exception:
                pass


class StudioDockContainer(QMainWindow):
    """
    Central Workspace Dock Container (Premiere Pro / DaVinci Resolve Style).
    Manages all studio docks with live resizing, drag preview highlights, and workspace presets.
    Features:
    - Nested Docks, Tabbed Docks, Grouped Dragging, Animated Docks
    - Multi-Monitor management via QScreen
    - Workspace presets with QSettings layout state persistence
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks |
            QMainWindow.DockOption.AllowNestedDocks |
            QMainWindow.DockOption.AllowTabbedDocks |
            QMainWindow.DockOption.GroupedDragging
        )

        # Sleek dark NLE styling for dock dividers, tabs, and rubberband drop indicators
        self.setStyleSheet("""
            QMainWindow {
                background-color: #171a21;
            }
            QMainWindow::separator {
                background-color: #1e2430;
                width: 4px;
                height: 4px;
            }
            QMainWindow::separator:hover {
                background-color: #38bdf8;
            }
            QDockWidget {
                border: 1px solid #232b38;
                background-color: #1a1e27;
                titlebar-close-icon: url(none);
                titlebar-normal-icon: url(none);
            }
            QTabBar::tab {
                background-color: #141720;
                color: #94a3b8;
                padding: 5px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 11px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #1e2532;
                color: #38bdf8;
                border-bottom: 2px solid #38bdf8;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1a202c;
                color: #e2e8f0;
            }
            QRubberBand {
                background: rgba(56, 189, 248, 45);
                border: 2px solid #38bdf8;
                border-radius: 4px;
            }
        """)

        # Invisible zero-sized central placeholder so docks fill 100% of the screen
        central = QWidget()
        central.setMaximumSize(0, 0)
        central.setStyleSheet("background: transparent;")
        self.setCentralWidget(central)

        self.docks: Dict[str, StudioDockWidget] = {}

    def add_studio_dock(self, key: str, title: str, widget: QWidget, area: Qt.DockWidgetArea, icon_name: str = "fa5s.columns") -> StudioDockWidget:
        """Registers a child widget inside a managed studio dock."""
        dock = StudioDockWidget(title, self, icon_name=icon_name)
        dock.setObjectName(f"dock_{key}")
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.docks[key] = dock
        return dock

    def toggle_panel(self, key: str) -> bool:
        """Toggles visibility of a specific dock panel by key."""
        if key in self.docks:
            dock = self.docks[key]
            new_vis = dock.isHidden()
            dock.setVisible(new_vis)
            return new_vis
        return False

    def is_panel_visible(self, key: str) -> bool:
        """Returns True if panel is visible and not hidden."""
        if key in self.docks:
            return not self.docks[key].isHidden()
        return False

    def float_panel_to_screen(self, key: str, screen_idx: int = 1):
        """Floats a panel and moves it to the target screen."""
        if key in self.docks:
            dock = self.docks[key]
            dock.setFloating(True)
            screens = QApplication.screens()
            if 0 <= screen_idx < len(screens):
                screen = screens[screen_idx]
                geom = screen.availableGeometry()
                w = int(geom.width() * 0.85)
                h = int(geom.height() * 0.85)
                x = geom.x() + (geom.width() - w) // 2
                y = geom.y() + (geom.height() - h) // 2
                dock.setGeometry(x, y, w, h)

    def dock_all_floating(self):
        """Restores all floating panels back into docked mode."""
        for dock in self.docks.values():
            if dock.isFloating():
                dock.setFloating(False)

    # ------------------ WORKSPACE PRESETS ------------------
    def apply_default_layout(self):
        """
        Standard Pro Editing Layout (Premiere Pro / DaVinci Resolve):
        - Media & AI Tools (Far Left, 240px)
        - Video Preview Monitor (Center-Left)
        - Subtitles Virtual Table (Center-Right)
        - Multi-Track Timeline (Bottom Full-Width)
        - Diagnostic Logs (Bottom Tabbed with Timeline)
        - Dual-Tab Inspector (Far Right Column)
        """
        self.dock_all_floating()

        if "media" in self.docks:
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.docks["media"])
            self.docks["media"].show()

        if "monitor" in self.docks:
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.docks["monitor"])
            self.docks["monitor"].show()

        if "subtitles" in self.docks:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.docks["subtitles"])
            self.docks["subtitles"].show()

        if "inspector" in self.docks:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.docks["inspector"])
            self.docks["inspector"].show()

        if "timeline" in self.docks:
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.docks["timeline"])
            self.docks["timeline"].show()

        if "logs" in self.docks:
            self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.docks["logs"])
            if "timeline" in self.docks:
                self.tabifyDockWidget(self.docks["timeline"], self.docks["logs"])
            self.docks["logs"].show()

    def apply_subtitling_layout(self):
        """Focuses on Subtitles and Video Monitor side-by-side with maximum height."""
        self.apply_default_layout()
        if "timeline" in self.docks:
            self.docks["timeline"].hide()
        if "logs" in self.docks:
            self.docks["logs"].hide()

    def apply_dubbing_layout(self):
        """Voice Dubbing layout: Monitor, Timeline, and Inspector Dubbing Mixer focused."""
        self.apply_default_layout()
        if "media" in self.docks:
            self.docks["media"].hide()
        if "timeline" in self.docks:
            self.docks["timeline"].show()
        if "inspector" in self.docks:
            self.docks["inspector"].show()

    def apply_color_grading_layout(self):
        """Color Grading layout: Maximized Video Preview Monitor & Object Properties LUTs."""
        self.apply_default_layout()
        if "subtitles" in self.docks:
            self.docks["subtitles"].hide()
        if "timeline" in self.docks:
            self.docks["timeline"].hide()
        if "logs" in self.docks:
            self.docks["logs"].hide()

    def apply_dual_monitor_layout(self):
        """
        Multi-Monitor Pro Layout:
        - Floats the Video Preview Monitor onto Screen 2 (if available).
        - Expands Timeline, Subtitles, and Inspector across Screen 1.
        """
        self.apply_default_layout()
        self.float_panel_to_screen("monitor", screen_idx=1)

    def reset_to_default_layout(self):
        """Resets all panels to factory default NLE editing layout."""
        self.dock_all_floating()
        self.apply_default_layout()

    # ------------------ QSETTINGS PERSISTENCE ------------------
    def save_layout_state(self, key: str = "studio_dock_workspace"):
        """Saves exact positions, floating states, geometry, and tabs to QSettings."""
        try:
            settings = QSettings("koyStudio", "AIKhmerMovieStudio")
            settings.setValue(f"{key}_state", self.saveState())
            settings.setValue(f"{key}_geom", self.saveGeometry())
        except Exception:
            pass

    def restore_layout_state(self, key: str = "studio_dock_workspace") -> bool:
        """Restores dock positions and floating states from previous session."""
        try:
            settings = QSettings("koyStudio", "AIKhmerMovieStudio")
            state = settings.value(f"{key}_state")
            geom = settings.value(f"{key}_geom")
            if geom:
                self.restoreGeometry(geom)
            if state:
                return self.restoreState(state)
        except Exception:
            pass
        return False
