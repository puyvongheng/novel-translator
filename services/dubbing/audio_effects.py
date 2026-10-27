"""
Audio Effects & Equalizer Processing Module
Handles studio audio filters, voice cloning effects, equalizer profiles, and BGM mixing.
"""

import os
import subprocess
from services.dubbing.cloning import extract_reference_acoustic_profile


# Comprehensive CapCut-Style Voice Effects & Presets
CAPCUT_VOICE_EFFECTS = [
    ("none", "🔄 សំឡេងដើមធម្មតា (Original / Normal)", "none"),
    ("kid", "👶 សំឡេងកូនក្មេង (Kid / Child - CapCut)", "pitch_up"),
    ("baby", "🍼 សំឡេងទារក (Baby / Toddler)", "pitch_up"),
    ("chipmunk", "🐿️ សំឡេងកំប្រុក / អេលីយ៉ូម (Chipmunk / Helium)", "pitch_up"),
    ("robot", "🤖 សំឡេងមនុស្សយន្ត (Robot / Cyborg)", "vocoder"),
    ("deep_male", "🐻 សំឡេងធំ / ជ្រៅ (Deep Male / Villain)", "pitch_down"),
    ("giant", "👹 សំឡេងយក្ស (Giant Monster)", "pitch_down"),
    ("echo_hall", "🏛️ អេកូ / សាលធំ (Concert Hall Echo)", "reverb"),
    ("cave", "🏔️ រូងភ្នំ (Cave Echo Reverb)", "reverb"),
    ("telephone", "📞 ទូរស័ព្ទ (Old Telephone)", "filter"),
    ("walkie_talkie", "📻 វិទ្យុទាក់ទង (Walkie-Talkie Radio)", "filter"),
    ("megaphone", "📢 ឧបករណ៍បំពងសំឡេង (Megaphone)", "distortion"),
    ("ghost", "👻 ខ្មោច / ព្រឺព្រួច (Ghost / Horror)", "horror"),
    ("alien", "👽 ភពក្រៅ (Alien / Martian)", "synth"),
    ("tremolo", "〰️ សំឡេងញ័រ (Tremolo Vibrato)", "mod"),
    ("distortion", "🎸 សំឡេងបែក Distortion (Heavy Rock)", "distortion"),
    ("cinema_bass", "🎬 រោងកុន Cinema Bass (Cinema Warmth)", "cinema"),
    ("soft_whisper", "🤫 សំឡេងខ្សឹប (Soft Whisper)", "whisper")
]

# Preset equalizer, pitch transformation, and audio filter chains
PRESET_EFFECTS = {
    # CapCut Voice Changers
    "kid": "asetrate=44100*1.32,aresample=44100,atempo=1/1.32,equalizer=f=3200:width_type=o:width=1.5:g=3.5",
    "baby": "asetrate=44100*1.42,aresample=44100,atempo=1/1.42,equalizer=f=3500:width_type=o:width=1.2:g=4",
    "chipmunk": "asetrate=44100*1.55,aresample=44100,atempo=1/1.55,equalizer=f=4000:width_type=o:width=1.5:g=3",
    "robot": "flanger=delay=5:depth=2:regen=55:width=80:speed=0.6,equalizer=f=1200:width_type=h:width=250:g=9,aecho=0.8:0.85:25:0.5",
    "deep_male": "asetrate=44100*0.75,aresample=44100,atempo=1/0.75,equalizer=f=100:width_type=o:width=1.2:g=8,compand=attacks=0.02:decays=0.2:points=-50/-40|-20/-10|0/-2",
    "giant": "asetrate=44100*0.68,aresample=44100,atempo=1/0.68,equalizer=f=80:width_type=o:width=1.2:g=10,aecho=0.8:0.9:40:0.3",
    "echo_hall": "aecho=0.8:0.88:60|120:0.4|0.25",
    "reverb_hall": "aecho=0.8:0.88:40|80:0.3|0.2",
    "cave": "aecho=0.8:0.85:120|240|360:0.5|0.3|0.15",
    "telephone": "highpass=f=450,lowpass=f=3200,equalizer=f=1600:width_type=h:width=800:g=6,volume=1.3",
    "walkie_talkie": "highpass=f=500,lowpass=f=2800,equalizer=f=1800:width_type=h:width=600:g=8,overdrive=8,volume=1.2",
    "megaphone": "highpass=f=600,lowpass=f=2600,equalizer=f=2000:width_type=h:width=700:g=10,overdrive=14,volume=1.25",
    "radio": "highpass=f=350,lowpass=f=3800,equalizer=f=1500:width_type=o:width=1.5:g=3.5,compand=attacks=0.01:decays=0.1:points=-50/-40|-20/-12|0/-1",
    "radio_warmth": "highpass=f=350,lowpass=f=3800,equalizer=f=1500:width_type=o:width=1.5:g=3.5,compand=attacks=0.01:decays=0.1:points=-50/-40|-20/-12|0/-1",
    "radio_am": "highpass=f=350,lowpass=f=3800,equalizer=f=1500:width_type=o:width=1.5:g=3.5,compand=attacks=0.01:decays=0.1:points=-50/-40|-20/-12|0/-1",
    "ghost": "asetrate=44100*0.86,aresample=44100,atempo=1/0.86,aecho=0.8:0.88:80|160:0.45|0.3,flanger=delay=8:depth=3:regen=45:speed=0.25",
    "alien": "asetrate=44100*1.18,aresample=44100,atempo=1/1.18,tremolo=f=14:d=0.7,flanger=delay=4:depth=3:regen=60",
    "tremolo": "tremolo=f=8:d=0.6",
    "distortion": "overdrive=18,equalizer=f=2200:width_type=o:width=1.2:g=5",
    "soft_whisper": "lowpass=f=4500,volume=0.9,compand=attacks=0.05:decays=0.3:points=-80/-80|-40/-30|0/-10",
    "cinema_bass": (
        "equalizer=f=80:width_type=o:width=1:g=8,"
        "equalizer=f=250:width_type=o:width=1:g=4,"
        "compand=attacks=0.02:decays=0.2:points=-60/-60|-20/-10|0/-3:soft-knee=6"
    ),
    "cinema_warmth": (
        "equalizer=f=90:width_type=o:width=1.2:g=5,"
        "equalizer=f=6000:width_type=o:width=1.5:g=3,"
        "compand=attacks=0.01:decays=0.15:points=-50/-40|-18/-10|0/-2"
    )
}


