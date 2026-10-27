"""
Professional Studio Vector Icon Generator for AI Khmer Movie Studio
Powered by QtAwesome (FontAwesome 5/6, Material Design Icons, Iconic).
Renders ultra-sharp, anti-aliased SVG-quality QIcons for menus, buttons, status bars, and table items.
"""

from ui_v_PyQt6.qt_compat import (
    QPixmap, QPainter, QColor, QPen, QBrush, QIcon, QPainterPath, Qt, QRectF
)

try:
    import qtawesome as qta
    _HAS_QTAWESOME = True
except ImportError:
    _HAS_QTAWESOME = False

_ICON_CACHE = {}


def _get_qta_or_fallback(qta_name: str, fallback_creator, color: str = "#ffffff", **kwargs) -> QIcon:
    """Returns a QtAwesome icon if available, otherwise delegates to vector fallback."""
    cache_key = f"{qta_name}_{color}_{kwargs}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    if _HAS_QTAWESOME:
        try:
            icon = qta.icon(qta_name, color=color, **kwargs)
            if not icon.isNull():
                _ICON_CACHE[cache_key] = icon
                return icon
        except Exception:
            pass

    # Fallback to local custom painter
    icon = fallback_creator()
    _ICON_CACHE[cache_key] = icon
    return icon


def get_qta_icon(name: str, color: str = "#ffffff", **kwargs) -> QIcon:
    """Universal QtAwesome icon generator with caching."""
    cache_key = f"qta_{name}_{color}_{kwargs}"
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]
    if _HAS_QTAWESOME:
        try:
            ic = qta.icon(name, color=color, **kwargs)
            _ICON_CACHE[cache_key] = ic
            return ic
        except Exception:
            pass
    return QIcon()


# ---------------- CHARACTER & ACTOR ICONS ----------------
def get_male_icon(size=20, color="#38bdf8") -> QIcon:
    """Crisp male character icon (Avatar / Mars)"""
    def _fallback():
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        r = size * 0.20
        p.drawEllipse(QRectF(size * 0.5 - r, size * 0.12, r * 2, r * 2))
        path = QPainterPath()
        path.moveTo(size * 0.16, size * 0.90)
        path.cubicTo(size * 0.16, size * 0.56, size * 0.84, size * 0.56, size * 0.84, size * 0.90)
        path.closeSubpath()
        p.drawPath(path)
        p.end()
        return QIcon(pm)
    return _get_qta_or_fallback("fa5s.user", _fallback, color=color)


def get_female_icon(size=20, color="#f472b6") -> QIcon:
    """Crisp female character icon"""
    def _fallback():
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        r = size * 0.18
        p.drawEllipse(QRectF(size * 0.5 - r, size * 0.12, r * 2, r * 2))
        path = QPainterPath()
        path.moveTo(size * 0.20, size * 0.90)
        path.lineTo(size * 0.35, size * 0.56)
        path.lineTo(size * 0.65, size * 0.56)
        path.lineTo(size * 0.80, size * 0.90)
        path.closeSubpath()
        p.drawPath(path)
        p.end()
        return QIcon(pm)
    return _get_qta_or_fallback("fa5s.female", _fallback, color=color)


def get_users_icon(size=20, color="#94a3b8") -> QIcon:
    """Dual user silhouette (group / all lines)"""
    def _fallback():
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(color)))
        p.drawEllipse(QRectF(size * 0.15, size * 0.20, size * 0.34, size * 0.34))
        p.end()
        return QIcon(pm)
    return _get_qta_or_fallback("fa5s.users", _fallback, color=color)


# ---------------- CONTROLS & TIMELINE ICONS ----------------
def get_swap_icon(size=20, color="#06b6d4") -> QIcon:
    """Cycle / swap arrows icon"""
    return _get_qta_or_fallback("fa5s.exchange-alt", lambda: QIcon(), color=color)


def get_speed_icon(size=20, color="#f59e0b") -> QIcon:
    """Speedometer / gauge icon"""
    return _get_qta_or_fallback("fa5s.tachometer-alt", lambda: QIcon(), color=color)


def get_mic_icon(size=20, color="#a855f7") -> QIcon:
    """Studio microphone icon"""
    return _get_qta_or_fallback("fa5s.microphone-alt", lambda: QIcon(), color=color)


def get_dub_icon(size=20, color="#10b981") -> QIcon:
    """Studio headphones dubbing icon"""
    return _get_qta_or_fallback("fa5s.headphones-alt", lambda: QIcon(), color=color)


def get_listen_icon(size=20, color="#38bdf8") -> QIcon:
    """Audio playback speaker with waves"""
    return _get_qta_or_fallback("fa5s.volume-up", lambda: QIcon(), color=color)


def get_translate_icon(size=20, color="#3b82f6") -> QIcon:
    """Globe / language icon"""
    return _get_qta_or_fallback("fa5s.language", lambda: QIcon(), color=color)


