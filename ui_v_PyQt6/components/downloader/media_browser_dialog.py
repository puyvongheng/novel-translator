"""
Built-in Media Browser & Smart Video Sniffer Dialog for PyQt6 / PySide6 Desktop Studio
Advanced Network Processing, Media, Subtitles & Context Menu Interceptor:
1. Embedded Chromium browser with HTML5 compatibility (Bilibili, Douyin, YouTube, Facebook, TikTok).
2. Right-Click Context Menu (Mouse ស្ដាំ):
   - 📥 Download This Video (ទាញយកវីដេអូនេះ)
   - 🎯 Catch Video URL (ចាប់យក Link វីដេអូ)
   - 📋 Copy Clean Video Link (ចម្លង Link ស្អាត)
   - 📡 Inspect Network Streams & CC (មើលតារាង Network)
3. Floating Catch Link Button: Instant one-click button to sniff current video while watching.
4. Active Video Play Event Listener: Sniffs video URLs when video starts playing or is clicked.
5. Full Support for Bilibili (/zh-Hans/video/BV..., /video/BV..., /video/av...).
6. Real-time Network Request Interceptor (.mp4, .m3u8, .m4s, .webm, .flv, .mp3, .m4a, CC/Subtitles).
7. Automatic Cookie & Session Capture.
"""

import os
import re
import shutil
import subprocess
import urllib.request
from ui_v_PyQt6.qt_compat import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, Qt, QTimer, QMessageBox, QFrame, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QMenu, QAction, QColor, QIcon, QSize, QScrollArea
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import (
        QWebEngineProfile, QWebEnginePage, QWebEngineSettings, QWebEngineScript,
        QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestInfo
    )
    from PySide6.QtNetwork import QNetworkCookie
    from PySide6.QtCore import QUrl, Signal
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False


CHROME_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# JavaScript Polyfill to bypass "您当前的浏览器不支持 HTML5 播放器" on Bilibili, Douyin, etc.
# hook into video play events, and bypass hidden videos/iframes on Sabayflix, KH Diamond, etc.
HTML5_POLYFILL_JS = """
(function() {
    // 1. Force canPlayType to report 'probably' for modern codecs (H.264, AAC, MP4, WebM)
    var origCanPlay = HTMLMediaElement.prototype.canPlayType;
    HTMLMediaElement.prototype.canPlayType = function(type) {
        if (!type) return '';
        var t = type.toLowerCase();
        if (t.indexOf('mp4') !== -1 || t.indexOf('avc1') !== -1 || t.indexOf('h264') !== -1 ||
            t.indexOf('m4a') !== -1 || t.indexOf('webm') !== -1 || t.indexOf('vp9') !== -1 ||
            t.indexOf('vp8') !== -1 || t.indexOf('aac') !== -1 || t.indexOf('mp3') !== -1 ||
            t.indexOf('ogg') !== -1 || t.indexOf('flv') !== -1 || t.indexOf('hls') !== -1 ||
            t.indexOf('mpegurl') !== -1) {
            return 'probably';
        }
        return origCanPlay ? origCanPlay.call(this, type) : 'maybe';
    };

    // 2. Polyfill MediaSource.isTypeSupported
    if (window.MediaSource) {
        var origIsTypeSupported = MediaSource.isTypeSupported;
        MediaSource.isTypeSupported = function(type) {
            if (!type) return false;
            var t = type.toLowerCase();
            if (t.indexOf('mp4') !== -1 || t.indexOf('avc1') !== -1 || t.indexOf('h264') !== -1 ||
                t.indexOf('m4a') !== -1 || t.indexOf('webm') !== -1 || t.indexOf('vp9') !== -1 ||
                t.indexOf('mp4a') !== -1 || t.indexOf('aac') !== -1 || t.indexOf('hls') !== -1 ||
                t.indexOf('mpegurl') !== -1) {
                return true;
            }
            return origIsTypeSupported ? origIsTypeSupported.call(this, type) : true;
        };
    }

    // 3. Remove webdriver bot flag
    try {
        Object.defineProperty(navigator, 'webdriver', { get: function() { return undefined; } });
    } catch(e) {}

    // 4. Force Bilibili HTML5 player mode in localStorage and cookie
    try {
        localStorage.setItem('bpx_player_profile', JSON.stringify({mediaType: 'mp4', defaultType: 'mp4', p2p: false}));
        localStorage.setItem('recommend_auto_play', 'open');
        localStorage.setItem('bilibili_player_settings', JSON.stringify({
            video_status: { panoramic: false, danmaku: true, auto_play: true },
            video_player: { player_type: 1 }
        }));
    } catch(e) {}

    // 5. Intercept fetch & XMLHttpRequest to capture all media streams
    window.__captured_media_streams__ = window.__captured_media_streams__ || [];
    function _recordStream(u, dur) {
        if (!u || typeof u !== 'string') return;
        var ul = u.toLowerCase();
        if (ul.indexOf('.m4s') !== -1 || ul.indexOf('bilivideo') !== -1 || 
            ul.indexOf('.mp4') !== -1 || ul.indexOf('.m3u8') !== -1 ||
            ul.indexOf('szbdyd.com') !== -1 || ul.indexOf('mcdn.bilivideo') !== -1 ||
            ul.indexOf('akamaized.net') !== -1 || ul.indexOf('upos-') !== -1 || ul.indexOf('playurl') !== -1 ||
            ul.indexOf('qznovelvod.com') !== -1 || ul.indexOf('novelquickapp') !== -1 ||
            ul.indexOf('hongguoduanju.com') !== -1 || ul.indexOf('byteimg.com') !== -1 ||
            ul.indexOf('stardusttv.net') !== -1 || ul.indexOf('stardust-tv.com') !== -1 ||
            ul.indexOf('sf-api.net') !== -1 || ul.indexOf('sabayflix') !== -1 ||
            ul.indexOf('khdiamond') !== -1 || ul.indexOf('dooplayer') !== -1 ||
            ul.indexOf('streamtape') !== -1 || ul.indexOf('dood') !== -1 ||
            ul.indexOf('filemoon') !== -1 || ul.indexOf('vidhide') !== -1 ||
            ul.indexOf('iqiyi') !== -1 || ul.indexOf('youku') !== -1 ||
            ul.indexOf('v.qq.com') !== -1 || ul.indexOf('mgtv') !== -1 ||
            ul.indexOf('ixigua') !== -1 || ul.indexOf('kuaishou') !== -1 ||
            ul.indexOf('.mp3') !== -1 || ul.indexOf('.m4a') !== -1 ||
            ul.indexOf('/subtitle') !== -1 || ul.indexOf('timedtext') !== -1) {
            
            var existing = false;
            for (var idx = 0; idx < window.__captured_media_streams__.length; idx++) {
                var it = window.__captured_media_streams__[idx];
                var itu = (typeof it === 'object') ? it.url : it;
                if (itu === u) { existing = true; break; }
            }
            if (!existing) {
                window.__captured_media_streams__.push({url: u, duration: dur || 0});
            }
        }
    }

    // 6. Hook into HTMLMediaElement play & load to catch active video streams + durations (e.g. 3:32 vs 2h:37m)
    var origPlay = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function() {
        try {
            var s = this.currentSrc || this.src;
            var dur = this.duration || 0;
            if (s && typeof s === 'string' && s.indexOf('http') === 0) {
                _recordStream(s, dur);
            }
        } catch(e) {}
        return origPlay ? origPlay.apply(this, arguments) : Promise.resolve();
    };

    var origLoad = HTMLMediaElement.prototype.load;
    HTMLMediaElement.prototype.load = function() {
        try {
            var s = this.currentSrc || this.src;
            var dur = this.duration || 0;
            if (s && typeof s === 'string' && s.indexOf('http') === 0) {
                _recordStream(s, dur);
            }
        } catch(e) {}
        return origLoad ? origLoad.apply(this, arguments) : undefined;
    };

    var origFetch = window.fetch;
    if (origFetch) {
        window.fetch = function(input, init) {
            try {
                var url = (typeof input === 'string') ? input : (input && input.url ? input.url : '');
                _recordStream(url, 0);
            } catch(e) {}
            return origFetch.apply(this, arguments);
        };
    }

    var origXhrOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url) {
        try {
            _recordStream(url ? url.toString() : '', 0);
        } catch(e) {}
        return origXhrOpen.apply(this, arguments);
    };
})();
"""


def setup_html5_media_profile(profile: "QWebEngineProfile"):
    """Configures modern Chromium User-Agent, media autoplay, WebGL and HTML5 polyfill."""
    if not WEBENGINE_AVAILABLE or not profile:
        return

    profile.setHttpUserAgent(CHROME_USER_AGENT)

    s = profile.settings()
    s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, True)

    script = QWebEngineScript()
    script.setName("html5_player_fix")
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(True)
    script.setSourceCode(HTML5_POLYFILL_JS)
    profile.scripts().insert(script)


_SHARED_PERSISTENT_PROFILE = None

def get_shared_persistent_profile() -> "QWebEngineProfile":
    """
    Returns a shared, persistent QWebEngineProfile stored on disk.
    Ensures login sessions, cookies, localStorage (e.g. SabayFlix auth JWT tokens),
    and IndexedDB are saved permanently to disk and never lost when closing the app.
    """
    global _SHARED_PERSISTENT_PROFILE
    if not WEBENGINE_AVAILABLE:
        return None
    if _SHARED_PERSISTENT_PROFILE is None:
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            storage_dir = os.path.join(base_dir, "browser_profile")
            os.makedirs(storage_dir, exist_ok=True)
            cache_dir = os.path.join(storage_dir, "cache")
            os.makedirs(cache_dir, exist_ok=True)

            profile = QWebEngineProfile("ai_khmer_movie_persistent_profile")
            profile.setPersistentStoragePath(storage_dir)
            profile.setCachePath(cache_dir)
            profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
            setup_html5_media_profile(profile)
            _SHARED_PERSISTENT_PROFILE = profile
        except Exception as e:
            print(f"[WebEngineProfile] Fallback to defaultProfile due to: {e}")
            _SHARED_PERSISTENT_PROFILE = QWebEngineProfile.defaultProfile()
    return _SHARED_PERSISTENT_PROFILE


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


def format_duration_str(seconds: float) -> str:
    """Formats seconds into human-readable string like '3:32' or '2h:37m'."""
    if not seconds or seconds <= 0:
        return ""
    total_sec = int(round(seconds))
    hours = total_sec // 3600
    minutes = (total_sec % 3600) // 60
    secs = total_sec % 60
    if hours > 0:
        return f"{hours}h:{minutes:02d}m"
    return f"{minutes}:{secs:02d}"


def clean_video_url(url: str) -> str:
    """Extracts a clean, single video URL for YouTube, Douyin, TikTok, Facebook, Bilibili, Sabayflix, KH Diamond, etc."""
    if not url:
        return ""
    text = url.strip()

    # YouTube: extract clean URL, preserving playlists (e.g. &list=PL...) while stripping auto-mixes (list=RD...)
    if "youtube.com/playlist" in text:
        m = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', text)
        if m:
            return f"https://www.youtube.com/playlist?list={m.group(1)}"
        return text
    elif "youtube.com/watch" in text:
        v_m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', text)
        list_m = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', text)
        if list_m and list_m.group(1).startswith("RD"):
            if v_m:
                return f"https://www.youtube.com/watch?v={v_m.group(1)}"
        if v_m and list_m:
            return f"https://www.youtube.com/watch?v={v_m.group(1)}&list={list_m.group(1)}"
        if v_m:
            return f"https://www.youtube.com/watch?v={v_m.group(1)}"
    elif "youtu.be/" in text:
        m = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', text)
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    elif "youtube.com/shorts/" in text:
        m = re.search(r'shorts/([a-zA-Z0-9_-]+)', text)
        if m:
            return f"https://www.youtube.com/shorts/{m.group(1)}"

    # Douyin: normalize modal_id
    if "douyin.com" in text:
        m = re.search(r'[?&]modal_id=(\d+)', text)
        if m:
            return f"https://www.douyin.com/video/{m.group(1)}"
        m2 = re.search(r'modal_id[=/](\d+)', text)
        if m2:
            return f"https://www.douyin.com/video/{m2.group(1)}"

    # Bilibili: clean BV / av URL (supports /zh-Hans/video/BV..., /video/BV..., /video/av...)
    if "bilibili.com" in text:
        m = re.search(r'video/(BV[a-zA-Z0-9]+|av\d+|[a-zA-Z0-9]+)', text)
        if m:
            return f"https://www.bilibili.com/video/{m.group(1)}/"

    # Sabayflix: clean movie URL
    if "sabayflix.net" in text:
        m = re.search(r'sabayflix\.net/movie/([a-zA-Z0-9_-]+)', text)
        if m:
            return f"https://www.sabayflix.net/movie/{m.group(1)}"

    # KH Diamond: clean movie URL
    if "khdiamond.net" in text:
        m = re.search(r'khdiamond\.net/movies/([a-zA-Z0-9_-]+)', text)
        if m:
            return f"https://khdiamond.net/movies/{m.group(1)}/"

    # Hongguo Short Drama: clean player URL
    if "hongguoduanju.com" in text:
        m = re.search(r'hongguoduanju\.com/(?:player|detail)[^/]*?/(\d+(?:/\d+)?)', text)
        if m:
            return f"https://hongguoduanju.com/player/{m.group(1)}"
        m_s = re.search(r'series_id=(\d+)', text)
        if m_s:
            return f"https://hongguoduanju.com/player/{m_s.group(1)}"

    # StardustTV Short Drama: clean episode URL
    if "stardusttv.net" in text:
        m = re.search(r'stardusttv\.net/episodes/([a-zA-Z0-9_-]+)', text)
        if m:
            return f"https://www.stardusttv.net/episodes/{m.group(1)}"

    # Mango TV: clean video URL (strips long tracking query parameters)
    if "mgtv.com" in text:
        m = re.search(r'mgtv\.com/([bv]/[a-zA-Z0-9_/]+\.html)', text)
        if m:
            return f"https://www.mgtv.com/{m.group(1)}"

    # KissKH Asian Drama: clean episode URL (strips pagination and tracking params)
    if "kisskh." in text:
        m = re.search(r'(kisskh\.[a-z]+/Drama/[^?]+(?:\?id=\d+&ep=\d+)?)', text)
        if m:
            return f"https://{m.group(1)}"

    return text


