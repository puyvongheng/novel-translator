import os
import sys

# Ensure FFmpeg binary directory is accessible in PATH across entire application
try:
    import imageio_ffmpeg
    _ff_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if _ff_exe and os.path.exists(_ff_exe):
        _ff_dir = os.path.dirname(_ff_exe)
        _std_ffmpeg = os.path.join(_ff_dir, "ffmpeg.exe")
        if not os.path.exists(_std_ffmpeg):
            import shutil
            shutil.copyfile(_ff_exe, _std_ffmpeg)
        if _ff_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = _ff_dir + os.path.pathsep + os.environ.get("PATH", "")
except Exception:
    pass

import tkinter as tk
from tkinter import font

# Base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Audio / TTS Voices for Khmer
KHMER_VOICES = {
    "Piseth (Male / ប្រុស)": "km-KH-PisethNeural",
    "Sreymom (Female / ស្រី)": "km-KH-SreymomNeural"
}

# Expanded Voices and Personas for Text-to-Speech & Voice Studio
VOICE_PROFILES = {
    # --- 🇰🇭 KHMER AI VOICES ---
    "Piseth - ធម្មជាតិ (Natural Male)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Khmer",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "សំឡេងបុរសខ្មែរធម្មជាតិ ច្បាស់ រលូន"
    },
    "Sreymom - ធម្មជាតិ (Natural Female)": {
        "voice": "km-KH-SreymomNeural", "lang": "km", "gender": "ស្រី / Female", "category": "Khmer",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "សំឡេងស្ត្រីខ្មែរធម្មជាតិ ទន់ភ្លន់ ពីរោះ"
    },
    "Piseth - រឿងនិទាន & ភាពយន្ត (Deep Movie Narrator)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Khmer",
        "pitch": "-15Hz", "rate": "+0%", "effect": "cinema_bass",
        "desc": "សំឡេងបាសធ្ងន់ អធិប្បាយរឿងភាពយន្ត និងរឿងព្រេង"
    },
    "Piseth - អានព័ត៌មានផ្លូវការ (Official News Anchor)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Khmer",
        "pitch": "-5Hz", "rate": "+10%", "effect": "radio_warmth",
        "desc": "សំឡេងអ្នកអានព័ត៌មានទូរទស្សន៍ផ្លូវការ ច្បាស់ៗ"
    },
    "Sreymom - រឿងនិទានស្រទន់ (Soft Storyteller / AudioBook)": {
        "voice": "km-KH-SreymomNeural", "lang": "km", "gender": "ស្រី / Female", "category": "Khmer",
        "pitch": "-5Hz", "rate": "-5%", "effect": "soft_whisper",
        "desc": "សំឡេងអានសៀវភៅ ឬរឿងនិទានមុនចូលគេង ស្រទន់"
    },
    "Sreymom - ពិធីការិនីពាណិជ្ជកម្ម (Commercial & Promo Host)": {
        "voice": "km-KH-SreymomNeural", "lang": "km", "gender": "ស្រី / Female", "category": "Khmer",
        "pitch": "+10Hz", "rate": "+15%", "effect": "radio_warmth",
        "desc": "សំឡេងរស់រវើក សម្រាប់ផ្សាយពាណិជ្ជកម្ម និង TikTok"
    },
    "Piseth - វីរបុរសល្បឿនលឿន (Action Hero Male)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Khmer",
        "pitch": "-10Hz", "rate": "+20%", "effect": "cinema_bass",
        "desc": "សំឡេងតួអង្គវីរបុរស ក្លៀវក្លា លឿនរហ័ស"
    },
    "Piseth - តាចាស់ / ព្រឹទ្ធាចារ្យ (Old Wise Master)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Khmer",
        "pitch": "-30Hz", "rate": "-15%", "effect": "vintage",
        "desc": "សំឡេងគ្រូគុន ឬតាចាស់បុរាណ យឺត និងធ្ងន់"
    },
    "Sreymom - ក្មេង / តុក្កតា (Cute Youth / Anime Girl)": {
        "voice": "km-KH-SreymomNeural", "lang": "km", "gender": "ស្រី / Female", "category": "Khmer",
        "pitch": "+35Hz", "rate": "+10%", "effect": "none",
        "desc": "សំឡេងតុក្កតា ក្មេងស្រី គួរឱ្យស្រលាញ់"
    },
    "Piseth - មនុស្សយន្ត AI (Robot Sci-Fi)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "មនុស្សយន្ត", "category": "Khmer",
        "pitch": "+0Hz", "rate": "+0%", "effect": "robot",
        "desc": "សំឡេងមនុស្សយន្តបែបវិទ្យាសាស្ត្រ Metallic"
    },

    # --- 🧬 CLONED PERSONAS ---
    "✨ [CLONE] Cinema Movie Narrator (Deep Baritone)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Clone",
        "pitch": "-20Hz", "rate": "-5%", "effect": "cinema_bass", "is_clone": True,
        "clone_params": {"pitch_scale": 0.88, "formant": "preserved", "bass_gain": 8, "treble_gain": 2},
        "desc": "សំឡេង Clone បាសធ្ងន់បំផុត កម្រិតភាពយន្តហូលីវូដ"
    },
    "✨ [CLONE] Anime Heroine (Cute & High Pitch)": {
        "voice": "km-KH-SreymomNeural", "lang": "km", "gender": "ស្រី / Female", "category": "Clone",
        "pitch": "+30Hz", "rate": "+10%", "effect": "none", "is_clone": True,
        "clone_params": {"pitch_scale": 1.25, "formant": "shifted", "bass_gain": -3, "treble_gain": 6},
        "desc": "សំឡេង Clone តុក្កតាជប៉ុន ស្រួយស្រទន់"
    },
    "✨ [CLONE] Radio Broadcast DJ (Warm Air)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Clone",
        "pitch": "-8Hz", "rate": "+5%", "effect": "radio_warmth", "is_clone": True,
        "clone_params": {"pitch_scale": 0.94, "formant": "preserved", "bass_gain": 6, "treble_gain": 4},
        "desc": "សំឡេង Clone ពិធីករវិទ្យុ FM ដ៏ទាក់ទាញ"
    },
    "✨ [CLONE] Vintage Film Voice (1960s Classic)": {
        "voice": "km-KH-PisethNeural", "lang": "km", "gender": "ប្រុស / Male", "category": "Clone",
        "pitch": "-15Hz", "rate": "-10%", "effect": "telephone", "is_clone": True,
        "clone_params": {"pitch_scale": 0.90, "formant": "shifted", "bass_gain": 4, "treble_gain": -4},
        "desc": "សំឡេង Clone បែបកុនសម័យដើម"
    },

    # --- 🌐 MULTILINGUAL & INTERNATIONAL ---
    "🇺🇸 Brian - Multilingual Deep Male": {
        "voice": "en-US-BrianMultilingualNeural", "lang": "en", "gender": "Male", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "US Deep Male Natural Voice"
    },
    "🇺🇸 Emma - Multilingual Female": {
        "voice": "en-US-EmmaMultilingualNeural", "lang": "en", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "US Expressive Natural Female Voice"
    },
    "🇺🇸 Andrew - Warm Storyteller": {
        "voice": "en-US-AndrewMultilingualNeural", "lang": "en", "gender": "Male", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "US Warm Storyteller Voice"
    },
    "🇺🇸 Ava - Expressive Female": {
        "voice": "en-US-AvaMultilingualNeural", "lang": "en", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "US Expressive Female Voice"
    },
    "🇬🇧 Ryan - British Male": {
        "voice": "en-GB-RyanNeural", "lang": "en-GB", "gender": "Male", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "British Accent Male Voice"
    },
    "🇬🇧 Sonia - British Female": {
        "voice": "en-GB-SoniaNeural", "lang": "en-GB", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "British Accent Female Voice"
    },
    "🇨🇳 Xiaoxiao - Chinese Female": {
        "voice": "zh-CN-XiaoxiaoNeural", "lang": "zh", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "Chinese Mandarin Warm Female"
    },
    "🇨🇳 Yunxi - Chinese Male": {
        "voice": "zh-CN-YunxiNeural", "lang": "zh", "gender": "Male", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "Chinese Mandarin Lively Male"
    },
    "🇯🇵 Nanami - Japanese Female": {
        "voice": "ja-JP-NanamiNeural", "lang": "ja", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "Japanese Sweet Female Voice"
    },
    "🇹🇭 Premwadee - Thai Female": {
        "voice": "th-TH-PremwadeeNeural", "lang": "th", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "Thai Natural Female Voice"
    },
    "🇻🇳 HoaiMy - Vietnamese Female": {
        "voice": "vi-VN-HoaiMyNeural", "lang": "vi", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "Vietnamese Expressive Female"
    },
    "🇫🇷 Denise - French Female": {
        "voice": "fr-FR-DeniseNeural", "lang": "fr", "gender": "Female", "category": "Multilingual",
        "pitch": "+0Hz", "rate": "+0%", "effect": "none",
        "desc": "French Natural Female Voice"
    }
}

