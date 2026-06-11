"""svf.py — Sky-View Factor (SVF) computation for terrain analysis.
exports: sky_view_factor(dem, cellsize, num_directions, search_radius, noise_level) -> ndarray
used_by: algorithms/svf_algorithm.py → sky_view_factor
rules:
  Pure NumPy — no QGIS imports.
"""

import numpy as np
from .array_utils import _shift_array


def sky_view_factor(
    dem: np.ndarray,
    cellsize: float,
    num_directions: int = 16,
    search_radius: int = 10,
    noise_level: int = 0,
    feedback=None,
) -> np.ndarray:
    rows, cols = dem.shape

    nan_mask = np.isnan(dem)
    dem_mean = np.nanmean(dem)
    dem_filled = dem.copy()
    dem_filled[nan_mask] = dem_mean

    azimuths_rad = np.linspace(0, 2 * np.pi, num_directions, endpoint=False)
    dir_rows = -np.cos(azimuths_rad)
    dir_cols = np.sin(azimuths_rad)

    sin_horizon_sum = np.zeros((rows, cols), dtype=np.float32)

    for dir_idx in range(num_directions):
        if feedback is not None and feedback.isCanceled():
            return np.full_like(dem, np.nan)

        dr = dir_rows[dir_idx]
        dc = dir_cols[dir_idx]

        max_sin = np.zeros((rows, cols), dtype=np.float32)

        if noise_level > 0:
            candidate_sin = np.zeros((rows, cols), dtype=np.float32)
            countdown = np.zeros((rows, cols), dtype=np.int32)
            candidate_valid = np.zeros((rows, cols), dtype=bool)

        for dist in range(1, search_radius + 1):
            row_offset = dr * dist
            col_offset = dc * dist
            row_shift = int(round(row_offset))
            col_shift = int(round(col_offset))

            if row_shift == 0 and col_shift == 0:
                continue

            shifted = _shift_array(dem_filled, row_shift, col_shift, dem_mean)
            actual_dist = np.sqrt(
                (row_shift * cellsize) ** 2 + (col_shift * cellsize) ** 2
            )

            delta_z = shifted - dem_filled
            hypot_3d = np.hypot(delta_z, actual_dist)
            # Avoid division by zero
            hypot_3d = np.where(hypot_3d == 0, 1.0, hypot_3d)
            sin_angle = delta_z / hypot_3d

            if noise_level > 0:
                is_tracking = countdown > 0

                # Validate if subsequent pixel maintains or exceeds candidate
                just_validated = is_tracking & (sin_angle >= candidate_sin)
                candidate_valid = candidate_valid | just_validated

                # New candidate found
                is_new_candidate = sin_angle > np.maximum(max_sin, candidate_sin)

                # If tracking and found new candidate, old candidate is validated implicitly (since sin_angle > candidate_sin)
                max_sin = np.where(
                    is_tracking & is_new_candidate, candidate_sin, max_sin
                )

                # Set new candidate
                candidate_sin = np.where(is_new_candidate, sin_angle, candidate_sin)
                countdown = np.where(is_new_candidate, noise_level, countdown)
                candidate_valid = np.where(is_new_candidate, False, candidate_valid)

                # Decrement countdown
                countdown = np.where(
                    ~is_new_candidate & is_tracking, countdown - 1, countdown
                )

                # Check expirations
                expired = (countdown == 0) & is_tracking & ~is_new_candidate
                max_sin = np.where(expired & candidate_valid, candidate_sin, max_sin)
                candidate_sin = np.where(expired, max_sin, candidate_sin)
                candidate_valid = np.where(expired, False, candidate_valid)
            else:
                max_sin = np.maximum(max_sin, sin_angle)

        if noise_level > 0:
            # At the end of the ray, promote candidates that were valid, or didn't get enough look-ahead pixels to be rejected
            promote_end = candidate_valid | (countdown > 0)
            max_sin = np.where(promote_end, np.maximum(max_sin, candidate_sin), max_sin)

        max_sin = np.maximum(max_sin, 0.0)
        sin_horizon_sum += max_sin

        if feedback is not None:
            feedback.setProgress(int((dir_idx + 1) / num_directions * 100))

    svf = 1.0 - (sin_horizon_sum / num_directions)
    svf = np.clip(svf, 0.0, 1.0).astype(np.float32)
    svf[nan_mask] = np.nan

    return svf
