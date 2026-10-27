"""
AI Khmer Movie Studio - Vector Shapes & Badges Studio Dialog
Matches the pro Canva / CapCut / Illustrator Shapes & Badges Studio UI:
- Top Header with Search, Category Filter, View Mode toggles, and Close button
- Left Category Sidebar with item count badges (All, Straight Line, Arrow Line, Double Arrow,
  Rounded Rectangle, Shape Rectangle, Perfect Circle, Triangle, Star, Heart, Crystal Badge)
- Center Shapes Gallery with categorized sections & visual shape cards
- Right Preview & Customizer:
  * Hero Checkerboard Transparency Preview Area with Bounding Box & 8 Resize Handles
  * Action Bar: [ Insert to Canvas ] [ Edit ] [ Color ] [ Flip ] [ More ]
  * Properties Card: Fill Color Palette (swatches + rainbow picker), Stroke toggle & width, Opacity
  * Preview Variations Card: 4 Live Style/Color Variant Thumbnails
"""

import math
from typing import Optional, Dict, Any, List

from ui_v_PyQt6.qt_compat import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QScrollArea, QFrame, QGridLayout, QSlider,
    QColorDialog, QColor, QFont, QPen, QBrush, QPointF, QRectF,
    QPainter, QPainterPath, QLinearGradient, Qt, Signal, QSize, QCursor
)
from ui_v_PyQt6.icons import get_qta_icon


