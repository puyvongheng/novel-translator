"""
Dubbing Engine Orchestrator
Coordinates voice cloning, timing alignment, neural synthesis, audio filters, and video track mixing.
"""

import os
import asyncio
import subprocess
import edge_tts
from pydub import AudioSegment

from services.speech.edge_tts_model import EdgeTTSModel

from config import KHMER_VOICES, VOICE_PROFILES
from utils.time_utils import format_filename_timestamp

from services.dubbing.cloning import (
    CLONED_VOICES_FILE,
    get_cloned_voices,
    save_cloned_voice,
    delete_cloned_voice,
    analyze_voice_sample,
    extract_reference_acoustic_profile,
)
from services.dubbing.audio_effects import (
    PRESET_EFFECTS,
    build_voice_filters,
    apply_audio_effects,
)
from services.dubbing.timing_ducking import (
    calculate_auto_rate,
    get_audio_duration,
    fit_audio_to_duration,
    merge_dub_with_movie,
)
from services.dubbing.track_assembler import (
    generate_segment_files,
    assemble_dubbed_audio,
)


class DubbingEngine:
    """
    OOP Khmer Dubbing Engine:
    - Generates separate individual audio files for each subtitle line:
      Example: #1 00:00:00 - 00:00:10 -> '#1_00-00-00_to_00-00-10.mp3'
    - Pre-caches speech for instant real-time playback during video preview
    - Assembles synchronized audio track for final movie export
    """
    CLONED_VOICES_FILE = CLONED_VOICES_FILE

    def __init__(self, voice_name: str = "km-KH-PisethNeural", log_callback=None):
        self.voice_name = voice_name
        self.log_callback = log_callback

    def log(self, text: str):
        """Dispatches log message to log_callback if registered, or stdout."""
        if self.log_callback:
            try:
                self.log_callback(text)
                return
            except Exception:
                pass
        try:
            print(f"[AI Voice Engine] {text}")
        except Exception:
            try:
                safe_text = text.encode("ascii", errors="replace").decode("ascii")
                print(f"[AI Voice Engine] {safe_text}")
            except Exception:
                pass

    def set_voice(self, voice_key: str):
        """Resolves voice name from key or preset profile."""
        if voice_key in VOICE_PROFILES:
            self.voice_name = VOICE_PROFILES[voice_key]["voice"]
        elif voice_key in KHMER_VOICES:
            self.voice_name = KHMER_VOICES[voice_key]
        elif "-" in voice_key and "Neural" in voice_key:
            self.voice_name = voice_key
        else:
            found = False
            for k, v in VOICE_PROFILES.items():
                first_word = voice_key.split()[0] if voice_key else ""
                if first_word and (first_word in k or k in voice_key):
                    self.voice_name = v["voice"]
                    found = True
                    break
            if not found:
                if "Sreymom" in voice_key or "ស្រី" in voice_key:
                    self.voice_name = "km-KH-SreymomNeural"
                else:
                    self.voice_name = "km-KH-PisethNeural"

    # --- Delegated Cloning API ---
    @classmethod
    def get_cloned_voices(cls) -> dict:
        return get_cloned_voices()

    @classmethod
    def save_cloned_voice(cls, name: str, base_voice: str, pitch_scale: float, formant: str, bass_gain: float, treble_gain: float, ref_path: str = None) -> bool:
        return save_cloned_voice(name, base_voice, pitch_scale, formant, bass_gain, treble_gain, ref_path)

    @classmethod
    def delete_cloned_voice(cls, name: str) -> bool:
        return delete_cloned_voice(name)

    @staticmethod
    def analyze_voice_sample(sample_path: str) -> dict:
        return analyze_voice_sample(sample_path)

    @staticmethod
    def extract_reference_acoustic_profile(sample_path: str) -> dict:
        return extract_reference_acoustic_profile(sample_path)

    # --- Delegated Effects API ---
    @staticmethod
    def apply_audio_effects(
        raw_audio_path: str,
        output_path: str,
        voice_effect: str = "none",
        clone_params: dict = None,
        bgm_path: str = None,
        bgm_vol: float = 0.15,
        bitrate: str = "320k",
        acodec: str = "libmp3lame"
    ) -> bool:
        return apply_audio_effects(
            raw_audio_path=raw_audio_path,
            output_path=output_path,
            voice_effect=voice_effect,
            clone_params=clone_params,
            bgm_path=bgm_path,
            bgm_vol=bgm_vol,
            bitrate=bitrate,
            acodec=acodec
        )

    # --- Delegated Timing API ---
    @staticmethod
    def calculate_auto_rate(text: str, target_dur: float, user_rate: str = "+0%") -> str:
        return calculate_auto_rate(text, target_dur, user_rate)

    @staticmethod
    def get_audio_duration(filepath: str) -> float:
        return get_audio_duration(filepath)

    @staticmethod
    def fit_audio_to_duration(filepath: str, target_dur: float) -> bool:
        return fit_audio_to_duration(filepath, target_dur)

    @staticmethod
    def merge_dub_with_movie(
        video_path: str,
        dubbed_audio_path: str,
        output_video_path: str,
        original_volume: float = 0.85,
        dub_volume: float = 1.0,
        auto_ducking: bool = True,
        progress_callback=None
    ) -> bool:
        return merge_dub_with_movie(
            video_path=video_path,
            dubbed_audio_path=dubbed_audio_path,
            output_video_path=output_video_path,
            original_volume=original_volume,
            dub_volume=dub_volume,
            auto_ducking=auto_ducking,
            progress_callback=progress_callback
        )

    # --- Gemini 2.0 Native Audio Synthesis ---
    @staticmethod
    def synthesize_gemini_audio(
        text: str,
        output_path: str,
        api_key: str,
        model: str = "gemini-2.0-flash",
        voice_name: str = "Puck",
        persona: str = "",
        emotion: str = ""
    ) -> bool:
        """
        Synthesizes real audio directly from Google DeepMind Gemini API (Gemini 2.0 native audio generation).
        """
        import base64
        import requests

        if not api_key:
            print("Gemini API Error: No API key provided")
            return False

        model_clean = model.split()[0].strip() if model else "gemini-2.0-flash"
        v_name = voice_name.split()[0].strip() if voice_name else "Puck"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_clean}:generateContent?key={api_key}"

        p_desc = f"Voice Persona: {persona}." if persona else ""
        e_desc = f"Emotional Tone: {emotion}." if emotion else ""
        system_instruction = f"{p_desc} {e_desc}".strip()
        full_prompt = f"{system_instruction}\n\nRead the following text out loud with authentic voice:\n{text}".strip()

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": full_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": v_name
                        }
                    }
                }
            }
        }

        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
            if resp.status_code != 200:
                print(f"Gemini API returned status {resp.status_code}: {resp.text[:250]}")
                return False

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                print("Gemini API: No candidates in response")
                return False

            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                if "inlineData" in p:
                    b64_data = p["inlineData"].get("data", "")
                    mime_type = p["inlineData"].get("mimeType", "")
                    if b64_data:
                        raw_bytes = base64.b64decode(b64_data)
                        tmp_raw = output_path + ".gemini_raw"
                        with open(tmp_raw, "wb") as f_out:
                            f_out.write(raw_bytes)

                        # Convert to target output format via ffmpeg
                        if "pcm" in mime_type.lower():
                            conv_cmd = ["ffmpeg", "-y", "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", tmp_raw, output_path]
                        else:
                            conv_cmd = ["ffmpeg", "-y", "-i", tmp_raw, output_path]

                        subprocess.run(conv_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if os.path.exists(tmp_raw):
                            try:
                                os.remove(tmp_raw)
                            except Exception:
                                pass
                        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
            return False
        except Exception as e:
            print(f"Gemini Audio error: {e}")
            return False

    # --- Line Level Synthesis & Effects Pipeline ---
    def synthesize_line(
        self,
        text: str,
        output_path: str,
        rate: str = "+0%",
        pitch: str = "+8Hz",   # +8Hz default — Khmer sounds warmer & more natural
        volume: str = "+0%",
        voice_effect: str = "none",
        clone_params: dict = None,
        bgm_path: str = None,
        bgm_vol: float = 0.15,
        bitrate: str = "192k",
        acodec: str = "libmp3lame",
        target_dur: float = 0.0,
        auto_rate: bool = False,  # Default False: don't override user's rate unless explicitly requested
        engine: str = "edgetts",
        gemini_config: dict = None,
        enhance: bool = False,  # False for ultra-fast line dubbing; master EQ applied during assembly
        voice_name: str = None
    ) -> bool:
        """Synthesizes a single subtitle dialogue line with dynamic rate sync and ultra-fast generation."""
        # Clamp rate gently (max +15%) so voice sounds natural and easy to understand
        try:
            r_clean = str(rate).replace("%", "").replace("+", "").strip()
            r_val = int(r_clean) if r_clean else 0
            if r_val > 35:
                rate = "+35%"
            elif r_val < -20:
                rate = "-20%"
            else:
                rate = f"+{r_val}%" if r_val >= 0 else f"{r_val}%"
        except Exception:
            rate = "+0%"

        if auto_rate and target_dur > 0:
            rate = self.calculate_auto_rate(text, target_dur, rate)

        is_gemini = "gemini" in engine.lower() and gemini_config and gemini_config.get("api_key")
        is_m4a = output_path.lower().endswith(".m4a")

        try:
            needs_effects = (
                voice_effect != "none"
                or bool(clone_params)
                or (bgm_path and os.path.exists(bgm_path))
                or (acodec != "libmp3lame" and not is_m4a)
            )

            raw_file = output_path + ".raw.mp3" if needs_effects else output_path

            # Branch 1: Google Gemini 2.0 Audio Synthesis
            if is_gemini:
                ok = self.synthesize_gemini_audio(
                    text=text,
                    output_path=raw_file,
                    api_key=gemini_config["api_key"],
                    model=gemini_config.get("model", "gemini-2.0-flash"),
                    voice_name=gemini_config.get("voice_name", "Puck"),
                    persona=gemini_config.get("persona", ""),
                    emotion=gemini_config.get("emotion", "")
                )
                chosen_v = voice_name or self.voice_name
                if not ok:
                    _em = EdgeTTSModel(default_voice=chosen_v)
                    _em.generate_speech(
                        text=text, output_path=raw_file,
                        voice_name=chosen_v, rate=rate, pitch=pitch,
                        volume=volume, enhance=enhance
                    )
            else:
                # Branch 2: Edge TTS Neural (ultra-fast direct synthesis)
                chosen_v = voice_name or self.voice_name
                _em = EdgeTTSModel(default_voice=chosen_v)
                _em.generate_speech(
                    text=text,
                    output_path=raw_file,
                    voice_name=chosen_v,
                    rate=rate,
                    pitch=pitch,
                    volume=volume,
                    enhance=enhance
                )

            ok = os.path.exists(raw_file) and os.path.getsize(raw_file) > 0
            if not ok:
                self.log(f"❌ [AI Voice] បរាជ័យក្នុងការបង្កើតសំឡេងដោយ AI ({'Gemini' if is_gemini else 'Edge TTS'})")
                return False

            if target_dur > 0:
                self.fit_audio_to_duration(raw_file, target_dur)

            if needs_effects:
                fx_ok = self.apply_audio_effects(
                    raw_audio_path=raw_file,
                    output_path=output_path,
                    voice_effect=voice_effect,
                    clone_params=clone_params,
                    bgm_path=bgm_path,
                    bgm_vol=bgm_vol,
                    bitrate=bitrate,
                    acodec=acodec
                )
                if os.path.exists(raw_file):
                    try:
                        os.remove(raw_file)
                    except Exception:
                        pass
                if fx_ok:
                    self.log(f"✅ [AI Voice] បង្កើតសំឡេងដោយ AI ជោគជ័យ -> {os.path.basename(output_path)}")
                return fx_ok

            self.log(f"✅ [AI Voice] បង្កើតសំឡេងដោយ AI ជោគជ័យ -> {os.path.basename(output_path)}")
            return True
        except Exception as e:
            print(f"TTS error: {e}")
            self.log(f"❌ [AI Voice] កំហុសពេលបង្កើតសំឡេងដោយ AI: {e}")
            return False

    # --- Multi-segment Batch and Assembly ---
    def generate_segment_files(
        self,
        subtitles: list,
        voice_dir: str,
        default_rate: str = "+0%",
        force_refresh: bool = False,
        progress_callback=None
    ) -> list:
        """Generates individual voice files per subtitle segment concurrently."""
        return generate_segment_files(
            subtitles=subtitles,
            voice_dir=voice_dir,
            voice_name=self.voice_name,
            default_rate=default_rate,
            force_refresh=force_refresh,
            progress_callback=progress_callback,
            log_callback=self.log
        )

    def assemble_dubbed_audio(
        self,
        subtitles: list,
        total_duration_sec: float,
        output_wav_path: str,
        voice_dir: str = None,
        default_rate: str = "+0%",
        progress_callback=None
    ) -> str:
        """Assembles individual audio segment clips into a single synchronized audio track."""
        return assemble_dubbed_audio(
            subtitles=subtitles,
            total_duration_sec=total_duration_sec,
            output_wav_path=output_wav_path,
            voice_dir=voice_dir,
            default_rate=default_rate,
            voice_name=self.voice_name,
            progress_callback=progress_callback,
            log_callback=self.log
        )

    def create_dubbed_audio(
        self,
        subtitles: list,
        total_duration_sec: float,
        output_wav_path: str,
        voice_dir: str = None,
        progress_callback=None
    ) -> str:
        """Alias for backward compatibility - creates individual segment files then assembles."""
        if not voice_dir:
            voice_dir = os.path.join(os.path.dirname(output_wav_path), "khmer_voices")
        return self.assemble_dubbed_audio(subtitles, total_duration_sec, output_wav_path, voice_dir, progress_callback=progress_callback)

    def mute_dialogue_at_srt_intervals(
        self,
        input_media_path: str,
        output_audio_path: str,
        subtitles: list,
        fade_ms: float = 45.0,
        progress_callback=None
    ) -> bool:
        """
        Blazing-fast sample-accurate audio muting strictly at SRT subtitle intervals.
        Mutes original Chinese dialogue during timecodes (e.g. 1:05 - 1:40) with smooth 45ms fade curves.
        Leaves 100% of background music, fight sounds, and environment noise intact outside subtitle cues.
        """
        from services.dubbing.track_assembler import mute_audio_at_srt_intervals
        return mute_audio_at_srt_intervals(
            input_media_path=input_media_path,
            output_audio_path=output_audio_path,
            subtitles=subtitles,
            fade_ms=fade_ms,
            progress_callback=progress_callback
        )
