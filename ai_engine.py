from __future__ import annotations

import gc
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Union

import cv2
import numpy as np
import hashlib
from PIL import Image

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    nn = object
    F = None

Image.MAX_IMAGE_PIXELS = 200_000_000

def verify_model_checksum(model_path: Union[str, Path], expected_sha256: str) -> bool:
    clean_p = sanitize_path(model_path, must_exist=True)
    sha256 = hashlib.sha256()
    with open(clean_p, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest().lower() == expected_sha256.lower()

# Known SHA-256 hashes for official model weights
_MODEL_SHA256 = {
    "RealESRGAN_x4plus.pth": "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1",
}

try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

logger = logging.getLogger("MKB_Engine")
logger.setLevel(logging.INFO)

class SecurityError(Exception): pass
class CUDAOutOfMemoryError(Exception): pass
class ImageLoadError(Exception): pass

RESERVED_WIN_NAMES = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}

_BLOCKED_SYSTEM_PREFIXES = (
    os.path.normcase(os.environ.get("SYSTEMROOT", r"C:\Windows")),
    os.path.normcase(r"C:\Windows"),
)

def sanitize_path(file_path: Union[str, Path], must_exist: bool = False, allow_creation: bool = False) -> Path:
    raw_str = str(file_path).strip()
    p = Path(raw_str)

    # Block reserved Windows device names
    if p.stem.upper() in RESERVED_WIN_NAMES:
        raise SecurityError(f"Reserved Windows device name detected: {raw_str}")

    # Block directory traversal sequences
    if ".." in p.parts or ".." in raw_str:
        raise SecurityError(f"Directory traversal detected: {file_path}")

    # Block tilde home-directory expansion
    if raw_str.startswith("~") or "~/" in raw_str or "~\\" in raw_str:
        raise SecurityError(f"Tilde home-directory expansion blocked: {file_path}")

    try:
        resolved_p = p.resolve()
    except Exception:
        resolved_p = p.absolute()

    # Block access to system directories
    norm_resolved = os.path.normcase(str(resolved_p))
    for prefix in _BLOCKED_SYSTEM_PREFIXES:
        if norm_resolved.startswith(prefix):
            raise SecurityError(f"Access to system directory blocked: {resolved_p}")

    if must_exist and not resolved_p.exists():
        raise SecurityError(f"Path does not exist: {resolved_p}")

    if allow_creation and not resolved_p.parent.exists():
        resolved_p.parent.mkdir(parents=True, exist_ok=True)

    return resolved_p

RAW_EXTENSIONS = {'.raf', '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.pef'}
STANDARD_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}

def load_image_safe(file_path: Union[str, Path], use_auto_wb: bool = True) -> np.ndarray:
    clean_p = sanitize_path(file_path, must_exist=True)
    ext = clean_p.suffix.lower()

    if ext in RAW_EXTENSIONS:
        if not HAS_RAWPY:
            raise ImageLoadError("rawpy is not installed.")
        try:
            with rawpy.imread(str(clean_p)) as raw:
                rgb = raw.postprocess(
                    use_camera_wb=use_auto_wb,
                    half_size=False,
                    no_auto_bright=False,
                    auto_bright_thr=0.01,
                    gamma=(2.222, 4.5),
                    output_bps=8
                )
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            raise ImageLoadError(f"RAW decode error: {exc}")
    elif ext in STANDARD_EXTENSIONS or ext == "":
        try:
            with open(clean_p, "rb") as f:
                bytes_data = np.frombuffer(f.read(), dtype=np.uint8)
            bgr = cv2.imdecode(bytes_data, cv2.IMREAD_COLOR)
            if bgr is not None:
                return bgr
            with Image.open(clean_p) as pil_img:
                rgb = np.array(pil_img.convert("RGB"))
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            raise ImageLoadError(f"Image load error: {exc}")
    else:
        raise ImageLoadError(f"Unsupported format: {ext}")

load_image_as_rgb = load_image_safe

