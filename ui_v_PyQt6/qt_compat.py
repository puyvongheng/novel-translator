"""
Qt Compatibility Layer for PySide6 and PyQt6
Automatically detects and imports available Qt6 binding.
Prioritizes PySide6 (official Qt for Python) and falls back to PyQt6.
"""

import os
import sys

# Suppress Qt font database fallback warnings and invalid point size logs
os.environ.setdefault(
    "QT_LOGGING_RULES",
    "qt.text.font.db=false;qt.text.*=false;qt.gui.font=false;qt.core.qobject.font=false"
)

QT_LIB = None

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, QTimer, QThread, Signal, Slot, QPoint, QPointF, QRect, QRectF, QSize, QUrl, QObject, QEvent, QSettings, QMimeData
    from PySide6.QtGui import (
        QColor, QFont, QIcon, QImage, QPixmap, QPainter, QPen, QBrush, 
        QLinearGradient, QRadialGradient, QAction, QKeySequence, QCursor, QShortcut,
        QTransform, QPainterPath, QImageReader, QMovie, QKeyEvent, QDrag
    )
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QFrame, QGroupBox, QLabel, QPushButton, 
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QCheckBox, 
        QSlider, QProgressBar, QSplitter, QScrollArea, QTabWidget, 
        QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, 
        QHBoxLayout, QGridLayout, QFormLayout, QFileDialog, QMessageBox, 
        QMenu, QMenuBar, QStatusBar, QToolBar, QSizePolicy, QDialog, QInputDialog,
        QToolTip, QSpinBox, QDoubleSpinBox, QStackedWidget, QColorDialog, QTabBar,
        QRadioButton, QButtonGroup, QDockWidget, QLayout, QLayoutItem, QSpacerItem, QToolButton,
        QStyledItemDelegate, QStyle, QAbstractItemView
    )
    QT_LIB = "PySide6"
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal as Signal, pyqtSlot as Slot, QPoint, QPointF, QRect, QRectF, QSize, QUrl, QObject, QEvent, QSettings, QMimeData
        from PyQt6.QtGui import (
            QColor, QFont, QIcon, QImage, QPixmap, QPainter, QPen, QBrush, 
            QLinearGradient, QRadialGradient, QAction, QKeySequence, QCursor, QShortcut,
            QTransform, QPainterPath, QImageReader, QMovie, QKeyEvent, QDrag
        )
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QFrame, QGroupBox, QLabel, QPushButton, 
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QCheckBox, 
            QSlider, QProgressBar, QSplitter, QScrollArea, QTabWidget, 
            QTableWidget, QTableWidgetItem, QHeaderView, QVBoxLayout, 
            QHBoxLayout, QGridLayout, QFormLayout, QFileDialog, QMessageBox, 
            QMenu, QMenuBar, QStatusBar, QToolBar, QSizePolicy, QDialog, QInputDialog,
            QToolTip, QSpinBox, QDoubleSpinBox, QStackedWidget, QColorDialog, QTabBar,
            QRadioButton, QButtonGroup, QDockWidget, QLayout, QLayoutItem, QSpacerItem, QToolButton,
            QStyledItemDelegate, QStyle, QAbstractItemView
        )
        QT_LIB = "PyQt6"
    except ImportError as e:
        raise ImportError(
            "Neither PySide6 nor PyQt6 is installed. Please run: pip install PySide6"
        ) from e


def _clean_qt_message_handler(mode, context, message):
    """
    Silences harmless Qt internal warnings such as QFont::setPointSize <= 0
    caused by stylesheet font resolution or missing OpenType tables.
    """
    if "setPointSize" in message and "<= 0" in message:
        return
    if "qt.text.font.db" in message or "OpenType support missing" in message:
        return
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


try:
    QtCore.qInstallMessageHandler(_clean_qt_message_handler)
except Exception:
    pass

