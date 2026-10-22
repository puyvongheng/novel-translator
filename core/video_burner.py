import os
import re
import subprocess
import tempfile
from core.utils import format_timestamp, format_ass_timestamp, get_video_info
from config import WATERMARK_POSITIONS

_DETECTED_ENCODER = None

def get_fastest_video_encoder():
    """
    Auto-detects the fastest video encoder available on the system:
    1. NVIDIA NVENC (h264_nvenc) - High Quality GPU hardware acceleration (preset p5)
    2. Intel QSV (h264_qsv) - Intel Quick Sync hardware
    3. CPU libx264 with high quality multithreading
    """
    global _DETECTED_ENCODER
    if _DETECTED_ENCODER is not None:
        return _DETECTED_ENCODER

    # Test NVENC
    try:
        cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'h264_nvenc', '-f', 'null', '-']
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            _DETECTED_ENCODER = ("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p5"], "NVIDIA GPU NVENC (High Quality)")
            return _DETECTED_ENCODER
    except Exception:
        pass

    # Test QSV
    try:
        cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=640x360:rate=30', '-c:v', 'h264_qsv', '-f', 'null', '-']
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0:
            _DETECTED_ENCODER = ("h264_qsv", ["-c:v", "h264_qsv", "-preset", "medium"], "Intel QuickSync QSV")
            return _DETECTED_ENCODER
    except Exception:
        pass

    # CPU multithreaded fallback
    _DETECTED_ENCODER = ("libx264", ["-c:v", "libx264", "-preset", "medium"], "CPU Multi-threaded x264 (HQ)")
    return _DETECTED_ENCODER

def get_encoder_and_bitrate_flags(enc_name: str, enc_flags: list, v_info: dict, crf_val: str = "22") -> tuple:
    """
    Computes optimal video encoding flags ensuring:
    1. YUV420P color space is enforced (prevents file bloating from 4:4:4 GBRP RGB).
    2. Bitrate preserves source video quality without artificial 4Mbps degradation.
    3. Hardware acceleration (NVENC / QSV) is fully utilized with proper buffer sizes.
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
        elif crf_int >= 26:
            target_br = int(target_br * 0.75)
    except Exception:
        pass

    max_br = int(target_br * 1.5)
    buf_size = int(target_br * 2.0)

    if enc_name == "h264_nvenc":
        flags = [
            "-c:v", "h264_nvenc",
            "-preset", "p5",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{target_br}",
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}",
            "-cq", str(crf_val)
        ]
    elif enc_name == "h264_qsv":
        flags = [
            "-c:v", "h264_qsv",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-b:v", f"{target_br}",
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}",
            "-global_quality", str(crf_val)
        ]
    else:
        flags = [
            "-c:v", "libx264",
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-crf", str(crf_val),
            "-maxrate", f"{max_br}",
            "-bufsize", f"{buf_size}"
        ]

    return flags, target_br

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
        border_width: int = 3
    ):
        """
        Generates an ASS subtitle file with exact screen positioning (\\pos(X, Y)),
        custom font, background box, and advanced animations (Karaoke word-by-word, Popup, Fade, Slide Up).
        """
        from config import CC_BG_STYLES, CC_HIGHLIGHT_COLORS
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

        # Safe font fallback chain
        clean_font = font_name.strip() if font_name else "Leelawadee UI"

        header = f"""[Script Info]
