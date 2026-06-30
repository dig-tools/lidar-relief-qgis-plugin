#!/usr/bin/env python3
"""Guard: ensure CHANGELOG.md has an entry for the version in metadata.txt.

Exits 0 if CHANGELOG.md contains a `## [VERSION]` header that matches the
`version=` line in `metadata.txt`; exits 1 if not. Exits 2 if either input
file is missing or metadata.txt has no `version=` line.

This script is intentionally dependency-free (standard library only) so it
runs in any environment that can invoke Python — pre-commit hook, GitHub
Actions runner, or a manual `python3 scripts/check_changelog.py` invocation.

The QGIS plugin scanner reports lint findings and bandit's security score
on every published zip; preventing an accidental release without release
notes sidesteps the failure mode where plugins.qgis.org uploads succeed but
the GitHub Release page shows the auto-generated "Full Changelog" link with
no narrative behind it.

Usage:
    python3 scripts/check_changelog.py
    python3 scripts/check_changelog.py \\
        --metadata lidar_relief/metadata.txt \\
        --changelog CHANGELOG.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CHANGELOG_VERSION_HEADER = re.compile(
    # Match `## [VERSION]` (allows Lower-Level maybe `### [...])` if ever
    # needed; today only H2 is used). Optional ` - YYYY-MM-DD` suffix.
    r'^#{2,3}\s+\[(?P<version>[0-9]+(?:\.[0-9]+){0,3}'
    r'[A-Za-z0-9.\-]*)\]'
    r'(?:\s*-\s*\d{4}-\d{2}-\d{2})?\s*$',
    re.MULTILINE,
)

VERSION_LINE = re.compile(
    # Match a `version = ...` line in metadata.txt (INI-style key=value).
    r'^\s*version\s*=\s*(?P<version>[^\s#]+)\s*$',
    re.MULTILINE | re.IGNORECASE,
)

PLACEHOLDER_VERSIONS = frozenset({'unreleased', ''})


def read_metadata_version(metadata_path: Path) -> str:
    """Parse metadata.txt and return the value of the `version` key."""
    if not metadata_path.exists():
        print(
            f"::error ::metadata.txt not found at {metadata_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    text = metadata_path.read_text(encoding='utf-8', errors='replace')
    match = VERSION_LINE.search(text)
    if not match:
        print(
            f"::error ::No 'version=' line found in {metadata_path}",
            file=sys.stderr,
        )
        sys.exit(2)
    return match.group('version').strip()


def find_changelog_entry(changelog_path: Path, version: str) -> bool:
    """Return True if `## [version]` (or `### [version]`) appears."""
    if not changelog_path.exists():
        print(
            f"::error ::CHANGELOG.md not found at {changelog_path}",
            file=sys.stderr,
        )
        sys.exit(2)

    text = changelog_path.read_text(encoding='utf-8', errors='replace')
    target = version.lower()
    for header in CHANGELOG_VERSION_HEADER.finditer(text):
        if header.group('version').lower() == target:
            return True
    return False


def collect_changelog_versions(changelog_path: Path) -> list[str]:
    """All version strings declared in [bracketed headers], dedup'd."""
    if not changelog_path.exists():
        return []
    text = changelog_path.read_text(encoding='utf-8', errors='replace')
    return sorted(
        {m.group('version').strip() for m in CHANGELOG_VERSION_HEADER.finditer(text)},
        reverse=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Fail if CHANGELOG.md has no `## [<version>]` header for the '
            'version= declared in metadata.txt.'
        ),
    )
    parser.add_argument(
        '--metadata',
        type=Path,
        default=Path('lidar_relief/metadata.txt'),
        help=(
            'Path to QGIS plugin metadata.txt '
            '(default: ./lidar_relief/metadata.txt — matches '
            '"plugin_path: lidar_relief" in .qgis-plugin-ci).'
        ),
    )
    parser.add_argument(
        '--changelog',
        type=Path,
        default=Path('CHANGELOG.md'),
        help='Path to CHANGELOG.md (default: ./CHANGELOG.md).',
    )
    parser.add_argument(
        '--quiet',
        '-q',
        action='store_true',
        help='Suppress the success message; print only on failure.',
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    version = read_metadata_version(args.metadata).strip()

    if version.lower() in PLACEHOLDER_VERSIONS:
        print(
            f"::error ::suspicious 'version={version}' in {args.metadata}",
            file=sys.stderr,
        )
        return 2

    if find_changelog_entry(args.changelog, version):
        if not args.quiet:
            print(f"✓ CHANGELOG.md has `## [{version}]` entry.")
        return 0

    found = collect_changelog_versions(args.changelog)
    print(
        f"::error ::CHANGELOG.md is missing an entry for version {version!r}\n"
        f"  Expected header : `## [{version}]` (optional `- YYYY-MM-DD` suffix)\n"
        f"  Found versions  : {found or '[]'}\n\n"
        f"  To fix, add a section to CHANGELOG.md BEFORE tagging the release,\n"
        f"  and list at least one bullet under ### Fixed / ### Added / ### Changed:\n\n"
        f"      ## [{version}] - YYYY-MM-DD\n"
        f"      ### Fixed\n"
        f"      - one bullet describing the most important change.\n\n"
        f"  Notes for the GitHub Release page are generated automatically by\n"
        f"  `gh release create --generate-notes`, but plugins.qgis.org only\n"
        f"  shows the metadata.txt `changelog` URL fragment; without an\n"
        f"  entry here users will see no release notes on either the GitHub\n"
        f"  or the QGIS plugin pages.",
        file=sys.stderr,
    )
    return 1


if __name__ == '__main__':
    sys.exit(main())
