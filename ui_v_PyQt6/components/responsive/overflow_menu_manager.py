"""
OverflowMenuManager: Professional Overflow Handler for Adaptive Toolbars
Maintains high-priority actions on toolbars while gracefully moving secondary actions
into a sleek popup menu (...) when space is constrained.
"""

from enum import IntEnum
from typing import List, Dict, Any, Optional, Callable
from ui_v_PyQt6.qt_compat import (
    QObject, QWidget, QMenu, QAction, QPushButton, QIcon, QSize, Qt, Signal
)
from ui_v_PyQt6.icons import get_qta_icon


class Priority(IntEnum):
    HIGH = 3    # Always stay visible as long as possible
    MEDIUM = 2  # Visible in medium/normal views, collapses to overflow in compact
    LOW = 1     # Moves to overflow first when space is constrained


class OverflowActionItem:
    """Represents a single registered action item with priority and metadata"""
    def __init__(
        self,
        identifier: str,
        text: str,
        icon: Optional[QIcon] = None,
        callback: Optional[Callable[[], None]] = None,
        priority: Priority = Priority.MEDIUM,
        action: Optional[QAction] = None,
        widget: Optional[QWidget] = None,
        tooltip: str = ""
    ):
        self.identifier = identifier
        self.text = text
        self.icon = icon
        self.callback = callback
        self.priority = priority
        self.action = action
        self.widget = widget
        self.tooltip = tooltip
        self.is_overflowed = False


class OverflowMenuManager(QObject):
    """
    Manages overflow actions and renders a modern dark studio popup menu
    when secondary buttons cannot fit on a toolbar.
    """
    overflow_changed = Signal(int)  # emits number of hidden actions

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[OverflowActionItem] = []
        self._overflow_btn = QPushButton("...")
        self._overflow_menu = QMenu(parent)
        self._setup_overflow_button()

    def _setup_overflow_button(self):
        self._overflow_btn.setFixedSize(26, 26)
        self._overflow_btn.setToolTip("More actions / មុខងារបន្ថែម (...)")
        self._overflow_btn.setIcon(get_qta_icon("fa5s.ellipsis-h", color="#94a3b8"))
        self._overflow_btn.setIconSize(QSize(12, 12))
        self._overflow_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2636;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #cbd5e1;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #2e3a50;
                border-color: #38bdf8;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #0284c7;
            }
        """)
        self._overflow_btn.clicked.connect(self._show_overflow_menu)
        self._overflow_btn.hide()

        self._overflow_menu.setStyleSheet("""
            QMenu {
                background-color: #161b26;
                border: 1px solid #283344;
                border-radius: 6px;
                padding: 4px;
                color: #e2e8f0;
                font-size: 11px;
            }
            QMenu::item {
                padding: 6px 20px 6px 10px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #0284c7;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #283344;
                margin: 4px 6px;
            }
        """)

    @property
    def button(self) -> QPushButton:
        return self._overflow_btn

    def register_item(self, item: OverflowActionItem):
        self._items.append(item)

    def set_item_overflowed(self, identifier: str, overflowed: bool):
        for it in self._items:
            if it.identifier == identifier:
                it.is_overflowed = overflowed
                if it.widget:
                    it.widget.setVisible(not overflowed)
                break
        self._update_button_visibility()

    def _update_button_visibility(self):
        overflowed_count = sum(1 for it in self._items if it.is_overflowed)
        self._overflow_btn.setVisible(overflowed_count > 0)
        self.overflow_changed.emit(overflowed_count)

    def _show_overflow_menu(self):
        self._overflow_menu.clear()
        overflowed_items = [it for it in self._items if it.is_overflowed]
        if not overflowed_items:
            return

        for it in overflowed_items:
            if it.action:
                self._overflow_menu.addAction(it.action)
            else:
                act = self._overflow_menu.addAction(it.text)
                if it.icon:
                    act.setIcon(it.icon)
                if it.tooltip:
                    act.setToolTip(it.tooltip)
                if it.callback:
                    act.triggered.connect(it.callback)

        self._overflow_menu.exec(self._overflow_btn.mapToGlobal(self._overflow_btn.rect().bottomLeft()))
