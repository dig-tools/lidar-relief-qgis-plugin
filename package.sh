#!/bin/bash
set -e

# Extract version from metadata.txt
VERSION=$(grep '^version=' lidar_relief/metadata.txt | cut -d'=' -f2)

# Sanity check: ensure metadata.txt version matches the top entry of
# CHANGELOG.md. The two have drifted in the past, causing users to see
# the wrong changelog when installing a new version.
CHANGELOG_TOP=$(grep -E '^##\s+\[' CHANGELOG.md | head -1 | sed -E 's/^## \[([0-9.]+)\].*$/\1/')
if [ -n "$CHANGELOG_TOP" ] && [ "$CHANGELOG_TOP" != "$VERSION" ]; then
    echo "ERROR: metadata.txt version ($VERSION) does not match top CHANGELOG.md entry ($CHANGELOG_TOP)"
    echo "Please update both files to the same version before packaging."
    exit 1
fi

ZIP_NAME="lidar_relief_v${VERSION}.zip"

echo "Packaging LiDAR Relief Visualization Plugin v${VERSION}..."

# Remove old zip if it exists
if [ -f "$ZIP_NAME" ]; then
    rm "$ZIP_NAME"
fi

# Copy documentation into the plugin folder for packaging.
# Use a trap to guarantee cleanup runs even if zip fails (set -e would
# otherwise leave these stray files in the working tree, where they
# could be accidentally committed).
cp CHANGELOG.md lidar_relief/
# USER_GUIDE.md is optional — only copy if it exists.
if [ -f docs/USER_GUIDE.md ]; then
    cp docs/USER_GUIDE.md lidar_relief/
elif [ -f USER_GUIDE.md ]; then
    cp USER_GUIDE.md lidar_relief/
fi

trap 'rm -f lidar_relief/CHANGELOG.md lidar_relief/USER_GUIDE.md' EXIT

# Zip the plugin folder, excluding tests, pycache, hidden files, etc.
zip -r "$ZIP_NAME" lidar_relief/ \
    -x "lidar_relief/tests/*" \
    -x "lidar_relief/tests" \
    -x "*/__pycache__/*" \
    -x "*/.pytest_cache/*" \
    -x "*/.*" \
    -x "*.pyc"

# Disable the trap before manual cleanup so it doesn't run twice.
trap - EXIT
rm -f lidar_relief/CHANGELOG.md lidar_relief/USER_GUIDE.md

echo ""
echo "Successfully created $ZIP_NAME!"
echo "This file can be uploaded to the QGIS Plugin Repository or attached to a GitHub Release."
