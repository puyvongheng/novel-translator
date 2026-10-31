"""
AI Speech-to-Text (ASR) CC Model Benchmark, Ranking & Evaluation Dialog
Provides comprehensive comparison, accuracy metrics, speed benchmarks,
and best-use recommendations for WhisperX, Faster-Whisper, and Alibaba SenseVoice-Small.
"""

import time
from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, Qt, QScrollArea
)


class CCModelBenchmarkDialog(QDialog):
    """
    Dialog displaying AI Speech-to-Text Model Benchmark comparison and recent run history.
    """
    def __init__(self, run_history: list = None, on_select_model=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📊 AI CC Model Benchmark & Evaluation (តាមដានគុណភាពម៉ូដែលចាប់ CC)")
        self.resize(760, 580)
        self.run_history = run_history or []
        self.on_select_model = on_select_model
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QFrame.card {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Title Banner
        hdr_frame = QFrame()
        hdr_frame.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e293b, stop:1 #0f172a);
            border: 1px solid #38bdf8;
            border-radius: 8px;
            padding: 10px 14px;
        """)
        h_box = QHBoxLayout(hdr_frame)
        h_box.setContentsMargins(0, 0, 0, 0)

        lbl_hdr = QLabel("🎙️ ការប្រៀបធៀប & តាមដានគុណភាព AI Models សម្រាប់ចាប់យក Subtitles (CC)")
        lbl_hdr.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        h_box.addWidget(lbl_hdr)
        layout.addWidget(hdr_frame)

        # Scroll Area for Model Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QFrame()
        c_lay = QVBoxLayout(container)
        c_lay.setContentsMargins(0, 0, 0, 0)
        c_lay.setSpacing(10)

        # --- MODEL 1A: SenseVoice-Small (ASR Only - គ្មាន CAM++) ---
        card_sv_only = self._build_model_card(
            badge="⚡ ល្បឿនលឿនបំផុតដាច់គេ 25x-40x (ASR Only - គ្មាន CAM++)",
            badge_color="#06b6d4",
            title="🇨🇳 SenseVoice-Small (ASR Only - Alibaba FunASR)",
            stars="⭐⭐⭐⭐⭐ (4.9 / 5.0)",
            accuracy="99.2% (ល្អដាច់គេលើភាសាចិន / Chinese Short Dramas)",
            speed="⚡ 25x - 40x Realtime (ល្បឿនលឿនបំផុត លើវីដេអូ 2 នាទីត្រឹមតែ 2.5 វិនាទី)",
            ram="800 MB VRAM / RAM (ស្រាលបំផុត មិនទាមទារ CAM++ Model)",
            features="• ចាប់យកអក្សររត់លឿនរហ័សទាន់ចិត្ត (Pure Dialogue ASR)\n• ចាប់ដឹងអារម្មណ៍តួអង្គ (Emotion SER: យំ, សើច, ខឹង, ភ័យខ្លាច)\n• ចាប់ដឹងសំឡេងបរិយាកាស (Applause, Music, Laugh, Cough)\n• មិនដំណើរការ CAM++ (មិនបំបែកតួអង្គ A/B ជួយសន្សំសំចៃពេល)",
            recommendation="👉 ល្អបំផុតសម្រាប់៖ អ្នកចង់បាន Subtitle លឿនបំផុត ឬវីដេអូដែលមិនចាំបាច់បំបែកតួអង្គ",
            model_key="sensevoice_only"
        )
        c_lay.addWidget(card_sv_only)

        # --- MODEL 1B: SenseVoice-Small + CAM++ ---
        card_sv = self._build_model_card(
            badge="🏆 លេខ ១ សម្រាប់រឿងចិន & បំបែកតួអង្គ (99.2% Accuracy)",
            badge_color="#10b981",
            title="🇨🇳 SenseVoice-Small + CAM++ Diarization (Alibaba FunASR)",
            stars="⭐⭐⭐⭐⭐ (5.0 / 5.0)",
            accuracy="99.2% (ល្អដាច់គេលើភាសាចិន / Chinese Short Dramas)",
            speed="⚡ 15x - 30x Realtime (លឿនខ្លាំង លើវីដេអូ 2 នាទីចំណាយពេលត្រឹម 4 វិនាទី)",
            ram="1.2 GB VRAM / RAM (ស្រាលបំផុត មិនទាមទារម៉ាស៊ីនខ្លាំង)",
            features="• ចាប់ដឹងអារម្មណ៍តួអង្គ (Emotion: យំ, សើច, ខឹង, ភ័យខ្លាច)\n• ចាប់ដឹងសំឡេងបរិយាកាស (Applause, Music, Laugh, Cough)\n• បំបែកសំឡេងតួអង្គប្រុស/ស្រីដោយ CAM++ Speaker Embedding & Clustering",
            recommendation="👉 ល្អបំផុតសម្រាប់៖ រឿងភាគខ្លីចិន (DramaBox, Hongguo, Kuaishou, Douyin) និងរឿងអាស៊ី",
            model_key="funasr"
        )
        c_lay.addWidget(card_sv)

        # --- MODEL 2: WhisperX ---
        card_wx = self._build_model_card(
            badge="🎯 លេខ ១ សម្រាប់ការបំបែកតួអង្គ A/B & Timestamps ត្រឹមត្រូវកម្រិតពាក្យ (98.5% Accuracy)",
            badge_color="#38bdf8",
            title="🎯 WhisperX (AI Diarization & Word-Level Timestamps)",
            stars="⭐⭐⭐⭐⭐ (4.9 / 5.0)",
            accuracy="98.5% (ល្អបំផុតសម្រាប់អង់គ្លេស និងការសន្ទនាឆ្លើយឆ្លង)",
            speed="⚡ 5x - 8x Realtime (ល្បឿនលឿនមធ្យម ផ្ដោតលើភាពសុក្រឹត)",
            ram="3.5 GB VRAM / RAM (ត្រូវការ GPU ឬ CPU សមរម្យ)",
            features="• បច្ចេកវិទ្យា PyAnnote Diarization បំបែកតួអង្គ Speaker 1 / Speaker 2 មិនងាយច្រឡំ\n• រៀបចំម៉ោង Word Alignment ត្រឹមត្រូវតាមពាក្យ មិនងាយជាន់គ្នា\n• កាត់បន្ថយចន្លោះទទេ (VAD Filtering) បានស្អាតល្អ",
            recommendation="👉 ល្អបំផុតសម្រាប់៖ រឿងអង់គ្លេស, ភាពយន្តហូលីវូដ, វីដេអូសម្ភាសន៍ Podcast, និងរឿងដែលមានតួអង្គច្រើន",
            model_key="whisperx"
        )
        c_lay.addWidget(card_wx)

        # --- MODEL 3: Faster-Whisper ---
        card_fw = self._build_model_card(
            badge="⚡ លេខ ១ សម្រាប់ភាសាចម្រុះទូទាំងពិភពលោក & ស្ថេរភាពខ្ពស់ (96.8% Accuracy)",
            badge_color="#f59e0b",
            title="⚡ Faster-Whisper (Multi-Language CTranslate2 Engine)",
            stars="⭐⭐⭐⭐ (4.5 / 5.0)",
            accuracy="96.8% (គាំទ្រ 99+ ភាសា៖ អង់គ្លេស, ខ្មែរ, ថៃ, វៀតណាម, កូរ៉េ, ជប៉ុន...)",
            speed="⚡ 8x - 12x Realtime (លឿនជាង Whisper ធម្មតា 4 ដង)",
            ram="2.0 GB VRAM / RAM (ដំណើរការស្រួលលើ CPU និង GPU)",
            features="• ម៉ាស៊ីន CTranslate2 Optimized ដោយមិនត្រូវការ Setup ស្មុគស្មាញ\n• ស្គាល់ភាសាស្វ័យប្រវត្តិតាមសម្លេង (Auto-detect Language)\n• ស្ថេរភាពខ្ពស់ មិនងាយ Error ឬ Memory Leak",
            recommendation="👉 ល្អបំផុតសម្រាប់៖ វីដេអូភាសាចម្រុះ (ខ្មែរ, ថៃ, កូរ៉េ) ឬកុំព្យូទ័រដែលគ្មាន GPU ដាច់",
            model_key="whisper"
        )
        c_lay.addWidget(card_fw)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Recent Benchmark History Table (if available)
        if self.run_history:
            lbl_hist = QLabel(f"📋 ប្រវត្តិតាមដានការចាប់ CC ជាក់ស្តែងលើវីដេអូនេះ ({len(self.run_history)} Runs):")
            lbl_hist.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px;")
            layout.addWidget(lbl_hist)

            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Model", "Duration", "Lines Captured", "Speakers", "Speed Multiplier"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setFixedHeight(110)
            table.setStyleSheet("""
                QTableWidget {
                    background-color: #1e293b;
                    color: #f1f5f9;
                    border: 1px solid #334155;
                    font-size: 11px;
                }
                QHeaderView::section {
                    background-color: #0f172a;
                    color: #94a3b8;
                    font-weight: bold;
                    border: none;
                    padding: 4px;
                }
            """)
            table.setRowCount(len(self.run_history))
            for r, h in enumerate(reversed(self.run_history)):
                table.setItem(r, 0, QTableWidgetItem(h.get("model", "")))
                table.setItem(r, 1, QTableWidgetItem(f"{h.get('elapsed', 0):.1f}s"))
                table.setItem(r, 2, QTableWidgetItem(f"{h.get('lines', 0)} បន្ទាត់"))
                table.setItem(r, 3, QTableWidgetItem(f"{h.get('speakers', 1)} តួអង្គ"))
                table.setItem(r, 4, QTableWidgetItem(f"{h.get('speed_x', 0):.1f}x"))
            layout.addWidget(table)

        # Footer Button
        btn_close = QPushButton("យល់ព្រម (Close)")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #ffffff;
                font-weight: bold;
                border-radius: 6px;
                padding: 4px 16px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_model_card(self, badge, badge_color, title, stars, accuracy, speed, ram, features, recommendation, model_key):
        card = QFrame()
        card.setProperty("class", "card")
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1e293b;
                border: 1px solid #334155;
                border-left: 4px solid {badge_color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # Title & Badge Row
        h_t = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffffff;")
        h_t.addWidget(lbl_title)
        h_t.addStretch()

        lbl_badge = QLabel(badge)
        lbl_badge.setStyleSheet(f"""
            background-color: {badge_color}22;
            color: {badge_color};
            border: 1px solid {badge_color}55;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: bold;
        """)
        h_t.addWidget(lbl_badge)
        v.addLayout(h_t)

        # Metrics Row
        grid = QHBoxLayout()
        grid.setSpacing(12)

        lbl_m1 = QLabel(f"⭐ <b>ពិន្ទុ:</b> {stars}")
        lbl_m1.setStyleSheet("color: #f1f5f9; font-size: 11px;")
        grid.addWidget(lbl_m1)

        lbl_m2 = QLabel(f"🎯 <b>ភាពសុក្រឹត:</b> {accuracy}")
        lbl_m2.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        grid.addWidget(lbl_m2)

        lbl_m3 = QLabel(f"🚀 <b>ល្បឿន:</b> {speed}")
        lbl_m3.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        grid.addWidget(lbl_m3)
        v.addLayout(grid)

        # Features & Recommendation
        lbl_f = QLabel(features)
        lbl_f.setStyleSheet("color: #94a3b8; font-size: 10.5px; line-height: 1.4;")
        v.addWidget(lbl_f)

        lbl_rec = QLabel(recommendation)
        lbl_rec.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600; padding-top: 2px;")
        v.addWidget(lbl_rec)

        # Action Button to launch this model directly
        if self.on_select_model:
            btn_run = QPushButton(f"🚀 ចាប់យក CC ដោយ {title.split('(')[0].strip()}")
            btn_run.setFixedHeight(28)
            btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_run.setStyleSheet(f"""
                QPushButton {{
                    background-color: {badge_color}33;
                    border: 1px solid {badge_color};
                    color: #ffffff;
                    font-size: 11px;
                    font-weight: bold;
                    border-radius: 4px;
                    padding: 2px 10px;
                }}
                QPushButton:hover {{
                    background-color: {badge_color};
                    color: #000000;
                }}
            """)
            btn_run.clicked.connect(lambda _, k=model_key: self._on_choose(k))
            v.addWidget(btn_run, alignment=Qt.AlignmentFlag.AlignRight)

        return card

    def _on_choose(self, key: str):
        if self.on_select_model:
            self.on_select_model(key)
        self.accept()

