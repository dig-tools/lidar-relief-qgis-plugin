"""dem_difference.py — Multi-temporal DEM change detection with probabilistic DoD.

exports: compute_dod(dem_old_path, dem_new_path, **kwargs) -> dict
         compute_dod_xarray(dem_old, dem_new, **kwargs) -> dict
         load_dem(path) -> xr.DataArray

used_by: algorithms/temporal_difference_algorithm.py

rules:
  Uses xarray + rioxarray for labeled array operations.
  Probabilistic Level of Detection (LoD) masks noise using propagated RMSE.
  All dependencies are optional — check availability before calling.
"""

import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

try:
    import xarray as xr
    import rioxarray

    _XARRAY_AVAILABLE = True
except ImportError:
    _XARRAY_AVAILABLE = False


def xarray_available() -> bool:
    """Check if xarray and rioxarray are installed."""
    return _XARRAY_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError with clear instructions if xarray missing."""
    if not _XARRAY_AVAILABLE:
        raise ImportError(
            "Multi-temporal change detection requires 'xarray' and "
            "'rioxarray'.\n\n"
            "Install them via the OSGeo4W Shell:\n"
            "  pip install xarray rioxarray\n"
        )


def load_dem(path: str, band: int = 1) -> "xr.DataArray":
    """Load a DEM raster into an xarray DataArray with spatial coordinates.

    Args:
        path: Path to the DEM GeoTIFF.
        band: Raster band to load (default 1).

    Returns:
        xarray DataArray with 'x' and 'y' coordinate dims and CRS metadata.

    Raises:
        RuntimeError: If the file cannot be opened.
    """
    check_dependencies()

    try:
        da = rioxarray.open_rasterio(path, band_as_variable=False)
    except Exception as e:
        raise RuntimeError(f"Cannot open DEM: {path}: {e}") from e

    # Select band and squeeze if single-band
    if da.sizes.get("band", 0) > 1:
        da = da.isel(band=band - 1)

    # Remove band dim if present
    if "band" in da.dims:
        da = da.squeeze("band")

    da.name = os.path.splitext(os.path.basename(path))[0]
    return da


def compute_dod(
    dem_old_path: str,
    dem_new_path: str,
    output_dir: str,
    rmse_old: float = 0.15,
    rmse_new: float = 0.15,
    confidence_level: float = 1.96,
    align_method: str = "bilinear",
    project_name: str = "change_detection",
) -> dict:
    """Compute a probabilistic DEM of Difference (DoD) between two DEMs.

    Args:
        dem_old_path: Path to the older DEM (GeoTIFF).
        dem_new_path: Path to the newer DEM (GeoTIFF).
        output_dir: Directory for output rasters.
        rmse_old: Vertical RMSE of the older DEM (metres).
        rmse_new: Vertical RMSE of the newer DEM (metres).
        confidence_level: Z-score for significance threshold
            (1.96 = 95% confidence, 2.58 = 99% confidence).
        align_method: Resampling method for alignment
            ('bilinear', 'cubic', 'nearest').
        project_name: Prefix for output filenames.

    Returns:
        dict with paths to output rasters and summary statistics.
    """
    check_dependencies()
    os.makedirs(output_dir, exist_ok=True)

    # Load DEMs
    dem_old = load_dem(dem_old_path)
    dem_new = load_dem(dem_new_path)

    return compute_dod_xarray(
        dem_old=dem_old,
        dem_new=dem_new,
        output_dir=output_dir,
        rmse_old=rmse_old,
        rmse_new=rmse_new,
        confidence_level=confidence_level,
        align_method=align_method,
        project_name=project_name,
    )


def compute_dod_xarray(
    dem_old: "xr.DataArray",
    dem_new: "xr.DataArray",
    output_dir: str,
    rmse_old: float = 0.15,
    rmse_new: float = 0.15,
    confidence_level: float = 1.96,
    align_method: str = "bilinear",
    project_name: str = "change_detection",
) -> dict:
    """Compute probabilistic DEM of Difference from xarray DataArrays.

    The DoD methodology:
        1. Align new DEM to old DEM grid (reproject if needed)
        2. DoD = DEM_new - DEM_old
        3. Propagated error: sigma = sqrt(RMSE_old² + RMSE_new²)
        4. LoD threshold: |DoD| > confidence_level × sigma
        5. Output: DoD raster + significance mask + volume report

    Args:
        dem_old: xarray DataArray of the older DEM.
        dem_new: xarray DataArray of the newer DEM.
        output_dir: Directory for output rasters.
        rmse_old: Vertical RMSE of older DEM.
        rmse_new: Vertical RMSE of newer DEM.
        confidence_level: Z-score for significance.
        align_method: Resampling method.
        project_name: Prefix for output filenames.

    Returns:
        dict with:
            - 'dod_path': path to the signed DoD raster
            - 'mask_path': path to the significance mask (byte)
            - 'volume_report': dict of cut/fill volumes
            - 'propagated_error': propagated RMSE
            - 'threshold': LoD threshold used
            - 'significant_pixels': count of significant changes
            - 'total_pixels': total valid pixels
    """
    check_dependencies()

    import rioxarray  # noqa: F401 — registers .rio accessor on xarray objects

    # Align new DEM to old DEM grid (reproject / match CRS)
    if dem_old.rio.crs != dem_new.rio.crs:
        logger.info(
            "CRS mismatch: %s → %s. Reprojecting...",
            dem_new.rio.crs, dem_old.rio.crs,
        )
        dem_new = dem_new.rio.reproject_match(dem_old, resampling=align_method)

    # Match grid to old DEM
    dem_new_aligned = dem_new.rio.reproject_match(
        dem_old, resampling=align_method
    )

    # Fill nodata with NaN for safe arithmetic
    dem_old_filled = dem_old.copy()
    dem_new_filled = dem_new_aligned.copy()

    if hasattr(dem_old_filled, 'rio') and dem_old_filled.rio.nodata is not None:
        dem_old_filled = dem_old_filled.where(
            dem_old_filled != dem_old_filled.rio.nodata
        )
    if hasattr(dem_new_filled, 'rio') and dem_new_filled.rio.nodata is not None:
        dem_new_filled = dem_new_filled.where(
            dem_new_filled != dem_new_filled.rio.nodata
        )

    # Compute DoD
    dod = dem_new_filled - dem_old_filled

    # Propagated error
    propagated_error = np.sqrt(rmse_old ** 2 + rmse_new ** 2)
    threshold = confidence_level * propagated_error

    # Significance mask
    # 0 = no significant change, 1 = negative change (erosion/cut),
    # 2 = positive change (deposition/fill)
    mask = xr.where(np.abs(dod) > threshold, 1, 0).astype(np.int8)
    mask = xr.where(
        (dod < -threshold) & (np.abs(dod) > threshold),
        np.int8(1),  # negative change
        mask,
    )
    mask = xr.where(
        (dod > threshold) & (np.abs(dod) > threshold),
        np.int8(2),  # positive change
        mask,
    )

    # Statistics
    valid_mask = ~np.isnan(dod)
    total_pixels = int(valid_mask.sum().values)
    significant = int((mask > 0).sum().values)
    neg_changes = int((mask == 1).sum().values)
    pos_changes = int((mask == 2).sum().values)

    # Volume estimates (metres³ assuming CRS units are metres)
    # Cell area from geotransform
    if hasattr(dod, 'rio'):
        transform = dod.rio.transform()
        cell_area = abs(transform[0] * transform[4])  # pixel_width × pixel_height
    else:
        cell_area = 1.0

    # Cut volume (negative change) and fill volume (positive change)
    dod_valid = dod.where(~np.isnan(dod), 0)
    cut_volume = float(abs(dod_valid.where(dod_valid < 0, 0)).sum().values * cell_area)
    fill_volume = float(dod_valid.where(dod_valid > 0, 0).sum().values * cell_area)
    net_volume = fill_volume - cut_volume

    # Write outputs
    dod_path = os.path.join(output_dir, f"{project_name}_dod.tif")
    mask_path = os.path.join(output_dir, f"{project_name}_mask.tif")

    # Set CRS and nodata for export
    dod_out = dod.copy()
    mask_out = mask.copy()

    for attr_name in ["crs", "transform"]:
        for ds in [dod_out, mask_out]:
            if hasattr(ds, "rio"):
                try:
                    ds.rio.set_crs(dem_old.rio.crs)
                except Exception:
                    pass

    # Write using rioxarray
    try:
        dod_out.rio.to_raster(dod_path, dtype="float32", nodata=np.nan,
                              compress="LZW", tiled=True)
        mask_out.rio.to_raster(mask_path, dtype="int8", nodata=0,
                               compress="LZW", tiled=True)
    except Exception as e:
        logger.warning("rioxarray write failed, trying GDAL: %s", e)
        # Fallback: write via GDAL
        _write_array_via_gdal(dod, dod_path, "float32", dem_old)
        _write_array_via_gdal(mask.astype(np.int8), mask_path, "int8", dem_old)

    volume_report = {
        "cut_volume_m3": round(cut_volume, 1),
        "fill_volume_m3": round(fill_volume, 1),
        "net_volume_m3": round(net_volume, 1),
        "cell_area_m2": round(cell_area, 4),
        "propagated_error_m": round(propagated_error, 4),
        "lod_threshold_m": round(threshold, 4),
    }

    return {
        "dod_path": dod_path,
        "mask_path": mask_path,
        "volume_report": volume_report,
        "total_pixels": total_pixels,
        "significant_pixels": significant,
        "negative_change_pixels": neg_changes,
        "positive_change_pixels": pos_changes,
        "propagated_error": round(propagated_error, 4),
        "threshold": round(threshold, 4),
    }


def _write_array_via_gdal(
    data: "xr.DataArray",
    path: str,
    dtype: str,
    template: "xr.DataArray",
) -> None:
    """Fallback raster write using GDAL when rioxarray fails."""
    from osgeo import gdal

    rows, cols = data.shape
    gdal_dtype = gdal.GDT_Float32 if dtype == "float32" else gdal.GDT_Byte

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(
        path, cols, rows, 1, gdal_dtype,
        options=["COMPRESS=LZW", "TILED=YES"],
    )

    if hasattr(template, "rio"):
        ds.SetGeoTransform(template.rio.transform())
        ds.SetProjection(str(template.rio.crs))

    band = ds.GetRasterBand(1)
    values = data.values
    if np.issubdtype(values.dtype, np.floating):
        nan_mask = np.isnan(values)
        values = values.copy()
        values[nan_mask] = -9999.0
        band.SetNoDataValue(-9999.0)

    band.WriteArray(values)
    band.FlushCache()
    ds = None
