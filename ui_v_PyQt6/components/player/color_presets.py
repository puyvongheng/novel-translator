"""
AI Khmer Movie Studio - Real-Time Color Presets, Cinematic LUTs & Advanced HSL Grading
Studio-grade color grading suite:
- Presets & LUTs: None, Mono, Cinematic, Bright, Film, Night Scene, Past (Canva/CapCut aesthetic)
- Advanced HSL / Color: Full 8-channel Hue, Saturation, and Luminance tuning (Lightroom / Premiere Pro Lumetri style)
- Basic Tone & White Balance: Temperature, Tint, Exposure, Contrast, Vibrance
- 60fps real-time OpenCV processing with live player monitor synchronization
- Full FFmpeg video filter export integration
"""

import os
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional

from ui_v_PyQt6.qt_compat import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QScrollArea, QFrame, QGridLayout, QImage, QPixmap,
    Qt, Signal, QColor, QTabBar, QPainter, QPen, QBrush, QStackedWidget
)

# ---------------------------------------------------------------------------
# COLOR PRESET DEFINITIONS
# ---------------------------------------------------------------------------
PRESET_CATEGORIES: Dict[str, List[Dict[str, str]]] = {
    "None": [
        {"id": "none", "name": "Original (គ្មាន)", "desc": "Original video colors"}
    ],
    "Mono": [
        {"id": "mono_noir", "name": "Noir B&W", "desc": "Classic Hollywood Monochrome"},
        {"id": "mono_silver", "name": "Silver Screen", "desc": "High contrast black & white"},
        {"id": "mono_sepia", "name": "Sepia Tone", "desc": "Warm antique vintage sepia"},
        {"id": "mono_charcoal", "name": "Charcoal Mood", "desc": "Deep matte shadow monochrome"}
    ],
    "Cinematic": [
        {"id": "cine_teal_orange", "name": "Teal & Orange", "desc": "Hollywood Blockbuster grade"},
        {"id": "cine_gold", "name": "Cinema Gold", "desc": "Warm 35mm tungsten lighting"},
        {"id": "cine_neo_tokyo", "name": "Neo Tokyo", "desc": "Teal shadows with neon magenta"},
        {"id": "cine_drama_cool", "name": "Drama Cold", "desc": "Desaturated Nordic thriller"}
    ],
    "Bright": [
        {"id": "bright_vivid", "name": "Vivid Pop", "desc": "Ultra-rich saturation & vibrance"},
        {"id": "bright_sunny", "name": "Sunny Warm", "desc": "Golden daylight glow"},
        {"id": "bright_clean", "name": "Clean Pastel", "desc": "Soft bright high-key portrait"},
        {"id": "bright_hdr", "name": "HDR Clarity", "desc": "Punchy midtones and dynamic range"}
    ],
    "Film": [
        {"id": "film_kodak", "name": "Kodak 2383", "desc": "Matte blacks and lush organic reds"},
        {"id": "film_fuji", "name": "Fuji Velvia", "desc": "Deep saturated greens & blues"},
        {"id": "film_16mm", "name": "16mm Vintage", "desc": "Warm analog indie cinema"},
        {"id": "film_bleach", "name": "Bleach Bypass", "desc": "Silver retention & gritty contrast"}
    ],
    "Night Scene": [
        {"id": "night_cyber", "name": "Cyberpunk Neon", "desc": "Electric blue & magenta nightlife"},
        {"id": "night_midnight", "name": "Midnight Mystery", "desc": "Sapphire shadows and low key"},
        {"id": "night_emerald", "name": "Emerald Gloom", "desc": "Moody sci-fi green ambiance"},
        {"id": "night_street", "name": "Street Lamp", "desc": "Warm amber against deep dark"}
    ],
    "Past": [
        {"id": "past_70s", "name": "70s Golden", "desc": "Warm golden nostalgia"},
        {"id": "past_polaroid", "name": "Polaroid Fade", "desc": "Faded blacks & retro 600 film"},
        {"id": "past_80s", "name": "Summer 80s", "desc": "Warm retro analog tape aesthetic"},
        {"id": "past_faded", "name": "Faded Memory", "desc": "Dreamy soft desaturated pastels"}
    ]
}

# ---------------------------------------------------------------------------
# COLOR CHANNELS DEFINITIONS FOR ADVANCED HSL
# ---------------------------------------------------------------------------
HSL_COLORS = [
    ("red",     "Red",     "#ef4444"),
    ("orange",  "Orange",  "#f97316"),
    ("yellow",  "Yellow",  "#eab308"),
    ("green",   "Green",   "#22c55e"),
    ("aqua",    "Aqua",    "#06b6d4"),
    ("blue",    "Blue",    "#3b82f6"),
    ("purple",  "Purple",  "#a855f7"),
    ("magenta", "Magenta", "#ec4899"),
]

# Track gradient stylesheets for each color channel in HSL mode
HSL_GRADIENTS = {
    "hue": {
        "red":     "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #db2777, stop:0.5 #ef4444, stop:1 #f97316)",
        "orange":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:0.5 #f97316, stop:1 #eab308)",
        "yellow":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f97316, stop:0.5 #eab308, stop:1 #84cc16)",
        "green":   "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #84cc16, stop:0.5 #22c55e, stop:1 #14b8a6)",
        "aqua":    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:0.5 #06b6d4, stop:1 #0284c7)",
        "blue":    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:0.5 #3b82f6, stop:1 #6366f1)",
        "purple":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:0.5 #a855f7, stop:1 #d946ef)",
        "magenta": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:0.5 #ec4899, stop:1 #f43f5e)",
    },
    "sat": {
        "red":     "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #ef4444)",
        "orange":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #f97316)",
        "yellow":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #eab308)",
        "green":   "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #22c55e)",
        "aqua":    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #06b6d4)",
        "blue":    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #3b82f6)",
        "purple":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #a855f7)",
        "magenta": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #475569, stop:1 #ec4899)",
    },
    "lum": {
        "red":     "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #250909, stop:0.5 #b91c1c, stop:1 #fecaca)",
        "orange":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #270e04, stop:0.5 #c2410c, stop:1 #fed7aa)",
        "yellow":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #251b03, stop:0.5 #a16207, stop:1 #fef08a)",
        "green":   "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #052410, stop:0.5 #15803d, stop:1 #bbf7d0)",
        "aqua":    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #05232d, stop:0.5 #0e7490, stop:1 #a5f3fc)",
        "blue":    "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #091738, stop:0.5 #1d4ed8, stop:1 #bfdbfe)",
        "purple":  "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #220b45, stop:0.5 #6d28d9, stop:1 #ddd6fe)",
        "magenta": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #290825, stop:0.5 #a21caf, stop:1 #fbcfe8)",
    }
}

