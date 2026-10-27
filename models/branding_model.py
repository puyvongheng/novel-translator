"""
AI Khmer Movie Studio - Branding & Animated Sponsor Ads Model
Data structures & mathematical interpolation engine for:
- Global Branding (Logo Watermark, Intro/Outro, Lower-Third Footer)
- Sponsor Ads & Dynamic Rotation (Timestamp-based scheduled ads, Safe Areas)
- Motion Path & Keyframe Animation Engine (Easing, Loops, Ping-Pong, Direction, JSON)
- Responsive Layout Templates (16:9 Cinema, 9:16 TikTok/Shorts, 1:1 Square)
"""

import os
import math
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple


# ---------------------------------------------------------------------------
# EASING FUNCTIONS
# ---------------------------------------------------------------------------
def ease_linear(t: float) -> float:
    return max(0.0, min(1.0, t))

def ease_in_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t

def ease_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * (2.0 - t)

def ease_in_out_quad(t: float) -> float:
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 2.0 * t * t
    return -1.0 + (4.0 - 2.0 * t) * t

def ease_in_out_sine(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 0.5 * (1.0 - math.cos(math.pi * t))

EASING_MAP = {
    "linear": ease_linear,
    "ease_in": ease_in_quad,
    "ease_out": ease_out_quad,
    "ease_in_out": ease_in_out_quad,
    "sine": ease_in_out_sine
}


# ---------------------------------------------------------------------------
# MOTION PATH & KEYFRAME ANIMATION ENGINE
# ---------------------------------------------------------------------------
@dataclass
class KeyframePoint:
    time: float = 0.0          # relative timestamp in seconds (0.0 to duration)
    x: float = 0.5             # normalized canvas X (0.0 - 1.0)
    y: float = 0.5             # normalized canvas Y (0.0 - 1.0)
    scale: float = 1.0         # relative scale multiplier
    rotation: float = 0.0      # degrees
    opacity: float = 1.0       # 0.0 to 1.0

    def to_dict(self) -> dict:
        return {
            "time": round(float(self.time), 2),
            "x": round(float(self.x), 3),
            "y": round(float(self.y), 3),
            "scale": round(float(self.scale), 2),
            "rotation": round(float(self.rotation), 1),
            "opacity": round(float(self.opacity), 2)
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            time=float(data.get("time", 0.0)),
            x=float(data.get("x", 0.5)),
            y=float(data.get("y", 0.5)),
            scale=float(data.get("scale", 1.0)),
            rotation=float(data.get("rotation", 0.0)),
            opacity=float(data.get("opacity", 1.0))
        )


@dataclass
class MotionPathAnimation:
    """
    Evaluates dynamic position (x, y), scale, rotation, and opacity at any playback time (t).
    Supports:
    - Loop Infinite or Loop Count (2, 3, 5, 10)
    - Direction: Normal, Reverse, Ping-Pong (bounces back and forth)
    - Delay before start & Pause between loops
    - Easing: Linear, Ease In, Ease Out, Ease In-Out
    - Custom Motion Path keyframes
    """
    mode: str = "motion_path"          # "motion_path", "slide", "bounce", "pulse", "orbit"
    duration: float = 8.0              # duration of 1 animation loop in seconds
    loop: bool = True                  # True = infinite or count
    loop_count: int = 0                # 0 = infinite, or 2, 3, 5, 10
    direction: str = "normal"          # "normal", "reverse", "ping_pong"
    easing: str = "linear"             # "linear", "ease_in", "ease_out", "ease_in_out"
    delay: float = 0.0                 # initial delay before animation begins (seconds)
    pause_between_loops: float = 0.0   # rest duration between loops (seconds)
    safe_area: bool = True             # auto-dock away from subtitle zone
    keyframes: List[KeyframePoint] = field(default_factory=list)

    def evaluate(self, elapsed: float) -> Tuple[float, float, float, float, float]:
        """
        Returns (x, y, scale, rotation, opacity) at elapsed seconds since ad start.
        """
        if not self.keyframes or len(self.keyframes) == 0:
            return (0.5, 0.5, 1.0, 0.0, 1.0)

        if len(self.keyframes) == 1:
            kf = self.keyframes[0]
            return (kf.x, kf.y, kf.scale, kf.rotation, kf.opacity)

        # 1. Handle Delay
        if elapsed < self.delay:
            first = self.keyframes[0]
            return (first.x, first.y, first.scale, first.rotation, first.opacity)

        t_active = elapsed - self.delay
        loop_dur = max(0.5, float(self.duration))
        cycle_dur = loop_dur + max(0.0, float(self.pause_between_loops))

        # 2. Check Loop Count limit
        if not self.loop and t_active > loop_dur:
            last = self.keyframes[-1]
            return (last.x, last.y, last.scale, last.rotation, last.opacity)

        if self.loop_count > 0:
            current_cycle = int(t_active // cycle_dur)
            if current_cycle >= self.loop_count:
                last = self.keyframes[-1] if self.direction != "reverse" else self.keyframes[0]
                return (last.x, last.y, last.scale, last.rotation, last.opacity)

        # 3. Calculate position inside current cycle
        cycle_pos = t_active % cycle_dur
        if cycle_pos > loop_dur:
            # Inside pause between loops
            last = self.keyframes[-1] if self.direction == "normal" else self.keyframes[0]
            return (last.x, last.y, last.scale, last.rotation, last.opacity)

        # Progress within [0.0, 1.0]
        progress = cycle_pos / loop_dur

        # 4. Handle Ping-Pong & Reverse direction
        if self.direction == "ping_pong":
            cycle_idx = int(t_active // cycle_dur)
            if cycle_idx % 2 == 1:
                progress = 1.0 - progress
        elif self.direction == "reverse":
            progress = 1.0 - progress

        # 5. Apply Easing
        easing_fn = EASING_MAP.get(self.easing, ease_linear)
        eased_progress = easing_fn(progress)
        target_t = eased_progress * loop_dur

        # 6. Interpolate between surrounding keyframes
        sorted_kfs = sorted(self.keyframes, key=lambda k: k.time)
        if target_t <= sorted_kfs[0].time:
            k = sorted_kfs[0]
            return (k.x, k.y, k.scale, k.rotation, k.opacity)
        if target_t >= sorted_kfs[-1].time:
            k = sorted_kfs[-1]
            return (k.x, k.y, k.scale, k.rotation, k.opacity)

        for i in range(len(sorted_kfs) - 1):
            k1 = sorted_kfs[i]
            k2 = sorted_kfs[i + 1]
            if k1.time <= target_t <= k2.time:
                span = max(0.001, k2.time - k1.time)
                ratio = (target_t - k1.time) / span
                # Linear lerp
                x = k1.x + (k2.x - k1.x) * ratio
                y = k1.y + (k2.y - k1.y) * ratio
                sc = k1.scale + (k2.scale - k1.scale) * ratio
                rot = k1.rotation + (k2.rotation - k1.rotation) * ratio
                op = k1.opacity + (k2.opacity - k1.opacity) * ratio
                return (x, y, sc, rot, op)

        last = sorted_kfs[-1]
        return (last.x, last.y, last.scale, last.rotation, last.opacity)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "duration": round(float(self.duration), 2),
            "loop": bool(self.loop),
            "loop_count": int(self.loop_count),
            "direction": self.direction,
            "easing": self.easing,
            "delay": round(float(self.delay), 2),
            "pause_between_loops": round(float(self.pause_between_loops), 2),
            "safe_area": bool(self.safe_area),
            "keyframes": [kf.to_dict() for kf in self.keyframes]
        }

    @classmethod
    def from_dict(cls, data: dict):
        kfs = [KeyframePoint.from_dict(k) for k in data.get("keyframes", [])]
        return cls(
            mode=data.get("mode", "motion_path"),
            duration=float(data.get("duration", 8.0)),
            loop=bool(data.get("loop", True)),
            loop_count=int(data.get("loop_count", 0)),
            direction=data.get("direction", "normal"),
            easing=data.get("easing", "linear"),
            delay=float(data.get("delay", 0.0)),
            pause_between_loops=float(data.get("pause_between_loops", 0.0)),
            safe_area=bool(data.get("safe_area", True)),
            keyframes=kfs
        )


# ---------------------------------------------------------------------------
# PRESET ANIMATION GENERATORS
# ---------------------------------------------------------------------------
def create_animation_preset(preset_name: str, duration: float = 8.0) -> MotionPathAnimation:
    """Creates ready-to-use animation trajectories with smooth mathematical keyframes."""
    dur = max(2.0, duration)

    if preset_name == "slide_left_right":
        kfs = [
            KeyframePoint(time=0.0, x=0.08, y=0.15, scale=1.0, rotation=0.0, opacity=0.0),
            KeyframePoint(time=dur * 0.15, x=0.20, y=0.15, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.85, x=0.80, y=0.15, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur, x=0.92, y=0.15, scale=1.0, rotation=0.0, opacity=0.0)
        ]
        return MotionPathAnimation(mode="slide", duration=dur, loop=True, direction="ping_pong", easing="ease_in_out", keyframes=kfs)

    elif preset_name == "corner_orbit":
        # Glides through 4 corners avoiding center screen
        kfs = [
            KeyframePoint(time=0.0, x=0.12, y=0.12, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.25, x=0.88, y=0.12, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.50, x=0.88, y=0.80, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.75, x=0.12, y=0.80, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur, x=0.12, y=0.12, scale=1.0, rotation=0.0, opacity=1.0)
        ]
        return MotionPathAnimation(mode="orbit", duration=dur, loop=True, direction="normal", easing="ease_in_out", keyframes=kfs)

    elif preset_name == "bounce_pulse":
        # Floating bob with gentle breathing scale
        kfs = [
            KeyframePoint(time=0.0, x=0.85, y=0.15, scale=0.95, rotation=0.0, opacity=0.9),
            KeyframePoint(time=dur * 0.25, x=0.85, y=0.12, scale=1.08, rotation=2.0, opacity=1.0),
            KeyframePoint(time=dur * 0.50, x=0.85, y=0.16, scale=0.95, rotation=0.0, opacity=0.95),
            KeyframePoint(time=dur * 0.75, x=0.85, y=0.13, scale=1.05, rotation=-2.0, opacity=1.0),
            KeyframePoint(time=dur, x=0.85, y=0.15, scale=0.95, rotation=0.0, opacity=0.9)
        ]
        return MotionPathAnimation(mode="bounce", duration=dur, loop=True, direction="normal", easing="sine", keyframes=kfs)

    elif preset_name == "bottom_banner_pop":
        # Pops up from bottom-center, holds, and slides down
        kfs = [
            KeyframePoint(time=0.0, x=0.5, y=0.95, scale=0.6, rotation=0.0, opacity=0.0),
            KeyframePoint(time=dur * 0.12, x=0.5, y=0.84, scale=1.05, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.18, x=0.5, y=0.85, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.85, x=0.5, y=0.85, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur, x=0.5, y=0.95, scale=0.8, rotation=0.0, opacity=0.0)
        ]
        return MotionPathAnimation(mode="banner", duration=dur, loop=True, direction="normal", pause_between_loops=3.0, easing="ease_out", keyframes=kfs)

    else:
        # Default 4-corner motion path matching user's spec
        kfs = [
            KeyframePoint(time=0.0, x=0.10, y=0.10, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.25, x=0.90, y=0.10, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.50, x=0.90, y=0.85, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur * 0.75, x=0.10, y=0.85, scale=1.0, rotation=0.0, opacity=1.0),
            KeyframePoint(time=dur, x=0.10, y=0.10, scale=1.0, rotation=0.0, opacity=1.0)
        ]
        return MotionPathAnimation(mode="motion_path", duration=dur, loop=True, direction="normal", easing="linear", keyframes=kfs)


# ---------------------------------------------------------------------------
# SPONSOR AD DATA MODEL
# ---------------------------------------------------------------------------
@dataclass
class SponsorAdItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Sponsor Brand"
    asset: str = ""                    # path to logo image / banner
    qr_code_path: str = ""             # optional QR code image
    website_text: str = ""             # e.g. "www.sponsor.com"
    brand_color: str = "#0ea5e9"       # hex accent color
    start_time: float = 10.0           # appear at seconds (e.g. 120 = 2:00)
    end_time: float = 22.0             # disappear at seconds
    w: float = 0.22                    # normalized width
    h: float = 0.12                    # normalized height
    animation: MotionPathAnimation = field(default_factory=lambda: create_animation_preset("slide_left_right"))

    def to_dict(self) -> dict:
        return {
            "type": "sponsor_ad",
            "id": self.id,
            "name": self.name,
            "asset": self.asset,
            "qr_code_path": self.qr_code_path,
            "website_text": self.website_text,
            "brand_color": self.brand_color,
            "start": round(float(self.start_time), 2),
            "end": round(float(self.end_time), 2),
            "w": round(float(self.w), 3),
            "h": round(float(self.h), 3),
            "animation": self.animation.to_dict()
        }

    @classmethod
    def from_dict(cls, data: dict):
        anim_data = data.get("animation", {})
        anim = MotionPathAnimation.from_dict(anim_data) if anim_data else create_animation_preset("slide_left_right")
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Sponsor Brand"),
            asset=data.get("asset", ""),
            qr_code_path=data.get("qr_code_path", ""),
            website_text=data.get("website_text", ""),
            brand_color=data.get("brand_color", "#0ea5e9"),
            start_time=float(data.get("start", 10.0)),
            end_time=float(data.get("end", 22.0)),
            w=float(data.get("w", 0.22)),
            h=float(data.get("h", 0.12)),
            animation=anim
        )


# ---------------------------------------------------------------------------
# GLOBAL BRANDING & TEMPLATE PROFILE
# ---------------------------------------------------------------------------
@dataclass
class GlobalBrandingProfile:
    """
    Complete Branding & Template Profile:
    - Logo Watermark (Position, Size, Opacity, Animation)
    - Auto Intro / Outro video clips
    - Lower Third / Footer Title bar
    - List of Scheduled Sponsor Ads with Rotation
    - Aspect ratio template (16:9, 9:16, 1:1)
    """
    name: str = "Default YouTube Branding"
    aspect_ratio: str = "16:9"         # "16:9", "9:16", "1:1"
    
    # Logo Watermark
    enable_logo: bool = True
    logo_path: str = ""
    logo_position: str = "top_right"   # "top_right", "top_left", "bottom_right", "bottom_left", "custom"
    logo_x: float = 0.88
    logo_y: float = 0.10
    logo_size: float = 0.12            # relative size
    logo_opacity: float = 0.85
    logo_animation: str = "pulse"      # "none", "pulse", "fade", "rotate", "bounce"
    
    # Auto Intro & Outro
    enable_intro: bool = False
    intro_video_path: str = ""
    enable_outro: bool = False
    outro_video_path: str = ""
    
    # Lower Third / Footer Banner
    enable_footer: bool = False
    footer_text: str = ""
    footer_subtext: str = ""
    footer_color: str = "#0284c7"
    
    # Sponsor Ads & Rotations
    sponsors: List[SponsorAdItem] = field(default_factory=list)
    sponsor_rotation_enabled: bool = True
    sponsor_interval_mins: float = 3.0 # show sponsor every 3 minutes

    def to_json(self) -> str:
        data = {
            "name": self.name,
            "aspect_ratio": self.aspect_ratio,
            "enable_logo": self.enable_logo,
            "logo_path": self.logo_path,
            "logo_position": self.logo_position,
            "logo_x": self.logo_x,
            "logo_y": self.logo_y,
            "logo_size": self.logo_size,
            "logo_opacity": self.logo_opacity,
            "logo_animation": self.logo_animation,
            "enable_intro": self.enable_intro,
            "intro_video_path": self.intro_video_path,
            "enable_outro": self.enable_outro,
            "outro_video_path": self.outro_video_path,
            "enable_footer": self.enable_footer,
            "footer_text": self.footer_text,
            "footer_subtext": self.footer_subtext,
            "footer_color": self.footer_color,
            "sponsor_rotation_enabled": self.sponsor_rotation_enabled,
            "sponsor_interval_mins": self.sponsor_interval_mins,
            "sponsors": [sp.to_dict() for sp in self.sponsors]
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str):
        try:
            data = json.loads(json_str)
            sponsors = [SponsorAdItem.from_dict(sp) for sp in data.get("sponsors", [])]
            return cls(
                name=data.get("name", "Branding Profile"),
                aspect_ratio=data.get("aspect_ratio", "16:9"),
                enable_logo=bool(data.get("enable_logo", True)),
                logo_path=data.get("logo_path", ""),
                logo_position=data.get("logo_position", "top_right"),
                logo_x=float(data.get("logo_x", 0.88)),
                logo_y=float(data.get("logo_y", 0.10)),
                logo_size=float(data.get("logo_size", 0.12)),
                logo_opacity=float(data.get("logo_opacity", 0.85)),
                logo_animation=data.get("logo_animation", "pulse"),
                enable_intro=bool(data.get("enable_intro", False)),
                intro_video_path=data.get("intro_video_path", ""),
                enable_outro=bool(data.get("enable_outro", False)),
                outro_video_path=data.get("outro_video_path", ""),
                enable_footer=bool(data.get("enable_footer", False)),
                footer_text=data.get("footer_text", ""),
                footer_subtext=data.get("footer_subtext", ""),
                footer_color=data.get("footer_color", "#0284c7"),
                sponsor_rotation_enabled=bool(data.get("sponsor_rotation_enabled", True)),
                sponsor_interval_mins=float(data.get("sponsor_interval_mins", 3.0)),
                sponsors=sponsors
            )
        except Exception:
            return cls()