# Voice Audio Effects Presets
VOICE_EFFECTS = {
    "None (ធម្មជាតិ / Natural)": "none",
    "Cinema Bass Boost (បាសធ្ងន់បែបភាពយន្ត)": "cinema_bass",
    "Broadcast Radio Warmth (វិទ្យុទន់ភ្លន់)": "radio_warmth",
    "Studio Reverb / Hall (សាលប្រជុំ / បន្ទរ)": "reverb_hall",
    "Telephone / Vintage (ទូរស័ព្ទ / ឧបករណ៍បំពង)": "telephone",
    "Robot / Sci-Fi FX (មនុស្សយន្ត)": "robot",
    "Soft Whisper (ខ្សឹបតិចៗ)": "soft_whisper"
}

# Export Quality & Bitrates (Fast Direct MP3 and Lossless WAV)
AUDIO_EXPORT_QUALITIES = {
    "MP3 320 kbps (Studio Quality / ច្បាស់បំផុត)": {"ext": ".mp3", "bitrate": "320k", "acodec": "libmp3lame"},
    "MP3 192 kbps (High Quality / មធ្យម)": {"ext": ".mp3", "bitrate": "192k", "acodec": "libmp3lame"},
    "MP3 128 kbps (Compact / ស្រាល)": {"ext": ".mp3", "bitrate": "128k", "acodec": "libmp3lame"},
    "WAV 48kHz (Lossless Audio / ដើម)": {"ext": ".wav", "bitrate": None, "acodec": "pcm_s16le"},
}

