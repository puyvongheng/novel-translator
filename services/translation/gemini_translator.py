"""
Google Gemini AI Translation Engine
Translates dialogues using Google Gemini 2.0 / 1.5 Flash API with custom Khmer voice dubbing styling.
"""

import os
import requests
from requests.adapters import HTTPAdapter

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro"
]

class GeminiTranslatorEngine:
    """
    Google Gemini Translation Engine:
    - Contextual dialogue translation tailored to Cambodian cinema
    - Supports Comedy, Ancient Wuxia, Natural Drama, and Standard Khmer dubbing styles
    - Automatic multi-model candidate rotation
    """
    def __init__(self, api_key: str = "", model_name: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
        self._session.mount('https://', adapter)

    def _build_prompt(self, text: str, style: str = "📖 ធម្មតា (Standard)") -> str:
        style_lower = (style or "").lower()
        if "comedy" in style_lower or "កំប្លែង" in (style or ""):
            style_instruction = (
                "You are an elite Cambodian movie voice dubbing comedian (អ្នកបញ្ចូលសំឡេងរឿងកំប្លែងល្បីៗ). "
                "Translate this movie dialogue into vibrant, hilarious, and natural conversational Khmer (ភាសាខ្មែរ). "
                "Use witty movie dubbing punchlines and expressive comedy slang while keeping the dialogue natural."
            )
        elif "wuxia" in style_lower or "បុរាណ" in (style or "") or "ក្បាច់គុន" in (style or ""):
            style_instruction = (
                "You are an expert ancient Chinese and martial arts drama Khmer voice dubber (អ្នកបញ្ចូលសំឡេងរឿងភាគបុរាណចិន/ក្បាច់គុន). "
                "Translate this dialogue into ancient royal/wuxia Khmer phrasing (ម្ចាស់បង, ទូលបង្គំ, អាចារ្យ, ក្បាច់គុន...). "
                "Make it epic, dramatic, and respectful."
            )
        elif "natural" in style_lower or "ធម្មជាតិ" in (style or ""):
            style_instruction = (
                "You are a professional cinema voice dubbing artist. "
                "Translate this movie dialogue into smooth, natural, and emotionally expressive conversational Khmer."
            )
        else:
            style_instruction = (
                "You are a professional movie subtitle translator. "
                "Translate the following movie subtitle dialogue into accurate, natural conversational Khmer (ភាសាខ្មែរ)."
            )

        return (
            f"{style_instruction}\n"
            "CRITICAL: Output ONLY the translated Khmer text. "
            "Do NOT include English, pronunciation notes, quotation marks, or markdown bullet points.\n\n"
            f"Subtitle: {text.strip()}"
        )

    def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "km",
        style: str = "📖 ធម្មតា (Standard)",
        api_key: str = None
    ) -> str:
        """
        Translates text with Gemini API.
        """
        if not text or not text.strip():
            return text

        key = api_key or self.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            try:
                from config import GEMINI_API_KEY
                key = GEMINI_API_KEY
            except Exception:
                pass

        if not key:
            return ""

        headers = {"Content-Type": "application/json"}
        prompt = self._build_prompt(text, style=style)
        temp = 0.55 if ("comedy" in (style or "").lower() or "កំប្លែង" in (style or "")) else 0.3
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temp}
        }

        models_to_try = [self.model_name] + [m for m in GEMINI_MODELS if m != self.model_name]
        for model in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                res = self._session.post(url, json=payload, headers=headers, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"].strip()
                            clean = raw_text.replace("*", "").replace('"', '').strip()
                            lines = [ln.strip() for ln in clean.splitlines() if ln.strip()]
                            if lines:
                                return lines[0]
            except Exception:
                continue

        return ""

def translate_gemini(
    text: str,
    source_lang: str = "auto",
    target_lang: str = "km",
    style: str = "📖 ធម្មតា (Standard)",
    api_key: str = None
) -> str:
    engine = GeminiTranslatorEngine(api_key=api_key)
    return engine.translate(text, source_lang=source_lang, target_lang=target_lang, style=style)
