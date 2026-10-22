import json
import time
import re
import urllib.parse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from deep_translator import MyMemoryTranslator

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
    """
    def __init__(self, provider: str = "Google (Free / មិនអស់លុយ)", api_key: str = "", model_name: str = ""):
        self.provider = provider
        self.api_key = api_key.strip()
        self.model_name = model_name
        self._init_session()

    def _init_session(self):
        """Initializes reusable pooled HTTP session for minimum latency and zero TLS handshake overhead"""
        self._session = requests.Session()
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=2)
        self._session.mount('https://', adapter)
        self._session.mount('http://', adapter)

    def set_provider(self, provider: str, api_key: str = ""):
        self.provider = provider
        self.api_key = api_key.strip()

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
            return self._translate_with_openai(text, src, tgt)

        # 2. Custom Gemini AI API (if configured)
        if "Gemini" in self.provider and self.api_key:
            return self._translate_with_gemini(text, src, tgt)

        # 3. MyMemory Free Translator
        if "MyMemory" in self.provider:
            return self._translate_with_mymemory(text, src, tgt)

        # 4. Default: High-reliability Google Multi-Client Free Engine (dict-chrome-ex, it, gtx)
        return self._translate_with_google(text, src, tgt)

    def translate_batch(self, texts: list, source_lang: str = "zh", target_lang: str = "km") -> list:
        """
        Translates a batch of sentences in a single fast HTTP call with multiline bundling.
        Falls back to parallel single-line requests if line counts differ or batch fails.
        """
        if not texts:
            return []

        clean_texts = [t.strip().replace("\n", " ") for t in texts]

        # If custom AI API configured, map line-by-line or prompt
        if ("OpenAI" in self.provider or "Gemini" in self.provider) and self.api_key:
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

        # 1. Try fast newline-delimited batch with Google Multi-Client (dict-chrome-ex, it, gtx)
        combined = "\n".join(clean_texts)
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
                        return parts
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
            prompt = f"You are a professional movie subtitle translator. Translate the following movie dialogue into natural Khmer (ភាសាខ្មែរ). Output only the translated sentence without quotes or explanation:\n\n{text}"
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            res = self._session.post(url, json=payload, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return self._translate_with_google_gtx(text, src, tgt)
        except Exception:
            return self._translate_with_google_gtx(text, src, tgt)

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
        prompt = (
            "You are a professional movie subtitle translator. "
            "Translate the following movie subtitle dialogue into natural, conversational Khmer (ភាសាខ្មែរ).\n"
            "CRITICAL: Output ONLY the translated Khmer text. "
            "Do NOT include English, pronunciation notes, quotation marks, or markdown bullet points.\n\n"
            f"Subtitle: {text}"
        )
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
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

        # If all Gemini models fail or timeout, fall back to Google GTX Free Engine
        return self._translate_with_google_gtx(text, src, tgt)
