# -*- coding: utf-8 -*-
"""
test_env.py -- ML Ortam Dogrulama Scripti
==========================================
PyTorch (CUDA), OpenCV ve CustomTkinter kurulumunu
dogrular; GPU bilgilerini ayrintili olarak raporlar.
"""

import sys
import io
import platform

# Windows terminali icin UTF-8 zorunlu
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

RESET   = "\033[0m"
BOLD    = "\033[1m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"

def ok(msg):   print(f"  {GREEN}[OK]  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}[!!]  {msg}{RESET}")
def fail(msg): print(f"  {RED}[XX]  {msg}{RESET}")
def info(msg): print(f"  {CYAN}[..] {msg}{RESET}")

def section(title):
    print()
    print(f"{BOLD}{BLUE}{'='*58}{RESET}")
    print(f"{BOLD}{MAGENTA}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*58}{RESET}")

# --- Sistem Bilgisi --------------------------------------------------
section("SISTEM BILGISI")
info(f"Isletim Sistemi  : {platform.system()} {platform.release()} ({platform.version()})")
info(f"Makine Adi       : {platform.node()}")
info(f"Mimari           : {platform.machine()}")
info(f"Python Surumu    : {sys.version}")

# --- PyTorch ---------------------------------------------------------
section("PyTorch (CUDA)")
try:
    import torch
    ok(f"PyTorch surumu   : {torch.__version__}")

    cuda_available = torch.cuda.is_available()
    if cuda_available:
        ok(f"CUDA Destegi     : AKTIF  (CUDA {torch.version.cuda})")
        try:
            ok(f"cuDNN Surumu     : {torch.backends.cudnn.version()}")
        except Exception:
            warn("cuDNN surumu alinamadi")

        gpu_count = torch.cuda.device_count()
        ok(f"GPU Sayisi       : {gpu_count}")

        for i in range(gpu_count):
            name  = torch.cuda.get_device_name(i)
            props = torch.cuda.get_device_properties(i)
            total_mem = props.total_memory / (1024**3)
            ok(f"GPU {i}            : {name}")
            info(f"   Toplam Bellek : {total_mem:.2f} GB")
            info(f"   SM Sayisi     : {props.multi_processor_count}")
            info(f"   CUDA Yetenegii: {props.major}.{props.minor}")

        # GPU tensör testi
        try:
            x = torch.randn(1000, 1000, device="cuda")
            y = torch.randn(1000, 1000, device="cuda")
            z = torch.matmul(x, y)
            ok(f"GPU Matmul Testi : Basarili  (1000x1000 -> shape {tuple(z.shape)})")
        except Exception as e:
            fail(f"GPU Matmul Testi : {e}")
    else:
        warn("CUDA Destegi     : YOK -- CPU modu kullaniliyor")

except ImportError as e:
    fail(f"PyTorch bulunamadi: {e}")

# --- OpenCV ----------------------------------------------------------
section("OpenCV")
try:
    import cv2
    ok(f"OpenCV surumu    : {cv2.__version__}")

    # Basit goruntu isleme testi
    import numpy as np
    img      = np.zeros((100, 100, 3), dtype=np.uint8)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ok(f"Goruntu Testi    : Basarili  (100x100 BGR->GRAY, shape {img_gray.shape})")

    # Gaussian blur testi
    blurred = cv2.GaussianBlur(img, (5, 5), 0)
    ok(f"GaussianBlur     : Basarili  (shape {blurred.shape})")

except ImportError as e:
    fail(f"OpenCV bulunamadi: {e}")

# --- CustomTkinter ---------------------------------------------------
section("CustomTkinter")
try:
    import customtkinter as ctk
    ok(f"CustomTkinter    : {ctk.__version__}")

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    ok(f"Tkinter          : v{tk.TkVersion}")
    root.destroy()
    ok("GUI Baslatma     : Basarili (headless)")

except ImportError as e:
    fail(f"CustomTkinter bulunamadi: {e}")
except Exception as e:
    warn(f"CustomTkinter GUI testi: {e}")

# --- Ozet ------------------------------------------------------------
section("OZET")
results = {}
try:
    import torch
    results["PyTorch"] = torch.__version__
except ImportError:
    results["PyTorch"] = None

try:
    import cv2
    results["OpenCV"] = cv2.__version__
except ImportError:
    results["OpenCV"] = None

try:
    import customtkinter as ctk
    results["CustomTkinter"] = ctk.__version__
except ImportError:
    results["CustomTkinter"] = None

all_ok = all(v is not None for v in results.values())

for lib, ver in results.items():
    if ver:
        ok(f"{lib:<16}: v{ver}")
    else:
        fail(f"{lib:<16}: EKSIK")

print()
try:
    import torch
    if torch.cuda.is_available():
        ok(f"GPU Hizlandirma  : {torch.cuda.get_device_name(0)} uzerinde AKTIF")
    else:
        warn("GPU Hizlandirma  : Mevcut degil (CPU modu)")
except Exception:
    pass

print()
if all_ok:
    print(f"{BOLD}{GREEN}{'='*58}{RESET}")
    print(f"{BOLD}{GREEN}  Tum kutuphaneler basariyla yuklendi ve dogrulandi!{RESET}")
    print(f"{BOLD}{GREEN}{'='*58}{RESET}")
else:
    print(f"{BOLD}{RED}{'='*58}{RESET}")
    print(f"{BOLD}{RED}  Bazi kutuphaneler eksik!{RESET}")
    print(f"{BOLD}{RED}{'='*58}{RESET}")
print()
