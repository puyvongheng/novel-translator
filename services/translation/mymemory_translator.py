"""
MyMemory Translation Engine
Provides free translation using MyMemory API with language code normalization.
"""

from deep_translator import MyMemoryTranslator

class MyMemoryTranslatorEngine:
    """
    MyMemory Free Translation Service:
    - Normalizes ISO language codes to country locales (e.g. km -> km-KH, zh -> zh-CN)
    - Free community translation memory database
    """
    def __init__(self):
        self.lang_map = {
            "km": "km-KH",
            "khmer": "km-KH",
            "zh": "zh-CN",
            "zh-cn": "zh-CN",
            "zh-tw": "zh-TW",
            "en": "en-US",
            "auto": "zh-CN"
        }

    def translate(self, text: str, source_lang: str = "auto", target_lang: str = "km") -> str:
        """
        Translates text with MyMemory translator.
        """
        if not text or not text.strip():
            return text

        s = self.lang_map.get(source_lang.lower(), source_lang)
        t = self.lang_map.get(target_lang.lower(), target_lang)

        try:
            trans = MyMemoryTranslator(source=s, target=t)
            res = trans.translate(text.strip())
            return res if res else text
        except Exception as e:
            print(f"MyMemory translation error: {e}")
            return text

_default_mymemory = MyMemoryTranslatorEngine()

def translate_mymemory(text: str, source_lang: str = "auto", target_lang: str = "km") -> str:
    return _default_mymemory.translate(text, source_lang=source_lang, target_lang=target_lang)
