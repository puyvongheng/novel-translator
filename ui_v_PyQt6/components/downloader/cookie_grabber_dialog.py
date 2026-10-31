"""
Built-in Browser Cookie Grabber Dialog for PyQt6 / PySide6
Safely captures Douyin, TikTok, Bilibili session cookies and tokens (e.g. s_v_web_id, ttwid)
directly inside the application using embedded Chromium (QWebEngineView).
Eliminates the security risk of third-party browser extensions.
"""

import os
from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, Qt, QTimer, QMessageBox
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineProfile
    from PySide6.QtNetwork import QNetworkCookie
    from PySide6.QtCore import QUrl
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False


def cookie_to_netscape_format(cookie: "QNetworkCookie") -> str:
    """Formats a QNetworkCookie object into a standard Netscape cookies.txt row."""
    domain = cookie.domain()
    flag = "TRUE" if domain.startswith(".") else "FALSE"
    path = cookie.path() or "/"
    secure = "TRUE" if cookie.isSecure() else "FALSE"
    expires = int(cookie.expirationDate().toSecsSinceEpoch()) if not cookie.isSessionCookie() else 0
    name = bytes(cookie.name()).decode("utf-8", errors="ignore")
    value = bytes(cookie.value()).decode("utf-8", errors="ignore")
    return f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}"