def build_voice_filters(voice_effect: str = "none", clone_params: dict = None) -> list:
    """Builds the list of FFmpeg audio filters based on clone parameters and preset voice effects."""
    v_filters = []

    # 1. Voice Clone Transformation
    if clone_params:
        ref_path = clone_params.get("ref_path", "")
        preset_model = clone_params.get("preset_model", "")

        # If user provided a real audio sample, perform real acoustic clone extraction
        if ref_path and os.path.exists(ref_path):
            profile = extract_reference_acoustic_profile(ref_path)
            p_scale = profile.get("pitch_scale", 1.0) * float(clone_params.get("pitch_scale", 1.0))
            b_gain = profile.get("bass_db", 0.0) + float(clone_params.get("bass_gain", 0.0))
            t_gain = profile.get("treble_db", 0.0) + float(clone_params.get("treble_gain", 0.0))
            m_gain = profile.get("mid_db", 0.0)

            if abs(p_scale - 1.0) > 0.01:
                v_filters.append(f"rubberband=pitch={p_scale:.3f}:formant=shifted")
            if b_gain != 0:
                v_filters.append(f"equalizer=f=120:width_type=o:width=1.2:g={b_gain:.1f}")
            if m_gain != 0:
                v_filters.append(f"equalizer=f=1500:width_type=o:width=1.5:g={m_gain:.1f}")
            if t_gain != 0:
                v_filters.append(f"equalizer=f=7500:width_type=o:width=1.5:g={t_gain:.1f}")
        else:
            # Handle preset models or manual slider adjustments
            pitch_scale = float(clone_params.get("pitch_scale", 1.0))
            formant = clone_params.get("formant", "preserved")
            bass = float(clone_params.get("bass_gain", 0))
            treble = float(clone_params.get("treble_gain", 0))

            # Preset Specific Neural Modeling
            if "Uncle Narration" in preset_model or "ចាស់ទុំ" in preset_model:
                pitch_scale = 0.84
                formant = "shifted"
                bass += 6.5
                v_filters.append("compand=attacks=0.02:decays=0.2:points=-50/-40|-20/-10|0/-2:soft-knee=6")
            elif "Anime" in preset_model or "Cartoon" in preset_model:
                pitch_scale = 1.28
                formant = "shifted"
                treble += 4.5
                v_filters.append("equalizer=f=3400:width_type=o:width=1.2:g=4")
            elif "Radio" in preset_model or "វិទ្យុ" in preset_model:
                v_filters.append("highpass=f=350,lowpass=f=3500,equalizer=f=1800:width_type=h:width=800:g=4,volume=1.2")
            elif "Trailer" in preset_model or "សង្គ្រាម" in preset_model:
                pitch_scale = 0.88
                bass += 7.0
                treble += 3.5
                v_filters.append("compand=attacks=0.01:decays=0.15:points=-60/-50|-18/-8|0/-1")

            if abs(pitch_scale - 1.0) > 0.01:
                v_filters.append(f"rubberband=pitch={pitch_scale:.3f}:formant={formant}")

            if bass != 0:
                v_filters.append(f"equalizer=f=100:width_type=o:width=1:g={bass:.1f}")

            if treble != 0:
                v_filters.append(f"equalizer=f=8000:width_type=o:width=1:g={treble:.1f}")

    # 2. Preset Voice Effects
    if voice_effect in PRESET_EFFECTS:
        v_filters.append(PRESET_EFFECTS[voice_effect])

    return v_filters


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
    """Applies pitch/formant voice cloning, studio equalization, and background music mixing."""
    if not os.path.exists(raw_audio_path) or os.path.getsize(raw_audio_path) == 0:
        return False

    v_filters = build_voice_filters(voice_effect=voice_effect, clone_params=clone_params)
    v_filter_str = ",".join(v_filters) if v_filters else "anull"

    try:
        if bgm_path and os.path.exists(bgm_path) and os.path.getsize(bgm_path) > 0:
            filter_complex = f"[0:a]{v_filter_str}[v];[1:a]volume={bgm_vol:.2f}[b];[v][b]amix=inputs=2:duration=first:dropout_transition=2[out]"
            cmd = ["ffmpeg", "-y", "-i", raw_audio_path, "-stream_loop", "-1", "-i", bgm_path, "-filter_complex", filter_complex, "-map", "[out]"]
        else:
            cmd = ["ffmpeg", "-y", "-i", raw_audio_path, "-filter:a", v_filter_str]

        if acodec:
            cmd.extend(["-acodec", acodec])
        if bitrate and acodec == "libmp3lame":
            cmd.extend(["-b:a", bitrate])

        cmd.append(output_path)
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as e:
        print(f"Apply audio effects error: {e}")
        return False


