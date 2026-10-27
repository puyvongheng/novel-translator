import json
import os
import time
import re
import urllib.parse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from deep_translator import MyMemoryTranslator
from services.translation.google_translator import GoogleTranslatorEngine
from services.translation.gemini_translator import GeminiTranslatorEngine
from services.translation.chatgpt_translator import ChatGPTTranslatorEngine
from services.translation.mymemory_translator import MyMemoryTranslatorEngine
from services.translation.groq_translator import GroqTranslatorEngine
from services.translation.openrouter_translator import OpenRouterTranslatorEngine
from services.translation.nvidia_translator import NvidiaTranslatorEngine

# Auto-load .env API keys if present
def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if v and not os.environ.get(k):
                        os.environ[k] = v
_load_env()

def is_khmer_text(text: str) -> bool:
    """Checks whether the string contains Khmer Unicode characters"""
    if not text:
        return False
    return any(('\u1780' <= ch <= '\u17ff') or ('\u19e0' <= ch <= '\u19ff') for ch in text)

class TranslationService:
    """
    High-Performance Translation Service supporting:
    1. Free Google Translate (Direct GTX Engine with Connection Pooling & Multiline Batching)
    2. Multi-threaded Parallel Subtitle Translation (Ultra-Fast for 3000+ CC lines)
    3. Free MyMemory Translator (Automatic failover)
    4. Custom OpenAI ChatGPT (API Key)
    5. Custom Google Gemini AI (API Key)
    6. Groq LPU Fast Inference (LLaMA 3.3, Mixtral, Gemma 2)
    7. OpenRouter Multi-Model Router (Claude, GPT-4o, Llama, Mistral, Gemini...)
    8. NVIDIA NIM GPU Cloud Inference (LLaMA 3.1, Mistral NeMo, Nemotron)
    """
    def __init__(self, provider: str = "Google (Free / មិនអស់លុយ)", api_key: str = "", model_name: str = "", style: str = "📖 ធម្មតា (Standard)"):
        self.provider = provider
        self.api_key = api_key.strip()
        self.model_name = model_name
        self.style = style
        self.google_engine = GoogleTranslatorEngine()
        self.gemini_engine = GeminiTranslatorEngine(api_key=self.api_key, model_name=self.model_name or "gemini-2.0-flash")
        self.chatgpt_engine = ChatGPTTranslatorEngine(api_key=self.api_key, model_name=self.model_name or "gpt-4o-mini")
        self.mymemory_engine = MyMemoryTranslatorEngine()
        self.groq_engine = GroqTranslatorEngine(api_key=self.api_key or os.environ.get("GROQ_API_KEY", ""), model_name=self.model_name)
        self.openrouter_engine = OpenRouterTranslatorEngine(api_key=self.api_key or os.environ.get("OPENROUTER_API_KEY", ""), model_name=self.model_name)
        self.nvidia_engine = NvidiaTranslatorEngine(api_key=self.api_key or os.environ.get("NVIDIA_API_KEY", ""), model_name=self.model_name)
        self._init_session()

    def _init_session(self):
        """Initializes reusable pooled HTTP session for minimum latency and zero TLS handshake overhead"""
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=2)
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)

    def set_style(self, style: str):
        self.style = style or "📖 ធម្មតា (Standard)"

    def set_provider(self, provider: str, api_key: str = "", style: str = ""):
        self.provider = provider
        # Re-read .env keys so switching provider at runtime picks up stored keys
        _load_env()
        # Prefer explicitly passed key, else fall back to env vars per provider
        if api_key and api_key.strip():
            self.api_key = api_key.strip()
        elif "Groq" in provider:
            self.api_key = os.environ.get("GROQ_API_KEY", "")
        elif "OpenRouter" in provider:
            self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        elif "NVIDIA" in provider:
            self.api_key = os.environ.get("NVIDIA_API_KEY", "")
        elif "Gemini" in provider:
            self.api_key = os.environ.get("GEMINI_API_KEY", "")
        elif "OpenAI" in provider:
            self.api_key = os.environ.get("OPENAI_API_KEY", "")
        else:
            self.api_key = api_key.strip()
        if style:
            self.style = style
        # Propagate resolved key to all engine instances
        self.groq_engine.api_key = os.environ.get("GROQ_API_KEY", "") or self.api_key
        self.openrouter_engine.api_key = os.environ.get("OPENROUTER_API_KEY", "") or self.api_key
        self.nvidia_engine.api_key = os.environ.get("NVIDIA_API_KEY", "") or self.api_key
        self.gemini_engine.api_key = os.environ.get("GEMINI_API_KEY", "") or self.api_key
        self.chatgpt_engine.api_key = os.environ.get("OPENAI_API_KEY", "") or self.api_key


    def _get_ai_prompt(self, text: str) -> str:
        """Approach 1: Custom Tone/Style Prompts for Gemini & OpenAI"""
        style_lower = (self.style or "").lower()
        if "comedy" in style_lower or "កំប្លែង" in (self.style or ""):
            style_instruction = (
                "You are an elite Cambodian movie voice dubbing comedian (អ្នកបញ្ចូលសំឡេងរឿងកំប្លែងល្បីៗ). "
                "Translate this movie dialogue into vibrant, hilarious, and natural conversational Khmer (ភាសាខ្មែរ). "
                "Use witty movie dubbing punchlines, expressive comedy slang (e.g. ញាក់សាច់, វីវរធំហើយលោកអើយ, ចង់បែកក្បាលមែនហ្អី, អាអូនកុំចង់ខ្លាំង, ឡូយមែនទែន) "
                "while keeping the dialogue meaningful and funny."
            )
        elif "wuxia" in style_lower or "បុរាណ" in (self.style or "") or "ក្បាច់គុន" in (self.style or ""):
            style_instruction = (
                "You are an expert ancient Chinese and martial arts drama Khmer voice dubber (អ្នកបញ្ចូលសំឡេងរឿងភាគបុរាណចិន/ក្បាច់គុន). "
                "Translate this dialogue into ancient royal/wuxia Khmer phrasing (using terms like ម្ចាស់បង, ទូលបង្គំ, អាចារ្យ, ហ៊ានប្រមាថ, គំនុំសងសឹក, ក្បាច់គុន...). "
                "Make it epic, dramatic, and respectful."
            )
        elif "natural" in style_lower or "ធម្មជាតិ" in (self.style or ""):
            style_instruction = (
                "You are a professional cinema voice dubbing artist. "
                "Translate this movie dialogue into smooth, natural, and emotionally expressive conversational Khmer."
            )
        else:
            # Default Standard: No comedy injected, accurate and direct
            style_instruction = (
                "You are a professional movie subtitle translator. "
                "Translate the following movie subtitle dialogue into accurate, natural conversational Khmer (ភាសាខ្មែរ)."
            )

        return (
            f"{style_instruction}\n"
            "CRITICAL: Output ONLY the translated Khmer text. "
            "Do NOT include English, pronunciation notes, quotation marks, or markdown bullet points.\n\n"
            f"Subtitle: {text}"
        )

    def _apply_style_postprocessing(self, khmer_text: str) -> str:
        """Approach 2: Post-processing vocabulary & tone filter for Google Free / MyMemory translations"""
        if not khmer_text or not self.style:
            return khmer_text
        style_lower = (self.style or "").lower()

        # If default: វាមិនប្រើទេធម្មតា (leave 100% untouched)
        if "ធម្មតា" in (self.style or "") or "standard" in style_lower:
            return khmer_text

        if "comedy" in style_lower or "កំប្លែង" in (self.style or ""):
            return self._apply_khmer_comedy_enhancer(khmer_text)
        elif "wuxia" in style_lower or "បុរាណ" in (self.style or "") or "ក្បាច់គុន" in (self.style or ""):
            return self._apply_khmer_wuxia_enhancer(khmer_text)
        elif "natural" in style_lower or "ធម្មជាតិ" in (self.style or ""):
            return self._apply_khmer_natural_enhancer(khmer_text)
        return khmer_text

    def _apply_khmer_comedy_enhancer(self, text: str) -> str:
        """Approach 2: Enhances stiff literal Google machine translations into vibrant, comedic Khmer movie dubbing phrasing"""
        if not text:
            return text

        replacements = [
            ("តើអ្នកកំពុងធ្វើអ្វី", "ឯងចង់ធ្វើស្អីហ្នឹង?!"),
            ("អ្នកកំពុងធ្វើអ្វី", "ឯងចង់ធ្វើស្អីហ្នឹង?!"),
            ("តើអ្នកជាអ្នកណា", "ឯងជាអាមុខខ្មោចណាគេ?!"),
            ("អ្នកជាអ្នកណា", "ឯងជាអាមុខខ្មោចណាគេ?!"),
            ("តើអ្នកចង់ស្លាប់មែនទេ", "ចង់បែកក្បាលមែនហ្អី?!"),
            ("អ្នកចង់ស្លាប់មែនទេ", "ចង់បែកក្បាលមែនហ្អី?!"),
            ("ចង់ស្លាប់មែនទេ", "ចង់បែកក្បាលមែនហ្អី?!"),
            ("តើអ្នកឆ្កួតមែនទេ", "សរសៃប្រសាទមែនហ្អី?!"),
            ("អ្នកឆ្កួតមែនទេ", "សរសៃប្រសាទមែនហ្អី?!"),
            ("តើវាជាអ្វី", "ស្អីគេហ្នឹង?!"),
            ("តើមានរឿងអ្វីកើតឡើង", "មានរឿងស្អីកើតឡើងហ្នឹង?!"),
            ("មានរឿងអ្វីកើតឡើង", "មានរឿងស្អីកើតឡើងហ្នឹង?!"),
            ("តើអ្នកដឹងទេ", "ឯងដឹងអត់?!"),
            ("តើពិតមែនទេ", "មែនទែនហ្នឹង?!"),
            ("ពិតមែនទេ", "មែនទែនហ្នឹង?!"),
            ("វាមិនល្អទេ", "វីវរធំហើយលោកអើយ!"),
            ("មិនល្អទេ", "វីវរធំហើយលោកអើយ!"),
            ("ខ្ញុំនឹងសម្លាប់អ្នក", "កុំចង់រស់ឱ្យសោះវ៉ើយ!"),
            ("សម្លាប់វាទៅ", "កម្ទេចវាឱ្យបែកក្បាលទៅ!"),
            ("វាមិនអាចទៅរួចទេ", "មិនជឿដាច់ខាត! មិនគួរឱ្យជឿសោះ!"),
            ("មិនអាចទៅរួចទេ", "មិនជឿដាច់ខាត! មិនគួរឱ្យជឿសោះ!"),
            ("ពិតជាអស្ចារ្យណាស់", "ញាក់សាច់ហ្មង!"),
            ("អស្ចារ្យណាស់", "ញាក់សាច់ហ្មង!"),
            ("ទៅឱ្យឆ្ងាយ", "ចេញឱ្យឆ្ងាយភ្លាមទៅវ៉ើយ!"),
            ("ទៅឆ្ងាយទៅ", "ចេញឱ្យឆ្ងាយភ្លាមទៅវ៉ើយ!"),
            ("រត់ទៅ", "រត់យកប្រាសអាយូសទៅ!"),
            ("រត់លឿនឡើង", "រត់យកប្រាសអាយូសឱ្យលឿនឡើង!"),
            ("ជួយខ្ញុំផង", "ជួយផងលោកអើយ!"),
            ("ជួយផង", "ជួយផងលោកអើយ!"),
            ("ពិតជាគួរឱ្យអស់សំណើចណាស់", "កំប្លែងញាក់សាច់ហ្មង!"),
            ("គួរឱ្យអស់សំណើចណាស់", "កំប្លែងញាក់សាច់ហ្មង!"),
            ("អ្នកខ្លាំងណាស់", "ឡូយមែនទែន!"),
            ("កុំមកជិតខ្ញុំ", "កុំមកជិតខ្ញុំប្រយ័ត្នបែកក្បាល!"),
            ("ឆាប់ឡើង", "ឆាប់ឡើងៗ លឿនម៉េស!"),
            ("រង់ចាំខ្ញុំផង", "ចាំខ្ញុំផងវ៉ើយ!"),
            ("ចាំខ្ញុំផង", "ចាំខ្ញុំផងវ៉ើយ!"),
            ("កុំបារម្ភ", "កុំភ័យ កុំបារម្ភអី!"),
            ("ខ្ញុំមិនដឹងទេ", "ខ្ញុំដឹងស្អីទៅ!"),
            ("ខ្ញុំសុំទោស", "សុំទោសផងលោកបង!"),
            ("អ្នកឯង", "ឯង"),
            ("កុំនិយាយមិនសមហេតុផល", "កុំមកនិយាយកុហកភូតភរ!"),
        ]
        result = text
        for pat, rep in replacements:
            result = result.replace(pat, rep)
        return result

    def _apply_khmer_wuxia_enhancer(self, text: str) -> str:
        """Wuxia/Ancient drama martial arts dialogue enhancer"""
        if not text:
            return text
        replacements = [
            ("បងប្រុស", "ម្ចាស់បង"),
            ("ប្អូនស្រី", "ម្ចាស់ប្អូន"),
            ("លោកគ្រូ", "លោកគ្រូអាចារ្យ"),
            ("សុំទោស", "ទូលបង្គំសូមអភ័យទោស"),
            ("អរគុណ", "អរព្រះគុណ"),
            ("ព្រះរាជា", "ព្រះចៅអធិរាជ"),
            ("សម្លាប់", "កម្ចាត់ចោល"),
            ("សងសឹក", "សងគំនុំឈាម"),
            ("ប្រយុទ្ធ", "ប្រយុទ្ធក្បាច់គុន"),
            ("ចៅហ្វាយ", "លោកម្ចាស់"),
        ]
        result = text
        for pat, rep in replacements:
            result = result.replace(pat, rep)
        return result

    def _apply_khmer_natural_enhancer(self, text: str) -> str:
        """Smooths literal machine translated pronouns into conversational drama Khmer"""
        if not text:
            return text
        replacements = [
            ("តើអ្នក", "អ្នក"),
            ("តើខ្ញុំ", "ខ្ញុំ"),
            ("មិនអីទេ", "គ្មានបញ្ហាទេ"),
            ("តើពិតទេ", "ពិតមែនអ្ហ៎"),
        ]
        result = text
        for pat, rep in replacements:
            result = result.replace(pat, rep)
        return result

    def translate_text(self, text: str, source_lang: str = "zh", target_lang: str = "km") -> str:
        """Translates a single line of text with fallback cascade"""
        text = text.strip()
        if not text:
            return ""

        # Normalize source language with Chinese movie optimization
        is_chinese = bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', text))
        if source_lang in ["auto", "Auto Detect"]:
            src = "zh-CN" if is_chinese else "auto"
        elif source_lang in ["zh", "Chinese", "zh-CN", "zh-TW", "ចិន"]:
            src = "zh-CN"
        else:
            src = source_lang
        tgt = "km" if target_lang in ["km", "Khmer", "ភាសាខ្មែរ"] else target_lang

        # 1. Custom OpenAI API (if configured)
        if "OpenAI" in self.provider and self.api_key:
            res = self.chatgpt_engine.translate(text, src, tgt, style=self.style, api_key=self.api_key)
            if res:
                return res
            return self._apply_style_postprocessing(self.google_engine.translate(text, src, tgt))

        # 2. Custom Gemini AI API (if configured)
        if "Gemini" in self.provider:
            res = self.gemini_engine.translate(text, src, tgt, style=self.style, api_key=self.api_key)
            if res:
                return res
            return self._apply_style_postprocessing(self.google_engine.translate(text, src, tgt))

        # 3. Groq LPU Fast Inference
        if "Groq" in self.provider:
            key = self.api_key or os.environ.get("GROQ_API_KEY", "")
            res = self.groq_engine.translate(text, src, tgt, style=self.style, api_key=key)
            if res:
                return res
            return self._apply_style_postprocessing(self.google_engine.translate(text, src, tgt))

        # 4. OpenRouter Multi-Model Router
        if "OpenRouter" in self.provider:
            key = self.api_key or os.environ.get("OPENROUTER_API_KEY", "")
            res = self.openrouter_engine.translate(text, src, tgt, style=self.style, api_key=key)
            if res:
                return res
            return self._apply_style_postprocessing(self.google_engine.translate(text, src, tgt))

        # 5. NVIDIA NIM GPU Cloud Inference
        if "NVIDIA" in self.provider:
            key = self.api_key or os.environ.get("NVIDIA_API_KEY", "")
            res = self.nvidia_engine.translate(text, src, tgt, style=self.style, api_key=key)
            if res:
                return res
            return self._apply_style_postprocessing(self.google_engine.translate(text, src, tgt))

        # 6. MyMemory Free Translator
        if "MyMemory" in self.provider:
            res = self.mymemory_engine.translate(text, src, tgt)
            return self._apply_style_postprocessing(res)

        # 7. Default: High-reliability Google Multi-Client Free Engine (dict-chrome-ex, it, gtx)
        res = self.google_engine.translate(text, src, tgt)
        return self._apply_style_postprocessing(res)

    def translate_batch(self, texts: list, source_lang: str = "zh", target_lang: str = "km") -> list:
        """
        Translates a batch of sentences in a single fast HTTP call with multiline bundling.
        Falls back to parallel single-line requests if line counts differ or batch fails.
        """
        if not texts:
            return []

        clean_texts = [t.strip().replace("\n", " ") for t in texts]

        # If custom AI API configured, map line-by-line or prompt
        if ("OpenAI" in self.provider or "Gemini" in self.provider
                or "Groq" in self.provider or "OpenRouter" in self.provider
                or "NVIDIA" in self.provider) and (self.api_key
                or os.environ.get("GROQ_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("NVIDIA_API_KEY")):
            with ThreadPoolExecutor(max_workers=min(len(clean_texts), 6)) as ex:
                return list(ex.map(lambda t: self.translate_text(t, source_lang, target_lang), clean_texts))

        # Normalize languages
        is_any_chinese = any(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf]', t) for t in clean_texts[:5])
        if source_lang in ["auto", "Auto Detect"]:
            src = "zh-CN" if is_any_chinese else "auto"
        elif source_lang in ["zh", "Chinese", "zh-CN", "zh-TW", "ចិន"]:
            src = "zh-CN"
        else:
            src = source_lang
        tgt = "km" if target_lang in ["km", "Khmer", "ភាសាខ្មែរ"] else target_lang

        # 1. Try fast newline-delimited batch with clients5.google.com (Highest reliability)
        combined = "\n".join(clean_texts)
        try:
            url = "https://clients5.google.com/translate_a/t"
            params = {"client": "dict-chrome-ex", "sl": src, "tl": tgt, "q": combined}
            res = self._session.get(url, params=params, timeout=8)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and data:
                    full_trans = data[0][0] if isinstance(data[0], list) else data[0]
                    parts = [p.strip() for p in full_trans.split("\n")]
                    if len(parts) == len(clean_texts):
                        return [self._apply_style_postprocessing(p) for p in parts]
        except Exception:
            pass

        # 2. Try translate.googleapis.com
        for client in ["dict-chrome-ex", "it", "gtx"]:
            try:
                url = "https://translate.googleapis.com/translate_a/single"
                params = {
                    "client": client,
                    "sl": src,
                    "tl": tgt,
                    "dt": "t",
                    "q": combined
                }
                res = self._session.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    },
                    timeout=8
                )
                if res.status_code == 200:
                    data = res.json()
                    translated_parts = [segment[0] for segment in data[0] if segment and segment[0]]
                    full_trans = "".join(translated_parts)
                    parts = [p.strip() for p in full_trans.split("\n")]
                    if len(parts) == len(clean_texts):
                        return [self._apply_style_postprocessing(p) for p in parts]
            except Exception:
                continue

        # 2. Parallel fallback using pooled worker threads
        def _translate_item(t):
            return self.translate_text(t, source_lang=source_lang, target_lang=target_lang)

        with ThreadPoolExecutor(max_workers=min(len(clean_texts), 8)) as executor:
            return list(executor.map(_translate_item, clean_texts))

    def translate_subtitles_parallel(
        self,
        subtitles: list,
        source_lang: str = "auto",
        target_lang: str = "km",
        batch_size: int = 15,
        max_workers: int = 16,
        progress_callback=None,
        check_cancel=None
    ) -> int:
        """
        Ultra-fast parallel batch translator for CC / subtitles:
        Translates thousands of subtitle lines in seconds using concurrent worker threads
        and multiline batching with real-time status updates.
        """
        # Find items that need translation
        items_to_translate = []
        for s in subtitles:
            orig = s.get("original", "").strip()
            tr = s.get("translated", "").strip()
            if orig and (not tr or not is_khmer_text(tr)):
                items_to_translate.append(s)

        total = len(items_to_translate)
        if total == 0:
            if progress_callback:
                progress_callback("✅ គ្រប់បន្ទាត់ CC ទាំងអស់ត្រូវបានបកប្រែរួចរាល់!", 1.0)
            return 0

        # Chunk items into batches
        batches = [items_to_translate[i:i + batch_size] for i in range(0, total, batch_size)]
        total_batches = len(batches)

        completed_count = 0
        counter_lock = threading.Lock()

        def process_batch(batch_items):
            nonlocal completed_count
            if check_cancel and check_cancel():
                return

            orig_texts = [b.get("original", "").strip() for b in batch_items]
            try:
                translated_texts = self.translate_batch(orig_texts, source_lang=source_lang, target_lang=target_lang)
            except Exception:
                translated_texts = []

            is_target_km = target_lang in ["km", "Khmer", "ភាសាខ្មែរ"]
            for i, item in enumerate(batch_items):
                orig = item.get("original", "").strip()
                km = translated_texts[i].strip() if i < len(translated_texts) else ""
                # If batch failed to produce Khmer text for a line, try individual translate fallback
                if is_target_km and orig and (not km or not is_khmer_text(km)):
                    try:
                        km = self.translate_text(orig, source_lang=source_lang, target_lang=target_lang).strip()
                    except Exception:
                        pass
                if km:
                    item["translated"] = km

            with counter_lock:
                completed_count += len(batch_items)
                curr_done = min(completed_count, total)
                pct = 0.10 + (0.85 * (curr_done / total))
                if progress_callback and not (check_cancel and check_cancel()):
                    progress_callback(
                        f"⚡ កំពុងបកប្រែ CC: {curr_done}/{total}... ({pct*100:.0f}%)",
                        pct
                    )

        # Execute batches concurrently with thread pool
        actual_workers = min(max_workers, max(4, total_batches))
        with ThreadPoolExecutor(max_workers=actual_workers) as executor:
            futures = [executor.submit(process_batch, b) for b in batches]
            for f in as_completed(futures):
                if check_cancel and check_cancel():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    f.result()
                except Exception:
                    pass

        if progress_callback and not (check_cancel and check_cancel()):
            progress_callback(f"✅ បានបកប្រែ CC ជោគជ័យទាំងអស់ ({total} បន្ទាត់)! (Turbo 100x Speed)", 1.0)

        return total

    def _translate_with_google(self, text: str, src: str, tgt: str) -> str:
        """Direct Google Multi-Client translator endpoint (dict-chrome-ex, it, gtx) with MyMemory & Gemini fallback"""
        for client in ["dict-chrome-ex", "it", "gtx"]:
            try:
                url = "https://translate.googleapis.com/translate_a/single"
                params = {
                    "client": client,
                    "sl": src,
                    "tl": tgt,
                    "dt": "t",
                    "q": text
                }
                res = self._session.get(
                    url,
                    params=params,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    },
                    timeout=8
                )
                if res.status_code == 200:
                    data = res.json()
                    translated_parts = [segment[0] for segment in data[0] if segment and segment[0]]
                    translated = "".join(translated_parts).strip()
                    if translated:
                        return translated
            except Exception:
                continue

        # Fallback 1: MyMemory Translator with proper country locale codes
        try:
            res = self._translate_with_mymemory(text, src, tgt)
            if res and res != text:
                return res
        except Exception:
            pass

        # Fallback 2: Gemini API if key is present in config
        try:
            from config import GEMINI_API_KEY
            if GEMINI_API_KEY:
                saved_key = self.api_key
                self.api_key = GEMINI_API_KEY
                gemini_res = self._translate_with_gemini(text, src, tgt)
                self.api_key = saved_key
                if gemini_res and gemini_res != text:
                    return gemini_res
        except Exception:
            pass

        return text

    def _translate_with_google_gtx(self, text: str, src: str, tgt: str) -> str:
        """Backward compatibility alias for _translate_with_google"""
        return self._translate_with_google(text, src, tgt)

    def _translate_with_mymemory(self, text: str, src: str, tgt: str) -> str:
        """Translates text with MyMemory translator, normalizing language codes (e.g. km-KH, zh-CN)"""
        try:
            # Map simple ISO 639-1 language codes to MyMemory required format
            lang_map = {
                "km": "km-KH",
                "khmer": "km-KH",
                "zh": "zh-CN",
                "zh-cn": "zh-CN",
                "zh-tw": "zh-TW",
                "en": "en-US",
                "auto": "zh-CN"
            }
            s = lang_map.get(src.lower(), src)
            t = lang_map.get(tgt.lower(), tgt)
            trans = MyMemoryTranslator(source=s, target=t)
            res = trans.translate(text)
            return res if res else text
        except Exception:
            return text

    def _translate_with_openai(self, text: str, src: str, tgt: str) -> str:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            prompt = self._get_ai_prompt(text)
            temp = 0.55 if ("comedy" in (self.style or "").lower() or "កំប្លែង" in (self.style or "")) else 0.3
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temp
            }
            res = self._session.post(url, json=payload, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return self._apply_style_postprocessing(self._translate_with_google_gtx(text, src, tgt))
        except Exception:
            return self._apply_style_postprocessing(self._translate_with_google_gtx(text, src, tgt))

    GEMINI_MODELS = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-flash-latest"
    ]

    def _translate_with_gemini(self, text: str, src: str, tgt: str) -> str:
        """Translates movie subtitle into natural Khmer using Gemini AI with model auto-fallback"""
        if not hasattr(self, "_active_gemini_model") or not self._active_gemini_model:
            self._active_gemini_model = "gemini-3.5-flash"

        headers = {"Content-Type": "application/json"}
        prompt = self._get_ai_prompt(text)
        temp = 0.55 if ("comedy" in (self.style or "").lower() or "កំប្លែង" in (self.style or "")) else 0.3
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": temp
            }
        }

        # Try current active model first, then fall back to candidate models
        models_to_try = [self._active_gemini_model] + [m for m in self.GEMINI_MODELS if m != self._active_gemini_model]

        for model_name in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
                res = self._session.post(url, json=payload, headers=headers, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"].strip()
                            clean_text = raw_text.replace("*", "").replace('"', '').strip()
                            lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
                            if lines:
                                self._active_gemini_model = model_name
                                return lines[0]
                elif res.status_code == 404:
                    continue
            except Exception:
                continue

        # If all Gemini models fail or timeout, fall back to Google GTX Free Engine with style postprocessing
        return self._apply_style_postprocessing(self._translate_with_google_gtx(text, src, tgt))
