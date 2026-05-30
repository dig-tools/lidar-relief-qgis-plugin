"""pca.py — Principal Component Analysis (PCA) composite.
exports: compute_pca_composite(svf, openness, slope, local_dominance)
used_by: algorithms/pca_algorithm.py
rules:
  Compute PCA of 4 input variables to generate a 3-band RGB image.
  Uses scipy for eigen decomposition.
"""

import numpy as np
from scipy import linalg


def compute_pca_composite(
    svf: np.ndarray,
    openness: np.ndarray,
    slope: np.ndarray,
    local_dominance: np.ndarray,
    feedback=None,
) -> np.ndarray:
    """Compute PCA RGB Composite.

    Combines 4 relief metrics into a 3-band (RGB) image representing the
    first 3 Principal Components.

    Args:
        svf, openness, slope, local_dominance: 2D numpy arrays of same shape.

    Returns:
        3D numpy array (rows, cols, 3) in [0, 255] float32.
    """
    rows, cols = svf.shape

    # Mask out NaNs
    mask = ~(
        np.isnan(svf) | np.isnan(openness) | np.isnan(slope) | np.isnan(local_dominance)
    )

    # Extract valid pixels
    v_svf = svf[mask]
    v_open = openness[mask]
    v_slope = slope[mask]
    v_ld = local_dominance[mask]

    if len(v_svf) == 0:
        return np.zeros((rows, cols, 3), dtype=np.float32)

    if feedback and feedback.isCanceled():
        return np.array([])

    # Standardize data (0 mean, 1 variance)
    data = np.stack([v_svf, v_open, v_slope, v_ld], axis=1)  # (N, 4)
    mean = np.mean(data, axis=0)
    std = np.std(data, axis=0)

    # Avoid division by zero
    std[std == 0] = 1.0
    data_std = (data - mean) / std

    if feedback and feedback.isCanceled():
        return np.array([])

    # Covariance matrix (4x4)
    cov = np.cov(data_std, rowvar=False)

    # Eigen decomposition using scipy
    evals, evecs = linalg.eigh(cov)

    # Sort eigenvalues in descending order
    idx = np.argsort(evals)[::-1]
    evecs = evecs[:, idx]

    # Take first 3 principal components (N, 3)
    pc = np.dot(data_std, evecs[:, :3])

    if feedback and feedback.isCanceled():
        return np.array([])

    # Normalize PCs to [0, 255]
    # Use 2-98 percentile for robust contrast stretch
    pc_out = np.zeros_like(pc)
    for i in range(3):
        pmin = np.percentile(pc[:, i], 2)
        pmax = np.percentile(pc[:, i], 98)
        if pmax > pmin:
            pc_out[:, i] = (pc[:, i] - pmin) / (pmax - pmin) * 255.0
        else:
            pc_out[:, i] = 0.0

    pc_out = np.clip(pc_out, 0.0, 255.0)

    # Reconstruct 3D array
    rgb = np.zeros((rows, cols, 3), dtype=np.float32)
    rgb[mask, 0] = pc_out[:, 0]
    rgb[mask, 1] = pc_out[:, 1]
    rgb[mask, 2] = pc_out[:, 2]

    # Fill masked areas with NaN
    rgb[~mask] = np.nan

    return rgb
