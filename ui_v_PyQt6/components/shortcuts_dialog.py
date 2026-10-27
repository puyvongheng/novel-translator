"""
Studio Keyboard Shortcuts Modal Dialog (FilmCraft / CapCut / Premiere Style)
Provides an elegant, categorized visual cheat sheet of all studio keyboard controls.
"""

from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QWidget, Qt, QFont
)

class KeyboardShortcutsDialog(QDialog):
    """
    Studio Keyboard Shortcuts visual guide.
    Displays grouped keyboard hotkeys with styled keycaps (<kbd>).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⌨️ Studio Keyboard Shortcuts (គ្រាប់ចុចកាត់)")
        self.resize(760, 620)
        self.setMinimumSize(640, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0e1218;
                color: #e2e8f0;
                font-family: 'Segoe UI', sans-serif;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
            QFrame.shortcut-card {
                background-color: #161b24;
                border: 1px solid #232d3d;
                border-radius: 8px;
                padding: 12px;
            }
            QLabel.group-title {
                color: #38bdf8;
                font-size: 13px;
                font-weight: 700;
                padding-bottom: 6px;
                border-bottom: 1px solid #232d3d;
            }
            QLabel.key-badge {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2d3748, stop:1 #1e2532);
                color: #ffffff;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                font-weight: 700;
                border: 1px solid #4a5568;
                border-radius: 4px;
                padding: 3px 8px;
            }
            QLabel.action-desc {
                color: #cbd5e1;
                font-size: 12px;
            }
            QPushButton#btn_close {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                border-radius: 6px;
                padding: 8px 24px;
            }
            QPushButton#btn_close:hover {
                background-color: #0369a1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Title
        h_layout = QHBoxLayout()
        icon_lbl = QLabel("⌨️")
        icon_lbl.setStyleSheet("font-size: 26px;")
        h_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("FilmCraft Studio - Keyboard Shortcuts (គ្រាប់ចុចកាត់ទាំងអស់)")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        lbl_subtitle = QLabel("ប្រើគ្រាប់ចុចកាត់នៅលើ Keyboard ដើម្បីកាត់ត ចាក់វីដេអូ និងកែសម្រួលអក្សររត់បានរហ័ស 60 FPS")
        lbl_subtitle.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_subtitle)
        h_layout.addLayout(title_box, 1)

        layout.addLayout(h_layout)

        # Scroll Area for shortcut categories
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_w = QWidget()
        c_layout = QVBoxLayout(content_w)
        c_layout.setContentsMargins(0, 0, 8, 0)
        c_layout.setSpacing(12)

        # CATEGORY 1: Playback & Transport
        cat1 = [
            ("Space", "ចាក់ ឬ ផ្អាកវីដេអូ (Play / Pause toggle)"),
            ("←  /  →", "ថយក្រោយ ឬ ទៅមុខ 2 វិនាទី (Seek ±2s)"),
            ("Shift + ←  /  →", "ថយក្រោយ ឬ ទៅមុខលឿន 5 វិនាទី (Fast Seek ±5s)"),
            ("Ctrl + ←  /  →", "ថយក្រោយ ឬ ទៅមុខម្ដង 1 Frame (Step 1 frame)"),
            ("Home  /  End", "លោតទៅដើមវីដេអូ 00:00:00 ឬ ទៅចុងបញ្ចប់ (Jump Start / End)"),
            ("J  /  K  /  L", "ថយក្រោយ (J) / ផ្អាក (K) / លេងបង្កើនល្បឿន 1x, 1.25x, 1.5x, 2x (L)"),
        ]
        c_layout.addWidget(self._create_category_card("🎬 ចាក់ និងរំកិលវីដេអូ (Playback & Transport)", cat1))

        # CATEGORY 2: Volume & Audio Controls
        cat2 = [
            ("↑  /  ↓", "បង្កើន ឬ បន្ថយសំឡេង Master Volume ±5%"),
            ("M", "បិទ ឬ បើកសំឡេងវីដេអូ / Voice Dubbing (Toggle Mute)"),
        ]
        c_layout.addWidget(self._create_category_card("🔊 សំឡេង និងការគ្រប់គ្រង (Audio & Volume)", cat2))

        # CATEGORY 3: Timeline & Clip Editing Tools
        cat3 = [
            ("S  (ឬ  C)", "កាត់ Clip / Subtitle ត្រង់ទីតាំង Cursor (Split at Playhead)"),
            ("I", "កំណត់ចំណុចចាប់ផ្ដើម Mark In (Mark In Point)"),
            ("O", "កំណត់ចំណុចបញ្ចប់ Mark Out (Mark Out Point)"),
            ("Alt + X", "លុបកំណត់ផ្នែក Mark In / Out ចោល (Clear In/Out)"),
            ("Shift + Delete  (ឬ X)", "លុបផ្នែកមួយ ហើយបិទចន្លោះដោយស្វ័យប្រវត្តិ (Ripple Delete)"),
            ("[  /  ]  (ឬ PgUp / PgDn)", "លោតទៅបន្ទាត់អក្សររត់មុន ឬ បន្ទាប់ (Jump Prev / Next Subtitle)"),
            ("Delete  /  Backspace", "លុប Clip, អក្សររត់ ឬ Sticker/Overlay ដែលបានរើស"),
        ]
        c_layout.addWidget(self._create_category_card("✂️ កាត់ត និងបន្ទាត់ពេលវេលា (Timeline & Clip Editing)", cat3))

        # CATEGORY 4: Project, Files & History
        cat4 = [
            ("Ctrl + O", "បើកឯកសារវីដេអូ (Open Video File)"),
            ("Ctrl + S", "រក្សាទុក និងនាំចេញឯកសារអក្សររត់ (Export / Save SRT)"),
            ("Ctrl + I", "នាំចូលឯកសារអក្សររត់ SRT ពីខាងក្រៅ (Import SRT)"),
            ("Ctrl + E", "បើកផ្ទាំងនាំចេញវីដេអូធំ (Master Export Movie Dialog)"),
            ("Ctrl + Z", "មិនធ្វើវិញ ឬ ត្រឡប់ក្រោយ (Undo Action)"),
            ("Ctrl + Y  (ឬ Ctrl+Shift+Z)", "ធ្វើសកម្មភាពឡើងវិញ (Redo Action)"),
        ]
        c_layout.addWidget(self._create_category_card("📁 គម្រោង និងឯកសារ (Project, Files & Undo)", cat4))

        # CATEGORY 5: View, Display & Helpers
        cat5 = [
            ("F", "បើក / បិទ ពេញអេក្រង់វីដេអូ (Toggle Fullscreen Monitor)"),
            ("T", "បង្ហាញ ឬ លាក់ផ្ទាំងបន្ទាត់ពេលវេលា (Toggle Timeline Panel)"),
            ("Ctrl + +  /  Ctrl + -", "ពង្រីក ឬ បង្រួមទំហំអក្សរ UI (Global Studio Zoom)"),
            ("Ctrl + 0", "កំណត់ទំហំអក្សរ UI ទៅដើមវិញ 100% (Reset Zoom)"),
            ("F1  (ឬ  ?)", "បើកមើលផ្ទាំងគ្រាប់ចុចកាត់នេះ (Show Shortcuts Guide)"),
        ]
        c_layout.addWidget(self._create_category_card("🖥️ ទិដ្ឋភាព និងជំនួយ (View, Panels & Zoom)", cat5))

        scroll.setWidget(content_w)
        layout.addWidget(scroll, 1)

        # Bottom Action Bar
        b_layout = QHBoxLayout()
        tip_lbl = QLabel("💡 <i>ចំណាំ: គ្រាប់ចុចកាត់ដំណើរការគ្រប់ពេលលើកលែងតែពេលកំពុងវាយបញ្ចូលអក្សរក្នុងប្រអប់អត្ថបទ។</i>")
        tip_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        b_layout.addWidget(tip_lbl)
        b_layout.addStretch()

        btn_close = QPushButton("យល់ព្រម (Close)")
        btn_close.setObjectName("btn_close")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        b_layout.addWidget(btn_close)

        layout.addLayout(b_layout)

    def _create_category_card(self, title: str, items: list) -> QFrame:
        card = QFrame()
        card.setProperty("class", "shortcut-card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        lbl_title = QLabel(title)
        lbl_title.setProperty("class", "group-title")
        layout.addWidget(lbl_title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(4, 4, 4, 4)

        for row, (key_str, desc_str) in enumerate(items):
            lbl_key = QLabel(key_str)
            lbl_key.setProperty("class", "key-badge")
            lbl_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_key.setMinimumWidth(110)

            lbl_desc = QLabel(desc_str)
            lbl_desc.setProperty("class", "action-desc")

            grid.addWidget(lbl_key, row, 0)
            grid.addWidget(lbl_desc, row, 1)

        layout.addLayout(grid)
        return card
