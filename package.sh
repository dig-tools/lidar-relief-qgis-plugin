#!/bin/bash
set -e

# Extract version from metadata.txt
VERSION=$(grep '^version=' lidar_relief/metadata.txt | cut -d'=' -f2)

ZIP_NAME="lidar_relief_v${VERSION}.zip"

echo "Packaging LiDAR Relief Visualization Plugin v${VERSION}..."

# Remove old zip if it exists
if [ -f "$ZIP_NAME" ]; then
    rm "$ZIP_NAME"
fi

# Copy documentation into the plugin folder for packaging
cp CHANGELOG.md lidar_relief/
cp docs/USER_GUIDE.md lidar_relief/

# Zip the plugin folder, excluding tests, pycache, hidden files, etc.
zip -r "$ZIP_NAME" lidar_relief/ \
    -x "lidar_relief/tests/*" \
    -x "lidar_relief/tests" \
    -x "*/__pycache__/*" \
    -x "*/.pytest_cache/*" \
    -x "*/.*" \
    -x "*.pyc"

# Clean up copied files
rm lidar_relief/CHANGELOG.md
rm lidar_relief/USER_GUIDE.md

echo ""
echo "Successfully created $ZIP_NAME!"
echo "This file can be uploaded to the QGIS Plugin Repository or attached to a GitHub Release."
