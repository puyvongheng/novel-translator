"""
Unified Khmer Text-to-Speech Engine Manager
Orchestrates multi-model TTS synthesis:
1. Microsoft Edge-TTS (EdgeTTSModel) - Natural Khmer Neural voices
2. Google Gemini 2.0 (GeminiTTSModel) - AI Native Audio Speech (Piseth, Sreymom, Borey)
3. Google Cloud TTS (GoogleCloudTTSModel) - km-KH-Standard-A/B voices
"""

import os
import subprocess
import tempfile
from pydub import AudioSegment

from services.speech.edge_tts_model import EdgeTTSModel, EDGE_KHMER_VOICES
from services.speech.gemini_tts_model import GeminiTTSModel
from services.speech.google_cloud_tts_model import GoogleCloudTTSModel

# Comprehensive voice dictionary across all models
KHMER_VOICES = {
    "Piseth (Male / ប្រុស)": "km-KH-PisethNeural",
    "Sreymom (Female / ស្រី)": "km-KH-SreymomNeural",
    "Gemini Voice: Piseth (ប្រុស)": "Puck",
    "Gemini Voice: Sreymom (ស្រី)": "Aoede",
    "Gemini Voice: Borey (Action)": "Fenrir",
    "Google Cloud: km-KH-Standard-A (ស្រី)": "km-KH-Standard-A",
    "Google Cloud: km-KH-Standard-B (ប្រុស)": "km-KH-Standard-B"
}

_edge_engine = EdgeTTSModel()
_gemini_engine = GeminiTTSModel()
_gcloud_engine = GoogleCloudTTSModel()

def generate_speech_file(
    text: str,
    voice_name_or_output: str = None,
    output_path: str = None,
    rate: str = "+0%",
    api_key: str = None,
    voice_name: str = None,
    pitch: str = "+0Hz",
    volume: str = "+0%",
    enhance: bool = True
) -> bool:
    """
    Unified multi-model speech synthesis dispatcher.
    Supports flexible arguments:
    - generate_speech_file(text, output_path)
    - generate_speech_file(text, voice_name, output_path)
    - generate_speech_file(text, output_path, voice_name="...")
    """
    if not text or not text.strip():
        return False

    # Flexible argument resolution
    if voice_name:
        chosen_voice = voice_name
        target_output = output_path or voice_name_or_output
    elif output_path:
        chosen_voice = voice_name_or_output or "km-KH-PisethNeural"
        target_output = output_path
    else:
        chosen_voice = "km-KH-PisethNeural"
        target_output = voice_name_or_output

    if not target_output:
        return False

    v_lower = str(chosen_voice).lower()

    # 1. Google Gemini AI Voice Model
    if "gemini" in v_lower:
        ok = _gemini_engine.generate_speech(text, target_output, voice_name=chosen_voice, api_key=api_key)
        if ok and os.path.exists(target_output) and os.path.getsize(target_output) > 0:
            return True
        print("Gemini TTS failed, falling back to Edge-TTS Neural...")

    # 2. Google Cloud Standard Voices Model
    elif "google cloud" in v_lower or "standard-" in v_lower:
        ok = _gcloud_engine.generate_speech(text, target_output, voice_name=chosen_voice, rate=rate, api_key=api_key)
        if ok and os.path.exists(target_output) and os.path.getsize(target_output) > 0:
            return True
        print("Google Cloud TTS failed, falling back to Edge-TTS Neural...")

    # 3. Microsoft Edge-TTS Neural (Default Primary / Fallback)
    return _edge_engine.generate_speech(
        text,
        target_output,
        voice_name=chosen_voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
        enhance=enhance
    )

