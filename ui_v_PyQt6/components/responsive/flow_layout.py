"""
FlowLayout: Pure Qt-Compliant Dynamic Wrapping Layout
Automatically arranges child widgets horizontally and wraps them into subsequent rows
when the available container width shrinks, preventing clipping and broken layouts.
"""

from typing import List, Optional
from ui_v_PyQt6.qt_compat import (
    QLayout, QLayoutItem, QWidget, QRect, QSize, QPoint, Qt, QSizePolicy
)


class FlowLayout(QLayout):
    """
    Standard Qt FlowLayout implementation for PySide6 / PyQt6.
    Dynamically reflows widgets into multiple lines based on available container width.
    """

    def __init__(self, parent: Optional[QWidget] = None, margin: int = 4, h_spacing: int = 6, v_spacing: int = 6):
        super().__init__(parent)
        self._items: List[QLayoutItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QLayoutItem):
        self._items.append(item)

    def horizontalSpacing(self) -> int:
        return self._h_spacing

    def setHorizontalSpacing(self, spacing: int):
        self._h_spacing = spacing
        self.invalidate()

    def verticalSpacing(self) -> int:
        return self._v_spacing

    def setVerticalSpacing(self, spacing: int):
        self._v_spacing = spacing
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), apply_geometry=False)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, apply_geometry=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, apply_geometry: bool = True) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._items:
            widget = item.widget()
            if widget and widget.isHidden():
                continue

            item_size = item.sizeHint()
            space_x = self._h_spacing
            space_y = self._v_spacing

            next_x = x + item_size.width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item_size.width() + space_x
                line_height = 0

            if apply_geometry:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + margins.bottom()
