"""sentinel_fusion.py — Multi-sensor fusion: LiDAR relief + Sentinel-2 multispectral.

exports: fusion_available() -> bool,
         co_register_bands(lidar_path, s2_stack_path, output_path, **kwargs) -> dict,
         apply_fusion_recipe(lidar_path, s2_paths, recipe_name, output_path, **kwargs) -> dict,
         FUSION_RECIPES

used_by: algorithms/fusion_algorithm.py

rules:
  All dependencies (rasterio, rioxarray) are optional — check availability.
  Fusion recipes combine LiDAR topographic layers with spectral bands.
  Co-registration uses rioxarray.reproject_match for pixel-perfect alignment.
"""

import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import rasterio
    from rasterio.enums import Resampling
    import rioxarray
    import xarray as xr

    _FUSION_AVAILABLE = True
except ImportError:
    _FUSION_AVAILABLE = False

# Sentinel-2 band designations
SENTINEL2_BANDS = {
    "B2": {"desc": "Blue", "resolution": 10, "center_nm": 490},
    "B3": {"desc": "Green", "resolution": 10, "center_nm": 560},
    "B4": {"desc": "Red", "resolution": 10, "center_nm": 665},
    "B5": {"desc": "Vegetation Red Edge", "resolution": 20, "center_nm": 705},
    "B6": {"desc": "Vegetation Red Edge", "resolution": 20, "center_nm": 740},
    "B7": {"desc": "Vegetation Red Edge", "resolution": 20, "center_nm": 783},
    "B8": {"desc": "NIR", "resolution": 10, "center_nm": 842},
    "B8A": {"desc": "Narrow NIR", "resolution": 20, "center_nm": 865},
    "B11": {"desc": "SWIR 1", "resolution": 20, "center_nm": 1610},
    "B12": {"desc": "SWIR 2", "resolution": 20, "center_nm": 2190},
}

# Pre-defined LiDAR + Multispectral fusion recipes
# Each recipe defines:
#   - lidar_layer: the LiDAR algorithm to use as base
#   - bands: Sentinel-2 bands to fetch
#   - blend: how to combine them
#   - description: usage context
FUSION_RECIPES = {
    "terrain_cir": {
        "name": "Terrain + Colour Infrared",
        "description": "SVF hillshade as luminance base, overlaid with "
        "Sentinel-2 CIR (B8,NIR,B4) colour. Ideal for simultaneous "
        "topographic and vegetation analysis.",
        "lidar_layer": "svf",
        "s2_bands": ["B8", "B4", "B3"],
        "blend_mode": "luminance_overlay",
        "lidar_opacity": 0.6,
    },
    "crop_marks": {
        "name": "Crop Mark Enhancement",
        "description": "Local Dominance (concavity detection) blended "
        "with true-colour Sentinel-2 at 50% opacity. Reveals buried "
        "features expressed as crop marks.",
        "lidar_layer": "local_dominance",
        "s2_bands": ["B4", "B3", "B2"],
        "blend_mode": "overlay",
        "lidar_opacity": 0.5,
    },
    "erosion_risk": {
        "name": "Erosion Risk Mapping",
        "description": "Slope overlaid on SWIR bands for simultaneous "
        "topographic and soil moisture analysis.",
        "lidar_layer": "slope",
        "s2_bands": ["B11", "B8", "B4"],
        "blend_mode": "multiply",
        "lidar_opacity": 0.7,
    },
    "bare_earth": {
        "name": "Bare Earth Composite",
        "description": "SLRM micro-relief with shortwave infrared for "
        "vegetation-free archaeological prospection.",
        "lidar_layer": "slrm",
        "s2_bands": ["B11", "B12", "B4"],
        "blend_mode": "screen",
        "lidar_opacity": 0.5,
    },
}


