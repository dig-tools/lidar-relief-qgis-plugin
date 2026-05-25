#!/bin/bash
set -e

echo "=== Running Code Formatter (ruff) ==="
python3 -m ruff format lidar_relief/

echo "=== Running Linter (ruff) ==="
python3 -m ruff check --fix lidar_relief/

echo "=== Running Unit Tests (pytest) ==="
python3 -m pytest lidar_relief/tests/

echo "✅ All tests and linting passed successfully!"
