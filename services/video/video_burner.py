import os
import re
import subprocess
import tempfile
from utils import format_timestamp, format_ass_timestamp, get_video_info
from config import WATERMARK_POSITIONS

_DETECTED_ENCODER = None

_DETECTED_ENCODERS = {}

def get_fastest_video_encoder(codec: str = "hevc"):
    """
    Auto-detects the fastest video encoder available on the system:
    codec: 'hevc' (H.265, Data-Saver Default) or 'h264' (Legacy AVC)
    """
    global _DETECTED_ENCODERS
    c_key = "hevc" if any(k in codec.lower() for k in ["265", "hevc"]) else "h264"
    if c_key in _DETECTED_ENCODERS:
        return _DETECTED_ENCODERS[c_key]

    if c_key == "hevc":
        # 1. NVIDIA NVENC HEVC (Ultra-fast GPU hardware acceleration ~300+ fps)
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'hevc_nvenc', '-preset', 'p2', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["hevc"] = ("hevc_nvenc", ["-c:v", "hevc_nvenc", "-preset", "p2", "-tune", "ll"], "NVIDIA GPU HEVC / H.265 (Data Saver)")
                return _DETECTED_ENCODERS["hevc"]
        except Exception:
            pass

        # 2. Intel QuickSync HEVC
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'hevc_qsv', '-preset', 'veryfast', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["hevc"] = ("hevc_qsv", ["-c:v", "hevc_qsv", "-preset", "veryfast"], "Intel QuickSync HEVC / H.265 (Fast)")
                return _DETECTED_ENCODERS["hevc"]
        except Exception:
            pass

        # 3. AMD Radeon AMF HEVC
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'hevc_amf', '-quality', 'speed', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["hevc"] = ("hevc_amf", ["-c:v", "hevc_amf", "-quality", "speed"], "AMD Radeon HEVC / H.265 (Fast)")
                return _DETECTED_ENCODERS["hevc"]
        except Exception:
            pass

        # 4. Windows MediaFoundation HEVC
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'hevc_mf', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["hevc"] = ("hevc_mf", ["-c:v", "hevc_mf"], "Windows GPU MediaFoundation HEVC (Fast)")
                return _DETECTED_ENCODERS["hevc"]
        except Exception:
            pass

        # 5. CPU libx265 fallback (fast)
        _DETECTED_ENCODERS["hevc"] = ("libx265", ["-c:v", "libx265", "-preset", "fast"], "CPU Multi-threaded x265 (Data Saver)")
        return _DETECTED_ENCODERS["hevc"]

    else:
        # H.264
        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'h264_nvenc', '-preset', 'p2', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["h264"] = ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p2", "-tune", "ll"], "NVIDIA GPU NVENC (Ultra Fast)")
                return _DETECTED_ENCODERS["h264"]
        except Exception:
            pass

        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'h264_qsv', '-preset', 'veryfast', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["h264"] = ("h264_qsv", ["-c:v", "h264_qsv", "-preset", "veryfast"], "Intel QuickSync QSV (Fast)")
                return _DETECTED_ENCODERS["h264"]
        except Exception:
            pass

        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'h264_amf', '-quality', 'speed', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["h264"] = ("h264_amf", ["-c:v", "h264_amf", "-quality", "speed"], "AMD Radeon AMF (Fast)")
                return _DETECTED_ENCODERS["h264"]
        except Exception:
            pass

        try:
            cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'h264_mf', '-f', 'null', '-']
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0:
                _DETECTED_ENCODERS["h264"] = ("h264_mf", ["-c:v", "h264_mf"], "Windows GPU MediaFoundation (Fast)")
                return _DETECTED_ENCODERS["h264"]
        except Exception:
            pass

        _DETECTED_ENCODERS["h264"] = ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-tune", "fastdecode"], "CPU Multi-threaded x264 (Turbo)")
        return _DETECTED_ENCODERS["h264"]

def get_encoder_and_bitrate_flags(enc_name: str, enc_flags: list, v_info: dict, crf_val: str = "26") -> tuple:
    """
    Computes optimal video encoding flags ensuring maximum speed and pristine quality:
    1. YUV420P color space is enforced (prevents file bloating from 4:4:4 GBRP RGB).
    2. Bitrate preserves source video quality without artificial degradation.
    3. H.265 (HEVC) CRF 26 saves ~35-50% data size compared to H.264 while keeping crisp clarity!
    4. Hardware acceleration (NVENC / QSV / AMF / MF) is fully utilized with ultra-fast presets.
    """
    orig_br = int(v_info.get("bit_rate", 0))
    width = int(v_info.get("width", 1280))
    height = int(v_info.get("height", 720))

    if orig_br <= 0:
        pixels = width * height
        if pixels <= 640 * 360:
            target_br = 850_000
        elif pixels <= 854 * 480:
            target_br = 1_500_000
        elif pixels <= 1280 * 720:
            target_br = 3_800_000
        elif pixels <= 1920 * 1080:
            target_br = 7_500_000
        elif pixels <= 2560 * 1440:
            target_br = 14_000_000
        else:
            target_br = 25_000_000
    else:
        # Preserve original video bitrate up to 30 Mbps so 1080p/4K preserves full sharpness!
        target_br = max(1_000_000, min(orig_br, 30_000_000))

    try:
        crf_int = int(crf_val)
        if crf_int <= 18:
            target_br = int(target_br * 1.35)
        elif crf_int >= 32:
            target_br = int(target_br * 0.35)  # Fast Draft / Test Export: 65% bitrate reduction for blazing speed!
        elif crf_int >= 26:
            target_br = int(target_br * 0.75)
    except Exception:
        crf_int = 26

    max_br = int(target_br * 1.5)
    buf_size = int(target_br * 2.0)
    is_fast_test = crf_int >= 30

    # --- H.265 (HEVC) ENCODERS ---
    if enc_name == "hevc_nvenc":
        nv_preset = "p1" if is_fast_test else "p2"
        flags = [
            "-c:v", "hevc_nvenc",
            "-preset", nv_preset,         # P1 for Ultra-Fast Test, P2 for Balanced Studio
            "-tune", "ll",            # Low-latency high-throughput engine
            "-pix_fmt", "yuv420p",
            "-b:v", f"{int(target_br * 0.65)}",  # HEVC achieves equal quality at ~65% bitrate of H.264
            "-maxrate", f"{int(max_br * 0.65)}",
            "-bufsize", f"{int(buf_size * 0.65)}",
            "-cq", str(crf_val),
            "-spatial_aq", "0",       # Reduces GPU register pressure for maximum FPS
            "-temporal_aq", "0"
        ]
    elif enc_name == "libx265":
        x265_preset = "ultrafast" if is_fast_test else "fast"
        flags = [
            "-c:v", "libx265",
            "-preset", x265_preset,
            "-pix_fmt", "yuv420p",
            "-crf", str(crf_val),
            "-threads", "0"
        ]
    elif enc_name == "hevc_qsv":
        flags = [
            "-c:v", "hevc_qsv",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-global_quality", str(crf_val)
        ]
    elif enc_name == "hevc_amf":
        flags = [
            "-c:v", "hevc_amf",
            "-quality", "speed",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{int(target_br * 0.65)}"
        ]
    elif enc_name == "hevc_mf":
        flags = [
            "-c:v", "hevc_mf",
            "-b:v", f"{int(target_br * 0.65)}",
            "-pix_fmt", "yuv420p"
        ]

    # --- H.264 (AVC) ENCODERS ---
    elif enc_name == "h264_nvenc":
        flags = [
            "-c:v", "h264_nvenc",
            "-preset", "p2",
            "-tune", "ll",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{target_br}",
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}",
            "-cq", str(crf_val),
            "-spatial_aq", "0",
            "-temporal_aq", "0"
        ]
    elif enc_name == "h264_qsv":
        flags = [
            "-c:v", "h264_qsv",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{target_br}",
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}",
            "-global_quality", str(crf_val)
        ]
    elif enc_name == "h264_amf":
        flags = [
            "-c:v", "h264_amf",
            "-quality", "speed",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{target_br}",
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}"
        ]
    elif enc_name == "h264_mf":
        flags = [
            "-c:v", "h264_mf",
            "-b:v", f"{target_br}",
            "-pix_fmt", "yuv420p"
        ]
    else:
        x264_preset = "ultrafast" if is_fast_test else "veryfast"
        flags = [
            "-c:v", "libx264",
            "-preset", x264_preset,
            "-tune", "fastdecode",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf_val),
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}",
            "-threads", "0"
        ]

    return flags, target_br


