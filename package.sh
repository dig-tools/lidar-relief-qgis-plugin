#!/bin/bash
# package.sh — Build a properly structured QGIS plugin zip for local testing/release.
#
# QGIS REQUIRES the zip to contain a single top-level folder named after
# the plugin package (lidar_relief/). Without it, QGIS refuses to install.
#
# Usage: ./package.sh [version]
#   e.g. ./package.sh 1.3.3
#
# If no version is given it reads from metadata.txt automatically.

set -e

PLUGIN_DIR="lidar_relief"

# Read version from metadata.txt if not given as argument
if [ -z "$1" ]; then
    VERSION=$(grep "^version=" "${PLUGIN_DIR}/metadata.txt" | cut -d'=' -f2 | tr -d '[:space:]')
    echo "No version argument given — using version from metadata.txt: $VERSION"
else
    VERSION="$1"
fi

OUTPUT="lidar_relief_plugin_v${VERSION}.zip"

echo "Packaging ${OUTPUT}..."

# Remove any old version of this zip
rm -f "${OUTPUT}"

# Build the zip — lidar_relief/ is the top-level folder inside the archive.
# Excludes: test files, pycache, compiled Python, editor dirs, OS junk.
zip -r "${OUTPUT}" "${PLUGIN_DIR}/" \
    --exclude "*/tests/*" \
    --exclude "*/__pycache__/*" \
    --exclude "*.pyc" \
    --exclude "*.pyo" \
    --exclude "*/.DS_Store" \
    --exclude "*/.idea/*" \
    --exclude "*/.vscode/*"

echo ""
echo "✅ Done: ${OUTPUT}"
echo ""
echo "Verifying top-level structure:"
unzip -l "${OUTPUT}" | head -10
