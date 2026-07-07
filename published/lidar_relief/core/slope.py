"""slope.py — Slope computation using Horn's 3×3 finite difference method.
exports: compute_slope(dem, cellsize, units, method) -> ndarray
used_by: algorithms/slope_algorithm.py → compute_slope
         algorithms/batch_algorithm.py → compute_slope
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Shares gradient logic with hillshade.py (Horn's method).
  Output units are either degrees or percent.
  Two methods are supported:
    - 'horn' (default): 3×3 weighted kernel (1-2-1) / 8. Standard
      for QGIS/ArcGIS. Smoother on noisy data.
    - 'finite_difference': (z[i+1] - z[i-1]) / 2. Matches rvt-py /
      ESRI's older tools. Sharper on noisy data.
"""

import numpy as np


def compute_slope(
    dem: np.ndarray,
    cellsize: float,
    units: str = "degrees",
    method: str = "horn",
) -> np.ndarray:
    """Compute terrain slope from a DEM.

    Args:
        dem: 2D float32 elevation array (nodata as np.nan).
        cellsize: Pixel size in map units.
        units: Output units — 'degrees' or 'percent'.
        method: Gradient estimation method — 'horn' (default, 3×3
            weighted kernel, matches QGIS/ArcGIS) or 'finite_difference'
            (2-pixel central difference, matches rvt-py/ESRI older
            tools).

    Returns:
        Float32 array of slope values.
        - Degrees: range [0, ~90]
        - Percent: range [0, ∞) where 100% = 45°

    Raises:
        ValueError: If units is not 'degrees' or 'percent', or method
            is not 'horn' or 'finite_difference'.

    Rules:
        NaN pixels in input are preserved as NaN in output.
        Edge pixels use padded (replicated) boundaries for gradient calculation.
    """
    if units not in ("degrees", "percent"):
        raise ValueError(f"units must be 'degrees' or 'percent', got '{units}'")
    if method not in ("horn", "finite_difference"):
        raise ValueError(
            f"method must be 'horn' or 'finite_difference', got '{method}'"
        )

    # Replace NaN with global mean for gradient computation to prevent edge halos
    dem_mean = np.nanmean(dem)
    dem_filled = np.copy(dem)
    dem_filled[np.isnan(dem)] = dem_mean

    # Pad with edge replication
    padded = np.pad(dem_filled, 1, mode="edge")

    if method == "horn":
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
    else:
        # Finite difference (matches rvt-py / ESRI older tools):
        # dz/dx = (z[i, j+1] - z[i, j-1]) / 2
        # dz/dy = (z[i+1, j] - z[i-1, j]) / 2
        # Note: rvt-py uses (roll(-1) - roll(+1)) / 2 for dzdx, which
        # is the negative of the conventional finite difference. We use
        # the conventional form here; the slope magnitude is the same.
        east = padded[1:-1, 2:]
        west = padded[1:-1, :-2]
        north = padded[:-2, 1:-1]
        south = padded[2:, 1:-1]

        dz_dx = (east - west) / (2.0 * cellsize)
        dz_dy = (south - north) / (2.0 * cellsize)

    # Slope magnitude
    slope_rad = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))

    if units == "degrees":
        result = np.rad2deg(slope_rad).astype(np.float32)
    else:  # percent
        result = (np.tan(slope_rad) * 100.0).astype(np.float32)

    # Preserve NaN from input
    result[np.isnan(dem)] = np.nan

    return result
