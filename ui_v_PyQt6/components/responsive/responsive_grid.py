"""
ResponsiveGrid: Dynamic Column Reflow Grid
Automatically recalculates column counts based on container width and minimum item width,
ensuring items wrap neatly across 1, 2, 3, or more columns without overlapping or clipping.
"""

from typing import List, Optional
from ui_v_PyQt6.qt_compat import (
    QWidget, QGridLayout, QSize, Qt, QTimer
)


class ResponsiveGrid(QWidget):
    """
    Adaptive grid that automatically reflows child widgets into the optimal
    number of columns based on container width.
    """

    def __init__(
        self,
        min_item_width: int = 160,
        spacing: int = 8,
        margin: int = 4,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.min_item_width = min_item_width
        self.spacing = spacing
        self.margin = margin
        self._items: List[QWidget] = []
        self._current_cols = 1

        self._grid_layout = QGridLayout(self)
        self._grid_layout.setContentsMargins(margin, margin, margin, margin)
        self._grid_layout.setSpacing(spacing)

        # 16ms debouncer to avoid excessive recalculation during dragging
        self._reflow_timer = QTimer(self)
        self._reflow_timer.setSingleShot(True)
        self._reflow_timer.timeout.connect(self._recalculate_columns)

    def add_item(self, widget: QWidget):
        """Adds a widget to the responsive grid"""
        self._items.append(widget)
        self._reflow_timer.start(16)

    def remove_item(self, widget: QWidget):
        if widget in self._items:
            self._items.remove(widget)
            self._grid_layout.removeWidget(widget)
            self._reflow_timer.start(16)

    def clear(self):
        for w in self._items:
            self._grid_layout.removeWidget(w)
        self._items.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reflow_timer.start(16)

    def _recalculate_columns(self):
        w = self.width() - (2 * self.margin)
        if w <= 0 or not self._items:
            return

        # Calculate optimal column count
        calculated_cols = max(1, w // (self.min_item_width + self.spacing))

        # Re-arrange items in the grid
        self._current_cols = calculated_cols

        # Detach from grid
        for widget in self._items:
            self._grid_layout.removeWidget(widget)

        # Re-attach in (row, col) order
        for idx, widget in enumerate(self._items):
            row = idx // calculated_cols
            col = idx % calculated_cols
            self._grid_layout.addWidget(widget, row, col)
