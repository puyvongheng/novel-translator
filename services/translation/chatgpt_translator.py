"""
OpenAI ChatGPT Translation Engine
Translates dialogues using OpenAI Chat Completions (gpt-4o-mini, gpt-4o).
"""

import os
import requests
from requests.adapters import HTTPAdapter

class ChatGPTTranslatorEngine:
    """
    OpenAI ChatGPT Translation Client:
    - High accuracy conversational translation
    - Tailored dubbing style prompting
    """
    def __init__(self, api_key: str = "", model_name: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model_name = model_name
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=1)
        self._session.mount('https://', adapter)

    def _build_prompt(self, text: str, style: str = "📖 ធម្មតា (Standard)") -> str:
        style_lower = (style or "").lower()
        if "comedy" in style_lower or "កំប្លែង" in (style or ""):
            style_instruction = (
                "You are an expert Cambodian movie dubbing comedian. "
                "Translate this movie dialogue into vibrant, hilarious, and natural conversational Khmer (ភាសាខ្មែរ)."
            )
        elif "wuxia" in style_lower or "បុរាណ" in (style or "") or "ក្បាច់គុន" in (style or ""):
            style_instruction = (
                "You are an expert ancient Chinese martial arts drama voice dubber. "
                "Translate this dialogue into ancient royal/wuxia Khmer phrasing (ម្ចាស់បង, ទូលបង្គំ, អាចារ្យ...). "
                "Make it epic and dramatic."
            )
        else:
            style_instruction = (
                "You are a professional movie subtitle translator. "
                "Translate this subtitle dialogue into natural conversational Khmer (ភាសាខ្មែរ)."
            )

        return (
            f"{style_instruction}\n"
            "CRITICAL: Output ONLY the translated Khmer text without quotation marks or bullet points.\n\n"
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
        Translates text with OpenAI ChatGPT.
        """
        if not text or not text.strip():
            return text

        key = api_key or self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not key:
            return ""

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        prompt = self._build_prompt(text, style=style)
        temp = 0.55 if ("comedy" in (style or "").lower() or "កំប្លែង" in (style or "")) else 0.3
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temp
        }

        try:
            res = self._session.post(url, json=payload, headers=headers, timeout=14)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"ChatGPT translation error: {e}")

        return ""

def translate_chatgpt(
    text: str,
    source_lang: str = "auto",
    target_lang: str = "km",
    style: str = "📖 ធម្មតា (Standard)",
    api_key: str = None
) -> str:
    engine = ChatGPTTranslatorEngine(api_key=api_key)
    return engine.translate(text, source_lang=source_lang, target_lang=target_lang, style=style)
