<div align="center">

# ✦ MKB AI Super Resolution Tool

### v7.2 — Camera RAW · CUDA · Fujifilm Color Science · CustomTkinter GUI

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x%20CUDA-ee4c2c?logo=pytorch)](https://pytorch.org/)
[![CUDA](https://img.shields.io/badge/CUDA-12.8-76b900?logo=nvidia)](https://developer.nvidia.com/cuda-downloads)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-Kursat--27-181717?logo=github)](https://github.com/Kursat-27/MKB-SuperResolution-Tool)

</div>

---

## Overview

**MKB AI Super Resolution Tool** is a production-ready desktop application for upscaling single images and Camera RAW files using the [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) neural network (`RealESRGAN_x4plus`) on NVIDIA CUDA GPUs.

The application features:
- **CUDA-accelerated 4x / 2x AI upscaling** via `RRDBNet` (64 RRDB blocks)
- **Camera RAW demosaicing** with LibRaw (`rawpy`) — RAF, CR2, CR3, NEF, ARW, DNG
- **Fujifilm Color Science** — Classic Chrome, Velvia, Classic Negative, Pro Neg.Hi, Acros (B&W)
- **Organic CUDA film grain** generator (midtone-masked)
- **Fast lossless PNG saving** in ~15 seconds via `cv2.imencode` + level-1 compression
- **Clean CustomTkinter GUI** with drag-and-drop, tabbed workspace, and real-time log console

---

## Screenshots

> _Launch the app via `START.vbs` (silent) or `SuperResolutionApp.bat` (console)._

---

## Features

| Feature | Details |
|---|---|
| **AI Model** | RealESRGAN_x4plus — `RRDBNet(nf=64, nb=23, gc=32, scale=4)` |
| **Scale Modes** | 4x direct AI upscale · 2x AI + Lanczos-4 downsampling |
| **Precision** | FP16 CUDA mixed precision (`torch.cuda.amp.autocast`) |
| **Tiled Inference** | Auto VRAM-aware tiling (512 → 384 → 256 → 192 px) with OOM recovery |
| **Camera RAW** | `rawpy` LibRaw, `no_auto_bright=False`, `gamma=(2.222, 4.5)` for vivid exposure |
| **Color Science** | CUDA Fujifilm presets: Classic Chrome, Velvia, Classic Negative, Pro Neg.Hi, Acros |
| **Film Grain** | Organic midtone-masked CUDA noise generator (0–100 slider) |
| **Fast PNG Save** | `cv2.imencode` + `IMWRITE_PNG_COMPRESSION=1` (~15 sec on high-megapixel images) |
| **Path Security** | Directory traversal + Windows reserved device name protection |
| **Model Integrity** | SHA-256 checksum verification (`verify_model_checksum`) |
| **Cancel** | Thread-safe mid-inference cancellation via `threading.Event` |

---

## Supported Formats

| Category | Extensions |
|---|---|
| **Standard Images** | `.jpg` `.jpeg` `.png` `.webp` `.bmp` `.tif` `.tiff` |
| **Camera RAW** | `.raf` `.cr2` `.cr3` `.nef` `.arw` `.dng` `.orf` `.rw2` `.pef` |

---

## Requirements

- **OS**: Windows 10/11 (64-bit)
- **GPU**: NVIDIA GPU with CUDA 12.x support (RTX 4060 or better recommended)
- **Python**: 3.10+
- **VRAM**: 4 GB minimum · 8 GB recommended for 512 px tiles

### Python Dependencies

```
torch>=2.1.0+cu121
torchvision
customtkinter>=5.2.0
tkinterdnd2
rawpy
opencv-python
Pillow
numpy
```

> Full list in [`requirements.txt`](requirements.txt).

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Kursat-27/MKB-SuperResolution-Tool.git
cd MKB-SuperResolution-Tool
```

### 2. Create Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Install PyTorch with CUDA 12.x

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### 4. Download Model Weights

Create a `models/` directory and download the official Real-ESRGAN weights:

```powershell
mkdir models
curl -L -o models\RealESRGAN_x4plus.pth ^
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
```

> **SHA-256 (RealESRGAN_x4plus.pth)**:  
> `4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1`

The app automatically resolves the model path relative to `ai_engine.py`:
```
SuperResolutionApp/
└── models/
    └── RealESRGAN_x4plus.pth   ← place here
```

### 5. Launch the App

```powershell
# Option A — Silent windowless launch (recommended)
cscript //nologo START.vbs

# Option B — Console launch (shows logs)
.\SuperResolutionApp.bat
```

---

## Usage

1. **Select Input**: Click "Görsel Seç" or drag-and-drop an image / RAW file onto the input panel.
2. **Choose Scale**: Select 2x or 4x from the sidebar.
3. **RAW White Balance**: Toggle "Kamera Otomatik WB" for camera white balance on RAW files.
4. **Fujifilm Color Science**: Pick a film simulation preset and set the Film Grain slider (0–100).
5. **Start Processing**: Click "▶ İşlemi Başlat" — real-time logs appear in the console.
6. **View Output**: The upscaled image appears in the "Çıkış" tab; compare with the "Karşılaştır" tab.

---

## Project Structure

```
SuperResolutionApp/
├── ai_engine.py            # Core PyTorch CUDA engine (SuperResolutionEngine, FujiColorEngine)
├── app_gui.py              # CustomTkinter desktop GUI (App class, WorkerThread)
├── model_downloader.py     # Automated model weight downloader with SHA-256 verification
├── test_suite.py           # 10 automated unit tests (100% pass rate)
├── test_ai.py              # AI inference integration tests
├── test_env.py             # Environment & dependency checks
├── requirements.txt        # Python dependencies
├── START.vbs               # Silent windowless VBScript launcher
├── SuperResolutionApp.bat  # Console batch launcher
└── models/
    └── RealESRGAN_x4plus.pth   # Model weights (download separately — excluded from git)
```

---

## Architecture

```
app_gui.py (CustomTkinter GUI)
    │
    └── WorkerThread (daemon thread)
            │
            ├── load_image_safe()         ← rawpy RAW decode / cv2 standard decode
            ├── SuperResolutionEngine
            │       ├── _load_model()     ← RRDBNet(scale=4) + params_ema checkpoint
            │       ├── enhance_image()   ← CUDA FP16 tiled inference
            │       └── FujiColorEngine   ← CUDA color matrix + film grain
            └── save_image_safe()         ← cv2.imencode + open(wb) PNG_COMPRESSION=1
```

---

## API Reference

### `sanitize_path(file_path, must_exist=False, allow_creation=False) → Path`
Validates and resolves file paths. Raises `SecurityError` on directory traversal or Windows reserved device names.

### `load_image_safe(file_path, use_auto_wb=True) → np.ndarray`
Loads Camera RAW files via `rawpy` (`no_auto_bright=False`, `gamma=(2.222, 4.5)`) or standard images via `cv2.imdecode`. Returns a BGR `np.ndarray`.

### `save_image_safe(output_path, image_bgr) → Path`
Encodes and writes images via memory buffers for Windows non-ASCII path safety. Uses `IMWRITE_PNG_COMPRESSION=1` for fast PNG saves.

### `ColorConfig(preset, film_grain)`
Dataclass holding Fujifilm color preset name and film grain intensity (0.0–100.0).

### `FujiColorEngine.apply_color_science(tensor_rgb, config) → Tensor`
Applies CUDA color matrix transformation and organic midtone-masked film grain to an RGB tensor `(1, 3, H, W)`.

### `SuperResolutionEngine.enhance_image(input_image, color_config, use_auto_wb, cancel_event, progress_callback) → np.ndarray`
Full pipeline: load → color science → tiled CUDA inference → 2x Lanczos-4 downsampling (if scale=2) → return BGR array.

---

## Running Tests

```powershell
.\venv\Scripts\python.exe -m unittest test_suite.py -v
```

**Expected output:**
```
test_cancellation ... ok
test_film_grain ... ok
test_forbidden_traversal ... ok
test_fuji_presets ... ok
test_load_image_safe ... ok
test_reserved_windows_names ... ok
test_save_image_safe_png_compression ... ok
test_upscale_bicubic ... ok
test_upscale_with_fuji_color ... ok
test_valid_path_resolution ... ok

----------------------------------------------------------------------
Ran 10 tests in 0.052s

OK
```

---

## GPU Memory Guide

| VRAM | Tile Size | Recommended For |
|---|---|---|
| 8 GB+ | 512 px | 24 MP+ images (RTX 4070+) |
| 4–8 GB | 384 px | 12–24 MP images (RTX 4060) |
| 2–4 GB | 256 px | 8–12 MP images |
| < 2 GB | 192 px | CPU fallback mode |

The engine auto-detects free VRAM via `torch.cuda.mem_get_info()` and adjusts tile size dynamically. On OOM, it halves the tile size and retries automatically.

---

## Changelog

### v7.2 (2026-08-04)
- Added `_C_ERROR_HOVER = "#dc2626"` color constant
- Windows non-ASCII path safety: `cv2.imdecode` + `cv2.imencode` memory buffer I/O
- Reserved Windows device name validation (`CON`, `NUL`, `PRN`, `COM1`–`COM9`, `LPT1`–`LPT9`)
- `verify_model_checksum()` SHA-256 model integrity verification
- `HAS_TORCH` flag for graceful degradation on CPU-only systems

### v7.1 (2026-08-03)
- Complete GUI restoration: 280px sidebar, `CTkScrollableFrame`, fixed bottom action panel
- `_C_ERROR_HOVER`, module-level color constants, `ctk.set_default_color_theme("blue")`
- CUDA Fujifilm Color Science Engine: 5 film presets + organic midtone-masked film grain
- Fast PNG saving: `IMWRITE_PNG_COMPRESSION=1` (~15 seconds for high-megapixel images)
- `params_ema` checkpoint key resolution for official RealESRGAN weights
- `weights_only=False` compatibility for PyTorch 2.6+ / 2.11+
- 2x scale: 4x CUDA inference + `cv2.INTER_LANCZOS4` downsampling

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) by xinntao — RRDBNet architecture & pretrained weights
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) by TomSchimansky — modern Tkinter UI
- [rawpy](https://github.com/letmaik/rawpy) — Python bindings for LibRaw

---

<div align="center">
Made with ❤️ · <a href="https://github.com/Kursat-27/MKB-SuperResolution-Tool">github.com/Kursat-27/MKB-SuperResolution-Tool</a>
</div>
