"""svf.py — Sky-View Factor (SVF) computation for terrain analysis.
exports: sky_view_factor(dem, cellsize, num_directions, search_radius, noise_level) -> ndarray
used_by: algorithms/svf_algorithm.py → sky_view_factor
rules:
  Pure NumPy — no QGIS imports.
"""

import numpy as np
from .array_utils import _shift_array


def _build_horizon_samples(num_directions, search_radius, scale=3):
    """Build the list of (row_shift, col_shift, distance) samples for each
    direction, deduplicated by integer pixel coordinates.

    This mirrors rvt-py's horizon_shift_vector approach: supersample the
    ray at `scale` times the integer resolution, round to integer pixel
    coordinates, deduplicate, and sort by true Euclidean distance. This
    ensures every integer pixel along the ray is visited at least once
    (fixing the previous undersampling bug where consecutive distances
    rounded to the same pixel on diagonal azimuths), AND the distance
    used for the slope calculation is the true Euclidean distance to
    that pixel.

    Returns:
        List of tuples: (direction_index, row_shift, col_shift, distance)
        sorted by direction then by distance ascending.
    """
    angles = (2 * np.pi / num_directions) * np.arange(num_directions)
    dir_rows = -np.cos(angles)  # negative because row index increases southward
    dir_cols = np.sin(angles)

    min_radius = 1  # don't sample the origin pixel
    samples = []
    for dir_idx in range(num_directions):
        dr = dir_rows[dir_idx]
        dc = dir_cols[dir_idx]
        # Supersample the ray from min_radius to search_radius at `scale`
        # resolution. This matches rvt-py's horizon_shift_vector exactly:
        # radii = arange((radius_max - min_radius) * scale + 1) / scale + min_radius
        radii = np.arange((search_radius - min_radius) * scale + 1) / scale + min_radius
        # Compute fractional pixel coordinates along the ray
        row_frac = dr * radii
        col_frac = dc * radii
        # Round to integer pixel coordinates
        row_int = np.round(row_frac).astype(np.int32)
        col_int = np.round(col_frac).astype(np.int32)
        # Deduplicate by (row, col) — keep the first occurrence (smallest radius)
        seen = set()
        unique_rows = []
        unique_cols = []
        unique_dists = []
        for r, c, frac_r, frac_c in zip(row_int, col_int, row_frac, col_frac):
            key = (int(r), int(c))
            if key in seen:
                continue
            if r == 0 and c == 0:
                continue
            seen.add(key)
            unique_rows.append(int(r))
            unique_cols.append(int(c))
            # True Euclidean distance to this pixel centre (in pixel units)
            unique_dists.append(float(np.hypot(frac_r, frac_c)))
        samples.append((dir_idx, unique_rows, unique_cols, unique_dists))
    return samples


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

    # Pre-compute the horizon sample points for each direction using
    # the supersampling+dedup approach (fixes the horizon rounding bug
    # documented in the v2.0.6 review).
    horizon_samples = _build_horizon_samples(num_directions, search_radius)

    sin_horizon_sum = np.zeros((rows, cols), dtype=np.float32)

    for dir_idx, row_shifts, col_shifts, dists in horizon_samples:
        if feedback is not None and feedback.isCanceled():
            return np.full_like(dem, np.nan)

        max_sin = np.zeros((rows, cols), dtype=np.float32)

        if noise_level > 0:
            candidate_sin = np.zeros((rows, cols), dtype=np.float32)
            countdown = np.zeros((rows, cols), dtype=np.int32)
            candidate_valid = np.zeros((rows, cols), dtype=bool)

        for row_shift, col_shift, dist_units in zip(row_shifts, col_shifts, dists):
            # actual distance in map units (cellsize * pixel-distance)
            actual_dist = dist_units * cellsize
            if actual_dist == 0:
                continue

            shifted = _shift_array(dem_filled, row_shift, col_shift, dem_mean)

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

                # If tracking and found new candidate, old candidate is validated implicitly
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
            # At the end of the ray, promote candidates that were valid,
            # or didn't get enough look-ahead pixels to be rejected
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
