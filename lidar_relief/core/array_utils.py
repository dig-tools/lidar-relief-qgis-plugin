"""array_utils.py — Array manipulation utilities for LiDAR Relief plugin.
exports: _shift_array(array, row_shift, col_shift, fill_value) -> ndarray
used_by: core/svf.py → _shift_array
         core/openness.py → _shift_array
rules:
  Pure NumPy — no QGIS or GDAL imports.
"""

import numpy as np


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
    if any(
        [
            src_row_end <= src_row_start,
            src_col_end <= src_col_start,
            dst_row_end <= dst_row_start,
            dst_col_end <= dst_col_start,
        ]
    ):
        return result

    result[dst_row_start:dst_row_end, dst_col_start:dst_col_end] = array[
        src_row_start:src_row_end, src_col_start:src_col_end
    ]

    return result