# Sample Khmer text presets
KHMER_SAMPLE_TEXTS = {
    "🎬 សាច់រឿងភាពយន្ត (Movie Narration)": "នៅរាត្រីដ៏ស្ងប់ស្ងាត់មួយ ក្រោមពន្លឺព្រះចន្ទពេញបូណ៌មី វីរបុរសវ័យក្មេងបានបោះជំហានចូលទៅក្នុងព្រៃអាថ៌កំបាំង ដើម្បីស្វែងរកការពិតដែលត្រូវបានកប់ទុកជាយូរមកហើយ។",
    "📰 ព័ត៌មានទាន់ហេតុការណ៍ (Breaking News)": "សូមស្វាគមន៍មកកាន់ការផ្សាយព័ត៌មានពិសេស។ នៅថ្ងៃនេះ ក្រសួងព័ត៌មានបានប្រកាសដាក់ឱ្យប្រើប្រាស់ប្រព័ន្ធបញ្ញាសិប្បនិម្មិតថ្មី សម្រាប់ជួយសម្រួលដល់ការងារប្រចាំថ្ងៃរបស់ប្រជាពលរដ្ឋទូទាំងប្រទេស។",
    "🎙️ ស្ពតពាណិជ្ជកម្ម (Commercial Ad)": "តើអ្នកកំពុងស្វែងរកដំណោះស្រាយដ៏អស្ចារ្យសម្រាប់អាជីវកម្មរបស់អ្នកមែនទេ? សាកល្បងឥឡូវនេះជាមួយនឹងបច្ចេកវិទ្យាទំនើបចុងក្រោយគេ ដែលផ្តល់ទំនុកចិត្ត និងប្រសិទ្ធភាពខ្ពស់បំផុត!",
    "📖 រឿងនិទានកុមារ (Bedtime Story)": "កាលពីព្រេងនាយ មានកូនទន្សាយតូចមួយរស់នៅក្នុងព្រៃធំ។ វាតែងតែចូលចិត្តរត់លេង និងចែករំលែកផ្លែឈើឆ្ងាញ់ៗជាមួយមិត្តភក្តិទាំងអស់ដោយក្តីរីករាយ។"
}

