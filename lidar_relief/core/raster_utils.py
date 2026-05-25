"""raster_utils.py — GDAL raster I/O utilities for LiDAR Relief plugin.
exports: DemData, read_dem_to_array(path, feedback) -> DemData,
         write_array_to_raster(array, path, geotransform, projection, nodata),
         get_cell_size(geotransform) -> float, apply_nodata_mask(input, output, nodata) -> ndarray
used_by: algorithms/hillshade_algorithm.py → read_dem_to_array, write_array_to_raster
         algorithms/slrm_algorithm.py → read_dem_to_array, write_array_to_raster
         algorithms/svf_algorithm.py → read_dem_to_array, write_array_to_raster
         algorithms/slope_algorithm.py → read_dem_to_array, write_array_to_raster
         algorithms/batch_algorithm.py → read_dem_to_array, write_array_to_raster
rules:
  All raster I/O MUST go through GDAL — never raw file operations.
  NoData values must be converted to np.nan before processing.
  Output arrays must have nodata re-applied before writing.
  No QGIS imports — only GDAL and NumPy.
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from osgeo import gdal, osr

# Suppress GDAL printing errors to stderr; we handle them ourselves.
gdal.UseExceptions()


@dataclass
class DemData:
    """Container for DEM raster data and metadata.

    Rules:
        array is always float32 with nodata pixels set to np.nan.
        nodata_mask is a boolean array: True where original data was nodata.
    """
    array: np.ndarray
    nodata: Optional[float]
    nodata_mask: np.ndarray
    geotransform: tuple
    projection: str
    x_size: int
    y_size: int


def read_dem_to_array(source_path: str, feedback=None) -> DemData:
    """Read a DEM raster file into a NumPy float32 array via GDAL.

    Args:
        source_path: File path to the raster dataset.
        feedback: Optional QGIS feedback object for progress reporting.

    Returns:
        DemData with elevation values as float32, nodata pixels as np.nan.

    Raises:
        ValueError: If the raster cannot be opened or has no bands.

    Rules:
        Always reads band 1 only.
        Always casts to float32 for consistent arithmetic.
        Nodata values are replaced with np.nan for safe neighbourhood operations.
    """
    dataset = gdal.Open(source_path, gdal.GA_ReadOnly)
    if dataset is None:
        raise ValueError(f"Cannot open raster: {source_path}")

    band = dataset.GetRasterBand(1)
    if band is None:
        raise ValueError(f"Raster has no bands: {source_path}")

    nodata = band.GetNoDataValue()
    geotransform = dataset.GetGeoTransform()
    projection = dataset.GetProjection()
    x_size = dataset.RasterXSize
    y_size = dataset.RasterYSize

    if feedback:
        feedback.setProgressText("Reading DEM raster...")

    array = band.ReadAsArray().astype(np.float32)

    # Build nodata mask and replace with NaN
    if nodata is not None:
        nodata_mask = np.isclose(array, nodata, rtol=1e-5) | np.isnan(array)
    else:
        nodata_mask = np.isnan(array)

    array[nodata_mask] = np.nan

    # Clean up GDAL objects
    band = None
    dataset = None

    return DemData(
        array=array,
        nodata=nodata,
        nodata_mask=nodata_mask,
        geotransform=geotransform,
        projection=projection,
        x_size=x_size,
        y_size=y_size,
    )


def write_array_to_raster(
    array: np.ndarray,
    output_path: str,
    geotransform: tuple,
    projection: str,
    nodata: Optional[float] = None,
) -> None:
    """Write a NumPy array to a GeoTIFF file via GDAL.

    Args:
        array: 2D NumPy array to write.
        output_path: Output file path (.tif).
        geotransform: GDAL geotransform tuple (6 elements).
        projection: WKT projection string.
        nodata: NoData value to set on the output band.

    Rules:
        Always writes as GeoTIFF with LZW compression.
        np.nan values in the array are written as the nodata value.
        FlushCache is called to ensure complete disk write.
    """
    if array.ndim == 3:
        y_size, x_size, bands = array.shape
    else:
        y_size, x_size = array.shape
        bands = 1

    # Determine output data type
    if array.dtype == np.uint8:
        gdal_dtype = gdal.GDT_Byte
    else:
        gdal_dtype = gdal.GDT_Float32

    driver = gdal.GetDriverByName("GTiff")
    
    creation_options = ["COMPRESS=LZW", "TILED=YES"]
    if bands == 3:
        creation_options.append("PHOTOMETRIC=RGB")
        
    out_dataset = driver.Create(
        output_path,
        x_size,
        y_size,
        bands,
        gdal_dtype,
        options=creation_options,
    )

    out_dataset.SetGeoTransform(geotransform)
    out_dataset.SetProjection(projection)

    if bands == 1:
        out_band = out_dataset.GetRasterBand(1)

        # Replace NaN with nodata value before writing
        write_array = array.copy()
        if nodata is not None:
            nan_mask = np.isnan(write_array)
            write_array[nan_mask] = nodata
            out_band.SetNoDataValue(float(nodata))
        elif np.any(np.isnan(write_array)):
            # If no nodata was specified but we have NaN, use -9999
            nan_mask = np.isnan(write_array)
            write_array[nan_mask] = -9999.0
            out_band.SetNoDataValue(-9999.0)

        out_band.WriteArray(write_array)
    else:
        for b in range(bands):
            out_band = out_dataset.GetRasterBand(b + 1)
            write_array = array[:, :, b].copy()
            
            # RGB images don't typically use nodata in the same way, 
            # but if it's not uint8 we should handle NaN
            if array.dtype != np.uint8:
                if nodata is not None:
                    nan_mask = np.isnan(write_array)
                    write_array[nan_mask] = nodata
                    out_band.SetNoDataValue(float(nodata))
            elif nodata is not None:
                # For uint8, if nodata is provided, just set it
                out_band.SetNoDataValue(float(nodata))
                
            out_band.WriteArray(write_array)

    out_dataset.FlushCache()

    # Clean up
    out_band = None
    out_dataset = None


def get_cell_size(geotransform: tuple) -> float:
    """Extract the pixel size (cell size) from a GDAL geotransform.

    Args:
        geotransform: GDAL geotransform tuple (originX, pixelW, rot, originY, rot, pixelH).

    Returns:
        Cell size in map units (average of |pixelW| and |pixelH|).

    Rules:
        Returns absolute value — cell size is always positive.
        Averages X and Y pixel sizes for non-square pixels.
    """
    pixel_width = abs(geotransform[1])
    pixel_height = abs(geotransform[5])
    return (pixel_width + pixel_height) / 2.0


def apply_nodata_mask(
    input_array: np.ndarray,
    output_array: np.ndarray,
    nodata_mask: np.ndarray,
) -> np.ndarray:
    """Propagate nodata from input to output array.

    Args:
        input_array: Original DEM array (used for reference only).
        output_array: Computed result array.
        nodata_mask: Boolean mask — True where input was nodata.

    Returns:
        Output array with nodata pixels set to np.nan.

    Rules:
        Nodata propagation must happen AFTER algorithm computation.
        Original nodata pixels must always remain nodata in output.
    """
    result = output_array.copy()
    result[nodata_mask] = np.nan
    return result


def process_in_tiles(
    source_path: str,
    output_path: str,
    algorithm_func,
    halo_size: int,
    tile_size: int = 2048,
    feedback=None,
    **kwargs
) -> None:
    """Process a large DEM in tiles to conserve memory.

    Args:
        source_path: Input DEM path.
        output_path: Output raster path.
        algorithm_func: Callable algorithm (e.g. sky_view_factor).
        halo_size: Margin around each tile in pixels to prevent edge effects.
        tile_size: Processing block size (interior pixels).
        feedback: QGIS feedback object for progress and cancellation.
        **kwargs: Extra arguments passed to algorithm_func.

    Rules:
        Reads blocks of (tile_size + 2*halo_size).
        Writes interior blocks of (tile_size).
        Respects dataset boundaries.
    """
    dataset = gdal.Open(source_path, gdal.GA_ReadOnly)
    if dataset is None:
        raise ValueError(f"Cannot open {source_path}")

    band = dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    x_size = dataset.RasterXSize
    y_size = dataset.RasterYSize
    geotransform = dataset.GetGeoTransform()
    cellsize = get_cell_size(geotransform)

    # First, test the algorithm on a small 1x1 block to get output dtype and bands
    test_out = algorithm_func(np.zeros((3, 3), dtype=np.float32), cellsize, **kwargs)
    if test_out.ndim == 3:
        out_bands = test_out.shape[2]
    else:
        out_bands = 1
        
    if test_out.dtype == np.uint8:
        gdal_dtype = gdal.GDT_Byte
    else:
        gdal_dtype = gdal.GDT_Float32

    driver = gdal.GetDriverByName("GTiff")
    creation_options = ["COMPRESS=LZW", "TILED=YES"]
    if out_bands == 3:
        creation_options.append("PHOTOMETRIC=RGB")
        
    out_dataset = driver.Create(
        output_path, x_size, y_size, out_bands, gdal_dtype, options=creation_options
    )
    out_dataset.SetGeoTransform(geotransform)
    out_dataset.SetProjection(dataset.GetProjection())
    
    if nodata is not None and gdal_dtype != gdal.GDT_Byte:
        for b in range(out_bands):
            out_dataset.GetRasterBand(b + 1).SetNoDataValue(float(nodata))

    total_tiles = ((x_size + tile_size - 1) // tile_size) * ((y_size + tile_size - 1) // tile_size)
    tiles_done = 0

    for y in range(0, y_size, tile_size):
        for x in range(0, x_size, tile_size):
            if feedback and feedback.isCanceled():
                out_dataset = None
                dataset = None
                return

            # Compute actual tile dimensions (handling edges)
            win_x_size = min(tile_size, x_size - x)
            win_y_size = min(tile_size, y_size - y)

            # Compute read window (with halo)
            read_x = max(0, x - halo_size)
            read_y = max(0, y - halo_size)
            read_x_size = min(x_size - read_x, win_x_size + (x - read_x) + halo_size)
            read_y_size = min(y_size - read_y, win_y_size + (y - read_y) + halo_size)

            # Read block
            block = band.ReadAsArray(read_x, read_y, read_x_size, read_y_size).astype(np.float32)
            
            # Handle nodata in input
            block_nodata_mask = np.zeros_like(block, dtype=bool)
            if nodata is not None:
                block_nodata_mask = np.isclose(block, nodata, rtol=1e-5) | np.isnan(block)
            else:
                block_nodata_mask = np.isnan(block)
                
            block[block_nodata_mask] = np.nan

            # Run algorithm
            result_block = algorithm_func(block, cellsize, **kwargs)
            
            # Reapply nodata mask
            if result_block.ndim == 3:
                for b in range(out_bands):
                    band_slice = result_block[:, :, b]
                    band_slice[block_nodata_mask] = 0 if gdal_dtype == gdal.GDT_Byte else np.nan
            else:
                result_block[block_nodata_mask] = 0 if gdal_dtype == gdal.GDT_Byte else np.nan

            # Extract the interior (remove halo)
            crop_top = y - read_y
            crop_bottom = crop_top + win_y_size
            crop_left = x - read_x
            crop_right = crop_left + win_x_size

            if result_block.ndim == 3:
                interior = result_block[crop_top:crop_bottom, crop_left:crop_right, :]
            else:
                interior = result_block[crop_top:crop_bottom, crop_left:crop_right]

            # Replace remaining NaNs with nodata for writing
            if gdal_dtype != gdal.GDT_Byte and nodata is not None:
                interior[np.isnan(interior)] = nodata

            # Write to output
            if out_bands == 1:
                out_dataset.GetRasterBand(1).WriteArray(interior, x, y)
            else:
                for b in range(out_bands):
                    out_dataset.GetRasterBand(b + 1).WriteArray(interior[:, :, b], x, y)

            tiles_done += 1
            if feedback:
                feedback.setProgress(int(100 * tiles_done / total_tiles))

    out_dataset.FlushCache()
    out_dataset = None
    dataset = None
