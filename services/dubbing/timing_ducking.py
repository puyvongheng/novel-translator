"""
Timing & Audio Ducking Module
Handles dynamic speech rate calculation, audio duration fitting (atempo), and smart auto-ducking mixing.
"""

import os
import subprocess



def calculate_auto_rate(
    text: str,
    target_dur: float,
    user_rate: str = "+0%"
) -> str:
    """
    គណនាល្បឿន AI Voice ឱ្យសមរម្យ និងធម្មជាតិបំផុត។
    Rate អតិបរមាត្រឹម +15% យ៉ាងច្រើនបំផុត ដើម្បីកុំឱ្យសំឡេងនិយាយលឿនពេក ពិបាកស្តាប់។
    """
    MAX_RATE = 35  # អតិបរមាត្រឹម +35% សម្រាប់ប្រយោគវែងៗដើម្បីកុំឱ្យដាច់ពាក្យចុងក្រោយ

    if target_dur <= 0.1:
        return "+0%"

    # បម្លែង Rate ទៅជាលេខ និងការពារតម្លៃមិនត្រឹមត្រូវ
    try:
        cleaned = str(user_rate).replace("%", "").replace("+", "").strip()
        user_pct = int(cleaned) if cleaned else 0
    except (ValueError, TypeError):
        user_pct = 0

    user_pct = max(-20, min(MAX_RATE, user_pct))

    char_count = len(text.replace(" ", "").replace("\n", ""))
    expected_dur = max(0.6, char_count / 10.5)

    # គណនាល្បឿនដែលត្រូវការដើម្បីឱ្យទាន់ពេល
    if expected_dur > target_dur:
        ratio = expected_dur / target_dur
        needed_pct = int((ratio - 1.0) * 100)
        needed_pct = max(0, min(MAX_RATE, needed_pct))
        chosen_pct = max(user_pct, needed_pct)
        return f"+{chosen_pct}%"

    return f"+{user_pct}%" if user_pct >= 0 else f"{user_pct}%"



def get_audio_duration(filepath: str) -> float:
    """High-speed pure C duration reader (0.3ms per file) with ffprobe fallback."""
    try:
        import soundfile
        return float(soundfile.info(filepath).duration)
    except Exception:
        pass
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", filepath]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0


def fit_audio_to_duration(filepath: str, target_dur: float, max_ratio: float = 1.35) -> bool:
    """
    សម្រួលរយៈពេលសំឡេងដោយរក្សាសំឡេងធម្មជាតិ និងច្បាស់ស្រួលស្តាប់។
    រូបមន្ត៖ Speed Ratio = TTS Duration / SRT Duration
    កម្រិតល្បឿន atempo អតិបរមាត្រឹម max_ratio (លំនាំដើម 1.35x) ដើម្បីឱ្យសំឡេងនិយាយចប់សព្វគ្រប់ មិនដាច់ពាក្យចុងក្រោយ។
    """
    if not os.path.exists(filepath) or target_dur <= 0.2:
        return False
    try:
        actual_dur = get_audio_duration(filepath)
        if actual_dur <= 0.0:
            return False

        # កែសម្រួលតែនៅពេលសំឡេងវែងជាង target_dur លើសពី 4% ប៉ុណ្ណោះ
        if actual_dur > target_dur * 1.04:
            speed_mult = min(max_ratio, actual_dur / target_dur)
            if speed_mult <= 1.03:
                return False

            stretched_tmp = filepath + ".stretched.mp3"
            filter_str = f"atempo={speed_mult:.3f}"

            scmd = ["ffmpeg", "-y", "-i", filepath, "-filter:a", filter_str, "-vn", "-acodec", "libmp3lame", "-q:a", "4", stretched_tmp]
            sres = subprocess.run(scmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if sres.returncode == 0 and os.path.exists(stretched_tmp) and os.path.getsize(stretched_tmp) > 0:
                try:
                    os.replace(stretched_tmp, filepath)
                except Exception:
                    import shutil
                    shutil.move(stretched_tmp, filepath)
                return True
    except Exception as e:
        print(f"Fit audio error: {e}")
    return False


def change_audio_speed(filepath: str, speed_mult: float) -> bool:
    """
    កែប្រែល្បឿនសំឡេងដោយផ្ទាល់តាមរយៈ FFmpeg atempo filter (0.5x - 2.0x) ដោយរក្សា Pitch ដើមឱ្យនៅដដែល។
    """
    if not os.path.exists(filepath) or speed_mult <= 0.2:
        return False
    speed_mult = max(0.5, min(2.0, speed_mult))
    if abs(speed_mult - 1.0) < 0.02:
        return True
    try:
        stretched_tmp = filepath + ".speed.mp3"
        filter_str = f"atempo={speed_mult:.3f}"
        scmd = ["ffmpeg", "-y", "-i", filepath, "-filter:a", filter_str, "-vn", "-acodec", "libmp3lame", "-q:a", "4", stretched_tmp]
        sres = subprocess.run(scmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if sres.returncode == 0 and os.path.exists(stretched_tmp) and os.path.getsize(stretched_tmp) > 0:
            try:
                os.replace(stretched_tmp, filepath)
            except Exception:
                import shutil
                shutil.move(stretched_tmp, filepath)
            return True
    except Exception as e:
        print(f"Change audio speed error: {e}")
    return False


def merge_dub_with_movie(
    video_path: str,
    dubbed_audio_path: str,
    output_video_path: str,
    original_volume: float = 0.85,
    dub_volume: float = 1.0,
    auto_ducking: bool = True,
    progress_callback=None
) -> bool:
    """Blends video background audio with clear Khmer voiceover using smart auto-ducking sidechain."""
    if progress_callback:
        progress_callback("Mixing movie audio with Khmer voiceover (Auto-Ducking)...", 0.2)

    if auto_ducking:
        try:
            from services.dubbing.track_assembler import mix_movie_with_dubbed_audio
            import tempfile
            temp_mix = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            if mix_movie_with_dubbed_audio(
                video_or_orig_audio=video_path,
                dubbed_audio_path=dubbed_audio_path,
                output_audio_path=temp_mix,
                orig_vol=original_volume,
                dub_vol=dub_volume,
                auto_duck=True
            ):
                cmd = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-i", temp_mix,
                    "-map", "0:v",
                    "-map", "1:a",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    output_video_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    os.remove(temp_mix)
                except Exception:
                    pass
                if progress_callback:
                    progress_callback("Dubbed movie export complete!", 1.0)
                return res.returncode == 0
        except Exception:
            pass

        filter_complex = (
            f"[0:a]volume={original_volume}[bg];"
            f"[1:a]volume={dub_volume}[dub];"
            f"[bg][dub]sidechaincompress=threshold=0.01:ratio=20:attack=10:release=250[bg_ducked];"
            f"[bg_ducked][dub]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
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
        # Fallback if original video had no audio track
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