# API Keys — loaded from .env file
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# Translation Providers
TRANSLATION_PROVIDERS = [
    "Google (Free / មិនអស់លុយ)",
    "Gemini / Google AI (API Key)",
    "OpenAI ChatGPT (API Key)",
    "⚡ Groq (LLaMA Fast)",
    "🌐 OpenRouter (Multi-Model)",
    "🖥️ NVIDIA NIM (LLaMA GPU)",
    "MyMemory (Free / មិនអស់លុយ)"
]

# Translation Styles / Tones (Voice Dubbing Style)
TRANSLATION_STYLES = [
    "📖 ធម្មតា (Standard)",
    "😂 កំប្លែង រស់រវើក (Comedy)",
    "⚔️ រឿងបុរាណ / ក្បាច់គុន (Wuxia)",
    "🎬 ភាពយន្តធម្មជាតិ (Natural Drama)"
]

# Whisper Model Sizes
WHISPER_MODELS = [
    "base (លឿនបំផុត Fast)",
    "tiny (ស្រាល Ultra-light)",
    "small (មធ្យម Balanced)",
    "medium (ច្បាស់ខ្ពស់ Accurate)"
]

# Subtitle Color Presets (ASS format BGR hex)
SUBTITLE_COLORS = {
    "White (ស)": "&H00FFFFFF",
    "Yellow (លឿង)": "&H0000FFFF",
    "Cyan Neon (ផ្ទៃមេឃ)": "&H00FFFF00",
    "Lime Green (បៃតងខ្ចី)": "&H0000FF00",
    "Hot Pink (ផ្កាឈូក)": "&H009948EC",
    "Orange Glow (ទឹកក្រូច)": "&H000080FF"
}

# CC Animation Presets (Popup, Karaoke Active Word, Fade, Slide, Bounce)
CC_ANIMATION_PRESETS = [
    "🎤 Karaoke (Active Word Highlight)",
    "✨ Popup / Pop-in (Zoom In)",
    "🌊 Fade In / Fade Out",
    "⬆️ Slide Up (ពីក្រោមឡើងលើ)",
    "🦘 Bounce (លោតតិចៗ TikTok)",
    "📝 Classic Static (ធម្មតា)"
]

# CC Background Box Styles
CC_BG_STYLES = {
    "None (គ្មានផ្ទៃក្រោយ)": {"type": "none", "color": "transparent", "ass_border": 1, "ass_box": "&H80000000"},
    "Black Box 50% (ប្រអប់ខ្មៅស្រាល)": {"type": "box", "color": "#181a20", "ass_border": 3, "ass_box": "&H80000000"},
    "Black Box 85% (ប្រអប់ខ្មៅដិត)": {"type": "box", "color": "#090a0f", "ass_border": 3, "ass_box": "&H20000000"},
    "Pill Dark Badge (ប្រអប់មូល)": {"type": "pill", "color": "#111827", "ass_border": 3, "ass_box": "&H30101010"},
    "Yellow Box / Black Text": {"type": "yellow_box", "color": "#facc15", "ass_border": 3, "ass_box": "&H0000D4FF"},
    "Neon Cyan Glow (ពន្លឺ Neon)": {"type": "neon_cyan", "color": "#082f49", "ass_border": 1, "ass_box": "&H00FFFF00"}
}

# CC Border Outlines
CC_BORDER_PRESETS = {
    "Medium Outline (3px)": 3,
    "Thick Outline (5px)": 5,
    "Thin Outline (1.5px)": 2,
    "No Outline (0px)": 0
}

