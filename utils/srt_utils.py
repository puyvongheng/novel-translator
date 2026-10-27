"""
SRT & Subtitle Formatting Utilities
Supports robust parsing of UTF-8 / UTF-16 SRT files and generating valid SRT files.
"""

import os
import re
from typing import List, Dict
from utils.time_utils import format_timestamp, parse_timestamp_to_seconds

def is_khmer_text(text: str) -> bool:
    """Checks whether the string contains Khmer Unicode characters"""
    if not text:
        return False
    return any(('\u1780' <= ch <= '\u17ff') or ('\u19e0' <= ch <= '\u19ff') for ch in text)

def parse_srt_content(content: str) -> List[Dict]:
    """Parses SRT file content string into structured subtitle dictionaries"""
    if not content:
        return []

    lines = [line.strip() for line in content.splitlines()]
    subtitles = []
    current_block = []

    for line in lines:
        if not line:
            if current_block:
                _process_block(current_block, subtitles)
                current_block = []
        else:
            current_block.append(line)

    if current_block:
        _process_block(current_block, subtitles)

    return subtitles

def _process_block(block: List[str], out_list: List[Dict]):
    if not block:
        return

    # Find the line with the timestamp arrow '-->'
    time_idx = -1
    for idx, l in enumerate(block):
        if "-->" in l:
            time_idx = idx
            break

    if time_idx == -1:
        return

    timing = block[time_idx]
    try:
        parts = timing.split("-->")
        start_sec = parse_timestamp_to_seconds(parts[0].strip())
        end_sec = parse_timestamp_to_seconds(parts[1].strip())
    except Exception:
        return

    text_lines = block[time_idx + 1:]
    full_text = " ".join(text_lines).strip()

    # Determine if text is already Khmer
    khmer_val = full_text if is_khmer_text(full_text) else ""
    orig_val = "" if is_khmer_text(full_text) else full_text

    out_list.append({
        "id": len(out_list) + 1,
        "start": start_sec,
        "end": end_sec,
        "orig_text": orig_val,
        "khmer_text": khmer_val,
        "text": full_text
    })

def parse_srt_file(file_path: str) -> List[Dict]:
    """Reads SRT file with automatic encoding detection (utf-8, utf-8-sig, utf-16, cp1252)"""
    if not os.path.exists(file_path):
        return []

    for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "cp1252"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            return parse_srt_content(content)
        except Exception:
            continue
    return []

def generate_srt_content(subtitles: List[Dict]) -> str:
    """Generates standard SRT formatted text from subtitle items"""
    blocks = []
    for idx, sub in enumerate(subtitles, 1):
        st = format_timestamp(sub.get("start", 0.0))
        et = format_timestamp(sub.get("end", 0.0))
        text = sub.get("khmer_text") or sub.get("orig_text") or sub.get("text") or ""
        blocks.append(f"{idx}\n{st} --> {et}\n{text}\n")
    return "\n".join(blocks)

def parse_raw_srt_blocks(content: str) -> List[Dict]:
    """
    Faithfully parses SRT content preserving exact timing strings and multi-line text.
    Returns a list of cue dictionaries:
    [{'id': int, 'start_str': str, 'end_str': str, 'start': float, 'end': float, 'text': str}]
    """
    if not content:
        return []

    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    raw_blocks = re.split(r'\n\s*\n', content.strip())
    cues = []
    timing_pattern = re.compile(r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})')

    for block in raw_blocks:
        lines = [ln.strip() for ln in block.strip().split("\n") if ln.strip()]
        if not lines:
            continue

        time_idx = -1
        match = None
        for i, l in enumerate(lines):
            m = timing_pattern.search(l)
            if m:
                time_idx = i
                match = m
                break

        if time_idx == -1 or not match:
            continue

        start_str = match.group(1).replace(".", ",")
        end_str = match.group(2).replace(".", ",")
        start_sec = parse_timestamp_to_seconds(start_str)
        end_sec = parse_timestamp_to_seconds(end_str)

        cue_id = len(cues) + 1
        if time_idx > 0:
            try:
                cue_id = int(lines[0])
            except ValueError:
                pass

        dialogue_text = "\n".join(lines[time_idx + 1:])

        cues.append({
            "id": cue_id,
            "start_str": start_str,
            "end_str": end_str,
            "start": start_sec,
            "end": end_sec,
            "text": dialogue_text
        })

    return cues

