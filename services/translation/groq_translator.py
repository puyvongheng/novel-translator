"""
Groq Translation Engine
Ultra-fast inference using Groq LPU cloud (LLaMA 3.1, Mixtral, Gemma 2).
Ideal for batch subtitle translation with low latency.
"""

import os
import requests
from requests.adapters import HTTPAdapter

# Groq supported models for translation
GROQ_MODELS = {
    "LLaMA 3.3 70B (Groq Fast)": "llama-3.3-70b-versatile",
    "LLaMA 3.1 8B (Groq Ultra Fast)": "llama-3.1-8b-instant",
    "Gemma 2 9B (Groq)": "gemma2-9b-it",
    "Mixtral 8x7B (Groq)": "mixtral-8x7b-32768",
}
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class GroqTranslatorEngine:
    """
    Groq LPU Inference Translation Engine:
    - Ultra-fast cloud LLM inference (10-100x faster than OpenAI)
    - Supports LLaMA 3.3, Gemma 2, Mixtral
    - Tailored Khmer movie dubbing prompts
    """

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.model_name = model_name or DEFAULT_GROQ_MODEL
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
        self._session.mount("https://", adapter)

    def _build_prompt(self, text: str, style: str = "📖 ធម្មតា (Standard)") -> str:
        style_lower = (style or "").lower()
        if "comedy" in style_lower or "កំប្លែង" in (style or ""):
            instruction = (
                "You are an elite Cambodian movie voice dubbing comedian. "
                "Translate this movie dialogue into vibrant, hilarious, natural conversational Khmer (ភាសាខ្មែរ)."
            )
        elif "wuxia" in style_lower or "បុរាណ" in (style or "") or "ក្បាច់គុន" in (style or ""):
            instruction = (
                "You are an expert ancient Chinese martial arts drama Khmer voice dubber. "
                "Translate into ancient royal Khmer phrasing (ម្ចាស់បង, ទូលបង្គំ, អាចារ្យ...). Make it epic."
            )
        else:
            instruction = (
                "You are a professional movie subtitle translator. "
                "Translate the subtitle into accurate, natural conversational Khmer (ភាសាខ្មែរ)."
            )
        return (
            f"{instruction}\n"
            "CRITICAL: Output ONLY the translated Khmer text. "
            "No English, no quotation marks, no bullet points.\n\n"
            f"Subtitle: {text.strip()}"
        )

    def translate(
        self,
        text: str,
        source_lang: str = "auto",
        target_lang: str = "km",
        style: str = "📖 ធម្មតា (Standard)",
        api_key: str = None,
    ) -> str:
        """Translates text using Groq LPU cloud inference."""
        if not text or not text.strip():
            return text

        key = api_key or self.api_key or os.environ.get("GROQ_API_KEY", "")
        if not key:
            return ""

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": self._build_prompt(text, style)}],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            res = self._session.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"[Groq] Error {res.status_code}: {res.text[:200]}")
        except Exception as e:
            print(f"[Groq] Translation error: {e}")
        return ""


def translate_groq(
    text: str,
    source_lang: str = "auto",
    target_lang: str = "km",
    style: str = "📖 ធម្មតា (Standard)",
    api_key: str = None,
    model_name: str = "",
) -> str:
    engine = GroqTranslatorEngine(api_key=api_key, model_name=model_name)
    return engine.translate(text, source_lang=source_lang, target_lang=target_lang, style=style)
