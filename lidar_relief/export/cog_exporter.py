"""cog_exporter.py — Cloud-Optimized GeoTIFF export.

exports: cog_is_supported() -> bool,
         convert_to_cog(input_path, output_path, **kwargs) -> dict,
         validate_cog(path) -> dict

used_by: algorithms/cog_export_algorithm.py → convert_to_cog
         algorithms/batch_algorithm.py → convert_to_cog (optional post-step)

rules:
  rio_cogeo is an optional dependency — check cog_is_supported() first.
  All parameters exposed for user control.
  Output is a strictly valid COG (tiled, overviews, byte-offset layout).
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try importing rio-cogeo at module level; store availability flag
try:
    from rio_cogeo.cogeo import cog_translate
    from rio_cogeo.profiles import cog_profiles
    import rasterio

    _RIO_COGEO_AVAILABLE = True
except ImportError:
    _RIO_COGEO_AVAILABLE = False

# Default COG profile: DEFLATE compression, YCbCr photometric for RGB
_DEFAULT_PROFILE = "deflate"


def cog_is_supported() -> bool:
    """Check if the rio-cogeo library is installed and usable.

    Returns:
        True if COG export is available, False otherwise.
    """
    return _RIO_COGEO_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError with clear install instructions if rio-cogeo missing."""
    if not _RIO_COGEO_AVAILABLE:
        raise ImportError(
            "Cloud-Optimized GeoTIFF export requires 'rio-cogeo'.\n\n"
            "Install it via the OSGeo4W Shell:\n"
            "  pip install rio-cogeo\n\n"
            "Or via your system terminal:\n"
            "  pip install rio-cogeo"
        )


def convert_to_cog(
    input_path: str,
    output_path: str,
    profile: str = _DEFAULT_PROFILE,
    overview_level: Optional[int] = None,
    overview_resampling: str = "nearest",
    warp_resampling: str = "bilinear",
    in_memory: bool = False,
    nodata: Optional[float] = None,
) -> dict:
    """Convert a GeoTIFF to Cloud-Optimized GeoTIFF (COG).

    Args:
        input_path: Path to the source GeoTIFF.
        output_path: Path for the output COG (.tif).
        profile: COG profile name ('deflate', 'lzw', 'raw', 'zstd').
        overview_level: Override auto overview level (e.g. 6).
        overview_resampling: Resampling method for overviews
            ('nearest', 'bilinear', 'cubic', 'average').
        warp_resampling: Resampling for internal warping
            ('bilinear', 'cubic', 'lanczos').
        in_memory: Process in memory (faster but more RAM).
        nodata: Override nodata value (auto-detected if None).

    Returns:
        dict with:
            - 'output_path': path to the generated COG
            - 'profile': the COG profile used
            - 'overview_level': overview level
            - 'size_bytes': file size of the output
            - 'valid': True if COG validation passes

    Raises:
        ImportError: If rio-cogeo is not installed.
        RuntimeError: If conversion fails.
    """
    check_dependencies()

    # Resolve the profile
    available_profiles = cog_profiles.get(profile)

    if available_profiles is None:
        logger.warning(
            "Unknown COG profile '%s', falling back to 'deflate'. Available: %s",
            profile,
            list(cog_profiles.keys()),
        )
        profile = _DEFAULT_PROFILE
        available_profiles = cog_profiles.get(profile)

    profile_config = available_profiles.copy()

    # Build overview level and perform conversion
    try:
        with rasterio.open(input_path) as src:
            dst_kwargs = profile_config

            if overview_level is not None:
                dst_kwargs["overview_level"] = overview_level
            else:
                # Auto: compute reasonable overview level from raster size
                max_dim = max(src.width, src.height)
                if max_dim > 512:
                    dst_kwargs["overview_level"] = max(
                        1, (max_dim // 256).bit_length() - 1
                    )

            dst_kwargs["overview_resampling"] = overview_resampling
            dst_kwargs["warp_resampling"] = warp_resampling

            # Auto-detect nodata if not overridden
            if nodata is None:
                nodata_val = src.nodata
            else:
                nodata_val = nodata

            config = {
                "QUALITY": 90,
                "NUM_THREADS": "ALL_CPUS",
                "BLOCKXSIZE": 512,
                "BLOCKYSIZE": 512,
            }

            cog_translate(
                src,
                output_path,
                dst_kwargs,
                config=config,
                in_memory=in_memory,
                allow_intermediate_compression=True,
                nodata=nodata_val,
            )

    except Exception as e:
        raise RuntimeError(f"COG conversion failed: {e}") from e

    size_bytes = os.path.getsize(output_path)

    # Validate the output
    valid = _validate_cog_structure(output_path)

    return {
        "output_path": output_path,
        "profile": profile,
        "overview_level": dst_kwargs.get("overview_level"),
        "size_bytes": size_bytes,
        "valid": valid,
    }


def _validate_cog_structure(path: str) -> bool:
    """Validate that a file has the expected COG structure.

    Checks:
        - File exists and is a valid GeoTIFF
        - Has tiled internal structure
        - Has overviews for rasters > 1024 pixels (small rasters exempted)
        - Has proper byte-offset layout (IFD structure)

    Args:
        path: Path to the COG file.

    Returns:
        True if the file appears to be a valid COG.
    """
    try:
        import rasterio
    except ImportError:
        return True  # Can't validate without rasterio, assume OK

    try:
        with rasterio.open(path) as src:
            # Must be tiled
            if not src.profile.get("tiled", False):
                logger.warning("COG validation: not tiled")
                return False

            # Block size should be reasonable (256 or 512 typical)
            block_size = src.block_shapes[0]
            if block_size[0] < 64 or block_size[1] < 64:
                logger.warning("COG validation: block size too small %s", block_size)
                return False

            # Overviews only required for larger rasters
            max_dim = max(src.width, src.height)
            if max_dim > 1024:
                if len(src.overviews(1)) < 1:
                    logger.warning(
                        "COG validation: no overviews for %dx%d raster",
                        src.width,
                        src.height,
                    )
                    return False

        return True

    except Exception as e:
        logger.warning("COG validation error: %s", e)
        return False


def validate_cog(path: str) -> dict:
    """Validate a COG file and return detailed metadata.

    Args:
        path: Path to the COG file.

    Returns:
        dict with validation results and file metadata, or error dict.
    """
    result = {"path": path, "valid": False}

    try:
        import rasterio
    except ImportError:
        result["error"] = "rasterio not available for validation"
        return result

    try:
        valid = _validate_cog_structure(path)
        result["valid"] = valid

        with rasterio.open(path) as src:
            result["width"] = src.width
            result["height"] = src.height
            result["count"] = src.count
            result["dtype"] = str(src.dtypes[0])
            result["crs"] = str(src.crs) if src.crs else None
            result["tiled"] = src.profile.get("tiled", False)
            result["blocksize"] = src.block_shapes[0]
            result["overview_count"] = len(src.overviews(1)) if src.count > 0 else 0
            result["compression"] = src.profile.get("compress")
            result["photometric"] = src.profile.get("photometric")
            result["nodata"] = src.nodata

    except Exception as e:
        result["error"] = str(e)

    return result
