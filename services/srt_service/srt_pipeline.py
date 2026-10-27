"""
End-to-End Subtitle Pipeline Orchestrator
One-call capture: Video/Audio -> ASR Speech Recognition -> Fixed Timestamps -> Saved .srt file.
"""

import os
from services.srt_service.audio_extractor import AudioExtractor
from services.srt_service.whisper_transcriber import WhisperTranscriber
from services.srt_service.funasr_transcriber import FunASRTranscriber
from services.srt_service.srt_formatter import SrtFormatter


def capture_video_subtitles(
    video_path: str,
    engine: str = "whisper",
    model_size: str = "base",
    source_lang: str = "auto",
    output_srt: str = None,
    progress_callback=None
) -> tuple[list[dict], str, str]:
    """
    High-level end-to-end subtitle capture workflow:
    1. Checks/extracts high-quality MP3 audio next to video
    2. Runs chosen ASR engine (Faster-Whisper with auto-CPU fallback, or FunASR for Chinese)
    3. Normalizes subtitle items & eliminates overlapping timestamps
    4. Automatically writes clean .srt file next to video
    Returns:
        (subtitles: list[dict], srt_path: str, audio_path: str)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    v_folder = os.path.dirname(os.path.abspath(video_path))
    base_name = os.path.splitext(os.path.basename(video_path))[0]

    # Audio & SRT target paths in video folder
    audio_mp3 = os.path.join(v_folder, f"{base_name}_audio.mp3")
    legacy_mp3 = os.path.join(v_folder, f"movie_orig_audio_{abs(hash(video_path))}.mp3")
    if not os.path.exists(audio_mp3) and os.path.exists(legacy_mp3) and os.path.getsize(legacy_mp3) > 1000:
        audio_mp3 = legacy_mp3

    srt_path = output_srt or os.path.join(v_folder, f"{base_name}.srt")

    # Step 1: Ensure audio file is ready
    if not os.path.exists(audio_mp3) or os.path.getsize(audio_mp3) < 1000:
        if progress_callback:
            progress_callback("Extracting audio stream for playback and recognition...", 0.05)
        AudioExtractor.extract_preview_mp3(video_path, audio_mp3)

    # Step 2: Speech Recognition
    is_funasr = (engine.lower() == "funasr")
    if is_funasr:
        raw_items = FunASRTranscriber.transcribe(
            media_path=audio_mp3 if os.path.exists(audio_mp3) else video_path,
            progress_callback=progress_callback
        )
    else:
        transcriber = WhisperTranscriber(model_size=model_size, device="auto")
        raw_items = transcriber.transcribe(
            media_path=audio_mp3 if os.path.exists(audio_mp3) else video_path,
            source_lang=source_lang,
            progress_callback=progress_callback
        )

    if not raw_items:
        return [], "", audio_mp3

    # Step 3: Format, clean and fix overlaps
    if progress_callback:
        progress_callback("Aligning timestamps and fixing subtitle overlaps...", 0.96)

    fixed_subtitles, _ = SrtFormatter.clean_and_fix_overlaps(raw_items)

    # Step 4: Save SRT file
    saved_srt = SrtFormatter.save_to_file(fixed_subtitles, srt_path)

    if progress_callback:
        progress_callback(f"Saved {len(fixed_subtitles)} subtitle items to {os.path.basename(saved_srt)}", 1.0)

    return fixed_subtitles, saved_srt, audio_mp3