# Karaoke / Active Word Highlight Colors
CC_HIGHLIGHT_COLORS = {
    "Gold / Yellow (លឿងទុំ)": {"hex": "#facc15", "ass": "&H0000E6FF"},
    "Neon Cyan (ផ្ទៃមេឃ)": {"hex": "#06b6d4", "ass": "&H00FFFF00"},
    "Lime Green (បៃតងខ្ចី)": {"hex": "#22c55e", "ass": "&H0022FF22"},
    "Hot Pink (ផ្កាឈូក)": {"hex": "#ec4899", "ass": "&H009948EC"},
    "Pure White (ពណ៌ស)": {"hex": "#ffffff", "ass": "&H00FFFFFF"}
}

# Standard Khmer Font Family for Windows UI
KHMER_FONT_FAMILY = "Kantumruy Pro"

# Speech Speed presets for Khmer Dubbing
SPEECH_SPEED_PRESETS = {
    "1.0x (Normal / ធម្មតា)": "+0%",
    "1.1x (+10%)": "+10%",
    "1.15x (+15%)": "+15%",
    "1.2x (+20% លឿនល្មម)": "+20%",
    "1.25x (+25%)": "+25%",
    "1.3x (+30% លឿន)": "+30%",
    "1.5x (+50% លឿនខ្លាំង)": "+50%",
    "0.9x (-10% យឺតបន្តិច)": "-10%",
    "0.8x (-20% យឺត)": "-20%"
}

# Video Player Preview Aspect Ratios & Formats
PREVIEW_ASPECT_RATIOS = {
    "Auto (Fit Original)": None,
    "16:9 Long Video (YouTube / Movie)": 16.0 / 9.0,
    "9:16 Short Video (TikTok / Reels / Shorts)": 9.0 / 16.0,
    "1:1 Square (Instagram / Post)": 1.0,
    "4:5 Portrait (Instagram Feed)": 4.0 / 5.0,
    "21:9 Ultrawide Cinema": 21.0 / 9.0,
    "Custom Resolution...": "custom"
}

# Export Resolutions (Support 16:9 Landscape Long Video, 9:16 TikTok Vertical, 1:1 Square)
EXPORT_RESOLUTIONS = {
    "Original (តាមវីដេអូដើម)": None,
    "1080p Long Video (Full HD 16:9 - 1920x1080)": (1920, 1080),
    "720p Long Video (HD 16:9 - 1280x720)": (1280, 720),
    "480p Fast Draft (SD 16:9 - 854x480 - សម្រាប់ Test លឿន)": (854, 480),
    "360p Ultra Fast (Draft - 640x360 - សម្រាប់ Test លឿនបំផុត)": (640, 360),
    "TikTok / Reels / Shorts (9:16 Vertical - 1080x1920)": (1080, 1920),
    "TikTok / Shorts 720p (9:16 Vertical - 720x1280)": (720, 1280),
    "TikTok Draft 480p (9:16 Vertical - 480x854 - សម្រាប់ Test)": (480, 854),
    "Square 1:1 (Instagram - 1080x1080)": (1080, 1080),
    "Portrait 4:5 (Instagram - 1080x1350)": (1080, 1350),
    "4K Ultra HD (16:9 - 3840x2160)": (3840, 2160)
}

# Export Frame Rates
EXPORT_FPS = {
    "30 FPS (Standard)": 30,
    "60 FPS (Ultra Smooth)": 60,
    "24 FPS (Cinema)": 24
}