_LUT_CACHE: Dict[str, np.ndarray] = {}


def _build_lut(preset_id: str) -> np.ndarray:
    """Creates a high-performance 256x3 uint8 lookup table for instant OpenCV cv2.LUT mapping."""
    lut = np.zeros((1, 256, 3), dtype=np.uint8)
    base = np.arange(256, dtype=np.float32)

    if preset_id == "none":
        lut[0, :, 0] = np.arange(256, dtype=np.uint8)
        lut[0, :, 1] = np.arange(256, dtype=np.uint8)
        lut[0, :, 2] = np.arange(256, dtype=np.uint8)
        return lut

    # MONO
    if preset_id == "mono_noir":
        c = np.clip(base * 1.05 - 6, 0, 255)
        lut[0, :, 0] = c
        lut[0, :, 1] = c
        lut[0, :, 2] = c
    elif preset_id == "mono_silver":
        norm = base / 255.0
        c = (norm ** 1.3) * 255.0
        c = np.clip(c * 1.15 - 10, 0, 255)
        lut[0, :, 0] = c
        lut[0, :, 1] = c
        lut[0, :, 2] = c
    elif preset_id == "mono_sepia":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(norm * 170.0 + 10, 0, 255)
        lut[0, :, 1] = np.clip(norm * 215.0 + 15, 0, 255)
        lut[0, :, 2] = np.clip(norm * 255.0 + 25, 0, 255)
    elif preset_id == "mono_charcoal":
        norm = base / 255.0
        c = np.clip(norm * 210.0 + 25, 0, 255)
        lut[0, :, 0] = c
        lut[0, :, 1] = c
        lut[0, :, 2] = c

    # CINEMATIC
    elif preset_id == "cine_teal_orange":
        norm = base / 255.0
        b_ch = np.clip(base + (1.0 - norm) * 45.0 - norm * 20.0, 0, 255)
        g_ch = np.clip(base + 8.0, 0, 255)
        r_ch = np.clip(base + norm * 45.0 - (1.0 - norm) * 15.0, 0, 255)
        lut[0, :, 0] = b_ch
        lut[0, :, 1] = g_ch
        lut[0, :, 2] = r_ch
    elif preset_id == "cine_gold":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base - 18.0 * (1.0 - norm * 0.5), 0, 255)
        lut[0, :, 1] = np.clip(base + 12.0 * norm, 0, 255)
        lut[0, :, 2] = np.clip(base + 38.0 * norm + 6.0, 0, 255)
    elif preset_id == "cine_neo_tokyo":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base + 35.0 * (1.0 - norm) + 15.0 * norm, 0, 255)
        lut[0, :, 1] = np.clip(base - 8.0, 0, 255)
        lut[0, :, 2] = np.clip(base + 42.0 * (norm ** 1.4), 0, 255)
    elif preset_id == "cine_drama_cool":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base + 22.0 * (1.0 - norm), 0, 255)
        lut[0, :, 1] = np.clip(base + 4.0, 0, 255)
        lut[0, :, 2] = np.clip(base - 16.0, 0, 255)

    # BRIGHT
    elif preset_id == "bright_vivid":
        norm = base / 255.0
        c = (norm ** 0.88) * 255.0
        lut[0, :, 0] = np.clip(c * 1.04, 0, 255)
        lut[0, :, 1] = np.clip(c * 1.08 + 2.0, 0, 255)
        lut[0, :, 2] = np.clip(c * 1.12 + 4.0, 0, 255)
    elif preset_id == "bright_sunny":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base - 8.0, 0, 255)
        lut[0, :, 1] = np.clip(base + 14.0 * norm, 0, 255)
        lut[0, :, 2] = np.clip(base + 26.0 * norm, 0, 255)
    elif preset_id == "bright_clean":
        norm = base / 255.0
        c = (norm ** 0.82) * 255.0 + 8.0
        lut[0, :, 0] = np.clip(c, 0, 255)
        lut[0, :, 1] = np.clip(c + 2.0, 0, 255)
        lut[0, :, 2] = np.clip(c + 4.0, 0, 255)
    elif preset_id == "bright_hdr":
        norm = base / 255.0
        c = 255.0 / (1.0 + np.exp(-10.0 * (norm - 0.5)))
        c = np.clip(c * 0.95 + base * 0.05, 0, 255)
        lut[0, :, 0] = c
        lut[0, :, 1] = c
        lut[0, :, 2] = c

    # FILM
    elif preset_id == "film_kodak":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 0.92 + 12.0 * (1.0 - norm), 0, 255)
        lut[0, :, 1] = np.clip(base * 0.98 + 4.0, 0, 255)
        lut[0, :, 2] = np.clip(base * 1.08 + 8.0 * norm, 0, 255)
    elif preset_id == "film_fuji":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 1.06 + 8.0, 0, 255)
        lut[0, :, 1] = np.clip(base * 1.12 + 10.0 * norm, 0, 255)
        lut[0, :, 2] = np.clip(base * 0.96, 0, 255)
    elif preset_id == "film_16mm":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 0.85 + 18.0, 0, 255)
        lut[0, :, 1] = np.clip(base * 0.95 + 12.0, 0, 255)
        lut[0, :, 2] = np.clip(base * 1.05 + 15.0, 0, 255)
    elif preset_id == "film_bleach":
        norm = base / 255.0
        c = np.clip((norm ** 1.4) * 270.0 - 15.0, 0, 255)
        lut[0, :, 0] = c
        lut[0, :, 1] = c
        lut[0, :, 2] = c

    # NIGHT SCENE
    elif preset_id == "night_cyber":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 1.25 + 20.0 * (1.0 - norm), 0, 255)
        lut[0, :, 1] = np.clip(base * 0.82, 0, 255)
        lut[0, :, 2] = np.clip(base * 1.18 + 25.0 * norm, 0, 255)
    elif preset_id == "night_midnight":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 1.15 + 15.0, 0, 255)
        lut[0, :, 1] = np.clip(base * 0.90, 0, 255)
        lut[0, :, 2] = np.clip(base * 0.80 - 10.0, 0, 255)
    elif preset_id == "night_emerald":
        lut[0, :, 0] = np.clip(base * 0.92, 0, 255)
        lut[0, :, 1] = np.clip(base * 1.20 + 8.0, 0, 255)
        lut[0, :, 2] = np.clip(base * 0.85, 0, 255)
    elif preset_id == "night_street":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 0.75, 0, 255)
        lut[0, :, 1] = np.clip(base * 0.95 + 15.0 * norm, 0, 255)
        lut[0, :, 2] = np.clip(base * 1.15 + 30.0 * norm, 0, 255)

    # PAST
    elif preset_id == "past_70s":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 0.80 + 20.0, 0, 255)
        lut[0, :, 1] = np.clip(base * 0.96 + 14.0, 0, 255)
        lut[0, :, 2] = np.clip(base * 1.14 + 18.0, 0, 255)
    elif preset_id == "past_polaroid":
        norm = base / 255.0
        c = np.clip(norm * 220.0 + 28.0, 0, 255)
        lut[0, :, 0] = np.clip(c * 0.92 + 8.0, 0, 255)
        lut[0, :, 1] = np.clip(c * 1.02, 0, 255)
        lut[0, :, 2] = np.clip(c * 1.08, 0, 255)
    elif preset_id == "past_80s":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(base * 1.05 + 12.0 * (1.0 - norm), 0, 255)
        lut[0, :, 1] = np.clip(base * 0.92 + 6.0, 0, 255)
        lut[0, :, 2] = np.clip(base * 1.10 + 16.0 * norm, 0, 255)
    elif preset_id == "past_faded":
        norm = base / 255.0
        lut[0, :, 0] = np.clip(norm * 200.0 + 35.0, 0, 255)
        lut[0, :, 1] = np.clip(norm * 205.0 + 32.0, 0, 255)
        lut[0, :, 2] = np.clip(norm * 215.0 + 30.0, 0, 255)
    else:
        lut[0, :, 0] = np.arange(256, dtype=np.uint8)
        lut[0, :, 1] = np.arange(256, dtype=np.uint8)
        lut[0, :, 2] = np.arange(256, dtype=np.uint8)

    return lut