def split_srt_file(
    file_path: str,
    chunk_size: int = 2000,
    output_dir: str = None,
    renumber: bool = True,
    prefix: str = None
) -> List[Dict]:
    """
    Splits an SRT file into multiple smaller SRT files with chunk_size cues each.
    Example: 6000 cues with chunk_size 2000 -> 3 files of 2000 cues each.
    
    Args:
        file_path: Path to the input SRT file
        chunk_size: Maximum subtitles/cues per output file (default 2000)
        output_dir: Target directory (defaults to [file_name]_split_parts/ next to input)
        renumber: If True, resets subtitle ID to 1..chunk_size in each file (recommended for AI)
        prefix: Custom prefix for output files (defaults to base file name)
        
    Returns:
        List of generated file metadata dictionaries.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SRT file not found: {file_path}")

    # Read content using robust encoding detection
    content = ""
    for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "cp1252"]:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
            if content:
                break
        except Exception:
            continue

    cues = parse_raw_srt_blocks(content)
    if not cues:
        # Fallback to standard parse_srt_file
        alt_cues = parse_srt_file(file_path)
        cues = []
        for c in alt_cues:
            txt = c.get("khmer_text") or c.get("orig_text") or c.get("text") or ""
            cues.append({
                "id": c.get("id", len(cues) + 1),
                "start_str": format_timestamp(c.get("start", 0.0)),
                "end_str": format_timestamp(c.get("end", 0.0)),
                "start": c.get("start", 0.0),
                "end": c.get("end", 0.0),
                "text": txt
            })

    total_cues = len(cues)
    if total_cues == 0:
        raise ValueError("No subtitle cues found in file.")

    chunk_size = max(1, int(chunk_size))
    
    # Calculate output directory
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    parent_dir = os.path.dirname(os.path.abspath(file_path))
    if not output_dir:
        output_dir = os.path.join(parent_dir, f"{base_name}_split_parts")
    os.makedirs(output_dir, exist_ok=True)

    prefix_str = prefix.strip() if prefix else base_name
    
    # Split into chunks
    num_parts = (total_cues + chunk_size - 1) // chunk_size
    pad_len = 2 if num_parts < 100 else len(str(num_parts))
    
    generated_files = []

    for part_idx in range(num_parts):
        start_idx = part_idx * chunk_size
        end_idx = min(start_idx + chunk_size, total_cues)
        part_cues = cues[start_idx:end_idx]

        part_num = part_idx + 1
        part_str = str(part_num).zfill(pad_len)
        out_filename = f"{prefix_str}_part{part_str}.srt"
        out_filepath = os.path.join(output_dir, out_filename)

        # Assemble SRT text
        lines = []
        for i, cue in enumerate(part_cues):
            cue_id = (i + 1) if renumber else cue["id"]
            lines.append(f"{cue_id}\n{cue['start_str']} --> {cue['end_str']}\n{cue['text']}\n")

        out_content = "\n".join(lines)
        with open(out_filepath, "w", encoding="utf-8") as fp:
            fp.write(out_content)

        file_size = os.path.getsize(out_filepath)
        generated_files.append({
            "part": part_num,
            "filename": out_filename,
            "file_path": out_filepath,
            "start_cue": start_idx + 1,
            "end_cue": end_idx,
            "count": len(part_cues),
            "start_time": part_cues[0]["start_str"] if part_cues else "00:00:00,000",
            "end_time": part_cues[-1]["end_str"] if part_cues else "00:00:00,000",
            "file_size": file_size
        })

    return generated_files

def merge_srt_files(
    file_paths: List[str],
    output_path: str,
    renumber: bool = True
) -> Dict:
    """
    Merges multiple SRT files in sequence into a single master SRT file.
    
    Args:
        file_paths: Ordered list of SRT file paths
        output_path: Target destination for the merged SRT file
        renumber: If True, renumbers IDs continuously from 1..N
        
    Returns:
        Metadata dict of the merged file.
    """
    if not file_paths:
        raise ValueError("No SRT files provided to merge.")

    all_cues = []
    for fp in file_paths:
        if not os.path.exists(fp):
            continue
        content = ""
        for enc in ["utf-8-sig", "utf-8", "utf-16", "gbk", "cp1252"]:
            try:
                with open(fp, "r", encoding=enc) as f:
                    content = f.read()
                if content:
                    break
            except Exception:
                continue
        file_cues = parse_raw_srt_blocks(content)
        all_cues.extend(file_cues)

    if not all_cues:
        raise ValueError("Could not parse any subtitle cues from provided files.")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    lines = []
    for i, cue in enumerate(all_cues):
        cue_id = (i + 1) if renumber else cue["id"]
        lines.append(f"{cue_id}\n{cue['start_str']} --> {cue['end_str']}\n{cue['text']}\n")

    merged_content = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as fp:
        fp.write(merged_content)

    return {
        "file_path": output_path,
        "filename": os.path.basename(output_path),
        "total_cues": len(all_cues),
        "start_time": all_cues[0]["start_str"] if all_cues else "00:00:00,000",
        "end_time": all_cues[-1]["end_str"] if all_cues else "00:00:00,000",
        "file_size": os.path.getsize(output_path)
    }

# Backward compatibility alias
parse_srt = parse_srt_file


def fix_overlapping_subtitles(subtitles: List[Dict], min_gap: float = 0.0, min_dur: float = 0.5) -> tuple:
    """
    Auto-corrects overlapping subtitle cues.
    Example:
      Line 1: 00:20 - 00:30
      Line 2: 00:25 - 00:40
    Result:
      Line 1: 00:20 - 00:30
      Line 2: 00:30 - 00:40  (shifted start to previous line's end)
    
    If the next line is completely inside the current line (e.g. 00:25-00:28),
    its end is shifted accordingly to preserve dialogue duration.
    
    Returns:
        (updated_subtitles_list, count_of_fixed_lines)
    """
    if not subtitles or len(subtitles) < 2:
        return subtitles, 0

    fixed_count = 0
    for i in range(len(subtitles) - 1):
        curr_sub = subtitles[i]
        next_sub = subtitles[i + 1]

        curr_end = float(curr_sub.get("end", 0.0))
        next_start = float(next_sub.get("start", 0.0))
        next_end = float(next_sub.get("end", next_start + 1.0))

        # Check for overlap: next line starts before current line ends
        if next_start < curr_end:
            fixed_count += 1
            orig_next_dur = max(min_dur, next_end - next_start)
            new_start = round(curr_end + min_gap, 3)

            # If original end has enough space after new_start, keep original end;
            # otherwise push new_end so the dialogue has at least orig_next_dur.
            if next_end >= new_start + min_dur:
                new_end = round(next_end, 3)
            else:
                new_end = round(new_start + orig_next_dur, 3)

            next_sub["start"] = new_start
            next_sub["end"] = new_end

    return subtitles, fixed_count
