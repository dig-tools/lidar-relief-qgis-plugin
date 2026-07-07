"""core/__init__.py — Core algorithm package for LiDAR Relief Visualization.
exports: (submodules: hillshade, slrm, svf, slope, raster_utils)
used_by: algorithms/*.py → core function imports
rules:
  All modules in this package must be pure NumPy/GDAL — no QGIS imports.
  This ensures algorithms are testable without a running QGIS instance.
"""
