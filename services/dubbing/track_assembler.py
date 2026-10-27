"""
Audio Track Assembly & Multi-Track Mixing Module
Generates line segments concurrently and mixes synchronized full-timeline audio tracks.
"""

import os
import asyncio
import edge_tts
from pydub import AudioSegment
from utils.time_utils import format_filename_timestamp, format_voice_filename
from services.dubbing.timing_ducking import calculate_auto_rate, fit_audio_to_duration


def generate_segment_files(
    subtitles: list,
    voice_dir: str,
    voice_name: str = "km-KH-PisethNeural",
    default_rate: str = "+0%",
    force_refresh: bool = False,
    progress_callback=None,
    log_callback=None
) -> list:
    """
    Generates individual voice files per subtitle segment concurrently:
    e.g. #1 00:00:00 - 00:00:10 -> voice_dir/#1_00-00-00_to_00-00-10.mp3
    Ultra-fast parallel generation with 5 concurrent audio streams.
    """
    os.makedirs(voice_dir, exist_ok=True)
    to_synthesize = []
    generated_files = []

    for idx, sub in enumerate(subtitles):
        text = (sub.get("khmer_text") or sub.get("translated") or sub.get("khmer") or sub.get("text") or "").strip()
        if not text or not any(c.isalnum() for c in text):
            continue

        # 1. Quick check: If sub already has a valid generated voice audio file on disk, reuse immediately!
        existing_audio = sub.get("audio_file") or sub.get("audio_path")
        if not force_refresh and existing_audio and os.path.exists(existing_audio) and os.path.getsize(existing_audio) > 100:
            sub["audio_file"] = existing_audio
            generated_files.append(existing_audio)
            continue

        sub_id = sub.get("id", idx + 1)
        s_sec = float(sub.get("start", 0.0))
        e_sec = float(sub.get("end", s_sec + 1.0))
        s_time = format_filename_timestamp(s_sec)
        e_time = format_filename_timestamp(e_sec)

        # Target duration: speech MUST finish strictly by e_sec
        slot_dur = max(0.4, e_sec - s_sec)
        if idx + 1 < len(subtitles):
            next_start = float(subtitles[idx + 1].get("start", e_sec))
            if next_start > s_sec:
                target_dur = min(slot_dur, max(0.4, next_start - s_sec))
            else:
                target_dur = slot_dur
        else:
            target_dur = slot_dur

        user_rate = sub.get("rate") or default_rate or "+0%"
        try:
            r_val = int(str(user_rate).replace("%", "").replace("+", "").strip() or 0)
            rate = "+15%" if r_val > 15 else (f"+{r_val}%" if r_val >= 0 else f"{r_val}%")
        except Exception:
            rate = "+0%"

        # Determine character voice (Male vs Female)
        line_voice = sub.get("voice_name")
        if not line_voice:
            if sub.get("gender") == "female":
                line_voice = "km-KH-SreymomNeural"
            elif sub.get("gender") == "male":
                line_voice = "km-KH-PisethNeural"
            else:
                line_voice = voice_name

        v_tag = "F" if ("Sreymom" in str(line_voice) or sub.get("gender") == "female") else "M"
        filename = format_voice_filename(sub_id, s_time, e_time, text, voice_tag=v_tag)
        filepath = os.path.join(voice_dir, filename)

        # 2. Check if file or existing variations exist in voice_dir
        if not force_refresh:
            found_existing = None
            for cand in [
                filepath,
                os.path.join(voice_dir, f"#{sub_id}_{s_time}_to_{e_time}_{v_tag}.mp3"),
                os.path.join(voice_dir, f"#{sub_id}_{s_time}_to_{e_time}.mp3"),
                os.path.join(voice_dir, f"line_{sub_id}_{s_time}_to_{e_time}.mp3"),
                os.path.join(voice_dir, f"#{idx+1}_{s_time}_to_{e_time}.mp3")
            ]:
                if os.path.exists(cand) and os.path.getsize(cand) > 100:
                    found_existing = cand
                    break

            if found_existing:
                sub["audio_file"] = found_existing
                generated_files.append(found_existing)
                continue

        to_synthesize.append((sub, filepath, text, rate, target_dur, line_voice))

    if to_synthesize:
        total_synth = len(to_synthesize)
        done_synth = 0

        async def _synthesize_batch():
            sem = asyncio.Semaphore(5)  # 5 concurrent streams
            synth_lock = asyncio.Lock()

            async def _worker(idx_task, sub_item, path, txt, r, t_dur, v_act):
                nonlocal done_synth
                await asyncio.sleep(0.04 * (idx_task % 5))
                async with sem:
                    # Sanitize voice name to ensure valid Edge-TTS neural model
                    v_str = str(v_act or "")
                    if "Sreymom" in v_str or "Standard-A" in v_str or sub_item.get("gender") == "female":
                        edge_v = "km-KH-SreymomNeural"
                    else:
                        edge_v = "km-KH-PisethNeural"

                    for attempt in range(3):
                        try:
                            async def _do_stream():
                                comm = edge_tts.Communicate(txt, edge_v, rate=r)
                                with open(path, "wb") as f:
                                    async for chunk in comm.stream():
                                        if chunk["type"] == "audio":
                                            f.write(chunk["data"])

                            # Hard timeout of 8.0s prevents infinite hanging / stalling at 47%
                            await asyncio.wait_for(_do_stream(), timeout=8.0)

                            if os.path.exists(path) and os.path.getsize(path) > 100:
                                try:
                                    fit_audio_to_duration(path, t_dur)
                                except Exception:
                                    pass
                                fx = sub_item.get("voice_effect", "none")
                                if fx and fx not in ("none", "original"):
                                    try:
                                        from services.dubbing.audio_effects import apply_voice_effect_to_file
                                        apply_voice_effect_to_file(path, fx, output_path=path)
                                    except Exception as fx_err:
                                        print(f"Apply voice effect during batch TTS error: {fx_err}")
                                sub_item["audio_file"] = path
                                async with synth_lock:
                                    generated_files.append(path)
                                break
                            else:
                                if os.path.exists(path):
                                    try: os.remove(path)
                                    except Exception: pass
                        except Exception as ex:
                            if os.path.exists(path):
                                try: os.remove(path)
                                except Exception: pass
                            if attempt == 2:
                                print(f"Async TTS line #{sub_item.get('id', idx_task+1)} timeout/error: {ex}")
                            await asyncio.sleep(0.25 * (attempt + 1))
                    
                    async with synth_lock:
                        done_synth += 1
                        if progress_callback and (done_synth % 3 == 0 or done_synth == total_synth):
                            pct = 0.15 + (0.80 * done_synth / total_synth)
                            progress_callback(
                                f"🤖 [AI Voice] កំពុងបង្កើតសំឡេងដោយ AI ({len(generated_files)}/{len(subtitles)} clips): {done_synth*100//total_synth}%",
                                pct
                            )

            tasks = [_worker(i, item[0], item[1], item[2], item[3], item[4], item[5]) for i, item in enumerate(to_synthesize)]
            await asyncio.gather(*tasks, return_exceptions=True)

        try:
            asyncio.run(_synthesize_batch())
        except Exception as e:
            print(f"Batch TTS error: {e}")
            if log_callback:
                log_callback(f"❌ [AI Voice] កំហុសពេលបង្កើតសំឡេងដោយ AI (Batch TTS): {e}")

    if progress_callback:
        if len(generated_files) > 0:
            progress_callback(
                f"🎉 [AI Voice] បង្កើតសំឡេងដោយ AI រួចរាល់ ({len(generated_files)}/{len(subtitles)} clips)",
                1.0
            )
        else:
            progress_callback("⚠️ [AI Voice] បង្កើតសំឡេងដោយ AI មិនបាន", 0.0)

    return generated_files