class CheckerboardPreviewWidget(QWidget):
    """
    Renders the selected shape / badge over a transparency checkerboard pattern
    with an active selection bounding box and 8 circular resize handles.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 220)
        self.shape_info = {
            "category": "badge",
            "type": "crown_badge",
            "title": "Sample Text",
            "fill_color": QColor("#c084fc"),
            "border_color": QColor("#ffffff"),
            "border_width": 3,
            "opacity": 1.0,
            "is_flipped": False,
            "style": "solid",
            "text": "Sample Text"
        }

    def set_shape_data(self, data: dict):
        self.shape_info.update(data)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())

        # 1. Draw Checkerboard Transparency Grid
        grid_sz = 14
        cols = int(w // grid_sz) + 2
        rows = int(h // grid_sz) + 2
        for r in range(rows):
            for c in range(cols):
                col = QColor("#181e2b") if (r + c) % 2 == 0 else QColor("#222938")
                painter.fillRect(c * grid_sz, r * grid_sz, grid_sz, grid_sz, col)

        # 2. Draw Subtle Border around Preview
        painter.setPen(QPen(QColor("#2d3748"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 8, 8)

        # 3. Target Shape Bounding Box Area
        box_w = min(w * 0.76, 230.0)
        box_h = min(h * 0.72, 160.0)
        box_x = (w - box_w) / 2.0
        box_y = (h - box_h) / 2.0
        box_rect = QRectF(box_x, box_y, box_w, box_h)

        # Setup Opacity & Flip
        opacity = float(self.shape_info.get("opacity", 1.0))
        painter.setOpacity(opacity)

        painter.save()
        if self.shape_info.get("is_flipped", False):
            painter.translate(w, 0)
            painter.scale(-1, 1)

        # Draw the selected shape/badge
        stype = self.shape_info.get("type", "rounded_rect")
        fill_col = self.shape_info.get("fill_color", QColor("#38bdf8"))
        b_col = self.shape_info.get("border_color", QColor("#ffffff"))
        b_width = int(self.shape_info.get("border_width", 3))
        style_mode = self.shape_info.get("style", "solid")

        self._draw_shape_content(painter, box_rect, stype, fill_col, b_col, b_width, style_mode)
        painter.restore()

        # 4. Draw Active Selection Bounding Box & 8 Handles (matches screenshot)
        painter.setOpacity(1.0)
        painter.setPen(QPen(QColor("#38bdf8"), 1.5, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(box_rect)

        # 8 circular handles (corners + midpoints)
        h_r = 4.0
        handles = [
            box_rect.topLeft(),
            QPointF(box_rect.center().x(), box_rect.top()),
            box_rect.topRight(),
            QPointF(box_rect.right(), box_rect.center().y()),
            box_rect.bottomRight(),
            QPointF(box_rect.center().x(), box_rect.bottom()),
            box_rect.bottomLeft(),
            QPointF(box_rect.left(), box_rect.center().y()),
        ]
        painter.setBrush(QColor("#ffffff"))
        painter.setPen(QPen(QColor("#0284c7"), 1.5))
        for pt in handles:
            painter.drawEllipse(pt, h_r, h_r)

    def _draw_shape_content(self, painter: QPainter, rect: QRectF, stype: str, fill: QColor, border: QColor, b_width: int, style: str):
        # Pen setup
        if b_width > 0:
            pen = QPen(border, b_width)
            if style == "dashed":
                pen.setStyle(Qt.PenStyle.DashLine)
            elif style == "dotted":
                pen.setStyle(Qt.PenStyle.DotLine)
            else:
                pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        else:
            pen = QPen(Qt.PenStyle.NoPen)

        # Brush setup
        if style == "gradient":
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0, fill.lighter(130))
            grad.setColorAt(1, fill.darker(130))
            brush = QBrush(grad)
        elif style == "neon":
            brush = QBrush(fill)
            # Draw glow underneath
            glow_pen = QPen(fill.lighter(120), b_width + 8)
            glow_pen.setColor(QColor(fill.red(), fill.green(), fill.blue(), 90))
            painter.setPen(glow_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 16, 16)
        elif style == "outline":
            brush = Qt.BrushStyle.NoBrush
            if b_width <= 0:
                pen = QPen(fill, 3)
        else:
            brush = QBrush(fill)

        painter.setPen(pen)
        painter.setBrush(brush)

        # Draw by category / shape type
        if stype in ("line", "straight_line"):
            y = rect.center().y()
            eff_pen = pen if b_width > 0 else QPen(fill, 4)
            painter.setPen(eff_pen)
            painter.drawLine(QPointF(rect.left() + 10, y), QPointF(rect.right() - 10, y))

        elif stype in ("arrow", "arrow_line"):
            y = rect.center().y()
            eff_pen = pen if b_width > 0 else QPen(fill, 4)
            eff_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(eff_pen)
            p1 = QPointF(rect.left() + 10, y)
            p2 = QPointF(rect.right() - 14, y)
            painter.drawLine(p1, p2)
            # Arrowhead
            a_sz = 14.0
            path = QPainterPath()
            path.moveTo(p2.x() + 4, y)
            path.lineTo(p2.x() - a_sz, y - a_sz * 0.6)
            path.lineTo(p2.x() - a_sz * 0.6, y)
            path.lineTo(p2.x() - a_sz, y + a_sz * 0.6)
            path.closeSubpath()
            painter.setBrush(eff_pen.color())
            painter.drawPath(path)

        elif stype in ("curved_arrow_up", "curved_arrow_down"):
            eff_pen = pen if b_width > 0 else QPen(fill, 4)
            painter.setPen(eff_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            c_path = QPainterPath()
            c_path.moveTo(rect.left() + 15, rect.bottom() - 15)
            ctrl_y = rect.top() + 5 if stype == "curved_arrow_up" else rect.bottom() - 5
            c_path.quadToPoint(QPointF(rect.center().x(), ctrl_y), QPointF(rect.right() - 15, rect.top() + 25))
            painter.drawPath(c_path)

        elif stype in ("double_arrow", "double_arrow_line"):
            y = rect.center().y()
            eff_pen = pen if b_width > 0 else QPen(fill, 4)
            painter.setPen(eff_pen)
            p1 = QPointF(rect.left() + 20, y)
            p2 = QPointF(rect.right() - 20, y)
            painter.drawLine(p1, p2)
            # Both arrowheads
            a_sz = 12.0
            painter.setBrush(eff_pen.color())
            for tip, dir_mult in [(p1, -1), (p2, 1)]:
                path = QPainterPath()
                path.moveTo(tip.x() + dir_mult * 6, y)
                path.lineTo(tip.x() - dir_mult * a_sz, y - a_sz * 0.55)
                path.lineTo(tip.x() - dir_mult * (a_sz * 0.5), y)
                path.lineTo(tip.x() - dir_mult * a_sz, y + a_sz * 0.55)
                path.closeSubpath()
                painter.drawPath(path)

        elif stype in ("rect", "shape_rectangle"):
            painter.drawRect(rect)

        elif stype in ("rounded_rect", "rounded_rectangle"):
            rad = min(rect.width(), rect.height()) * 0.28
            painter.drawRoundedRect(rect, rad, rad)

        elif stype in ("circle", "perfect_circle"):
            d = min(rect.width(), rect.height()) * 0.88
            c_rect = QRectF(rect.center().x() - d / 2, rect.center().y() - d / 2, d, d)
            painter.drawEllipse(c_rect)

        elif stype == "triangle":
            path = QPainterPath()
            path.moveTo(rect.center().x(), rect.top() + 8)
            path.lineTo(rect.right() - 10, rect.bottom() - 8)
            path.lineTo(rect.left() + 10, rect.bottom() - 8)
            path.closeSubpath()
            painter.drawPath(path)

        elif stype in ("star", "5_point_star"):
            cx, cy = rect.center().x(), rect.center().y()
            r_out = min(rect.width(), rect.height()) * 0.44
            r_in = r_out * 0.42
            path = QPainterPath()
            for i in range(10):
                ang = i * (math.pi / 5.0) - (math.pi / 2.0)
                r = r_out if i % 2 == 0 else r_in
                px = cx + r * math.cos(ang)
                py = cy + r * math.sin(ang)
                if i == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            path.closeSubpath()
            painter.drawPath(path)

        elif stype == "heart":
            cx, cy = rect.center().x(), rect.center().y()
            scale = min(rect.width(), rect.height()) / 120.0
            path = QPainterPath()
            path.moveTo(cx, cy + 28 * scale)
            path.cubicToPoint(QPointF(cx - 55 * scale, cy - 20 * scale), QPointF(cx - 30 * scale, cy - 50 * scale), QPointF(cx, cy - 25 * scale))
            path.cubicToPoint(QPointF(cx + 30 * scale, cy - 50 * scale), QPointF(cx + 55 * scale, cy - 20 * scale), QPointF(cx, cy + 28 * scale))
            painter.drawPath(path)

        else:
            # Crown / Cloud Badge (Matches the exact cute sample text badge in user's image!)
            self._draw_cute_cloud_badge(painter, rect, fill, border, b_width)

    def _draw_cute_cloud_badge(self, painter: QPainter, rect: QRectF, fill: QColor, border: QColor, b_width: int):
        cx, cy = rect.center().x(), rect.center().y()
        bw = rect.width() * 0.82
        bh = rect.height() * 0.65

        # 1. Cloud badge body
        cloud_rect = QRectF(cx - bw / 2, cy - bh / 2 + 8, bw, bh)

        # Thick white sticker outline around cloud
        painter.setPen(QPen(QColor("#ffffff"), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        grad = QLinearGradient(cloud_rect.topLeft(), cloud_rect.bottomRight())
        grad.setColorAt(0, fill.lighter(125))
        grad.setColorAt(1, fill.darker(110))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(cloud_rect, bh * 0.45, bh * 0.45)

        # 2. Golden Crown on top left
        c_x = cloud_rect.left() + 18
        c_y = cloud_rect.top() - 10
        crown = QPainterPath()
        crown.moveTo(c_x, c_y + 14)
        crown.lineTo(c_x - 6, c_y)
        crown.lineTo(c_x + 8, c_y + 6)
        crown.lineTo(c_x + 18, c_y - 8)
        crown.lineTo(c_x + 28, c_y + 6)
        crown.lineTo(c_x + 42, c_y)
        crown.lineTo(c_x + 36, c_y + 14)
        crown.closeSubpath()
        painter.setPen(QPen(QColor("#ffffff"), 3))
        painter.setBrush(QColor("#facc15"))
        painter.drawPath(crown)

        # 3. Yellow star accents
        for sx, sy, s_r in [(cloud_rect.left() - 4, cloud_rect.bottom() - 16, 8.0), (cloud_rect.right() + 4, cloud_rect.bottom() - 12, 10.0)]:
            s_path = QPainterPath()
            for i in range(10):
                ang = i * (math.pi / 5.0) - (math.pi / 2.0)
                r = s_r if i % 2 == 0 else s_r * 0.45
                px = sx + r * math.cos(ang)
                py = sy + r * math.sin(ang)
                if i == 0:
                    s_path.moveTo(px, py)
                else:
                    s_path.lineTo(px, py)
            s_path.closeSubpath()
            painter.setPen(QPen(QColor("#ffffff"), 2.5))
            painter.setBrush(QColor("#facc15"))
            painter.drawPath(s_path)

        # 4. Text inside Badge "Sample Text"
        badge_txt = self.shape_info.get("text", "Sample Text")
        painter.setPen(QPen(QColor("#ffffff"), 4))
        f = QFont("Arial", 16, QFont.Weight.Black)
        painter.setFont(f)

        # Draw thick 3D text
        painter.setPen(QColor("#a855f7"))
        painter.drawText(cloud_rect.adjusted(0, 2, 0, 2), Qt.AlignmentFlag.AlignCenter, badge_txt)
        painter.setPen(QColor("#ffffff"))
        painter.drawText(cloud_rect, Qt.AlignmentFlag.AlignCenter, badge_txt)


class ShapeCardWidget(QFrame):
    """Mini preview card inside the center shapes gallery."""
    clicked = Signal(dict)

    def __init__(self, item_data: dict, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.setFixedSize(116, 52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_selected = False
        self.setStyleSheet("""
            ShapeCardWidget {
                background-color: #121622;
                border: 1px solid #1e2638;
                border-radius: 8px;
            }
            ShapeCardWidget:hover {
                border: 1.5px solid #38bdf8;
                background-color: #171d2b;
            }
        """)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        if selected:
            self.setStyleSheet("""
                ShapeCardWidget {
                    background-color: #151e2f;
                    border: 2px solid #38bdf8;
                    border-radius: 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                ShapeCardWidget {
                    background-color: #121622;
                    border: 1px solid #1e2638;
                    border-radius: 8px;
                }
                ShapeCardWidget:hover {
                    border: 1.5px solid #38bdf8;
                    background-color: #171d2b;
                }
            """)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item_data)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = float(self.width())
        h = float(self.height())
        rect = QRectF(12, 10, w - 24, h - 20)

        stype = self.item_data.get("type", "rounded_rect")
        fill_col = self.item_data.get("fill_color", QColor("#38bdf8"))
        b_col = self.item_data.get("border_color", QColor("#ffffff"))
        style_mode = self.item_data.get("style", "solid")

        eff_col = fill_col if fill_col.alpha() > 0 else b_col

        if "line" in stype:
            eff_pen = QPen(eff_col, 3)
            if style_mode == "dashed":
                eff_pen.setStyle(Qt.PenStyle.DashLine)
            elif style_mode == "neon":
                eff_pen.setColor(eff_col)
                # Outer glow
                painter.setPen(QPen(QColor(eff_col.red(), eff_col.green(), eff_col.blue(), 100), 7))
                painter.drawLine(QPointF(rect.left(), rect.center().y()), QPointF(rect.right(), rect.center().y()))
            painter.setPen(eff_pen)
            painter.drawLine(QPointF(rect.left(), rect.center().y()), QPointF(rect.right(), rect.center().y()))

            if "arrow" in stype:
                a_sz = 9.0
                p_tip = QPointF(rect.right(), rect.center().y())
                path = QPainterPath()
                path.moveTo(p_tip.x(), p_tip.y())
                path.lineTo(p_tip.x() - a_sz, p_tip.y() - a_sz * 0.5)
                path.lineTo(p_tip.x() - a_sz * 0.6, p_tip.y())
                path.lineTo(p_tip.x() - a_sz, p_tip.y() + a_sz * 0.5)
                path.closeSubpath()
                painter.setBrush(eff_col)
                painter.drawPath(path)
                if "double" in stype:
                    p_left = QPointF(rect.left(), rect.center().y())
                    l_path = QPainterPath()
                    l_path.moveTo(p_left.x(), p_left.y())
                    l_path.lineTo(p_left.x() + a_sz, p_left.y() - a_sz * 0.5)
                    l_path.lineTo(p_left.x() + a_sz * 0.6, p_left.y())
                    l_path.lineTo(p_left.x() + a_sz, p_left.y() + a_sz * 0.5)
                    l_path.closeSubpath()
                    painter.drawPath(l_path)

        elif "curved_arrow" in stype:
            eff_pen = QPen(eff_col, 3)
            painter.setPen(eff_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            c_path = QPainterPath()
            c_path.moveTo(rect.left() + 4, rect.bottom() - 4)
            c_path.quadToPoint(QPointF(rect.center().x(), rect.top() + 2), QPointF(rect.right() - 4, rect.top() + 6))
            painter.drawPath(c_path)
            # tip
            tip = QPointF(rect.right() - 4, rect.top() + 6)
            a_sz = 8.0
            p = QPainterPath()
            p.moveTo(tip)
            p.lineTo(tip.x() - a_sz, tip.y() - 2)
            p.lineTo(tip.x() - 4, tip.y() + a_sz)
            p.closeSubpath()
            painter.setBrush(eff_col)
            painter.drawPath(p)

        elif stype in ("rounded_rect", "rect"):
            rad = 8.0 if stype == "rounded_rect" else 2.0
            if style_mode == "outline":
                painter.setPen(QPen(eff_col, 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            elif style_mode == "dashed":
                painter.setPen(QPen(eff_col, 2, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
            elif style_mode == "gradient":
                grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
                grad.setColorAt(0, eff_col.lighter(130))
                grad.setColorAt(1, eff_col.darker(130))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(grad)
            else:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(eff_col)
            painter.drawRoundedRect(rect, rad, rad)

        elif stype == "circle":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(eff_col)
            d = min(rect.width(), rect.height()) * 0.8
            painter.drawEllipse(QRectF(rect.center().x() - d / 2, rect.center().y() - d / 2, d, d))

        elif stype == "triangle":
            path = QPainterPath()
            path.moveTo(rect.center().x(), rect.top() + 2)
            path.lineTo(rect.right() - 6, rect.bottom() - 2)
            path.lineTo(rect.left() + 6, rect.bottom() - 2)
            path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(eff_col)
            painter.drawPath(path)

        elif stype == "star":
            cx, cy = rect.center().x(), rect.center().y()
            r_out = min(rect.width(), rect.height()) * 0.42
            r_in = r_out * 0.42
            path = QPainterPath()
            for i in range(10):
                ang = i * (math.pi / 5.0) - (math.pi / 2.0)
                r = r_out if i % 2 == 0 else r_in
                px = cx + r * math.cos(ang)
                py = cy + r * math.sin(ang)
                if i == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(eff_col)
            painter.drawPath(path)

        elif stype == "heart":
            cx, cy = rect.center().x(), rect.center().y()
            s = 0.28
            path = QPainterPath()
            path.moveTo(cx, cy + 10 * s)
            path.cubicToPoint(QPointF(cx - 30 * s, cy - 15 * s), QPointF(cx - 15 * s, cy - 35 * s), QPointF(cx, cy - 15 * s))
            path.cubicToPoint(QPointF(cx + 15 * s, cy - 35 * s), QPointF(cx + 30 * s, cy - 15 * s), QPointF(cx, cy + 10 * s))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(eff_col)
            painter.drawPath(path)

        elif stype == "badge":
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.setBrush(eff_col)
            painter.drawRoundedRect(rect, 8, 8)
            painter.setPen(QColor("#ffffff"))
            f = QFont("Arial", 8, QFont.Weight.Bold)
            painter.setFont(f)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "BADGE")


class VectorShapesStudioDialog(QDialog):
    """
    State-of-the-art Vector Shapes & Badges Studio Dialog matching user image:
    - Top titlebar with search, filter, view modes, and close button
    - Left categorized menu (Straight line, Arrow, Double arrow, Rectangles, Circle, Triangle, Star, Heart, Badge)
    - Center gallery with labeled sections and visual cards
    - Right preview with checkerboard, 8 handles, actions, color palette, stroke, opacity & variations
    """
    shape_inserted = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vector Shapes & Badges")
        self.resize(1100, 680)
        self.setMinimumSize(920, 580)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e17;
                color: #f1f5f9;
            }
        """)

        self.current_shape_data = {
            "category": "badge",
            "type": "crown_badge",
            "title": "Crown Cloud Badge",
            "fill_color": QColor("#c084fc"),
            "border_color": QColor("#ffffff"),
            "border_width": 3,
            "opacity": 1.0,
            "is_flipped": False,
            "style": "solid",
            "text": "Sample Text"
        }

        self._all_cards: List[ShapeCardWidget] = []
        self._init_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        # ---------------- 1. TOP HEADER BAR ----------------
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        # Brand Icon & Title
        btn_brand = QPushButton("▶")
        btn_brand.setFixedSize(28, 28)
        btn_brand.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8b5cf6, stop:1 #38bdf8);
                color: #ffffff;
                font-weight: 900;
                border-radius: 8px;
                border: none;
                font-size: 13px;
            }
        """)
        hdr.addWidget(btn_brand)

        lbl_title = QLabel("Vector Shapes & Badges")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #f8fafc;")
        hdr.addWidget(lbl_title)

        hdr.addSpacing(16)

        # Search Bar
        self.entry_search = QLineEdit()
        self.entry_search.setPlaceholderText("🔍 Search shapes, badges, stickers...")
        self.entry_search.setStyleSheet("""
            QLineEdit {
                background-color: #121622;
                color: #e2e8f0;
                border: 1px solid #1e2638;
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 11px;
                min-width: 240px;
            }
            QLineEdit:focus {
                border: 1px solid #38bdf8;
                background-color: #151a28;
            }
        """)
        self.entry_search.textChanged.connect(self._on_search_filter)
        hdr.addWidget(self.entry_search)

        # Category Dropdown
        self.combo_cat = QComboBox()
        self.combo_cat.addItems(["All Categories", "Lines & Arrows", "Geometric Shapes", "Badges & Ribbons", "Icons"])
        self.combo_cat.setStyleSheet("""
            QComboBox {
                background-color: #121622;
                color: #cbd5e1;
                border: 1px solid #1e2638;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                min-width: 120px;
            }
            QComboBox QAbstractItemView {
                background-color: #121622;
                color: #e2e8f0;
                selection-background-color: #0284c7;
            }
        """)
        self.combo_cat.currentIndexChanged.connect(self._on_cat_filter)
        hdr.addWidget(self.combo_cat)

        hdr.addStretch()

        # View Mode Toggle Icons
        btn_list = QPushButton()
        btn_list.setIcon(get_qta_icon("fa5s.th-list", color="#64748b"))
        btn_list.setFixedSize(30, 30)
        btn_list.setStyleSheet("background: #141824; border: 1px solid #1e2638; border-radius: 6px;")

        btn_grid = QPushButton()
        btn_grid.setIcon(get_qta_icon("fa5s.th-large", color="#ffffff"))
        btn_grid.setFixedSize(30, 30)
        btn_grid.setStyleSheet("background: #2563eb; border: 1px solid #3b82f6; border-radius: 6px;")

        btn_compact = QPushButton()
        btn_compact.setIcon(get_qta_icon("fa5s.bars", color="#64748b"))
        btn_compact.setFixedSize(30, 30)
        btn_compact.setStyleSheet("background: #141824; border: 1px solid #1e2638; border-radius: 6px;")

        hdr.addWidget(btn_list)
        hdr.addWidget(btn_grid)
        hdr.addWidget(btn_compact)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #94a3b8;
                font-size: 15px;
                font-weight: bold;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1e2638;
                color: #ffffff;
            }
        """)
        btn_close.clicked.connect(self.close)
        hdr.addWidget(btn_close)

        root.addLayout(hdr)

        # ---------------- 2. MAIN 3-COLUMN STUDIO LAYOUT ----------------
        main_h = QHBoxLayout()
        main_h.setSpacing(14)

        # --- (A) LEFT CATEGORY SIDEBAR ---
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #0d101a;
                border: 1px solid #1a202f;
                border-radius: 10px;
            }
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(6, 8, 6, 8)
        sb_layout.setSpacing(3)

        self._sidebar_buttons = []
        categories_data = [
            ("all", "▦  All", "1,240", True),
            ("straight_line", "—  Straight Line", "120", False),
            ("arrow_line", "↗  Arrow Line", "250", False),
            ("double_arrow", "↔  Double Arrow", "180", False),
            ("rounded_rect", "■  Rounded Rect", "160", False),
            ("shape_rect", "□  Shape Rect", "140", False),
            ("circle", "●  Perfect Circle", "220", False),
            ("triangle", "▲  Triangle", "180", False),
            ("star", "★  5-Point Star", "200", False),
            ("heart", "♥  Heart", "120", False),
            ("crystal_badge", "💎  Crystal Badge", "90", False),
        ]

        for cat_id, cat_title, cat_cnt, is_active in categories_data:
            btn_cat = QPushButton()
            btn_cat.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cat.setFixedHeight(34)
            b_layout = QHBoxLayout(btn_cat)
            b_layout.setContentsMargins(10, 0, 8, 0)

            lbl_t = QLabel(cat_title)
            lbl_t.setStyleSheet("font-size: 11px; font-weight: 600; background: transparent;")
            lbl_c = QLabel(cat_cnt)
            lbl_c.setStyleSheet("font-size: 10px; color: #64748b; background: transparent;")

            b_layout.addWidget(lbl_t)
            b_layout.addStretch()
            b_layout.addWidget(lbl_c)

            self._style_category_button(btn_cat, is_active)
            btn_cat.clicked.connect(lambda _, cid=cat_id, b=btn_cat: self._on_category_clicked(cid, b))
            sb_layout.addWidget(btn_cat)
            self._sidebar_buttons.append((btn_cat, cat_id))

        sb_layout.addStretch()
        main_h.addWidget(sidebar)

        # --- (B) CENTER SHAPES GALLERY (SCROLL AREA) ---
        scroll_gallery = QScrollArea()
        scroll_gallery.setWidgetResizable(True)
        scroll_gallery.setFrameShape(QFrame.Shape.NoFrame)
        scroll_gallery.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        gallery_container = QWidget()
        self.g_layout = QVBoxLayout(gallery_container)
        self.g_layout.setContentsMargins(0, 0, 8, 0)
        self.g_layout.setSpacing(14)

        # Populate Sections matching the screenshot
        self._build_gallery_sections()

        scroll_gallery.setWidget(gallery_container)
        main_h.addWidget(scroll_gallery, 1)

        # --- (C) RIGHT COLUMN: HERO PREVIEW & CUSTOMIZER ---
        right_col = QFrame()
        right_col.setFixedWidth(380)
        right_col.setStyleSheet("""
            QFrame {
                background-color: transparent;
            }
        """)
        rc_layout = QVBoxLayout(right_col)
        rc_layout.setContentsMargins(0, 0, 0, 0)
        rc_layout.setSpacing(10)

        # 1. Top Hero Checkerboard Preview
        self.preview_widget = CheckerboardPreviewWidget()
        rc_layout.addWidget(self.preview_widget)

        # 2. Action Buttons Toolbar directly below preview
        act_row = QHBoxLayout()
        act_row.setSpacing(6)

        self.btn_insert = QPushButton(" 📥 Insert to Canvas")
        self.btn_insert.setIcon(get_qta_icon("fa5s.download", color="#ffffff"))
        self.btn_insert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_insert.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #3b82f6);
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #2563eb);
            }
        """)
        self.btn_insert.clicked.connect(self._on_insert_clicked)
        act_row.addWidget(self.btn_insert, 2)

        btn_edit = QPushButton(" ✏️ Edit")
        btn_edit.setStyleSheet(self._sub_btn_style())
        btn_edit.clicked.connect(self._on_edit_text_clicked)
        act_row.addWidget(btn_edit, 1)

        btn_col = QPushButton(" 🎨 Color")
        btn_col.setStyleSheet(self._sub_btn_style())
        btn_col.clicked.connect(self._pick_custom_color)
        act_row.addWidget(btn_col, 1)

        btn_flip = QPushButton(" ⇄ Flip")
        btn_flip.setStyleSheet(self._sub_btn_style())
        btn_flip.clicked.connect(self._on_flip_clicked)
        act_row.addWidget(btn_flip, 1)

        btn_more = QPushButton(" ⋯ More")
        btn_more.setStyleSheet(self._sub_btn_style())
        act_row.addWidget(btn_more, 1)

        rc_layout.addLayout(act_row)

        # 3. Bottom Row: 2 Cards Side-by-Side (Properties & Variations)
        bot_h = QHBoxLayout()
        bot_h.setSpacing(8)

        # Left Card: Properties
        card_props = QFrame()
        card_props.setStyleSheet("""
            QFrame {
                background-color: #10141f;
                border: 1px solid #1a2233;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        cp_layout = QVBoxLayout(card_props)
        cp_layout.setContentsMargins(6, 6, 6, 6)
        cp_layout.setSpacing(6)

        lbl_p_title = QLabel("Properties")
        lbl_p_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        cp_layout.addWidget(lbl_p_title)

        # Fill Color Row & Swatches
        lbl_fc = QLabel("Fill Color:")
        lbl_fc.setStyleSheet("color: #94a3b8; font-size: 10px;")
        cp_layout.addWidget(lbl_fc)

        palette_h = QHBoxLayout()
        palette_h.setSpacing(4)
        swatches = ["#ffffff", "#f43f5e", "#f97316", "#eab308", "#10b981", "#06b6d4", "#3b82f6", "#8b5cf6"]
        for c_hex in swatches:
            btn_swatch = QPushButton()
            btn_swatch.setFixedSize(16, 16)
            btn_swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_swatch.setStyleSheet(f"background-color: {c_hex}; border: 1px solid #ffffff; border-radius: 8px;")
            btn_swatch.clicked.connect(lambda _, col=c_hex: self._set_preview_fill_color(col))
            palette_h.addWidget(btn_swatch)

        # Rainbow color picker button
        btn_rainbow = QPushButton("🌈")
        btn_rainbow.setFixedSize(18, 18)
        btn_rainbow.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rainbow.setStyleSheet("background: transparent; border: 1px solid #475569; border-radius: 9px; font-size: 9px;")
        btn_rainbow.clicked.connect(self._pick_custom_color)
        palette_h.addWidget(btn_rainbow)
        cp_layout.addLayout(palette_h)

        # Stroke Row
        row_strk = QHBoxLayout()
        row_strk.addWidget(QLabel("Stroke:"))
        self.btn_stroke_col = QPushButton()
        self.btn_stroke_col.setFixedSize(14, 14)
        self.btn_stroke_col.setStyleSheet("background-color: #ffffff; border-radius: 7px; border: 1px solid #94a3b8;")
        self.btn_stroke_col.clicked.connect(self._pick_stroke_color)
        row_strk.addWidget(self.btn_stroke_col)

        self.slider_stroke = QSlider(Qt.Orientation.Horizontal)
        self.slider_stroke.setRange(0, 16)
        self.slider_stroke.setValue(3)
        self.slider_stroke.valueChanged.connect(self._on_stroke_changed)
        row_strk.addWidget(self.slider_stroke)

        self.lbl_stroke_val = QLabel("3 px")
        self.lbl_stroke_val.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: bold;")
        row_strk.addWidget(self.lbl_stroke_val)
        cp_layout.addLayout(row_strk)

        # Opacity Row
        row_op = QHBoxLayout()
        row_op.addWidget(QLabel("Opacity:"))
        self.slider_op = QSlider(Qt.Orientation.Horizontal)
        self.slider_op.setRange(10, 100)
        self.slider_op.setValue(100)
        self.slider_op.valueChanged.connect(self._on_opacity_changed)
        row_op.addWidget(self.slider_op)

        self.lbl_op_val = QLabel("100%")
        self.lbl_op_val.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: bold;")
        row_op.addWidget(self.lbl_op_val)
        cp_layout.addLayout(row_op)

        bot_h.addWidget(card_props, 1)

        # Right Card: Preview Variations
        card_var = QFrame()
        card_var.setStyleSheet("""
            QFrame {
                background-color: #10141f;
                border: 1px solid #1a2233;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        cv_layout = QVBoxLayout(card_var)
        cv_layout.setContentsMargins(6, 6, 6, 6)
        cv_layout.setSpacing(4)

        lbl_v_title = QLabel("Preview Variations")
        lbl_v_title.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px;")
        cv_layout.addWidget(lbl_v_title)

        var_grid = QGridLayout()
        var_grid.setSpacing(4)

        variants = [
            ("Pink Pastel", "#ec4899"),
            ("Neon Cyan", "#06b6d4"),
            ("Sunset Gold", "#f59e0b"),
            ("Dark Velvet", "#334155")
        ]
        for v_idx, (v_name, v_col) in enumerate(variants):
            btn_v = QPushButton()
            btn_v.setFixedSize(68, 36)
            btn_v.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_v.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {v_col}, stop:1 #1e293b);
                    border: 1.5px solid #ffffff;
                    border-radius: 6px;
                    color: #ffffff;
                    font-size: 8px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    border: 2px solid #38bdf8;
                }}
            """)
            btn_v.setText(v_name.split()[0])
            btn_v.clicked.connect(lambda _, col=v_col: self._set_preview_fill_color(col))
            var_grid.addWidget(btn_v, v_idx // 2, v_idx % 2)

        cv_layout.addLayout(var_grid)
        bot_h.addWidget(card_var, 1)

        rc_layout.addLayout(bot_h)
        main_h.addWidget(right_col)

        root.addLayout(main_h)

    # ------------------ GALLERY BUILDER ------------------
    def _build_gallery_sections(self):
        sections_data = [
            ("Straight Line (120)", [
                {"category": "straight_line", "type": "line", "title": "White Solid Line", "fill_color": QColor("#ffffff"), "style": "solid"},
                {"category": "straight_line", "type": "line", "title": "Dashed Line", "fill_color": QColor("#ffffff"), "style": "dashed"},
                {"category": "straight_line", "type": "line", "title": "Neon Blue Line", "fill_color": QColor("#38bdf8"), "style": "neon"},
                {"category": "straight_line", "type": "arrow", "title": "Right Arrow", "fill_color": QColor("#ffffff"), "style": "solid"},
                {"category": "straight_line", "type": "arrow", "title": "Neon Green Arrow", "fill_color": QColor("#10b981"), "style": "neon"},
                {"category": "straight_line", "type": "arrow", "title": "Red Dashed Arrow", "fill_color": QColor("#ef4444"), "style": "dashed"},
            ]),
            ("Arrow Line (250)", [
                {"category": "arrow_line", "type": "arrow", "title": "Straight Arrow", "fill_color": QColor("#ffffff"), "style": "solid"},
                {"category": "arrow_line", "type": "arrow", "title": "Neon Pink Arrow", "fill_color": QColor("#ec4899"), "style": "neon"},
                {"category": "arrow_line", "type": "curved_arrow_up", "title": "Yellow Arc Arrow", "fill_color": QColor("#eab308"), "style": "solid"},
                {"category": "arrow_line", "type": "curved_arrow_down", "title": "Cyan Arc Arrow", "fill_color": QColor("#06b6d4"), "style": "neon"},
                {"category": "arrow_line", "type": "curved_arrow_up", "title": "Dashed Arc Arrow", "fill_color": QColor("#ffffff"), "style": "dashed"},
                {"category": "arrow_line", "type": "curved_arrow_down", "title": "Orange Curved", "fill_color": QColor("#f97316"), "style": "solid"},
            ]),
            ("Double Arrow (180)", [
                {"category": "double_arrow", "type": "double_arrow", "title": "White Double Arrow", "fill_color": QColor("#ffffff"), "style": "solid"},
                {"category": "double_arrow", "type": "double_arrow", "title": "Green Double Arrow", "fill_color": QColor("#10b981"), "style": "solid"},
                {"category": "double_arrow", "type": "double_arrow", "title": "Pink Neon Double", "fill_color": QColor("#ec4899"), "style": "neon"},
                {"category": "double_arrow", "type": "double_arrow", "title": "Dashed Double Arrow", "fill_color": QColor("#ffffff"), "style": "dashed"},
                {"category": "double_arrow", "type": "double_arrow", "title": "Cyan Neon Double", "fill_color": QColor("#06b6d4"), "style": "neon"},
                {"category": "double_arrow", "type": "double_arrow", "title": "Gold Double Arrow", "fill_color": QColor("#eab308"), "style": "solid"},
            ]),
            ("Rounded Rectangle (160)", [
                {"category": "rounded_rect", "type": "rounded_rect", "title": "White Outline", "fill_color": QColor(0, 0, 0, 0), "border_color": QColor("#ffffff"), "style": "outline"},
                {"category": "rounded_rect", "type": "rounded_rect", "title": "Blue Gradient", "fill_color": QColor("#2563eb"), "style": "gradient"},
                {"category": "rounded_rect", "type": "rounded_rect", "title": "Purple Dashed", "fill_color": QColor(0, 0, 0, 0), "border_color": QColor("#c084fc"), "style": "dashed"},
                {"category": "rounded_rect", "type": "rounded_rect", "title": "Sunset Gradient", "fill_color": QColor("#f43f5e"), "style": "gradient"},
                {"category": "rounded_rect", "type": "rounded_rect", "title": "Cyan Neon Outline", "fill_color": QColor(0, 0, 0, 0), "border_color": QColor("#06b6d4"), "style": "outline"},
                {"category": "rounded_rect", "type": "rounded_rect", "title": "Frosted Blue", "fill_color": QColor("#0284c7"), "style": "solid"},
            ]),
            ("Shape Rectangle (140)", [
                {"category": "shape_rect", "type": "rect", "title": "White Solid Rect", "fill_color": QColor("#ffffff"), "style": "solid"},
                {"category": "shape_rect", "type": "rect", "title": "Purple Gradient", "fill_color": QColor("#7c3aed"), "style": "gradient"},
                {"category": "shape_rect", "type": "rect", "title": "White Outline", "fill_color": QColor(0, 0, 0, 0), "border_color": QColor("#ffffff"), "style": "outline"},
                {"category": "shape_rect", "type": "rect", "title": "Dark Box", "fill_color": QColor("#1e293b"), "style": "solid"},
            ]),
            ("Geometric Shapes (Circle, Star, Heart, Triangle)", [
                {"category": "circle", "type": "circle", "title": "White Circle", "fill_color": QColor("#ffffff"), "style": "solid"},
                {"category": "triangle", "type": "triangle", "title": "Red Triangle", "fill_color": QColor("#f43f5e"), "style": "solid"},
                {"category": "star", "type": "star", "title": "Golden 5-Point Star", "fill_color": QColor("#eab308"), "style": "solid"},
                {"category": "heart", "type": "heart", "title": "Pink Heart", "fill_color": QColor("#ec4899"), "style": "solid"},
                {"category": "crystal_badge", "type": "crown_badge", "title": "Crown Cloud Badge", "fill_color": QColor("#c084fc"), "style": "badge"},
                {"category": "crystal_badge", "type": "badge", "title": "Vector Badge", "fill_color": QColor("#0284c7"), "style": "badge"},
            ])
        ]

        for sec_title, items in sections_data:
            sec_header = QHBoxLayout()
            lbl_s = QLabel(f"› {sec_title}")
            lbl_s.setStyleSheet("color: #f1f5f9; font-weight: 700; font-size: 12px;")
            sec_header.addWidget(lbl_s)
            sec_header.addStretch()

            btn_see = QPushButton("See All ›")
            btn_see.setStyleSheet("background: transparent; border: none; color: #38bdf8; font-size: 11px; font-weight: bold;")
            sec_header.addWidget(btn_see)
            self.g_layout.addLayout(sec_header)

            grid = QGridLayout()
            grid.setSpacing(8)
            for idx, item_data in enumerate(items):
                card = ShapeCardWidget(item_data)
                card.clicked.connect(self._on_card_selected)
                grid.addWidget(card, idx // 3, idx % 3)
                self._all_cards.append(card)

            self.g_layout.addLayout(grid)

        # Highlight default first badge card
        if self._all_cards:
            self._all_cards[0].set_selected(True)

    # ------------------ STYLES & HANDLERS ------------------
    def _sub_btn_style(self) -> str:
        return """
            QPushButton {
                background-color: #141926;
                color: #cbd5e1;
                font-size: 10px;
                font-weight: 600;
                border: 1px solid #1e2638;
                border-radius: 6px;
                padding: 6px 4px;
            }
            QPushButton:hover {
                background-color: #1f273b;
                border: 1px solid #38bdf8;
                color: #ffffff;
            }
        """

    def _style_category_button(self, btn: QPushButton, is_active: bool):
        if is_active:
            btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #4f46e5);
                    border: none;
                    border-radius: 6px;
                    color: #ffffff;
                }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    color: #cbd5e1;
                }
                QPushButton:hover {
                    background-color: #161c2a;
                    color: #ffffff;
                }
            """)

    def _on_category_clicked(self, cat_id: str, active_btn: QPushButton):
        for btn, _ in self._sidebar_buttons:
            self._style_category_button(btn, btn == active_btn)

        # Filter gallery items
        for card in self._all_cards:
            c_cat = card.item_data.get("category", "")
            if cat_id == "all" or cat_id == c_cat or (cat_id in c_cat):
                card.show()
            else:
                card.hide()

    def _on_search_filter(self, text: str):
        q = text.lower().strip()
        for card in self._all_cards:
            title = card.item_data.get("title", "").lower()
            cat = card.item_data.get("category", "").lower()
            stype = card.item_data.get("type", "").lower()
            card.setVisible(not q or (q in title or q in cat or q in stype))

    def _on_cat_filter(self, idx: int):
        cat_map = {0: "all", 1: "line", 2: "rect", 3: "badge", 4: "star"}
        target = cat_map.get(idx, "all")
        for card in self._all_cards:
            c_cat = card.item_data.get("category", "")
            card.setVisible(target == "all" or target in c_cat)

    def _on_card_selected(self, item_data: dict):
        for card in self._all_cards:
            card.set_selected(card.item_data == item_data)

        self.current_shape_data.update(item_data)
        self.preview_widget.set_shape_data(self.current_shape_data)

    def _set_preview_fill_color(self, hex_color: str):
        self.current_shape_data["fill_color"] = QColor(hex_color)
        self.preview_widget.set_shape_data(self.current_shape_data)

    def _pick_custom_color(self):
        cur = self.current_shape_data.get("fill_color", QColor("#38bdf8"))
        col = QColorDialog.getColor(cur, self, "Select Shape Color")
        if col.isValid():
            self._set_preview_fill_color(col.name())

    def _pick_stroke_color(self):
        cur = self.current_shape_data.get("border_color", QColor("#ffffff"))
        col = QColorDialog.getColor(cur, self, "Select Stroke Color")
        if col.isValid():
            self.current_shape_data["border_color"] = col
            self.btn_stroke_col.setStyleSheet(f"background-color: {col.name()}; border-radius: 7px; border: 1px solid #ffffff;")
            self.preview_widget.set_shape_data(self.current_shape_data)

    def _on_stroke_changed(self, val: int):
        self.current_shape_data["border_width"] = val
        self.lbl_stroke_val.setText(f"{val} px")
        self.preview_widget.set_shape_data(self.current_shape_data)

    def _on_opacity_changed(self, val: int):
        op = val / 100.0
        self.current_shape_data["opacity"] = op
        self.lbl_op_val.setText(f"{val}%")
        self.preview_widget.set_shape_data(self.current_shape_data)

    def _on_flip_clicked(self):
        cur = self.current_shape_data.get("is_flipped", False)
        self.current_shape_data["is_flipped"] = not cur
        self.preview_widget.set_shape_data(self.current_shape_data)

    def _on_edit_text_clicked(self):
        from ui_v_PyQt6.qt_compat import QInputDialog
        cur = self.current_shape_data.get("text", "Sample Text")
        txt, ok = QInputDialog.getText(self, "Edit Badge Text", "Enter Text for Shape / Badge:", text=cur)
        if ok and txt.strip():
            self.current_shape_data["text"] = txt.strip()
            self.preview_widget.set_shape_data(self.current_shape_data)

    def _on_insert_clicked(self):
        """Emits selected shape data and closes dialog."""
        self.shape_inserted.emit(dict(self.current_shape_data))
        self.accept()
