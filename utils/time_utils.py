"""
Time & Timestamp Utilities
Converts between seconds, SRT timestamps, filename timestamps, and human-readable time.
"""

from datetime import timedelta

def format_timestamp(seconds: float) -> str:
    """Formats float seconds into standard SRT timestamp HH:MM:SS,mmm"""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def format_filename_timestamp(seconds: float) -> str:
    """Formats seconds into filename-safe timestamp HH-MM-SS_mmm"""
    s = format_timestamp(seconds)
    return s.replace(":", "-").replace(",", "_")

def format_ass_timestamp(seconds: float) -> str:
    """Format seconds into ASS timestamp string H:MM:SS.cc"""
    total_seconds = int(max(0.0, seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

def parse_timestamp_to_seconds(ts_str: str) -> float:
    """Parses standard HH:MM:SS,mmm or HH:MM:SS.mmm into float seconds"""
    try:
        clean = ts_str.strip().replace(",", ".")
        parts = clean.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        return float(clean)
    except Exception:
        return 0.0

import re

def format_voice_filename(sub_id: int, s_time: str, e_time: str, text: str = "", voice_tag: str = "") -> str:
    """
    Builds a unique, descriptive audio filename for a subtitle dialogue line.
    Appends sanitized translated text and optional character voice tag (e.g. M / F)
    so changing the character role or text generates a fresh audio file without cache collision.
    Example:
        format_voice_filename(4, "00-00-05_566", "00-00-07_166", "សួស្តី", "F")
        -> "#4_00-00-05_566_to_00-00-07_166_F_សួស្តី.mp3"
    """
    clean_txt = ""
    if text:
        # Remove characters forbidden in Windows filenames: \ / : * ? " < > | and control chars
        clean_txt = re.sub(r'[\s\\/*?:"<>|\r\n\t]+', '_', str(text).strip()).strip('_')
        # Limit to 30 characters to stay safely within filesystem MAX_PATH limits
        clean_txt = clean_txt[:30].strip('_')

    tag_str = f"_{voice_tag}" if voice_tag else ""
    if clean_txt:
        return f"#{sub_id}_{s_time}_to_{e_time}{tag_str}_{clean_txt}.mp3"
    return f"#{sub_id}_{s_time}_to_{e_time}{tag_str}.mp3"


def format_duration_short(seconds: float) -> str:
    """Formats seconds into human-friendly duration: MM:SS or HH:MM:SS"""
    s = max(0, int(round(seconds)))
    m = s // 60
    sec = s % 60
    h = m // 60
    if h > 0:
        return f"{h:02d}:{m%60:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def format_compact_time(seconds: float, force_hours: bool = False, include_millis: bool = False) -> str:
    """
    Formats float seconds into clean, human-readable compact timecode:
    - If video/time is under 1 hour (< 3600s): returns MM:SS (e.g. 00:00, 00:07, 04:55, 05:00)
    - If video/time is 1 hour or more: returns HH:MM:SS (e.g. 01:02:15)
    - If include_millis=True: appends .s (tenths of second)
    """
    total_sec = max(0.0, float(seconds))
    s_int = int(total_sec)
    hours = s_int // 3600
    minutes = (s_int % 3600) // 60
    secs = s_int % 60

    if include_millis:
        millis = int(round((total_sec - s_int) * 10))
        if millis >= 10:
            millis = 9
        if hours > 0 or force_hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:01d}"
        return f"{minutes:02d}:{secs:02d}.{millis:01d}"

    if hours > 0 or force_hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_compact_timing_range(start_sec: float, end_sec: float, force_hours: bool = False) -> str:
    """
    Formats subtitle dialogue range cleanly without unnecessary hours or milliseconds.
    Example:
        format_compact_timing_range(0.0, 7.73) -> "00:00 -> 00:07"
        format_compact_timing_range(65.2, 70.0) -> "01:05 -> 01:10"
        format_compact_timing_range(3605.0, 3612.0) -> "01:00:05 -> 01:00:12"
    """
    s_val = max(0.0, float(start_sec))
    e_val = max(0.0, float(end_sec))
    has_hours = force_hours or (s_val >= 3600.0) or (e_val >= 3600.0)

    # If cue duration is very short and start/end round to exact same second, show tenths
    if int(s_val) == int(e_val) and abs(e_val - s_val) > 0.05:
        st_str = format_compact_time(s_val, force_hours=has_hours, include_millis=True)
        en_str = format_compact_time(e_val, force_hours=has_hours, include_millis=True)
    else:
        st_str = format_compact_time(s_val, force_hours=has_hours, include_millis=False)
        en_str = format_compact_time(e_val, force_hours=has_hours, include_millis=False)

    return f"{st_str} -> {en_str}"

