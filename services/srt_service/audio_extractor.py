"""
Audio Extractor Service
Extracts and normalizes audio streams from video files for speech recognition and studio playback.
"""

import os
import subprocess
import tempfile


class AudioExtractor:
    """
    Handles audio extraction from video files using FFmpeg.
    - Mono 16kHz PCM WAV with speech bandpass & dynamic normalization for ASR (Whisper / FunASR)
    - High-quality MP3 (stereo, 44.1kHz) for playback in Movie Studio monitor
    """

    @staticmethod
    def extract_asr_wav(video_path: str, output_wav: str = None) -> str:
        """
        Extracts 16kHz mono WAV optimized for Whisper & FunASR speech recognition.
        If output_wav is None, creates a temporary file.
        Returns the path to the extracted WAV file, or raises RuntimeError on failure.
        """
        if not output_wav:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            output_wav = tmp.name
            tmp.close()

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            "-af", "highpass=f=80,lowpass=f=7500,dynaudnorm=f=150:g=15",
            output_wav
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0 or not os.path.exists(output_wav) or os.path.getsize(output_wav) < 100:
            raise RuntimeError(f"FFmpeg failed to extract ASR WAV audio from: {video_path}")

        return output_wav

    @staticmethod
    def extract_preview_mp3(video_path: str, output_mp3: str, bitrate: str = "128k") -> bool:
        """
        Extracts high-quality MP3 audio for cinema playback in Movie Studio transport.
        Returns True if successful, False otherwise.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_mp3)), exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "libmp3lame", "-b:a", bitrate,
            "-ar", "44100", "-ac", "2", "-threads", "0",
            output_mp3
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0 and os.path.exists(output_mp3) and os.path.getsize(output_mp3) > 1000