# Export Formats & Codecs (H.265 CRF 26 as first choice for Data-Saving Uploads)
EXPORT_CODECS = {
    "MP4 + H.265 / HEVC (CRF 26) - សន្សំ Data Upload (Recommended)": {
        "codec": "hevc",
        "crf": "26",
        "ext": ".mp4",
        "desc": "សន្សំទំហំ 50% គុណភាពច្បាស់ល្អ សន្សំ Data Upload"
    },
    "MP4 + H.264 / AVC (CRF 22) - Standard ឆបគ្នាគ្រប់ Device": {
        "codec": "h264",
        "crf": "22",
        "ext": ".mp4",
        "desc": "ឆបគ្នា 100% លើគ្រប់ Device និង Web Browser"
    },
    "⚡ MP4 + H.264 Fast Test Draft (CRF 32) - Export លឿនបំផុតសម្រាប់ Test": {
        "codec": "h264",
        "crf": "32",
        "ext": ".mp4",
        "desc": "ទម្លាក់គុណភាព និងទំហំតូចបំផុត Export ក្នុងប៉ុន្មានវិនាទីសម្រាប់ Test"
    },
    "WebM + VP9 (CRF 24) - Web Streaming": {
        "codec": "vp9",
        "crf": "24",
        "ext": ".webm",
        "desc": "សម្រាប់ YouTube & Web Streaming"
    }
}

EXPORT_FORMATS = list(EXPORT_CODECS.keys())

# Export Quality / CRF
EXPORT_QUALITY = {
    "CRF 26 (សន្សំ Data Upload / គុណភាពច្បាស់ - Recommended)": "26",
    "⚡ Fast Draft / Test (CRF 32 - ទម្លាក់គុណភាព Export លឿនសម្រាប់ Test)": "32",
    "⚡ Ultra Fast Preview (CRF 36 - ស្រាលបំផុត លឿនបំផុតសម្រាប់ Test)": "36",
    "CRF 22 (Balanced / កម្រិតមធ្យម)": "22",
    "CRF 18 (Ultra High Quality / គុណភាពខ្ពស់)": "18"
}

# Watermark Positions
WATERMARK_POSITIONS = {
    "Top-Right (លើ ស្ដាំ)": "W-w-20:20",
    "Top-Left (លើ ឆ្វេង)": "20:20",
    "Bottom-Right (ក្រោម ស្ដាំ)": "W-w-20:H-h-20",
    "Bottom-Left (ក្រោម ឆ្វេង)": "20:H-h-20",
    "Center (កណ្ដាល)": "(W-w)/2:(H-h)/2",
    "Custom (អូសតាមចិត្ត / Drag & Drop)": None
}

_CACHED_KHMER_FONTS = None

def get_installed_khmer_fonts():
    """Detects and returns all Khmer & Unicode fonts installed on the computer"""
    global _CACHED_KHMER_FONTS
    if _CACHED_KHMER_FONTS and len(_CACHED_KHMER_FONTS) > 3:
        return _CACHED_KHMER_FONTS

    all_families = []
    try:
        if tk._default_root is None:
            _hidden = tk.Tk()
            _hidden.withdraw()
            all_families = sorted(list(set(font.families())))
            _hidden.destroy()
        else:
            all_families = sorted(list(set(font.families())))
    except Exception:
        try:
            all_families = sorted(list(set(font.families())))
        except Exception:
            all_families = []

    top_khmer = [
        "Kantumruy Pro",
        "Khmer OS Siemreap",
        "Khmer OS Battambang",
        "Khmer OS Content",
        "Khmer OS Bokor",
        "Khmer OS Muol Light",
        "Khmer UI",
        "Leelawadee UI",
        "Noto Sans Khmer",
        "DaunPenh",
        "MoolBoran",
        "Segoe UI"
    ]

    detected = []
    for f in all_families:
        cleaned = f.strip()
        if cleaned.startswith("!"):
            cleaned = cleaned[1:].strip()
        if any(k in f.lower() for k in ['khmer', 'kantumruy', 'leelawadee', 'daunpenh', 'moolboran', 'noto', 'segoe']):
            if cleaned not in detected:
                detected.append(cleaned)

    # Place top favorites first
    final_list = []
    for top in top_khmer:
        for d in detected:
            if top.lower() == d.lower() and d not in final_list:
                final_list.append(d)

    for d in detected:
        if d not in final_list:
            final_list.append(d)

    if not final_list:
        final_list = ["Leelawadee UI", "Segoe UI", "Arial"]
    else:
        _CACHED_KHMER_FONTS = final_list

    return final_list