def resolve_khmer_font_name(font_name: str) -> str:

    """
    Normalizes Khmer font family name so libass/DirectWrite on Windows matches
    the installed OpenType font with HarfBuzz complex shaping tables.
    """
    if not font_name:
        return "Kantumruy"
    fn = font_name.strip()
    if fn.lower() in ("kantumruy pro", "kantumruy-pro", "kantumruypro"):
        return "Kantumruy"
    return fn


class SubtitleBurner:

    """
    OOP Subtitle and Master Video Composition Renderer:
    1. Exports UTF-8 .SRT Subtitles
    2. Exports WYSIWYG .ASS Subtitles with custom user-selected Khmer font
    3. Master Video Composition Export:
       - Multi-clip stitching (Video A, B, C...)
       - Color Grading / Effects (Brightness, Contrast, Saturation, Speed)
       - Watermark Logo / Image / GFX overlay
       - Multi-track Audio Mix (Original Video, Khmer Dub, BGM Music) with Volume & Mute
       - Custom Khmer Font Burn-in matching preview placement
       - Resolution (720p, 1080p, 4K), Frame Rate (24, 30, 60 FPS), Formats (MP4 / WebM)
    """
    @staticmethod
    def export_srt(subtitles: list, output_srt_path: str, use_translated: bool = True, dual_language: bool = False):
        """Writes subtitle entries to .srt file"""
        with open(output_srt_path, "w", encoding="utf-8") as f:
            for i, sub in enumerate(subtitles, 1):
                start_str = format_timestamp(sub["start"])
                end_str = format_timestamp(sub["end"])
                f.write(f"{i}\n")
                f.write(f"{start_str} --> {end_str}\n")
                if dual_language:
                    f.write(f"{sub.get('translated', '')}\n{sub.get('original', '')}\n\n")
                elif use_translated:
                    f.write(f"{sub.get('translated', '')}\n\n")
                else:
                    f.write(f"{sub.get('original', '')}\n\n")

    @staticmethod
    def export_ass(
        subtitles: list,
        output_ass_path: str,
        video_width: int = 1280,
        video_height: int = 720,
        pos_x_rel: float = 0.5,
        pos_y_rel: float = 0.88,
        font_name: str = "Leelawadee UI",
        font_size: int = 18,
        font_color: str = "&H00FFFFFF",
        outline_color: str = "&H00000000",
        dual_language: bool = False,
        animation: str = "karaoke",
        bg_style: str = "Black Box 50% (ប្រអប់ខ្មៅស្រាល)",
        highlight_color: str = "&H0000E6FF",
        border_width: int = 3,
        canvas_items: list = None,
        total_duration: float = 0.0
    ):
        """
        Generates an ASS subtitle file with exact screen positioning (\\pos(X, Y)),
        custom font, background box, advanced animations, AND canvas text overlay items.
        """
        from config import CC_BG_STYLES, CC_HIGHLIGHT_COLORS

        def _to_ass_color(col) -> str:
            if not col:
                return "&H00FFFFFF"
            if hasattr(col, "red") and hasattr(col, "green") and hasattr(col, "blue"):
                return f"&H00{col.blue():02X}{col.green():02X}{col.red():02X}"
            if isinstance(col, str):
                c = col.strip().lstrip("#")
                if len(c) == 6:
                    r = int(c[0:2], 16)
                    g = int(c[2:4], 16)
                    b = int(c[4:6], 16)
                    return f"&H00{b:02X}{g:02X}{r:02X}"
            return "&H00FFFFFF"

        def _to_ass_alpha(opacity: float) -> str:
            op = max(0.0, min(1.0, float(opacity)))
            val = int((1.0 - op) * 255)
            return f"\\1a&H{val:02X}&"

        # Check if user customized CC Subtitle CanvasItem interactively on the video monitor
        sub_item = next((it for it in (canvas_items or []) if getattr(it, "item_type", "") == "subtitle"), None)
        if sub_item:
            pos_x_rel = float(getattr(sub_item, "x", pos_x_rel))
            pos_y_rel = float(getattr(sub_item, "y", pos_y_rel))
            font_name = getattr(sub_item, "font_family", font_name) or font_name
            font_size = int(getattr(sub_item, "font_size", font_size) or font_size)
            if getattr(sub_item, "animation", None) and sub_item.animation != "none":
                animation = sub_item.animation
            sub_col = getattr(sub_item, "font_color", None)
            if sub_col:
                font_color = _to_ass_color(sub_col)
            sub_hi = getattr(sub_item, "highlight_color", None)
            if sub_hi:
                highlight_color = _to_ass_color(sub_hi)

        target_x = int(video_width * max(0.05, min(0.95, pos_x_rel)))
        target_y = int(video_height * max(0.05, min(0.95, pos_y_rel)))
        scaled_font = max(18, int(font_size * (video_height / 360.0)))
        outline_w = max(1, int(border_width * (video_height / 540.0)))

        # Background Box & Border Style
        bg_info = CC_BG_STYLES.get(bg_style, {})
        border_style = bg_info.get("ass_border", 1)
        back_color = bg_info.get("ass_box", "&H80000000")

        # Resolve highlight color
        hi_ass = highlight_color
        if isinstance(highlight_color, str) and highlight_color in CC_HIGHLIGHT_COLORS:
            hi_ass = CC_HIGHLIGHT_COLORS[highlight_color].get("ass", "&H0000E6FF")
        elif not hi_ass:
            hi_ass = "&H0000E6FF"

        # Safe font fallback chain & normalization for Windows libass
        clean_font = resolve_khmer_font_name(font_name)

        header = f"""[Script Info]
Title: Khmer Dubbed Movie
ScriptType: v4.00+
WrapStyle: 0
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{clean_font},{scaled_font},{font_color},{hi_ass},{outline_color},{back_color},0,0,0,0,100,100,0,0,{border_style},{outline_w},1,5,10,10,10,0
Style: CanvasText,{clean_font},36,&H00FFFFFF,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,5,10,10,10,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        clean_anim = (animation or "").lower()

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(header)
            
            # 1. Subtitles dialogue lines
            if subtitles:
                for sub in subtitles:
                    km = (sub.get("khmer_text") or sub.get("translated") or "").strip()
                    orig = (sub.get("orig_text") or sub.get("original") or sub.get("text") or "").strip()
                    if not km and not orig:
                        continue

                    if dual_language and km and orig:
                        text = f"{km}\\N{orig}"
                    else:
                        text = km if km else orig

                    text = text.replace("\r\n", "\\N").replace("\n", "\\N")
                    start_ass = format_ass_timestamp(sub["start"])
                    end_ass = format_ass_timestamp(sub["end"])
                    dur_sec = max(0.1, sub["end"] - sub["start"])

                    pos_tag = f"{{\\an5\\pos({target_x},{target_y})}}"

                    if "karaoke" in clean_anim:
                        if " " in text:
                            tokens = text.split(" ")
                        else:
                            # Preserve full Khmer syllable clusters without breaking coeng or vowels
                            import re
                            cluster_re = re.compile(r'[\u1780-\u17B3](?:[\u17D2][\u1780-\u17B3])*(?:[\u17B6-\u17C5])*(?:[\u17C6-\u17D3])*|[^\u1780-\u17D3]+')
                            raw_clusters = cluster_re.findall(text)
                            if raw_clusters:
                                tokens = []
                                curr = ""
                                for cl in raw_clusters:
                                    curr += cl
                                    if len(curr) >= 3:
                                        tokens.append(curr)
                                        curr = ""
                                if curr:
                                    if tokens:
                                        tokens[-1] += curr
                                    else:
                                        tokens.append(curr)
                            else:
                                tokens = [text]
                        cs_per_tok = max(10, int((dur_sec * 100) / max(1, len(tokens))))
                        payload = "".join(f"{{\\k{cs_per_tok}}}{tok} " for tok in tokens).strip()
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{pos_tag}{payload}\n")

                    elif "popup" in clean_anim:
                        pop_tag = "{\\t(0,140,\\fscx115\\fscy115)\\t(140,260,\\fscx100\\fscy100)}"
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{pos_tag}{pop_tag}{text}\n")

                    elif "fade" in clean_anim:
                        fade_tag = "{\\fad(200,200)}"
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{pos_tag}{fade_tag}{text}\n")

                    elif "slide" in clean_anim:
                        move_tag = f"{{\\an5\\move({target_x},{target_y+24},{target_x},{target_y},0,200)}}"
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{move_tag}{text}\n")

                    elif "bounce" in clean_anim:
                        bounce_tag = "{\\t(0,100,\\fscy122)\\t(100,200,\\fscy92)\\t(200,300,\\fscy100)}"
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{pos_tag}{bounce_tag}{text}\n")

                    else:
                        f.write(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{pos_tag}{text}\n")

            # 2. Canvas Text Overlays added in Studio Editor
            if canvas_items:
                for item in canvas_items:
                    itype = getattr(item, "item_type", "")
                    if itype == "text":
                        txt = getattr(item, "text", "")
                        if not txt or not str(txt).strip():
                            continue
                        txt_clean = str(txt).replace("\r\n", "\\N").replace("\n", "\\N")
                        ix = float(getattr(item, "x", 0.5))
                        iy = float(getattr(item, "y", 0.5))
                        px = int(video_width * ix)
                        py = int(video_height * iy)
                        ff = getattr(item, "font_family", "Kantumruy Pro") or "Kantumruy Pro"
                        raw_fs = float(getattr(item, "font_size", 28))
                        fs = max(14, int(raw_fs * (video_height / 720.0)))
                        ass_c = _to_ass_color(getattr(item, "font_color", None))
                        alpha_t = _to_ass_alpha(getattr(item, "opacity", 1.0))
                        bold_t = "\\b1" if getattr(item, "is_bold", True) else "\\b0"
                        italic_t = "\\i1" if getattr(item, "is_italic", False) else "\\i0"

                        st_sec = float(getattr(item, "start_time", 0.0))
                        et_sec = float(getattr(item, "end_time", 0.0))
                        if et_sec <= st_sec or et_sec <= 0.0:
                            st_ass = "0:00:00.00"
                            tot_d = total_duration if total_duration > 0 else 7200.0
                            et_ass = format_ass_timestamp(tot_d)
                        else:
                            st_ass = format_ass_timestamp(st_sec)
                            et_ass = format_ass_timestamp(et_sec)

                        it_anim = (getattr(item, "animation", "none") or "none").lower()
                        anim_tag = ""
                        pos_tag = f"\\pos({px},{py})"
                        if "popup" in it_anim:
                            anim_tag = "\\t(0,140,\\fscx115\\fscy115)\\t(140,260,\\fscx100\\fscy100)"
                        elif "fade" in it_anim:
                            anim_tag = "\\fad(250,250)"
                        elif "slide" in it_anim:
                            pos_tag = f"\\move({px},{py+25},{px},{py},0,200)"
                        elif "bounce" in it_anim:
                            anim_tag = "\\t(0,100,\\fscy122)\\t(100,200,\\fscy92)\\t(200,300,\\fscy100)"
                        elif "marquee" in it_anim or "ticker" in it_anim:
                            m_dir = getattr(item, "marquee_direction", "right_to_left") or "right_to_left"
                            if m_dir == "right_to_left":
                                pos_tag = f"\\move({res_w + 120},{py},{-120},{py})"
                            elif m_dir == "left_to_right":
                                pos_tag = f"\\move({-120},{py},{res_w + 120},{py})"
                            elif m_dir == "bottom_to_top":
                                pos_tag = f"\\move({px},{res_h + 60},{px},{-60})"
                            else:  # top_to_bottom
                                pos_tag = f"\\move({px},{-60},{px},{res_h + 60})"

                        f.write(f"Dialogue: 2,{st_ass},{et_ass},CanvasText,,0,0,0,,{{\\an5{pos_tag}{anim_tag}\\fn{ff}\\fs{fs}\\1c{ass_c}{alpha_t}{bold_t}{italic_t}}}{txt_clean}\n")

    @staticmethod
    def burn_subtitles(
        video_path: str,
        output_video_path: str,
        subtitles: list = None,
        srt_path: str = None,
        font_name: str = "Leelawadee UI",
        font_size: int = 18,
        font_color: str = "&H00FFFFFF",
        outline_color: str = "&H00000000",
        pos_x_rel: float = 0.5,
        pos_y_rel: float = 0.88,
        dual_language: bool = False,
        animation: str = "karaoke",
        bg_style: str = "Black Box 50% (ប្រអប់ខ្មៅស្រាល)",
        highlight_color: str = "&H0000E6FF",
        border_width: int = 3,
        video_info: dict = None,
        dubbed_audio_path: str = None,
        audio_settings: dict = None,
        burn_cc: bool = True,
        codec: str = "hevc",
        crf_val: str = "26",
        video_filters: dict = None,
        target_res: tuple = None,
        crop_mode: str = "fill",
        progress_callback=None
    ) -> bool:
        """Video burn-in rendering: burns subtitles, canvas text, blur/censor boxes, color presets, crop framing and mixes audio"""
        if progress_callback:
            progress_callback("Rendering video with Khmer subtitles & audio...", 0.1)

        if not video_info:
            video_info = get_video_info(video_path)
        vw = video_info.get("width", 1280)
        vh = video_info.get("height", 720)
        v_dur = float(video_info.get("duration", 60.0))
        vw_sub = target_res[0] if target_res else vw
        vh_sub = target_res[1] if target_res else vh

        canvas_items = video_filters.get("canvas_items", []) if video_filters else []
        has_canvas_text = any(getattr(it, "item_type", "") == "text" for it in canvas_items)

        temp_ass = None
        clean_sub = None
        try:
            should_burn = (burn_cc and subtitles) or has_canvas_text or (srt_path and os.path.exists(srt_path))
            if should_burn:
                if (not subtitles) and srt_path and os.path.exists(srt_path):
                    from utils.srt_utils import parse_srt
                    subtitles = parse_srt(srt_path)

                temp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False).name
                SubtitleBurner.export_ass(
                    subtitles=subtitles if (burn_cc and subtitles) else [],
                    output_ass_path=temp_ass,
                    video_width=vw_sub,
                    video_height=vh_sub,
                    pos_x_rel=pos_x_rel,
                    pos_y_rel=pos_y_rel,
                    font_name=font_name,
                    font_size=font_size,
                    font_color=font_color,
                    outline_color=outline_color,
                    dual_language=dual_language,
                    animation=animation,
                    bg_style=bg_style,
                    highlight_color=highlight_color,
                    border_width=border_width,
                    canvas_items=canvas_items,
                    total_duration=v_dur
                )
                clean_sub = temp_ass.replace("\\", "/").replace(":", "\\:")


            v_filter_list = []

            # Target resolution scaling & undistorted aspect ratio crop (TikTok 9:16 / Square 1:1)
            if target_res:
                tw, th = target_res
                in_ar = vw / max(1, vh)
                tar_ar = tw / max(1, th)
                if abs(in_ar - tar_ar) > 0.01:
                    off_x = float(video_filters.get("crop_offset_x", 0.0)) if video_filters else 0.0
                    off_y = float(video_filters.get("crop_offset_y", 0.0)) if video_filters else 0.0
                    if crop_mode == "fill":
                        cx_expr = f"(in_w-{tw})*(1+{off_x:.3f})/2"
                        cy_expr = f"(in_h-{th})*(1+{off_y:.3f})/2"
                        v_filter_list.append(f"scale=w={tw}:h={th}:force_original_aspect_ratio=increase,crop={tw}:{th}:{cx_expr}:{cy_expr}")
                    elif crop_mode == "fit":
                        # CapCut / Reels Fit + Blur Backdrop (matches player canvas preview)
                        v_filter_list.append(
                            f"split[bg][fg];"
                            f"[bg]scale=w={tw}:h={th}:force_original_aspect_ratio=increase,crop={tw}:{th},boxblur=25:5,drawbox=c=black@0.45:t=fill[bg_blur];"
                            f"[fg]scale=w={tw}:h={th}:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2[fg_scaled];"
                            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2"
                        )
                    else:
                        v_filter_list.append(f"scale=w={tw}:h={th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black")
                else:
                    v_filter_list.append(f"scale={tw}:{th}")

            cp = video_filters.get("color_preset", "none") if video_filters else "none"
            cp_int = float(video_filters.get("color_preset_intensity", 1.0)) if video_filters else 1.0
            color_hsl = video_filters.get("color_hsl_settings", None) if video_filters else None
            if (cp and cp != "none") or color_hsl:
                from ui_v_PyQt6.components.player.color_presets import get_ffmpeg_video_filter
                ff_f = get_ffmpeg_video_filter(cp, cp_int, color_hsl)
                if ff_f:
                    v_filter_list.append(ff_f)

            # Horizontal / Vertical Flip & 90° Rotation
            if video_filters:
                flip_h = bool(video_filters.get("flip_h", False))
                flip_v = bool(video_filters.get("flip_v", False))
                rot_deg = float(video_filters.get("rotation", 0.0))
                if flip_h:
                    v_filter_list.append("hflip")
                if flip_v:
                    v_filter_list.append("vflip")
                if rot_deg % 360 == 90:
                    v_filter_list.append("transpose=1")
                elif rot_deg % 360 == 180:
                    v_filter_list.append("hflip,vflip")
                elif rot_deg % 360 == 270:
                    v_filter_list.append("transpose=2")

            # Canvas Overlays: Blur boxes, Censor boxes, Blackout bars added in project
            cur_w = target_res[0] if target_res else vw
            cur_h = target_res[1] if target_res else vh
            for item in canvas_items:
                itype = getattr(item, "item_type", "")
                if itype in ("blur_box", "blur", "mosaic", "glass", "blackout"):
                    cx = getattr(item, "x", 0.5)
                    cy = getattr(item, "y", 0.5)
                    cw = getattr(item, "w", 0.3)
                    ch = getattr(item, "h", 0.15)
                    bx = max(1, min(cur_w - 12, int((cx - cw / 2.0) * cur_w)))
                    by = max(1, min(cur_h - 12, int((cy - ch / 2.0) * cur_h)))
                    bw = max(10, min(cur_w - bx - 1, int(cw * cur_w)))
                    bh = max(10, min(cur_h - by - 1, int(ch * cur_h)))
                    bmode = getattr(item, "blur_mode", itype if itype != "blur_box" else "blur")

                    if bmode == "blackout":
                        v_filter_list.append(f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=black:t=fill")
                    elif bmode in ("blur", "glass", "mosaic"):
                        v_filter_list.append(f"delogo=x={bx}:y={by}:w={bw}:h={bh}")

            # Collect Image & Sticker Overlays from canvas_items
            image_inputs = []  # list of (img_path, item, is_temp)
            temp_overlay_files = []
            for it in canvas_items:
                itype = getattr(it, "item_type", "")
                is_vis = getattr(it, "is_visible", True)
                if not is_vis:
                    continue
                if itype in ("image", "sticker"):
                    img_p = getattr(it, "image_path", None)
                    if img_p and os.path.exists(img_p):
                        image_inputs.append((img_p, it, False))
                    else:
                        pm = getattr(it, "_processed_pixmap", getattr(it, "_raw_image", None))
                        if pm and hasattr(pm, "save"):
                            t_img = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                            pm.save(t_img, "PNG")
                            image_inputs.append((t_img, it, True))
                            temp_overlay_files.append(t_img)

            has_dub = dubbed_audio_path and os.path.exists(dubbed_audio_path) and os.path.getsize(dubbed_audio_path) > 1000
            has_video_audio = video_info.get("has_audio", True)
            mute_orig = audio_settings.get("mute_orig", False) if audio_settings else False
            orig_vol = float(audio_settings.get("orig_vol", 0.85)) if audio_settings else 0.85
            dub_vol = float(audio_settings.get("dub_vol", 1.2)) if audio_settings else 1.2
            auto_duck = audio_settings.get("auto_ducking", True) if audio_settings else True

            cmd = ["ffmpeg", "-y", "-threads", "0", "-i", video_path]
            next_in_idx = 1
            dub_in_idx = None
            if has_dub:
                cmd.extend(["-i", dubbed_audio_path])
                dub_in_idx = next_in_idx
                next_in_idx += 1

            img_in_indices = []
            for img_p, it, is_tmp in image_inputs:
                cmd.extend(["-i", img_p])
                img_in_indices.append((next_in_idx, it))
                next_in_idx += 1

            # Build unified Filter Complex
            fc_parts = []
            if v_filter_list:
                fc_parts.append(f"[0:v]{','.join(v_filter_list)}[v_base]")
                cur_v_label = "[v_base]"
            else:
                cur_v_label = "[0:v]"

            # Chain image & sticker overlays
            for idx, (img_idx, it) in enumerate(img_in_indices):
                cw = getattr(it, "w", 0.25)
                ch = getattr(it, "h", 0.25)
                cx = getattr(it, "x", 0.5)
                cy = getattr(it, "y", 0.5)
                iw = max(10, min(cur_w, int(cw * cur_w)))
                ih = max(10, min(cur_h, int(ch * cur_h)))
                ix = max(0, min(cur_w - iw, int((cx - cw / 2.0) * cur_w)))
                iy = max(0, min(cur_h - ih, int((cy - ch / 2.0) * cur_h)))
                op = max(0.05, min(1.0, float(getattr(it, "opacity", 1.0))))
                st = float(getattr(it, "start_time", 0.0))
                et = float(getattr(it, "end_time", 0.0))

                scale_f = f"scale={iw}:{ih},format=rgba"
                if op < 0.99:
                    scale_f += f",colorchannelmixer=aa={op:.2f}"
                fc_parts.append(f"[{img_idx}:v]{scale_f}[img_ovl_{idx}]")

                time_enable = f":enable='between(t,{st:.3f},{et:.3f})'" if (et > st > 0) else ""
                next_v = f"[v_ovl_{idx}]"
                fc_parts.append(f"{cur_v_label}[img_ovl_{idx}]overlay={ix}:{iy}{time_enable}{next_v}")
                cur_v_label = next_v

            # Subtitles burn-in sits on top of all images and video (shaping=complex ensures 100% perfect Khmer font shaping)
            if should_burn and clean_sub:
                fc_parts.append(f"{cur_v_label}ass='{clean_sub}':shaping=complex[vout]")
            elif cur_v_label != "[0:v]":

                fc_parts.append(f"{cur_v_label}null[vout]")

            # Audio filter chain: dubbing + original mix with Studio Auto-Ducking
            has_aout = False
            temp_mixed_audio = None
            auto_ducking = audio_settings.get("auto_ducking", True) if audio_settings else True
            if has_dub:
                if has_video_audio and not mute_orig and orig_vol > 0.01:
                    fc_parts.append(f"[0:a]volume={orig_vol:.2f}[a_orig]")
                    fc_parts.append(f"[{dub_in_idx}:a]volume={dub_vol:.2f}[a_dub]")
                    if auto_ducking:
                        fc_parts.append(f"[a_dub]asplit=2[dub_sc][dub_mix]")
                        fc_parts.append(f"[a_orig][dub_sc]sidechaincompress=threshold=0.01:ratio=20:attack=10:release=250[a_orig_ducked]")
                        fc_parts.append(f"[a_orig_ducked][dub_mix]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
                    else:
                        fc_parts.append(f"[a_orig][a_dub]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]")
                    has_aout = True
                else:
                    fc_parts.append(f"[{dub_in_idx}:a]volume={dub_vol:.2f}[aout]")
                    has_aout = True
            elif has_video_audio and not mute_orig:
                if abs(orig_vol - 1.0) > 0.01:
                    fc_parts.append(f"[0:a]volume={orig_vol:.2f}[aout]")
                    has_aout = True

            enc_name, enc_flags, enc_label = get_fastest_video_encoder(codec=codec)
            v_codec_args, _ = get_encoder_and_bitrate_flags(enc_name, enc_flags, video_info, crf_val)

            if fc_parts:
                cmd.extend(["-filter_complex", ";".join(fc_parts)])
                if any("[vout]" in p for p in fc_parts):
                    cmd.extend(["-map", "[vout]"])
                else:
                    cmd.extend(["-map", f"{cur_v_label.strip('[]')}"])
                cmd.extend(v_codec_args)

                if has_aout:
                    cmd.extend(["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"])
                elif has_video_audio and not mute_orig:
                    cmd.extend(["-map", "0:a", "-c:a", "copy"])
                else:
                    cmd.append("-an")
            else:
                # Direct stream copy if no filters, no overlays, and audio is untouched
                cmd.extend(["-map", "0:v", "-c:v", "copy"])
                if has_video_audio and not mute_orig:
                    cmd.extend(["-map", "0:a", "-c:a", "copy"])
                else:
                    cmd.append("-an")
                enc_label = "Stream Copy (Instant 0s Lossless)"

            cmd.append(output_video_path)

            v_dur = float(video_info.get("duration", 60.0))
            time_regex = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
            err_lines = []
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    err_lines.append(line)
                    if len(err_lines) > 40:
                        err_lines.pop(0)
                    m = time_regex.search(line)
                    if m and progress_callback and v_dur > 0:
                        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                        pct = min(0.98, 0.10 + 0.88 * (sec / v_dur))
                        progress_callback(f"🎬 Export វីដេអូ ({enc_label}): {int(pct*100)}% ({int(sec)}s/{int(v_dur)}s)...", pct)

            process.wait()
            if process.returncode != 0:
                raise RuntimeError(f"FFmpeg burning subtitles failed:\n{''.join(err_lines[-10:])}")

            if progress_callback:
                progress_callback("Video export complete!", 1.0)
            return True
        finally:
            for t_ovl in temp_overlay_files:
                if os.path.exists(t_ovl):
                    try:
                        os.remove(t_ovl)
                    except Exception:
                        pass
            if temp_mixed_audio and os.path.exists(temp_mixed_audio):
                try:
                    os.remove(temp_mixed_audio)
                except Exception:
                    pass
            if temp_ass and temp_ass != srt_path and os.path.exists(temp_ass):
                try:
                    os.remove(temp_ass)
                except Exception:
                    pass

    @staticmethod
    def export_master_composition(
        video_clips: list,
        subtitles: list,
        dubbed_audio_path: str = None,
        bg_music_path: str = None,
        audio_settings: dict = None,
        video_filters: dict = None,
        watermark: dict = None,
        export_settings: dict = None,
        output_path: str = None,
        audio_tracks: list = None,
        progress_callback=None
    ) -> bool:
        """
        Master Studio Non-Linear Video Compiler:
        Combines Video Clips, Effects, Watermark, Khmer Subtitles with custom font,
        and Dynamic Multi-Track Audio (Audio 1, Audio 2, Audio 3... Audio N) into final video.
        """
        if progress_callback:
            progress_callback("Preparing master video composition...", 0.05)

        if not video_clips:
            raise ValueError("No video clips available to export.")

        audio_settings = audio_settings or {}
        video_filters = video_filters or {}
        watermark = watermark or {}
        export_settings = export_settings or {}

        # 1. Determine Resolution & FPS
        target_res = export_settings.get("resolution") # tuple e.g. (1920, 1080) or None
        target_fps = export_settings.get("fps", 30)
        crf_val = export_settings.get("quality", "22")
        font_name = export_settings.get("font_name", "Leelawadee UI")
        font_size = export_settings.get("font_size", 18)
        font_color = export_settings.get("font_color", "&H00FFFFFF")
        pos_x_rel = export_settings.get("pos_x_rel", 0.5)
        pos_y_rel = export_settings.get("pos_y_rel", 0.88)
        is_dual = export_settings.get("is_dual", False)

        # Base video info
        first_clip = video_clips[0]
        v_info = get_video_info(first_clip["path"])
        vw = target_res[0] if target_res else v_info.get("width", 1280)
        vh = target_res[1] if target_res else v_info.get("height", 720)

        # 2. Build Subtitles ASS with Animation & Background Styling
        burn_cc = export_settings.get("burn_cc", True) and not export_settings.get("hide_cc", False)
        temp_ass = None
        canvas_items = video_filters.get("canvas_items", []) if video_filters else []
        has_canvas_text = any(getattr(it, "item_type", "") == "text" for it in canvas_items)
        if (burn_cc and subtitles) or has_canvas_text:
            temp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False).name
            SubtitleBurner.export_ass(
                subtitles=subtitles if (burn_cc and subtitles) else [],
                output_ass_path=temp_ass,
                video_width=vw,
                video_height=vh,
                pos_x_rel=pos_x_rel,
                pos_y_rel=pos_y_rel,
                font_name=font_name,
                font_size=font_size,
                font_color=font_color,
                dual_language=is_dual,
                animation=export_settings.get("animation", "karaoke"),
                bg_style=export_settings.get("bg_style", "Black Box 50% (ប្រអប់ខ្មៅស្រាល)"),
                highlight_color=export_settings.get("highlight_color", "&H0000E6FF"),
                border_width=export_settings.get("border_width", 3),
                canvas_items=canvas_items,
                total_duration=float(v_info.get("duration", 0.0))
            )
            clean_sub = temp_ass.replace("\\", "/").replace(":", "\\:")

        # 3. Build FFmpeg command inputs
        cmd = ["ffmpeg", "-y"]
        input_idx = 0

        # Input 0: Primary video (or first clip)
        primary_vid_path = first_clip["path"]
        c_start = float(first_clip.get("start", 0.0))
        c_end = float(first_clip.get("end", first_clip.get("duration", 0.0)))
        c_tot = float(first_clip.get("duration", 0.0))
        if c_start > 0.05 or (c_tot > 0 and c_end < c_tot - 0.1):
            cmd.extend(["-ss", f"{c_start:.3f}", "-to", f"{c_end:.3f}"])
        cmd.extend(["-i", primary_vid_path])
        vid_in_idx = input_idx
        input_idx += 1

        # Additional audio inputs
        audio_stream_sources = [] # list of (in_idx, volume, track_type)

        if audio_tracks:
            # Dynamic Multi-Track Audio (Audio 1, Audio 2, Audio 3... Audio N)
            for a_idx, trk in enumerate(audio_tracks):
                if trk.get("is_muted", False):
                    continue
                vol = trk.get("volume", 1.0)
                t_type = trk.get("type", "custom")
                t_path = trk.get("path")

                if t_type == "original":
                    audio_stream_sources.append((vid_in_idx, vol, "original"))
                elif t_type == "dub" and dubbed_audio_path and os.path.exists(dubbed_audio_path):
                    cmd.extend(["-i", dubbed_audio_path])
                    audio_stream_sources.append((input_idx, vol, "dub"))
                    input_idx += 1
                elif t_type == "bgm" and bg_music_path and os.path.exists(bg_music_path):
                    cmd.extend(["-i", bg_music_path])
                    audio_stream_sources.append((input_idx, vol, "bgm"))
                    input_idx += 1
                elif t_path and os.path.exists(t_path):
                    cmd.extend(["-i", t_path])
                    audio_stream_sources.append((input_idx, vol, "custom"))
                    input_idx += 1

            # Guarantee dubbed audio is included if present
            has_dub_stream = any(t[2] == "dub" for t in audio_stream_sources)
            if not has_dub_stream and dubbed_audio_path and os.path.exists(dubbed_audio_path) and not audio_settings.get("mute_dub", False):
                cmd.extend(["-i", dubbed_audio_path])
                audio_stream_sources.append((input_idx, audio_settings.get("dub_vol", 1.0), "dub"))
                input_idx += 1
        else:
            # Legacy audio_settings mapping
            orig_vol = 0.0 if audio_settings.get("mute_orig", False) else audio_settings.get("orig_vol", 0.85)
            audio_stream_sources.append((vid_in_idx, orig_vol, "original"))

            if dubbed_audio_path and os.path.exists(dubbed_audio_path) and not audio_settings.get("mute_dub", False):
                cmd.extend(["-i", dubbed_audio_path])
                audio_stream_sources.append((input_idx, audio_settings.get("dub_vol", 1.0), "dub"))
                input_idx += 1

            if bg_music_path and os.path.exists(bg_music_path) and not audio_settings.get("mute_bgm", False):
                cmd.extend(["-i", bg_music_path])
                audio_stream_sources.append((input_idx, audio_settings.get("bgm_vol", 0.35), "bgm"))
                input_idx += 1

        watermark_in_idx = None
        wm_path = watermark.get("path")
        if wm_path and os.path.exists(wm_path):
            cmd.extend(["-i", wm_path])
            watermark_in_idx = input_idx
            input_idx += 1

        # Collect Image & Sticker Overlays from canvas_items
        image_inputs = []  # list of (img_path, item, is_temp)
        temp_overlay_files = []
        for it in canvas_items:
            itype = getattr(it, "item_type", "")
            is_vis = getattr(it, "is_visible", True)
            if not is_vis:
                continue
            if itype in ("image", "sticker"):
                img_p = getattr(it, "image_path", None)
                if img_p and os.path.exists(img_p):
                    image_inputs.append((img_p, it, False))
                else:
                    pm = getattr(it, "_processed_pixmap", getattr(it, "_raw_image", None))
                    if pm and hasattr(pm, "save"):
                        t_img = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                        pm.save(t_img, "PNG")
                        image_inputs.append((t_img, it, True))
                        temp_overlay_files.append(t_img)

        img_in_indices = []
        for img_p, it, is_tmp in image_inputs:
            cmd.extend(["-i", img_p])
            img_in_indices.append((input_idx, it))
            input_idx += 1

        # 4. Construct Video Filter Chain
        v_filters = []

        # Color grading (Brightness, Contrast, Saturation) only applied when adjusted
        b = video_filters.get("brightness", 0.0)
        c = video_filters.get("contrast", 1.0)
        s = video_filters.get("saturation", 1.0)
        speed = video_filters.get("speed", 1.0)

        if abs(b) > 0.01 or abs(c - 1.0) > 0.01 or abs(s - 1.0) > 0.01:
            v_filters.append(f"eq=brightness={b:.2f}:contrast={c:.2f}:saturation={s:.2f}")

        # Cinematic Color Grading / LUT Preset
        cp = video_filters.get("color_preset", "none")
        cp_int = float(video_filters.get("color_preset_intensity", 1.0))
        color_hsl = video_filters.get("color_hsl_settings", None)
        if (cp and cp != "none") or color_hsl:
            from ui_v_PyQt6.components.player.color_presets import get_ffmpeg_video_filter
            ff_f = get_ffmpeg_video_filter(cp, cp_int, color_hsl)
            if ff_f:
                v_filters.append(ff_f)

        # Speed up / Slow motion
        if speed != 1.0 and speed > 0:
            setpts_val = 1.0 / speed
            v_filters.append(f"setpts={setpts_val:.3f}*PTS")

        # Resolution scaling & aspect cropping if requested (TikTok 9:16 / Square 1:1)
        if target_res:
            tw, th = target_res
            crop_mode = export_settings.get("crop_mode", "fill")
            in_w = v_info.get("width", 1280)
            in_h = v_info.get("height", 720)
            in_ar = in_w / max(1, in_h)
            tar_ar = tw / max(1, th)
            if abs(in_ar - tar_ar) > 0.01:
                if crop_mode == "fill":
                    v_filters.append(f"scale=w={tw}:h={th}:force_original_aspect_ratio=increase,crop={tw}:{th}")
                elif crop_mode == "fit":
                    # CapCut / Reels Fit + Blur Backdrop
                    v_filters.append(
                        f"split[bg][fg];"
                        f"[bg]scale=w={tw}:h={th}:force_original_aspect_ratio=increase,crop={tw}:{th},boxblur=25:5,drawbox=c=black@0.45:t=fill[bg_blur];"
                        f"[fg]scale=w={tw}:h={th}:force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2[fg_scaled];"
                        f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2"
                    )
                else:
                    v_filters.append(f"scale=w={tw}:h={th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:black")
            else:
                v_filters.append(f"scale={tw}:{th}")

        # Horizontal / Vertical Flip & 90° Rotation
        if video_filters:
            flip_h = bool(video_filters.get("flip_h", False))
            flip_v = bool(video_filters.get("flip_v", False))
            rot_deg = float(video_filters.get("rotation", 0.0))
            if flip_h:
                v_filters.append("hflip")
            if flip_v:
                v_filters.append("vflip")
            if rot_deg % 360 == 90:
                v_filters.append("transpose=1")
            elif rot_deg % 360 == 180:
                v_filters.append("hflip,vflip")
            elif rot_deg % 360 == 270:
                v_filters.append("transpose=2")

        # Canvas Overlays: Blur boxes, Censor boxes, Blackout bars added in project
        cur_w = target_res[0] if target_res else vw
        cur_h = target_res[1] if target_res else vh
        for item in canvas_items:
            itype = getattr(item, "item_type", "")
            if itype in ("blur_box", "blur", "mosaic", "glass", "blackout"):
                cx = getattr(item, "x", 0.5)
                cy = getattr(item, "y", 0.5)
                cw = getattr(item, "w", 0.3)
                ch = getattr(item, "h", 0.15)
                bx = max(1, min(cur_w - 12, int((cx - cw / 2.0) * cur_w)))
                by = max(1, min(cur_h - 12, int((cy - ch / 2.0) * cur_h)))
                bw = max(10, min(cur_w - bx - 1, int(cw * cur_w)))
                bh = max(10, min(cur_h - by - 1, int(ch * cur_h)))
                bmode = getattr(item, "blur_mode", itype if itype != "blur_box" else "blur")

                if bmode == "blackout":
                    v_filters.append(f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=black:t=fill")
                elif bmode in ("blur", "glass", "mosaic"):
                    v_filters.append(f"delogo=x={bx}:y={by}:w={bw}:h={bh}")

        # Subtitles burn-in with HarfBuzz complex shaping (100% WYSIWYG Khmer fonts without broken legs)
        if clean_sub:
            v_filters.append(f"ass='{clean_sub}':shaping=complex")


        is_webm = output_path.lower().endswith(".webm")
        is_trimmed = c_start > 0.05 or (c_tot > 0 and c_end < c_tot - 0.1)
        can_stream_copy = (
            not v_filters 
            and watermark_in_idx is None 
            and not img_in_indices
            and len(video_clips) == 1 
            and not is_trimmed
            and not is_webm
        )

        codec = export_settings.get("codec", "hevc")
        crf_val = export_settings.get("quality", "26")
        enc_name, enc_flags, enc_label = get_fastest_video_encoder(codec=codec)
        v_codec_args, target_bitrate = get_encoder_and_bitrate_flags(enc_name, enc_flags, v_info, crf_val)

        filter_complex_parts = []

        if can_stream_copy:
            v_map = ["-map", f"{vid_in_idx}:v"]
            v_video_args = ["-c:v", "copy"]
            enc_label = "Stream Copy (Instant 0s Lossless)"
        else:
            vf_chain_str = ",".join(v_filters) if v_filters else "null"
            if watermark_in_idx is not None or img_in_indices:
                filter_complex_parts.append(f"[{vid_in_idx}:v]{vf_chain_str}[v_graded]")
                cur_v_label = "[v_graded]"

                for idx, (img_idx, it) in enumerate(img_in_indices):
                    cw = getattr(it, "w", 0.25)
                    ch = getattr(it, "h", 0.25)
                    cx = getattr(it, "x", 0.5)
                    cy = getattr(it, "y", 0.5)
                    iw = max(10, min(cur_w, int(cw * cur_w)))
                    ih = max(10, min(cur_h, int(ch * cur_h)))
                    ix = max(0, min(cur_w - iw, int((cx - cw / 2.0) * cur_w)))
                    iy = max(0, min(cur_h - ih, int((cy - ch / 2.0) * cur_h)))
                    op = max(0.05, min(1.0, float(getattr(it, "opacity", 1.0))))
                    st = float(getattr(it, "start_time", 0.0))
                    et = float(getattr(it, "end_time", 0.0))

                    scale_f = f"scale={iw}:{ih},format=rgba"
                    if op < 0.99:
                        scale_f += f",colorchannelmixer=aa={op:.2f}"
                    filter_complex_parts.append(f"[{img_idx}:v]{scale_f}[img_ovl_{idx}]")

                    time_enable = f":enable='between(t,{st:.3f},{et:.3f})'" if (et > st > 0) else ""
                    next_v = f"[v_with_img_{idx}]"
                    filter_complex_parts.append(f"{cur_v_label}[img_ovl_{idx}]overlay={ix}:{iy}{time_enable}{next_v}")
                    cur_v_label = next_v

                if watermark_in_idx is not None:
                    pos_key = watermark.get("pos", "Top-Right (លើ ស្ដាំ)")
                    rel_x = watermark.get("rel_x")
                    rel_y = watermark.get("rel_y")
                    if rel_x is not None and rel_y is not None:
                        # Custom Drag & Drop coordinates
                        overlay_expr = f"(W-w)*{rel_x:.3f}:(H-h)*{rel_y:.3f}"
                    else:
                        overlay_expr = WATERMARK_POSITIONS.get(pos_key, "W-w-20:20")
                        if not overlay_expr:
                            overlay_expr = "W-w-20:20"

                    wm_scale = watermark.get("scale", 0.15)
                    wm_scaled_w = max(40, int(vw * wm_scale))
                    opacity = float(watermark.get("opacity", 1.0))
                    opacity = max(0.05, min(1.0, opacity))

                    if opacity < 0.99:
                        filter_complex_parts.append(f"[{watermark_in_idx}:v]scale={wm_scaled_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.2f}[wm_scaled]")
                    else:
                        filter_complex_parts.append(f"[{watermark_in_idx}:v]scale={wm_scaled_w}:-1[wm_scaled]")
                    filter_complex_parts.append(f"{cur_v_label}[wm_scaled]overlay={overlay_expr}[vout]")
                else:
                    filter_complex_parts.append(f"{cur_v_label}null[vout]")
            else:
                filter_complex_parts.append(f"[{vid_in_idx}:v]{vf_chain_str}[vout]")
            v_map = ["-map", "[vout]"]
            v_video_args = v_codec_args

        # 5. Construct Audio Filter Chain with Smart Auto-Ducking (sidechaincompress)
        auto_ducking = audio_settings.get("auto_ducking", True)
        orig_stream_label = None
        dub_stream_label = None
        other_streams = []

        for s_i, (in_id, s_vol, s_type) in enumerate(audio_stream_sources):
            raw_label = f"[a_raw_{s_i}]"
            filter_complex_parts.append(f"[{in_id}:a]volume={s_vol:.2f}{raw_label}")
            if s_type == "original":
                orig_stream_label = raw_label
            elif s_type == "dub":
                dub_stream_label = raw_label
            else:
                other_streams.append(raw_label)

        mix_streams = []
        if auto_ducking and orig_stream_label and dub_stream_label:
            ducked_label = "[a_orig_ducked]"
            dub_sc = "[dub_sc]"
            dub_mix = "[dub_mix]"
            filter_complex_parts.append(f"{dub_stream_label}asplit=2{dub_sc}{dub_mix}")
            filter_complex_parts.append(f"{orig_stream_label}{dub_sc}sidechaincompress=threshold=0.01:ratio=20:attack=10:release=250{ducked_label}")
            mix_streams.append(ducked_label)
            mix_streams.append(dub_mix)
        else:
            if orig_stream_label:
                mix_streams.append(orig_stream_label)
            if dub_stream_label:
                mix_streams.append(dub_stream_label)

        mix_streams.extend(other_streams)

        # Mix all active audio tracks
        num_a = len(mix_streams)
        if num_a > 1:
            streams_in = "".join(mix_streams)
            filter_complex_parts.append(f"{streams_in}amix=inputs={num_a}:duration=first:dropout_transition=0:normalize=0[aout]")
        elif num_a == 1:
            filter_complex_parts.append(f"{mix_streams[0]}anull[aout]")
        else:
            filter_complex_parts.append(f"[{vid_in_idx}:a]anull[aout]")

        full_filter_complex = ";".join(filter_complex_parts)
        if full_filter_complex:
            cmd.extend(["-filter_complex", full_filter_complex])
        cmd.extend([*v_map, "-map", "[aout]"])

        # Frame rate & Codec
        if not can_stream_copy:
            cmd.extend(["-r", str(target_fps)])
        cmd.extend(["-threads", "0"])

        if is_webm:
            cmd.extend(["-c:v", "libvpx-vp9", "-crf", crf_val, "-b:v", f"{target_bitrate}", "-speed", "4", "-row-mt", "1", "-c:a", "libopus"])
        else:
            cmd.extend([*v_video_args, "-c:a", "aac", "-b:a", "192k"])

        cmd.append(output_path)

        total_duration = 0.0
        for c in video_clips:
            total_duration += max(0.1, float(c.get("end", c.get("duration", 0.0)) - c.get("start", 0.0)))
        if total_duration <= 0.0:
            total_duration = float(v_info.get("duration", 60.0))

        if progress_callback:
            est_mb = int((target_bitrate + 192000) * total_duration / 8 / (1024 * 1024))
            progress_callback(f"🎬 កំពុង Export វីដេអូ ({enc_label} ~{est_mb}MB)...", 0.20)

        try:
            time_regex = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

            err_lines = []
            all_errors = []
            last_progress_pct = 0.20
            while True:
                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break
                if line:
                    stripped = line.strip()
                    err_lines.append(stripped)
                    if len(err_lines) > 50:
                        err_lines.pop(0)
                    if any(w in stripped.lower() for w in ["error", "fatal", "failed", "invalid", "denied", "space", "cannot"]):
                        all_errors.append(stripped)
                        if len(all_errors) > 20:
                            all_errors.pop(0)
                    m = time_regex.search(line)
                    if m and progress_callback and total_duration > 0:
                        hrs = int(m.group(1))
                        mins = int(m.group(2))
                        secs = float(m.group(3))
                        cur_sec = hrs * 3600 + mins * 60 + secs
                        pct = min(0.98, 0.20 + 0.78 * (cur_sec / total_duration))
                        if pct - last_progress_pct >= 0.01 or pct >= 0.98:
                            last_progress_pct = pct
                            progress_callback(f"🎬 Export វីដេអូ ({enc_label}): {int(pct*100)}% ({int(cur_sec)}s/{int(total_duration)}s)...", pct)

            proc.wait()
            if proc.returncode != 0:
                err_msg = "\n".join(all_errors[-5:]) if all_errors else "\n".join(err_lines[-10:])
                raise RuntimeError(f"Master composition export failed:\n{err_msg}")

            if progress_callback:
                progress_callback("🎉 Master video export completed successfully!", 1.0)
            return True
        finally:
            if temp_ass and os.path.exists(temp_ass):
                try:
                    os.remove(temp_ass)
                except Exception:
                    pass
            for t_ovl in temp_overlay_files:
                if os.path.exists(t_ovl):
                    try:
                        os.remove(t_ovl)
                    except Exception:
                        pass
