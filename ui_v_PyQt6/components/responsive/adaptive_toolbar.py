"""
AdaptiveToolbar: High-Performance Multi-Breakpoint Toolbar
Automatically transitions across 3 display modes:
  1. Wide Width: Full Icons + Text Labels
  2. Medium Width: Icons Only (clean, compact look)
  3. Narrow Width: High-Priority visible + Overflow Popup (...)
"""

from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from ui_v_PyQt6.qt_compat import (
    QFrame, QHBoxLayout, QVBoxLayout, QToolButton, QPushButton, QLabel, 
    QAction, QIcon, QSize, Qt, Signal, QTimer, QSizePolicy, QWidget
)
from ui_v_PyQt6.icons import get_qta_icon
from ui_v_PyQt6.components.responsive.overflow_menu_manager import (
    OverflowMenuManager, OverflowActionItem, Priority
)


class ToolbarDisplayMode(Enum):
    EXPANDED = "expanded"    # Icons + Text Labels
    COMPACT = "compact"      # Icons Only
    OVERFLOW = "overflow"    # Icons Only + Secondary actions moved to (...)


class AdaptiveToolButton(QToolButton):
    """Sleek Dark Studio Tool Button with priority level and adaptive icon/text styling"""
    def __init__(
        self,
        identifier: str,
        text: str,
        icon: Optional[QIcon] = None,
        priority: Priority = Priority.MEDIUM,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.identifier = identifier
        self.full_text = text
        self.priority = priority
        if icon:
            self.setIcon(icon)
        self.setText(text)
        self.setToolTip(text)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QSize(13, 13))
        self.setStyleSheet("""
            QToolButton {
                background-color: #1e2636;
                border: 1px solid #283344;
                border-radius: 4px;
                color: #cbd5e1;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QToolButton:hover {
                background-color: #283548;
                border-color: #38bdf8;
                color: #ffffff;
            }
            QToolButton:pressed {
                background-color: #0284c7;
                color: #ffffff;
            }
            QToolButton:checked {
                background-color: #0369a1;
                border-color: #38bdf8;
                color: #ffffff;
            }
        """)


class AdaptiveToolbar(QFrame):
    """
    Intelligent Adaptive Toolbar that monitors its own geometry and smoothly
    switches between Full Text+Icon, Icon-Only, and Priority Overflow.
    """
    mode_changed = Signal(str)  # emits "expanded", "compact", "overflow"

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
        expanded_breakpoint: int = 580,
        compact_breakpoint: int = 340,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.orientation = orientation
        self.expanded_breakpoint = expanded_breakpoint
        self.compact_breakpoint = compact_breakpoint
        self.current_mode = ToolbarDisplayMode.EXPANDED

        self._buttons: List[AdaptiveToolButton] = []
        self._overflow_mgr = OverflowMenuManager(self)

        # Smooth resize debounce timer (single-shot 20ms) to prevent UI churn during continuous dragging
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._recalculate_layout)

        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            AdaptiveToolbar {
                background-color: #12161f;
                border-bottom: 1px solid #1f2736;
                padding: 2px 4px;
            }
        """)
        if self.orientation == Qt.Orientation.Horizontal:
            self._layout = QHBoxLayout(self)
            self._layout.setContentsMargins(4, 2, 4, 2)
            self._layout.setSpacing(4)
            self.setFixedHeight(34)
        else:
            self._layout = QVBoxLayout(self)
            self._layout.setContentsMargins(2, 4, 2, 4)
            self._layout.setSpacing(4)
            self.setFixedWidth(34)

        # Add overflow button at the end
        self._layout.addWidget(self._overflow_mgr.button)

    def add_tool_button(
        self,
        identifier: str,
        text: str,
        icon_name_or_icon: Any,
        callback: Optional[Callable[[], None]] = None,
        priority: Priority = Priority.MEDIUM,
        tooltip: str = ""
    ) -> AdaptiveToolButton:
        """Adds a button with priority classification"""
        icon = None
        if isinstance(icon_name_or_icon, str):
            icon = get_qta_icon(icon_name_or_icon, color="#38bdf8")
        elif isinstance(icon_name_or_icon, QIcon):
            icon = icon_name_or_icon

        btn = AdaptiveToolButton(identifier, text, icon, priority=priority, parent=self)
        if callback:
            btn.clicked.connect(callback)
        if tooltip:
            btn.setToolTip(tooltip)

        self._buttons.append(btn)
        # Insert before the overflow button
        insert_idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(insert_idx, btn)

        # Register with overflow manager
        item = OverflowActionItem(
            identifier=identifier,
            text=text,
            icon=icon,
            callback=callback,
            priority=priority,
            widget=btn,
            tooltip=tooltip or text
        )
        self._overflow_mgr.register_item(item)

        self.schedule_layout_update()
        return btn

    def add_separator(self):
        """Adds a subtle vertical/horizontal divider"""
        sep = QFrame(self)
        if self.orientation == Qt.Orientation.Horizontal:
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFixedHeight(18)
        else:
            sep.setFrameShape(QFrame.Shape.HLine)
            sep.setFixedWidth(18)
        sep.setStyleSheet("background-color: #283344; max-width: 1px; max-height: 18px;")
        insert_idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(insert_idx, sep)

    def add_stretch(self):
        insert_idx = max(0, self._layout.count() - 1)
        self._layout.insertStretch(insert_idx)

    def schedule_layout_update(self):
        self._debounce_timer.start(16)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.schedule_layout_update()

    def _recalculate_layout(self):
        """Intelligently updates tool button styles and overflow states based on width"""
        w = self.width() if self.orientation == Qt.Orientation.Horizontal else self.height()
        if w <= 0:
            return

        # Determine target mode
        if w >= self.expanded_breakpoint:
            target_mode = ToolbarDisplayMode.EXPANDED
        elif w >= self.compact_breakpoint:
            target_mode = ToolbarDisplayMode.COMPACT
        else:
            target_mode = ToolbarDisplayMode.OVERFLOW

        # Apply button styles and visibility
        if target_mode == ToolbarDisplayMode.EXPANDED:
            for btn in self._buttons:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                self._overflow_mgr.set_item_overflowed(btn.identifier, False)
        elif target_mode == ToolbarDisplayMode.COMPACT:
            for btn in self._buttons:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                self._overflow_mgr.set_item_overflowed(btn.identifier, False)
        else:
            # OVERFLOW Mode: Show High priority buttons only, move Medium and Low to overflow
            for btn in self._buttons:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                if btn.priority == Priority.HIGH:
                    self._overflow_mgr.set_item_overflowed(btn.identifier, False)
                else:
                    self._overflow_mgr.set_item_overflowed(btn.identifier, True)

        if target_mode != self.current_mode:
            self.current_mode = target_mode
            self.mode_changed.emit(target_mode.value)