def sanitize_folder_name(name: str) -> str:
    """Sanitizes text to be a safe Windows filename."""
    if not name:
        return "downloaded_media"
    clean = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    clean = re.sub(r'[\r\n\t]+', " ", clean).strip(". ")
    return clean[:70] if clean else "downloaded_media"


def vtt_to_srt(vtt_text: str) -> str:
    """Converts WebVTT, timedtext, or Bilibili JSON string into standard valid SRT format."""
    text_clean = vtt_text.strip()
    
    # 1. Handle Bilibili JSON Subtitles
    if text_clean.startswith("{") and ("body" in text_clean or "subtitles" in text_clean):
        try:
            import json
            from utils.time_utils import format_timestamp
            data = json.loads(text_clean)
            
            # If outer wrapper containing subtitles list
            if "data" in data and isinstance(data["data"], dict) and "subtitles" in data["data"]:
                sub_list = data["data"]["subtitles"]
                if sub_list and isinstance(sub_list, list) and "subtitle_url" in sub_list[0]:
                    sub_url = sub_list[0]["subtitle_url"]
                    if sub_url.startswith("//"):
                        sub_url = "https:" + sub_url
                    req = urllib.request.Request(sub_url, headers={"User-Agent": CHROME_USER_AGENT})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        data = json.loads(r.read().decode("utf-8", errors="replace"))

            body = data.get("body", [])
            if body and isinstance(body, list):
                srt_blocks = []
                for idx, item in enumerate(body, 1):
                    st = format_timestamp(float(item.get("from", 0))).replace(".", ",")
                    et = format_timestamp(float(item.get("to", 0))).replace(".", ",")
                    c = str(item.get("content", "")).strip()
                    if c:
                        srt_blocks.append(f"{idx}\n{st} --> {et}\n{c}\n")
                if srt_blocks:
                    return "\n".join(srt_blocks)
        except Exception:
            pass

    # 2. Handle Standard WebVTT / timedtext
    lines = vtt_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    srt_blocks = []
    cue_idx = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line:
            parts = line.split("-->")
            if len(parts) == 2:
                st = parts[0].strip().replace(".", ",")
                et = parts[1].strip().split(" ")[0].strip().replace(".", ",")
                if st.count(":") == 1:
                    st = "00:" + st
                if et.count(":") == 1:
                    et = "00:" + et

                text_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                    clean_line = re.sub(r'<[^>]+>', '', lines[i].strip())
                    if clean_line:
                        text_lines.append(clean_line)
                    i += 1

                sub_text = "\n".join(text_lines).strip()
                if sub_text:
                    srt_blocks.append(f"{cue_idx}\n{st} --> {et}\n{sub_text}\n")
                    cue_idx += 1
                continue
        i += 1

    return "\n".join(srt_blocks) if srt_blocks else vtt_text


if WEBENGINE_AVAILABLE:
    class SnifferWebEnginePage(QWebEnginePage):
        """Custom Page that silences noisy benign console warnings (preloads, tracking scripts, Firebase analytics)."""
        def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
            noisy = [
                "was preloaded using link preload but not used",
                "a preload for",
                "@firebase/analytics",
                "measurement id",
                "firebase",
                "gsi_logger",
                "credentialscontainer",
                "request credentials mode does not match",
                "identitycredentialrequestoptions",
                "unrecognized feature",
                "missing required parameter: client_id"
            ]
            msg_lower = message.lower()
            if any(k in msg_lower for k in noisy):
                return
            super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)

    class SnifferWebEngineView(QWebEngineView):
        """
        Subclassed Chromium View with Right-Click Context Menu (Mouse ស្ដាំ)
        allowing the user to right-click on any video or page and immediately:
        - Download This Video (ទាញយកវីដេអូនេះ)
        - Catch Video URL (ចាប់យក Link វីដេអូ)
        - Copy Video Link (ចម្លង Link ស្អាត)
        - Open Network Processing Drawer (មើលតារាង Streams)
        """
        sig_download_requested = Signal()
        sig_sniff_requested = Signal()
        sig_copy_requested = Signal()
        sig_open_network = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            profile = get_shared_persistent_profile()
            if profile:
                self.setPage(SnifferWebEnginePage(profile, self))
            else:
                self.setPage(SnifferWebEnginePage(self))

        def contextMenuEvent(self, event):
            menu = self.createStandardContextMenu()
            menu.addSeparator()

            act_sniff = menu.addAction("🎯 ចាប់យក Link វីដេអូនេះ (Catch Video URL)")
            act_sniff.triggered.connect(self.sig_sniff_requested)

            act_dl = menu.addAction("📥 ទាញយកវីដេអូនេះភ្លាម (Download Video Now)")
            act_dl.triggered.connect(self.sig_download_requested)

            act_copy = menu.addAction("📋 ចម្លង Link វីដេអូស្អាត (Copy Clean Video Link)")
            act_copy.triggered.connect(self.sig_copy_requested)

            act_net = menu.addAction("📡 មើលតារាង Network Streams & CC (Open Network Drawer)")
            act_net.triggered.connect(self.sig_open_network)

            menu.exec(event.globalPos())

    class MediaNetworkInterceptor(QWebEngineUrlRequestInterceptor):
        """
        Deep Network Request Sniffer:
        Intercepts all HTTP/HTTPS network traffic initiated by the browser and identifies:
        - Video Streams (.mp4, .m3u8, .mpd, .m4s, .webm, .flv, bilivideo)
        - Audio Streams (.mp3, .m4a, .aac)
        - Subtitles / Closed Captions (timedtext, .vtt, .srt, .ass, .ttml)
        """
        sig_media_intercepted = Signal(str, str, str)  # (url, media_type, domain)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.seen_signatures = set()

        def interceptRequest(self, info: "QWebEngineUrlRequestInfo"):
            url = info.requestUrl().toString()
            if not url or url.startswith("data:") or url.startswith("blob:"):
                return

            # Fake IP / Fake VPN Header Injection (Bypasses Geo-Restriction for Chinese & Global Sites)
            url_lower = url.lower()

            # In-page Floating Tag Button Actions (in web ផ្ទាល់)
            if "agy-sniffer-action.local" in url_lower:
                info.block()
                p = self.parent() if callable(getattr(self, "parent", None)) else None
                if p:
                    if "download" in url_lower and hasattr(p, "_on_download_clicked"):
                        QTimer.singleShot(0, p._on_download_clicked)
                    elif "catch" in url_lower and hasattr(p, "_on_sniff_clicked"):
                        QTimer.singleShot(0, p._on_sniff_clicked)
                return

            # Fake IP / Fake VPN Header Injection (Bypasses Geo-Restriction for Chinese & Global Sites)
            if any(cn in url_lower for cn in ["mgtv.com", "bilibili.com", "iqiyi.com", "youku.com", "v.qq.com", "qq.com", "douyin.com", "ixigua.com", "kuaishou.com", "hongguoduanju.com"]):
                info.setHttpHeader(b"X-Forwarded-For", b"116.228.89.24")
                info.setHttpHeader(b"Client-IP", b"116.228.89.24")
                info.setHttpHeader(b"X-Real-IP", b"116.228.89.24")

            res_type = info.resourceType()
            is_media_res = (res_type == QWebEngineUrlRequestInfo.ResourceType.ResourceTypeMedia)

            media_type = ""

            # 1. Subtitles & Closed Captions (CC)
            if "timedtext" in url_lower:
                lang_match = re.search(r'[?&]lang=([a-zA-Z0-9_-]+)', url)
                lang_code = lang_match.group(1) if lang_match else "auto"
                media_type = f"💬 Subtitle CC (YouTube: {lang_code})"
            elif any(ext in url_lower for ext in [".vtt", ".srt", ".ass", ".ssa", ".ttml", ".dfxp"]):
                if ".vtt" in url_lower:
                    media_type = "💬 Subtitle CC (.vtt)"
                elif ".srt" in url_lower:
                    media_type = "💬 Subtitle (.srt)"
                elif ".ass" in url_lower or ".ssa" in url_lower:
                    media_type = "💬 Subtitle (.ass)"
                else:
                    media_type = "💬 Subtitle (TTML)"
            elif "/subtitle" in url_lower or "/caption" in url_lower or "subtitles" in url_lower or "captions" in url_lower:
                media_type = "💬 Subtitle / CC Stream"

            # 2. Khmer Movie Streams (Sabayflix, KH Diamond, Dooplayer, Kolab Khmer, PhumiKhmer, MerlMovie)
            elif any(k in url_lower for k in [
                "sf-api.net", "sabayflix", "khdiamond", "dooplayer",
                "kolabkhmer", "phumikhmer", "merlmovie"
            ]):
                if any(t in url_lower for t in ["trailer", "preview", "short-clips"]):
                    media_type = "🎞️ Trailer Clip (~3:32)"
                elif ".m3u8" in url_lower or "/stream" in url_lower or "movie" in url_lower:
                    media_type = "🎬 ភាពយន្តពេញ / Full Movie Stream (.m3u8)"
                else:
                    media_type = "🎬 Khmer Movie Stream"

            # 3. China Video & Drama Platforms (iQiyi, Tencent Video, Youku, MangoTV, Xigua, Kuaishou, Hongguo)
            elif any(k in url_lower for k in [
                "iqiyi.com", "qiyi.com", "v.qq.com", "tc.qq.com", "youku.com", "ykimg.com",
                "mgtv.com", "hunantv.com", "ixigua.com", "kuaishou.com", "yximgs.com",
                "qznovelvod.com", "fqnovelstatic"
            ]):
                if "qznovelvod" in url_lower or "novelquickapp" in url_lower:
                    media_type = "🎬 Hongguo Drama (红果短剧)"
                elif "iqiyi" in url_lower or "qiyi" in url_lower:
                    media_type = "🎬 iQiyi Video (爱奇艺)"
                elif "qq.com" in url_lower:
                    media_type = "🎬 Tencent Video (腾讯视频)"
                elif "youku" in url_lower:
                    media_type = "🎬 Youku Video (优酷)"
                elif "mgtv" in url_lower or "hunantv" in url_lower:
                    media_type = "🎬 Mango TV (芒果TV)"
                elif "ixigua" in url_lower:
                    media_type = "🎬 Xigua Video (西瓜视频)"
                elif "kuaishou" in url_lower:
                    media_type = "🎬 Kuaishou Video (快手)"
                else:
                    media_type = "🎬 China Video Stream"

            # 4. Third-Party Movie Embed Servers & KissKH (Streamtape, Doodstream, Filemoon, Vidhide, Mixdrop, KissKH)
            elif any(e in url_lower for e in [
                "streamtape.com", "doodstream", "dood.", "filemoon", "vidhide",
                "mixdrop", "superembed", "upstream", "voe.sx", "googleusercontent.com/videoplayback",
                "kisskh", "cache.kisskh", "stream.kisskh"
            ]):
                if "kisskh" in url_lower:
                    media_type = "🎬 KissKH Asian Drama Stream (.m3u8)"
                else:
                    media_type = "🎬 ភាពយន្តពេញ / Movie Embed Stream"

            # 5. Bilibili Streams (.m4s, bilivideo CDN, mcdn, szbdyd, upos, playurl, akamaized)
            elif any(k in url_lower for k in [
                "bilivideo", ".m4s", "mcdn.bilivideo", "szbdyd.com", "upos-", "acgvideo.com",
                "akamaized.net", "/player/wbi/playurl", "/player/playurl", "/player/v2", "biliapi.net"
            ]):
                if "playurl" in url_lower:
                    media_type = "🎬 Bilibili PlayURL API"
                elif any(a in url_lower for a in ["audio", "-30280", "-30232", "-30216", "-30200", "audio/mp4"]):
                    media_type = "🎵 Bilibili Audio Stream (.m4s)"
                else:
                    media_type = "🎬 Bilibili Video Stream (.m4s)"

            # 6. YouTube Streams (googlevideo)
            elif "googlevideo.com" in url_lower:
                if "mime=audio" in url_lower or "audio" in url_lower:
                    media_type = "🎵 YouTube Audio Stream"
                elif "mime=video" in url_lower:
                    media_type = "🎬 YouTube Video Stream"
                elif is_media_res:
                    media_type = "🎬 YouTube Stream"

            # 6.5 StardustTV Streams (.m3u8, agilecdn-v.stardust-tv.com)
            elif any(k in url_lower for k in ["stardust-tv.com", "stardusttv.net", "agilecdn-v"]):
                if ".m3u8" in url_lower:
                    media_type = "🎬 StardustTV HLS Stream (.m3u8)"
                else:
                    media_type = "🎬 StardustTV Stream"

            # 7. HLS Streams (.m3u8) - common on movie sites, live streams
            elif ".m3u8" in url_lower:
                if any(t in url_lower for t in ["trailer", "preview", "sample"]):
                    media_type = "🎞️ Trailer HLS (.m3u8)"
                else:
                    media_type = "🎬 ភាពយន្តពេញ / Full Movie Stream (.m3u8)"

            # 8. DASH Streams (.mpd)
            elif ".mpd" in url_lower:
                media_type = "📡 DASH (.mpd)"
            # 9. MP4 Video
            elif ".mp4" in url_lower or "video/mp4" in url_lower:
                if any(t in url_lower for t in ["trailer", "preview", "sample"]):
                    media_type = "🎞️ Trailer Clip (MP4)"
                else:
                    media_type = "🎬 Video (MP4)"
            # 10. WebM Video
            elif ".webm" in url_lower or "video/webm" in url_lower:
                media_type = "🎥 Video (WebM)"
            # 11. FLV Video
            elif ".flv" in url_lower:
                media_type = "📺 Video (FLV)"
            # 12. Audio MP3 / M4A / AAC
            elif ".mp3" in url_lower or "audio/mp3" in url_lower or "audio/mpeg" in url_lower:
                media_type = "🎵 Audio (MP3)"
            elif ".m4a" in url_lower or ".aac" in url_lower or "audio/mp4" in url_lower:
                media_type = "🎵 Audio (M4A)"
            # 13. Douyin / TikTok video stream
            elif any(d in url_lower for d in ["douyinvod.com", "tiktokcdn.com"]):
                media_type = "🎬 Video Stream"
            # 14. Facebook Videos, Reels, Stories & Photos
            elif "fbcdn.net" in url_lower:
                if any(ext in url_lower for ext in [".mp4", "bytestart=", "/v/t42.", "/v/t39.", "video.xx.fbcdn"]):
                    media_type = "🎬 Facebook Video / Story Stream"
                elif any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]) and not any(ic in url_lower for ic in ["emoji", "rsrc.php", "static.xx", "assets", "q=10", "s50x50", "p50x50"]):
                    media_type = "🖼️ Facebook Photo / Story Image"
            # 15. Instagram Reels, Stories & Photos
            elif "cdninstagram.com" in url_lower:
                if ".mp4" in url_lower or "bytestart=" in url_lower:
                    media_type = "🎬 Instagram Reel / Story Video"
                elif any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]) and not any(ic in url_lower for ic in ["emoji", "static", "s150x150"]):
                    media_type = "🖼️ Instagram Photo / Story Image"
            # 16. Telegram Web & Media (telesco.pe / telegram.org)
            elif any(d in url_lower for d in ["telesco.pe", "telegram.org", "web.telegram.org"]):
                if ".mp4" in url_lower:
                    media_type = "🎬 Telegram Video Stream"
                elif any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                    media_type = "🖼️ Telegram High-Res Photo"
            # 17. Pinterest Images & Videos (i.pinimg.com / v.pinimg.com)
            elif "pinimg.com" in url_lower:
                if ".mp4" in url_lower:
                    media_type = "🎬 Pinterest Video Stream"
                elif any(ext in url_lower for ext in [".jpg", ".jpeg", ".png", ".webp"]) and not any(ic in url_lower for ic in ["75x75", "150x150"]):
                    media_type = "🖼️ Pinterest Original Image"
            # 18. Pngtree Graphics & Transparent PNGs
            elif "pngtree.com" in url_lower:
                if any(ext in url_lower for ext in [".png", ".jpg", ".webp"]):
                    media_type = "🖼️ Pngtree Transparent PNG / Vector"
            # 19. Generic media resource
            elif is_media_res:
                media_type = "🎞️ Media Resource"

            if media_type:
                sig = url.split("?")[0] if ("googlevideo.com" not in url) else (url[:80] + url[-30:])
                if sig not in self.seen_signatures:
                    self.seen_signatures.add(sig)
                    domain = info.requestUrl().host()
                    self.sig_media_intercepted.emit(url, media_type, domain)
