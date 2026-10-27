"""
Google Gemini 2.0 AI Audio Speech Model
Synthesizes speech using Google DeepMind Gemini 2.0 native audio generation API.
Supports dynamic voice personas, emotional tones, and automatic conversion to MP3.
"""

import base64
import os
import subprocess
import requests

GEMINI_VOICE_MAP = {
    "piseth": "Puck",
    "sreymom": "Aoede",
    "borey": "Fenrir",
    "puck": "Puck",
    "aoede": "Aoede",
    "kore": "Kore",
    "fenrir": "Fenrir",
    "charon": "Charon"
}

class GeminiTTSModel:
    """
    Google Gemini 2.0 AI Audio Voice Synthesis Engine:
    - Native AI audio generation directly from Gemini models
    - Realistic human intonation, acting personas, and emotions
    """
    def __init__(self, api_key: str = "", model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model

    def resolve_gemini_voice(self, voice_choice: str) -> str:
        """Maps Khmer UI voice label to valid Gemini prebuilt voice name"""
        if not voice_choice:
            return "Puck"
        v_low = voice_choice.lower()
        if "sreymom" in v_low or "ស្រី" in v_low:
            return "Aoede"
        elif "borey" in v_low or "action" in v_low:
            return "Fenrir"
        elif "piseth" in v_low or "ប្រុស" in v_low:
            return "Puck"
        for k, v in GEMINI_VOICE_MAP.items():
            if k in v_low:
                return v
        return "Puck"

    def generate_speech(
        self,
        text: str,
        output_path: str,
        voice_name: str = "Puck",
        api_key: str = None,
        model: str = None,
        persona: str = "",
        emotion: str = ""
    ) -> bool:
        """
        Synthesizes text into an audio file using Gemini 2.0 Flash Audio API.
        """
        if not text or not text.strip():
            return False

        key = api_key or self.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            try:
                from config import GEMINI_API_KEY
                key = GEMINI_API_KEY
            except Exception:
                pass

        if not key:
            print("Gemini TTS Error: No GEMINI_API_KEY available.")
            return False

        m_name = (model or self.model).split()[0].strip()
        v_name = self.resolve_gemini_voice(voice_name)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={key}"

        p_desc = f"Voice Persona: {persona}." if persona else ""
        e_desc = f"Emotional Tone: {emotion}." if emotion else ""
        system_instruction = f"{p_desc} {e_desc}".strip()
        full_prompt = f"{system_instruction}\n\nRead the following text out loud clearly in natural authentic voice:\n{text.strip()}".strip()

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
            resp = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=45
            )
            if resp.status_code != 200:
                print(f"Gemini TTS API returned status {resp.status_code}: {resp.text[:250]}")
                return False

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                print("Gemini TTS: No candidates returned in API response")
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

                        # Convert to target format using ffmpeg
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
            print(f"Gemini TTS generation error: {e}")
            return False

# Standalone helper function
def generate_gemini_tts(
    text: str,
    output_path: str,
    voice_name: str = "Puck",
    api_key: str = None
) -> bool:
    model = GeminiTTSModel(api_key=api_key)
    return model.generate_speech(text, output_path, voice_name=voice_name)