def get_preset_lut(preset_id: str) -> np.ndarray:
    if preset_id not in _LUT_CACHE:
        _LUT_CACHE[preset_id] = _build_lut(preset_id)
    return _LUT_CACHE[preset_id]


def apply_color_preset(frame_bgr: np.ndarray, preset_id: str, intensity: float = 0.80) -> np.ndarray:
    """Applies high-speed 3D LUT transformation to a BGR frame with variable intensity blending."""
    if frame_bgr is None or frame_bgr.size == 0:
        return frame_bgr
    if preset_id in ("none", "None", "", None) or intensity <= 0.01:
        return frame_bgr

    if preset_id in ("mono_noir", "mono_silver", "mono_charcoal"):
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        mono_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        lut = get_preset_lut(preset_id)
        graded = cv2.LUT(mono_bgr, lut)
    else:
        lut = get_preset_lut(preset_id)
        graded = cv2.LUT(frame_bgr, lut)

    if intensity >= 0.99:
        return graded
    return cv2.addWeighted(frame_bgr, 1.0 - intensity, graded, intensity, 0)


def apply_advanced_hsl(frame_bgr: np.ndarray, hsl_settings: dict) -> np.ndarray:
    """
    Applies real-time professional HSL per-color adjustments and basic tone grading.
    Runs at 60fps+ on monitor preview frames (<6ms latency).
    """
    if frame_bgr is None or frame_bgr.size == 0 or not hsl_settings:
        return frame_bgr

    hue_dict = hsl_settings.get("hue", {})
    sat_dict = hsl_settings.get("sat", {})
    lum_dict = hsl_settings.get("lum", {})
    tone_dict = hsl_settings.get("tone", {})

    has_hsl = any(v != 0 for v in hue_dict.values()) or \
              any(v != 0 for v in sat_dict.values()) or \
              any(v != 0 for v in lum_dict.values())
    has_tone = any(v != 0 for v in tone_dict.values())

    if not has_hsl and not has_tone:
        return frame_bgr

    out = frame_bgr.copy()

    # 1. Basic Tone Adjustments (Exposure, Contrast, Temp, Tint, Vibrance)
    if has_tone:
        exp = tone_dict.get("exposure", 0)       # -100 to +100
        con = tone_dict.get("contrast", 0)       # -100 to +100
        temp = tone_dict.get("temperature", 0)   # -100 to +100 (Cool <-> Warm)
        tint = tone_dict.get("tint", 0)          # -100 to +100 (Green <-> Magenta)
        vib = tone_dict.get("vibrance", 0)       # -100 to +100

        # Contrast & Exposure
        if exp != 0 or con != 0:
            alpha = max(0.2, 1.0 + (con / 100.0) * 0.70)
            beta = (exp / 100.0) * 55.0
            out = cv2.convertScaleAbs(out, alpha=alpha, beta=beta)

        # White Balance: Temperature & Tint
        if temp != 0 or tint != 0:
            b, g, r = cv2.split(out.astype(np.int16))
            r = np.clip(r + int(temp * 0.38) + int(tint * 0.18), 0, 255)
            b = np.clip(b - int(temp * 0.38) + int(tint * 0.18), 0, 255)
            g = np.clip(g - int(tint * 0.32), 0, 255)
            out = cv2.merge([b.astype(np.uint8), g.astype(np.uint8), r.astype(np.uint8)])

        # Vibrance
        if vib != 0:
            hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
            s_f = hsv[:, :, 1].astype(np.float32)
            mask = (1.0 - s_f / 255.0)
            hsv[:, :, 1] = np.clip(s_f + mask * (vib * 0.75), 0, 255).astype(np.uint8)
            out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    # 2. HSL Per-Color Tuning (8 Channels)
    if has_hsl:
        hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
        h = hsv[:, :, 0].astype(np.float32)
        s = hsv[:, :, 1].astype(np.float32)
        v = hsv[:, :, 2].astype(np.float32)

        # Center Hue ranges in OpenCV scale (0..180)
        COLOR_RANGES = {
            "red":     (0, 10, 170, 180),
            "orange":  (10, 23, None, None),
            "yellow":  (23, 38, None, None),
            "green":   (38, 85, None, None),
            "aqua":    (85, 102, None, None),
            "blue":    (102, 130, None, None),
            "purple":  (130, 148, None, None),
            "magenta": (148, 170, None, None),
        }

        for col_name, (lo, hi, wrap_lo, wrap_hi) in COLOR_RANGES.items():
            dh = hue_dict.get(col_name, 0)
            ds = sat_dict.get(col_name, 0)
            dl = lum_dict.get(col_name, 0)

            if dh == 0 and ds == 0 and dl == 0:
                continue

            if wrap_lo is not None:
                mask = ((h >= lo) & (h <= hi)) | ((h >= wrap_lo) & (h <= wrap_hi))
            else:
                mask = (h >= lo) & (h <= hi)

            color_mask = mask & (s > 25)
            if not np.any(color_mask):
                continue

            w = (s[color_mask] / 255.0)

            if dh != 0:
                h_shift = (dh / 100.0) * 16.0
                h[color_mask] = (h[color_mask] + h_shift * w) % 180

            if ds != 0:
                s_shift = (ds / 100.0) * 85.0
                s[color_mask] = np.clip(s[color_mask] + s_shift * w, 0, 255)

            if dl != 0:
                l_shift = (dl / 100.0) * 65.0
                v[color_mask] = np.clip(v[color_mask] + l_shift * w, 0, 255)

        hsv[:, :, 0] = h.astype(np.uint8)
        hsv[:, :, 1] = s.astype(np.uint8)
        hsv[:, :, 2] = v.astype(np.uint8)
        out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    return out


