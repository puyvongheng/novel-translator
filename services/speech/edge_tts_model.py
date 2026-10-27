"""
Microsoft Edge-TTS Neural Voice Model
Provides natural Khmer neural voice synthesis (km-KH-PisethNeural, km-KH-SreymomNeural).
With built-in studio-quality post-processing for a richer, more melodious Khmer voice.
"""

import asyncio
import os
import subprocess
import edge_tts

# Standard Edge-TTS Khmer voices
EDGE_KHMER_VOICES = {
    "Piseth Neural": "km-KH-PisethNeural",
    "Sreymom Neural": "km-KH-SreymomNeural",
    "km-KH-PisethNeural": "km-KH-PisethNeural",
    "km-KH-SreymomNeural": "km-KH-SreymomNeural"
}

# ── Studio Enhancement Filter Chain for Khmer Neural Voices ──────────────────
# Applied automatically after every Edge TTS synthesis.
# Goal: ពិរោះ រណ្ដាំ ធម្មជាតិ — warm, present, clear, cinema-quality.
#
# Filter breakdown:
#  1. highpass=f=60        — cut sub-bass rumble (mic noise)
#  2. equalizer warmth     — +4dB at 220Hz: body & warmth in Khmer vowels
#  3. equalizer presence   — +3dB at 3200Hz: articulation & clarity
#  4. equalizer air        — +2dB at 10000Hz: subtle sparkle/air
#  5. compand              — gentle dynamic compression: steady, confident voice
#  6. loudnorm             — EBU R128 loudness normalisation (-16 LUFS broadcast)
# ─────────────────────────────────────────────────────────────────────────────
EDGE_TTS_ENHANCE_FILTER_SHORT = (
    "highpass=f=60,"
    "equalizer=f=220:width_type=o:width=1.4:g=4,"
    "equalizer=f=3200:width_type=o:width=1.2:g=3,"
    "equalizer=f=10000:width_type=o:width=1.0:g=2,"
    "compand=attacks=0.02:decays=0.15:points=-70/-70|-30/-22|-10/-8|0/-3:soft-knee=6"
)
EDGE_TTS_ENHANCE_FILTER = EDGE_TTS_ENHANCE_FILTER_SHORT


