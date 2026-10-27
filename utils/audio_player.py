"""
Audio Player Utility
Plays audio files reliably across Windows environments using pygame, ffplay, or system player fallback.
"""

import os
import subprocess

def play_audio_file(audio_path: str, channel: int = None, volume: float = 1.0):
    """Plays an audio file reliably across Windows environments without blocking or crashing"""
    if not audio_path or not os.path.exists(audio_path):
        return

    # Method 1: Pygame Sound (multi-channel playback, does not interrupt background music)
    try:
        import pygame
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            except Exception:
                pygame.mixer.init()
        sound = pygame.mixer.Sound(audio_path)
        sound.set_volume(max(0.0, min(1.0, float(volume))))
        if channel is not None:
            ch = pygame.mixer.Channel(channel)
            ch.play(sound)
        else:
            ch = pygame.mixer.find_channel(True)
            if ch:
                ch.play(sound)
            else:
                sound.play()
        return
    except Exception:
        pass

    # Method 2: Pygame music fallback
    try:
        import pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.music.load(audio_path)
        pygame.mixer.music.set_volume(max(0.0, min(1.0, float(volume))))
        pygame.mixer.music.play()
        return
    except Exception:
        pass

    # Method 3: FFplay background process
    try:
        subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", audio_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return
    except Exception:
        pass

    # Method 4: Windows default audio player
    try:
        os.startfile(audio_path)
    except Exception:
        pass