def generate_khmer_dubbing(
    subtitles: list,
    total_duration_sec: float,
    voice_name: str = "km-KH-PisethNeural",
    output_dub_audio_path: str = "dubbed_khmer.wav",
    progress_callback=None
) -> str:
    """
    Takes subtitle segments and generates a full-length dubbed audio track 
    where each Khmer line is synthesized and placed precisely at its timestamp.
    """
    if progress_callback:
        progress_callback(f"🤖 [AI Voice] កំពុងរៀបចំសំឡេងនិយាយភាសាខ្មែរដោយ AI ({voice_name})...", 0.05)

    # Base silent track matching video duration
    total_ms = int(total_duration_sec * 1000) + 2000
    base_track = AudioSegment.silent(duration=total_ms)

    temp_files = []
    total_subs = len(subtitles)
    last_end_ms = 0

    try:
        for idx, sub in enumerate(subtitles):
            text = sub.get("translated", "") or sub.get("khmer_text", "")
            text = text.strip()
            if not text:
                continue

            start_ms = int(sub["start"] * 1000)
            end_ms = int(sub["end"] * 1000)
            target_duration_ms = max(500, end_ms - start_ms)

            # Generate temp mp3 for this sentence
            temp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            temp_files.append(temp_mp3)

            rate = sub.get("rate", "+0%")
            line_v = sub.get("voice_name")
            if not line_v:
                line_v = "km-KH-SreymomNeural" if sub.get("gender") == "female" else voice_name
            ok = generate_speech_file(text, line_v, temp_mp3, rate=rate)
            if not ok or not os.path.exists(temp_mp3):
                continue

            # Load segment audio
            try:
                line_audio = AudioSegment.from_file(temp_mp3)
                speech_len = len(line_audio)
                if speech_len > target_duration_ms * 1.06:
                    speed_factor = min(1.18, speech_len / target_duration_ms)
                    if speed_factor >= 1.05:
                        line_audio = line_audio.speedup(playback_speed=speed_factor)
                        speech_len = len(line_audio)

                # Dialogue starts strictly at subtitle start timestamp (e.g. 00:20)
                actual_start_ms = max(start_ms, last_end_ms + 20)

                # Overlay at timestamp
                base_track = base_track.overlay(line_audio, position=actual_start_ms)
                last_end_ms = actual_start_ms + speech_len
            except Exception as ex:
                print(f"Overlay line error: {ex}")

            if progress_callback:
                pct = 0.05 + (0.85 * (idx + 1) / total_subs)
                progress_callback(f"🎙️ [AI Voice] បង្កើតសំឡេងដោយ AI ({voice_name}) [{idx+1}/{total_subs}]: {text[:25]}...", pct)

        if progress_callback:
            progress_callback("Exporting final dubbed audio...", 0.95)

        out_ext = os.path.splitext(output_dub_audio_path)[1].lower()
        if out_ext == ".m4a":
            base_track.export(output_dub_audio_path, format="ipod", codec="aac", bitrate="160k")
        elif out_ext == ".mp3":
            base_track.export(output_dub_audio_path, format="mp3", bitrate="192k")
        else:
            base_track.export(output_dub_audio_path, format="wav")
        return output_dub_audio_path


    finally:
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

def merge_video_with_dubbing(
    video_path: str,
    dubbed_audio_path: str,
    output_video_path: str,
    original_volume: float = 0.15,
    dub_volume: float = 1.0,
    progress_callback=None
) -> bool:
    """
    Merges original video with dubbed Khmer audio, keeping background music at reduced volume.
    """
    if progress_callback:
        progress_callback("កំពុងបញ្ចូលសំឡេងខ្មែរ (Mixing Dub Audio with Video)...", 0.2)

    filter_complex = f"[0:a]volume={original_volume}[bg];[1:a]volume={dub_volume}[dub];[bg][dub]amix=inputs=2:duration=first:dropout_transition=2[aout]"

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", dubbed_audio_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        output_video_path
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        cmd_fallback = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", dubbed_audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_video_path
        ]
        res = subprocess.run(cmd_fallback, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if progress_callback:
        progress_callback("Dubbed movie export complete!", 1.0)

    return res.returncode == 0

# Convenient aliases
generate_voice_file = generate_speech_file
generate_voice_file_sync = generate_speech_file
