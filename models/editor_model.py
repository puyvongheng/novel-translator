import os
import copy
from utils import get_video_info

class EditorModel:
    """
    Non-Linear Video Editor State Model:
    - Multiple Video Clips (Video A, Video B, Video C...)
    - Split, Trim (In/Out), Delete, Reorder clips
    - Multi-Track Audio (Original Video, Khmer Dub, Background Music) with Volume & Mute
    - Color Grading & Video Filters (Brightness, Contrast, Saturation, Speed)
    - Watermark / Logo / GFX image overlay
    - Full Undo / Redo history
    """
    def __init__(self):
        self.clips = []
        self.bg_music = {
            "path": None,
            "name": "No music loaded",
            "volume": 0.35,
            "is_muted": False,
            "timeline_start": 0.0,
            "duration": 0.0
        }
        self.audio_settings = {
            "orig_vol": 0.85,
            "duck_vol": 0.15,
            "auto_ducking": True,
            "mute_orig": False,
            "dub_vol": 1.0,
            "mute_dub": False,
            "bgm_vol": 0.35,
            "mute_bgm": False
        }
        # Dynamic N CC (Subtitle) Tracks
        self.cc_tracks = [
            {"id": 0, "name": "CC 1 (Khmer)", "color": "#db2777", "subtitles": []}
        ]
        # Dynamic N Audio Tracks (Audio 1, Audio 2, Audio 3... Audio N)
        self.audio_tracks = [
            {"id": 0, "name": "Audio 1 (Original Video)", "type": "original", "path": None, "volume": 0.85, "is_muted": False, "color": "#0d9488", "clips": []},
            {"id": 1, "name": "Audio 2 (Khmer Dub)", "type": "dub", "path": None, "volume": 1.0, "is_muted": False, "color": "#14b8a6", "clips": []},
            {"id": 2, "name": "Audio 3 (Music BGM)", "type": "bgm", "path": None, "volume": 0.35, "is_muted": False, "color": "#d97706", "clips": []}
        ]
        self.watermark = {
            "path": None,
            "pos": "Top-Right (លើ ស្ដាំ)",
            "scale": 0.15,
            "opacity": 1.0,
            "rel_x": 0.90,
            "rel_y": 0.10
        }
        self.video_filters = {
            "brightness": 0.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "speed": 1.0
        }
        self.active_font = "Leelawadee UI"
        self.active_clip_idx = 0
        self.cc_style = {
            "animation": "karaoke",
            "bg_style": "Black Box 50% (ប្រអប់ខ្មៅស្រាល)",
            "highlight_color": "Gold / Yellow (លឿងទុំ)",
            "border_width": 3
        }

        self.undo_stack = []
        self.redo_stack = []

    def save_state(self):
        """Saves deep copy of current editable state for Undo"""
        snapshot = {
            "clips": copy.deepcopy(self.clips),
            "bg_music": copy.deepcopy(self.bg_music),
            "audio_settings": copy.deepcopy(self.audio_settings),
            "cc_tracks": copy.deepcopy(self.cc_tracks),
            "audio_tracks": copy.deepcopy(self.audio_tracks),
            "watermark": copy.deepcopy(self.watermark),
            "video_filters": copy.deepcopy(self.video_filters),
            "active_font": self.active_font,
            "active_clip_idx": self.active_clip_idx,
            "cc_style": copy.deepcopy(self.cc_style)
        }
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        current_state = {
            "clips": copy.deepcopy(self.clips),
            "bg_music": copy.deepcopy(self.bg_music),
            "audio_settings": copy.deepcopy(self.audio_settings),
            "cc_tracks": copy.deepcopy(self.cc_tracks),
            "audio_tracks": copy.deepcopy(self.audio_tracks),
            "watermark": copy.deepcopy(self.watermark),
            "video_filters": copy.deepcopy(self.video_filters),
            "active_font": self.active_font,
            "active_clip_idx": self.active_clip_idx,
            "cc_style": copy.deepcopy(self.cc_style)
        }
        self.redo_stack.append(current_state)
        prev = self.undo_stack.pop()
        self.clips = prev["clips"]
        self.bg_music = prev["bg_music"]
        self.audio_settings = prev["audio_settings"]
        self.cc_tracks = prev.get("cc_tracks", self.cc_tracks)
        self.audio_tracks = prev.get("audio_tracks", self.audio_tracks)
        self.watermark = prev["watermark"]
        self.video_filters = prev["video_filters"]
        self.active_font = prev.get("active_font", "Leelawadee UI")
        self.active_clip_idx = prev.get("active_clip_idx", 0)
        self.cc_style = prev.get("cc_style", self.cc_style)
        self._recalculate_timeline_starts()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        current_state = {
            "clips": copy.deepcopy(self.clips),
            "bg_music": copy.deepcopy(self.bg_music),
            "audio_settings": copy.deepcopy(self.audio_settings),
            "cc_tracks": copy.deepcopy(self.cc_tracks),
            "audio_tracks": copy.deepcopy(self.audio_tracks),
            "watermark": copy.deepcopy(self.watermark),
            "video_filters": copy.deepcopy(self.video_filters),
            "active_font": self.active_font,
            "active_clip_idx": self.active_clip_idx,
            "cc_style": copy.deepcopy(self.cc_style)
        }
        self.undo_stack.append(current_state)
        next_state = self.redo_stack.pop()
        self.clips = next_state["clips"]
        self.bg_music = next_state["bg_music"]
        self.audio_settings = next_state["audio_settings"]
        self.cc_tracks = next_state.get("cc_tracks", self.cc_tracks)
        self.audio_tracks = next_state.get("audio_tracks", self.audio_tracks)
        self.watermark = next_state["watermark"]
        self.video_filters = next_state["video_filters"]
        self.active_font = next_state.get("active_font", "Leelawadee UI")
        self.active_clip_idx = next_state.get("active_clip_idx", 0)
        self.cc_style = next_state.get("cc_style", self.cc_style)
        self._recalculate_timeline_starts()
        return True

    # ------------------ DYNAMIC AUDIO & CC TRACKS ------------------
    def add_audio_track(self, name: str = None, track_type: str = "custom", path: str = None, volume: float = 0.8, color: str = None) -> int:
        """Adds a new dynamic Audio track (Audio 1, Audio 2, Audio 3... Audio N)"""
        self.save_state()
        new_id = len(self.audio_tracks)
        palette = ["#0d9488", "#14b8a6", "#d97706", "#7c3aed", "#2563eb", "#059669", "#dc2626", "#ea580c"]
        chosen_color = color if color else palette[new_id % len(palette)]
        track_name = name if name else f"Audio {new_id + 1}"
        new_track = {
            "id": new_id,
            "name": track_name,
            "type": track_type,
            "path": path,
            "volume": volume,
            "is_muted": False,
            "color": chosen_color,
            "clips": []
        }
        self.audio_tracks.append(new_track)
        return new_id

    def delete_audio_track(self, idx: int) -> bool:
        """Removes an audio track (keeps at least 1 track)"""
        if len(self.audio_tracks) <= 1 or not (0 <= idx < len(self.audio_tracks)):
            return False
        self.save_state()
        self.audio_tracks.pop(idx)
        for i, trk in enumerate(self.audio_tracks):
            trk["id"] = i
        return True

    def toggle_audio_track_mute(self, idx: int) -> bool:
        if 0 <= idx < len(self.audio_tracks):
            self.save_state()
            self.audio_tracks[idx]["is_muted"] = not self.audio_tracks[idx]["is_muted"]
            return self.audio_tracks[idx]["is_muted"]
        return False

    def set_audio_track_volume(self, idx: int, volume: float):
        if 0 <= idx < len(self.audio_tracks):
            self.audio_tracks[idx]["volume"] = max(0.0, min(2.0, volume))

    def add_cc_track(self, name: str = None, color: str = None) -> int:
        """Adds a new dynamic Subtitle / CC track (CC 1, CC 2... CC N)"""
        self.save_state()
        new_id = len(self.cc_tracks)
        palette = ["#db2777", "#8b5cf6", "#ec4899", "#f43f5e", "#a855f7", "#06b6d4"]
        chosen_color = color if color else palette[new_id % len(palette)]
        track_name = name if name else f"CC {new_id + 1}"
        new_track = {
            "id": new_id,
            "name": track_name,
            "color": chosen_color,
            "subtitles": []
        }
        self.cc_tracks.append(new_track)
        return new_id

    def delete_cc_track(self, idx: int) -> bool:
        if len(self.cc_tracks) <= 1 or not (0 <= idx < len(self.cc_tracks)):
            return False
        self.save_state()
        self.cc_tracks.pop(idx)
        for i, trk in enumerate(self.cc_tracks):
            trk["id"] = i
        return True

    def set_primary_video(self, video_path: str, duration: float, width: int = 1280, height: int = 720, fps: float = 30.0):
        self.save_state()
        self.clips = [{
            "id": 0,
            "path": video_path,
            "name": "Video A",
            "start": 0.0,
            "end": duration,
            "duration": duration,
            "timeline_start": 0.0,
            "width": width,
            "height": height,
            "fps": fps
        }]
        self.active_clip_idx = 0

    def add_clip(self, video_path: str, duration: float, name: str = None) -> int:
        self.save_state()
        info = get_video_info(video_path)
        clip_letter = chr(ord('A') + len(self.clips)) if len(self.clips) < 26 else str(len(self.clips) + 1)
        clip_name = name if name else f"Video {clip_letter}"
        new_clip = {
            "id": len(self.clips),
            "path": video_path,
            "name": clip_name,
            "start": 0.0,
            "end": duration,
            "duration": duration,
            "timeline_start": self.get_total_duration(),
            "width": info.get("width", 1280),
            "height": info.get("height", 720),
            "fps": info.get("fps", 30.0)
        }
        self.clips.append(new_clip)
        self._recalculate_timeline_starts()
        self.active_clip_idx = len(self.clips) - 1
        return self.active_clip_idx

    def split_clip_at(self, timeline_time_sec: float) -> bool:
        """Splits the active video clip at the given timeline timestamp into two parts"""
        if not self.clips:
            return False

        # Find which clip contains timeline_time_sec
        target_idx = None
        for i, c in enumerate(self.clips):
            t_start = c["timeline_start"]
            t_end = t_start + c["duration"]
            if t_start < timeline_time_sec < t_end:
                target_idx = i
                break

        if target_idx is None:
            return False

        self.save_state()
        c = self.clips[target_idx]
        split_offset = timeline_time_sec - c["timeline_start"]
        cut_point = c["start"] + split_offset

        part1_dur = cut_point - c["start"]
        part2_dur = c["end"] - cut_point

        if part1_dur < 0.2 or part2_dur < 0.2:
            return False

        c_name = c.get("name", "Clip")
        part1 = copy.deepcopy(c)
        part1["name"] = f"{c_name} (1)"
        part1["end"] = cut_point
        part1["duration"] = part1_dur

        part2 = copy.deepcopy(c)
        part2["name"] = f"{c_name} (2)"
        part2["start"] = cut_point
        part2["duration"] = part2_dur

        self.clips.pop(target_idx)
        self.clips.insert(target_idx, part2)
        self.clips.insert(target_idx, part1)
        self._recalculate_timeline_starts()
        self.active_clip_idx = target_idx
        return True

    def trim_active_clip(self, trim_start_delta: float = 0.0, trim_end_delta: float = 0.0) -> bool:
        """Trims start or end of active clip"""
        if not self.clips or not (0 <= self.active_clip_idx < len(self.clips)):
            return False
        self.save_state()
        c = self.clips[self.active_clip_idx]
        new_start = max(0.0, c["start"] + trim_start_delta)
        new_end = max(new_start + 0.3, c["end"] + trim_end_delta)
        c["start"] = new_start
        c["end"] = new_end
        c["duration"] = new_end - new_start
        self._recalculate_timeline_starts()
        return True

    def delete_active_clip(self) -> bool:
        """Deletes currently selected video clip"""
        if len(self.clips) <= 1:
            return False  # Keep at least one clip
        self.save_state()
        self.clips.pop(self.active_clip_idx)
        self.active_clip_idx = max(0, self.active_clip_idx - 1)
        self._recalculate_timeline_starts()
        return True

    def _recalculate_timeline_starts(self):
        t = 0.0
        for i, c in enumerate(self.clips):
            c["timeline_start"] = t
            c["id"] = i
            t += c["duration"]

    def get_total_duration(self) -> float:
        if not self.clips:
            return 1.0
        return sum(c["duration"] for c in self.clips)

    def get_clip_at_time(self, timeline_sec: float):
        """Returns (clip_dict, local_time_sec) for video rendering"""
        if not self.clips:
            return None, 0.0
        for c in self.clips:
            t_start = c["timeline_start"]
            t_end = t_start + c["duration"]
            if t_start <= timeline_sec < t_end:
                local_time = c["start"] + (timeline_sec - t_start)
                return c, local_time
        # Edge case: at or past end
        last_clip = self.clips[-1]
        return last_clip, last_clip["end"]

    def set_bg_music(self, audio_path: str, duration: float):
        self.save_state()
        self.bg_music["path"] = audio_path
        self.bg_music["name"] = os.path.basename(audio_path)
        self.bg_music["duration"] = duration
        self.bg_music["timeline_start"] = 0.0

    def set_watermark(self, image_path: str, pos: str = "Top-Right (លើ ស្ដាំ)", scale: float = 0.15, opacity: float = 1.0, rel_x: float = None, rel_y: float = None):
        self.save_state()
        self.watermark["path"] = image_path
        self.watermark["pos"] = pos
        self.watermark["scale"] = scale
        self.watermark["opacity"] = opacity
        if rel_x is not None:
            self.watermark["rel_x"] = rel_x
        if rel_y is not None:
            self.watermark["rel_y"] = rel_y

    def set_filters(self, brightness: float = None, contrast: float = None, saturation: float = None, speed: float = None):
        if brightness is not None:
            self.video_filters["brightness"] = brightness
        if contrast is not None:
            self.video_filters["contrast"] = contrast
        if saturation is not None:
            self.video_filters["saturation"] = saturation
        if speed is not None:
            self.video_filters["speed"] = speed
