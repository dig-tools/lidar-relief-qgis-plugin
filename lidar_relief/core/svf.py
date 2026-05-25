"""svf.py — Sky-View Factor (SVF) computation for terrain analysis.
exports: sky_view_factor(dem, cellsize, num_directions, search_radius) -> ndarray
used_by: algorithms/svf_algorithm.py → sky_view_factor
         algorithms/batch_algorithm.py → sky_view_factor
rules:
  Pure NumPy — no QGIS imports.
  Input dem must be float32 with nodata as np.nan.
  Output is float32 in range [0, 1] (1 = full sky visibility, 0 = fully occluded).
  This is the most computationally expensive algorithm — all operations MUST be vectorised.
  No per-pixel Python loops.
"""

import numpy as np


def sky_view_factor(
    dem: np.ndarray,
    cellsize: float,
    num_directions: int = 16,
    search_radius: int = 10,
    feedback=None,
) -> np.ndarray:
    """Compute Sky-View Factor for each pixel of a DEM.

    For each pixel, samples the horizon elevation angle at N evenly-spaced
    azimuths over a search radius R:

        γ_i = max elevation angle along direction i within radius R
        SVF = 1 − mean(sin(γ_i)) for i = 1..N

    Where the elevation angle at distance d along direction i is:
        γ_i(d) = arctan((DEM(x_d, y_d) - DEM(x_0, y_0)) / (d * cellsize))

    Args:
        dem: 2D float32 elevation array (nodata as np.nan).
        cellsize: Pixel size in map units.
        num_directions: Number of azimuth directions (8, 16, or 32).
                       More directions = more accurate but slower.
        search_radius: Maximum search distance in pixels.
        feedback: Optional QGIS feedback object for progress/cancellation.

    Returns:
        Float32 array of SVF values in [0, 1].
        - 1.0 = full sky visibility (flat terrain, ridgetops)
        - 0.0 = completely occluded (theoretical deep pit)

    Rules:
        All operations must be fully vectorised across the raster.
        Shifted arrays are used to simulate ray-casting along each direction.
        NaN pixels in input are preserved as NaN in output.
        Must check feedback.isCanceled() in the direction loop.
    """
    rows, cols = dem.shape

    # Fill NaN with the array mean for shifted lookups
    nan_mask = np.isnan(dem)
    dem_mean = np.nanmean(dem)
    dem_filled = dem.copy()
    dem_filled[nan_mask] = dem_mean

    # Generate evenly-spaced azimuth angles
    azimuths_rad = np.linspace(0, 2 * np.pi, num_directions, endpoint=False)

    # Pre-compute direction vectors (row_offset, col_offset) per unit step
    # Note: in array coordinates, row increases downward (south), col increases right (east)
    # Azimuth 0 = north = negative row direction
    dir_rows = -np.cos(azimuths_rad)  # negative because north = row decrease
    dir_cols = np.sin(azimuths_rad)  # east = col increase

    # Accumulate sin(max_horizon_angle) for each direction
    sin_horizon_sum = np.zeros((rows, cols), dtype=np.float32)

    total_steps = num_directions
    for dir_idx in range(num_directions):
        if feedback is not None and feedback.isCanceled():
            return np.full_like(dem, np.nan)

        dr = dir_rows[dir_idx]
        dc = dir_cols[dir_idx]

        # Track maximum elevation angle along this direction for all pixels
        max_angle = np.zeros((rows, cols), dtype=np.float32)

        for dist in range(1, search_radius + 1):
            # Compute the row/col offset for this distance step
            row_offset = dr * dist
            col_offset = dc * dist

            # Compute shifted elevation using bilinear-like nearest sampling
            # Use integer rounding for the shift offsets
            row_shift = int(round(row_offset))
            col_shift = int(round(col_offset))

            # Skip if the shift is zero (would compare pixel to itself)
            if row_shift == 0 and col_shift == 0:
                continue

            # Create the shifted view via slicing (much faster than np.roll)
            shifted = _shift_array(dem_filled, row_shift, col_shift, dem_mean)

            # Horizontal distance in map units
            actual_dist = np.sqrt(
                (row_shift * cellsize) ** 2 + (col_shift * cellsize) ** 2
            )

            # Elevation angle: arctan(Δz / distance)
            delta_z = shifted - dem_filled
            angle = np.arctan2(delta_z, actual_dist)

            # Update running maximum
            max_angle = np.maximum(max_angle, angle)

        # Clamp negative angles to 0 (below horizon doesn't occlude sky)
        max_angle = np.maximum(max_angle, 0.0)

        # Accumulate sin(max_horizon_angle)
        sin_horizon_sum += np.sin(max_angle)

        if feedback is not None:
            feedback.setProgress(int((dir_idx + 1) / total_steps * 100))

    # SVF = 1 - mean(sin(horizon_angles))
    svf = 1.0 - (sin_horizon_sum / num_directions)

    # Clamp to valid range
    svf = np.clip(svf, 0.0, 1.0).astype(np.float32)

    # Restore NaN
    svf[nan_mask] = np.nan

    return svf


def _shift_array(
    array: np.ndarray,
    row_shift: int,
    col_shift: int,
    fill_value: float,
) -> np.ndarray:
    """Create a shifted view of a 2D array, filling edges with a constant.

    This is equivalent to np.roll but without wrapping — shifted-out pixels
    are filled with fill_value instead of wrapping around.

    Args:
        array: 2D input array.
        row_shift: Number of rows to shift (positive = shift down).
        col_shift: Number of columns to shift (positive = shift right).
        fill_value: Value to fill at shifted-out edges.

    Returns:
        Shifted array with same shape as input.

    Rules:
        No wrapping — edge-shifted pixels get fill_value.
        This prevents horizon rays from wrapping around the raster edges.
    """
    rows, cols = array.shape
    result = np.full_like(array, fill_value)

    # Compute source and destination slices
    if row_shift >= 0:
        src_row_start, src_row_end = 0, rows - row_shift
        dst_row_start, dst_row_end = row_shift, rows
    else:
        src_row_start, src_row_end = -row_shift, rows
        dst_row_start, dst_row_end = 0, rows + row_shift

    if col_shift >= 0:
        src_col_start, src_col_end = 0, cols - col_shift
        dst_col_start, dst_col_end = col_shift, cols
    else:
        src_col_start, src_col_end = -col_shift, cols
        dst_col_start, dst_col_end = 0, cols + col_shift

    # Bounds check
    if (
        src_row_end <= src_row_start or
        src_col_end <= src_col_start or
        dst_row_end <= dst_row_start or
        dst_col_end <= dst_col_start
    ):
        return result

    result[dst_row_start:dst_row_end, dst_col_start:dst_col_end] = array[
        src_row_start:src_row_end, src_col_start:src_col_end
    ]

    return result
