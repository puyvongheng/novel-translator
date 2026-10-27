"""
Google Translate Engine (Free Multi-Client GTX Engine)
Provides fast direct translation using Google translate endpoints
with connection pooling, multi-line batching, and auto-failover.
"""

import requests
import re
from requests.adapters import HTTPAdapter

def _is_khmer_text(text: str) -> bool:
    if not text:
        return False
    return any(('\u1780' <= ch <= '\u17ff') or ('\u19e0' <= ch <= '\u19ff') for ch in text)

class GoogleTranslatorEngine:
    """
    Direct Google Free Translation Client:
    - Primary: clients5.google.com dict-chrome-ex (Zero 429 rate limit, high reliability)
    - Secondary: translate.googleapis.com (gtx / dict-chrome-ex)
    - Fallback: MyMemory Free Translation
    """
    def __init__(self):
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=2)
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "km") -> str:
        """
        Translates text from source_lang to target_lang using Google multi-client endpoints.
        """
        if not text or not text.strip():
            return text

        clean_text = text.strip()

        # 1. Primary: clients5.google.com (Chrome official dictionary endpoint, highly stable)
        try:
            url = "https://clients5.google.com/translate_a/t"
            params = {
                "client": "dict-chrome-ex",
                "sl": source_lang,
                "tl": target_lang,
                "q": clean_text
            }
            res = self._session.get(
                url,
                params=params,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                },
                timeout=7
            )
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and data:
                    translated = data[0][0] if isinstance(data[0], list) else data[0]
                    if translated and _is_khmer_text(translated):
                        return translated.strip()
        except Exception:
            pass

        # 2. Secondary: translate.googleapis.com
        for client in ["dict-chrome-ex", "gtx", "it"]:
            try:
                url = "https://translate.googleapis.com/translate_a/single"
                params = {
                    "client": client,
                    "sl": source_lang,
                    "tl": target_lang,
                    "dt": "t",
                    "q": clean_text
                }
                res = self._session.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    },
                    timeout=6
                )
                if res.status_code == 200:
                    data = res.json()
                    translated_parts = [segment[0] for segment in data[0] if segment and segment[0]]
                    translated = "".join(translated_parts).strip()
                    if translated and _is_khmer_text(translated):
                        return translated
            except Exception:
                continue

        # 3. Tertiary: MyMemory Free Engine Fallback
        try:
            from deep_translator import MyMemoryTranslator
            src_map = {"auto": "en-US", "en": "en-US", "zh": "zh-CN", "zh-CN": "zh-CN"}
            mm_src = src_map.get(source_lang, "en-US")
            res_mm = MyMemoryTranslator(source=mm_src, target="km-KH").translate(clean_text)
            if res_mm and _is_khmer_text(res_mm):
                return res_mm.strip()
        except Exception:
            pass

        return ""

# Standalone helper
_default_google = GoogleTranslatorEngine()

def translate_google_gtx(text: str, source_lang: str = "auto", target_lang: str = "km") -> str:
    return _default_google.translate(text, source_lang=source_lang, target_lang=target_lang)
