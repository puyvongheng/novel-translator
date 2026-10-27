"""
Whisper Runtime & Hardware Accelerators
Safely manages Faster-Whisper model loading, CUDA library verification (cublas64_12.dll),
and multi-threaded CPU fallback.
"""

import os
import ctypes


def is_cuda_runtime_available() -> tuple[bool, str]:
    """
    Checks if CUDA hardware AND required CTranslate2 runtime libraries (cublas64_12.dll)
    are present and loadable on Windows.
    Returns:
        (is_available: bool, reason: str)
    """
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() <= 0:
            return False, "No CUDA GPU detected on system."
    except Exception as e:
        return False, f"CTranslate2 CUDA probe error: {e}"

    # On Windows, CTranslate2 requires cublas64_12.dll or cublas64_11.dll
    # If the DLL is missing, calling forward pass will crash with RuntimeError
    can_load_cublas = False
    for dll_name in ["cublas64_12.dll", "cublas64_11.dll"]:
        try:
            ctypes.CDLL(dll_name)
            can_load_cublas = True
            break
        except Exception:
            pass

    if not can_load_cublas:
        return False, "CUDA GPU exists but cublas64_12.dll is not found in PATH."

    return True, "CUDA GPU & cuBLAS runtime available."


class WhisperModelLoader:
    """
    Caches and serves Faster-Whisper models with automatic CPU fallback.
    """
    _cache: dict = {}

    @classmethod
    def get_model(
        cls,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = None,
        cpu_threads: int = None
    ):
        """
        Loads or returns a cached Faster-Whisper model.
        Automatically verifies CUDA compatibility and falls back to CPU (int8) if needed.
        """
        from faster_whisper import WhisperModel

        target_threads = cpu_threads or max(4, (os.cpu_count() or 4) - 1)

        # 1. Determine safe device & compute_type
        if device == "auto":
            cuda_ok, reason = is_cuda_runtime_available()
            if cuda_ok:
                actual_device = "cuda"
                actual_compute = compute_type or "float16"
            else:
                actual_device = "cpu"
                actual_compute = "int8"
        elif device == "cuda":
            cuda_ok, _ = is_cuda_runtime_available()
            if cuda_ok:
                actual_device = "cuda"
                actual_compute = compute_type or "float16"
            else:
                # User asked for CUDA but DLL is missing -> safe fallback
                actual_device = "cpu"
                actual_compute = "int8"
        else:
            actual_device = "cpu"
            actual_compute = compute_type or "int8"

        cache_key = f"{model_size}_{actual_device}_{actual_compute}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        try:
            model = WhisperModel(
                model_size,
                device=actual_device,
                compute_type=actual_compute,
                cpu_threads=target_threads
            )
            cls._cache[cache_key] = model
            return model
        except Exception as err:
            # If CUDA instantiation fails, fallback directly to CPU int8
            if actual_device == "cuda":
                fallback_key = f"{model_size}_cpu_int8"
                if fallback_key in cls._cache:
                    return cls._cache[fallback_key]

                model = WhisperModel(
                    model_size,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=target_threads
                )
                cls._cache[fallback_key] = model
                return model
            raise err

    @classmethod
    def clear_cache(cls):
        """Releases cached Whisper models from memory."""
        cls._cache.clear()
