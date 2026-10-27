"""
Video Segment Editor & Timeline Clip Manipulation Service
Handles:
1. Non-destructive splitting & trimming
2. Auto-split by duration (5 min, 10 min, 30 min, custom)
3. Ripple delete (removes section and auto-shifts subsequent items to close the gap)
4. Fast lossless range extraction (-c copy)
5. Batch segment export
6. Segment concatenation & merging
"""

import os
import subprocess
import tempfile
import time
from typing import List, Dict, Optional, Callable, Tuple


class SegmentEditorService:
    """
    Non-destructive video segmentation, range extraction, and batch rendering engine.
    """

    @staticmethod
    def auto_split_intervals(total_duration: float, interval_seconds: float) -> List[Dict]:
        """
        Calculates non-destructive virtual segment cut intervals.
        Example: duration=1800s, interval=300s (5min) -> 6 segments.
        """
        if total_duration <= 0 or interval_seconds <= 0:
            return []

        segments = []
        cur_start = 0.0
        seg_idx = 1

        while cur_start < total_duration - 0.5:
            cur_end = min(total_duration, cur_start + interval_seconds)
            dur = cur_end - cur_start
            if dur < 1.0:
                break
            segments.append({
                "id": seg_idx,
                "name": f"Part {seg_idx:02d}",
                "start": round(cur_start, 3),
                "end": round(cur_end, 3),
                "duration": round(dur, 3),
                "timeline_start": round(cur_start, 3)
            })
            cur_start = cur_end
            seg_idx += 1

        return segments

    @staticmethod
    def ripple_delete_range(
        subtitles: List[Dict],
        clips: List[Dict],
        del_start: float,
        del_end: float
    ) -> Tuple[List[Dict], List[Dict], float]:
        """
        Removes items inside [del_start, del_end], trims intersecting items,
        and shifts all subsequent items left by (del_end - del_start) to close the gap!
        Returns (new_subtitles, new_clips, shift_amount).
        """
        shift_amount = max(0.0, del_end - del_start)
        if shift_amount < 0.05:
            return subtitles, clips, 0.0

        new_subs = []
        for s in subtitles:
            st = float(s.get("start", 0.0))
            et = float(s.get("end", st + 0.1))

            # Case 1: Completely before deleted range -> unchanged
            if et <= del_start:
                new_subs.append(dict(s))
            # Case 2: Completely after deleted range -> shifted left by shift_amount
            elif st >= del_end:
                sub_copy = dict(s)
                sub_copy["start"] = max(0.0, round(st - shift_amount, 3))
                sub_copy["end"] = max(sub_copy["start"] + 0.1, round(et - shift_amount, 3))
                new_subs.append(sub_copy)
            # Case 3: Completely inside deleted range -> dropped!
            elif st >= del_start and et <= del_end:
                continue
            # Case 4: Overlaps start of delete range -> trimmed to del_start
            elif st < del_start and et > del_start and et <= del_end:
                sub_copy = dict(s)
                sub_copy["end"] = round(del_start, 3)
                if sub_copy["end"] - sub_copy["start"] >= 0.2:
                    new_subs.append(sub_copy)
            # Case 5: Overlaps end of delete range -> trimmed and shifted
            elif st >= del_start and st < del_end and et > del_end:
                sub_copy = dict(s)
                sub_copy["start"] = round(del_start, 3)
                sub_copy["end"] = round(del_start + (et - del_end), 3)
                if sub_copy["end"] - sub_copy["start"] >= 0.2:
                    new_subs.append(sub_copy)
            # Case 6: Straddles entire delete range -> split or shortened by shift_amount
            elif st < del_start and et > del_end:
                sub_copy = dict(s)
                sub_copy["end"] = round(et - shift_amount, 3)
                new_subs.append(sub_copy)

        # Re-number subtitle indices
        for i, sub in enumerate(new_subs):
            sub["index"] = i + 1

        # Adjust video clips if any
        new_clips = []
        for c in clips:
            st = float(c.get("timeline_start", 0.0))
            dur = float(c.get("duration", 0.0))
            et = st + dur

            if et <= del_start:
                new_clips.append(dict(c))
            elif st >= del_end:
                c_copy = dict(c)
                c_copy["timeline_start"] = max(0.0, round(st - shift_amount, 3))
                new_clips.append(c_copy)
            elif st >= del_start and et <= del_end:
                continue
            else:
                c_copy = dict(c)
                if st < del_start:
                    keep_dur = del_start - st
                    c_copy["duration"] = round(keep_dur, 3)
                    c_copy["end"] = round(c_copy.get("start", 0.0) + keep_dur, 3)
                else:
                    offset = del_end - st
                    c_copy["start"] = round(c_copy.get("start", 0.0) + offset, 3)
                    c_copy["duration"] = round(dur - offset, 3)
                    c_copy["timeline_start"] = round(del_start, 3)
                if c_copy["duration"] >= 0.2:
                    new_clips.append(c_copy)

        return new_subs, new_clips, shift_amount

    @staticmethod
    def extract_range_lossless(
        input_video: str,
        output_video: str,
        start_sec: float,
        end_sec: float,
        progress_cb: Optional[Callable[[str, float], None]] = None
    ) -> bool:
        """
        Fast lossless stream copy (-c copy) of the given range in < 2 seconds without re-encoding!
        """
        if not input_video or not os.path.exists(input_video):
            return False

        dur = max(0.1, end_sec - start_sec)
        os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)

        if progress_cb:
            progress_cb("Extracting selected range (Lossless Stream Copy)...", 0.1)

        # -ss before -i for fast keyframe seek, -to for precise end
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_sec:.3f}",
            "-to", f"{end_sec:.3f}",
            "-i", input_video,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_video
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 1000:
                if progress_cb:
                    progress_cb("Range extracted successfully!", 1.0)
                return True
        except Exception:
            pass

        # Fallback to fast ultrafast re-encode if stream copy fails on non-keyframe cut
        if progress_cb:
            progress_cb("Re-encoding cut boundary smoothly...", 0.4)

        fallback_cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start_sec:.3f}",
            "-to", f"{end_sec:.3f}",
            "-i", input_video,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            output_video
        ]

        try:
            res = subprocess.run(fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            ok = res.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 1000
            if progress_cb and ok:
                progress_cb("Range extracted successfully!", 1.0)
            return ok
        except Exception:
            return False

    @staticmethod
    def export_segments_batch(
        input_video: str,
        segments: List[Dict],
        output_dir: str,
        base_filename: str = "segment",
        progress_cb: Optional[Callable[[str, float], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> List[str]:
        """
        Batch-exports all segments sequentially.
        Returns list of exported file paths.
        """
        if not input_video or not os.path.exists(input_video) or not segments:
            return []

        os.makedirs(output_dir, exist_ok=True)
        total = len(segments)
        exported = []

        for i, seg in enumerate(segments):
            if is_cancelled and is_cancelled():
                break

            s_start = float(seg.get("start", 0.0))
            s_end = float(seg.get("end", s_start + 1.0))
            seg_title = seg.get("name") or f"Part {i+1:02d}"
            clean_title = "".join(c for c in seg_title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")

            out_name = f"{base_filename}_{i+1:02d}_{clean_title}.mp4"
            out_path = os.path.join(output_dir, out_name)

            pct = i / float(total)
            if progress_cb:
                progress_cb(f"Exporting segment {i+1}/{total}: {out_name}...", pct)

            ok = SegmentEditorService.extract_range_lossless(input_video, out_path, s_start, s_end)
            if ok:
                exported.append(out_path)

        if progress_cb:
            progress_cb(f"Exported {len(exported)}/{total} segments successfully!", 1.0)

        return exported

    @staticmethod
    def merge_video_segments(
        segment_files: List[str],
        output_video: str,
        progress_cb: Optional[Callable[[str, float], None]] = None
    ) -> bool:
        """
        Merges / concatenates multiple video segment MP4 files into one continuous file.
        Uses FFmpeg concat demuxer for lossless instant merging.
        """
        valid_files = [f for f in segment_files if f and os.path.exists(f) and os.path.getsize(f) > 1000]
        if not valid_files:
            return False

        os.makedirs(os.path.dirname(os.path.abspath(output_video)), exist_ok=True)

        if progress_cb:
            progress_cb("Merging segments into single video...", 0.2)

        # Create temporary file list for concat demuxer
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fp:
            for vf in valid_files:
                # Escape single quotes and use forward slashes
                esc_path = os.path.abspath(vf).replace("\\", "/").replace("'", "'\\''")
                fp.write(f"file '{esc_path}'\n")
            list_file = fp.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                output_video
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 1000:
                if progress_cb:
                    progress_cb("Segments merged successfully!", 1.0)
                return True
        except Exception:
            pass
        finally:
            if os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except Exception:
                    pass

        # Fallback to re-encoding concat filter if codec parameters differ
        if progress_cb:
            progress_cb("Standardizing & merging video streams...", 0.5)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fp:
            for vf in valid_files:
                esc_path = os.path.abspath(vf).replace("\\", "/").replace("'", "'\\''")
                fp.write(f"file '{esc_path}'\n")
            list_file = fp.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                output_video
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            ok = res.returncode == 0 and os.path.exists(output_video) and os.path.getsize(output_video) > 1000
            if progress_cb and ok:
                progress_cb("Segments merged successfully!", 1.0)
            return ok
        except Exception:
            return False
        finally:
            if os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except Exception:
                    pass
