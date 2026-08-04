"""
app_gui.py
─────────────────────────────────────────────────────────────────────────────
Module: MKB AI Super Resolution Tool - Desktop GUI Application (v7.1 Production Ready)
Features:
  - Clean, Spacious, Elegant Layout (Matches Original Image 1 Design)
  - Single Image & Camera RAW Processing (PNG, JPG, WEBP, RAF, CR2, CR3, NEF, ARW, DNG)
  - 280px Left Sidebar Container:
      * Logo Area: MKB AI SUPER RESOLUTION, Powered by Real-ESRGAN + RAW, Developed by MKB
      * Görsel Seçimi: Clean "Görsel / RAW Yükle" button + Selected Filename Label (No cramped path textboxes)
      * Büyütme Ayarları: Çözünürlük Çarpanı (4x, 2x) + Çıktı Formatı (PNG, JPG, WEBP)
      * RAW Kamera Ayarları: Kamera Beyaz Dengesi (WB) Checkbox
      * Fujifilm Color Science: Presets Dropdown + 0-100% Film Grain Slider
      * Action Controls: Large Green "▶ İşlemi Başlat" (40px) + Red "■ İşlemi Durdur" (40px)
      * GPU Status Badge: "GPU Aktif (CUDA)" + Footer Version
  - Main Area (Tabview Workspace): "Giriş", "Çıkış", "Karşılaştır"
  - Enlarged Live Log Console (Height 200 / 10 lines) & Status Bar
  - Non-blocking Queue Event Loop (0% UI Freeze)
  - Clean WM_DELETE_WINDOW Shutdown Protocol & VRAM Clearance
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np
from PIL import Image, ImageTk

import customtkinter as ctk
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_TKINTERDND2: bool = True
except ImportError:
    HAS_TKINTERDND2 = False
    DND_FILES = "DND_Files"

    class TkinterDnD:  # type: ignore[no-redef]
        class DnDWrapper:
            def drop_target_register(self, *args: Any, **kwargs: Any) -> None:
                pass

            def dnd_bind(self, *args: Any, **kwargs: Any) -> None:
                pass

from ai_engine import ColorConfig, FujiColorEngine, ImageUpscaler, SecurityError, SuperResolutionEngine, load_image_safe, sanitize_path, save_image_safe

try:
    import torch
    HAS_TORCH: bool = True
except ImportError:
    HAS_TORCH = False
    torch = None  # type: ignore[assignment]


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Global Color Palette Constants
_C_BG: str = "#0a0a0f"
_C_SIDEBAR: str = "#12121d"
_C_CARD: str = "#1e1e2a"
_C_CARD_HOVER: str = "#222233"
_C_LOG_PANEL: str = "#161624"
_C_ACCENT: str = "#a855f7"
_C_ACCENT_HOVER: str = "#9333ea"
_C_SUCCESS: str = "#10b981"
_C_SUCCESS_HOVER: str = "#059669"
_C_WARN: str = "#f59e0b"
_C_ERR: str = "#ef4444"
_C_ERROR: str = "#ef4444"
_C_ERROR_HOVER: str = "#dc2626"
_C_INFO: str = "#3b82f6"
_C_TEXT: str = "#f1f5f9"
_C_DIM: str = "#94a3b8"
_C_BORDER: str = "#26263a"


class WorkerThread(threading.Thread):
    """Background worker thread for executing AI Image upscaling without freezing the GUI."""

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        scale_factor: int,
        color_config: ColorConfig,
        use_auto_wb: bool,
        ui_queue: Queue[Tuple[str, Any]],
        cancel_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True, name="ImageWorker")
        self.input_path = input_path
        self.output_path = output_path
        self.scale_factor = scale_factor
        self.color_config = color_config
        self.use_auto_wb = use_auto_wb
        self.q = ui_queue
        self.cancel_event = cancel_event

    def _post(self, event_type: str, payload: Any = None) -> None:
        try:
            self.q.put_nowait((event_type, payload))
        except Exception:
            pass

    def run(self) -> None:
        try:
            self._post("stage", "Görsel Yükleniyor...")
            self._post("log", f"Girdi görseli okunuyor: {self.input_path.name}")

            upscaler = SuperResolutionEngine(
                scale_factor=self.scale_factor,
                config=self.color_config,
                log_callback=lambda msg: self._post("log", msg),
            )

            def _on_progress(ratio: float) -> None:
                self._post("progress", ratio)

            self._post("stage", "AI Büyütme & Renk Simülasyonu Uygulanıyor...")
            out_bgr = upscaler.enhance_image(
                input_image=self.input_path,
                color_config=self.color_config,
                use_auto_wb=self.use_auto_wb,
                cancel_event=self.cancel_event,
                progress_callback=_on_progress,
            )

            if self.cancel_event.is_set():
                self._post("cancelled")
                return

            self._post("stage", "Çıktı Kaydediliyor...")
            final_path = save_image_safe(self.output_path, out_bgr)
            self._post("done", (final_path, out_bgr))

        except Exception as exc:
            import traceback
            self._post("error", traceback.format_exc())


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    """MKB AI Super Resolution Desktop Application (Clean UI Design)."""

    _C_BG = _C_BG
    _C_SIDEBAR = _C_SIDEBAR
    _C_CARD = _C_CARD
    _C_CARD_HOVER = _C_CARD_HOVER
    _C_LOG_PANEL = _C_LOG_PANEL
    _C_ACCENT = _C_ACCENT
    _C_ACCENT_HOVER = _C_ACCENT_HOVER
    _C_SUCCESS = _C_SUCCESS
    _C_SUCCESS_HOVER = _C_SUCCESS_HOVER
    _C_WARN = _C_WARN
    _C_ERR = _C_ERR
    _C_ERROR = _C_ERROR
    _C_ERROR_HOVER = _C_ERROR_HOVER
    _C_INFO = _C_INFO
    _C_TEXT = _C_TEXT
    _C_DIM = _C_DIM
    _C_BORDER = _C_BORDER

    def __init__(self) -> None:
        super().__init__()

        if HAS_TKINTERDND2:
            self.TkdndVersion = TkinterDnD._require(self)

        self.title("MKB AI Super Resolution Tool")
        self.geometry("1180x880")
        self.minsize(1020, 740)
        self.configure(fg_color=self._C_BG)

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._worker: Optional[WorkerThread] = None
        self._cancel_event: threading.Event = threading.Event()
        self._ui_queue: Queue[Tuple[str, Any]] = Queue()
        self._processing: bool = False

        self._selected_input_path: Optional[Path] = None
        self._input_image_bgr: Optional[np.ndarray] = None
        self._output_image_bgr: Optional[np.ndarray] = None

        self._build_clean_layout()

        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>", self._on_drop)

        self._poll_ui_queue()
        threading.Thread(target=self._probe_device, daemon=True).start()

    def _on_closing(self) -> None:
        if self._processing and self._worker and self._worker.is_alive():
            if mb.askokcancel("Çıkış", "İşlem devam ediyor. İptal edip çıkmak istiyor musunuz?"):
                self._cancel_event.set()
                self._worker.join(timeout=3.0)
                self._cleanup_gpu()
                self.destroy()
                os._exit(0)
        else:
            self._cleanup_gpu()
            self.destroy()
            os._exit(0)

    def _cleanup_gpu(self) -> None:
        """Deterministic GPU memory release on shutdown."""
        try:
            import gc
            gc.collect()
            if HAS_TORCH and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()
        except Exception:
            pass

    def _probe_device(self) -> None:
        try:
            if HAS_TORCH and torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                self.after(
                    0,
                    lambda: self._gpu_badge.configure(
                        text=f"GPU Aktif ({name})", text_color=self._C_SUCCESS
                    ),
                )
            else:
                self.after(
                    0,
                    lambda: self._gpu_badge.configure(
                        text="CPU Modu (PyTorch CUDA Yok)", text_color=self._C_DIM
                    ),
                )
        except Exception:
            self.after(
                0,
                lambda: self._gpu_badge.configure(
                    text="Torch missing", text_color=self._C_ERROR
                ),
            )

    # ────────────────────────────────────────────────────────────
    # Clean UI Layout: 280px Left Sidebar + Spacious Right Main Workspace
    # ────────────────────────────────────────────────────────────

    def _build_clean_layout(self) -> None:
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=14, pady=14)

        # ── 1. LEFT SIDEBAR CONTAINER (Width 280px) ──
        sidebar_frame = ctk.CTkFrame(main_frame, fg_color=self._C_SIDEBAR, corner_radius=16, width=280)
        sidebar_frame.pack(side="left", fill="y", padx=(0, 14))
        sidebar_frame.pack_propagate(False)

        # Visible right border for sidebar
        sidebar_border = ctk.CTkFrame(main_frame, fg_color="#2a2a3e", width=1)
        sidebar_border.pack(side="left", fill="y")

        # Top Scrollable Content inside Sidebar
        sidebar_scroll = ctk.CTkScrollableFrame(sidebar_frame, fg_color="transparent", corner_radius=0)
        sidebar_scroll.pack(side="top", fill="both", expand=True, padx=8, pady=(12, 0))

        # Fixed Bottom Panel inside Sidebar
        sidebar_bottom = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
        sidebar_bottom.pack(side="bottom", fill="x", padx=12, pady=14)

        # ── 2. RIGHT MAIN WORKSPACE ──
        right_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        right_frame.pack(side="left", fill="both", expand=True)

        # Populate Sidebar Top Scroll Area
        self._build_sidebar_logo(sidebar_scroll)
        self._build_sidebar_card_input(sidebar_scroll)
        self._build_sidebar_card_settings(sidebar_scroll)
        self._build_sidebar_card_raw(sidebar_scroll)
        self._build_sidebar_card_fuji(sidebar_scroll)

        # Populate Sidebar Fixed Bottom Panel
        self._build_sidebar_bottom_controls(sidebar_bottom)

        # Populate Right Main Workspace
        self._build_workspace_tabs(right_frame)
        self._build_log_console_and_progress(right_frame)

    # ── Sidebar Section Card Builder Helper ──

    def _make_section_card(self, parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=self._C_CARD, corner_radius=12)
        outer.pack(fill="x", pady=6)

        ctk.CTkLabel(
            outer, text=title,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=self._C_ACCENT,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 4))

        ctk.CTkFrame(
            outer, fg_color=self._C_BORDER, height=1, corner_radius=0
        ).pack(fill="x", padx=12, pady=(0, 6))

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=(0, 8))
        return inner

    # ── Sidebar Logo Header ──

    def _build_sidebar_logo(self, parent: ctk.CTkFrame) -> None:
        logo_box = ctk.CTkFrame(parent, fg_color="transparent")
        logo_box.pack(fill="x", padx=4, pady=(0, 10))

        ctk.CTkLabel(
            logo_box, text="MKB AI SUPER RESOLUTION",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=self._C_ACCENT, anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            logo_box, text="Powered by Real-ESRGAN + RAW",
            font=ctk.CTkFont(size=11),
            text_color=self._C_TEXT, anchor="w",
        ).pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(
            logo_box, text="Developed by MKB",
            font=ctk.CTkFont(size=10),
            text_color=self._C_DIM, anchor="w",
        ).pack(fill="x", pady=(1, 0))

    # ── Sidebar Card 1: GÖRSEL SEÇİMİ ──

    def _build_sidebar_card_input(self, parent: ctk.CTkFrame) -> None:
        inner = self._make_section_card(parent, "GÖRSEL SEÇİMİ")

        self._upload_btn = ctk.CTkButton(
            inner, text="Görsel / RAW Yükle",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=self._C_ACCENT, hover_color=self._C_ACCENT_HOVER,
            text_color="#ffffff", height=38, corner_radius=10,
            command=self._browse_input,
        )
        self._upload_btn.pack(fill="x", pady=(2, 6))

        self._filename_lbl = ctk.CTkLabel(
            inner, text="Henüz dosya seçilmedi",
            font=ctk.CTkFont(size=10),
            text_color=self._C_DIM,
            wraplength=230, anchor="w",
        )
        self._filename_lbl.pack(fill="x", padx=2)

    # ── Sidebar Card 2: BÜYÜTME AYARLARI ──

    def _build_sidebar_card_settings(self, parent: ctk.CTkFrame) -> None:
        inner = self._make_section_card(parent, "BÜYÜTME AYARLARI")

        ctk.CTkLabel(
            inner, text="Çözünürlük Çarpanı",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=self._C_DIM, anchor="w"
        ).pack(fill="x", pady=(2, 2))

        self._scale_var = tk.StringVar(value="4x")
        ctk.CTkOptionMenu(
            inner, values=["4x", "2x"], variable=self._scale_var,
            fg_color=self._C_BG, button_color=self._C_ACCENT,
            button_hover_color=self._C_ACCENT_HOVER, text_color=self._C_TEXT,
            dropdown_fg_color=self._C_CARD, dropdown_text_color=self._C_TEXT,
            height=32, corner_radius=8,
        ).pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            inner, text="ÇIKTI FORMATI",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=self._C_DIM, anchor="w"
        ).pack(fill="x", pady=(2, 2))

        self._fmt_var = tk.StringVar(value="PNG")
        ctk.CTkSegmentedButton(
            inner, values=["PNG", "JPG", "WEBP"], variable=self._fmt_var,
            selected_color=self._C_ACCENT, selected_hover_color=self._C_ACCENT_HOVER,
            unselected_color=self._C_BG, unselected_hover_color=self._C_CARD_HOVER,
            text_color=self._C_TEXT, height=30, corner_radius=8,
        ).pack(fill="x")

    # ── Sidebar Card 3: RAW KAMERA AYARLARI ──

    def _build_sidebar_card_raw(self, parent: ctk.CTkFrame) -> None:
        inner = self._make_section_card(parent, "RAW KAMERA AYARLARI")

        self._raw_wb_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            inner,
            text="Kamera Beyaz Dengesi (WB)",
            variable=self._raw_wb_var,
            checkbox_width=18, checkbox_height=18,
            fg_color=self._C_ACCENT, hover_color=self._C_ACCENT_HOVER,
            text_color=self._C_TEXT,
            font=ctk.CTkFont(size=11),
        ).pack(fill="x", pady=2)

    # ── Sidebar Card 4: FUJIFILM COLOR SCIENCE ──

    def _build_sidebar_card_fuji(self, parent: ctk.CTkFrame) -> None:
        inner = self._make_section_card(parent, "FUJIFILM COLOR SCIENCE")

        ctk.CTkLabel(
            inner, text="Film Simülasyonu Preseti:",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=self._C_DIM, anchor="w"
        ).pack(fill="x", pady=(2, 2))

        self.color_preset_var = tk.StringVar(value="None (Original)")

        ctk.CTkOptionMenu(
            inner,
            values=[
                "None (Original)",
                "Classic Chrome",
                "Velvia (Vivid)",
                "Classic Negative",
                "Pro Neg.Hi",
                "Acros (B&W)",
            ],
            variable=self.color_preset_var,
            fg_color=self._C_BG, button_color=self._C_ACCENT,
            button_hover_color=self._C_ACCENT_HOVER, text_color=self._C_TEXT,
            dropdown_fg_color=self._C_CARD, dropdown_text_color=self._C_TEXT,
            height=32, corner_radius=8,
        ).pack(fill="x", pady=(0, 6))

        grain_hdr = ctk.CTkFrame(inner, fg_color="transparent")
        grain_hdr.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(
            grain_hdr, text="Film Grain Oranı:",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=self._C_DIM,
        ).pack(side="left")

        self._grain_val_lbl = ctk.CTkLabel(
            grain_hdr, text="0%",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=self._C_ACCENT,
        )
        self._grain_val_lbl.pack(side="right")

        self._grain_slider = ctk.CTkSlider(
            inner, from_=0, to=100, number_of_steps=100,
            fg_color=self._C_BG, progress_color=self._C_ACCENT,
            button_color=self._C_ACCENT, button_hover_color=self._C_ACCENT_HOVER,
            command=self._on_grain_slider_moved,
        )
        self._grain_slider.set(0)
        self._grain_slider.pack(fill="x", pady=(4, 2))

    def _on_grain_slider_moved(self, value: float) -> None:
        pct = int(value)
        self._grain_val_lbl.configure(text=f"{pct}%")

    # ── Sidebar Fixed Bottom Controls ──

    def _build_sidebar_bottom_controls(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkFrame(parent, fg_color=self._C_BORDER, height=1, corner_radius=0).pack(fill="x", pady=(0, 10))

        self._start_btn = ctk.CTkButton(
            parent, text="▶   İşlemi Başlat", command=self._on_start,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=self._C_SUCCESS, hover_color=self._C_SUCCESS_HOVER,
            text_color="#ffffff", height=40, corner_radius=12,
        )
        self._start_btn.pack(fill="x", pady=(0, 6))

        self._cancel_btn = ctk.CTkButton(
            parent, text="■   İşlemi Durdur", command=self._on_cancel,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self._C_ERROR, hover_color=self._C_ERROR_HOVER,
            text_color="#ffffff", height=40, corner_radius=10,
            state="disabled",
        )
        self._cancel_btn.pack(fill="x", pady=(0, 10))

        self._gpu_badge = ctk.CTkLabel(
            parent, text="GPU Aktif (CUDA)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self._C_SUCCESS, fg_color=self._C_CARD,
            corner_radius=10, padx=10, pady=5,
        )
        self._gpu_badge.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(
            parent, text="v7.1 · Production Ready",
            font=ctk.CTkFont(size=9), text_color=self._C_DIM, anchor="center",
        ).pack(fill="x")

    # ────────────────────────────────────────────────────────────
    # Main Area: Workspace Tabview & Central Canvas
    # ────────────────────────────────────────────────────────────

    def _build_workspace_tabs(self, parent: ctk.CTkFrame) -> None:
        self.tabview = ctk.CTkTabview(
            parent, fg_color=self._C_SIDEBAR, corner_radius=16,
            segmented_button_selected_color=self._C_ACCENT,
            segmented_button_selected_hover_color=self._C_ACCENT_HOVER,
            segmented_button_unselected_color=self._C_CARD,
        )
        self.tabview.pack(fill="both", expand=True, pady=(0, 10))

        self.tab_input = self.tabview.add("Giriş")
        self.tab_output = self.tabview.add("Çıkış")
        self.tab_compare = self.tabview.add("Karşılaştır")

        # Tab 1: Giriş Preview Canvas
        self._input_lbl = ctk.CTkLabel(
            self.tab_input,
            text="Görsel veya RAW Kamera Dosyası Yükleyin\n(PNG, JPG, WEBP, RAF, CR2, NEF, ARW, DNG...)",
            font=ctk.CTkFont(size=13), text_color=self._C_DIM,
        )
        self._input_lbl.pack(expand=True, fill="both", padx=16, pady=16)

        # Tab 2: Çıkış Preview Canvas
        self._output_lbl = ctk.CTkLabel(
            self.tab_output, text="Henüz AI Büyütme Uygulanmadı",
            font=ctk.CTkFont(size=13), text_color=self._C_DIM,
        )
        self._output_lbl.pack(expand=True, fill="both", padx=16, pady=16)

        # Tab 3: Karşılaştır Side-by-Side Canvas
        comp_frame = ctk.CTkFrame(self.tab_compare, fg_color="transparent")
        comp_frame.pack(fill="both", expand=True, padx=8, pady=8)
        comp_frame.columnconfigure(0, weight=1)
        comp_frame.columnconfigure(1, weight=1)

        box_orig = ctk.CTkFrame(comp_frame, fg_color=self._C_CARD, corner_radius=12)
        box_orig.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        ctk.CTkLabel(box_orig, text="Orijinal Görsel", font=ctk.CTkFont(size=12, weight="bold"), text_color=self._C_ACCENT).pack(pady=6)
        self._comp_orig_lbl = ctk.CTkLabel(box_orig, text="Yüklenmedi", text_color=self._C_DIM)
        self._comp_orig_lbl.pack(expand=True, fill="both")

        box_out = ctk.CTkFrame(comp_frame, fg_color=self._C_CARD, corner_radius=12)
        box_out.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        ctk.CTkLabel(box_out, text="AI Super Resolution + Fujifilm Color", font=ctk.CTkFont(size=12, weight="bold"), text_color=self._C_SUCCESS).pack(pady=6)
        self._comp_out_lbl = ctk.CTkLabel(box_out, text="Büyütülmedi", text_color=self._C_DIM)
        self._comp_out_lbl.pack(expand=True, fill="both")

    def _build_log_console_and_progress(self, parent: ctk.CTkFrame) -> None:
        outer = ctk.CTkFrame(parent, fg_color=self._C_LOG_PANEL, corner_radius=14, border_width=1, border_color="#33334d")
        outer.pack(fill="both", expand=True, side="bottom")

        top_row = ctk.CTkFrame(outer, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(8, 2))

        self._stage_label = ctk.CTkLabel(
            top_row, text="Hazır",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self._C_DIM, anchor="w",
        )
        self._stage_label.pack(side="left")

        self._progress_bar = ctk.CTkProgressBar(
            outer, orientation="horizontal", mode="determinate",
            progress_color=self._C_ACCENT, fg_color=self._C_BG,
            height=12, corner_radius=6,
        )
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=14, pady=(2, 8))

        log_hdr = ctk.CTkFrame(outer, fg_color="transparent")
        log_hdr.pack(fill="x", padx=14, pady=(2, 0))

        ctk.CTkLabel(
            log_hdr, text="📋 İŞLEM LOGLARI",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=self._C_ACCENT, anchor="w",
        ).pack(side="left")

        ctk.CTkButton(
            log_hdr, text="Temizle", width=50, height=18,
            fg_color=self._C_CARD, hover_color=self._C_BORDER,
            text_color=self._C_DIM, corner_radius=4,
            command=self._clear_log,
        ).pack(side="right")

        self._log_expanded = False
        self._log_toggle_btn = ctk.CTkButton(
            log_hdr, text="▲ Genişlet", width=70, height=18,
            fg_color=self._C_CARD, hover_color=self._C_BORDER,
            text_color=self._C_DIM, corner_radius=4,
            command=self._toggle_log_expand,
        )
        self._log_toggle_btn.pack(side="right", padx=(4, 0))

        self._log_box = tk.Text(
            outer, state="disabled", bg="#0d0d16", fg=self._C_TEXT,
            font=("Consolas", 9), relief="flat", bd=0, highlightthickness=0,
            wrap="word", height=8, padx=10, pady=8,
        )
        self._log_box.pack(fill="both", expand=True, padx=14, pady=(4, 10))

        self._log_box.tag_configure("stage", foreground="#c084fc")
        self._log_box.tag_configure("success", foreground=self._C_SUCCESS)
        self._log_box.tag_configure("warn", foreground=self._C_WARN)
        self._log_box.tag_configure("error", foreground=self._C_ERROR)

    def _toggle_log_expand(self) -> None:
        if self._log_expanded:
            self._log_box.configure(height=8)
            self._log_toggle_btn.configure(text="▲ Genişlet")
        else:
            self._log_box.configure(height=22)
            self._log_toggle_btn.configure(text="▼ Daralt")
        self._log_expanded = not self._log_expanded

    # ────────────────────────────────────────────────────────────
    # Callbacks & Event Handlers
    # ────────────────────────────────────────────────────────────

    def _browse_input(self) -> None:
        path = fd.askopenfilename(
            title="Görsel veya Camera RAW Dosyası Seçin",
            filetypes=[
                ("Desteklenen Dosyalar", "*.png *.jpg *.jpeg *.webp *.bmp *.raf *.cr2 *.cr3 *.nef *.arw *.dng"),
                ("Tüm Dosyalar", "*.*"),
            ],
        )
        if path:
            self._set_input_file(Path(path))

    def _set_input_file(self, p: Path) -> None:
        self._selected_input_path = p
        self._filename_lbl.configure(text=f"📄 {p.name}", text_color=self._C_TEXT)

        try:
            bgr = load_image_safe(p, use_auto_wb=self._raw_wb_var.get())
            self._input_image_bgr = bgr

            # Render Input Tab & Compare Tab previews
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            pil_img.thumbnail((750, 520), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

            self._input_lbl.configure(image=ctk_img, text="")
            self._comp_orig_lbl.configure(image=ctk_img, text="")

            self.tabview.set("Giriş")
            self._log_append(f"📁 Dosya Yüklendi: {p.name} ({bgr.shape[1]}x{bgr.shape[0]} px)", "stage")
        except Exception as exc:
            self._log_append(f"❌ Görsel yükleme hatası: {exc}", "error")

    def _on_start(self) -> None:
        if not self._selected_input_path:
            mb.showerror("Görsel Eksik", "Lütfen büyütülecek bir görsel veya Camera RAW dosyası seçin.")
            return

        fmt = self._fmt_var.get().lower()
        out_path = self._selected_input_path.parent / f"{self._selected_input_path.stem}_ai_4x.{fmt}"

        try:
            clean_input = sanitize_path(self._selected_input_path, must_exist=True)
            clean_output = sanitize_path(out_path, allow_creation=True, must_exist=False)
        except SecurityError as sec_err:
            mb.showerror("Güvenlik Uyarısı", f"Yol doğrulama başarısız:\n{sec_err}")
            return

        scale_val = 4 if "4" in self._scale_var.get() else 2
        color_config = ColorConfig(
            preset=self.color_preset_var.get(),
            film_grain=float(self._grain_slider.get()) / 100.0,
        )

        self._cancel_event.clear()
        self._progress_bar.set(0)
        self._clear_log()
        self._log_append(f"AI Büyütme başlatılıyor · Scale = {scale_val}x · Fuji Preset = {color_config.preset}", "stage")
        self._set_processing(True)

        self._worker = WorkerThread(
            input_path=clean_input,
            output_path=clean_output,
            scale_factor=scale_val,
            color_config=color_config,
            use_auto_wb=self._raw_wb_var.get(),
            ui_queue=self._ui_queue,
            cancel_event=self._cancel_event,
        )
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.is_alive():
            self._cancel_event.set()
            self._log_append("İptal talebi alındı — durduruluyor...", "warn")
            self._cancel_btn.configure(state="disabled", text="İptal Ediliyor...")
            self._gpu_badge.configure(text="⬤ İPTAL EDİLİYOR", text_color=self._C_WARN)

    def _poll_ui_queue(self) -> None:
        while True:
            try:
                event_type, payload = self._ui_queue.get_nowait()
                self._handle_event(event_type, payload)
            except Empty:
                break

        self.after(50, self._poll_ui_queue)

    def _handle_event(self, event_type: str, payload: Any) -> None:
        if event_type == "log":
            text = str(payload)
            tag = (
                "error" if "error" in text.lower() or "exception" in text.lower() else
                "warn" if "warning" in text.lower() else
                "success" if "done" in text.lower() or "complete" in text.lower() or "kaydedildi" in text.lower() else
                "stage" if "başlatılıyor" in text.lower() or "yükleniyor" in text.lower() else
                None
            )
            self._log_append(text, tag)

        elif event_type == "stage":
            self._stage_label.configure(text=str(payload), text_color=self._C_TEXT)

        elif event_type == "progress":
            ratio = float(payload)
            self._progress_bar.set(ratio)

        elif event_type == "done":
            out_path, out_bgr = payload
            self._output_image_bgr = out_bgr
            self._stage_label.configure(text="✅ İşlem Tamamlandı!", text_color=self._C_SUCCESS)
            self._progress_bar.set(1.0)
            self._log_append(f"✅ Çıktı kaydedildi: {out_path}", "success")

            # Render Output & Compare Tab Previews
            rgb_out = cv2.cvtColor(out_bgr, cv2.COLOR_BGR2RGB)
            pil_out = Image.fromarray(rgb_out)
            pil_out.thumbnail((750, 520), Image.Resampling.LANCZOS)
            ctk_out_img = ctk.CTkImage(light_image=pil_out, dark_image=pil_out, size=pil_out.size)

            self._output_lbl.configure(image=ctk_out_img, text="")
            self._comp_out_lbl.configure(image=ctk_out_img, text="")
            self.tabview.set("Çıkış")

            self._set_processing(False)
            self._gpu_badge.configure(text="GPU Aktif (CUDA)", text_color=self._C_SUCCESS)

        elif event_type == "cancelled":
            self._stage_label.configure(text="⚠ İptal Edildi", text_color=self._C_WARN)
            self._log_append("⚠ İşlem kullanıcı tarafından iptal edildi.", "warn")
            self._set_processing(False)
            self._gpu_badge.configure(text="GPU Aktif (CUDA)", text_color=self._C_SUCCESS)

        elif event_type == "error":
            err_text = str(payload)
            self._stage_label.configure(text="❌ İşlem Hatası", text_color=self._C_ERROR)
            self._log_append(f"❌ Hata:\n{err_text}", "error")
            self._set_processing(False)
            self._gpu_badge.configure(text="❌ İşlem Hatası", text_color=self._C_ERROR)
            mb.showerror("İşlem Hatası", f"Bir hata oluştu:\n\n{err_text[:400]}")

    def _set_processing(self, active: bool) -> None:
        self._processing = active
        if active:
            self._start_btn.configure(state="disabled", text="İşleniyor...")
            self._cancel_btn.configure(state="normal", text="■   İşlemi Durdur", fg_color=self._C_ERROR)
            self._gpu_badge.configure(text="⬤ İşleniyor (CUDA)...", text_color=self._C_ACCENT)
        else:
            self._start_btn.configure(state="normal", text="▶   İşlemi Başlat")
            self._cancel_btn.configure(state="disabled", text="■   İşlemi Durdur", fg_color=self._C_BORDER)

    def _log_append(self, text: str, tag: Optional[str] = None) -> None:
        self._log_box.configure(state="normal")
        if tag:
            self._log_box.insert("end", text + "\n", tag)
        else:
            self._log_box.insert("end", text + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _on_drop(self, event: Any) -> None:
        raw: str = event.data.strip()
        if raw.startswith("{"):
            end = raw.find("}")
            path_str = raw[1:end] if end != -1 else raw[1:]
        else:
            path_str = raw.split()[0]

        p = Path(path_str.strip())
        if p.is_file():
            self._set_input_file(p)


def main() -> None:
    def _global_exc_handler(exc_type: Any, exc_value: Any, exc_tb: Any) -> None:
        import traceback
        full_tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[UNHANDLED EXCEPTION]\n{full_tb}")

    sys.excepthook = _global_exc_handler
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