def save_image_safe(output_path: Union[str, Path], image_bgr: np.ndarray) -> Path:
    clean_p = sanitize_path(output_path, allow_creation=True)
    ext = clean_p.suffix.lower()

    try:
        if ext in ('.png', ''):
            success, buf = cv2.imencode('.png', image_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        elif ext in ('.jpg', '.jpeg'):
            success, buf = cv2.imencode('.jpg', image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        elif ext == '.webp':
            success, buf = cv2.imencode('.webp', image_bgr, [cv2.IMWRITE_WEBP_QUALITY, 95])
        else:
            success, buf = cv2.imencode('.png', image_bgr, [cv2.IMWRITE_PNG_COMPRESSION, 1])

        if not success:
            raise ImageLoadError(f"Failed to encode image for '{clean_p.name}'")

        with open(clean_p, "wb") as f:
            f.write(buf.tobytes())

        return clean_p
    except Exception as exc:
        raise ImageLoadError(f"Failed to save image file '{clean_p.name}': {exc}")

@dataclass
class ColorConfig:
    preset: str = "None (Original)"
    film_grain: float = 0.0

class FujiColorEngine:
    PRESETS = {
        "Classic Chrome": {"desat": 0.88, "contrast": 1.12},
        "Velvia (Vivid)": {"desat": 1.22, "contrast": 1.18},
        "Classic Negative": {"desat": 0.92, "contrast": 1.25},
        "Pro Neg.Hi": {"desat": 0.96, "contrast": 1.15},
        "Acros (B&W)": {"desat": 0.0, "contrast": 1.20},
    }

    @staticmethod
    def apply_color_science(tensor_rgb: torch.Tensor, config: ColorConfig) -> torch.Tensor:
        preset = config.preset if config else "None (Original)"
        if not preset or preset.startswith("None"):
            out_tensor = tensor_rgb
        else:
            if "Chrome" in preset:
                r, g, b = tensor_rgb[:, 0:1], tensor_rgb[:, 1:2], tensor_rgb[:, 2:3]
                r_out = 0.85 * r + 0.10 * g + 0.05 * b
                g_out = 0.05 * r + 0.85 * g + 0.10 * b
                b_out = 0.05 * r + 0.10 * g + 0.80 * b
                out_tensor = torch.cat([r_out, g_out, b_out], dim=1) * 0.95 + 0.02
            elif "Velvia" in preset:
                r, g, b = tensor_rgb[:, 0:1], tensor_rgb[:, 1:2], tensor_rgb[:, 2:3]
                r_out = 1.15 * r - 0.10 * g - 0.05 * b
                g_out = -0.05 * r + 1.20 * g - 0.15 * b
                b_out = -0.05 * r - 0.10 * g + 1.20 * b
                out_tensor = torch.cat([r_out, g_out, b_out], dim=1)
            elif "Negative" in preset:
                r, g, b = tensor_rgb[:, 0:1], tensor_rgb[:, 1:2], tensor_rgb[:, 2:3]
                r_out = 0.95 * r + 0.05 * g - 0.05 * b
                g_out = -0.05 * r + 0.90 * g + 0.15 * b
                b_out = 0.10 * r - 0.10 * g + 0.90 * b
                out_tensor = torch.cat([r_out, g_out, b_out], dim=1)
            elif "Pro Neg" in preset:
                r, g, b = tensor_rgb[:, 0:1], tensor_rgb[:, 1:2], tensor_rgb[:, 2:3]
                r_out = 1.05 * r - 0.03 * g - 0.02 * b
                g_out = 0.02 * r + 1.02 * g - 0.04 * b
                b_out = 0.01 * r - 0.02 * g + 1.01 * b
                out_tensor = torch.cat([r_out, g_out, b_out], dim=1)
            elif "Acros" in preset:
                gray = 0.299 * tensor_rgb[:, 0:1] + 0.587 * tensor_rgb[:, 1:2] + 0.114 * tensor_rgb[:, 2:3]
                out_tensor = torch.cat([gray, gray, gray], dim=1)
            else:
                out_tensor = tensor_rgb

        out_tensor = torch.clamp(out_tensor, 0.0, 1.0)
        grain_amount = getattr(config, 'film_grain', 0.0) if config else 0.0
        if grain_amount > 0.0:
            grain_intensity = (grain_amount / 1.0) * 0.05 if grain_amount <= 1.0 else (grain_amount / 100.0) * 0.05
            noise = torch.randn_like(out_tensor) * grain_intensity
            luminance = 0.299 * out_tensor[:, 0:1] + 0.587 * out_tensor[:, 1:2] + 0.114 * out_tensor[:, 2:3]
            midtone_mask = 4.0 * luminance * (1.0 - luminance)
            out_tensor = torch.clamp(out_tensor + noise * midtone_mask, 0.0, 1.0)

        return out_tensor

    @classmethod
    def apply_preset(cls, tensor_rgb: torch.Tensor, config: ColorConfig) -> torch.Tensor:
        return cls.apply_color_science(tensor_rgb, config)

class ResidualDenseBlock_5C(nn.Module):
    def __init__(self, nf=64, gc=32, bias=True):
        super(ResidualDenseBlock_5C, self).__init__()
        self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1, bias=bias)
        self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1, bias=bias)
        self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1, bias=bias)
        self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1, bias=bias)
        self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1, bias=bias)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x

