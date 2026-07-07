"""test_svf_noise.py — Tests for SVF noise lookahead feature.
exports: test_svf_noise_reduction()
used_by: pytest runner
"""

import numpy as np
from lidar_relief.core.svf import sky_view_factor


def test_svf_noise_reduction():
    # 20x20 dummy DEM
    rows, cols = 20, 20
    dem = np.zeros((rows, cols), dtype=np.float32)
    center = 10

    # Create a 1-pixel anomalous spike (noise)
    dem[center, center] = 100.0

    # Run SVF with NO noise reduction (level 0)
    # The spike should heavily occlude the sky for nearby pixels
    svf_noisy = sky_view_factor(dem, cellsize=1.0, search_radius=10, noise_level=0)

    # Run SVF with high noise reduction (level 3)
    # The look-ahead should discard the 1-pixel spike
    svf_clean = sky_view_factor(dem, cellsize=1.0, search_radius=10, noise_level=3)

    # The adjacent pixel (10, 11) should have a much higher SVF in the clean version
    # because the spike is ignored.
    val_noisy = svf_noisy[10, 11]
    val_clean = svf_clean[10, 11]

    assert val_clean > val_noisy

    # In fact, since the rest of the DEM is flat, the clean SVF should be close to 1.0
    # whereas the noisy one will be significantly lower.
    assert val_clean > 0.9
