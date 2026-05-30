"""test_pca.py — Tests for PCA Composite.
exports: test_pca_basic()
used_by: pytest runner
"""

import numpy as np
from lidar_relief.core.pca import compute_pca_composite


def test_pca_basic():
    # 20x20 dummy inputs
    svf = np.random.rand(20, 20).astype(np.float32)
    openness = np.random.rand(20, 20).astype(np.float32)
    slope = np.random.rand(20, 20).astype(np.float32)
    ld = np.random.rand(20, 20).astype(np.float32)

    result = compute_pca_composite(svf, openness, slope, ld)

    # Check shape (3 channels)
    assert result.shape == (20, 20, 3)

    # Check values are between 0 and 255
    assert np.nanmin(result) >= 0.0
    assert np.nanmax(result) <= 255.0
