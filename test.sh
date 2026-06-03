#!/bin/bash
set -e

echo "=== Installing Optional Test Dependencies ==="
pip install rio-cogeo reportlab xarray rioxarray onnxruntime onnx 2>/dev/null || true
pip install cloth-simulation-filter 2>/dev/null || true

echo "=== Running Code Formatter (ruff) ==="
python3 -m ruff format lidar_relief/ --quiet

echo "=== Running Linter (ruff) ==="
python3 -m ruff check --fix lidar_relief/ --quiet

echo "=== Running Unit Tests (pytest) ==="
python3 -m pytest lidar_relief/tests/ -v --tb=short

echo "✅ All tests and linting passed successfully!"
