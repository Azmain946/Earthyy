"""Threshold-based segmentation and mask cleaning."""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def otsu_threshold(values: np.ndarray, bins: int = 256) -> float:
    """Otsu's method on finite values. Falls back to 0.0 when degenerate."""
    finite = values[np.isfinite(values)]
    if finite.size < 100:
        return 0.0
    hist, bin_edges = np.histogram(finite, bins=bins)
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total == 0:
        return 0.0
    centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    weight1 = np.cumsum(hist)
    weight2 = total - weight1
    with np.errstate(invalid="ignore", divide="ignore"):
        mean1 = np.cumsum(hist * centers) / weight1
        mean2 = (np.cumsum((hist * centers)[::-1])[::-1]) / np.maximum(weight2, 1e-12)
    var_between = weight1[:-1] * weight2[:-1] * (mean1[:-1] - mean2[:-1]) ** 2
    if not np.isfinite(var_between).any():
        return 0.0
    idx = int(np.nanargmax(var_between))
    return float(centers[idx])


def water_mask(mndwi_arr: np.ndarray, invalid: np.ndarray | None = None) -> tuple[np.ndarray, float]:
    """Water mask from MNDWI using Otsu thresholding, bounded to a sane range.

    Returns (mask, threshold). MNDWI > threshold is water; the Otsu split is
    clamped to [-0.05, 0.35] so degenerate histograms (all-water or all-land
    AOIs) do not produce absurd thresholds.
    """
    t = otsu_threshold(mndwi_arr)
    t = float(np.clip(t, -0.05, 0.35))
    mask = mndwi_arr > t
    if invalid is not None:
        mask &= ~invalid
    mask = clean_mask(mask, min_pixels=12)
    return mask, t


def vegetation_mask(ndvi_arr: np.ndarray, threshold: float = 0.4, invalid: np.ndarray | None = None) -> np.ndarray:
    mask = ndvi_arr > threshold
    if invalid is not None:
        mask &= ~invalid
    return clean_mask(mask, min_pixels=8)


def forest_mask(ndvi_arr: np.ndarray, threshold: float = 0.6, invalid: np.ndarray | None = None) -> np.ndarray:
    """Dense-canopy mask. NDVI-threshold proxy; see model registry limitations."""
    mask = ndvi_arr > threshold
    if invalid is not None:
        mask &= ~invalid
    # Closing fills small canopy gaps; opening removes speckle.
    mask = ndimage.binary_closing(mask, iterations=1)
    mask = ndimage.binary_opening(mask, iterations=1)
    return clean_mask(mask, min_pixels=16)


def clean_mask(mask: np.ndarray, min_pixels: int = 10) -> np.ndarray:
    """Remove connected components smaller than min_pixels."""
    labeled, n = ndimage.label(mask)
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    keep = np.zeros(n + 1, dtype=bool)
    keep[1:] = sizes >= min_pixels
    return keep[labeled]


def connected_components(mask: np.ndarray) -> tuple[np.ndarray, int]:
    return ndimage.label(mask)
