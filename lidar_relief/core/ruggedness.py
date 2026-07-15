"""Terrain Ruggedness Index (TRI) computation.

Implements the Riley et al. 3x3 neighbourhood measure using pure NumPy.
"""

import numpy as np


def compute_ruggedness(dem: np.ndarray, cellsize: float) -> np.ndarray:
    """Return Riley Terrain Ruggedness Index values in elevation units.

    Each output pixel is the square root of the summed squared elevation
    differences between the centre cell and its eight neighbours. Nodata
    centre cells remain nodata; nodata neighbours contribute zero so that
    data edges do not acquire artificial high-ruggedness halos.
    """
    if cellsize <= 0:
        raise ValueError("cellsize must be positive")
    if dem.ndim != 2:
        raise ValueError("dem must be a 2D array")

    source = np.asarray(dem, dtype=np.float64)
    padded = np.pad(source, 1, mode="edge")
    centre = padded[1:-1, 1:-1]
    squared_difference_sum = np.zeros(source.shape, dtype=np.float64)

    for row_offset in range(3):
        for column_offset in range(3):
            if row_offset == 1 and column_offset == 1:
                continue
            neighbour = padded[
                row_offset:row_offset + source.shape[0],
                column_offset:column_offset + source.shape[1],
            ]
            difference = np.where(np.isnan(neighbour), 0.0, neighbour - centre)
            squared_difference_sum += difference * difference

    result = np.sqrt(squared_difference_sum).astype(np.float32)
    result[np.isnan(source)] = np.nan
    return result
