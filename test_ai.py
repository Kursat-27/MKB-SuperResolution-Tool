# -*- coding: utf-8 -*-
"""
test_ai.py  --  Faz 2 Dogrulama Betigi
=======================================
- 100x100 piksellik test gorseli uretir
- ImageUpscaler ile 400x400 boyutuna buyutur
- Sonucu diske kaydeder
- Hatasiz tamamlanirsa 'Faz 2 Tamamlandi' yazar
"""

import sys
import io
import time
import traceback
from pathlib import Path

import cv2
import numpy as np
import torch

# Windows terminali icin UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from ai_engine import ImageUpscaler, download_model_weights

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BLUE   = "\033[94m"
MAG    = "\033[95m"

def ok(msg):   print(f"  {GREEN}[OK]  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}[!!]  {msg}{RESET}")
def fail(msg): print(f"  {RED}[XX]  {msg}{RESET}")
def info(msg): print(f"  {CYAN}[..] {msg}{RESET}")

def section(title):
    print()
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{MAG}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}")


def create_test_image(size: int = 100) -> np.ndarray:
    """
    100x100 piksellik rengarenk, yapisal bir test gorseli olusturur.
    Dusuk cozunurluklu goruntu; upscaler'in ne yaptigini gormeyi saglar.
    """
    img = np.zeros((size, size, 3), dtype=np.uint8)

    # Renkli kadranlara bol
    h2, w2 = size // 2, size // 2
    img[:h2, :w2]  = [220, 50,  50]   # Kirmizi
    img[:h2, w2:]  = [50, 200,  50]   # Yesil
    img[h2:, :w2]  = [50,  50, 220]   # Mavi
    img[h2:, w2:]  = [200, 200, 50]   # Sari

    # Ortaya beyaz daire
    cx, cy, r = size // 2, size // 2, size // 5
    cv2.circle(img, (cx, cy), r, (255, 255, 255), -1)

    # Kose kontrol noktalari
    cv2.circle(img, (5, 5),         3, (255, 0, 255), -1)
    cv2.circle(img, (size-6, 5),    3, (0, 255, 255), -1)
    cv2.circle(img, (5, size-6),    3, (0, 255, 255), -1)
    cv2.circle(img, (size-6, size-6), 3, (255, 128, 0), -1)

    # Ince cizgiler (edge detection zorlu)
    cv2.line(img, (0, size//2), (size, size//2), (255, 255, 255), 1)
    cv2.line(img, (size//2, 0), (size//2, size), (255, 255, 255), 1)

    return img


def run_test():
    section("FAZ 2 -- YZ CEKIRDEK ENTEGRASYON TESTI")

    errors = []
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)

    # ── Adim 1: GPU Durumu ─────────────────────────────────
    section("Adim 1/4 -- Sistem Kontrolu")
    if torch.cuda.is_available():
        ok(f"GPU Algilandi : {torch.cuda.get_device_name(0)}")
        ok(f"CUDA Surumu   : {torch.version.cuda}")
        mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        info(f"GPU Bellegi   : {mem:.1f} GB")
    else:
        warn("GPU yok -- CPU modu kullanilacak")

    # ── Adim 2: Model Agirliklarini Indir ─────────────────
    section("Adim 2/4 -- Model Agirliklarini Hazirla")
    try:
        t0 = time.time()
        model_path = download_model_weights("RealESRGAN_x4plus", save_dir="models")
        dt = time.time() - t0
        size_mb = model_path.stat().st_size / (1024**2)
        ok(f"Model dosyasi : {model_path.name}  ({size_mb:.1f} MB)")
        ok(f"Sure          : {dt:.1f}s  ({'Zaten mevcuttu' if dt < 2 else 'indirildi'})")
    except Exception as e:
        fail(f"Model indirme hatasi: {e}")
        errors.append(str(e))
        traceback.print_exc()

    # ── Adim 3: Test Gorseli Olustur ──────────────────────
    section("Adim 3/4 -- Test Gorseli Uret ve Upscale Et")
    try:
        # 100x100 test gorseli
        img_lr = create_test_image(100)
        assert img_lr.shape == (100, 100, 3), f"Gorsel boyutu hatali: {img_lr.shape}"
        ok(f"Gorsel olusturuldu : {img_lr.shape[1]}x{img_lr.shape[0]} piksel (BGR)")

        # Diske kaydet (giris)
        input_path = str(output_dir / "test_input_100x100.png")
        cv2.imwrite(input_path, img_lr)
        ok(f"Giris kaydedildi   : {input_path}")

        # ImageUpscaler yukle
        info("Model yukleniyor (ilk yuklemede birkac saniye surebilir)...")
        t0 = time.time()
        upscaler = ImageUpscaler(
            model_name     = "RealESRGAN_x4plus",
            models_dir     = "models",
            half_precision = torch.cuda.is_available(),   # GPU varsa float16
            tile           = 512,
        )
        load_time = time.time() - t0
        ok(f"Model yuklemesi    : {load_time:.2f}s")
        info(str(upscaler))

        # Upscale!
        info("Upscale basliyor: 100x100  ->  400x400 ...")
        t0 = time.time()
        img_hr = upscaler.upscale(img_lr)
        proc_time = time.time() - t0

        # Boyut dogrulama
        assert img_hr.shape == (400, 400, 3), \
            f"Beklenen (400,400,3), alinan {img_hr.shape}"
        ok(f"Upscale tamamlandi : {img_hr.shape[1]}x{img_hr.shape[0]}  ({proc_time:.2f}s)")

        # Diske kaydet (cikis)
        output_path = str(output_dir / "test_output_400x400.png")
        cv2.imwrite(output_path, img_hr)
        ok(f"Cikis kaydedildi   : {output_path}")

        # Piksel denetimi
        assert img_hr.dtype == np.uint8, "uint8 bekleniyor"
        assert img_hr.min() >= 0 and img_hr.max() <= 255, "Piksel degerleri aralik disi"
        ok(f"Piksel denetimi    : min={img_hr.min()}, max={img_hr.max()}, dtype={img_hr.dtype}")

    except Exception as e:
        fail(f"Gorsel isleme hatasi: {e}")
        errors.append(str(e))
        traceback.print_exc()

    # ── Adim 4: GPU Bellek Raporu ──────────────────────────
    section("Adim 4/4 -- GPU Bellek Raporu")
    try:
        if torch.cuda.is_available():
            alloc   = torch.cuda.memory_allocated(0)  / (1024**2)
            reserved = torch.cuda.memory_reserved(0)  / (1024**2)
            ok(f"Kullanilan GPU bellegi  : {alloc:.1f} MB")
            info(f"Rezerve GPU bellegi   : {reserved:.1f} MB")
            torch.cuda.empty_cache()
            ok("GPU bellegi temizlendi")
        else:
            info("GPU mevcut degil, bellek raporu atlanadi")
    except Exception as e:
        warn(f"GPU bellek raporu alinamadi: {e}")

    # ── Final Ozet ─────────────────────────────────────────
    section("OZET")
    if not errors:
        print()
        print(f"{BOLD}{GREEN}{'='*60}{RESET}")
        print(f"{BOLD}{GREEN}  Faz 2 Tamamlandi{RESET}")
        print(f"{BOLD}{GREEN}  Real-ESRGAN x4plus ile GPU upscale basarili!{RESET}")
        print(f"{BOLD}{GREEN}{'='*60}{RESET}")
        print()
        info(f"Giris gorseli  : test_outputs/test_input_100x100.png")
        info(f"Cikis gorseli  : test_outputs/test_output_400x400.png")
        print()
        return True
    else:
        print()
        print(f"{BOLD}{RED}{'='*60}{RESET}")
        print(f"{BOLD}{RED}  TEST BASARISIZ -- {len(errors)} hata{RESET}")
        for e in errors:
            print(f"  {RED}- {e}{RESET}")
        print(f"{BOLD}{RED}{'='*60}{RESET}")
        print()
        return False


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
