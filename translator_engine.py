import json
import os
import subprocess
import tempfile
import time
from datetime import timedelta
from deep_translator import GoogleTranslator

# Suppress Hugging Face unauthenticated warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def get_video_info(video_path: str) -> dict:
    """Retrieve video duration, width, height, fps using ffprobe"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", video_path
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            duration = float(data.get("format", {}).get("duration", 0))
            width = 1280
            height = 720
            fps = 30.0
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    width = int(s.get("width", 1280))
                    height = int(s.get("height", 720))
                    r_frame_rate = s.get("r_frame_rate", "30/1")
                    if "/" in r_frame_rate:
                        n, d = r_frame_rate.split("/")
                        fps = float(n) / float(d) if float(d) > 0 else 30.0
                    break
            return {
                "duration": duration,
                "width": width,
                "height": height,
                "fps": fps
            }
    except Exception as e:
        print(f"ffprobe error: {e}")
    return {"duration": 0.0, "width": 1280, "height": 720, "fps": 30.0}

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

def extract_audio(video_path: str, output_wav: str) -> bool:
    """Extract 16kHz mono audio from video file using FFmpeg"""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        output_wav
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return res.returncode == 0

def transcribe_and_translate(
    video_path: str,
    source_lang: str = "zh",
    target_lang: str = "km",
    model_size: str = "base",
    device: str = "auto",
    progress_callback=None
):
    """
    Transcribes video audio and translates to target language (Khmer).
    Returns list of subtitle dicts:
    [{'id': 1, 'start': 0.0, 'end': 2.5, 'original': '...', 'translated': '...'}]
    """
    if progress_callback:
        progress_callback("Extracting audio from video...", 0.05)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
        wav_path = tmp_audio.name

    try:
        ok = extract_audio(video_path, wav_path)
        if not ok:
            raise RuntimeError("Failed to extract audio from video with FFmpeg.")

        if progress_callback:
            progress_callback(f"Loading speech recognition model ({model_size})...", 0.15)

        from faster_whisper import WhisperModel
        
        try:
            model = WhisperModel(model_size, device=device if device != "auto" else "cpu", compute_type="int8")
        except Exception:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")

        if progress_callback:
            progress_callback("Detecting speech and recognizing Chinese/original voice...", 0.3)

        segments, info = model.transcribe(
            wav_path,
            language=source_lang if source_lang != "auto" else None,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        segments_list = list(segments)
        total_segs = len(segments_list)
        if total_segs == 0:
            if progress_callback:
                progress_callback("No speech detected.", 1.0)
            return []

        if progress_callback:
            progress_callback(f"Speech detected ({total_segs} lines). Translating to Khmer...", 0.5)

        translator = GoogleTranslator(source=source_lang if source_lang != "auto" else "auto", target=target_lang)
        
        subtitles = []
        for idx, seg in enumerate(segments_list):
            orig_text = seg.text.strip()
            if not orig_text:
                continue

            try:
                km_text = translator.translate(orig_text)
                time.sleep(0.04)  # slight polite delay
            except Exception:
                km_text = orig_text  # fallback

            item = {
                "id": idx + 1,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
                "original": orig_text,
                "translated": km_text
            }
            subtitles.append(item)

            if progress_callback:
                pct = 0.5 + (0.45 * (idx + 1) / total_segs)
                progress_callback(f"Translating line {idx+1}/{total_segs}: {km_text[:30]}...", pct)

        if progress_callback:
            progress_callback("Translation finished successfully!", 1.0)

        return subtitles

    finally:
        if os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass

def export_to_srt(subtitles: list, output_srt_path: str, use_translated: bool = True, dual_language: bool = False):
    """Exports subtitles to an .SRT file (UTF-8)"""
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

def burn_subtitles_to_video(
    video_path: str,
    srt_path: str,
    output_video_path: str,
    font_size: int = 22,
    font_color: str = "&H00FFFFFF",
    outline_color: str = "&H00000000",
    progress_callback=None
):
    """
    Hardcodes/Burns modern Khmer subtitles directly into the MP4 video using FFmpeg.
    """
    if progress_callback:
        progress_callback("Rendering video with Khmer subtitles (FFmpeg burn-in)...", 0.1)

    clean_srt = srt_path.replace("\\", "/").replace(":", "\\:")
    style = f"Fontsize={font_size},PrimaryColour={font_color},OutlineColour={outline_color},BorderStyle=1,Outline=2,Shadow=1,MarginV=30,Alignment=2"
    filter_arg = f"subtitles='{clean_srt}':force_style='{style}'"

    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", filter_arg,
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        output_video_path
    ]

    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg burning subtitles failed:\n{stderr[-400:] if stderr else ''}")

    if progress_callback:
        progress_callback("Video export complete!", 1.0)
    return True
