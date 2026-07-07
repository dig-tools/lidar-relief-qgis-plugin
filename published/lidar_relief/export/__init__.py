"""export/__init__.py — Export pipeline for LiDAR Relief plugin.

This package provides output pipeline components for transforming algorithm
results into shareable, publishable formats.

Modules:
    cog_exporter: Convert GeoTIFF → Cloud-Optimized GeoTIFF
    web_viewer: Generate interactive MapLibre GL JS HTML viewer
    field_packager: Package rasters + anomaly data for QField/Mergin
    report_generator: Generate CIfA-compliant PDF reports

Rules:
    All export modules have optional dependencies with graceful fallbacks.
    All export modules follow the same pattern:
        check_dependencies() -> bool
        export(input_path, output_path, **kwargs) -> dict
"""
