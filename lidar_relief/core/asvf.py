"""asvf.py — Anisotropic Sky-View Factor (ASVF).
exports: anisotropic_sky_view_factor(array, cellsize, num_directions, search_radius, anisotropy_dir, anisotropy_weight)
used_by: algorithms/asvf_algorithm.py
rules:
  Pure NumPy — no QGIS imports.
  Vectorized trigonometric functions.
"""

import numpy as np

from .array_utils import _shift_array


def anisotropic_sky_view_factor(
    array: np.ndarray,
    cellsize: float,
    num_directions: int = 16,
    search_radius: int = 10,
    anisotropy_dir: float = 315.0,
    anisotropy_weight: float = 0.5,
    noise_level: int = 0,
    feedback=None,
) -> np.ndarray:
    """Compute Anisotropic Sky-View Factor (ASVF)."""
    rows, cols = array.shape

    # Fill NaN with the array mean for shifted lookups
    nan_mask = np.isnan(array)
    dem_mean = np.nanmean(array)
    dem_filled = array.copy()
    dem_filled[nan_mask] = dem_mean

    azimuths_rad = np.linspace(0, 2 * np.pi, num_directions, endpoint=False)
    dir_rows = -np.cos(azimuths_rad)
    dir_cols = np.sin(azimuths_rad)

    total_asvf = np.zeros((rows, cols), dtype=np.float32)
    weight_sum = 0.0

    anisotropy_rad = np.radians(anisotropy_dir)
    threshold_sin = np.sin(np.radians(2.0))

    total_steps = num_directions

    for dir_idx in range(num_directions):
        if feedback is not None and feedback.isCanceled():
            return np.full_like(array, np.nan)

        dr = dir_rows[dir_idx]
        dc = dir_cols[dir_idx]
        azimuth = azimuths_rad[dir_idx]

        dir_weight = 1.0 + anisotropy_weight * np.cos(azimuth - anisotropy_rad)
        weight_sum += dir_weight

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
            sin_angle = delta_z / hypot_3d

            if noise_level > 0:
                is_tracking = countdown > 0
                candidate_valid = np.where(
                    is_tracking & (sin_angle >= candidate_sin - threshold_sin),
                    True,
                    candidate_valid,
                )

                new_candidate = sin_angle > np.maximum(max_sin, candidate_sin)
                promote_mask = new_candidate & candidate_valid
                max_sin = np.where(promote_mask, candidate_sin, max_sin)

                candidate_sin = np.where(new_candidate, sin_angle, candidate_sin)
                countdown = np.where(new_candidate, noise_level, countdown)
                candidate_valid = np.where(new_candidate, False, candidate_valid)

                countdown = np.maximum(0, countdown - 1)

                expired_mask = (
                    (countdown == 0) & candidate_valid & (candidate_sin > max_sin)
                )
                max_sin = np.where(expired_mask, candidate_sin, max_sin)
                candidate_valid = np.where(expired_mask, False, candidate_valid)
                candidate_sin = np.where(countdown == 0, max_sin, candidate_sin)
            else:
                max_sin = np.maximum(max_sin, sin_angle)

        if noise_level > 0:
            promote_end = candidate_valid | (countdown > 0)
            max_sin = np.where(promote_end, np.maximum(max_sin, candidate_sin), max_sin)

        max_sin = np.maximum(max_sin, 0.0)

        # ASVF formula component for this direction
        svf_dir = 1.0 - max_sin
        total_asvf += svf_dir * dir_weight

        if feedback is not None:
            feedback.setProgress(int((dir_idx + 1) / total_steps * 100))

    asvf = total_asvf / weight_sum
    asvf = np.clip(asvf, 0.0, 1.0).astype(np.float32)
    asvf[nan_mask] = np.nan

    return asvf
