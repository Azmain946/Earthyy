"""Spectral indices computed from surface-reflectance bands.

All formulas are standard, published remote-sensing indices. Inputs are
Sentinel-2 L2A reflectance (scaled integers); ratios are scale-invariant.
"""
from __future__ import annotations

import numpy as np

EPS = 1e-6


def _norm_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return (a - b) / (a + b + EPS)


def ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Normalized Difference Vegetation Index (Rouse et al., 1974)."""
    return _norm_diff(nir, red)


def ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI (McFeeters, 1996) — open-water delineation."""
    return _norm_diff(green, nir)


def mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Modified NDWI (Xu, 2006) — water vs built-up/soil separation."""
    return _norm_diff(green, swir)


def evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray, scale: float = 10000.0) -> np.ndarray:
    """Enhanced Vegetation Index (Huete et al., 2002). Requires reflectance 0-1."""
    n, r, b = nir / scale, red / scale, blue / scale
    with np.errstate(invalid="ignore", divide="ignore"):
        return 2.5 * (n - r) / (n + 6.0 * r - 7.5 * b + 1.0 + EPS)


def nbr(nir: np.ndarray, swir22: np.ndarray) -> np.ndarray:
    """Normalized Burn Ratio — disturbance indicator."""
    return _norm_diff(nir, swir22)


def bsi(swir16: np.ndarray, red: np.ndarray, nir: np.ndarray, blue: np.ndarray) -> np.ndarray:
    """Bare Soil Index (Rikimaru et al., 2002)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        return ((swir16 + red) - (nir + blue)) / ((swir16 + red) + (nir + blue) + EPS)


def ndmi(nir: np.ndarray, swir16: np.ndarray) -> np.ndarray:
    """Normalized Difference Moisture Index (Gao, 1996) — canopy water content."""
    return _norm_diff(nir, swir16)
