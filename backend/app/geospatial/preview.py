"""Render raster previews (PNG) for map overlays and reports."""
from __future__ import annotations

import io

import numpy as np
from PIL import Image


def _stretch(band: np.ndarray, p_low: float = 2, p_high: float = 98) -> np.ndarray:
    finite = band[np.isfinite(band)]
    if finite.size == 0:
        return np.zeros_like(band, dtype=np.uint8)
    lo, hi = np.percentile(finite, [p_low, p_high])
    if hi <= lo:
        hi = lo + 1
    scaled = np.clip((band - lo) / (hi - lo), 0, 1) * 255
    return np.nan_to_num(scaled).astype(np.uint8)


def render_rgb_png(rgb: np.ndarray) -> bytes:
    """rgb: (3, H, W) float array -> stretched PNG bytes with alpha for nodata."""
    r, g, b = (_stretch(rgb[i]) for i in range(3))
    alpha = (np.isfinite(rgb).all(axis=0) & (rgb.sum(axis=0) > 0)).astype(np.uint8) * 255
    img = Image.fromarray(np.dstack([r, g, b, alpha]), mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# Simple scientific colormaps (breakpoint, rgb) — rendered without matplotlib.
NDVI_RAMP = [
    (-0.2, (166, 97, 26)),
    (0.1, (223, 194, 125)),
    (0.3, (255, 255, 191)),
    (0.5, (128, 205, 92)),
    (0.7, (27, 152, 80)),
    (0.9, (0, 104, 55)),
]
WATER_RAMP = [
    (-0.6, (255, 255, 255)),
    (-0.2, (189, 215, 231)),
    (0.0, (107, 174, 214)),
    (0.3, (33, 113, 181)),
    (0.7, (8, 48, 107)),
]


def render_index_png(index: np.ndarray, ramp: list[tuple[float, tuple[int, int, int]]], mask: np.ndarray | None = None) -> bytes:
    """Colormapped PNG of an index array; transparent outside mask/finite data."""
    h, w = index.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    valid = np.isfinite(index)
    if mask is not None:
        valid &= mask
    xs = np.array([b for b, _ in ramp])
    cols = np.array([c for _, c in ramp], dtype=np.float64)
    vals = np.clip(index, xs[0], xs[-1])
    for ch in range(3):
        out[..., ch] = np.interp(vals, xs, cols[:, ch]).astype(np.uint8)
    out[..., 3] = np.where(valid, 200, 0).astype(np.uint8)
    img = Image.fromarray(out, mode="RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
