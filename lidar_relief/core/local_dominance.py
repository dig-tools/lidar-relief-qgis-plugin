"""local_dominance.py — Local Dominance visualization.
exports: compute_local_dominance(dem, cellsize, min_rad, max_rad, rad_inc, anglr_res, observer_h) -> ndarray
used_by: algorithms/local_dominance_algorithm.py → compute_local_dominance
rules:
  Pure NumPy — no QGIS imports.
"""

import numpy as np


def compute_local_dominance(
    dem: np.ndarray,
    cellsize: float,
    min_rad: float = 10.0,
    max_rad: float = 20.0,
    rad_inc: float = 1.0,
    anglr_res: float = 15.0,
    observer_h: float = 1.7,
    feedback=None,
) -> np.ndarray:
    """Compute Local Dominance using horizon-scanning ray trace."""
    if cellsize <= 0:
        raise ValueError("cellsize must be greater than 0")
    
    rows, cols = dem.shape

    z_obs = dem + observer_h
    pad_w = int(np.ceil(max_rad))
    padded_dem = np.pad(dem, pad_width=pad_w, mode="edge")

    ld_accumulator = np.zeros_like(dem, dtype=np.float32)
    valid_counts = np.zeros_like(dem, dtype=np.float32)

    directions = np.linspace(0, 2 * np.pi, int(360 / anglr_res), endpoint=False)
    radii = np.arange(min_rad, max_rad + rad_inc, rad_inc)

    total_steps = len(directions)

    for i, theta in enumerate(directions):
        if feedback and feedback.isCanceled():
            return np.array([])

        for r in radii:
            dy = int(np.round(-r * np.cos(theta)))
            dx = int(np.round(r * np.sin(theta)))

            # Slice padded DEM to get target_z
            y1, y2 = pad_w + dy, pad_w + dy + rows
            x1, x2 = pad_w + dx, pad_w + dx + cols
            target_z = padded_dem[y1:y2, x1:x2]

            delta_z = z_obs - target_z
            dist = r * cellsize

            angle_grid = np.arctan(delta_z / dist)

            # valid_counts where neither DEM nor target is NaN
            valid_mask = ~(np.isnan(dem) | np.isnan(target_z))

            # Mask out NaNs so they don't corrupt the accumulator
            angle_grid = np.where(valid_mask, angle_grid, 0)

            ld_accumulator += angle_grid
            valid_counts += valid_mask.astype(np.float32)

        if feedback is not None:
            feedback.setProgress(int((i + 1) / total_steps * 100))

    # To avoid division by zero on entirely NaN inputs
    with np.errstate(invalid="ignore"):
        ld_final = np.where(valid_counts > 0, ld_accumulator / valid_counts, np.nan)

    # Byte-scale
    ld_byte = np.clip((ld_final - 0.5) / (1.8 - 0.5) * 255, 0, 255)

    return ld_byte.astype(np.float32)
