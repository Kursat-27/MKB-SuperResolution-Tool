"""
model_downloader.py
─────────────────────────────────────────────────────────────────────────────
Module: Model Weight Downloader  (Phase 6)

Desteklenen modeller ve resmi URL'leri:
  ─ RealESRGAN_x4plus      : genel fotoğraf + video için (64 RRDB blok)
  ─ RealESRGAN_x4plus_anime: anime / çizgi film içerik için (6 RRDB blok)
  ─ RealESRGAN_x2plus      : 2× upscaling için (64 RRDB blok)

İndirme mimarisi:
  download_model() → urllib arka plan akışı (chunk-by-chunk)
    → progress_callback(downloaded_bytes, total_bytes)
    → log_callback(message)

Thread-safety: tüm dosya işlemleri modeller/ klasörüne atomik şekilde
yazılır (geçici .tmp uzantısıyla indirilip tamamlandığında yeniden adlandırılır).
─────────────────────────────────────────────────────────────────────────────
"""

import os
import threading
import urllib.request
from pathlib import Path
from typing import Callable, Optional


# ── Model registry ────────────────────────────────────────────────────────
# Her girdi: "model_key" → {"url": ..., "filename": ..., "description": ...}
MODEL_REGISTRY: dict[str, dict] = {
    "RealESRGAN_x4plus": {
        "url": (
            "https://github.com/xinntao/Real-ESRGAN/releases/download/"
            "v0.1.0/RealESRGAN_x4plus.pth"
        ),
        "filename": "RealESRGAN_x4plus.pth",
        "description": "Real-ESRGAN ×4 (general photo/video, 64 RRDB blocks)",
        "num_block": 23,
        "scale": 4,
    },
    "RealESRGAN_x4plus_anime": {
        "url": (
            "https://github.com/xinntao/Real-ESRGAN/releases/download/"
            "v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"
        ),
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "description": "Real-ESRGAN ×4 Anime (6 RRDB blocks, faster)",
        "num_block": 6,
        "scale": 4,
    },
    "RealESRGAN_x2plus": {
        "url": (
            "https://github.com/xinntao/Real-ESRGAN/releases/download/"
            "v0.2.1/RealESRGAN_x2plus.pth"
        ),
        "filename": "RealESRGAN_x2plus.pth",
        "description": "Real-ESRGAN ×2 (general photo/video, 64 RRDB blocks)",
        "num_block": 23,
        "scale": 2,
    },
}

# Default directory for storing downloaded weights
DEFAULT_MODELS_DIR = Path(__file__).parent / "models"


# ──────────────────────────────────────────────────────────────────────────
# Core download function
# ──────────────────────────────────────────────────────────────────────────
def download_model(
    model_key: str,
    models_dir: Optional[str | Path] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Path:
    """
    Downloads a pre-trained model weight file to *models_dir*.

    The file is first written with a ``.tmp`` suffix and renamed on
    successful completion so partial downloads are never mistaken for
    valid weights.

    Parameters
    ----------
    model_key : str
        Registry key (e.g. ``"RealESRGAN_x4plus"``).
    models_dir : str | Path | None
        Directory to save the weights.  Defaults to ``./models/``.
    progress_callback : Callable[[int, int], None] | None
        Called repeatedly with (downloaded_bytes, total_bytes).
        Use this to drive a GUI progress bar.
        ``total_bytes`` may be -1 if the server omits Content-Length.
    log_callback : Callable[[str], None] | None
        Called with informational / error messages.
    cancel_event : threading.Event | None
        When set, the download is aborted and the partial ``.tmp``
        file is deleted.

    Returns
    -------
    Path
        Resolved path of the downloaded ``.pth`` file.

    Raises
    ------
    KeyError
        If *model_key* is not in MODEL_REGISTRY.
    RuntimeError
        If the download is cancelled before completion.
    urllib.error.URLError
        On network errors.
    """
    if model_key not in MODEL_REGISTRY:
        raise KeyError(
            f"[ModelDownloader] Unknown model key '{model_key}'. "
            f"Available: {list(MODEL_REGISTRY)}"
        )

    info = MODEL_REGISTRY[model_key]
    url: str       = info["url"]
    filename: str  = info["filename"]

    models_dir = Path(models_dir or DEFAULT_MODELS_DIR)
    models_dir.mkdir(parents=True, exist_ok=True)

    dest_path = models_dir / filename
    tmp_path  = models_dir / (filename + ".tmp")

    def _log(msg: str) -> None:
        print(msg)
        if log_callback:
            log_callback(msg)

    # ── Already downloaded? ───────────────────────────────────
    if dest_path.is_file():
        _log(f"[ModelDownloader] Found cached weights: {dest_path}")
        return dest_path.resolve()

    _log(f"[ModelDownloader] Downloading {filename} …")
    _log(f"[ModelDownloader] URL: {url}")

    # ── Stream download ───────────────────────────────────────
    chunk_size = 1 << 15   # 32 KB per chunk

    try:
        with urllib.request.urlopen(url) as response:
            total_bytes: int = int(response.headers.get("Content-Length", -1))
            downloaded   = 0

            if total_bytes > 0:
                _log(
                    f"[ModelDownloader] File size: "
                    f"{total_bytes / 1_048_576:.1f} MB"
                )
            else:
                _log("[ModelDownloader] File size: unknown")

            with open(tmp_path, "wb") as fout:
                while True:
                    # ── Cancellation check ────────────────────
                    if cancel_event and cancel_event.is_set():
                        _log("[ModelDownloader] Download cancelled.")
                        tmp_path.unlink(missing_ok=True)
                        raise RuntimeError("Download cancelled by user.")

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    fout.write(chunk)
                    downloaded += len(chunk)

                    if progress_callback:
                        progress_callback(downloaded, total_bytes)

                    # Log every ~10 %
                    if total_bytes > 0:
                        pct = downloaded * 100 // total_bytes
                        if pct % 10 == 0 and downloaded % (total_bytes // 10 + 1) < chunk_size:
                            _log(
                                f"[ModelDownloader] {pct}%  "
                                f"({downloaded / 1_048_576:.1f} / "
                                f"{total_bytes / 1_048_576:.1f} MB)"
                            )

    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    # ── Atomic rename ─────────────────────────────────────────
    tmp_path.replace(dest_path)
    _log(f"[ModelDownloader] Saved to: {dest_path}")
    return dest_path.resolve()


# ──────────────────────────────────────────────────────────────────────────
# Convenience: ensure model is present (download if missing)
# ──────────────────────────────────────────────────────────────────────────
def ensure_model(
    model_key: str,
    models_dir: Optional[str | Path] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Path:
    """
    Returns the local path of *model_key*'s weights, downloading them first
    if they are not yet present in *models_dir*.

    This is the primary function called by :class:`FrameUpscaler`.
    """
    models_dir = Path(models_dir or DEFAULT_MODELS_DIR)
    filename   = MODEL_REGISTRY[model_key]["filename"]
    dest_path  = models_dir / filename

    if dest_path.is_file():
        return dest_path.resolve()

    return download_model(
        model_key,
        models_dir=models_dir,
        progress_callback=progress_callback,
        log_callback=log_callback,
        cancel_event=cancel_event,
    )
