"""
ResponsivePanel: High-Performance Self-Adapting Panel Container
Monitors its own geometry independently of the top-level window, provides smooth
debounced resizing, and fires breakpoint signals for compact, normal, wide, and ultrawide layouts.
"""

from enum import Enum
from typing import Optional
from ui_v_PyQt6.qt_compat import (
    QFrame, QWidget, QVBoxLayout, QSize, Qt, Signal, QTimer, QApplication
)


class ResponsiveBreakpoint(Enum):
    COMPACT = "compact"        # < 380px (narrow sidebar dock)
    NORMAL = "normal"          # 380px - 720px (standard dock panel)
    WIDE = "wide"              # 720px - 1100px (wide panel / expanded view)
    ULTRA_WIDE = "ultra_wide"  # > 1100px (full-screen / secondary monitor)


class ResponsivePanel(QFrame):
    """
    Base class or wrapper container for responsive video editor panels.
    Each panel dynamically adapts to its own allocated width and height.
    """
    breakpoint_changed = Signal(str)  # emits "compact", "normal", "wide", "ultra_wide"
    dimensions_changed = Signal(int, int)  # emits (width, height)

    def __init__(
        self,
        compact_threshold: int = 380,
        normal_threshold: int = 720,
        wide_threshold: int = 1100,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.compact_threshold = compact_threshold
        self.normal_threshold = normal_threshold
        self.wide_threshold = wide_threshold
        self.current_breakpoint = ResponsiveBreakpoint.NORMAL

        # 60fps / 16ms single-shot debouncer to eliminate stutter during active splitter dragging
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._evaluate_responsiveness)

        self.setStyleSheet("""
            ResponsivePanel {
                background-color: #141720;
                border: none;
            }
        """)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start(16)

    def _evaluate_responsiveness(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return

        # Determine breakpoint based on current panel width
        if w < self.compact_threshold:
            new_bp = ResponsiveBreakpoint.COMPACT
        elif w < self.normal_threshold:
            new_bp = ResponsiveBreakpoint.NORMAL
        elif w < self.wide_threshold:
            new_bp = ResponsiveBreakpoint.WIDE
        else:
            new_bp = ResponsiveBreakpoint.ULTRA_WIDE

        if new_bp != self.current_breakpoint:
            self.current_breakpoint = new_bp
            self.breakpoint_changed.emit(new_bp.value)
            self.on_breakpoint_changed(new_bp)

        self.dimensions_changed.emit(w, h)
        self.on_panel_resized(w, h)

    def on_breakpoint_changed(self, breakpoint: ResponsiveBreakpoint):
        """Virtual hook for subclass overrides"""
        pass

    def on_panel_resized(self, width: int, height: int):
        """Virtual hook for subclass overrides"""
        pass

    def is_compact(self) -> bool:
        return self.current_breakpoint == ResponsiveBreakpoint.COMPACT

    def is_normal(self) -> bool:
        return self.current_breakpoint == ResponsiveBreakpoint.NORMAL

    def is_wide(self) -> bool:
        return self.current_breakpoint in (ResponsiveBreakpoint.WIDE, ResponsiveBreakpoint.ULTRA_WIDE)

    def get_dpi_scale_factor(self) -> float:
        """Returns the DPI device pixel ratio for multi-monitor scaling"""
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            return float(screen.devicePixelRatio())
        return 1.0