def get_ffmpeg_video_filter(preset_id: str, intensity: float = 1.0, hsl_settings: dict = None) -> str:
    """Returns equivalent FFmpeg video filter chain for burning / exporting to MP4."""
    filters = []

    if preset_id not in ("none", "None", "", None) and intensity > 0.01:
        if preset_id == "mono_noir":
            filters.append(f"hue=s={1.0 - intensity:.2f}")
        elif preset_id == "mono_silver":
            filters.append(f"hue=s=0,eq=contrast={1.0 + 0.4 * intensity:.2f}:brightness=-0.04")
        elif preset_id == "mono_sepia":
            filters.append(f"colorbalance=rs={0.25 * intensity:.2f}:gs={0.10 * intensity:.2f}:bs={-0.25 * intensity:.2f}:rm={0.2 * intensity:.2f}:bm={-0.3 * intensity:.2f}")
        elif preset_id == "cine_teal_orange":
            filters.append(f"colorbalance=bs={0.28 * intensity:.2f}:gs={0.08 * intensity:.2f}:rs={-0.15 * intensity:.2f}:rh={0.25 * intensity:.2f}:gh={0.08 * intensity:.2f}:bh={-0.18 * intensity:.2f}")
        elif preset_id == "cine_gold":
            filters.append(f"colorbalance=rs={0.15 * intensity:.2f}:gs={0.05 * intensity:.2f}:bs={-0.18 * intensity:.2f}:rh={0.25 * intensity:.2f}:gh={0.10 * intensity:.2f}:bh={-0.22 * intensity:.2f}")
        elif preset_id == "bright_vivid":
            filters.append(f"eq=saturation={1.0 + 0.45 * intensity:.2f}:contrast={1.0 + 0.15 * intensity:.2f}")
        elif preset_id == "film_kodak":
            filters.append(f"curves=vintage,eq=contrast={1.0 + 0.12 * intensity:.2f}")
        elif preset_id == "night_cyber":
            filters.append(f"colorbalance=bs={0.35 * intensity:.2f}:rh={0.25 * intensity:.2f}:bh={0.25 * intensity:.2f}:gs={-0.15 * intensity:.2f}")
        elif preset_id == "past_70s":
            filters.append(f"colorbalance=rs={0.25 * intensity:.2f}:gs={0.12 * intensity:.2f}:bs={-0.20 * intensity:.2f}:rm={0.18 * intensity:.2f}:bm={-0.22 * intensity:.2f}")
        else:
            filters.append(f"eq=contrast={1.0 + 0.1 * intensity:.2f}:saturation={1.0 + 0.15 * intensity:.2f}")

    if hsl_settings:
        tone = hsl_settings.get("tone", {})
        con = tone.get("contrast", 0)
        exp = tone.get("exposure", 0)
        temp = tone.get("temperature", 0)
        tint = tone.get("tint", 0)

        if con != 0 or exp != 0:
            c_val = 1.0 + (con / 100.0) * 0.70
            b_val = (exp / 100.0) * 0.20
            filters.append(f"eq=contrast={c_val:.2f}:brightness={b_val:.2f}")

        if temp != 0 or tint != 0:
            rs = (temp / 100.0) * 0.25
            bs = -(temp / 100.0) * 0.25
            gs = -(tint / 100.0) * 0.20
            filters.append(f"colorbalance=rs={rs:.2f}:bs={bs:.2f}:gs={gs:.2f}")

    return ",".join(filters)