def fusion_available() -> bool:
    """Check if rasterio/rioxarray are installed."""
    return _FUSION_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError if fusion libraries missing."""
    if not _FUSION_AVAILABLE:
        raise ImportError(
            "Multi-sensor fusion requires 'rasterio' and 'rioxarray'.\n\n"
            "Install via OSGeo4W Shell:\n"
            "  pip install rasterio rioxarray"
        )


def co_register_bands(
    reference_path: str,
    target_path: str,
    output_path: str,
    resampling: str = "bilinear",
) -> dict:
    """Co-register a target raster to match a reference raster's grid.

    Args:
        reference_path: Path to the reference raster (e.g. LiDAR relief).
        target_path: Path to the target raster (e.g. Sentinel-2 band).
        output_path: Path for the co-registered output.
        resampling: Resampling method ('bilinear', 'cubic', 'nearest').

    Returns:
        dict with output metadata.
    """
    check_dependencies()

    resampling_map = {
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
        "nearest": Resampling.nearest,
        "lanczos": Resampling.lanczos,
        "average": Resampling.average,
    }
    resampler = resampling_map.get(resampling, Resampling.bilinear)

    ref = rioxarray.open_rasterio(reference_path)
    target = rioxarray.open_rasterio(target_path)

    # Reproject match
    aligned = target.rio.reproject_match(ref, resampling=resampler)

    # Write output
    aligned.rio.to_raster(
        output_path,
        compress="LZW",
        tiled=True,
        dtype=aligned.dtype,
    )

    return {
        "output_path": output_path,
        "width": aligned.sizes.get("x", 0),
        "height": aligned.sizes.get("y", 0),
        "crs": str(aligned.rio.crs) if hasattr(aligned, "rio") else None,
    }


def _normalize(array: np.ndarray) -> np.ndarray:
    """Normalize an array to 0.0–1.0 range for blending."""
    arr = array.astype(np.float64)
    min_val = np.nanmin(arr)
    max_val = np.nanmax(arr)
    if max_val - min_val > 1e-10:
        return (arr - min_val) / (max_val - min_val)
    return np.zeros_like(arr)


def _luminance_overlay(
    lidar: np.ndarray, s2_rgb: np.ndarray, lidar_opacity: float
) -> np.ndarray:
    """Use LiDAR as luminance base, S2 bands as colour overlay.

    Result = lidar_as_grey * (1 - opacity) + lidar_as_grey * s2_rgb * opacity
    """
    lidar_norm = _normalize(lidar)
    # Stack luminance into 3 channels
    lidar_3ch = np.stack([lidar_norm] * 3, axis=-1)
    s2_norm = np.zeros_like(lidar_3ch)
    for b in range(min(s2_rgb.shape[-1], 3)):
        s2_norm[:, :, b] = _normalize(s2_rgb[:, :, b])

    blended = lidar_3ch * (1 - lidar_opacity) + lidar_3ch * s2_norm * lidar_opacity
    return np.clip(blended * 255, 0, 255).astype(np.uint8)


def _overlay_blend(
    lidar: np.ndarray, s2_rgb: np.ndarray, lidar_opacity: float
) -> np.ndarray:
    """Overlay blend: darker areas from lidar darken S2."""
    lidar_norm = _normalize(lidar)
    lidar_3ch = np.stack([lidar_norm] * 3, axis=-1)
    s2_norm = np.zeros_like(lidar_3ch)
    for b in range(min(s2_rgb.shape[-1], 3)):
        s2_norm[:, :, b] = _normalize(s2_rgb[:, :, b])

    # Overlay: 2*base*active if base < 0.5, else 1 - 2*(1-base)*(1-active)
    overlay = np.where(
        lidar_3ch < 0.5,
        2 * lidar_3ch * s2_norm,
        1 - 2 * (1 - lidar_3ch) * (1 - s2_norm),
    )
    blended = (1 - lidar_opacity) * s2_norm + lidar_opacity * overlay
    return np.clip(blended * 255, 0, 255).astype(np.uint8)


def _multiply_blend(
    lidar: np.ndarray, s2_rgb: np.ndarray, lidar_opacity: float
) -> np.ndarray:
    """Multiply blend: lidar darkens S2 proportionally."""
    lidar_norm = _normalize(lidar)
    lidar_3ch = np.stack([lidar_norm] * 3, axis=-1)
    s2_norm = np.zeros_like(lidar_3ch)
    for b in range(min(s2_rgb.shape[-1], 3)):
        s2_norm[:, :, b] = _normalize(s2_rgb[:, :, b])

    multiplied = lidar_3ch * s2_norm
    blended = (1 - lidar_opacity) * s2_norm + lidar_opacity * multiplied
    return np.clip(blended * 255, 0, 255).astype(np.uint8)


def _screen_blend(
    lidar: np.ndarray, s2_rgb: np.ndarray, lidar_opacity: float
) -> np.ndarray:
    """Screen blend: lidar lightens S2 proportionally."""
    lidar_norm = _normalize(lidar)
    lidar_3ch = np.stack([lidar_norm] * 3, axis=-1)
    s2_norm = np.zeros_like(lidar_3ch)
    for b in range(min(s2_rgb.shape[-1], 3)):
        s2_norm[:, :, b] = _normalize(s2_rgb[:, :, b])

    screened = 1 - (1 - lidar_3ch) * (1 - s2_norm)
    blended = (1 - lidar_opacity) * s2_norm + lidar_opacity * screened
    return np.clip(blended * 255, 0, 255).astype(np.uint8)


BLEND_FUNCTIONS = {
    "luminance_overlay": _luminance_overlay,
    "overlay": _overlay_blend,
    "multiply": _multiply_blend,
    "screen": _screen_blend,
}


def apply_fusion_recipe(
    lidar_path: str,
    s2_paths: dict[str, str],
    recipe_name: str,
    output_path: str,
    lidar_opacity: Optional[float] = None,
) -> dict:
    """Apply a fusion recipe to combine LiDAR relief with Sentinel-2 bands.

    Args:
        lidar_path: Path to the LiDAR relief raster (single band).
        s2_paths: Dict mapping band name (e.g. 'B4') to file path.
        recipe_name: Name of the recipe from FUSION_RECIPES.
        output_path: Path for the output RGB fusion raster.
        lidar_opacity: Override recipe's default opacity.

    Returns:
        dict with output metadata.
    """
    check_dependencies()

    if recipe_name not in FUSION_RECIPES:
        raise ValueError(
            f"Unknown fusion recipe '{recipe_name}'. "
            f"Available: {list(FUSION_RECIPES.keys())}"
        )

    recipe = FUSION_RECIPES[recipe_name]
    opacity = lidar_opacity if lidar_opacity is not None else recipe["lidar_opacity"]
    blend_mode = recipe["blend_mode"]
    required_bands = recipe["s2_bands"]

    # Load LiDAR layer
    lidar_da = rioxarray.open_rasterio(lidar_path)
    if "band" in lidar_da.dims:
        lidar_da = lidar_da.squeeze("band")

    lidar_array = lidar_da.values.astype(np.float64)

    # Load and co-register S2 bands
    s2_arrays = []
    for band in required_bands:
        if band not in s2_paths:
            raise ValueError(
                f"Missing band {band} required for recipe '{recipe_name}'. "
                f"Provided: {list(s2_paths.keys())}"
            )
        band_da = rioxarray.open_rasterio(s2_paths[band])
        if "band" in band_da.dims:
            band_da = band_da.squeeze("band")
        # Align to LiDAR grid
        band_aligned = band_da.rio.reproject_match(
            lidar_da, resampling=Resampling.bilinear
        )
        s2_arrays.append(band_aligned.values.astype(np.float64))

    s2_stack = np.dstack(s2_arrays) if len(s2_arrays) > 1 else s2_arrays[0][:, :, np.newaxis]

    # Apply blend
    blend_fn = BLEND_FUNCTIONS.get(blend_mode)
    if blend_fn is None:
        raise ValueError(
            f"Unknown blend mode '{blend_mode}'. "
            f"Available: {list(BLEND_FUNCTIONS.keys())}"
        )

    result = blend_fn(lidar_array, s2_stack, opacity)

    # Write output using LiDAR's geotransform
    _write_rgb_raster(
        result,
        output_path,
        crs=str(lidar_da.rio.crs) if hasattr(lidar_da, 'rio') else None,
        transform=lidar_da.rio.transform() if hasattr(lidar_da, 'rio') else None,
    )

    return {
        "output_path": output_path,
        "recipe": recipe_name,
        "blend_mode": blend_mode,
        "lidar_opacity": opacity,
        "bands_used": required_bands,
    }


def _write_rgb_raster(
    rgb: np.ndarray,
    path: str,
    crs: Optional[str] = None,
    transform: Optional[tuple] = None,
) -> None:
    """Write a 3-band uint8 RGB array to GeoTIFF."""
    from osgeo import gdal

    rows, cols, bands = rgb.shape
    ds = gdal.GetDriverByName("GTiff").Create(
        path, cols, rows, bands, gdal.GDT_Byte,
        options=["COMPRESS=LZW", "TILED=YES", "PHOTOMETRIC=RGB"],
    )

    if transform is not None:
        # Handle both Affine objects and 6-element tuples
        try:
            # Affine has to_gdal() method
            gt = transform.to_gdal()
        except AttributeError:
            # Already a sequence
            if len(transform) >= 6:
                gt = transform[:6]
            else:
                gt = transform
        ds.SetGeoTransform(gt)
    if crs:
        ds.SetProjection(str(crs))

    for b in range(bands):
        band = ds.GetRasterBand(b + 1)
        band.WriteArray(rgb[:, :, b])

    ds.FlushCache()
    ds = None
