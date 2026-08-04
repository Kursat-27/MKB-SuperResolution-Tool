# -*- mode: python ; coding: utf-8 -*-
"""
SuperResolutionApp.spec
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
PyInstaller Specification File â€“ SuperResolutionVideoApp (Phase 5)

KullanÄ±m:
  pyinstaller SuperResolutionApp.spec

Bu spec dosyasÄ± ÅŸunlarÄ± otomatik olarak yapar:
  - customtkinter tema + varlÄ±k dosyalarÄ±nÄ± bundle iÃ§ine gÃ¶mer
  - ffmpeg_bin/ klasÃ¶rÃ¼ndeki FFmpeg binary'lerini runtime'da PATH'e ekler
  - BÃ¼yÃ¼k, kullanÄ±lmayan kÃ¼tÃ¼phaneleri derleme dÄ±ÅŸÄ±nda bÄ±rakÄ±r
  - Windows'ta konsol penceresi aÃ§Ä±lmasÄ±nÄ± engeller (windowed mode)
  - Linux'ta tek dosya (onedir) Ã§Ä±ktÄ±sÄ± Ã¼retir

Gereksinimler (derleme Ã¶ncesi):
  pip install pyinstaller
  # FFmpeg binary'lerini ffmpeg_bin/ klasÃ¶rÃ¼ne kopyalayÄ±n (build.py yapar)
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


# â”€â”€ Platform flags â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX   = sys.platform.startswith("linux")
IS_MACOS   = sys.platform.startswith("darwin")

# ——— Project root (directory containing this .spec file) ——————————————————————————————————————————————————————————————————————
PROJECT_ROOT = Path(SPECPATH)  # SPECPATH is injected by PyInstaller

# ——— Locate CustomTkinter package directory ——————————————————————————————————————————————————————————————————————————————————
import customtkinter as _ctk_mod
CTK_DIR = Path(_ctk_mod.__file__).parent

# ——— FFmpeg bundled binary directory ——————————————————————————————————————————————————————————————————————————————————————————
FFMPEG_BIN_DIR = PROJECT_ROOT / "ffmpeg_bin"

# ——————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# Data files to embed inside the bundle
# Format: (source_path_or_glob, destination_folder_inside_bundle)
# ——————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
app_datas = [
    # CustomTkinter: themes (light/dark JSON), images, font files
    (str(CTK_DIR), "customtkinter"),

    # Downloaded model weights directory (may be empty on first run â€“
    # model_downloader will populate it at runtime if needed)
    *([( str(PROJECT_ROOT / "models"), "models" )]
      if (PROJECT_ROOT / "models").is_dir() else []),
]

# â”€â”€ Include tkinterdnd2 Tcl/Tk bindings and binaries â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# tkinterdnd2 relies on native binaries (tkdnd.dll etc) loaded at runtime.
app_datas += collect_data_files("tkinterdnd2")

# NOTE: torch/torchvision loaded at runtime via hook (not bundled)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Binary executables to embed (treated differently from data files:
# PyInstaller sets the executable bit on Linux/macOS automatically)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app_binaries = []

if IS_WINDOWS:
    for _name in ("ffmpeg.exe", "ffprobe.exe"):
        _p = FFMPEG_BIN_DIR / _name
        if _p.is_file():
            app_binaries.append((str(_p), "ffmpeg_bin"))

elif IS_LINUX or IS_MACOS:
    for _name in ("ffmpeg", "ffprobe"):
        _p = FFMPEG_BIN_DIR / _name
        if _p.is_file():
            app_binaries.append((str(_p), "ffmpeg_bin"))

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Hidden imports
# PyInstaller's static analysis misses these dynamic/late imports.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app_hidden_imports = [
    # CustomTkinter internals loaded by string name
    "customtkinter",
    "customtkinter.windows",
    "customtkinter.windows.widgets",
    "customtkinter.windows.widgets.theme",

    # tkinter backends
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
    "_tkinter",

    # Drag-and-drop
    "tkinterdnd2",

    # Our own modules (imported at runtime inside PipelineWorker)
    "pipeline",
    "ai_engine",
    "app_gui",
    "video_analyzer",
    "frame_extractor",
    "muxer",
    "cleanup",

    # PyTorch CUDA runtime (loaded lazily)
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "torchvision",

    # OpenCV
    "cv2",

    # ffmpeg-python
    "ffmpeg",

    # Standard library used at runtime
    "queue",
    "threading",
    "pathlib",
    "re",
    "io",
    "traceback",

    # stdlib modules that torch.hub pulls in via urllib.request
    # PyInstaller misses these because they are imported transitively.
    "email",
    "email.message",
    "email.parser",
    "email.feedparser",
    "email.errors",
    "email.header",
    "email.charset",
    "email.encoders",
    "email.utils",
    "email.policy",
    "email.headerregistry",
    "email.contentmanager",
    "email._header_value_parser",
    "email._encoded_words",
    "email.mime",
    "email.mime.text",
    "email.mime.multipart",
    "email.mime.base",
    "email.mime.nonmultipart",
    "urllib",
    "urllib.request",
    "urllib.parse",
    "urllib.error",
    "urllib.response",
    "urllib.robotparser",
    "http",
    "http.client",
    "http.cookiejar",
    "http.cookies",
    "html",
    "html.parser",
    "ssl",
    "socket",
    "json",
    "json.decoder",
    "json.encoder",
    "logging",
    "logging.handlers",
    "hashlib",
    "base64",
    "struct",
    "decimal",
    "fractions",
    "calendar",
    "tempfile",
    "shutil",
    "fnmatch",
    "glob",
    "zipfile",
    "tarfile",
    "gzip",
    "bz2",
    "lzma",
    "pickle",
    "copyreg",
    "weakref",
    "contextlib",
    "abc",
    "typing",
    "typing_extensions",
    "dataclasses",
    "enum",
    "functools",
    "itertools",
    "operator",
    "copy",
    "pprint",
    "warnings",
    "importlib",
    "importlib.util",
    "importlib.machinery",
    "importlib.resources",
    "importlib.metadata",
    "concurrent",
    "concurrent.futures",
    "multiprocessing",
    "subprocess",
    "signal",
    "ctypes",
    "ctypes.util",
]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Excluded modules â€“ large packages not needed at runtime
#
# Boyut optimizasyonu: bu modÃ¼ller derleme dÄ±ÅŸÄ±nda bÄ±rakÄ±lÄ±r.
# Dikkat: bir modÃ¼lÃ¼ dÄ±ÅŸarÄ±da bÄ±rakmak onu transitif baÄŸÄ±mlÄ±lÄ±klarÄ±yla
# birlikte kaldÄ±rÄ±r; test ederek doÄŸrulayÄ±n.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
app_excludes = [
    # Data science / ML training stack (sadece inference yapÄ±yoruz)
    "matplotlib",
    "matplotlib.pyplot",
    "pandas",
    "scipy",
    "sklearn",
    "skimage",
    "seaborn",
    "plotly",
    "bokeh",
    "altair",
    "statsmodels",

    # Jupyter / interactive computing
    "IPython",
    "ipykernel",
    "ipywidgets",
    "jupyter",
    "jupyter_client",
    "jupyter_core",
    "notebook",
    "nbformat",
    "nbconvert",

    # Development / testing tools
    "pytest",
    "unittest",
    "doctest",
    "pydoc",
    "sphinx",
    "docutils",

    # PyTorch training-only modules (not needed for inference)
    "torch.optim.lr_scheduler",
    "torch.utils.tensorboard",
    "torch.utils.data.distributed",
    "torch.distributed",
    "torch.testing",

    # Unused standard library modules
    "email",
    "html",
    "http.server",
    "xmlrpc",
    "ftplib",
    "smtplib",
    "imaplib",
    "poplib",
    "telnetlib",
    "nntplib",

    # Large GUI toolkits we are NOT using
    "wx",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",

    # Crypto / network stacks not needed
    "cryptography",
    "OpenSSL",
    "paramiko",
    "Crypto",
]

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PyInstaller Analysis block
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
a = Analysis(
    # Entry point â€“ the GUI application
    [str(PROJECT_ROOT / "app_gui.py")],

    pathex=[str(PROJECT_ROOT)],
    binaries=app_binaries,
    datas=app_datas,
    hiddenimports=app_hidden_imports,
    hookspath=[],

    # Runtime hook: fires before gui_app.py, wires ffmpeg into PATH
    runtime_hooks=[str(PROJECT_ROOT / "runtime_hook_ffmpeg.py")],

    excludes=app_excludes,

    # noarchive=True stores .pyc files as plain files (easier debugging)
    noarchive=True,

    # Optimise bytecode
    optimize=1,
)

pyz = PYZ(a.pure)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Executable definition
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
exe = EXE(
    pyz,
    a.scripts,
    [],

    # Name of the output executable
    name="SuperResolutionVideoApp",

    # Windows: suppress the black console window
    console=False,

    # Windows icon (optional â€“ place SuperResolutionApp.ico in project root)
    icon=str(PROJECT_ROOT / "SuperResolutionApp.ico")
    if (PROJECT_ROOT / "SuperResolutionApp.ico").is_file()
    else None,

    # UPX compression (optional â€“ can break CUDA DLLs; disable if unstable)
    upx=False,

    # Strip debug symbols on Linux/macOS to reduce size
    strip=IS_LINUX or IS_MACOS,

    # Bootloader integrity check
    bootloader_ignore_signals=False,
    disable_windowed_traceback=False,

    # Pass argv emulation for macOS open events
    argv_emulation=IS_MACOS,

    # Target architecture (None = auto-detect host arch)
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Output directory (onedir mode â€“ faster startup than onefile)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=IS_LINUX or IS_MACOS,
    upx=False,
    upx_exclude=[
        # Never UPX-compress these â€“ they contain CUDA kernels
        "vcruntime*.dll",
        "msvcp*.dll",
        "torch_*.dll",
        "cublas*.dll",
        "cudnn*.dll",
        "*.pyd",
        "*.so",
    ],
    name="SuperResolutionVideoApp",
)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# macOS App Bundle (only generated on macOS)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if IS_MACOS:
    app = BUNDLE(
        coll,
        name="SuperResolutionVideoApp.app",
        icon=str(PROJECT_ROOT / "SuperResolutionApp.icns")
        if (PROJECT_ROOT / "SuperResolutionApp.icns").is_file()
        else None,
        bundle_identifier="com.superresolution.videoapp",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMinimumSystemVersion": "10.13.0",
        },
    )