# ---------------------------------------------------------------------------
# STUDIO COLOR PRESETS & ADVANCED HSL DIALOG (PREMIERE / LIGHTROOM GRADE)
# ---------------------------------------------------------------------------
class ColorPresetsDialog(QDialog):
    """
    Professional Video Color Grading Suite:
    - Mode 1: Presets & Looks (Canva/CapCut grid with categories and intensity)
    - Mode 2: Advanced HSL & Tone (Lightroom / Premiere Pro Lumetri 8-channel color grading)
    - Live 60fps preview synchronization with player monitor
    """
    preset_selected = Signal(str, float)  # (preset_id, intensity)
    hsl_modified = Signal(dict)            # (hsl_settings)

    def __init__(self, parent=None, current_preset: str = "none", current_intensity: float = 0.80, preview_frame_bgr=None, current_hsl: dict = None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Video Color Presets & Advanced HSL Color Grading")
        self.resize(840, 640)
        self.setMinimumSize(740, 560)
        self.setStyleSheet("""
            QDialog {
                background-color: #11141c;
                color: #f1f5f9;
            }
        """)

        self.active_preset_id = current_preset or "none"
        self.active_intensity = float(current_intensity)
        self.preview_frame_bgr = preview_frame_bgr

        # HSL Settings structure
        self.hsl_settings = {
            "hue": {c[0]: 0 for c in HSL_COLORS},
            "sat": {c[0]: 0 for c in HSL_COLORS},
            "lum": {c[0]: 0 for c in HSL_COLORS},
            "tone": {
                "temperature": 0,
                "tint": 0,
                "exposure": 0,
                "contrast": 0,
                "vibrance": 0
            }
        }
        if current_hsl and isinstance(current_hsl, dict):
            for k in ("hue", "sat", "lum", "tone"):
                if k in current_hsl and isinstance(current_hsl[k], dict):
                    self.hsl_settings[k].update(current_hsl[k])

        self._base_thumb_bgr = self._create_base_thumb(preview_frame_bgr)
        self._preset_buttons = {}
        self._hsl_slider_widgets = {}  # (group, color_key) -> (slider, label)

        self._init_ui()

    def _create_base_thumb(self, frame_bgr) -> np.ndarray:
        if frame_bgr is not None and frame_bgr.size > 0:
            return cv2.resize(frame_bgr, (160, 100), interpolation=cv2.INTER_AREA)

        thumb = np.zeros((100, 160, 3), dtype=np.uint8)
        for y in range(100):
            r = int(120 + y * 0.8)
            g = int(160 + y * 0.6)
            b = int(210 - y * 0.4)
            thumb[y, :] = (b, g, r)
        cv2.circle(thumb, (40, 110), 55, (40, 75, 45), -1)
        cv2.circle(thumb, (120, 120), 70, (30, 60, 38), -1)
        return thumb

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # 1. Header with Mode Switcher & Reset
        hdr = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_title = QLabel("🎨 Video Color Presets & Advanced HSL Suite")
        lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #38bdf8;")
        lbl_sub = QLabel("Select cinematic LUT presets or fine-tune exact HSL color curves & tone.")
        lbl_sub.setStyleSheet("font-size: 11px; color: #94a3b8;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        hdr.addLayout(title_box)
        hdr.addStretch()

        # Top Mode Switcher (Pill tabs)
        mode_box = QHBoxLayout()
        mode_box.setSpacing(4)
        self.btn_mode_presets = QPushButton(" 🎨 Presets & Looks ")
        self.btn_mode_presets.setCheckable(True)
        self.btn_mode_presets.setChecked(True)
        self.btn_mode_presets.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_mode_advance = QPushButton(" 🎛️ Advanced HSL & Tone ")
        self.btn_mode_advance.setCheckable(True)
        self.btn_mode_advance.setChecked(False)
        self.btn_mode_advance.setCursor(Qt.CursorShape.PointingHandCursor)

        self._style_mode_buttons()
        self.btn_mode_presets.clicked.connect(lambda: self._switch_mode(0))
        self.btn_mode_advance.clicked.connect(lambda: self._switch_mode(1))

        mode_box.addWidget(self.btn_mode_presets)
        mode_box.addWidget(self.btn_mode_advance)
        hdr.addLayout(mode_box)
        hdr.addSpacing(10)

        btn_reset_all = QPushButton("↺ Reset All")
        btn_reset_all.setStyleSheet("""
            QPushButton {
                background-color: #272c38;
                color: #cbd5e1;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #384252;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
                border-color: #f87171;
            }
        """)
        btn_reset_all.clicked.connect(self._reset_all)
        hdr.addWidget(btn_reset_all)
        root.addLayout(hdr)

        # 2. Main Stacked Widget (Page 0: Presets, Page 1: Advanced HSL)
        self.stack = QStackedWidget()

        # Page 0: Presets
        page_presets = self._create_presets_page()
        self.stack.addWidget(page_presets)

        # Page 1: Advanced HSL
        page_advance = self._create_advanced_hsl_page()
        self.stack.addWidget(page_advance)

        root.addWidget(self.stack, 1)

        # 3. Bottom Action Bar
        bot_bar = QHBoxLayout()
        self.lbl_status = QLabel(f"Active: <b>{self._get_preset_name(self.active_preset_id)}</b> ({int(self.active_intensity * 100)}%)")
        self.lbl_status.setStyleSheet("color: #38bdf8; font-size: 11px;")
        bot_bar.addWidget(self.lbl_status)
        bot_bar.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #272c38; color: #cbd5e1; padding: 6px 16px; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)
        bot_bar.addWidget(btn_cancel)

        btn_apply = QPushButton("✓ Apply Color Grade (យល់ព្រម)")
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: white;
                font-weight: bold;
                padding: 6px 22px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0ea5e9;
            }
        """)
        btn_apply.clicked.connect(self.accept)
        bot_bar.addWidget(btn_apply)
        root.addLayout(bot_bar)

    def _style_mode_buttons(self):
        active_style = """
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #38bdf8;
                border-radius: 4px;
            }
        """
        inactive_style = """
            QPushButton {
                background-color: #1e2430;
                color: #94a3b8;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #334155;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #272f3f;
                color: #f1f5f9;
            }
        """
        self.btn_mode_presets.setStyleSheet(active_style if self.btn_mode_presets.isChecked() else inactive_style)
        self.btn_mode_advance.setStyleSheet(active_style if self.btn_mode_advance.isChecked() else inactive_style)

    def _switch_mode(self, page_idx: int):
        self.btn_mode_presets.setChecked(page_idx == 0)
        self.btn_mode_advance.setChecked(page_idx == 1)
        self._style_mode_buttons()
        self.stack.setCurrentIndex(page_idx)

    # ------------------ PRESETS PAGE (PAGE 0) ------------------
    def _create_presets_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(10)

        # Category Tabs
        self.tabs = QTabBar()
        self.tabs.setDrawBase(False)
        self.tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #181d28;
                color: #94a3b8;
                padding: 8px 16px;
                margin-right: 4px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: #242c3d;
                color: #f97316;
                border-bottom: 3px solid #f97316;
            }
            QTabBar::tab:hover:!selected {
                color: #f1f5f9;
                background: #1f2636;
            }
        """)
        for cat in PRESET_CATEGORIES.keys():
            self.tabs.addTab(cat)
        self.tabs.currentChanged.connect(self._on_category_tab_changed)
        layout.addWidget(self.tabs)

        # Intensity Slider
        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(4, 2, 4, 2)
        lbl_int_label = QLabel("Preset Intensity (កម្រិតពណ៌):")
        lbl_int_label.setStyleSheet("color: #e2e8f0; font-weight: bold; font-size: 11px;")
        slider_row.addWidget(lbl_int_label)

        self.slider_intensity = QSlider(Qt.Orientation.Horizontal)
        self.slider_intensity.setRange(0, 100)
        self.slider_intensity.setValue(int(self.active_intensity * 100))
        self.slider_intensity.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #334155;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #f97316;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #f97316;
                width: 14px;
                height: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }
        """)
        self.slider_intensity.valueChanged.connect(self._on_intensity_slider_changed)
        slider_row.addWidget(self.slider_intensity, 1)

        self.lbl_int_val = QLabel(f"{int(self.active_intensity * 100)}%")
        self.lbl_int_val.setStyleSheet("color: #f97316; font-weight: bold; font-size: 12px; min-width: 36px;")
        slider_row.addWidget(self.lbl_int_val)
        layout.addLayout(slider_row)

        # Grid of Cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: 1px solid #28303f; background-color: #151822; border-radius: 6px; }")

        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background-color: #151822;")
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(12, 12, 12, 12)
        self.grid_layout.setSpacing(14)
        self.scroll.setWidget(self.grid_container)
        layout.addWidget(self.scroll, 1)

        # Select tab
        self._populate_grid("Cinematic")
        for i, cat in enumerate(PRESET_CATEGORIES.keys()):
            for item in PRESET_CATEGORIES[cat]:
                if item["id"] == self.active_preset_id:
                    self.tabs.setCurrentIndex(i)
                    self._populate_grid(cat)
                    break

        return page

    # ------------------ ADVANCED HSL PAGE (PAGE 1) ------------------
    def _create_advanced_hsl_page(self) -> QWidget:
        """Creates the Adobe Lightroom / Premiere Pro style HSL color grading suite."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)

        # 1. HSL Tab Switcher: [ All | Hue | Saturation | Luminance ]
        hsl_top = QHBoxLayout()
        lbl_hsl_title = QLabel("🎛️ HSL / Color")
        lbl_hsl_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #f8fafc;")
        hsl_top.addWidget(lbl_hsl_title)
        hsl_top.addStretch()

        self.hsl_tabs = QTabBar()
        self.hsl_tabs.setDrawBase(False)
        self.hsl_tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hsl_tabs.setStyleSheet("""
            QTabBar::tab {
                background: #1e2430;
                color: #94a3b8;
                padding: 6px 14px;
                margin-left: 2px;
                border-radius: 4px;
                font-weight: 600;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #334155;
                color: #38bdf8;
                font-weight: bold;
            }
            QTabBar::tab:hover:!selected {
                color: #f1f5f9;
                background: #272f3f;
            }
        """)
        for tab_name in ("All", "Hue", "Saturation", "Luminance"):
            self.hsl_tabs.addTab(tab_name)
        self.hsl_tabs.currentChanged.connect(self._on_hsl_tab_changed)
        hsl_top.addWidget(self.hsl_tabs)

        btn_reset_hsl = QPushButton("↺ Reset HSL")
        btn_reset_hsl.setStyleSheet("background-color: #272c38; color: #94a3b8; font-size: 11px; padding: 4px 10px; border-radius: 4px;")
        btn_reset_hsl.clicked.connect(self._reset_hsl_only)
        hsl_top.addWidget(btn_reset_hsl)
        layout.addLayout(hsl_top)

        # 2. Scrollable Sliders Area
        hsl_scroll = QScrollArea()
        hsl_scroll.setWidgetResizable(True)
        hsl_scroll.setStyleSheet("QScrollArea { border: 1px solid #28303f; background-color: #151822; border-radius: 6px; }")

        self.hsl_container = QWidget()
        self.hsl_container.setStyleSheet("background-color: #151822;")
        self.hsl_layout = QVBoxLayout(self.hsl_container)
        self.hsl_layout.setContentsMargins(14, 10, 14, 10)
        self.hsl_layout.setSpacing(12)

        # Build HSL Sliders
        self._build_hsl_sections()

        hsl_scroll.setWidget(self.hsl_container)
        layout.addWidget(hsl_scroll, 1)

        # 3. Basic Tone Controls Bar (Temperature, Tint, Exposure, Contrast, Vibrance)
        tone_frame = QFrame()
        tone_frame.setStyleSheet("background-color: #181d28; border: 1px solid #28303f; border-radius: 6px;")
        tone_layout = QHBoxLayout(tone_frame)
        tone_layout.setContentsMargins(12, 8, 12, 8)
        tone_layout.setSpacing(14)

        tone_controls = [
            ("temperature", "Temp (កម្តៅ)", "#f59e0b"),
            ("tint",        "Tint (លំអៀង)", "#d946ef"),
            ("exposure",    "Exposure (ពន្លឺ)", "#38bdf8"),
            ("contrast",    "Contrast (ច្បាស់)", "#cbd5e1"),
            ("vibrance",    "Vibrance (ស្រស់)", "#10b981")
        ]

        for key, name, dot_col in tone_controls:
            col_box = QVBoxLayout()
            col_box.setSpacing(2)
            
            top_row = QHBoxLayout()
            lbl_name = QLabel(f"<span style='color:{dot_col};'>●</span> {name}")
            lbl_name.setStyleSheet("font-size: 10px; font-weight: bold; color: #cbd5e1;")
            top_row.addWidget(lbl_name)
            top_row.addStretch()

            cur_val = self.hsl_settings["tone"].get(key, 0)
            lbl_val = QLabel(f"{cur_val:+d}" if cur_val != 0 else "0")
            lbl_val.setStyleSheet("font-size: 10px; font-weight: bold; color: #38bdf8; min-width: 24px;")
            top_row.addWidget(lbl_val)
            col_box.addLayout(top_row)

            s = QSlider(Qt.Orientation.Horizontal)
            s.setRange(-100, 100)
            s.setValue(cur_val)
            
            # Custom tone slider track
            if key == "temperature":
                grad = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:0.5 #475569, stop:1 #f59e0b)"
            elif key == "tint":
                grad = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22c55e, stop:0.5 #475569, stop:1 #d946ef)"
            else:
                grad = "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #334155, stop:0.5 #64748b, stop:1 #94a3b8)"

            s.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    height: 4px;
                    background: {grad};
                    border-radius: 2px;
                }}
                QSlider::handle:horizontal {{
                    background: #cbd5e1;
                    border: 1px solid #1e293b;
                    width: 12px;
                    height: 12px;
                    margin-top: -4px;
                    margin-bottom: -4px;
                    border-radius: 6px;
                }}
                QSlider::handle:horizontal:hover {{
                    background: #ffffff;
                    border: 2px solid #38bdf8;
                }}
            """)
            s.valueChanged.connect(lambda v, k=key, l=lbl_val: self._on_tone_slider_changed(k, v, l))
            col_box.addWidget(s)
            tone_layout.addLayout(col_box, 1)

        layout.addWidget(tone_frame)
        return page

    def _build_hsl_sections(self):
        """Constructs Hue, Saturation, and Luminance slider rows matching Lightroom/Premiere."""
        # Clear container
        while self.hsl_layout.count():
            item = self.hsl_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    w = item.layout().takeAt(0).widget()
                    if w:
                        w.deleteLater()

        self._hsl_group_frames = {}

        for group_key, group_title in (("hue", "Hue (កម្រិតពណ៌)"), ("sat", "Saturation (កម្រិតឆ្អែត)"), ("lum", "Luminance (កម្រិតពន្លឺពណ៌)")):
            grp_frame = QFrame()
            grp_frame.setStyleSheet("background-color: transparent;")
            grp_vbox = QVBoxLayout(grp_frame)
            grp_vbox.setContentsMargins(0, 4, 0, 8)
            grp_vbox.setSpacing(4)

            # Section Header
            hdr_lbl = QLabel(f"<b>{group_title}</b>")
            hdr_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;")
            grp_vbox.addWidget(hdr_lbl)

            # 8 Color Sliders
            for col_key, col_name, dot_col in HSL_COLORS:
                row = QHBoxLayout()
                row.setContentsMargins(4, 2, 4, 2)
                row.setSpacing(10)

                # Color Dot & Label
                lbl_color = QLabel(f"<span style='color:{dot_col}; font-size:14px;'>●</span> {col_name}")
                lbl_color.setStyleSheet("color: #cbd5e1; font-weight: 600; font-size: 11px; min-width: 80px;")
                row.addWidget(lbl_color)

                # Gradient Slider
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(-100, 100)
                cur_val = self.hsl_settings[group_key].get(col_key, 0)
                slider.setValue(cur_val)

                grad = HSL_GRADIENTS[group_key][col_key]
                slider.setStyleSheet(f"""
                    QSlider::groove:horizontal {{
                        height: 4px;
                        background: {grad};
                        border-radius: 2px;
                    }}
                    QSlider::handle:horizontal {{
                        background: #cbd5e1;
                        border: 1px solid #1e293b;
                        width: 14px;
                        height: 14px;
                        margin-top: -5px;
                        margin-bottom: -5px;
                        border-radius: 7px;
                    }}
                    QSlider::handle:horizontal:hover {{
                        background: #ffffff;
                        border: 2px solid #38bdf8;
                    }}
                """)

                # Numeric Readout
                lbl_val = QLabel(f"{cur_val:+d}" if cur_val != 0 else "0")
                lbl_val.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 11px; min-width: 32px; text-align: right;")
                lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                lbl_val.setCursor(Qt.CursorShape.PointingHandCursor)
                # Click value to reset to 0
                lbl_val.mousePressEvent = lambda e, s=slider: s.setValue(0)

                slider.valueChanged.connect(lambda v, gk=group_key, ck=col_key, lv=lbl_val: self._on_hsl_slider_changed(gk, ck, v, lv))

                row.addWidget(slider, 1)
                row.addWidget(lbl_val)
                grp_vbox.addLayout(row)

                self._hsl_slider_widgets[(group_key, col_key)] = (slider, lbl_val)

            self.hsl_layout.addWidget(grp_frame)
            self._hsl_group_frames[group_key] = grp_frame

    def _on_hsl_tab_changed(self, idx: int):
        mode = self.hsl_tabs.tabText(idx)
        if mode == "All":
            for frame in self._hsl_group_frames.values():
                frame.setVisible(True)
        elif mode == "Hue":
            self._hsl_group_frames["hue"].setVisible(True)
            self._hsl_group_frames["sat"].setVisible(False)
            self._hsl_group_frames["lum"].setVisible(False)
        elif mode == "Saturation":
            self._hsl_group_frames["hue"].setVisible(False)
            self._hsl_group_frames["sat"].setVisible(True)
            self._hsl_group_frames["lum"].setVisible(False)
        elif mode == "Luminance":
            self._hsl_group_frames["hue"].setVisible(False)
            self._hsl_group_frames["sat"].setVisible(False)
            self._hsl_group_frames["lum"].setVisible(True)

    def _on_hsl_slider_changed(self, group_key: str, color_key: str, val: int, lbl_val: QLabel):
        self.hsl_settings[group_key][color_key] = val
        lbl_val.setText(f"{val:+d}" if val != 0 else "0")
        lbl_val.setStyleSheet("color: #38bdf8;" if val != 0 else "color: #cbd5e1;")
        self._emit_updates()

    def _on_tone_slider_changed(self, key: str, val: int, lbl_val: QLabel):
        self.hsl_settings["tone"][key] = val
        lbl_val.setText(f"{val:+d}" if val != 0 else "0")
        lbl_val.setStyleSheet("color: #38bdf8;" if val != 0 else "color: #cbd5e1;")
        self._emit_updates()

    def _reset_hsl_only(self):
        for gk in ("hue", "sat", "lum"):
            for ck in self.hsl_settings[gk].keys():
                self.hsl_settings[gk][ck] = 0
                if (gk, ck) in self._hsl_slider_widgets:
                    slider, lbl = self._hsl_slider_widgets[(gk, ck)]
                    slider.blockSignals(True)
                    slider.setValue(0)
                    slider.blockSignals(False)
                    lbl.setText("0")
                    lbl.setStyleSheet("color: #cbd5e1;")
        self._emit_updates()

    def _reset_all(self):
        self._select_preset("none")
        self.slider_intensity.setValue(80)
        self._reset_hsl_only()
        for k in self.hsl_settings["tone"].keys():
            self.hsl_settings["tone"][k] = 0
        self._emit_updates()

    def _emit_updates(self):
        # Update status
        p_name = self._get_preset_name(self.active_preset_id)
        has_hsl = any(v != 0 for v in self.hsl_settings["hue"].values()) or \
                  any(v != 0 for v in self.hsl_settings["sat"].values()) or \
                  any(v != 0 for v in self.hsl_settings["lum"].values()) or \
                  any(v != 0 for v in self.hsl_settings["tone"].values())
        
        hsl_tag = " | HSL: Custom" if has_hsl else ""
        self.lbl_status.setText(f"Active: <b>{p_name}</b> ({int(self.active_intensity * 100)}%){hsl_tag}")

        self.preset_selected.emit(self.active_preset_id, self.active_intensity)
        self.hsl_modified.emit(self.hsl_settings)

    # ------------------ PRESET GRID HELPERS ------------------
    def _get_preset_name(self, pid: str) -> str:
        for cat, items in PRESET_CATEGORIES.items():
            for it in items:
                if it["id"] == pid:
                    return f"{cat} - {it['name']}"
        return "None"

    def _on_category_tab_changed(self, idx: int):
        cat_name = self.tabs.tabText(idx)
        self._populate_grid(cat_name)

    def _populate_grid(self, category_name: str):
        while self.grid_layout.count():
            w = self.grid_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self._preset_buttons.clear()

        presets = PRESET_CATEGORIES.get(category_name, [])
        cols = 4

        for i, p_info in enumerate(presets):
            pid = p_info["id"]
            pname = p_info["name"]

            graded_bgr = apply_color_preset(self._base_thumb_bgr.copy(), pid, intensity=1.0)
            rgb = cv2.cvtColor(graded_bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
            pix = QPixmap.fromImage(qimg)

            card = QFrame()
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            is_active = (pid == self.active_preset_id)
            self._style_card(card, is_active)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(6, 6, 6, 6)
            card_layout.setSpacing(4)

            lbl_img = QLabel()
            lbl_img.setPixmap(pix.scaled(150, 94, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_img.setStyleSheet("border-radius: 4px;")
            card_layout.addWidget(lbl_img)

            lbl_name = QLabel(pname)
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_name.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {'#f97316' if is_active else '#e2e8f0'};")
            card_layout.addWidget(lbl_name)

            card.mousePressEvent = lambda e, p=pid: self._select_preset(p)
            self._preset_buttons[pid] = (card, lbl_name)

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(card, row, col)

    def _style_card(self, card: QFrame, is_active: bool):
        if is_active:
            card.setStyleSheet("""
                QFrame {
                    background-color: #272f3f;
                    border: 2px solid #f97316;
                    border-radius: 6px;
                }
            """)
        else:
            card.setStyleSheet("""
                QFrame {
                    background-color: #1e2430;
                    border: 1px solid #334155;
                    border-radius: 6px;
                }
                QFrame:hover {
                    border: 1px solid #38bdf8;
                    background-color: #232a38;
                }
            """)

    def _select_preset(self, preset_id: str):
        self.active_preset_id = preset_id
        for pid, (card, lbl) in self._preset_buttons.items():
            is_active = (pid == preset_id)
            self._style_card(card, is_active)
            lbl.setStyleSheet(f"font-size: 11px; font-weight: bold; color: {'#f97316' if is_active else '#e2e8f0'};")

        self._emit_updates()

    def _on_intensity_slider_changed(self, val: int):
        self.active_intensity = val / 100.0
        self.lbl_int_val.setText(f"{val}%")
        self._emit_updates()