else:
    class SnifferWebEngineView:
        pass
    class MediaNetworkInterceptor:
        pass


class MediaBrowserDialog(QDialog):
    """
    Embedded Chromium Web Browser with Real-Time Network Processing,
    Right-Click Context Menu, Media & CC Sniffing, and seamless hand-off to Video Downloader.
    """

    def __init__(
        self,
        parent=None,
        initial_url: str = "https://www.youtube.com",
        on_video_selected=None,
        on_cookies_saved=None,
        proxy: str = ""
    ):
        super().__init__(parent)
        self.setWindowTitle("🌐 Built-in Media Browser & Smart Video Sniffer (ចុច Mouse ស្ដាំដើម្បីចាប់ Link ឬទាញយក)")
        self.resize(1220, 840)
        self.setMinimumSize(960, 640)

        self.on_video_selected = on_video_selected
        self.on_cookies_saved = on_cookies_saved
        self.initial_url = initial_url or "https://www.youtube.com"
        self.proxy_str = proxy or ""
        self.cookies_map = {}
        self.intercepted_records = []  # list of dicts: {url, type, domain}
        self.seen_signatures = set()
        self.active_network_filter = "all"
        self.current_detected_url = ""
        self.current_page_title = ""
        self.all_grabbed_video_urls = []
        self.table_network = None

        # Configure network proxy if specified
        if self.proxy_str and WEBENGINE_AVAILABLE:
            try:
                from PySide6.QtNetwork import QNetworkProxy
                p_clean = self.proxy_str.strip()
                p_type = QNetworkProxy.ProxyType.HttpProxy
                if p_clean.startswith("socks5://"):
                    p_type = QNetworkProxy.ProxyType.Socks5Proxy
                    p_clean = p_clean[9:]
                elif p_clean.startswith("http://"):
                    p_clean = p_clean[7:]
                elif p_clean.startswith("https://"):
                    p_clean = p_clean[8:]
                
                parts = p_clean.split(":")
                if len(parts) == 2:
                    net_proxy = QNetworkProxy()
                    net_proxy.setType(p_type)
                    net_proxy.setHostName(parts[0])
                    net_proxy.setPort(int(parts[1]))
                    QNetworkProxy.setApplicationProxy(net_proxy)
            except Exception:
                pass

        # Auto-save cookies debounced timer
        self.auto_cookie_timer = QTimer(self)
        self.auto_cookie_timer.setSingleShot(True)
        self.auto_cookie_timer.timeout.connect(self._save_cookies_silently)

        # Periodic DOM sniffer timer
        self.sniff_timer = QTimer(self)
        self.sniff_timer.setInterval(1500)
        self.sniff_timer.timeout.connect(self._run_dom_sniffer)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ── 1. TOP BAR: NAVIGATION, URL, DOWNLOAD, CATCH LINK & NETWORK PROCESSING TOGGLE ──
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)

        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("Back / ថយក្រោយ")
        self.btn_back.setFixedWidth(32)
        self.btn_back.clicked.connect(self._go_back)
        top_bar.addWidget(self.btn_back)

        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip("Forward / ទៅមុខ")
        self.btn_forward.setFixedWidth(32)
        self.btn_forward.clicked.connect(self._go_forward)
        top_bar.addWidget(self.btn_forward)

        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setToolTip("Reload / ដំណើរការឡើងវិញ")
        self.btn_refresh.setFixedWidth(32)
        self.btn_refresh.clicked.connect(self._reload_page)
        top_bar.addWidget(self.btn_refresh)

        # URL Input
        self.entry_url = QLineEdit(self.initial_url)
        self.entry_url.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px; padding: 5px 8px; "
            "background-color: #1e293b; color: #f8fafc; border: 1px solid #334155; border-radius: 4px;"
        )
        self.entry_url.returnPressed.connect(self._navigate_url)
        top_bar.addWidget(self.entry_url, 1)

        btn_go = QPushButton("Go")
        btn_go.setFixedWidth(40)
        btn_go.clicked.connect(self._navigate_url)
        top_bar.addWidget(btn_go)

        # 🎯 CATCH VIDEO LINK BUTTON
        self.btn_catch_link = QPushButton("🎯 ចាប់យក Link វីដេអូ")
        self.btn_catch_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_catch_link.setToolTip("ចុចដើម្បីចាប់យក Link វីដេអូដែលកំពុងចាក់ភ្លាមៗ")
        self.btn_catch_link.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #6d28d9);
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 12px;
                border: 1px solid #7c3aed;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #7c3aed;
            }
        """)
        self.btn_catch_link.clicked.connect(self._manual_catch_link)
        top_bar.addWidget(self.btn_catch_link)

        # PERMANENT TOP DOWNLOAD BUTTON
        self.btn_download_top = QPushButton("📥 Download Video (ទាញយក)")
        self.btn_download_top.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_top.setToolTip("ចុចទាញយកវីដេអូដែលកំពុងមើលក្នុងទំព័រនេះភ្លាមៗ")
        self.btn_download_top.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 14px;
                border: 1px solid #059669;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_download_top.clicked.connect(self._hand_off_video)
        top_bar.addWidget(self.btn_download_top)

        # NETWORK PROCESSING TOGGLE BUTTON (DRAWER)
        self.btn_toggle_network = QPushButton("📡 Network Processing (0)")
        self.btn_toggle_network.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_network.setToolTip("បើក/បិទផ្ទាំង Network Processing ដើម្បីមើល និងស្ទាក់ចាប់ Video, Audio & CC")
        self.btn_toggle_network.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 12px;
                border: 1px solid #0284c7;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #0284c7;
            }
        """)
        self.btn_toggle_network.clicked.connect(self._toggle_network_panel)
        top_bar.addWidget(self.btn_toggle_network)

        # Cookie badge
        self.lbl_cookie_badge = QLabel("🍪 Cookies: 0")
        self.lbl_cookie_badge.setStyleSheet(
            "background-color: #0f172a; color: #38bdf8; font-weight: bold; font-size: 11px; "
            "padding: 4px 8px; border-radius: 4px; border: 1px solid #1e293b;"
        )
        top_bar.addWidget(self.lbl_cookie_badge)

        btn_save_cookies = QPushButton("💾 Save Cookies")
        btn_save_cookies.setToolTip("រក្សាទុក Cookies ពី Browser នេះចូលទៅក្នុង Downloader")
        btn_save_cookies.setStyleSheet(
            "background-color: #334155; color: #e2e8f0; font-weight: bold; padding: 4px 10px; border-radius: 4px;"
        )
        btn_save_cookies.clicked.connect(self._save_cookies)
        top_bar.addWidget(btn_save_cookies)

        main_layout.addLayout(top_bar)

        # ── 2. MODERN CATEGORIZED QUICK ACCESS BOOKMARKS (CHINESE & KHMER MOVIE HUBS) ──
        bm_container = QFrame()
        bm_container.setObjectName("bm_container")
        bm_container.setStyleSheet("""
            QFrame#bm_container {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0f172a, stop:1 #090d16);
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        bm_vbox = QVBoxLayout(bm_container)
        bm_vbox.setContentsMargins(6, 4, 6, 4)
        bm_vbox.setSpacing(4)

        # Brand Custom Themes (grad1, grad2, border, text_color)
        BRAND_THEMES = {
            "youtube":     ("#dc2626", "#991b1b", "#ef4444", "#fecaca"),
            "tiktok":      ("#09090b", "#18181b", "#ec4899", "#fbcfe8"),
            "facebook":    ("#1d4ed8", "#1e40af", "#3b82f6", "#bfdbfe"),
            "kisskh":      ("#6d28d9", "#5b21b6", "#8b5cf6", "#ddd6fe"),
            "google":      ("#1e3a8a", "#14532d", "#38bdf8", "#bae6fd"),
            "sabayflix":   ("#047857", "#065f46", "#10b981", "#a7f3d0"),
            "khdiamond":   ("#0369a1", "#075985", "#0ea5e9", "#bae6fd"),
            "kolabkhmer":  ("#b45309", "#92400e", "#f59e0b", "#fde68a"),
            "phumikhmer":  ("#6d28d9", "#4c1d95", "#a855f7", "#e9d5ff"),
            "merlmovie":   ("#be123c", "#9f1239", "#f43f5e", "#fecdd3"),
            "bilibili":    ("#0284c7", "#0369a1", "#38bdf8", "#bae6fd"),
            "hongguo":     ("#c2410c", "#9a3412", "#f97316", "#ffedd5"),
            "instagram":   ("#c026d3", "#9333ea", "#e879f9", "#f5d0fe"),
            "telegram":    ("#0284c7", "#0369a1", "#38bdf8", "#e0f2fe"),
            "pinterest":   ("#e11d48", "#be123c", "#fb7185", "#ffe4e6"),
            "pngtree":     ("#059669", "#047857", "#34d399", "#d1fae5"),
            "hainanyuyue": ("#0369a1", "#1d4ed8", "#38bdf8", "#bae6fd"),
            "stardusttv":  ("#7e22ce", "#581c87", "#a855f7", "#f3e8ff"),
            "douyin":      ("#18181b", "#27272a", "#06b6d4", "#cffafe"),
            "iqiyi":       ("#15803d", "#166534", "#22c55e", "#bbf7d0"),
            "tencent":     ("#1d4ed8", "#1e40af", "#60a5fa", "#dbeafe"),
            "youku":       ("#0284c7", "#0f766e", "#38bdf8", "#cffafe"),
            "xigua":       ("#be123c", "#b91c1c", "#f87171", "#fee2e2"),
            "mangotv":     ("#ea580c", "#c2410c", "#fb923c", "#ffedd5"),
            "kuaishou":    ("#ea580c", "#b91c1c", "#f97316", "#ffedd5")
        }

        fav_base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "favicons")

        def _make_brand_btn(name, target, tip, icon_name):
            btn = QPushButton(f" {name}")
            icon_path = os.path.join(fav_base, f"{icon_name}.png")
            if os.path.exists(icon_path):
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(22, 22))
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            c = BRAND_THEMES.get(icon_name, ("#1e293b", "#0f172a", "#38bdf8", "#e2e8f0"))
            grad1, grad2, border, text_col = c
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {grad1}22, stop:1 {grad2}33);
                    color: {text_col};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 4px 10px 4px 8px;
                    border: 1px solid {border}44;
                    border-radius: 6px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {grad1}, stop:1 {grad2});
                    color: #ffffff;
                    border: 1px solid {border};
                    padding: 3px 10px 5px 8px;
                }}
                QPushButton:pressed {{
                    background: {grad2};
                    padding: 5px 10px 3px 8px;
                }}
            """)
            btn.clicked.connect(lambda checked, u=target: self._load_url(u))
            return btn

        # Row 1: Khmer Movie Portals & Global
        row1 = QHBoxLayout()
        row1.setSpacing(6)

        lbl_kh = QLabel("🇰🇭 Khmer:")
        lbl_kh.setStyleSheet("color: #34d399; font-size: 11px; font-weight: bold;")
        row1.addWidget(lbl_kh)

        khmer_sites = [
            ("Sabayflix", "https://www.sabayflix.net", "Sabayflix HD Movies & Series", "sabayflix"),
            ("KH Diamond", "https://khdiamond.net", "KH Diamond Movie Portal", "khdiamond"),
            ("Kolab Khmer", "https://kolabkhmer.com", "Kolab Khmer Video & Drama", "kolabkhmer"),
            ("PhumiKhmer", "https://phumikhmer.me", "Phumi Khmer Thai & Chinese Drama", "phumikhmer"),
            ("MerlMovie", "https://merlmovie.com", "Merl Movie Streaming", "merlmovie")
        ]
        for name, target, tip, icon_name in khmer_sites:
            row1.addWidget(_make_brand_btn(name, target, tip, icon_name))

        row1.addSpacing(8)

        lbl_gl = QLabel("🌐 Global:")
        lbl_gl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: bold;")
        row1.addWidget(lbl_gl)

        global_sites = [
            ("YouTube", "https://www.youtube.com", "YouTube 4K/HD", "youtube"),
            ("TikTok", "https://www.tiktok.com", "TikTok Video", "tiktok"),
            ("Facebook", "https://www.facebook.com", "Facebook Stories, Reels & Photos", "facebook"),
            ("Instagram", "https://www.instagram.com", "Instagram Reels, Stories & Photos", "instagram"),
            ("Telegram", "https://web.telegram.org", "Telegram Web Videos & Media", "telegram"),
            ("Pinterest", "https://www.pinterest.com", "Pinterest HD Images & Videos", "pinterest"),
            ("Pngtree", "https://pngtree.com", "Pngtree Transparent PNG & Graphics", "pngtree"),
            ("KissKH", "https://kisskh.do", "KissKH Asian Drama Streaming (Korean/Chinese/Thai)", "kisskh"),
            ("Google", "https://www.google.com", "Google Search", "google")
        ]
        for name, target, tip, icon_name in global_sites:
            row1.addWidget(_make_brand_btn(name, target, tip, icon_name))

        row1.addStretch()
        bm_vbox.addLayout(row1)

        # Row 2: China Video & Movie Platforms
        row2 = QHBoxLayout()
        row2.setSpacing(6)

        lbl_cn = QLabel("🇨🇳 China Drama:")
        lbl_cn.setStyleSheet("color: #f43f5e; font-size: 11px; font-weight: bold;")
        row2.addWidget(lbl_cn)

        china_sites = [
            ("Bilibili", "https://www.bilibili.com", "哔哩哔哩 (Bilibili Anime & Video)", "bilibili"),
            ("Hongguo", "https://hongguoduanju.com", "红果短剧 (Hongguo Short Drama & Series)", "hongguo"),
            ("Hainan Yuyue", "https://kylin.hainanyuyue.com/s/LelJr5xkxko/", "海南愉悦 (Hainan Yuyue Short Drama)", "hainanyuyue"),
            ("StardustTV", "https://www.stardusttv.net", "StardustTV Popular Short Drama Streaming", "stardusttv"),
            ("Douyin", "https://www.douyin.com", "抖音 (Douyin Video & Drama)", "douyin"),
            ("iQiyi", "https://www.iqiyi.com", "爱奇艺 (iQiyi HD Drama & Movies)", "iqiyi"),
            ("Tencent Video", "https://v.qq.com", "腾讯视频 (Tencent Video)", "tencent"),
            ("Youku", "https://www.youku.com", "优酷 (Youku Movies & Series)", "youku"),
            ("Xigua", "https://www.ixigua.com", "西瓜视频 (Xigua Cinema & Video)", "xigua"),
            ("Mango TV", "https://www.mgtv.com", "芒果TV (Mango TV Drama)", "mangotv"),
            ("Kuaishou", "https://www.kuaishou.com", "快手 (Kuaishou Drama & Shorts)", "kuaishou")
        ]
        for name, target, tip, icon_name in china_sites:
            row2.addWidget(_make_brand_btn(name, target, tip, icon_name))

        row2.addStretch()
        bm_vbox.addLayout(row2)

        main_layout.addWidget(bm_container)

        # ── 3. DETECTED VIDEO SNIFFER BANNER (GLOWING DYNAMIC NOTIFICATION) ──
        self.sniff_card = QFrame()
        self.sniff_card.setObjectName("sniff_card")
        self.sniff_card.setStyleSheet("""
            QFrame#sniff_card {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #064e3b, stop:1 #0f766e);
                border: 2px solid #10b981;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)
        sniff_layout = QHBoxLayout(self.sniff_card)
        sniff_layout.setContentsMargins(8, 6, 8, 6)
        sniff_layout.setSpacing(10)

        self.lbl_sniff_icon = QLabel("🎯")
        self.lbl_sniff_icon.setStyleSheet("font-size: 22px;")
        sniff_layout.addWidget(self.lbl_sniff_icon)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        self.lbl_sniff_status = QLabel("⚡ រកឃើញវីដេអូសម្រាប់ទាញយក (Detected Video Ready to Download!):")
        self.lbl_sniff_status.setStyleSheet("color: #a7f3d0; font-weight: bold; font-size: 12px;")
        info_box.addWidget(self.lbl_sniff_status)

        self.lbl_sniff_url = QLabel("កំពុងស្វែងរក... សូមចុចបើកវីដេអូណាមួយដើម្បីចាប់ Link")
        self.lbl_sniff_url.setStyleSheet("color: #ffffff; font-family: Consolas, monospace; font-size: 11px; font-weight: bold;")
        self.lbl_sniff_url.setWordWrap(True)
        info_box.addWidget(self.lbl_sniff_url)
        sniff_layout.addLayout(info_box, 1)

        # Action Buttons on Banner
        self.btn_download_now = QPushButton("📥 ទាញយកវីដេអូនេះភ្លាម (Download Video)")
        self.btn_download_now.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download_now.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 18px;
                border: 1px solid #059669;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        self.btn_download_now.clicked.connect(self._hand_off_video)
        sniff_layout.addWidget(self.btn_download_now)

        self.btn_play_stream = QPushButton("▶️ Play / ចាក់មើលវីដេអូ")
        self.btn_play_stream.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_stream.setToolTip("ចាក់វីដេអូផ្ទាល់តាមរយៈ Built-in Stream Player (Bypass កំហុស Browser)")
        self.btn_play_stream.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #6d28d9);
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border: 1px solid #7c3aed;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #6d28d9;
            }
        """)
        self.btn_play_stream.clicked.connect(self._play_detected_stream)
        sniff_layout.addWidget(self.btn_play_stream)

        self.btn_copy_detected = QPushButton("📋 Copy Link")
        self.btn_copy_detected.setStyleSheet(
            "background-color: #0f172a; color: #38bdf8; font-size: 11px; padding: 7px 12px; border-radius: 4px;"
        )
        self.btn_copy_detected.clicked.connect(self._copy_detected_url)
        sniff_layout.addWidget(self.btn_copy_detected)

        self.btn_grab_all_urls = QPushButton("📋 Grab All URLs")
        self.btn_grab_all_urls.setToolTip("ចម្លង Link វីដេអូ និងភាគទាំងអស់ដែលបានស្ទាក់ចាប់យកក្នុងទំព័រនេះ")
        self.btn_grab_all_urls.setStyleSheet(
            "background-color: #312e81; color: #a5b4fc; font-size: 11px; font-weight: bold; padding: 7px 12px; border: 1px solid #4f46e5; border-radius: 4px;"
        )
        self.btn_grab_all_urls.clicked.connect(self._copy_all_grabbed_urls)
        self.btn_grab_all_urls.setVisible(False)
        sniff_layout.addWidget(self.btn_grab_all_urls)

        main_layout.addWidget(self.sniff_card)
        self.sniff_card.setVisible(False)

        # ── 4. MAIN SPLITTER: WEB VIEW (TOP) & NETWORK PROCESSING PANEL (BOTTOM) ──
        self.v_splitter = QSplitter(Qt.Orientation.Vertical)
        self.v_splitter.setOpaqueResize(True)

        # Web View with Right-Click Context Menu
        if WEBENGINE_AVAILABLE:
            self.web_view = SnifferWebEngineView(self)
            self.web_view.sig_download_requested.connect(self._hand_off_video)
            self.web_view.sig_sniff_requested.connect(self._manual_catch_link)
            self.web_view.sig_copy_requested.connect(self._copy_detected_url)
            self.web_view.sig_open_network.connect(self._show_network_panel)

            profile = self.web_view.page().profile()

            # Fix HTML5 Player Compatibility (Bilibili, Douyin, etc.)
            setup_html5_media_profile(profile)

            # Attach Network Request Interceptor for real-time media & CC sniffing
            self.network_interceptor = MediaNetworkInterceptor(self)
            self.network_interceptor.sig_media_intercepted.connect(self._on_network_media_intercepted)
            profile.setUrlRequestInterceptor(self.network_interceptor)

            # Cookie capture
            self.cookie_store = profile.cookieStore()
            self.cookie_store.cookieAdded.connect(self._on_cookie_added)

            self.web_view.urlChanged.connect(self._on_url_changed)
            self.web_view.titleChanged.connect(self._on_title_changed)
            self.web_view.loadFinished.connect(self._on_load_finished)

            self.v_splitter.addWidget(self.web_view)
            self.sniff_timer.start()
        else:
            lbl_err = QLabel("⚠️ PySide6 QtWebEngine is not available on this Python installation.")
            lbl_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_err.setStyleSheet("color: #ef4444; font-size: 14px;")
            self.v_splitter.addWidget(lbl_err)

        # Network Processing Panel
        self.network_panel = QFrame()
        self.network_panel.setObjectName("network_panel")
        self.network_panel.setStyleSheet("""
            QFrame#network_panel {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        net_layout = QVBoxLayout(self.network_panel)
        net_layout.setContentsMargins(8, 8, 8, 8)
        net_layout.setSpacing(6)

        # Header of Network Panel
        net_header = QHBoxLayout()
        net_header.setSpacing(8)

        lbl_net_title = QLabel("📡 Network Processing / ស្ទាក់ចាប់ Video, Audio & CC ពីបណ្ដាញ:")
        lbl_net_title.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 12px;")
        net_header.addWidget(lbl_net_title)

        # Filters
        self.btn_filter_all = QPushButton("All")
        self.btn_filter_all.setCheckable(True)
        self.btn_filter_all.setChecked(True)
        self.btn_filter_all.clicked.connect(lambda: self._apply_filter("all"))
        net_header.addWidget(self.btn_filter_all)

        self.btn_filter_video = QPushButton("🎬 Videos")
        self.btn_filter_video.setCheckable(True)
        self.btn_filter_video.clicked.connect(lambda: self._apply_filter("video"))
        net_header.addWidget(self.btn_filter_video)

        self.btn_filter_hls = QPushButton("📡 HLS (m3u8)")
        self.btn_filter_hls.setCheckable(True)
        self.btn_filter_hls.clicked.connect(lambda: self._apply_filter("hls"))
        net_header.addWidget(self.btn_filter_hls)

        self.btn_filter_audio = QPushButton("🎵 Audios")
        self.btn_filter_audio.setCheckable(True)
        self.btn_filter_audio.clicked.connect(lambda: self._apply_filter("audio"))
        net_header.addWidget(self.btn_filter_audio)

        # Subtitles / CC Filter Button
        self.btn_filter_cc = QPushButton("💬 Subtitles / CC")
        self.btn_filter_cc.setCheckable(True)
        self.btn_filter_cc.clicked.connect(lambda: self._apply_filter("cc"))
        net_header.addWidget(self.btn_filter_cc)

        net_header.addStretch()

        btn_copy_all_net = QPushButton("📋 Copy All URLs")
        btn_copy_all_net.setFixedHeight(24)
        btn_copy_all_net.setStyleSheet("background-color: #312e81; color: #a5b4fc; font-weight: bold; font-size: 11px; padding: 2px 10px; border-radius: 4px; border: 1px solid #4f46e5;")
        btn_copy_all_net.clicked.connect(self._copy_all_grabbed_urls)
        net_header.addWidget(btn_copy_all_net)

        btn_clear_net = QPushButton("🗑️ Clear List")
        btn_clear_net.setFixedSize(85, 24)
        btn_clear_net.clicked.connect(self._clear_network_list)
        net_header.addWidget(btn_clear_net)

        btn_hide_net = QPushButton("✖ Close Panel")
        btn_hide_net.setFixedSize(95, 24)
        btn_hide_net.clicked.connect(lambda: self.network_panel.setVisible(False))
        net_header.addWidget(btn_hide_net)

        net_layout.addLayout(net_header)

        # Table of Intercepted Media Requests
        self.table_network = QTableWidget()
        self.table_network.setColumnCount(4)
        self.table_network.setHorizontalHeaderLabels(["Media / CC Type", "Host / Server", "Intercepted Stream URL", "Quick Actions"])
        self.table_network.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_network.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_network.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_network.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_network.verticalHeader().setVisible(False)
        self.table_network.setStyleSheet("""
            QTableWidget {
                background-color: #171b22;
                color: #e2e8f0;
                gridline-color: #283342;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #283342;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: bold;
                padding: 4px;
                border: 1px solid #334155;
            }
        """)
        net_layout.addWidget(self.table_network)

        self.v_splitter.addWidget(self.network_panel)
        # Default split: 70% web view, 30% network panel
        self.v_splitter.setStretchFactor(0, 7)
        self.v_splitter.setStretchFactor(1, 3)
        self.network_panel.setVisible(False)

        main_layout.addWidget(self.v_splitter, 1)

        # ── 5. BOTTOM BAR: INSTRUCTIONS & CLOSE ──
        bot_bar = QHBoxLayout()
        lbl_hint = QLabel(
            "💡 របៀបប្រើប្រាស់៖ នៅលើវីដេអូ អ្នកអាច **ចុច Mouse ស្ដាំ (Right-Click)** ដើម្បីទាញយក ឬចម្លង Link ភ្លាមៗ, "
            "ឬចុចប៊ូតុង **'🎯 ចាប់យក Link វីដេអូ'** នៅខាងលើបង្អស់។ គាំទ្រ Bilibili, YouTube, Douyin, TikTok, Facebook ពេញលេញ!"
        )
        lbl_hint.setStyleSheet("color: #38bdf8; font-size: 11px;")
        lbl_hint.setWordWrap(True)
        bot_bar.addWidget(lbl_hint, 1)

        btn_close = QPushButton("Close Browser")
        btn_close.clicked.connect(self.accept)
        bot_bar.addWidget(btn_close)
        main_layout.addLayout(bot_bar)

        if hasattr(self, "web_view") and WEBENGINE_AVAILABLE:
            self.web_view.setUrl(QUrl(self.initial_url))

    def _show_network_panel(self):
        """Opens and expands the Network Processing drawer."""
        self.network_panel.setVisible(True)
        self.v_splitter.setSizes([500, 260])

    def _toggle_network_panel(self):
        """Toggles the visibility of the Network Processing drawer."""
        is_vis = self.network_panel.isVisible()
        self.network_panel.setVisible(not is_vis)
        if not is_vis:
            self.v_splitter.setSizes([500, 260])

    def _manual_catch_link(self):
        """Explicitly catches the current video URL and triggers notification."""
        url = self.entry_url.text().strip()
        if hasattr(self, "web_view"):
            url = self.web_view.url().toString() or url

        clean_url = clean_video_url(url)
        self.current_detected_url = clean_url
        self._update_detected_ui(clean_url, self.current_page_title or "Captured Video Link")

        # Visual indicator on button
        self.btn_catch_link.setText("✅ បានចាប់យក!")
        QTimer.singleShot(1800, lambda: self.btn_catch_link.setText("🎯 ចាប់យក Link វីដេអូ"))

    def _on_network_media_intercepted(self, url: str, media_type: str, domain: str, duration: float = 0.0):
        """Triggered whenever a media stream or CC subtitle is intercepted."""
        record = {
            "url": url,
            "type": media_type,
            "domain": domain,
            "duration": duration
        }
        self.intercepted_records.append(record)

        total = len(self.intercepted_records)
        self.btn_toggle_network.setText(f"📡 Network Processing ({total})")
        self.btn_toggle_network.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
                padding: 5px 12px;
                border: 1px solid #10b981;
                border-radius: 4px;
            }
        """)

        # CRITICAL FIX: Subtitles/CC are NEVER assigned as the primary video download candidate!
        # Subtitles belong in the Network Drawer for direct .SRT conversion.
        is_sub_or_cc = ("Subtitle" in media_type or "CC" in media_type or any(s in url.lower() for s in ["/subtitle", "timedtext", ".vtt", ".srt", ".ass"]))
        if is_sub_or_cc:
            # If on Bilibili and primary video URL hasn't been locked yet, pin it from browser address bar
            cur_p = self.entry_url.text().strip() if hasattr(self, "entry_url") else ""
            if "bilibili.com" in cur_p and not self.current_detected_url:
                bili_clean = clean_video_url(cur_p)
                if bili_clean:
                    self.current_detected_url = bili_clean
                    self._update_detected_ui(bili_clean, f"🎬 Bilibili Video Ready to Download: {self.current_page_title}")
            # Keep current detected video URL intact!

        # Collector for "Grab All Video URLs"
        if not is_sub_or_cc and url and url != "about:blank":
            if not hasattr(self, "all_grabbed_video_urls"):
                self.all_grabbed_video_urls = []
            clean_rec = clean_video_url(url) or url
            if clean_rec not in self.all_grabbed_video_urls and not any(clean_rec.endswith(x) for x in [".vtt", ".srt", ".ass", ".jpg", ".png", ".webp"]):
                self.all_grabbed_video_urls.append(clean_rec)
                if hasattr(self, "btn_grab_all_urls"):
                    self.btn_grab_all_urls.setText(f"📋 Grab All URLs ({len(self.all_grabbed_video_urls)})")
                    self.btn_grab_all_urls.setVisible(True)

        # Media stream (e.g. .m4s, .m3u8, .mp4, bilivideo, sf-api, streamtape)
        elif any(k in media_type.lower() for k in ["video", "m4s", "m3u8", "mp4", "bilibili", "movie", "khmer", "stream"]):
            url_l = url.lower()
            mt_l = media_type.lower()

            is_trailer = (
                (0 < duration < 300) or
                any(t in url_l for t in ["trailer", "preview", "short-clips", "sample"]) or
                any(t in mt_l for t in ["trailer", "preview", "short-clips"])
            )

            is_full_movie = (
                duration >= 1200 or
                any(k in mt_l for k in ["ភាពយន្តពេញ", "full movie"]) or
                (
                    (".m3u8" in url_l or "sf-api" in url_l or "movie" in url_l or "/stream" in url_l or "dooplayer" in url_l)
                    and not is_trailer
                )
            )

            dur_str = format_duration_str(duration) if duration > 0 else ""

            if is_full_movie:
                # FULL MOVIE ALWAYS SUPERSEDES AND OVERWRITES ANY TRAILER!
                self.current_detected_url = url
                self.is_current_full_movie = True
                lbl_title = f"🎬 ភាពយន្តពេញ (Full Movie Ready)! [{dur_str or 'HD Stream'}] - {self.current_page_title}"
                self._update_detected_ui(url, lbl_title, is_full_movie=True, duration_str=dur_str)
            elif is_trailer:
                # If no full movie has been captured yet, show trailer with prompt
                if not getattr(self, "is_current_full_movie", False) and not self.current_detected_url:
                    self.current_detected_url = url
                    lbl_title = f"🎞️ Trailer Clip [{dur_str or '~3:32'}] - សូមចុច Play ភាពយន្តពេញនៅលើវេបសាយដើម្បីចាប់ Link 2h:37m"
                    self._update_detected_ui(url, lbl_title, is_full_movie=False, duration_str=dur_str or "~3:32")
            else:
                # Standard / generic video stream
                if not self.current_detected_url:
                    self.current_detected_url = url
                    self._update_detected_ui(url, f"🎬 Captured Video Stream [{media_type}]", is_full_movie=False)
                elif not getattr(self, "is_current_full_movie", False) and not any(plat in self.current_detected_url for plat in ["youtube.com/watch", "bilibili.com/video", "douyin.com/video", "tiktok.com"]):
                    self.current_detected_url = url
                    self._update_detected_ui(url, f"🎬 Captured Video Stream [{media_type}]", is_full_movie=False)

        self._add_table_row(record)

    def _add_table_row(self, record: dict):
        if not hasattr(self, "table_network") or self.table_network is None:
            return
        row = self.table_network.rowCount()
        self.table_network.insertRow(row)

        m_type = record["type"]
        dur = record.get("duration", 0.0)
        if dur > 0 and format_duration_str(dur) not in m_type:
            m_type = f"{m_type} ({format_duration_str(dur)})"

        is_sub = ("Subtitle" in m_type or "CC" in m_type or "vtt" in m_type or "srt" in m_type)
        is_full = ("ភាពយន្តពេញ" in m_type or "Full Movie" in m_type or dur >= 1200)

        # Column 0: Type with color coding
        item_type = QTableWidgetItem(m_type)
        item_type.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_sub:
            item_type.setForeground(Qt.GlobalColor.yellow)
        elif is_full:
            item_type.setForeground(Qt.GlobalColor.green)
        elif "Trailer" in m_type or "Clip" in m_type:
            item_type.setForeground(Qt.GlobalColor.yellow)
        elif "Video" in m_type or "MP4" in m_type or "Bilibili" in m_type:
            item_type.setForeground(Qt.GlobalColor.cyan)
        elif "HLS" in m_type:
            item_type.setForeground(Qt.GlobalColor.magenta)
        else:
            item_type.setForeground(Qt.GlobalColor.green)
        self.table_network.setItem(row, 0, item_type)

        # Column 1: Domain
        item_domain = QTableWidgetItem(record["domain"])
        item_domain.setForeground(QColor("#38bdf8"))
        self.table_network.setItem(row, 1, item_domain)

        # Column 2: URL
        item_url = QTableWidgetItem(record["url"][:120] + ("..." if len(record["url"]) > 120 else ""))
        item_url.setForeground(QColor("#f8fafc"))
        item_url.setToolTip(record["url"])
        self.table_network.setItem(row, 2, item_url)

        # Column 3: Action Buttons
        cell_widget = QWidget()
        h_box = QHBoxLayout(cell_widget)
        h_box.setContentsMargins(2, 2, 2, 2)
        h_box.setSpacing(4)

        is_audio = ("audio" in m_type.lower() or "mp3" in m_type.lower() or "m4a" in m_type.lower())

        if is_sub:
            btn_dl = QPushButton("📥 Download .SRT")
            btn_dl.setStyleSheet("background-color: #ca8a04; color: white; font-weight: bold; padding: 2px 8px; border-radius: 3px;")
            btn_dl.clicked.connect(lambda checked, u=record["url"]: self._download_subtitle_file(u))
        elif is_full:
            btn_dl = QPushButton("🎬 Download Movie")
            btn_dl.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 2px 8px; border-radius: 3px;")
            btn_dl.clicked.connect(lambda checked, u=record["url"]: self._download_network_url(u))
        elif is_audio:
            btn_dl = QPushButton("🎵 Download Audio")
            btn_dl.setStyleSheet("background-color: #7c3aed; color: white; font-weight: bold; padding: 2px 8px; border-radius: 3px;")
            btn_dl.clicked.connect(lambda checked, u=record["url"]: self._download_network_url(u))
        else:
            btn_dl = QPushButton("📥 Download")
            btn_dl.setStyleSheet("background-color: #10b981; color: white; font-weight: bold; padding: 2px 8px; border-radius: 3px;")
            btn_dl.clicked.connect(lambda checked, u=record["url"]: self._download_network_url(u))
        h_box.addWidget(btn_dl)

        btn_cp = QPushButton("📋 Copy")
        btn_cp.setStyleSheet("background-color: #334155; color: #94a3b8; padding: 2px 6px; border-radius: 3px;")
        btn_cp.clicked.connect(lambda checked, u=record["url"], b=btn_cp: self._copy_specific_url(u, b))
        h_box.addWidget(btn_cp)

        self.table_network.setCellWidget(row, 3, cell_widget)
        self.table_network.setRowHeight(row, 30)

        # Apply current filter visibility
        mode = getattr(self, "active_network_filter", "all")
        txt = m_type.lower()
        if mode == "all":
            self.table_network.setRowHidden(row, False)
        elif mode == "video":
            self.table_network.setRowHidden(row, "video" not in txt and "mp4" not in txt and "webm" not in txt and "bilibili" not in txt and "m4s" not in txt)
        elif mode == "hls":
            self.table_network.setRowHidden(row, "hls" not in txt and "m3u8" not in txt and "dash" not in txt)
        elif mode == "audio":
            self.table_network.setRowHidden(row, "audio" not in txt and "mp3" not in txt and "m4a" not in txt)
        elif mode == "cc":
            self.table_network.setRowHidden(row, "subtitle" not in txt and "cc" not in txt and "vtt" not in txt and "srt" not in txt)

        self.table_network.scrollToBottom()

    def _download_subtitle_file(self, url: str):
        """Downloads and converts a network subtitle (WebVTT or timedtext) directly to clean .srt file."""
        try:
            target_url = url
            if "timedtext" in target_url and "fmt=" not in target_url:
                sep = "&" if "?" in target_url else "?"
                target_url = target_url + sep + "fmt=vtt"

            req = urllib.request.Request(target_url, headers={"User-Agent": CHROME_USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="replace")

            srt_content = vtt_to_srt(content)

            os.makedirs("downloads", exist_ok=True)
            safe_name = sanitize_folder_name(self.current_page_title) or "downloaded_subtitle"
            out_srt = os.path.join("downloads", f"{safe_name}.srt")
            with open(out_srt, "w", encoding="utf-8") as f:
                f.write(srt_content)

            QMessageBox.information(
                self,
                "Subtitle Downloaded",
                f"🎉 បានទាញយក និងបម្លែងឯកសារ Subtitle (.srt) ដោយជោគជ័យ!\n\n"
                f"📁 ទីតាំង: {out_srt}\n"
                f"អ្នកអាចបើកប្រើក្នុង Movie Studio ឬកែសម្រួលបានភ្លាមៗ!"
            )
        except Exception as e:
            self._download_network_url(url)

    def _download_network_url(self, url: str):
        """Hands off the chosen intercepted network URL to VideoDownloaderView."""
        cookie_file = self._save_cookies_silently()
        if self.on_video_selected:
            self.on_video_selected(url, cookie_file)
        self.accept()

    def _copy_specific_url(self, url: str, btn: QPushButton):
        from ui_v_PyQt6.qt_compat import QApplication
        QApplication.clipboard().setText(url)
        btn.setText("Copied! ✅")
        QTimer.singleShot(1500, lambda: btn.setText("📋 Copy"))

    def _clear_network_list(self):
        self.table_network.setRowCount(0)
        self.intercepted_records.clear()
        self.btn_toggle_network.setText("📡 Network Processing (0)")

    def _apply_filter(self, mode: str):
        """Filters table rows by media type and updates active button appearance."""
        self.active_network_filter = mode
        
        # Visually highlight active filter button
        filters = [
            ("all", getattr(self, "btn_filter_all", None)),
            ("video", getattr(self, "btn_filter_video", None)),
            ("hls", getattr(self, "btn_filter_hls", None)),
            ("audio", getattr(self, "btn_filter_audio", None)),
            ("cc", getattr(self, "btn_filter_cc", None))
        ]
        for f_name, btn in filters:
            if not btn:
                continue
            if f_name == mode:
                btn.setChecked(True)
                btn.setStyleSheet("background-color: #0284c7; color: #ffffff; font-weight: bold; padding: 3px 10px; border-radius: 4px; border: 1px solid #38bdf8;")
            else:
                btn.setChecked(False)
                btn.setStyleSheet("background-color: #1e293b; color: #94a3b8; padding: 3px 10px; border-radius: 4px; border: 1px solid #334155;")

        for r in range(self.table_network.rowCount()):
            item = self.table_network.item(r, 0)
            txt = item.text().lower() if item else ""
            if mode == "all":
                self.table_network.setRowHidden(r, False)
            elif mode == "video":
                self.table_network.setRowHidden(r, "video" not in txt and "mp4" not in txt and "webm" not in txt and "bilibili" not in txt and "m4s" not in txt)
            elif mode == "hls":
                self.table_network.setRowHidden(r, "hls" not in txt and "m3u8" not in txt and "dash" not in txt)
            elif mode == "audio":
                self.table_network.setRowHidden(r, "audio" not in txt and "mp3" not in txt and "m4a" not in txt)
            elif mode == "cc":
                self.table_network.setRowHidden(r, "subtitle" not in txt and "cc" not in txt and "vtt" not in txt and "srt" not in txt)

    def _load_url(self, url: str):
        self.entry_url.setText(url)
        self._navigate_url()

    def _navigate_url(self):
        raw = self.entry_url.text().strip()
        if raw and hasattr(self, "web_view"):
            if not raw.startswith("http://") and not raw.startswith("https://"):
                if "." in raw and not " " in raw:
                    raw = "https://" + raw
                else:
                    raw = f"https://www.google.com/search?q={raw}"
            self.web_view.setUrl(QUrl(raw))

    def _go_back(self):
        if hasattr(self, "web_view"):
            self.web_view.back()

    def _go_forward(self):
        if hasattr(self, "web_view"):
            self.web_view.forward()

    def _reload_page(self):
        if hasattr(self, "web_view"):
            self.web_view.reload()

    def _on_url_changed(self, url: "QUrl"):
        url_str = url.toString()
        self.entry_url.setText(url_str)
        self._inspect_video_candidate(url_str)

    def _on_title_changed(self, title: str):
        self.current_page_title = title
        if self.current_detected_url:
            self._update_detected_ui(self.current_detected_url, title)

    def _on_load_finished(self, ok: bool):
        if ok:
            url_str = self.web_view.url().toString()
            self._inspect_video_candidate(url_str)
            self._run_dom_sniffer()

    def _run_dom_sniffer(self):
        """Periodically inspects page URL, HTML5 video tags, and CC subtitle tracks."""
        if not hasattr(self, "web_view") or not self.web_view.isVisible():
            return

        current_url = self.web_view.url().toString()
        if current_url and current_url != "about:blank":
            self._inspect_video_candidate(current_url)

        js_code = """
        (function() {
            var found = [];

            // A. Check Bilibili window.__playinfo__ (DASH & DURL) from window or script tags
            try {
                var playinfo = window.__playinfo__;
                if (!playinfo) {
                    var scripts = document.querySelectorAll('script');
                    for (var s = 0; s < scripts.length; s++) {
                        var text = scripts[s].innerText || '';
                        if (text.indexOf('__playinfo__=') !== -1 || text.indexOf('window.__playinfo__') !== -1) {
                            var jsonMatch = text.match(/__playinfo__\s*=\s*(\{.*?\});/);
                            if (jsonMatch) {
                                playinfo = JSON.parse(jsonMatch[1]);
                                break;
                            }
                        }
                    }
                }
                if (playinfo && playinfo.data) {
                    var d = playinfo.data;
                    if (d.dash) {
                        if (d.dash.video && d.dash.video.length > 0) {
                            for (var vi = 0; vi < d.dash.video.length; vi++) {
                                var v = d.dash.video[vi];
                                var vu = v.baseUrl || v.url || (v.backupUrl && v.backupUrl[0]);
                                var qid = v.id || 80;
                                var qlabel = (qid >= 112) ? '1080P+ 高清' : ((qid >= 80) ? '1080P 高清' : ((qid >= 64) ? '720P 高清' : (qid + 'P')));
                                if (vu) found.push({url: vu, type: 'video_bili', label: 'Bilibili Video Stream (' + qlabel + ')'});
                            }
                        }
                        if (d.dash.audio && d.dash.audio.length > 0) {
                            for (var ai = 0; ai < d.dash.audio.length; ai++) {
                                var a = d.dash.audio[ai];
                                var au = a.baseUrl || a.url || (a.backupUrl && a.backupUrl[0]);
                                var aid = a.id || 30280;
                                var alabel = (aid >= 30280) ? '192kbps HQ' : ((aid >= 30232) ? '132kbps' : '64kbps');
                                if (au) found.push({url: au, type: 'audio_bili', label: 'Bilibili Audio Stream (' + alabel + ')'});
                            }
                        }
                    } else if (d.durl && d.durl.length > 0) {
                        for (var di = 0; di < d.durl.length; di++) {
                            var du = d.durl[di].url || (d.durl[di].backup_url && d.durl[di].backup_url[0]);
                            if (du) found.push({url: du, type: 'video_bili', label: 'Bilibili MP4 Video'});
                        }
                    }
                }
            } catch(e) {}

            // B. Check XHR / Fetch Hook Buffer
            try {
                if (window.__captured_media_streams__ && window.__captured_media_streams__.length > 0) {
                    while (window.__captured_media_streams__.length > 0) {
                        var it = window.__captured_media_streams__.shift();
                        var cu = (typeof it === 'object' && it.url) ? it.url : it;
                        var cdur = (typeof it === 'object' && it.duration) ? it.duration : 0;
                        var cul = cu.toLowerCase();
                        var ctype = 'video';
                        var clabel = 'Media Stream';
                        if (cul.indexOf('/subtitle') !== -1 || cul.indexOf('timedtext') !== -1 || cul.indexOf('.vtt') !== -1 || cul.indexOf('.srt') !== -1) {
                            ctype = 'cc';
                            clabel = 'Subtitle / CC';
                        } else if (cul.indexOf('audio') !== -1 || cul.indexOf('.mp3') !== -1 || cul.indexOf('.m4a') !== -1 || cul.indexOf('30280') !== -1) {
                            ctype = 'audio_bili';
                            clabel = 'Audio Stream';
                        } else if (cul.indexOf('.m4s') !== -1 || cul.indexOf('bilivideo') !== -1 || cul.indexOf('szbdyd') !== -1 || cul.indexOf('upos') !== -1) {
                            ctype = 'video_bili';
                            clabel = 'Bilibili Stream (.m4s)';
                        } else if (cdur > 1200 || cul.indexOf('movie') !== -1 || cul.indexOf('/stream') !== -1) {
                            ctype = 'video_full';
                            clabel = 'ភាពយន្តពេញ / Full Movie';
                        } else if (cul.indexOf('trailer') !== -1 || cul.indexOf('preview') !== -1 || (cdur > 0 && cdur < 300)) {
                            ctype = 'video_trailer';
                            clabel = 'Trailer Clip';
                        }
                        found.push({url: cu, type: ctype, label: clabel, duration: cdur});
                    }
                }
            } catch(e) {}

            // C. HTML5 Video tags & Durations
            var vids = document.querySelectorAll('video');
            for (var i = 0; i < vids.length; i++) {
                var v = vids[i];
                var s = v.currentSrc || v.src;
                var dur = v.duration || 0;
                if (s && s.indexOf('http') === 0 && s.indexOf('googlevideo.com') === -1) {
                    var vtype = (dur >= 1200) ? 'video_full' : ((dur > 0 && dur < 300) ? 'video_trailer' : 'video');
                    var vlbl = (dur >= 1200) ? 'ភាពយន្តពេញ / Full Movie' : ((dur > 0 && dur < 300) ? 'Trailer Clip' : 'HTML5 Video');
                    found.push({url: s, type: vtype, label: vlbl, duration: dur});
                }
                var sources = v.querySelectorAll('source');
                for (var si = 0; si < sources.length; si++) {
                    var s_src = sources[si].src;
                    if (s_src && s_src.indexOf('http') === 0) {
                        found.push({url: s_src, type: 'video', label: 'Video Source', duration: dur});
                    }
                }
            }

            // D. Inspect IFrames (Hidden & Embedded players: Sabayflix, KH Diamond, Streamtape, Dood)
            var iframes = document.querySelectorAll('iframe');
            for (var f = 0; f < iframes.length; f++) {
                var ifr = iframes[f];
                var isrc = ifr.src || ifr.getAttribute('data-src') || ifr.getAttribute('data-lazy-src') || '';
                if (isrc && isrc.indexOf('http') === 0) {
                    var isrcl = isrc.toLowerCase();
                    if (isrcl.indexOf('.m3u8') !== -1 || isrcl.indexOf('.mp4') !== -1) {
                        found.push({url: isrc, type: 'video_full', label: 'IFrame Stream (.m3u8)', duration: 0});
                    } else if (isrcl.indexOf('sf-api') !== -1 || isrcl.indexOf('streamtape') !== -1 || isrcl.indexOf('dood') !== -1 || isrcl.indexOf('filemoon') !== -1 || isrcl.indexOf('vidhide') !== -1 || isrcl.indexOf('superembed') !== -1) {
                        found.push({url: isrc, type: 'video_embed', label: 'Movie Server Player', duration: 0});
                    }
                }
                try {
                    if (ifr.contentDocument) {
                        var innerVids = ifr.contentDocument.querySelectorAll('video');
                        for (var iv = 0; iv < innerVids.length; iv++) {
                            var iv_s = innerVids[iv].currentSrc || innerVids[iv].src;
                            var iv_dur = innerVids[iv].duration || 0;
                            if (iv_s && iv_s.indexOf('http') === 0) {
                                var iv_type = (iv_dur >= 1200) ? 'video_full' : 'video';
                                found.push({url: iv_s, type: iv_type, label: 'Iframe Video Stream', duration: iv_dur});
                            }
                        }
                    }
                } catch(e) {}
            }

            // E. Inspect data-video, data-stream, data-src attributes (Sabayflix & KH Diamond servers)
            var dataElems = document.querySelectorAll('[data-src], [data-video], [data-stream], [data-url], [data-embed], .server-item, .dooplayer');
            for (var de = 0; de < dataElems.length; de++) {
                var el = dataElems[de];
                var val = el.getAttribute('data-video') || el.getAttribute('data-stream') || el.getAttribute('data-src') || el.getAttribute('data-embed') || el.getAttribute('data-url') || '';
                if (val && val.indexOf('http') === 0) {
                    var vall = val.toLowerCase();
                    if (vall.indexOf('.m3u8') !== -1 || vall.indexOf('.mp4') !== -1) {
                        found.push({url: val, type: 'video_full', label: 'Server Stream URL', duration: 0});
                    }
                }
            }

            // F. Track tags (Closed Captions / Subtitles)
            var tracks = document.querySelectorAll('track');
            for (var j = 0; j < tracks.length; j++) {
                var ts = tracks[j].src;
                var tl = tracks[j].label || tracks[j].srclang || 'CC';
                if (ts && ts.indexOf('http') === 0) {
                    found.push({url: ts, type: 'cc', label: tl, duration: 0});
                }
            }

            // G. Drama Episodes & Video Links (Hongguo, StardustTV, YouTube, Sabayflix, KH Diamond)
            var epLinks = document.querySelectorAll('a[href*="/player/"], a[href*="/episodes/"], a[href*="/watch?"], a[href*="/video/"], a[href*="/movie/"], .episode-item, .ep-btn, [class*="episode"]');
            for (var e = 0; e < epLinks.length && e < 150; e++) {
                var el = epLinks[e];
                var h = el.href || el.getAttribute('href') || '';
                var t = (el.innerText || el.textContent || '').trim().replace(/\\s+/g, ' ');
                if (h && (h.indexOf('http') === 0 || h.indexOf('/') === 0)) {
                    var fullH = (h.indexOf('http') === 0) ? h : (window.location.origin + h);
                    if (fullH.indexOf('#') !== -1) fullH = fullH.split('#')[0];
                    if (fullH && fullH !== window.location.href) {
                        found.push({url: fullH, type: 'episode', label: '🎬 ' + (t || ('Episode ' + (e+1))), duration: 0});
                    }
                }
            }

            // H. Inject / Keep Active In-Page Floating Tag Button ("in web ផ្ទាល់")
            try {
                var btnId = '__agy_in_page_download_btn__';
                if (!document.getElementById(btnId) && document.body) {
                    var btn = document.createElement('div');
                    btn.id = btnId;
                    btn.style.cssText = 'position: fixed !important; top: 18px !important; right: 22px !important; z-index: 2147483647 !important; display: flex !important; align-items: center !important; gap: 8px !important; background: linear-gradient(135deg, #064e3b, #065f46) !important; border: 2px solid #10b981 !important; border-radius: 26px !important; padding: 6px 14px !important; color: #ffffff !important; font-family: system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif !important; font-size: 13px !important; font-weight: bold !important; box-shadow: 0 6px 20px rgba(0,0,0,0.6), 0 0 12px rgba(16,185,129,0.5) !important; cursor: pointer !important; user-select: none !important; transition: transform 0.2s, box-shadow 0.2s !important;';
                    btn.innerHTML = '<span style=\"font-size: 16px;\">📥</span><span style=\"color:#6ee7b7;\">Download Video</span><span id=\"__agy_in_page_copy__\" style=\"margin-left: 4px; background: rgba(0,0,0,0.35); padding: 2px 7px; border-radius: 12px; font-size: 11px; border: 1px solid #059669; color: #a7f3d0;\">📋 Link</span>';
                    document.body.appendChild(btn);

                    btn.onmouseenter = function() {
                        btn.style.transform = 'scale(1.06)';
                        btn.style.boxShadow = '0 8px 25px rgba(0,0,0,0.8), 0 0 20px rgba(16,185,129,0.8)';
                    };
                    btn.onmouseleave = function() {
                        btn.style.transform = 'scale(1.0)';
                        btn.style.boxShadow = '0 6px 20px rgba(0,0,0,0.6), 0 0 12px rgba(16,185,129,0.5)';
                    };

                    btn.onclick = function(ev) {
                        if (ev.target && ev.target.id === '__agy_in_page_copy__') {
                            ev.stopPropagation();
                            fetch('https://agy-sniffer-action.local/catch').catch(function(){});
                            ev.target.innerText = 'Copied! ✅';
                            setTimeout(function(){ ev.target.innerText = '📋 Link'; }, 1500);
                        } else {
                            fetch('https://agy-sniffer-action.local/download').catch(function(){});
                        }
                    };
                }
            } catch(errBtn) {}

            return found;
        })();
        """
        self.web_view.page().runJavaScript(js_code, self._on_dom_sniffer_result)

    def _on_dom_sniffer_result(self, result):
        if isinstance(result, list) and len(result) > 0:
            for item in result:
                if isinstance(item, dict):
                    url = item.get("url")
                    i_type = item.get("type", "")
                    label = item.get("label", "Media")
                    dur = float(item.get("duration", 0.0) or 0.0)
                    if url:
                        if i_type == "cc":
                            self._on_network_media_intercepted(url, f"💬 Subtitle CC ({label})", "DOM Track", duration=dur)
                        elif i_type == "episode":
                            self._on_network_media_intercepted(url, f"🎬 Episode ({label})", "Page Episode Link", duration=dur)
                        elif i_type == "audio_bili":
                            self._on_network_media_intercepted(url, f"🎵 {label}", "Bilibili Stream", duration=dur)
                        elif i_type == "video_bili":
                            self._on_network_media_intercepted(url, f"🎬 {label}", "Bilibili Stream", duration=dur)
                        elif i_type == "video_full":
                            self._on_network_media_intercepted(url, f"🎬 ភាពយន្តពេញ / Full Movie ({label})", "Movie Server", duration=dur)
                        elif i_type == "video_trailer":
                            self._on_network_media_intercepted(url, f"🎞️ Trailer Clip ({label})", "DOM Video", duration=dur)
                        elif i_type == "video":
                            self._on_network_media_intercepted(url, f"🎬 Video Stream ({label})", "DOM Video", duration=dur)
                elif isinstance(item, str):
                    self._inspect_video_candidate(item)

    def _inspect_video_candidate(self, url: str):
        """Analyzes URL to check if it's a valid downloadable video or subtitle."""
        if not url:
            return

        is_video = False
        target_clean_url = url

        # 1. YouTube Video, Shorts or Playlist
        if "youtube.com/watch" in url or "youtu.be/" in url or "youtube.com/shorts/" in url or "youtube.com/playlist" in url:
            target_clean_url = clean_video_url(url)
            is_video = True

        # 2. Douyin Video
        elif "douyin.com" in url:
            target_clean_url = clean_video_url(url)
            if "/video/" in target_clean_url or "modal_id=" in url:
                is_video = True

        # 3. TikTok Video
        elif "tiktok.com" in url:
            if "/video/" in url or "modal_id=" in url or "/@" in url:
                is_video = True

        # 4. Facebook Video / Watch
        elif "facebook.com" in url or "fb.watch" in url:
            if "/videos/" in url or "/watch" in url or "fb.watch" in url:
                is_video = True

        # 5. Bilibili Video (supports /zh-Hans/video/BV..., /video/BV..., /video/av...)
        elif "bilibili.com" in url:
            target_clean_url = clean_video_url(url)
            if "bilibili.com/video/" in target_clean_url or "BV" in url:
                is_video = True

        # 6. Sabayflix Movie Page
        elif "sabayflix.net/movie/" in url:
            target_clean_url = clean_video_url(url)
            is_video = True

        # 7. KH Diamond Movie Page
        elif "khdiamond.net/movies/" in url:
            target_clean_url = clean_video_url(url)
            is_video = True

        # 8. Hongguo Drama Series
        elif "hongguoduanju.com" in url:
            target_clean_url = clean_video_url(url)
            if "/player/" in target_clean_url or "detail" in url:
                is_video = True

        # 9. StardustTV Short Drama
        elif "stardusttv.net" in url:
            target_clean_url = clean_video_url(url)
            if "/episodes/" in target_clean_url:
                is_video = True

        # 10. Direct media stream
        elif any(url.lower().endswith(ext) or ext in url.lower() for ext in [".mp4", ".m3u8", ".webm", ".mov", ".flv"]):
            is_video = True

        if is_video:
            # If current detected URL is already a full movie stream, don't revert to top page URL
            if not getattr(self, "is_current_full_movie", False) or not self.current_detected_url:
                self.current_detected_url = target_clean_url
                self._update_detected_ui(target_clean_url, self.current_page_title)

            # Also ensure the clean video URL is registered in Network Processing drawer
            clean_sig = f"main_page:{target_clean_url}"
            if clean_sig not in self.seen_signatures and not any(target_clean_url.lower().endswith(x) for x in [".m4s", ".m3u8", ".mp3", ".vtt", ".srt"]):
                self.seen_signatures.add(clean_sig)
                p_label = "🎬 Bilibili Video (Clean URL)" if "bilibili" in target_clean_url else ("🎬 Hongguo Drama" if "hongguo" in target_clean_url else ("🎬 StardustTV Episode" if "stardusttv" in target_clean_url else "🎬 Main Video Page"))
                p_domain = target_clean_url.split("//")[-1].split("/")[0]
                self._on_network_media_intercepted(target_clean_url, p_label, p_domain)

    def _update_detected_ui(self, url: str, title: str = "", is_full_movie: bool = False, duration_str: str = ""):
        display_text = f"{title}\n{url}" if title and title != url else url
        self.lbl_sniff_url.setText(display_text[:140] + ("..." if len(display_text) > 140 else ""))
        self.sniff_card.setVisible(True)

        if is_full_movie:
            self.sniff_card.setStyleSheet("""
                QFrame#sniff_card {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #064e3b, stop:1 #065f46);
                    border: 2px solid #34d399;
                    border-radius: 6px;
                    padding: 6px 10px;
                }
            """)
            self.lbl_sniff_icon.setText("🎬")
            dur_tag = f" [{duration_str}]" if duration_str else ""
            self.lbl_sniff_status.setText(f"⚡ រកឃើញភាពយន្តពេញ Ready to Download!{dur_tag}:")
            self.lbl_sniff_status.setStyleSheet("color: #6ee7b7; font-weight: bold; font-size: 13px;")

            self.btn_download_top.setText("⚡ Download Full Movie (ទាញយកភាពយន្តពេញ)")
            self.btn_download_top.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #047857);
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 5px 14px;
                    border: 2px solid #34d399;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
            self.btn_download_now.setText("📥 ទាញយកភាពយន្តពេញភ្លាម (Download Full Movie)")
            self.btn_download_now.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 13px;
                    padding: 8px 18px;
                    border: 1px solid #34d399;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
        elif duration_str and ("3:32" in duration_str or "trailer" in title.lower() or "trailer" in url.lower()):
            self.lbl_sniff_icon.setText("🎞️")
            self.lbl_sniff_status.setText(f"🎞️ រកឃើញ Trailer Clip [{duration_str}] - សូមចុច Play ភាពយន្តពេញនៅលើវេបសាយដើម្បីចាប់ Link 2h:37m:")
            self.lbl_sniff_status.setStyleSheet("color: #fde047; font-weight: bold; font-size: 12px;")
            self.btn_download_top.setText(f"📥 Download Trailer ({duration_str})")
            self.btn_download_now.setText(f"📥 ទាញយក Trailer ({duration_str})")
        elif "hongguoduanju.com" in url.lower():
            self.lbl_sniff_icon.setText("🎬")
            self.lbl_sniff_status.setText("⚡ រកឃើញរឿង Hongguo ពេញលេញ (កុំបារម្ភពីសារ '不支持...' នៅក្នុង Web):")
            self.lbl_sniff_status.setStyleSheet("color: #34d399; font-weight: bold; font-size: 12px;")
            self.btn_download_top.setText("📥 ទាញយកភាគ Hongguo ពេញលេញ (Full 720p HD)")
            self.btn_download_top.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 5px 14px;
                    border: 2px solid #34d399;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
            self.btn_download_now.setText("📥 ទាញយកភាគរឿងនេះភ្លាម (Full 720p HD)")
        else:
            self.lbl_sniff_icon.setText("🎯")
            self.lbl_sniff_status.setText("⚡ រកឃើញវីដេអូសម្រាប់ទាញយក (Detected Video Ready to Download!):")
            self.lbl_sniff_status.setStyleSheet("color: #a7f3d0; font-weight: bold; font-size: 12px;")
            self.btn_download_top.setText("⚡ Download This Video (ទាញយកវីដេអូនេះ)")
            self.btn_download_top.setStyleSheet("""
                QPushButton {
                    background-color: #059669;
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 12px;
                    padding: 5px 14px;
                    border: 2px solid #34d399;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #047857;
                }
            """)
            self.btn_download_now.setText("📥 ទាញយកវីដេអូនេះភ្លាម (Download Video)")

    def _hand_off_video(self):
        """Transfers the detected video URL and saved cookies directly to VideoDownloaderView."""
        url = self.current_detected_url
        if not url:
            cur_p = self.entry_url.text().strip()
            # If on a client-side streaming platform, require user to hit play first to catch stream
            if any(dom in cur_p.lower() for dom in ["sabayflix", "khdiamond", "kolabkhmer", "phumikhmer", "merlmovie", "kisskh"]):
                QMessageBox.information(
                    self,
                    "Play Video First / សូមចុច Play",
                    "⚠️ មិនទាន់រកឃើញ Video Stream របស់រឿងនេះនៅឡើយទេ!\n\n"
                    "👉 សូមចុច 'Play' ឬចុចលើខ្សែភាពយន្តនៅលើអេក្រង់ Web ដើម្បីឱ្យវីដេអូចាប់ផ្តើមចាក់ "
                    "នោះ Sniffer នឹងចាប់យក Stream (.m3u8) របស់រឿងនេះភ្លាមៗ!"
                )
                return
            url = clean_video_url(cur_p)

        if not url or url == "about:blank":
            QMessageBox.warning(self, "No Video", "សូមបើកទំព័រវីដេអូណាមួយជាមុនសិន!")
            return

        cookie_file = self._save_cookies_silently()
        if self.on_video_selected:
            self.on_video_selected(url, cookie_file)
        self.accept()

    def _copy_detected_url(self):
        url = self.current_detected_url or clean_video_url(self.entry_url.text().strip())
        if url:
            from ui_v_PyQt6.qt_compat import QApplication
            QApplication.clipboard().setText(url)
            self.btn_copy_detected.setText("Copied! ✅")
            QTimer.singleShot(1500, lambda: self.btn_copy_detected.setText("📋 Copy Link"))

    def _copy_all_grabbed_urls(self):
        """Grabs and copies all intercepted video URLs to clipboard."""
        urls = list(getattr(self, "all_grabbed_video_urls", []))
        if self.current_detected_url and self.current_detected_url not in urls:
            urls.insert(0, self.current_detected_url)

        if not urls:
            QMessageBox.information(self, "No URLs", "មិនទាន់មាន Link វីដេអូត្រូវបានចាប់យកនៅឡើយទេ!")
            return

        from ui_v_PyQt6.qt_compat import QApplication
        QApplication.clipboard().setText("\n".join(urls))
        if hasattr(self, "btn_grab_all_urls"):
            self.btn_grab_all_urls.setText(f"Copied {len(urls)} URLs! ✅")
            QTimer.singleShot(2000, lambda: self.btn_grab_all_urls.setText(f"📋 Grab All URLs ({len(urls)})"))
        QMessageBox.information(self, "Grab All URLs", f"បានចម្លង {len(urls)} Video Links ទាំងអស់ទៅកាន់ Clipboard រួចរាល់!\nអ្នកអាច Paste ចូលក្នុងប្រអប់ទាញយក ឬរក្សាទុកបាន។")

    def _play_detected_stream(self):
        """Bypasses browser player limitations and plays the video stream directly via ffplay / system player."""
        url = self.current_detected_url or clean_video_url(self.entry_url.text().strip())
        if not url or url == "about:blank":
            QMessageBox.warning(self, "No Video", "សូមបើកទំព័រវីដេអូណាមួយជាមុនសិន!")
            return

        play_url = url
        dec_key = ""
        if "hongguoduanju.com" in url:
            try:
                import json, ssl
                m = re.findall(r'/(\d{10,25})', url)
                sid = m[0] if m else ""
                vid = m[1] if len(m) >= 2 else sid
                if sid and vid:
                    api_url = "https://hongguoduanju.com/api/video/protected/play-info"
                    payload = json.dumps({"series_id": str(sid), "item_id": str(vid), "definition": "720p"}).encode('utf-8')
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": f"https://hongguoduanju.com/player/{sid}/{vid}",
                        "Content-Type": "application/json",
                        "Origin": "https://hongguoduanju.com"
                    }
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    req = urllib.request.Request(api_url, data=payload, headers=headers)
                    with urllib.request.urlopen(req, context=ctx, timeout=8) as r:
                        data = json.loads(r.read().decode('utf-8'))
                        pi = data.get("play_info", {})
                        if pi.get("main_url"):
                            play_url = pi["main_url"]
                            from ui_v_PyQt6.components.downloader.video_downloader_view import unwrap_spade
                            dec_key = unwrap_spade(pi.get("player_access_key"))
                        else:
                            play_url = f"https://hongguoduanju.com/video/public/{vid}/360p.mp4"
            except Exception:
                pass

        ffplay_bin = shutil.which("ffplay") or os.path.abspath("bin/ffplay.exe")
        if ffplay_bin and os.path.exists(ffplay_bin):
            title = self.current_page_title or "Video Stream Player"
            cmd = [
                ffplay_bin,
                "-window_title", f"🎬 {title[:50]}",
                "-autoexit"
            ]
            if dec_key:
                cmd.extend(["-decryption_key", dec_key])
            cmd.append(play_url)
            subprocess.Popen(cmd)
        else:
            import webbrowser
            webbrowser.open(play_url)

    def _on_cookie_added(self, cookie: "QNetworkCookie"):
        """Triggered whenever a cookie is set by the browser."""
        name = bytes(cookie.name()).decode("utf-8", errors="ignore")
        domain = cookie.domain()
        self.cookies_map[(domain, name)] = cookie
        self.lbl_cookie_badge.setText(f"🍪 Cookies: {len(self.cookies_map)}")
        # Auto-save cookies in real time debounced by 1.5 seconds
        if hasattr(self, "auto_cookie_timer"):
            self.auto_cookie_timer.start(1500)

    def _save_cookies_silently(self) -> str:
        """Saves captured cookies to disk using atomic rename to prevent half-written/corrupt file reads."""
        if not self.cookies_map:
            return ""

        out_path = os.path.abspath("cookies.txt")
        tmp_path = out_path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Safely captured by AI Khmer Movie Studio Built-in Browser\n\n")
                for cookie in self.cookies_map.values():
                    f.write(cookie_to_netscape_format(cookie) + "\n")
            if os.path.exists(tmp_path):
                os.replace(tmp_path, out_path)

            if os.path.exists("downloads"):
                dl_path = os.path.abspath(os.path.join("downloads", "cookies.txt"))
                dl_tmp = dl_path + ".tmp"
                with open(dl_tmp, "w", encoding="utf-8") as f:
                    f.write("# Netscape HTTP Cookie File\n\n")
                    for cookie in self.cookies_map.values():
                        f.write(cookie_to_netscape_format(cookie) + "\n")
                if os.path.exists(dl_tmp):
                    os.replace(dl_tmp, dl_path)

            if self.on_cookies_saved:
                self.on_cookies_saved(out_path, len(self.cookies_map))
            return out_path
        except Exception:
            return ""

    def _save_cookies(self):
        """Manual save cookies with confirmation message."""
        if not self.cookies_map:
            QMessageBox.warning(self, "No Cookies", "មិនទាន់ចាប់បាន Cookies ណាមួយនៅឡើយទេ!")
            return

        out_path = self._save_cookies_silently()
        total = len(self.cookies_map)
        QMessageBox.information(
            self,
            "Cookies Saved",
            f"🎉 បានចាប់យក និងរក្សាទុក Cookies ចំនួន {total} ដោយជោគជ័យ!\n\n"
            f"📁 ទីតាំង: {out_path}\n"
            f"ឥឡូវនេះ Downloader អាចទាញយកវីដេអូបានយ៉ាងរលូន!"
        )

    def done(self, r):
        try:
            self._save_cookies_silently()
        except Exception:
            pass
        try:
            if hasattr(self, "cookie_store") and self.cookie_store:
                self.cookie_store.cookieAdded.disconnect(self._on_cookie_added)
        except Exception:
            pass
        super().done(r)

    def closeEvent(self, event):
        try:
            self._save_cookies_silently()
        except Exception:
            pass
        try:
            if hasattr(self, "cookie_store") and self.cookie_store:
                self.cookie_store.cookieAdded.disconnect(self._on_cookie_added)
        except Exception:
            pass
        super().closeEvent(event)
