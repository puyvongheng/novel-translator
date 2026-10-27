"""
NVIDIA NIM Translation Engine
Uses NVIDIA AI Endpoints (build.nvidia.com) with LLaMA 3.1, Mistral-NeMo, etc.
Powered by NVIDIA GPU cloud inference.
"""

import os
import requests
from requests.adapters import HTTPAdapter

# NVIDIA NIM available models for translation
NVIDIA_MODELS = {
    "LLaMA 3.1 70B (NVIDIA)": "meta/llama-3.1-70b-instruct",
    "LLaMA 3.1 8B (NVIDIA Fast)": "meta/llama-3.1-8b-instruct",
    "Mistral NeMo 12B (NVIDIA)": "mistralai/mistral-nemo-12b-instruct",
    "Mixtral 8x22B (NVIDIA)": "mistralai/mixtral-8x22b-instruct-v0.1",
    "Nemotron 70B (NVIDIA)": "nvidia/llama-3.1-nemotron-70b-instruct",
    "Qwen 2.5 72B (NVIDIA)": "qwen/qwen2.5-72b-instruct",
}
DEFAULT_NVIDIA_MODEL = "meta/llama-3.1-70b-instruct"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NvidiaTranslatorEngine:
    """
    NVIDIA NIM (Neural Inference Microservice) Translation Engine:
    - NVIDIA GPU-accelerated AI inference
    - Supports LLaMA 3.1, Mistral NeMo, Nemotron, Qwen 2.5
    - OpenAI-compatible API format
    - Tailored Khmer movie dubbing prompts
    """

    def __init__(self, api_key: str = "", model_name: str = ""):
        self.api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
        self.model_name = model_name or DEFAULT_NVIDIA_MODEL
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
        """Translates text using NVIDIA NIM GPU cloud inference."""
        if not text or not text.strip():
            return text

        key = api_key or self.api_key or os.environ.get("NVIDIA_API_KEY", "")
        if not key:
            return ""

        url = f"{NVIDIA_BASE_URL}/chat/completions"
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
            res = self._session.post(url, json=payload, headers=headers, timeout=20)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"[NVIDIA NIM] Error {res.status_code}: {res.text[:200]}")
        except Exception as e:
            print(f"[NVIDIA NIM] Translation error: {e}")
        return ""


def translate_nvidia(
    text: str,
    source_lang: str = "auto",
    target_lang: str = "km",
    style: str = "📖 ធម្មតា (Standard)",
    api_key: str = None,
    model_name: str = "",
) -> str:
    engine = NvidiaTranslatorEngine(api_key=api_key, model_name=model_name)
    return engine.translate(text, source_lang=source_lang, target_lang=target_lang, style=style)
