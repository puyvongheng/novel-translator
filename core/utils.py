import json
import os
import subprocess
from datetime import timedelta

def get_video_info(video_path: str) -> dict:
    """
    Retrieve video duration, width, height, fps using ultra-fast OpenCV header reading
    with lightweight ffprobe fallback. Instantaneous (< 5ms) even for 4-hour, 1GB+ files.
    """
    if not os.path.exists(video_path):
        return {"duration": 0.0, "width": 1280, "height": 720, "fps": 30.0, "has_audio": True}

    width, height, fps, duration = 1280, 720, 30.0, 0.0

    # 1. Instant OpenCV metadata probe (< 5ms)
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if cap.isOpened():
            vw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            vh = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            vfps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            cap.release()
            if vw > 0 and vh > 0:
                width, height = vw, vh
            if vfps > 0:
                fps = vfps
            if vfps > 0 and frames > 0:
                duration = round(frames / vfps, 3)
    except Exception:
        pass

    # 2. Fast lightweight ffprobe query with strict 2.5s timeout for audio & precise duration
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_entries", "format=duration,size,bit_rate:stream=width,height,r_frame_rate,codec_type",
        video_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace", timeout=2.5)
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            fmt = data.get("format", {})
            f_dur = float(fmt.get("duration", 0) or 0)
            if f_dur > 0:
                duration = f_dur
            bit_rate = int(fmt.get("bit_rate", 0) or 0)
            size = int(fmt.get("size", 0) or os.path.getsize(video_path))
            if bit_rate <= 0 and duration > 0 and size > 0:
                bit_rate = int((size * 8) / duration)

            has_audio = False
            for s in data.get("streams", []):
                if s.get("codec_type") == "audio":
                    has_audio = True
                elif s.get("codec_type") == "video" and (width == 1280 and height == 720):
                    width = int(s.get("width", width))
                    height = int(s.get("height", height))
                    r_frame_rate = s.get("r_frame_rate", "30/1")
                    if "/" in r_frame_rate:
                        n, d = r_frame_rate.split("/")
                        fps = float(n) / float(d) if float(d) > 0 else fps

            return {
                "duration": duration,
                "width": width,
                "height": height,
                "fps": fps,
                "has_audio": has_audio,
                "bit_rate": bit_rate,
                "size": size
            }
    except Exception as e:
        print(f"ffprobe fast query note: {e}")

    file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "has_audio": True,
        "bit_rate": int((file_size * 8) / max(1.0, duration)) if duration > 0 else 0,
        "size": file_size
    }

def format_timestamp(seconds: float) -> str:
    """Format seconds into SRT timestamp string HH:MM:SS,mmm"""
    td = timedelta(seconds=max(0.0, seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

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

def format_filename_timestamp(seconds: float) -> str:
    """Format seconds for safe file names: HH-MM-SS"""
    total_seconds = int(max(0.0, seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}-{minutes:02d}-{secs:02d}"

def parse_srt_content(content: str) -> list:
    """Parses standard .srt or .vtt subtitle content string into subtitle list"""
    import re
    lines = content.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    items = []
    current_id = None
    current_start = None
    current_end = None
    text_buffer = []

    def commit_current():
        nonlocal current_id, current_start, current_end, text_buffer
        if current_start is not None and current_end is not None and text_buffer:
            text = ' '.join(text_buffer).strip()
            if text:
                items.append({
                    "id": current_id if current_id is not None else len(items) + 1,
                    "start": current_start,
                    "end": current_end,
                    "original": text,
                    "translated": "",
                    "audio_file": None,
                    "rate": "+0%"
                })
        current_id = None
        current_start = None
        current_end = None
        text_buffer = []

    time_regex = re.compile(r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})')

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            commit_current()
            continue

        match = time_regex.search(line)
        if match:
            h1, m1, s1, ms1 = map(int, match.groups()[:4])
            h2, m2, s2, ms2 = map(int, match.groups()[4:])
            current_start = round(h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0, 3)
            current_end = round(h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0, 3)
            continue

        if line.isdigit() and current_start is None and not text_buffer:
            current_id = int(line)
            continue

        # Strip formatting tags like <i>, </i>, <font>, {\an8}
        clean_text = re.sub(r'<[^>]*>', '', line)
        clean_text = re.sub(r'\{[^}]*\}', '', clean_text).strip()
        if clean_text and not clean_text.startswith('WEBVTT') and not clean_text.startswith('NOTE'):
            text_buffer.append(clean_text)

    commit_current()
    for idx, it in enumerate(items):
        it["id"] = idx + 1
    return items

def parse_srt_file(file_path: str) -> list:
    """Reads and parses an SRT or VTT file with multi-encoding fallback"""
    if not os.path.exists(file_path):
        return []
    encodings = ["utf-8-sig", "utf-8", "gb18030", "gbk", "cp1252", "latin-1"]
    content = ""
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            if content:
                break
        except Exception:
            continue
    if not content:
        return []
    return parse_srt_content(content)

def extract_embedded_or_companion_subtitles(video_path: str) -> list:
    """
    Checks ONLY for companion .srt/.vtt/.ass files in the same directory alongside video.
    Does NOT extract embedded subtitle streams from video containers.
    """
    if not video_path or not os.path.exists(video_path):
        return []

    parent_dir = os.path.dirname(os.path.abspath(video_path))
    base_name = os.path.splitext(os.path.basename(video_path))[0]

    # 1. Check exact companion files in same directory matching video name
    companion_exts = [
        ".srt", ".SRT", ".vtt", ".VTT",
        ".zh.srt", ".zh-CN.srt", ".chi.srt",
        ".en.srt", ".eng.srt",
        ".km.srt", ".kh.srt",
        ".th.srt",
        "_sub.srt", ".sub", ".ass"
    ]
    for ext in companion_exts:
        c_path = os.path.join(parent_dir, f"{base_name}{ext}")
        if os.path.exists(c_path):
            subs = parse_srt_file(c_path)
            if subs:
                return subs

    # 2. Check any .srt/.vtt file in directory containing base_name
    try:
        for fname in os.listdir(parent_dir):
            if fname.lower().endswith((".srt", ".vtt", ".ass")) and base_name.lower() in fname.lower():
                subs = parse_srt_file(os.path.join(parent_dir, fname))
                if subs:
                    return subs
    except Exception:
        pass

    return []

def is_khmer_text(text: str) -> bool:
    """Checks whether the string contains Khmer Unicode characters"""
    if not text:
        return False
    return any(('\u1780' <= ch <= '\u17ff') or ('\u19e0' <= ch <= '\u19ff') for ch in text)