class RRDB(nn.Module):
    def __init__(self, nf, gc=32):
        super(RRDB, self).__init__()
        self.rdb1 = ResidualDenseBlock_5C(nf, gc)
        self.rdb2 = ResidualDenseBlock_5C(nf, gc)
        self.rdb3 = ResidualDenseBlock_5C(nf, gc)

    def forward(self, x):
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x

class RRDBNet(nn.Module):
    def __init__(self, in_nc=3, out_nc=3, nf=64, nb=23, gc=32, scale=4):
        super(RRDBNet, self).__init__()
        self.scale = scale
        self.conv_first = nn.Conv2d(in_nc, nf, 3, 1, 1, bias=True)
        self.body = nn.Sequential(*[RRDB(nf=nf, gc=gc) for _ in range(nb)])
        self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
        self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
        self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
        self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1, bias=True)
        self.conv_last = nn.Conv2d(nf, out_nc, 3, 1, 1, bias=True)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x):
        fea = self.conv_first(x)
        body_fea = self.conv_body(self.body(fea))
        fea = fea + body_fea
        fea = self.lrelu(self.conv_up1(F.interpolate(fea, scale_factor=2, mode='nearest')))
        fea = self.lrelu(self.conv_up2(F.interpolate(fea, scale_factor=2, mode='nearest')))
        out = self.conv_last(self.lrelu(self.conv_hr(fea)))
        return out

class _BicubicUpscaleNet(nn.Module):
    def __init__(self, scale=4):
        super(_BicubicUpscaleNet, self).__init__()
        self.scale = scale

    def forward(self, x):
        return F.interpolate(x, scale_factor=self.scale, mode="bicubic", align_corners=False)

def clear_vram_cache():
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

