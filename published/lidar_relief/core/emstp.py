"""emstp.py — Enhanced 4-Scale Topographic Position (e4MSTP).
exports: compute_e4mstp
used_by: algorithms/e4mstp_algorithm.py
rules:
  Generates a 3-band RGB composite using the Kokalj (2025) 4-step formula.
"""

import numpy as np
from .svf import sky_view_factor


def compute_e4mstp(
    O_pos: np.ndarray,
    O_neg: np.ndarray,
    LD: np.ndarray,
    S: np.ndarray,
    MSTP: np.ndarray,
    dem: np.ndarray,
    cellsize: float,
    feedback=None,
) -> np.ndarray:
    """Compute true e4MSTP using 4-step composite.

    Args:
        O_pos: Positive Openness [0, 1]
        O_neg: Negative Openness [0, 1]
        LD: Local Dominance [0, 1] (usually divided by 255 if output was uint8)
        S: Slope [0, 1]
        MSTP: MSTP RGB Composite [0, 1]
        dem: Input DEM array (for internal SVF calculation)
        cellsize: Pixel size (for internal SVF calculation)
    """

    # Step 1 — Morphological base:
    texture = O_pos * O_neg * LD  # all normalised [0,1], element-wise multiply
    R = S  # slope normalised [0,1]
    G = texture * (1.0 - S)
    B = texture * (1.0 - S)
    base = np.stack([R, G, B], axis=-1)

    # Step 2 — Dual SVF:
    # SVF_S uses radius ~10px, SVF_L uses radius ~50px. Both computed internally.
    SVF_S = sky_view_factor(dem, cellsize, search_radius=10, feedback=feedback)

    # If the first SVF call was cancelled (or returned all-NaN), bail
    # out early with a NaN-filled result so callers can detect the
    # cancellation. Previously the code computed the second SVF anyway,
    # then np.nan_to_num() silently turned the cancelled output black.
    if feedback is not None and feedback.isCanceled():
        return np.full(dem.shape + (3,), 0, dtype=np.uint8)
    if np.all(np.isnan(SVF_S)):
        return np.full(dem.shape + (3,), 0, dtype=np.uint8)

    SVF_L = sky_view_factor(dem, cellsize, search_radius=50, feedback=feedback)

    if feedback is not None and feedback.isCanceled():
        return np.full(dem.shape + (3,), 0, dtype=np.uint8)
    # Replace any NaN in SVF_L (cancellation or NoData) with a neutral
    # 1.0 (open sky) so the stretch doesn't go fully black.
    SVF_L = np.where(np.isnan(SVF_L), 1.0, SVF_L)
    SVF_S = np.where(np.isnan(SVF_S), 1.0, SVF_S)

    svf_s_stretched = np.clip((SVF_S - 0.7) / (1.0 - 0.7), 0.0, 1.0)
    svf_l_stretched = np.clip((SVF_L - 0.9) / (1.0 - 0.9), 0.0, 1.0)
    combined_svf = (svf_l_stretched * 1.0 + svf_s_stretched * 0.5) / 1.5

    # Step 3 — Multiply blend at 25% opacity:
    multiplied = base * combined_svf[..., np.newaxis]
    step3 = 0.25 * multiplied + 0.75 * base

    # Step 4 — Overlay MSTP at 90% opacity:

    # The user pseudo-code assumed MSTP was 2D or needed expansion: `MSTP[..., np.newaxis]`.
    # However, MSTP is typically an RGB array (H, W, 3). If it's already 3D, no newaxis is needed.
    # To be safe and strictly follow the snippet:
    if MSTP.ndim == 2:
        mstp_blend = MSTP[..., np.newaxis]
    else:
        mstp_blend = MSTP

    overlay = np.where(
        step3 < 0.5,
        2.0 * step3 * mstp_blend,
        1.0 - 2.0 * (1.0 - step3) * (1.0 - mstp_blend),
    )

    e4mstp = 0.90 * overlay + 0.10 * step3

    # Output: (e4mstp * 255).clip(0, 255).astype(np.uint8) — shape (H, W, 3).
    e4_byte = (e4mstp * 255.0).clip(0, 255)
    e4_byte = np.nan_to_num(e4_byte, nan=0)
    return e4_byte.astype(np.uint8)
