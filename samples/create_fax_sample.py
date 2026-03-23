#!/usr/bin/env python3
"""Create realistic fax-degraded PDFs from an EHR PDF and a DICOM screenshot.

Pipeline
--------
1. Render each page of the source PDF to a high-DPI image.
2. Load the companion PNG image and resize it to match page width.
3. Concatenate all pages into a single ordered list.
4. Apply a chain of degradation functions to each page:
   a. Fax header/footer injection (with optional stacked re-fax header)
   b. Rubber-stamp & date-stamp overlays
   c. Three-ring-binder punch holes & staple shadows
   d. Random skew + perspective warp
   e. Resolution/compression degradation (200x100 DPI simulation,
      binarisation, salt-and-pepper noise, JPEG artefact pass)
   CT/image pages receive a gentler variant of step (e) that preserves
   grayscale detail instead of hard-binarising.
5. Assemble the degraded pages into a single output PDF.

When ``--count N`` is given the script produces N variant PDFs, each with a
different seed (base_seed, base_seed+1000, base_seed+2000, ...).

Usage
-----
    python samples/create_fax_sample.py \\
        --pdf   samples/raw/example1/Case1TraumaFracture.pdf \\
        --image samples/raw/example1/DICOM_screenshot1.png \\
        --out   samples/processed/example1_fax.pdf \\
        --seed  42 \\
        --count 3

    # Override defaults via JSON:
    python samples/create_fax_sample.py ... --config my_config.json

    # Print the full active config and exit:
    python samples/create_fax_sample.py --pdf x --image x --out x --dump-config
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# =========================================================================
# Configuration dataclass -- every tunable knob lives here
# =========================================================================

@dataclass
class FaxConfig:
    """All tuneable parameters for the fax-degradation pipeline.

    Override any value via ``--config <path.json>`` on the CLI.  Any JSON
    key that matches an attribute name will be applied; unknown keys are
    warned about and ignored.
    """

    # -- Source rendering ---------------------------------------------------
    render_dpi: int = 300

    # -- Fax header ---------------------------------------------------------
    header_height_frac: float = 0.025          # fraction of page height
    header_min_px: int = 28
    header_primary_text: str = (
        "03/18/2026  14:32  FROM: ST. MARY'S MED CTR  "
        "FAX: (555) 482-7103  TO: (555) 319-8800"
    )
    header_refax_prob: float = 0.40
    header_refax_text: str = (
        "03/19/2026  08:17  FROM: RECORDS MGMT  "
        "FAX: (555) 210-4455  TO: (555) 319-8800"
    )

    # -- Stamps / overlays --------------------------------------------------
    stamp_received_prob: float = 0.40
    stamp_received_text: str = "RECEIVED"
    stamp_received_color: Tuple[int, int, int] = (180, 30, 30)
    stamp_received_rotation_range: Tuple[float, float] = (-18.0, -6.0)

    stamp_date_prob: float = 0.30
    stamp_date_text: str = "MAR 18 2026"
    stamp_date_color: Tuple[int, int, int] = (20, 20, 160)
    stamp_date_rotation_range: Tuple[float, float] = (-8.0, 8.0)

    # -- Punch holes / staple -----------------------------------------------
    punch_hole_radius_frac: float = 0.008      # fraction of page height
    punch_hole_margin_frac: float = 0.03       # fraction of page width
    punch_hole_positions: Tuple[float, ...] = (0.25, 0.50, 0.75)
    staple_prob: float = 0.20

    # -- Skew & warp --------------------------------------------------------
    skew_angle_range: Tuple[float, float] = (-2.5, 2.5)        # degrees
    warp_shift_x_frac_range: Tuple[float, float] = (0.005, 0.015)
    warp_shift_y_frac_range: Tuple[float, float] = (0.003, 0.010)

    # -- Resolution degradation (text pages) --------------------------------
    vertical_downsample_factor: int = 2        # 2 -> 200x100 DPI feel
    blur_kernel: Tuple[int, int] = (3, 1)
    blur_sigma_x: float = 0.8
    jpeg_quality_range: Tuple[int, int] = (15, 28)
    binarise: bool = True                      # Otsu threshold
    noise_frac_range: Tuple[float, float] = (0.001, 0.003)

    # -- Resolution degradation (CT / image pages -- gentler) ---------------
    ct_vertical_downsample_factor: int = 1     # 1 = no vertical smear
    ct_blur_kernel: Tuple[int, int] = (3, 3)
    ct_blur_sigma_x: float = 0.6
    ct_jpeg_quality_range: Tuple[int, int] = (45, 65)
    ct_binarise: bool = False                  # keep grayscale detail
    ct_noise_frac_range: Tuple[float, float] = (0.0005, 0.0015)

    # -- Output -------------------------------------------------------------
    output_pdf_dpi: float = 200.0

    # -- Multi-output -------------------------------------------------------
    seed_step: int = 1000        # seed offset between consecutive variants

    # ------------------------------------------------------------------
    def update_from_dict(self, d: Dict) -> None:
        """Overlay values from a plain dict (e.g. parsed JSON)."""
        for key, value in d.items():
            if hasattr(self, key):
                expected = type(getattr(self, key))
                if expected is tuple and isinstance(value, list):
                    value = tuple(value)
                setattr(self, key, value)
            else:
                print(f"WARNING: unknown config key '{key}', ignoring.")


# =========================================================================
# Helpers
# =========================================================================

def _pil_to_cv(pil_img: Image.Image) -> np.ndarray:
    arr = np.array(pil_img)
    if arr.ndim == 2:
        return arr
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _cv_to_pil(cv_img: np.ndarray) -> Image.Image:
    if cv_img.ndim == 2:
        return Image.fromarray(cv_img, mode="L")
    return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))


def _ensure_gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def _ensure_bgr(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def _get_font(size: int = 18) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Courier.dfont",
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# =========================================================================
# Degradation stages
# =========================================================================

# --- 3a  Fax header ------------------------------------------------------

def add_fax_header(
    img: np.ndarray,
    page_no: int,
    total_pages: int,
    rng: np.random.Generator,
    cfg: FaxConfig,
) -> np.ndarray:
    h, w = img.shape[:2]
    header_h = max(cfg.header_min_px, int(h * cfg.header_height_frac))

    pil = _cv_to_pil(_ensure_bgr(img))
    draw = ImageDraw.Draw(pil)
    font = _get_font(size=max(12, header_h - 8))

    primary = f"{cfg.header_primary_text}  P.{page_no:02d}/{total_pages:02d}"
    draw.rectangle([(0, 0), (w, header_h)], fill=(255, 255, 255))
    draw.text((10, 2), primary, fill=(0, 0, 0), font=font)

    if rng.random() < cfg.header_refax_prob:
        second = f"{cfg.header_refax_text}  P.{page_no:02d}/{total_pages:02d}"
        y_off = header_h + int(rng.integers(0, 6))
        draw.rectangle([(0, header_h), (w, y_off + header_h)],
                       fill=(255, 255, 255))
        font2 = _get_font(size=max(10, header_h - 10))
        draw.text(
            (8 + int(rng.integers(-3, 4)), y_off - 2),
            second, fill=(30, 30, 30), font=font2,
        )

    return _pil_to_cv(pil)


# --- 3b  Stamps / overlays -----------------------------------------------

def _make_stamp_image(
    text: str,
    font_size: int = 38,
    color: Tuple[int, int, int] = (180, 30, 30),
    rotation: float = -12.0,
) -> Image.Image:
    font = _get_font(font_size)
    scratch = Image.new("RGBA", (1, 1))
    sd = ImageDraw.Draw(scratch)
    bbox = sd.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0] + 30, bbox[3] - bbox[1] + 24

    stamp = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(stamp)
    d.rectangle([(4, 4), (tw - 5, th - 5)], outline=(*color, 200), width=3)
    d.text((15, 8), text, fill=(*color, 190), font=font)
    stamp = stamp.rotate(rotation, expand=True, fillcolor=(0, 0, 0, 0))
    return stamp


def add_stamps_and_overlays(
    img: np.ndarray,
    rng: np.random.Generator,
    cfg: FaxConfig,
) -> np.ndarray:
    h, w = img.shape[:2]
    pil = _cv_to_pil(_ensure_bgr(img)).convert("RGBA")

    if rng.random() < cfg.stamp_received_prob:
        stamp = _make_stamp_image(
            cfg.stamp_received_text,
            font_size=max(28, int(h * 0.03)),
            color=cfg.stamp_received_color,
            rotation=float(rng.uniform(*cfg.stamp_received_rotation_range)),
        )
        mx = max(0, w - stamp.width - 20)
        my = max(0, h - stamp.height - 20)
        pos = (int(rng.integers(20, max(21, mx))),
               int(rng.integers(20, max(21, my))))
        pil.paste(stamp, pos, stamp)

    if rng.random() < cfg.stamp_date_prob:
        stamp = _make_stamp_image(
            cfg.stamp_date_text,
            font_size=max(22, int(h * 0.022)),
            color=cfg.stamp_date_color,
            rotation=float(rng.uniform(*cfg.stamp_date_rotation_range)),
        )
        mx = max(0, w - stamp.width - 20)
        my = max(0, h - stamp.height - 20)
        pos = (int(rng.integers(20, max(21, mx))),
               int(rng.integers(int(h * 0.15), max(int(h * 0.15) + 1, my))))
        pil.paste(stamp, pos, stamp)

    return _pil_to_cv(pil.convert("RGB"))


# --- 3c  Punch holes / staple --------------------------------------------

def add_punch_holes(
    img: np.ndarray,
    rng: np.random.Generator,
    cfg: FaxConfig,
) -> np.ndarray:
    h, w = img.shape[:2]
    out = img.copy()
    radius = max(8, int(h * cfg.punch_hole_radius_frac))
    cx = int(w * cfg.punch_hole_margin_frac)

    for frac in cfg.punch_hole_positions:
        cy = int(h * frac) + int(rng.integers(-5, 6))
        cv2.circle(out, (cx, cy), radius,
                   (0, 0, 0) if out.ndim == 3 else 0,
                   thickness=-1, lineType=cv2.LINE_AA)
        cv2.circle(out, (cx, cy), max(2, radius - 3),
                   (255, 255, 255) if out.ndim == 3 else 255,
                   thickness=-1, lineType=cv2.LINE_AA)

    if rng.random() < cfg.staple_prob:
        sx = int(rng.integers(int(w * 0.02), int(w * 0.08)))
        sy = int(rng.integers(int(h * 0.02), int(h * 0.07)))
        sw, sh = int(rng.integers(10, 22)), int(rng.integers(4, 9))
        color = (40, 40, 40) if out.ndim == 3 else 40
        cv2.rectangle(out, (sx, sy), (sx + sw, sy + sh), color, thickness=-1)

    return out


# --- 3d  Skew & perspective warp -----------------------------------------

def apply_skew_and_warp(
    img: np.ndarray,
    rng: np.random.Generator,
    cfg: FaxConfig,
) -> np.ndarray:
    h, w = img.shape[:2]
    fill = 255

    angle = float(rng.uniform(*cfg.skew_angle_range))
    M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    out = cv2.warpAffine(
        img, M_rot, (w, h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(fill,) * (3 if img.ndim == 3 else 1),
    )

    shift_x = float(rng.uniform(*(f * w for f in cfg.warp_shift_x_frac_range)))
    shift_y = float(rng.uniform(*(f * h for f in cfg.warp_shift_y_frac_range)))

    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([
        [shift_x, shift_y],
        [w - shift_x * 0.3, shift_y * 0.5],
        [w - shift_x * 0.3, h - shift_y * 0.5],
        [shift_x, h - shift_y],
    ])
    M_persp = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(
        out, M_persp, (w, h),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(fill,) * (3 if img.ndim == 3 else 1),
    )
    return out


# --- 3e  Resolution & compression ----------------------------------------

def degrade_resolution(
    img: np.ndarray,
    rng: np.random.Generator,
    cfg: FaxConfig,
    *,
    is_ct: bool = False,
) -> np.ndarray:
    """Degrade resolution.

    When *is_ct* is True a gentler profile is used that preserves grayscale
    tonal detail instead of hard-binarising to pure black & white.
    """
    gray = _ensure_gray(img)
    h, w = gray.shape[:2]

    # Pick parameter set based on page type
    vds    = cfg.ct_vertical_downsample_factor if is_ct else cfg.vertical_downsample_factor
    bk     = cfg.ct_blur_kernel               if is_ct else cfg.blur_kernel
    bsigma = cfg.ct_blur_sigma_x              if is_ct else cfg.blur_sigma_x
    jq_lo, jq_hi = (cfg.ct_jpeg_quality_range if is_ct else cfg.jpeg_quality_range)
    do_bin = cfg.ct_binarise                   if is_ct else cfg.binarise
    nf_lo, nf_hi = (cfg.ct_noise_frac_range   if is_ct else cfg.noise_frac_range)

    # Non-square pixel simulation
    if vds > 1:
        small = cv2.resize(gray, (w, h // vds), interpolation=cv2.INTER_AREA)
        restored = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
    else:
        restored = gray.copy()

    # Blur
    restored = cv2.GaussianBlur(restored, bk, sigmaX=bsigma)

    # JPEG artefact pass
    quality = int(rng.integers(jq_lo, jq_hi + 1))
    _, enc = cv2.imencode(".jpg", restored, [cv2.IMWRITE_JPEG_QUALITY, quality])
    restored = cv2.imdecode(enc, cv2.IMREAD_GRAYSCALE)

    # Binarisation (text pages only by default)
    if do_bin:
        _, restored = cv2.threshold(
            restored, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )

    # Salt-and-pepper noise
    noise_frac = float(rng.uniform(nf_lo, nf_hi))
    n_pixels = int(h * w * noise_frac)
    for val in (255, 0):
        ys = rng.integers(0, h, size=n_pixels)
        xs = rng.integers(0, w, size=n_pixels)
        restored[ys, xs] = val

    return restored


# =========================================================================
# Master per-page pipeline
# =========================================================================

def degrade_page(
    img: np.ndarray,
    page_no: int,
    total_pages: int,
    base_seed: int,
    cfg: FaxConfig,
    *,
    is_ct: bool = False,
) -> np.ndarray:
    rng = np.random.default_rng(base_seed + page_no)

    img = add_fax_header(img, page_no, total_pages, rng, cfg)
    img = add_stamps_and_overlays(img, rng, cfg)
    img = add_punch_holes(img, rng, cfg)
    img = apply_skew_and_warp(img, rng, cfg)
    img = degrade_resolution(img, rng, cfg, is_ct=is_ct)
    return img


# =========================================================================
# Source loading
# =========================================================================

def load_pdf_pages(pdf_path: str, dpi: int = 300) -> List[np.ndarray]:
    doc = fitz.open(pdf_path)
    pages: List[np.ndarray] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for page in doc:
        pix = page.get_pixmap(matrix=mat, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3,
        )
        pages.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    doc.close()
    return pages


def load_and_fit_image(
    image_path: str,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    raw = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if raw is None:
        sys.exit(f"ERROR: cannot read image '{image_path}'")
    ih, iw = raw.shape[:2]

    scale = target_width / iw
    new_h = int(ih * scale)
    resized = cv2.resize(raw, (target_width, new_h), interpolation=cv2.INTER_AREA)

    if new_h < target_height:
        pad_top = (target_height - new_h) // 2
        pad_bot = target_height - new_h - pad_top
        resized = cv2.copyMakeBorder(
            resized, pad_top, pad_bot, 0, 0,
            cv2.BORDER_CONSTANT, value=(255, 255, 255),
        )
    elif new_h > target_height:
        resized = cv2.resize(
            resized, (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )
    return resized


# =========================================================================
# PDF assembly
# =========================================================================

def assemble_pdf(
    pages: List[np.ndarray],
    out_path: str,
    cfg: FaxConfig,
) -> None:
    pil_pages: List[Image.Image] = []
    for p in pages:
        pil_pages.append(_cv_to_pil(p).convert("L"))

    if not pil_pages:
        sys.exit("ERROR: no pages to assemble")

    first, *rest = pil_pages
    first.save(
        out_path, "PDF",
        resolution=cfg.output_pdf_dpi,
        save_all=True,
        append_images=rest,
    )


# =========================================================================
# Single-run helper
# =========================================================================

def generate_one(
    pdf_pages: List[np.ndarray],
    dicom_page: np.ndarray,
    out_path: str,
    seed: int,
    cfg: FaxConfig,
) -> None:
    """Degrade all pages and write one output PDF."""
    all_pages = pdf_pages + [dicom_page]
    total = len(all_pages)
    n_pdf = len(pdf_pages)

    degraded: List[np.ndarray] = []
    for i, page in enumerate(all_pages, start=1):
        is_ct = i > n_pdf  # pages after the PDF are CT images
        degraded.append(
            degrade_page(
                page, page_no=i, total_pages=total,
                base_seed=seed, cfg=cfg, is_ct=is_ct,
            )
        )

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    assemble_pdf(degraded, out_path, cfg)


# =========================================================================
# CLI
# =========================================================================

def _numbered_path(base: str, idx: int) -> str:
    """Insert ``_002`` before the extension: ``foo.pdf`` -> ``foo_002.pdf``."""
    p = Path(base)
    return str(p.with_stem(f"{p.stem}_{idx:03d}"))


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Create fax-degraded PDFs from an EHR PDF + DICOM screenshot.",
    )
    ap.add_argument("--pdf",    required=True, help="Source EHR PDF path")
    ap.add_argument("--image",  required=True, help="Companion DICOM PNG path")
    ap.add_argument("--out",    required=True,
                    help="Output fax PDF path (base name when --count > 1)")
    ap.add_argument("--seed",   type=int, default=42, help="Base RNG seed")
    ap.add_argument("--dpi",    type=int, default=300,
                    help="Render DPI for source PDF")
    ap.add_argument("--count",  type=int, default=1,
                    help="Number of variant PDFs to generate")
    ap.add_argument("--config", type=str, default=None,
                    help="Path to a JSON file overriding default FaxConfig values")
    ap.add_argument("--dump-config", action="store_true",
                    help="Print the active FaxConfig as JSON and exit")
    args = ap.parse_args()

    # -- Build config ------------------------------------------------------
    cfg = FaxConfig(render_dpi=args.dpi)
    if args.config:
        with open(args.config) as f:
            cfg.update_from_dict(json.load(f))
    if args.dpi != 300:  # explicit CLI --dpi wins over JSON
        cfg.render_dpi = args.dpi

    if args.dump_config:
        print(json.dumps(dataclasses.asdict(cfg), indent=2))
        sys.exit(0)

    # -- Load sources ------------------------------------------------------
    print(f"[1/4] Rendering PDF pages from {args.pdf} at {cfg.render_dpi} DPI ...")
    pdf_pages = load_pdf_pages(args.pdf, dpi=cfg.render_dpi)
    if not pdf_pages:
        sys.exit("ERROR: PDF contained no pages")
    ref_h, ref_w = pdf_pages[0].shape[:2]
    print(f"       -> {len(pdf_pages)} page(s), {ref_w}x{ref_h} px")

    print(f"[2/4] Loading companion image from {args.image} ...")
    dicom_page = load_and_fit_image(
        args.image, target_width=ref_w, target_height=ref_h,
    )
    total = len(pdf_pages) + 1
    print(f"       -> {total} total page(s) after concatenation")

    # -- Generate variants -------------------------------------------------
    count = max(1, args.count)

    for vi in range(count):
        seed_i = args.seed + vi * cfg.seed_step
        if count == 1:
            out_i = args.out
        else:
            out_i = _numbered_path(args.out, vi + 1)

        tag = f"[variant {vi + 1}/{count}] " if count > 1 else ""
        print(f"[3/4] {tag}Degrading {total} page(s) (seed={seed_i}) ...")
        generate_one(pdf_pages, dicom_page, out_i, seed_i, cfg)
        size_kb = os.path.getsize(out_i) / 1024
        print(f"[4/4] {tag}{out_i}  ({size_kb:.0f} KB)")

    print("Done.")


if __name__ == "__main__":
    main()
