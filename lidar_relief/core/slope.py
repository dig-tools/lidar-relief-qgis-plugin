"""slope.py — Slope computation using Horn's 3×3 finite difference method.
exports: compute_slope(dem, cellsize, units) -> ndarray
used_by: algorithms/slope_algorithm.py → compute_slope
         algorithms/batch_algorithm.py → compute_slope
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Shares gradient logic with hillshade.py (Horn's method).
  Output units are either degrees or percent.
"""

import numpy as np


def compute_slope(
    dem: np.ndarray,
    cellsize: float,
    units: str = "degrees",
) -> np.ndarray:
    """Compute terrain slope from a DEM using Horn's 3×3 method.

    Uses the same gradient estimation as hillshade (Horn, 1981):
        dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cellsize)
        dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cellsize)
        slope_radians = arctan(sqrt(dz_dx² + dz_dy²))

    Args:
        dem: 2D float32 elevation array (nodata as np.nan).
        cellsize: Pixel size in map units.
        units: Output units — 'degrees' or 'percent'.

    Returns:
        Float32 array of slope values.
        - Degrees: range [0, ~90]
        - Percent: range [0, ∞) where 100% = 45°

    Raises:
        ValueError: If units is not 'degrees' or 'percent'.

    Rules:
        NaN pixels in input are preserved as NaN in output.
        Edge pixels use padded (replicated) boundaries for gradient calculation.
    """
    if units not in ("degrees", "percent"):
        raise ValueError(f"units must be 'degrees' or 'percent', got '{units}'")

    # Replace NaN for gradient computation
    dem_filled = np.nan_to_num(dem, nan=0.0)

    # Pad with edge replication
    padded = np.pad(dem_filled, 1, mode="edge")

    # Horn's 3×3 kernel — extract 8 neighbours
    a = padded[:-2, :-2]
    b = padded[:-2, 1:-1]
    c = padded[:-2, 2:]
    d = padded[1:-1, :-2]
    f = padded[1:-1, 2:]
    g = padded[2:, :-2]
    h = padded[2:, 1:-1]
    i = padded[2:, 2:]

    dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * cellsize)
    dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * cellsize)

    # Slope magnitude
    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))

    if units == "degrees":
        result = np.rad2deg(slope_rad).astype(np.float32)
    else:  # percent
        result = (np.tan(slope_rad) * 100.0).astype(np.float32)

    # Preserve NaN from input
    result[np.isnan(dem)] = np.nan

    return result
