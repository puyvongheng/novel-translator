import asyncio
import os
import subprocess
import tempfile
import edge_tts
from pydub import AudioSegment

# Available high quality Khmer Neural Voices
KHMER_VOICES = {
    "Piseth (Male / ប្រុស)": "km-KH-PisethNeural",
    "Sreymom (Female / ស្រី)": "km-KH-SreymomNeural"
}

def generate_speech_file(text: str, voice_name: str, output_path: str, rate: str = "+0%") -> bool:
    """Generate audio file from Khmer text using Edge-TTS Neural Voice"""
    try:
        async def _speak():
            communicate = edge_tts.Communicate(text, voice_name, rate=rate)
            await communicate.save(output_path)
            
        asyncio.run(_speak())
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"TTS error: {e}")
        return False

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
        progress_callback("កំពុងរៀបចំសំឡេងនិយាយភាសាខ្មែរ (Initializing Khmer TTS)...", 0.05)

    # Base silent track matching video duration
    total_ms = int(total_duration_sec * 1000) + 2000
    base_track = AudioSegment.silent(duration=total_ms)

    temp_files = []
    total_subs = len(subtitles)

    try:
        for idx, sub in enumerate(subtitles):
            text = sub.get("translated", "").strip()
            if not text:
                continue

            start_ms = int(sub["start"] * 1000)
            end_ms = int(sub["end"] * 1000)
            target_duration_ms = max(500, end_ms - start_ms)

            # Generate temp mp3 for this sentence
            temp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            temp_files.append(temp_mp3)

            ok = generate_speech_file(text, voice_name, temp_mp3)
            if not ok or not os.path.exists(temp_mp3):
                continue

            # Load segment audio
            try:
                line_audio = AudioSegment.from_file(temp_mp3)
                # Adjust playback speed if speech is longer than video segment window
                speech_len = len(line_audio)
                if speech_len > target_duration_ms * 1.3:
                    # Accelerate slightly to fit dialogue timing if needed
                    speed_factor = min(1.35, speech_len / target_duration_ms)
                    # pydub speedup
                    line_audio = line_audio.speedup(playback_speed=speed_factor)

                # Overlay at timestamp
                base_track = base_track.overlay(line_audio, position=start_ms)
            except Exception as ex:
                print(f"Overlay line error: {ex}")

            if progress_callback:
                pct = 0.05 + (0.85 * (idx + 1) / total_subs)
                progress_callback(f"បង្កើតសំឡេងនិយាយខ្មែរ [{idx+1}/{total_subs}]: {text[:25]}...", pct)

        if progress_callback:
            progress_callback("Exporting final dubbed audio...", 0.95)

        # Export final audio file
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

    # ffmpeg amix filter to blend background sound (15%) + loud Khmer voice (100%)
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
        # Fallback if video had no audio stream originally
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