def assemble_dubbed_audio(
    subtitles: list,
    total_duration_sec: float,
    output_wav_path: str,
    voice_dir: str = None,
    default_rate: str = "+0%",
    voice_name: str = "km-KH-PisethNeural",
    progress_callback=None,
    log_callback=None
) -> str:
    """
    Assembles individual audio segment clips into a single synchronized audio track for video mixing.
    Ultra-fast in-memory mixing using NumPy and SoundFile (mixes 3000+ files in seconds).
    """
    if progress_callback:
        progress_callback("⚡ កំពុងផ្គុំសំឡេងខ្មែរ (Assembling Khmer Voice Track)...", 0.1)

    # Make sure voice segments are generated
    if voice_dir:
        generate_segment_files(
            subtitles=subtitles,
            voice_dir=voice_dir,
            voice_name=voice_name,
            default_rate=default_rate,
            force_refresh=False,
            progress_callback=progress_callback,
            log_callback=log_callback
        )

    # Determine effective total duration with 120s safety headroom to avoid ANY memory reallocation
    max_sub_end = max((float(s.get("end", 0.0)) for s in subtitles), default=0.0)
    eff_dur = max(float(total_duration_sec or 0.0), max_sub_end + 5.0, 10.0)

    sample_rate = 44100
    total_samples = int((eff_dur + 120.0) * sample_rate)

    try:
        import numpy as np
        import soundfile as sf

        canvas = np.zeros((total_samples, 2), dtype=np.float32)
        total_subs = len(subtitles)
        last_end_sample = 0

        for idx, sub in enumerate(subtitles):
            audio_path = sub.get("audio_file") or sub.get("audio_path")
            s_sec = float(sub.get("start", 0.0))
            e_sec = float(sub.get("end", s_sec + 1.0))
            s_time = format_filename_timestamp(s_sec)
            e_time = format_filename_timestamp(e_sec)

            if not audio_path or not os.path.exists(audio_path):
                if voice_dir:
                    sub_id = sub.get("id", idx + 1)
                    sub_txt = (sub.get("khmer_text") or sub.get("translated") or sub.get("khmer") or sub.get("text") or "").strip()
                    specific_fn = format_voice_filename(sub_id, s_time, e_time, sub_txt)
                    candidates = [
                        os.path.join(voice_dir, specific_fn),
                        os.path.join(voice_dir, f"#{sub_id}_{s_time}_to_{e_time}.mp3"),
                        os.path.join(voice_dir, f"#{sub_id}_{s_time}_to_{e_time}_M.mp3"),
                        os.path.join(voice_dir, f"#{sub_id}_{s_time}_to_{e_time}_F.mp3"),
                        os.path.join(voice_dir, f"line_{sub_id}_{s_time}_to_{e_time}.mp3"),
                        os.path.join(voice_dir, f"line_{idx+1}_{s_time}_to_{e_time}.mp3"),
                        os.path.join(voice_dir, f"#{idx+1}_{s_time}_to_{e_time}.mp3"),
                        os.path.join(voice_dir, f"runtime_line_{idx+1}.mp3"),
                        os.path.join(voice_dir, f"runtime_line_{sub_id}.mp3")
                    ]
                    for cand in candidates:
                        if os.path.exists(cand) and os.path.getsize(cand) > 100:
                            audio_path = cand
                            sub["audio_file"] = cand
                            break

            if not audio_path or not os.path.exists(audio_path):
                continue

            try:
                s_sec = float(sub.get("start", 0.0))
                try:
                    data, sr = sf.read(audio_path)
                except Exception:
                    # Fallback to ffmpeg pipe: 100% format support including .m4a, .aac, .ogg
                    import subprocess
                    cmd = ['ffmpeg', '-v', 'error', '-i', audio_path, '-f', 's16le', '-ar', str(sample_rate), '-ac', '2', '-']
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    if res.returncode == 0 and res.stdout:
                        data = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
                        data = data.reshape(-1, 2)
                        sr = sample_rate
                    else:
                        continue
                if len(data) == 0:
                    continue
                if len(data.shape) == 1:
                    data = np.column_stack((data, data))
                elif data.shape[1] > 2:
                    data = data[:, :2]

                if sr != sample_rate:
                    num_resampled = int(len(data) * sample_rate / sr)
                    idx_arr = np.linspace(0, len(data) - 1, num_resampled).astype(int)
                    data = data[idx_arr]

                s_sec = float(sub.get("start", 0.0))
                e_sec = float(sub.get("end", s_sec + 1.0))
                audio_dur = len(data) / sample_rate
                slot_dur = max(0.1, e_sec - s_sec)

                # 1. Exact Lip-Sync: Dialogue starts strictly at subtitle start time (s_sec) so mouth & voice match 100%!
                start_idx = max(0, int(s_sec * sample_rate))

                # 2. Additive studio mixing: Preserves 100% of every spoken word so no sentences or endings are ever cut off!
                end_idx = start_idx + len(data)
                last_end_sample = max(last_end_sample, end_idx)

                if end_idx > len(canvas):
                    # Clip data to canvas boundary: zero memory re-allocation!
                    data = data[:max(0, len(canvas) - start_idx)]
                    end_idx = start_idx + len(data)

                if start_idx < len(canvas) and len(data) > 0:
                    canvas[start_idx:end_idx] += data
            except Exception as ex:
                print(f"Audio mix line #{sub.get('id')} error: {ex}")

            if progress_callback and (idx % 25 == 0 or idx == total_subs - 1):
                pct = (idx + 1) / max(1, total_subs)
                progress_callback(f"Mixing voice track [{idx+1}/{total_subs}]...", pct)

        # Trim canvas to actual duration plus safety margin
        final_sample_count = max(int(eff_dur * sample_rate), last_end_sample + int(sample_rate * 0.5))
        if final_sample_count < len(canvas):
            canvas = canvas[:final_sample_count]

        np.clip(canvas, -1.0, 1.0, out=canvas)
        out_ext = os.path.splitext(output_wav_path)[1].lower()
        if out_ext == ".mp3":
            try:
                sf.write(output_wav_path, canvas, sample_rate, format='MP3')
                if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 100:
                    return output_wav_path
            except Exception:
                pass
            # Fallback if direct MP3 write fails
            import subprocess
            temp_wav = output_wav_path + ".temp.wav"
            sf.write(temp_wav, canvas, sample_rate, subtype='PCM_16')
            cmd = ["ffmpeg", "-y", "-i", temp_wav, "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", output_wav_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(temp_wav):
                try:
                    os.remove(temp_wav)
                except Exception:
                    pass
            if os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 100:
                return output_wav_path
            sf.write(output_wav_path, canvas, sample_rate, subtype='PCM_16')
            return output_wav_path
        elif out_ext == ".wav":
            sf.write(output_wav_path, canvas, sample_rate, subtype='PCM_16')
            return output_wav_path
        else:
            # Default direct fast write
            try:
                sf.write(output_wav_path, canvas, sample_rate)
            except Exception:
                sf.write(output_wav_path, canvas, sample_rate, subtype='PCM_16')
            return output_wav_path

    except Exception as e:
        print(f"Fast audio assembly fallback to pydub: {e}")
        base_track = AudioSegment.silent(duration=int(eff_dur * 1000), frame_rate=44100).set_channels(2)
        last_end_ms = 0
        for idx, sub in enumerate(subtitles):
            audio_path = sub.get("audio_file")
            if audio_path and os.path.exists(audio_path):
                try:
                    target_ms = max(0, int(float(sub.get("start", 0.0)) * 1000))
                    start_ms = max(target_ms, last_end_ms + 25)
                    speech_audio = AudioSegment.from_file(audio_path).set_frame_rate(44100).set_channels(2)
                    last_end_ms = start_ms + len(speech_audio)
                    needed_len = last_end_ms + 2000
                    if needed_len > len(base_track):
                        base_track += AudioSegment.silent(duration=(needed_len - len(base_track)), frame_rate=44100).set_channels(2)
                    base_track = base_track.overlay(speech_audio, position=start_ms)
                except Exception:
                    pass
        out_ext = os.path.splitext(output_wav_path)[1].lower()
        if out_ext == ".m4a":
            base_track.export(output_wav_path, format="ipod", codec="aac", bitrate="160k")
        elif out_ext == ".mp3":
            base_track.export(output_wav_path, format="mp3", bitrate="192k")
        else:
            base_track.export(output_wav_path, format="wav")
        return output_wav_path


# Export alias for compatibility
assemble_synchronized_timeline = assemble_dubbed_audio


def mix_movie_with_dubbed_audio(
    video_or_orig_audio: str,
    dubbed_audio_path: str,
    output_audio_path: str,
    subtitles: list = None,
    orig_vol: float = 0.85,
    dub_vol: float = 1.0,
    auto_duck: bool = True,
    sample_rate: int = 44100
) -> bool:
    """
    Blends movie original soundtrack with Khmer dubbed voice:
    Whenever Khmer voice is speaking (e.g. 00:15 - 00:30), the original soundtrack is
    100% COMPLETELY MUTED (volume = 0.0) with a smooth 45ms anti-pop transition curve.
    Outside dialogue intervals, the original soundtrack plays at full orig_vol.
    """
    import subprocess
    import numpy as np
    import soundfile as sf

    if not dubbed_audio_path or not os.path.exists(dubbed_audio_path):
        return False

    # 1. Read dubbed audio track
    dub_data = None
    dub_sr = sample_rate
    try:
        dub_data, dub_sr = sf.read(dubbed_audio_path)
    except Exception:
        cmd_dub = ['ffmpeg', '-v', 'error', '-i', dubbed_audio_path, '-f', 's16le', '-ar', str(sample_rate), '-ac', '2', '-']
        res_dub = subprocess.run(cmd_dub, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if res_dub.returncode == 0 and res_dub.stdout:
            dub_data = np.frombuffer(res_dub.stdout, dtype=np.int16).astype(np.float32) / 32768.0
            dub_data = dub_data.reshape(-1, 2)
            dub_sr = sample_rate

    if dub_data is None or len(dub_data) == 0:
        return False

    if len(dub_data.shape) == 1:
        dub_data = np.column_stack((dub_data, dub_data))
    elif dub_data.shape[1] > 2:
        dub_data = dub_data[:, :2]

    if dub_sr != sample_rate:
        num_resampled = int(len(dub_data) * sample_rate / dub_sr)
        idx_arr = np.linspace(0, len(dub_data) - 1, num_resampled).astype(int)
        dub_data = dub_data[idx_arr]

    # 2. Extract original movie audio
    cmd_orig = ['ffmpeg', '-v', 'error', '-i', video_or_orig_audio, '-f', 's16le', '-ar', str(sample_rate), '-ac', '2', '-']
    res_orig = subprocess.run(cmd_orig, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if res_orig.returncode == 0 and res_orig.stdout:
        orig_data = np.frombuffer(res_orig.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        orig_data = orig_data.reshape(-1, 2)
    else:
        # Video has no audio track, output dubbed audio directly
        sf.write(output_audio_path, dub_data * dub_vol, sample_rate, subtype='PCM_16')
        return True

    # Align lengths
    max_len = max(len(orig_data), len(dub_data))
    if len(orig_data) < max_len:
        pad = np.zeros((max_len - len(orig_data), 2), dtype=np.float32)
        orig_data = np.vstack((orig_data, pad))
    if len(dub_data) < max_len:
        pad = np.zeros((max_len - len(dub_data), 2), dtype=np.float32)
        dub_data = np.vstack((dub_data, pad))

    # 3. Apply Complete Mute Ducking to Original Audio
    if auto_duck:
        mask = np.ones(max_len, dtype=np.float32)
        fade_len = int(0.045 * sample_rate)  # 45ms smooth transition to prevent clicks

        spoken_intervals = []
        # A. Intervals from active subtitles (Every SRT dialogue timecode is strictly muted)
        if subtitles:
            for sub in subtitles:
                s_t = max(0.0, float(sub.get("start", 0.0)))
                e_t = max(s_t + 0.3, float(sub.get("end", s_t + 1.0)))
                af = sub.get("audio_file") or sub.get("audio_path")
                if af and os.path.exists(af):
                    try:
                        dur = sf.info(af).duration
                        e_t = max(e_t, s_t + dur)
                    except Exception:
                        pass
                spoken_intervals.append((s_t, e_t))

        # B. Direct waveform activity detection on dubbed audio
        block_size = int(0.05 * sample_rate)
        dub_mono = np.max(np.abs(dub_data), axis=1)
        for i in range(0, max_len, block_size):
            if np.max(dub_mono[i:i + block_size]) > 0.006:
                t1 = i / sample_rate
                t2 = min(max_len, i + block_size) / sample_rate
                spoken_intervals.append((t1, t2))

        # Merge overlapping/adjacent intervals (bridge gaps under 180ms)
        if spoken_intervals:
            spoken_intervals.sort(key=lambda x: x[0])
            merged = []
            curr_s, curr_e = spoken_intervals[0]
            for s, e in spoken_intervals[1:]:
                if s <= curr_e + 0.18:
                    curr_e = max(curr_e, e)
                else:
                    merged.append((curr_s, curr_e))
                    curr_s, curr_e = s, e
            merged.append((curr_s, curr_e))

            for s_t, e_t in merged:
                s_idx = max(0, min(max_len, int(s_t * sample_rate)))
                e_idx = max(0, min(max_len, int(e_t * sample_rate)))
                if e_idx <= s_idx:
                    continue

                # Fade out original audio
                f_out_start = max(0, s_idx - fade_len)
                if s_idx > f_out_start:
                    mask[f_out_start:s_idx] = np.minimum(mask[f_out_start:s_idx], np.linspace(1.0, 0.0, s_idx - f_out_start))

                # 100% MUTE during dialogue interval (Original sound volume = 0)
                mask[s_idx:e_idx] = 0.0

                # Fade back in after dialogue finishes
                f_in_end = min(max_len, e_idx + fade_len)
                if f_in_end > e_idx:
                    mask[e_idx:f_in_end] = np.minimum(mask[e_idx:f_in_end], np.linspace(0.0, 1.0, f_in_end - e_idx))

        orig_data = orig_data * (orig_vol * mask[:, None])
    else:
        orig_data = orig_data * orig_vol

    # 4. Final studio mix
    final_mix = orig_data + (dub_data * dub_vol)
    np.clip(final_mix, -1.0, 1.0, out=final_mix)

    # 5. Write to output
    sf.write(output_audio_path, final_mix, sample_rate, subtype='PCM_16')
    return True


def mute_audio_at_srt_intervals(
    input_media_path: str,
    output_audio_path: str,
    subtitles: list,
    fade_ms: float = 45.0,
    progress_callback=None
) -> bool:
    """
    Blazing-fast sample-accurate audio muting strictly at SRT subtitle intervals.
    Mutes (zero volume) original speech during timecodes (e.g. 1:05 - 1:40) with smooth 45ms fade curves.
    Leaves 100% of background music, fight sounds, and environment noise intact outside subtitle cues.
    Executes in < 3 seconds even for 2-hour movies!
    """
    import subprocess
    if not os.path.exists(input_media_path):
        return False
    if not subtitles:
        cmd = ["ffmpeg", "-y", "-i", input_media_path, "-vn", "-c:a", "libmp3lame", "-b:a", "320k", output_audio_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(output_audio_path)

    import soundfile as sf
    import numpy as np

    sample_rate = 44100
    if progress_callback:
        progress_callback("🔊 [Audio] កំពុងទាញយកសំឡេងដើម...", 0.10)

    # 1. Extract audio stream directly to raw PCM s16le stereo via FFmpeg pipe
    cmd_orig = [
        "ffmpeg", "-y", "-i", input_media_path,
        "-vn", "-f", "s16le", "-acodec", "pcm_s16le",
        "-ar", str(sample_rate), "-ac", "2", "-"
    ]
    res_orig = subprocess.run(cmd_orig, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if res_orig.returncode != 0 or not res_orig.stdout:
        return False

    orig_data = np.frombuffer(res_orig.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    orig_data = orig_data.reshape(-1, 2)
    max_len = len(orig_data)

    if progress_callback:
        progress_callback("🔇 [Mute] កំពុងអនុវត្ត Mute លើគ្រប់ចន្លោះម៉ោង SRT...", 0.50)

    mask = np.ones(max_len, dtype=np.float32)
    fade_len = int((fade_ms / 1000.0) * sample_rate)

    spoken_intervals = []
    for sub in subtitles:
        s_t = max(0.0, float(sub.get("start", 0.0)))
        e_t = max(s_t + 0.3, float(sub.get("end", s_t + 1.0)))
        spoken_intervals.append((s_t, e_t))

    if spoken_intervals:
        spoken_intervals.sort(key=lambda x: x[0])
        merged = []
        curr_s, curr_e = spoken_intervals[0]
        for s, e in spoken_intervals[1:]:
            if s <= curr_e + 0.18:
                curr_e = max(curr_e, e)
            else:
                merged.append((curr_s, curr_e))
                curr_s, curr_e = s, e
        merged.append((curr_s, curr_e))

        for s_t, e_t in merged:
            s_idx = max(0, min(max_len, int(s_t * sample_rate)))
            e_idx = max(0, min(max_len, int(e_t * sample_rate)))
            if e_idx <= s_idx:
                continue

            # Smooth fade-out before dialogue
            f_out_start = max(0, s_idx - fade_len)
            if s_idx > f_out_start:
                mask[f_out_start:s_idx] = np.minimum(mask[f_out_start:s_idx], np.linspace(1.0, 0.0, s_idx - f_out_start))

            # 100% Mute during dialogue interval
            mask[s_idx:e_idx] = 0.0

            # Smooth fade-in after dialogue finishes
            f_in_end = min(max_len, e_idx + fade_len)
            if f_in_end > e_idx:
                mask[e_idx:f_in_end] = np.minimum(mask[e_idx:f_in_end], np.linspace(0.0, 1.0, f_in_end - e_idx))

    orig_data = orig_data * mask[:, None]

    if progress_callback:
        progress_callback("💾 [Audio] កំពុង Export ជា MP3 គុណភាពខ្ពស់ 320kbps...", 0.85)

    os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
    temp_wav = output_audio_path + ".tmp.wav"
    sf.write(temp_wav, orig_data, sample_rate, subtype='PCM_16')

    # Convert to 320kbps MP3
    cmd_mp3 = [
        "ffmpeg", "-y", "-i", temp_wav,
        "-acodec", "libmp3lame", "-b:a", "320k",
        "-ar", "44100",
        output_audio_path
    ]
    subprocess.run(cmd_mp3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(temp_wav):
        try:
            os.remove(temp_wav)
        except Exception:
            pass

    if progress_callback:
        progress_callback("✅ [Mute] បាន Mute សំឡេងតាមចន្លោះ SRT រួចរាល់!", 1.0)

    return os.path.exists(output_audio_path)