class CookieGrabberDialog(QDialog):
    """
    Embedded Browser Dialog that automatically intercepts cookies from Douyin / TikTok / etc.
    and exports them safely to cookies.txt without third-party browser extensions.
    """

    def __init__(self, parent=None, initial_url: str = "https://www.douyin.com", on_cookies_saved=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Built-in Browser Cookie & Token Grabber (ចាប់យក Cookies ស្វ័យប្រវត្ត)")
        self.resize(1020, 720)
        self.setMinimumSize(800, 560)
        self.on_cookies_saved = on_cookies_saved
        self.initial_url = initial_url
        self.cookies_map = {}  # (domain, name) -> QNetworkCookie

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # ── TOP BAR: Header & Status ──
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        # Navigation buttons
        self.btn_back = QPushButton("◀")
        self.btn_back.setFixedWidth(34)
        self.btn_back.clicked.connect(self._go_back)
        top_bar.addWidget(self.btn_back)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setFixedWidth(34)
        self.btn_forward.clicked.connect(self._go_forward)
        top_bar.addWidget(self.btn_forward)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setFixedWidth(34)
        self.btn_refresh.clicked.connect(self._reload_page)
        top_bar.addWidget(self.btn_refresh)

        # URL address bar
        self.entry_url = QLineEdit(self.initial_url)
        self.entry_url.setStyleSheet("font-family: Consolas; font-size: 11px; padding: 4px 8px;")
        self.entry_url.returnPressed.connect(self._navigate_url)
        top_bar.addWidget(self.entry_url, 1)

        btn_go = QPushButton("Go")
        btn_go.clicked.connect(self._navigate_url)
        top_bar.addWidget(btn_go)

        # Cookie badge status
        self.lbl_cookie_badge = QLabel("🍪 Cookies: 0")
        self.lbl_cookie_badge.setStyleSheet(
            "background-color: #1e293b; color: #38bdf8; font-weight: bold; padding: 4px 10px; border-radius: 4px;"
        )
        top_bar.addWidget(self.lbl_cookie_badge)

        self.lbl_token_status = QLabel("⏳ Initializing...")
        self.lbl_token_status.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        top_bar.addWidget(self.lbl_token_status)

        # Save Action Button
        self.btn_save = QPushButton("💾 Save & Apply Cookies (រក្សាទុក)")
        self.btn_save.setObjectName("btn_primary")
        self.btn_save.setStyleSheet(
            "background-color: #0284c7; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_save.clicked.connect(self._save_cookies)
        top_bar.addWidget(self.btn_save)

        layout.addLayout(top_bar)

        # ── BROWSER VIEW (QWebEngineView) ──
        if WEBENGINE_AVAILABLE:
            from ui_v_PyQt6.components.downloader.media_browser_dialog import setup_html5_media_profile, get_shared_persistent_profile
            from PySide6.QtWebEngineCore import QWebEnginePage
            self.web_view = QWebEngineView(self)
            profile = get_shared_persistent_profile()
            if profile:
                self.web_view.setPage(QWebEnginePage(profile, self.web_view))
            else:
                profile = self.web_view.page().profile()
                setup_html5_media_profile(profile)

            self.cookie_store = profile.cookieStore()
            self.cookie_store.cookieAdded.connect(self._on_cookie_added)
            self.web_view.urlChanged.connect(self._on_url_changed)
            self.web_view.loadFinished.connect(self._on_load_finished)
            self.web_view.setUrl(QUrl(self.initial_url))
            layout.addWidget(self.web_view, 1)
        else:
            lbl_err = QLabel("⚠️ PySide6 QtWebEngine is not available on this Python installation.")
            lbl_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_err.setStyleSheet("color: #ef4444; font-size: 14px;")
            layout.addWidget(lbl_err, 1)

        # ── BOTTOM BAR: Instructions ──
        bot_bar = QHBoxLayout()
        lbl_hint = QLabel(
            "💡 របៀបប្រើប្រាស់៖ បើកទំព័រ Douyin ខាងលើនេះ (ឬចុចលើវីដេអូណាមួយ) ប្រព័ន្ធនឹងស្ទាក់ចាប់យក Cookies/Token "
            "ដោយសុវត្ថិភាព។ នៅពេលឃើញពាក្យ 'Ready' សូមចុចប៊ូតុង 'Save & Apply Cookies'!"
        )
        lbl_hint.setStyleSheet("color: #34d399; font-size: 11px;")
        lbl_hint.setWordWrap(True)
        bot_bar.addWidget(lbl_hint, 1)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        bot_bar.addWidget(btn_close)
        layout.addLayout(bot_bar)

    def _on_cookie_added(self, cookie: "QNetworkCookie"):
        """Triggered whenever a cookie is set by the browser."""
        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        domain = cookie.domain()
        self.cookies_map[(domain, name)] = cookie

        total = len(self.cookies_map)
        self.lbl_cookie_badge.setText(f"🍪 Cookies: {total}")

        # Check for key Douyin security cookies
        has_sv_web_id = any(k[1] == "s_v_web_id" for k in self.cookies_map.keys())
        has_ttwid = any(k[1] == "ttwid" for k in self.cookies_map.keys())
        has_signature = any(k[1] == "__ac_signature" for k in self.cookies_map.keys())

        if has_sv_web_id:
            self.lbl_token_status.setText("🟢 s_v_web_id & ttwid Ready!")
            self.lbl_token_status.setStyleSheet("color: #10b981; font-weight: bold;")
        elif has_ttwid or has_signature:
            self.lbl_token_status.setText("🟡 Capturing session...")
            self.lbl_token_status.setStyleSheet("color: #f59e0b; font-weight: bold;")

    def _on_url_changed(self, url: "QUrl"):
        self.entry_url.setText(url.toString())

    def _on_load_finished(self, ok: bool):
        if ok:
            total = len(self.cookies_map)
            has_sv = any(k[1] == "s_v_web_id" for k in self.cookies_map.keys())
            if has_sv:
                self.lbl_token_status.setText(f"✅ Ready! ({total} cookies)")
            else:
                self.lbl_token_status.setText(f"ℹ️ Loaded ({total} cookies). Click a video if s_v_web_id is needed.")

    def _go_back(self):
        if hasattr(self, "web_view"):
            self.web_view.back()

    def _go_forward(self):
        if hasattr(self, "web_view"):
            self.web_view.forward()

    def _reload_page(self):
        if hasattr(self, "web_view"):
            self.web_view.reload()

    def _navigate_url(self):
        raw = self.entry_url.text().strip()
        if raw and hasattr(self, "web_view"):
            if not raw.startswith("http://") and not raw.startswith("https://"):
                raw = "https://" + raw
            self.web_view.setUrl(QUrl(raw))

    def _save_cookies(self):
        """Exports captured cookies to Netscape cookies.txt and triggers callback."""
        if not self.cookies_map:
            QMessageBox.warning(self, "No Cookies", "មិនទាន់ចាប់បាន Cookies ណាមួយនៅឡើយទេ! សូមរង់ចាំឱ្យទំព័រដំណើរការចប់សិន។")
            return

        out_path = os.path.abspath("cookies.txt")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Safely captured by AI Khmer Movie Studio Built-in Browser\n")
                f.write("# https://github.com/puyvongheng/novel-translator\n\n")
                for cookie in self.cookies_map.values():
                    f.write(cookie_to_netscape_format(cookie) + "\n")

            # Also save to downloads folder if it exists
            if os.path.exists("downloads"):
                dl_path = os.path.abspath(os.path.join("downloads", "cookies.txt"))
                with open(dl_path, "w", encoding="utf-8") as f:
                    f.write("# Netscape HTTP Cookie File\n\n")
                    for cookie in self.cookies_map.values():
                        f.write(cookie_to_netscape_format(cookie) + "\n")

            total = len(self.cookies_map)
            QMessageBox.information(
                self,
                "Cookies Saved",
                f"🎉 បានចាប់យក និងរក្សាទុក Cookies ចំនួន {total} ដោយជោគជ័យ!\n\n"
                f"📁 ទីតាំង: {out_path}\n"
                f"ឥឡូវនេះអ្នកអាចទាញយកវីដេអូបានដោយសេរី មិនបាច់ប្រើ Extension ឡើយ!"
            )

            if self.on_cookies_saved:
                self.on_cookies_saved(out_path, total)

            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error Saving", f"មិនអាចរក្សាទុក Cookies បានទេ: {e}")

    def done(self, r):
        try:
            if hasattr(self, "cookie_store") and self.cookie_store:
                self.cookie_store.cookieAdded.disconnect(self._on_cookie_added)
        except Exception:
            pass
        super().done(r)

    def closeEvent(self, event):
        try:
            if hasattr(self, "cookie_store") and self.cookie_store:
                self.cookie_store.cookieAdded.disconnect(self._on_cookie_added)
        except Exception:
            pass
        super().closeEvent(event)
