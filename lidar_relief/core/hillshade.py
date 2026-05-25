"""hillshade.py — Multi-directional hillshade computation using Horn's method.
exports: multidirectional_hillshade(dem, cellsize, azimuths, altitude) -> ndarray
used_by: algorithms/hillshade_algorithm.py → multidirectional_hillshade
         algorithms/batch_algorithm.py → multidirectional_hillshade
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Output is float32 in range [0, 255] (illumination intensity).
  Uses Horn's (1981) 3×3 finite difference for gradient estimation.
"""

import numpy as np


def _horn_gradients(dem: np.ndarray, cellsize: float):
    """Compute dz/dx and dz/dy using Horn's 3×3 finite difference method.

    The 3×3 kernel uses the following cell labelling:

        a  b  c
        d  e  f
        g  h  i

    dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cellsize)
    dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cellsize)

    Args:
        dem: 2D float32 elevation array.
        cellsize: Pixel size in map units.

    Returns:
        Tuple (dz_dx, dz_dy) as float32 arrays with same shape as dem.
        Edge pixels are set to 0 (flat).

    Rules:
        Handles NaN by treating them as 0 gradient contribution.
        Uses np.nan_to_num internally for the kernel computation.
    """
    # Replace NaN with local mean for gradient computation
    dem_filled = np.nan_to_num(dem, nan=0.0)

    # Extract the 8 neighbours via slicing (avoids np.roll overhead)
    # Pad with edge values to handle boundaries
    padded = np.pad(dem_filled, 1, mode="edge")

    a = padded[:-2, :-2]   # top-left
    b = padded[:-2, 1:-1]  # top-centre
    c = padded[:-2, 2:]    # top-right
    d = padded[1:-1, :-2]  # mid-left
    # e = padded[1:-1, 1:-1]  # centre (not used)
    f = padded[1:-1, 2:]   # mid-right
    g = padded[2:, :-2]    # bottom-left
    h = padded[2:, 1:-1]   # bottom-centre
    i = padded[2:, 2:]     # bottom-right

    dz_dx = ((c + 2.0 * f + i) - (a + 2.0 * d + g)) / (8.0 * cellsize)
    dz_dy = ((g + 2.0 * h + i) - (a + 2.0 * b + c)) / (8.0 * cellsize)

    return dz_dx.astype(np.float32), dz_dy.astype(np.float32)


def _single_hillshade(
    dz_dx: np.ndarray,
    dz_dy: np.ndarray,
    azimuth_deg: float,
    altitude_deg: float,
) -> np.ndarray:
    """Compute hillshade for a single sun direction.

    hillshade = cos(slope) * cos(zenith) + sin(slope) * sin(zenith) * cos(azimuth - aspect)

    Args:
        dz_dx: Gradient in X direction.
        dz_dy: Gradient in Y direction.
        azimuth_deg: Sun azimuth in degrees (0=north, clockwise).
        altitude_deg: Sun altitude in degrees above horizon.

    Returns:
        Float32 array of illumination values in [0, 1].

    Rules:
        Azimuth is converted from geographic (N=0, clockwise) to math convention.
        Result is clipped to [0, 1] — no negative illumination.
    """
    # Convert to radians
    azimuth_rad = np.deg2rad(360.0 - azimuth_deg + 90.0)  # geographic → math
    zenith_rad = np.deg2rad(90.0 - altitude_deg)

    # Slope and aspect from gradients
    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))
    aspect_rad = np.arctan2(-dz_dy, dz_dx)

    # Hillshade formula
    shade = (
        np.cos(slope_rad) * np.cos(zenith_rad)
        + np.sin(slope_rad) * np.sin(zenith_rad) * np.cos(azimuth_rad - aspect_rad)
    )

    return np.clip(shade, 0.0, 1.0).astype(np.float32)


def multidirectional_hillshade(
    dem: np.ndarray,
    cellsize: float,
    azimuths: list[float] = None,
    altitude: float = 45.0,
) -> np.ndarray:
    """Compute multi-directional hillshade by blending multiple sun azimuths.

    For each azimuth, computes a single-direction hillshade using Horn's method,
    then averages all directions for uniform illumination without directional bias.

    Args:
        dem: 2D float32 elevation array (nodata as np.nan).
        cellsize: Pixel size in map units.
        azimuths: List of sun azimuth angles in degrees. Defaults to
                  [315, 45, 135, 225, 270, 360] (6-direction blend).
        altitude: Sun altitude angle in degrees above horizon (0–90).

    Returns:
        Float32 array scaled to [0, 255] (standard hillshade range).

    Rules:
        Must use Horn's 3×3 method for gradient estimation.
        NaN pixels in input are preserved as NaN in output.
        Default 6 azimuths provide good all-direction coverage for archaeology.
    """
    if azimuths is None:
        azimuths = [315.0, 45.0, 135.0, 225.0, 270.0, 360.0]

    dz_dx, dz_dy = _horn_gradients(dem, cellsize)

    # Accumulate hillshade from all azimuths
    shade_sum = np.zeros_like(dem, dtype=np.float32)
    for azimuth in azimuths:
        shade_sum += _single_hillshade(dz_dx, dz_dy, azimuth, altitude)

    # Average and scale to 0–255
    shade_avg = shade_sum / len(azimuths)
    result = (shade_avg * 255.0).astype(np.float32)

    # Preserve NaN from input
    result[np.isnan(dem)] = np.nan

    return result