def apply_voice_effect_to_file(raw_audio_path: str, voice_effect: str = "none", output_path: str = None) -> str:
    """
    Transforms an audio file with CapCut-style voice effects (kid, robot, deep male, echo, etc.).
    Returns path to the transformed audio file, or original path if effect is 'none'.
    """
    if not raw_audio_path or not os.path.exists(raw_audio_path):
        return raw_audio_path

    if not voice_effect or voice_effect in ("none", "original"):
        return raw_audio_path

    if not output_path:
        base_dir = os.path.dirname(raw_audio_path) or "."
        base_name, ext = os.path.splitext(os.path.basename(raw_audio_path))
        if not ext:
            ext = ".mp3"
        # Avoid chaining fx_kid_fx_robot...
        clean_name = base_name.split("_fx_")[0]
        output_path = os.path.join(base_dir, f"{clean_name}_fx_{voice_effect}{ext}")

    success = apply_audio_effects(raw_audio_path, output_path, voice_effect=voice_effect)
    if success and os.path.exists(output_path):
        return output_path
    return raw_audio_path


def get_voice_effect_label(fx_key: str) -> str:
    """Returns human-readable display label for voice effect key."""
    for key, label, _ in CAPCUT_VOICE_EFFECTS:
        if key == fx_key:
            return label
    return "🔄 សំឡេងដើមធម្មតា (Original / Normal)"


def get_voice_effect_icon(fx_key: str) -> str:
    """Returns representative emoji icon for voice effect key."""
    icons = {
        "kid": "👶",
        "baby": "🍼",
        "chipmunk": "🐿️",
        "robot": "🤖",
        "deep_male": "🐻",
        "giant": "👹",
        "echo_hall": "🏛️",
        "reverb_hall": "🏛️",
        "cave": "🏔️",
        "telephone": "📞",
        "walkie_talkie": "📻",
        "megaphone": "📢",
        "ghost": "👻",
        "alien": "👽",
        "tremolo": "〰️",
        "distortion": "🎸",
        "cinema_bass": "🎬",
        "soft_whisper": "🤫",
        "none": "🔄"
    }
    return icons.get(fx_key, "✨")


def stop_voice_effect_preview():
    """Stops any currently playing audio preview."""
    try:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.stop()
            pygame.mixer.music.stop()
    except Exception:
        pass


def preview_voice_effect(raw_audio_path: str, voice_effect: str = "none", max_seconds: float = 12.0) -> bool:
    """
    Applies the selected CapCut voice effect to an audio snippet and plays it instantly via Pygame.
    Stops previous playback before starting.
    """
    if not raw_audio_path or not os.path.exists(raw_audio_path):
        return False

    stop_voice_effect_preview()

    if not voice_effect or voice_effect in ("none", "original"):
        target_path = raw_audio_path
    else:
        # Create lightweight preview file in temp/scratch
        base_dir = os.path.dirname(raw_audio_path) or "."
        preview_path = os.path.join(base_dir, f"_preview_{voice_effect}.mp3")

        # Fast trim preview if file is long
        v_filters = build_voice_filters(voice_effect=voice_effect)
        v_filter_str = ",".join(v_filters) if v_filters else "anull"
        cmd = [
            "ffmpeg", "-y", "-i", raw_audio_path,
            "-t", str(max_seconds),
            "-filter:a", v_filter_str,
            "-acodec", "libmp3lame", "-b:a", "192k",
            preview_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and os.path.exists(preview_path) and os.path.getsize(preview_path) > 0:
                target_path = preview_path
            else:
                target_path = apply_voice_effect_to_file(raw_audio_path, voice_effect)
        except Exception:
            target_path = apply_voice_effect_to_file(raw_audio_path, voice_effect)

    if not target_path or not os.path.exists(target_path):
        return False

    try:
        import pygame
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            except Exception:
                pygame.mixer.init()
        snd = pygame.mixer.Sound(target_path)
        snd.set_volume(1.0)
        snd.play()
        return True
    except Exception as e:
        print(f"Preview voice effect error: {e}")
        try:
            from utils.audio_player import play_audio_file
            play_audio_file(target_path)
            return True
        except Exception:
            return False