Title: Khmer Dubbed Movie
ScriptType: v4.00+
WrapStyle: 0
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{clean_font},{scaled_font},{font_color},{hi_ass},{outline_color},{back_color},-1,0,0,0,100,100,0,0,{border_style},{outline_w},1,5,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        clean_anim = (animation or "").lower()

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write(header)
            for sub in subtitles:
                km = sub.get("translated", "").strip()
                orig = sub.get("original", "").strip()
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
                    # Native ASS Karaoke tag: {\k<cs>}Word
                    if " " in text:
                        tokens = text.split(" ")
                    else:
                        step = 4
                        tokens = [text[i:i+step] for i in range(0, len(text), step)] if len(text) > 4 else [text]
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
        progress_callback=None
    ) -> bool:
        """Simple subtitle burn-in matching interactive preview with animations and optional Khmer audio dubbing"""
        if progress_callback:
            progress_callback("Rendering video with Khmer subtitles & audio...", 0.1)

        if not video_info:
            video_info = get_video_info(video_path)
        vw = video_info.get("width", 1280)
        vh = video_info.get("height", 720)

        temp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False).name
        try:
            should_burn = burn_cc and (subtitles or (srt_path and os.path.exists(srt_path)))
            if should_burn:
                if subtitles:
                    SubtitleBurner.export_ass(
                        subtitles=subtitles,
                        output_ass_path=temp_ass,
                        video_width=vw,
                        video_height=vh,
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
                        border_width=border_width
                    )
                elif srt_path and os.path.exists(srt_path):
                    temp_ass = srt_path

                clean_sub = temp_ass.replace("\\", "/").replace(":", "\\:")
                vf_args = ["-vf", f"subtitles='{clean_sub}'"]
            else:
                vf_args = []
            
            has_dub = dubbed_audio_path and os.path.exists(dubbed_audio_path) and os.path.getsize(dubbed_audio_path) > 1000
            has_video_audio = video_info.get("has_audio", True)
            mute_orig = audio_settings.get("mute_orig", False) if audio_settings else False
            orig_vol = audio_settings.get("orig_vol", 0.85) if audio_settings else 0.85
            dub_vol = audio_settings.get("dub_vol", 1.2) if audio_settings else 1.2
            auto_duck = audio_settings.get("auto_ducking", True) if audio_settings else True

            if has_dub:
                if has_video_audio and not mute_orig and orig_vol > 0.01:
                    if auto_duck:
                        fc = (
                            f"[0:a]volume={orig_vol:.2f}[a_orig];"
                            f"[1:a]volume={dub_vol:.2f}[a_dub_pre];"
                            f"[a_dub_pre]asplit=2[dub_sc][dub_mix];"
                            f"[a_orig][dub_sc]sidechaincompress=threshold=0.04:ratio=12:attack=20:release=400[a_ducked];"
                            f"[a_ducked][dub_mix]amix=inputs=2:duration=first:dropout_transition=0:weights=1 2.5[aout]"
                        )
                    else:
                        fc = (
                            f"[0:a]volume={orig_vol:.2f}[a_orig];"
                            f"[1:a]volume={dub_vol:.2f}[a_dub];"
                            f"[a_orig][a_dub]amix=inputs=2:duration=first:dropout_transition=0:weights=1 2.0[aout]"
                        )
                else:
                    fc = f"[1:a]volume={dub_vol:.2f}[aout]"

                enc_name, enc_flags, enc_label = get_fastest_video_encoder()
                v_codec_args, _ = get_encoder_and_bitrate_flags(enc_name, enc_flags, video_info, "22")

                cmd = [
                    "ffmpeg", "-y",
                    "-threads", "0",
                    "-i", video_path,
                    "-i", dubbed_audio_path,
                    *vf_args,
                    "-filter_complex", fc,
                    "-map", "0:v",
                    "-map", "[aout]",
                    *v_codec_args,
                    "-c:a", "aac",
                    "-b:a", "192k",
                    output_video_path
                ]
            else:
                enc_name, enc_flags, enc_label = get_fastest_video_encoder()
                v_codec_args, _ = get_encoder_and_bitrate_flags(enc_name, enc_flags, video_info, "22")

                a_args = ["-c:a", "copy"] if has_video_audio and not mute_orig else []
                cmd = [
                    "ffmpeg", "-y",
                    "-threads", "0",
                    "-i", video_path,
                    *vf_args,
                    *a_args,
                    *v_codec_args,
                    output_video_path
                ]

            v_dur = float(get_video_info(video_path).get("duration", 60.0))
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
            if temp_ass != srt_path and os.path.exists(temp_ass):
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
        temp_ass = tempfile.NamedTemporaryFile(suffix=".ass", delete=False).name
        SubtitleBurner.export_ass(
            subtitles=subtitles,
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
            border_width=export_settings.get("border_width", 3)
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

        # 4. Construct Video Filter Chain
        v_filters = []

        # Color grading (Brightness, Contrast, Saturation)
        b = video_filters.get("brightness", 0.0)
        c = video_filters.get("contrast", 1.0)
        s = video_filters.get("saturation", 1.0)
        speed = video_filters.get("speed", 1.0)

        v_filters.append(f"eq=brightness={b:.2f}:contrast={c:.2f}:saturation={s:.2f}")

        # Speed up / Slow motion
        if speed != 1.0 and speed > 0:
            setpts_val = 1.0 / speed
            v_filters.append(f"setpts={setpts_val:.3f}*PTS")

        # Resolution scaling if requested
        if target_res:
            v_filters.append(f"scale={target_res[0]}:{target_res[1]}")

        # Subtitles burn-in (Can be disabled to hide CC on exported video)
        burn_cc = export_settings.get("burn_cc", True)
        if burn_cc and subtitles and not export_settings.get("hide_cc", False):
            v_filters.append(f"subtitles='{clean_sub}'")

        # Watermark overlay
        vf_chain_str = ",".join(v_filters) if v_filters else "null"
        filter_complex_parts = []

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

            filter_complex_parts.append(f"[{vid_in_idx}:v]{vf_chain_str}[v_graded]")
            if opacity < 0.99:
                filter_complex_parts.append(f"[{watermark_in_idx}:v]scale={wm_scaled_w}:-1,format=rgba,colorchannelmixer=aa={opacity:.2f}[wm_scaled]")
            else:
                filter_complex_parts.append(f"[{watermark_in_idx}:v]scale={wm_scaled_w}:-1[wm_scaled]")
            filter_complex_parts.append(f"[v_graded][wm_scaled]overlay={overlay_expr}[vout]")
        else:
            filter_complex_parts.append(f"[{vid_in_idx}:v]{vf_chain_str}[vout]")

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
            filter_complex_parts.append(f"{orig_stream_label}{dub_sc}sidechaincompress=threshold=0.04:ratio=12:attack=20:release=400{ducked_label}")
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
            # Higher weight on dub mix so Khmer speech is clearly audible
            weights_str = " ".join(["2.5" if s == "[dub_mix]" or (not auto_ducking and s == dub_stream_label) else "1" for s in mix_streams])
            filter_complex_parts.append(f"{streams_in}amix=inputs={num_a}:duration=first:dropout_transition=0:weights={weights_str}[aout]")
        elif num_a == 1:
            filter_complex_parts.append(f"{mix_streams[0]}anull[aout]")
        else:
            filter_complex_parts.append(f"[{vid_in_idx}:a]anull[aout]")

        full_filter_complex = ";".join(filter_complex_parts)
        cmd.extend(["-filter_complex", full_filter_complex])
        cmd.extend(["-map", "[vout]", "-map", "[aout]"])

        # Frame rate & Codec
        cmd.extend(["-r", str(target_fps), "-threads", "0"])
        enc_name, enc_flags, enc_label = get_fastest_video_encoder()
        v_codec_args, target_bitrate = get_encoder_and_bitrate_flags(enc_name, enc_flags, v_info, crf_val)

        is_webm = output_path.lower().endswith(".webm")
        if is_webm:
            cmd.extend(["-c:v", "libvpx-vp9", "-crf", crf_val, "-b:v", f"{target_bitrate}", "-speed", "4", "-row-mt", "1", "-c:a", "libopus"])
        else:
            cmd.extend([*v_codec_args, "-c:a", "aac", "-b:a", "192k"])

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
            if os.path.exists(temp_ass):
                try:
                    os.remove(temp_ass)
                except Exception:
                    pass
