# LiDAR Relief Visualization Plugin

A QGIS Processing plugin for advanced archaeological terrain visualization from Digital Elevation Models (DEMs). This toolset provides mathematically robust, pure-NumPy implementations of the most critical LiDAR visualizations used in archaeological prospecting.

## Features

This plugin integrates directly into the QGIS Processing Toolbox and provides the following algorithms:

- **Multi-directional Hillshade**: Blends multiple illumination angles to eliminate the directional bias of traditional single-light-source hillshades.
- **Simple Local Relief Model (SLRM)**: Removes macro-topography (large hills and slopes) to isolate micro-relief features like ancient ditches, walls, and mounds.
- **Sky-View Factor (SVF)**: Computes the proportion of the sky visible from each pixel. Concave features (pits, ditches) appear dark, while convex features (ridges, mounds) appear bright.
- **Topographic Openness (Positive/Negative)**: Measures the zenith or nadir angle of the horizon. Positive Openness highlights convex features; Negative Openness highlights concave features.
- **Multi-Scale Topographic Position (MSTP)**: Calculates Deviation from Mean Elevation (DEV) across three spatial scales (Broad, Meso, Local) and maps them to an RGB false-color image for holistic terrain interpretation.
- **Batch Relief Visualisation**: A convenience tool that reads a DEM once and runs multiple enabled visualizations simultaneously.
- **Blend Visualizations**: Replicates Photoshop-style blending (Multiply, Screen, Overlay) to combine two layers (e.g., SVF + Hillshade) into a single composite raster.

## Installation

### Method 1: Install from ZIP (Recommended for Users)
1. Navigate to the **[Releases](https://github.com/mabo-du/lidar-relief-qgis-plugin/releases)** page (or GitLab equivalent).
2. Download the latest `lidar_relief.zip` file (or similarly named asset).
3. Open QGIS.
4. Go to **Plugins → Manage and Install Plugins...** from the top menu.
5. Select the **Install from ZIP** tab on the left.
6. Browse for the downloaded zip file and click **Install Plugin**.
6. The algorithms will now be available in your **Processing Toolbox** (gear icon) under the `LiDAR Relief` group.

### Method 2: Manual Installation (For Developers)
Copy or symlink the `lidar_relief` directory into your QGIS plugins folder:
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

## Architecture

The plugin is designed with a strict separation between QGIS UI bindings and the mathematical core:
- **`core/`**: Pure NumPy/GDAL algorithms. Designed to run headless and be fully testable without a QGIS instance. Uses an integral image approach for $O(1)$ multi-scale computations.
- **`algorithms/`**: Thin `QgsProcessingAlgorithm` wrappers that connect QGIS user inputs and feedback mechanisms to the core processing engine.

All raster I/O uses optimized GDAL chunking (`process_in_tiles`) to process massive DEMs without exhausting system memory.

## License

This project is licensed under the MIT License.
