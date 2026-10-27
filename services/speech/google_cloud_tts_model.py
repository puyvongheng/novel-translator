"""
Google Cloud Text-to-Speech Model
Synthesizes speech using Google Cloud TTS API for Khmer (km-KH-Standard-A, km-KH-Standard-B),
with resilient automatic fallback to Google Translate Speech engine.
"""

import base64
import os
import urllib.parse
import requests

class GoogleCloudTTSModel:
    """
    Google Cloud Text-to-Speech Engine:
    - Official km-KH-Standard-A (Female) and km-KH-Standard-B (Male) voices
    - Direct Cloud REST API support with API key
    - Automatic free fallback via Google Translate TTS endpoint when API key is not present
    """
    def __init__(self, api_key: str = "", default_voice: str = "km-KH-Standard-A"):
        self.api_key = api_key or os.environ.get("GOOGLE_TTS_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        self.default_voice = default_voice

    def resolve_voice(self, voice_choice: str) -> str:
        if not voice_choice:
            return self.default_voice
        if "Standard-B" in voice_choice or "ប្រុស" in voice_choice:
            return "km-KH-Standard-B"
        return "km-KH-Standard-A"

    def generate_speech(
        self,
        text: str,
        output_path: str,
        voice_name: str = None,
        rate: str = "+0%",
        api_key: str = None
    ) -> bool:
        """
        Synthesizes text into an MP3 file using Google Cloud TTS or fallback.
        """
        if not text or not text.strip():
            return False

        key = api_key or self.api_key
        v_name = self.resolve_voice(voice_name)
        gender = "MALE" if "Standard-B" in v_name else "FEMALE"

        # Method 1: Google Cloud Text-to-Speech REST API (if key provided)
        if key:
            try:
                url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={key}"
                # Parse rate percentage into speakingRate (0.25 to 4.0)
                speed_float = 1.0
                try:
                    cleaned = rate.replace("%", "").replace("+", "").strip()
                    if cleaned:
                        speed_float = max(0.5, min(2.0, 1.0 + float(cleaned) / 100.0))
                except Exception:
                    speed_float = 1.0

                payload = {
                    "input": {"text": text.strip()},
                    "voice": {
                        "languageCode": "km-KH",
                        "name": v_name,
                        "ssmlGender": gender
                    },
                    "audioConfig": {
                        "audioEncoding": "MP3",
                        "speakingRate": speed_float
                    }
                }
                resp = requests.post(url, json=payload, timeout=25)
                if resp.status_code == 200:
                    data = resp.json()
                    audio_b64 = data.get("audioContent", "")
                    if audio_b64:
                        with open(output_path, "wb") as f_out:
                            f_out.write(base64.b64decode(audio_b64))
                        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                            return True
            except Exception as e:
                print(f"Google Cloud TTS API error: {e}, attempting fallback...")

        # Method 2: Resilient Google Translate TTS Fallback for Khmer
        try:
            encoded_text = urllib.parse.quote(text.strip()[:200])
            fallback_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl=km&total=1&idx=0&textlen={len(text)}&client=tw-ob"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            res = requests.get(fallback_url, headers=headers, timeout=20)
            if res.status_code == 200 and len(res.content) > 100:
                with open(output_path, "wb") as f_out:
                    f_out.write(res.content)
                return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Google Translate TTS fallback error: {e}")

        return False

# Standalone helper function
def generate_google_cloud_tts(
    text: str,
    output_path: str,
    voice_name: str = "km-KH-Standard-A"
) -> bool:
    model = GoogleCloudTTSModel()
    return model.generate_speech(text, output_path, voice_name=voice_name)
