"""
runtime_hook_ffmpeg.py
PyInstaller Runtime Hook - FFmpeg + PyTorch PATH Setup

This hook runs before the main application script when the bundled
exe starts. It sets up the environment so torch and ffmpeg are found.
"""

import os
import sys


def _setup_ffmpeg_path() -> None:
    """Adds bundled ffmpeg_bin/ directory to PATH."""
    bundle_dir: str | None = getattr(sys, "_MEIPASS", None)
    if bundle_dir is None:
        return

    ffmpeg_bin_dir = os.path.join(bundle_dir, "ffmpeg_bin")
    if os.path.isdir(ffmpeg_bin_dir):
        current_path = os.environ.get("PATH", "")
        os.environ["PATH"] = ffmpeg_bin_dir + os.pathsep + current_path


def _setup_torch_path() -> None:
    """
    Adds the Python 3.12 stdlib and site-packages (where torch is installed)
    to sys.path so that 'import torch' succeeds at runtime.

    torch is NOT bundled inside the PyInstaller package because bundling it
    causes cascading import failures (missing stdlib modules, module-init
    chains, etc). Instead we load torch from the actual Python 3.12
    environment managed by uv.
    """
    import pathlib  # noqa: PLC0415

    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir is None:
        return  # Running from source - torch is already on sys.path

    # Candidate locations for the uv-managed Python 3.12 environment
    _home = pathlib.Path.home()
    _candidates = [
        _home / "AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none",
        _home / "AppData/Roaming/uv/python/cpython-3.12.13-windows-x86_64-none",
    ]

    for _candidate in _candidates:
        if not _candidate.is_dir():
            continue

        _lib       = str(_candidate / "Lib")
        _site_pkgs = str(_candidate / "Lib" / "site-packages")
        _dlls      = str(_candidate / "DLLs")

        # Prepend so the real stdlib takes priority over frozen bundle modules
        for _p in [_site_pkgs, _lib, _dlls]:
            if os.path.isdir(_p) and _p not in sys.path:
                sys.path.insert(0, _p)

        # Add torch/lib DLLs to PATH and DLL loader so CUDA extensions load
        _torch_lib = _candidate / "Lib" / "site-packages" / "torch" / "lib"
        if _torch_lib.is_dir():
            os.environ["PATH"] = (
                str(_torch_lib) + os.pathsep +
                _lib + os.pathsep +
                os.environ.get("PATH", "")
            )
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(str(_torch_lib))
                    os.add_dll_directory(_lib)
                except (OSError, ValueError):
                    pass

        break  # Found a valid candidate, stop searching


# Run hooks before any application code executes.
# torch DLLs must be on PATH before anything imports torch.
_setup_torch_path()
_setup_ffmpeg_path()