class SuperResolutionEngine:
    def __init__(
        self,
        scale_factor: int = 4,
        config: Optional[ColorConfig] = None,
        log_callback: Optional[Callable[[str], None]] = None,
        device: str = "auto",
        model_type: str = "realesrgan",
        **kwargs: Any
    ) -> None:
        self.scale_factor = scale_factor
        self.color_config = config if config else ColorConfig()
        self.log_callback = log_callback
        self.model_type = model_type
        self.device = self._resolve_device(device)
        self.use_fp16 = True if self.device.type == "cuda" else False
        self.model = None

    def _resolve_device(self, requested: str) -> torch.device:
        if requested in ("auto", "cuda") and torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    def _log(self, msg: str) -> None:
        logger.info(msg)
        if self.log_callback:
            try: self.log_callback(msg)
            except Exception: pass

    def _load_model(self):
        if self.model is not None:
            return self.model

        if self.model_type == "bicubic":
            self._log("Using bicubic placeholder (Fast test mode).")
            self.model = _BicubicUpscaleNet(scale=self.scale_factor).to(self.device).eval()
            return self.model

        base_dir = Path(__file__).resolve().parent
        model_path = base_dir / "models" / "RealESRGAN_x4plus.pth"
        if not model_path.exists():
            model_path = base_dir / "RealESRGAN_x4plus.pth"

        if not model_path.exists():
            self._log("Model file not found. Falling back to bicubic placeholder.")
            self.model = _BicubicUpscaleNet(scale=self.scale_factor).to(self.device).eval()
            return self.model

        # SHA-256 integrity check
        expected_hash = _MODEL_SHA256.get(model_path.name)
        if expected_hash:
            if not verify_model_checksum(model_path, expected_hash):
                self._log(f"[SECURITY] SHA-256 mismatch for {model_path.name}! Deleting corrupted file.")
                model_path.unlink(missing_ok=True)
                raise SecurityError(
                    f"Model integrity check failed for '{model_path.name}'. "
                    f"The file has been deleted. Please re-download."
                )
            self._log(f"[SECURITY] SHA-256 verified OK: {model_path.name}")

        self._log(f"Model yükleniyor: {model_path.name}")
        net = RRDBNet(in_nc=3, out_nc=3, nf=64, nb=23, gc=32, scale=4)

        try:
            load_net = torch.load(str(model_path), map_location=self.device, weights_only=False)
            if "params_strict" in load_net: load_net = load_net["params_strict"]
            elif "params_ema" in load_net: load_net = load_net["params_ema"]
            elif "params" in load_net: load_net = load_net["params"]
            net.load_state_dict(load_net, strict=True)
        except Exception:
            try:
                load_net = torch.load(str(model_path), map_location=self.device)
                if "params_ema" in load_net: load_net = load_net["params_ema"]
                net.load_state_dict(load_net, strict=False)
            except Exception as exc:
                self._log(f"Model load warning ({exc}). Falling back to bicubic.")
                self.model = _BicubicUpscaleNet(scale=self.scale_factor).to(self.device).eval()
                return self.model

        net.eval()
        net.to(self.device)
        if self.use_fp16 and self.device.type == "cuda":
            net.half()

        self.model = net
        self._log("AI Modeli hazır.")
        return self.model

    def enhance_image(
        self,
        input_image: Union[str, Path, np.ndarray],
        color_config: Optional[ColorConfig] = None,
        use_auto_wb: bool = True,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> np.ndarray:
        if cancel_event and cancel_event.is_set():
            raise ImageLoadError("İşlem iptal edildi.")

        try:
            cfg = color_config if color_config else self.color_config

            if isinstance(input_image, (str, Path)):
                bgr = load_image_safe(input_image, use_auto_wb=use_auto_wb)
            elif isinstance(input_image, np.ndarray):
                bgr = input_image
            else:
                raise ImageLoadError(f"Invalid input image type: {type(input_image)}")

            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            net = self._load_model()

            if isinstance(net, _BicubicUpscaleNet):
                img_tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
                img_tensor = FujiColorEngine.apply_color_science(img_tensor, cfg)
                with torch.no_grad():
                    out_tensor = net(img_tensor)
                out_arr = out_tensor.squeeze(0).permute(1, 2, 0).detach().cpu().clamp(0, 1).numpy()
                out_rgb = (out_arr * 255.0).astype(np.uint8)
                if self.scale_factor == 2 and out_rgb.shape[:2] != (h * 2, w * 2):
                    out_rgb = cv2.resize(out_rgb, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)
                return cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)

            tile_size = 512
            if self.device.type == "cuda":
                try:
                    free_bytes, _ = torch.cuda.mem_get_info()
                    vram_gb = free_bytes / (1024 ** 3)
                    if vram_gb >= 8.0: tile_size = 512
                    elif vram_gb >= 4.0: tile_size = 384
                    elif vram_gb >= 2.0: tile_size = 256
                    else: tile_size = 192
                except Exception:
                    tile_size = 512

            out_rgb = self._run_tiled_with_oom_recovery(net, rgb, tile_size, cfg, cancel_event, progress_callback)

            if self.scale_factor == 2:
                self._log("2x Keskinleştirilmiş Boyutlandırma (Lanczos4)...")
                target_w, target_h = w * 2, h * 2
                out_rgb = cv2.resize(out_rgb, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

            return cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)
        finally:
            clear_vram_cache()

    def _run_tiled_with_oom_recovery(
        self, net: RRDBNet, rgb: np.ndarray, tile_size: int, config: ColorConfig, cancel_event: Optional[threading.Event], progress_callback: Optional[Callable[[float], None]]
    ) -> np.ndarray:
        current_tile = tile_size
        while True:
            try:
                if cancel_event and cancel_event.is_set():
                    raise ImageLoadError("İşlem iptal edildi.")
                return self._run_tiled_inference(net, rgb, current_tile, config, cancel_event, progress_callback)
            except torch.cuda.OutOfMemoryError:
                clear_vram_cache()
                if current_tile > 128:
                    current_tile //= 2
                    self._log(f"VRAM Doldu! Karo boyutu {current_tile}px seviyesine düşürüldü...")
                else:
                    raise CUDAOutOfMemoryError("Minimal karo boyutunda dahi VRAM yetersiz.")

    def _run_tiled_inference(
        self, net: RRDBNet, rgb: np.ndarray, tile_size: int, config: ColorConfig, cancel_event: Optional[threading.Event], progress_callback: Optional[Callable[[float], None]]
    ) -> np.ndarray:
        h, w, c = rgb.shape
        img_tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        img_tensor = img_tensor.to(self.device)

        img_tensor = FujiColorEngine.apply_color_science(img_tensor, config)

        if self.use_fp16 and self.device.type == "cuda":
            img_tensor = img_tensor.half()

        scale = 4
        pad = 10

        if tile_size <= 0 or (w <= tile_size and h <= tile_size):
            with torch.no_grad():
                with torch.cuda.amp.autocast(enabled=self.use_fp16 and self.device.type == "cuda"):
                    out_tensor = net(img_tensor)
            out_arr = out_tensor.squeeze(0).permute(1, 2, 0).detach().cpu().clamp(0, 1).numpy()
            return (out_arr * 255.0).astype(np.uint8)

        out_h, out_w = h * scale, w * scale
        output_tensor = torch.zeros((c, out_h, out_w), dtype=img_tensor.dtype, device=self.device)

        tiles_x = (w + tile_size - 1) // tile_size
        tiles_y = (h + tile_size - 1) // tile_size
        total_tiles = tiles_x * tiles_y
        tile_count = 0

        for y in range(0, h, tile_size):
            for x in range(0, w, tile_size):
                if cancel_event and cancel_event.is_set():
                    raise ImageLoadError("İşlem iptal edildi.")

                x1, x2 = max(x - pad, 0), min(x + tile_size + pad, w)
                y1, y2 = max(y - pad, 0), min(y + tile_size + pad, h)

                tile_in = img_tensor[:, :, y1:y2, x1:x2]

                with torch.no_grad():
                    with torch.cuda.amp.autocast(enabled=self.use_fp16 and self.device.type == "cuda"):
                        tile_out = net(tile_in)

                rx1, rx2 = (x - x1) * scale, (x - x1 + min(tile_size, w - x)) * scale
                ry1, ry2 = (y - y1) * scale, (y - y1 + min(tile_size, h - y)) * scale
                ox1, ox2 = x * scale, min(x + tile_size, w) * scale
                oy1, oy2 = y * scale, min(y + tile_size, h) * scale

                output_tensor[:, oy1:oy2, ox1:ox2] = tile_out[0, :, ry1:ry2, rx1:rx2]
                del tile_out  # Explicit tensor cleanup

                tile_count += 1
                if progress_callback:
                    progress_callback(tile_count / total_tiles)

        out_arr = output_tensor.permute(1, 2, 0).detach().cpu().clamp(0, 1).numpy()
        return (out_arr * 255.0).astype(np.uint8)

ImageUpscaler = SuperResolutionEngine
InferenceConfig = ColorConfig
CorruptImageError = ImageLoadError
InterruptedException = ImageLoadError
