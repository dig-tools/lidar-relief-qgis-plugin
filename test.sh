#!/bin/bash
set -e

echo "=== Installing Optional Test Dependencies ==="
pip install rio-cogeo reportlab xarray rioxarray onnxruntime onnx 2>/dev/null || true
pip install cloth-simulation-filter 2>/dev/null || true

echo "=== Running Code Formatter (ruff --check, read-only) ==="
# Use --check instead of auto-format so test.sh never modifies tracked files
# in CI. Auto-modification is what triggered the v2.0.11 publish failure —
# `ruff format`'s default style places binary operators at line start (W503
# violation per the QGIS plugin scanner's flake8 strict profile), which
# reintroduces the very lint findings we removed. Drift is logged as a
# warning but does not block CI; run `ruff format lidar_relief/` locally
# before committing if you want autofix.
python3 -m ruff format lidar_relief/ --check || echo "(format drift detected; informational only)"

echo "=== Running Linter (ruff check, no --fix) ==="
# Also read-only: no --fix so test.sh never auto-mutates tracked files.
# Findings here are informational only — the actual lint gate for the
# QGIS plugin scanner is `flake8 --isolated --select=W503,E402,E203`,
# which is run separately. Ruff's default rule set (E/F line) reports
# style opinions that the scanner doesn't enforce; surfacing them as
# warnings without blocking CI keeps the developer experience alive
# without risking the publish pipeline.
python3 -m ruff check lidar_relief/ || echo "(ruff check findings reported; informational only)"

echo "=== Running Comprehensive Linter (flake8 --isolated, mirrors QGIS scanner profile) ==="
# Mirrors plugins.qgis.org scanner exactly: enable W504 (line break AFTER
# binary operator) and explicitly ignore cosmetic visual-indent rules
# (#E117 over-indented, #E128 under-indented continuation, #E124 closing
# bracket mismatch, #E201 whitespace after '(') that the scanner does
# NOT enforce but default flake8 does. Net effect: CI failure mirrors
# scanner failure on the rules the scanner actually checks.
python3 -m flake8 --isolated --max-line-length=200     --extend-select=W504 --extend-ignore=E117,E128,E124,E201     lidar_relief/

echo "=== Running Unit Tests (pytest) ==="
python3 -m pytest lidar_relief/tests/ -v --tb=short

echo "=== Verifying CHANGELOG.md covers metadata.txt version ==="
# Local-dev safety net for the same guard CI runs in release.yml.  When this
# fails, the offending metadata.txt bump needs a matching `## [<version>]`
# header in CHANGELOG.md before tagging the release.  Pre-commit hook
# (.pre-commit-config.yaml) catches this on `git commit` too — this is
# belt-and-suspenders for devs who run `./test.sh` directly without
# `pre-commit install`.
python3 scripts/check_changelog.py

echo "✅ All tests and linting passed successfully!"