def get_copy_icon(size=20, color="#94a3b8") -> QIcon:
    """Document copy icon"""
    return _get_qta_or_fallback("fa5s.copy", lambda: QIcon(), color=color)


def get_plus_icon(size=20, color="#10b981") -> QIcon:
    """Add / insert line icon"""
    return _get_qta_or_fallback("fa5s.plus", lambda: QIcon(), color=color)


def get_trash_icon(size=20, color="#ef4444") -> QIcon:
    """Delete / trash icon"""
    return _get_qta_or_fallback("fa5s.trash-alt", lambda: QIcon(), color=color)


def get_clock_icon(size=20, color="#38bdf8") -> QIcon:
    """Timing clock icon"""
    return _get_qta_or_fallback("fa5s.clock", lambda: QIcon(), color=color)


def get_edit_icon(size=20, color="#f59e0b") -> QIcon:
    """Pencil / edit icon"""
    return _get_qta_or_fallback("fa5s.pencil-alt", lambda: QIcon(), color=color)


def get_sync_icon(size=20, color="#06b6d4") -> QIcon:
    """Refresh / auto-sync loop icon"""
    return _get_qta_or_fallback("fa5s.sync-alt", lambda: QIcon(), color=color)


def get_ai_icon(size=20, color="#ec4899") -> QIcon:
    """AI Magic / Sparkle icon"""
    return _get_qta_or_fallback("fa5s.magic", lambda: QIcon(), color=color)


def get_bot_icon(size=20, color="#10b981") -> QIcon:
    """Robot / AI Model icon"""
    return _get_qta_or_fallback("fa5s.robot", lambda: QIcon(), color=color)


def get_rewind_icon(size=20, color="#38bdf8") -> QIcon:
    """Rewind << icon"""
    return _get_qta_or_fallback("fa5s.backward", lambda: QIcon(), color=color)


def get_forward_icon(size=20, color="#38bdf8") -> QIcon:
    """Forward >> icon"""
    return _get_qta_or_fallback("fa5s.forward", lambda: QIcon(), color=color)


def get_minus_icon(size=20, color="#f87171") -> QIcon:
    """Minus / trim icon"""
    return _get_qta_or_fallback("fa5s.minus", lambda: QIcon(), color=color)


# ---------------- NEW EXTENDED STUDIO ICONS ----------------
def get_play_icon(size=20, color="#38bdf8") -> QIcon:
    """Play icon"""
    return _get_qta_or_fallback("fa5s.play", lambda: QIcon(), color=color)


def get_pause_icon(size=20, color="#f59e0b") -> QIcon:
    """Pause icon"""
    return _get_qta_or_fallback("fa5s.pause", lambda: QIcon(), color=color)


def get_stop_icon(size=20, color="#ef4444") -> QIcon:
    """Stop icon"""
    return _get_qta_or_fallback("fa5s.stop", lambda: QIcon(), color=color)


def get_folder_icon(size=20, color="#f59e0b") -> QIcon:
    """Folder open icon"""
    return _get_qta_or_fallback("fa5s.folder-open", lambda: QIcon(), color=color)


def get_download_icon(size=20, color="#38bdf8") -> QIcon:
    """Download icon"""
    return _get_qta_or_fallback("fa5s.cloud-download-alt", lambda: QIcon(), color=color)


def get_cut_icon(size=20, color="#06b6d4") -> QIcon:
    """Scissors / cut icon"""
    return _get_qta_or_fallback("fa5s.cut", lambda: QIcon(), color=color)


def get_film_icon(size=20, color="#f59e0b") -> QIcon:
    """Film strip icon"""
    return _get_qta_or_fallback("fa5s.film", lambda: QIcon(), color=color)


def get_video_icon(size=20, color="#38bdf8") -> QIcon:
    """Video camera icon"""
    return _get_qta_or_fallback("fa5s.video", lambda: QIcon(), color=color)


def get_clean_icon(size=20, color="#ef4444") -> QIcon:
    """Broom / clear icon"""
    return _get_qta_or_fallback("fa5s.broom", lambda: QIcon(), color=color)


def get_check_icon(size=20, color="#10b981") -> QIcon:
    """Checkmark icon"""
    return _get_qta_or_fallback("fa5s.check", lambda: QIcon(), color=color)


def get_search_icon(size=20, color="#94a3b8") -> QIcon:
    """Search / magnifying glass icon"""
    return _get_qta_or_fallback("fa5s.search", lambda: QIcon(), color=color)


def get_export_icon(size=20, color="#10b981") -> QIcon:
    """Export / upload icon"""
    return _get_qta_or_fallback("fa5s.file-export", lambda: QIcon(), color=color)


def get_settings_icon(size=20, color="#94a3b8") -> QIcon:
    """Settings / sliders icon"""
    return _get_qta_or_fallback("fa5s.sliders-h", lambda: QIcon(), color=color)


def get_fullscreen_icon(size=20, color="#94a3b8") -> QIcon:
    """Fullscreen expand icon"""
    return _get_qta_or_fallback("fa5s.expand", lambda: QIcon(), color=color)

