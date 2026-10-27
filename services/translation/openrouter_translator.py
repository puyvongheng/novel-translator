"""
OpenRouter Translation Engine
Routes to 200+ AI models (Claude 3.5, GPT-4o, Llama 3.3, Mistral, Gemini Pro, etc.)
via a single unified OpenAI-compatible API endpoint.
"""

import os
import requests
from requests.adapters import HTTPAdapter

# Popular OpenRouter models for translation quality
OPENROUTER_MODELS = {
    "Claude 3.5 Haiku (Fast)": "anthropic/claude-3-5-haiku",
    "Claude 3.5 Sonnet": "anthropic/claude-3-5-sonnet",
    "GPT-4o Mini (OpenAI)": "openai/gpt-4o-mini",
    "GPT-4o (OpenAI)": "openai/gpt-4o",
    "LLaMA 3.3 70B (Free)": "meta-llama/llama-3.3-70b-instruct:free",
    "Mistral 7B (Free)": "mistralai/mistral-7b-instruct:free",
    "Gemini 2.0 Flash": "google/gemini-2.0-flash-exp:free",
    "Qwen 2.5 72B": "qwen/qwen-2.5-72b-instruct",
}
DEFAULT_OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct:free"


class OpenRouterTranslatorEngine:
    """
    OpenRouter Multi-Model Translation Engine:
    - Access 200+ AI models with one API key
    - OpenAI-compatible API format
    - Includes free-tier models (Llama 3.3, Mistral 7B, Gemini 2.0 Flash)
    - Tailored Khmer movie dubbing prompts
    """

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.model_name = model_name or DEFAULT_OPENROUTER_MODEL
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
        """Translates text using OpenRouter multi-model routing."""
        if not text or not text.strip():
            return text

        key = api_key or self.api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            return ""

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://khmer-movie-studio.app",
            "X-Title": "AI Khmer Movie Studio",
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": self._build_prompt(text, style)}],
            "temperature": 0.3,
            "max_tokens": 512,
        }

        try:
            res = self._session.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"[OpenRouter] Error {res.status_code}: {res.text[:200]}")
        except Exception as e:
            print(f"[OpenRouter] Translation error: {e}")
        return ""


def translate_openrouter(
    text: str,
    source_lang: str = "auto",
    target_lang: str = "km",
    style: str = "📖 ធម្មតា (Standard)",
    api_key: str = None,
    model_name: str = "",
) -> str:
    engine = OpenRouterTranslatorEngine(api_key=api_key, model_name=model_name)
    return engine.translate(text, source_lang=source_lang, target_lang=target_lang, style=style)