class EdgeTTSModel:
    """
    Microsoft Edge-TTS Engine for Khmer Speech Synthesis:
    - High-quality natural neural sound
    - Free without API keys
    - Configurable speech rate (+0% to +20%), pitch, and volume
    - Automatic studio post-processing for richer, more melodious Khmer voice
    - Safe retry and duration-aware enhancement to ensure no words are lost
    """
    def __init__(self, default_voice: str = "km-KH-PisethNeural"):
        self.default_voice = default_voice

    def resolve_voice_name(self, voice_choice: str) -> str:
        """Maps user-friendly voice label to official Edge-TTS voice identifier"""
        if not voice_choice:
            return self.default_voice
        if "Sreymom" in voice_choice or "ស្រី" in voice_choice:
            return "km-KH-SreymomNeural"
        elif "Piseth" in voice_choice or "ប្រុស" in voice_choice:
            return "km-KH-PisethNeural"
        elif voice_choice in EDGE_KHMER_VOICES:
            return EDGE_KHMER_VOICES[voice_choice]
        return self.default_voice

    def generate_speech(
        self,
        text: str,
        output_path: str,
        voice_name: str = None,
        rate: str = "+0%",
        pitch: str = "+8Hz",   # +8Hz default: Khmer sounds warmer & more natural
        volume: str = "+0%",
        enhance: bool = True   # apply studio post-processing by default
    ) -> bool:
        """
        Synthesizes text into an MP3 file using Edge-TTS with automatic retry,
        then applies studio enhancement filters ensuring full voice preservation.
        """
        if not text or not text.strip() or not any(c.isalnum() for c in text):
            return False

        target_voice = self.resolve_voice_name(voice_name)

        # Check if text is pure Chinese while voice is Khmer
        has_khmer = any(('\u1780' <= ch <= '\u17ff') or ('\u19e0' <= ch <= '\u19ff') for ch in text)
        has_chinese = any('\u4e00' <= ch <= '\u9fff' for ch in text)
        if has_chinese and not has_khmer and target_voice.startswith("km-"):
            print(f"⚠️ [Edge-TTS] អត្ថបទនៅជាអក្សរចិន ('{text[:25]}...') មិនអាចនិយាយជាមួយសំឡេងខ្មែរ {target_voice} បានទេ! សូមបកប្រែជាភាសាខ្មែរជាមុនសិន។")
            return False

        try:
            is_m4a = output_path.lower().endswith(".m4a")
            # Step 1: Raw Edge TTS synthesis with retry loop
            raw_path = output_path + ".raw.mp3" if (enhance or is_m4a) else output_path

            async def _speak():
                for attempt in range(3):
                    try:
                        communicate = edge_tts.Communicate(
                            text.strip(),
                            target_voice,
                            rate=rate,
                            pitch=pitch,
                            volume=volume
                        )
                        await communicate.save(raw_path)
                        if os.path.exists(raw_path) and os.path.getsize(raw_path) > 100:
                            return True
                    except Exception as err:
                        if attempt == 2:
                            print(f"Edge TTS attempt {attempt+1} error: {err}")
                        await asyncio.sleep(0.3 * (attempt + 1))
                return os.path.exists(raw_path) and os.path.getsize(raw_path) > 100

            ok_speak = asyncio.run(_speak())

            if not ok_speak or not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
                return False

            # Step 2: Studio enhancement post-processing
            if enhance:
                # Check clip duration: loudnorm requires >= 0.8s, otherwise use SHORT filter
                filter_chain = EDGE_TTS_ENHANCE_FILTER
                try:
                    import soundfile
                    dur = float(soundfile.info(raw_path).duration)
                    if dur < 0.8:
                        filter_chain = EDGE_TTS_ENHANCE_FILTER_SHORT
                except Exception:
                    pass

                ok_enh = _apply_enhancement(raw_path, output_path, filter_str=filter_chain)
                if not ok_enh:
                    # Fallback to SHORT filter without loudnorm
                    ok_enh = _apply_enhancement(raw_path, output_path, filter_str=EDGE_TTS_ENHANCE_FILTER_SHORT)
                if not ok_enh:
                    if is_m4a:
                        cmd = ["ffmpeg", "-y", "-i", raw_path, "-c:a", "aac", "-b:a", "160k", "-threads", "1", output_path]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        import shutil
                        try:
                            shutil.copy2(raw_path, output_path)
                        except Exception:
                            pass

                # Safely clean up raw file AFTER output_path has been created
                if os.path.exists(raw_path) and raw_path != output_path:
                    try:
                        os.remove(raw_path)
                    except Exception:
                        pass

                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            elif is_m4a:
                # Convert raw mp3 to lightweight m4a (AAC)
                cmd = ["ffmpeg", "-y", "-i", raw_path, "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-threads", "1", output_path]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(raw_path):
                    try:
                        os.remove(raw_path)
                    except Exception:
                        pass
                return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0

            return os.path.exists(output_path) and os.path.getsize(output_path) > 0

        except Exception as e:
            print(f"Edge-TTS synthesis error: {e}")
            return False


def _apply_enhancement(raw_path: str, output_path: str, filter_str: str = None) -> bool:
    """
    Applies the studio-quality Khmer voice enhancement filter chain via FFmpeg.
    Supports both .m4a and .mp3 outputs with multi-thread safety.
    Returns True if successful.
    """
    try:
        f_to_use = filter_str or globals().get("EDGE_TTS_ENHANCE_FILTER") or EDGE_TTS_ENHANCE_FILTER_SHORT
        if not f_to_use:
            f_to_use = "highpass=f=60,equalizer=f=220:width_type=o:width=1.4:g=4,equalizer=f=3200:width_type=o:width=1.2:g=3"
        
        is_m4a = output_path.lower().endswith(".m4a")
        codec_args = ["-c:a", "aac", "-b:a", "160k"] if is_m4a else ["-acodec", "libmp3lame", "-b:a", "192k"]

        cmd = [
            "ffmpeg", "-y", "-i", raw_path,
            "-filter:a", f_to_use,
            *codec_args,
            "-ar", "44100",
            "-threads", "1",
            output_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"Enhancement filter error: {e}")
        return False


# Standalone helper function
def generate_edge_tts(
    text: str,
    output_path: str,
    voice_name: str = "km-KH-PisethNeural",
    rate: str = "+0%",
    pitch: str = "+8Hz",
    enhance: bool = True
) -> bool:
    model = EdgeTTSModel()
    return model.generate_speech(text, output_path, voice_name=voice_name, rate=rate, pitch=pitch, enhance=enhance)
