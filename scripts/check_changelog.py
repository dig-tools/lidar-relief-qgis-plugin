#!/usr/bin/env python3
"""Guard: ensure both CHANGELOG.md AND metadata.txt's changelog= block cover
the version declared in metadata.txt.

Exits 0 if both targets cover the current `version=`; exits 1 if either is
missing an entry. Exits 2 if metadata.txt itself is missing or has no
`version=` line.

This script is intentionally dependency-free (standard library only) so it
runs in any environment that can invoke Python — pre-commit hook, GitHub
Actions runner, or a manual `python3 scripts/check_changelog.py` invocation.

Two separate checks are enforced:

1. `CHANGELOG.md` has a `## [<version>]` header line (plus ideally bullets
   under it). This is the long-form narrative used by GitHub Releases.
2. `lidar_relief/metadata.txt` has a `    <version> - <title>` line inside
   the multi-line `changelog=` block. QGIS-Django auto-populates the
   plugins.qgis.org upload form's "Changes" textarea from this block, so
   if this block is stale the new release-notes are silently overridden on
   every upload — pasting text into the upload page appears to "not stick".

Without check (2) the plugin could pass the original CHANGELOG.md-only
guard and still ship without the user-facing release notes that led to the
upload discrepancy in the first place.

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
    # Match `## [VERSION]` (allows `### [...]` if ever needed). Optional
    # ` - YYYY-MM-DD` suffix.
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

# Strict match for the `changelog=` key. Note the trailing `=` in the regex;
# this deliberately does NOT match `changelog_url=` (a separate QGIS metadata
# field). Without this anchor the new `changelog_url=` line added in v2.0.16
# would be parsed as the start of the changelog block and produce false
# positives.
METADATA_CHANGELOG_KEY = re.compile(
    r'^changelog\s*=(?P<head>.*)$',
    re.MULTILINE,
)

# Match `<indent><version> - <title>` inside a metadata.txt changelog block.
# Leading digits (not `-`) so `- Sub-bullet: ...` lines are not mistaken for
# version entries. Indent can be spaces or tabs.
METADATA_CHANGELOG_ENTRY = re.compile(
    r'^[ \t]+(?P<version>[0-9]+(?:\.[0-9]+){0,3}[A-Za-z0-9.\-]*)\s+-.*$',
    re.MULTILINE,
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


def extract_metadata_changelog_block(metadata_text: str) -> str | None:
    """Return the multi-line `changelog=` value, or None if absent.

    QGIS metadata.txt supports keys whose value spans multiple lines as long
    as each continuation line is indented. The block ends on the first
    non-indented, non-empty line (next top-level key, section header, or
    EOF). Returns ``None`` when no `changelog=` key is present at all, and an
    empty string when the key exists but the value is empty.
    """
    lines = metadata_text.splitlines()
    start_index: int | None = None
    head_value = ''
    for i, line in enumerate(lines):
        m = METADATA_CHANGELOG_KEY.match(line)
        if m:
            start_index = i
            head_value = m.group('head').strip()
            break
    if start_index is None:
        return None

    block_lines: list[str] = []
    if head_value:
        block_lines.append(head_value)
    for cont in lines[start_index + 1:]:
        if not cont.strip():
            # Blank-line separators between version entries — tolerated by
            # QGIS' metadata parser, so we preserve them in the block and
            # do not terminate.
            block_lines.append(cont)
            continue
        if cont[:1].isspace():
            # Continuation line: starts with a space or tab.
            block_lines.append(cont)
            continue
        # First non-indented, non-empty line: end of block.
        break
    return '\n'.join(block_lines)


def find_metadata_changelog_entry(metadata_path: Path, version: str) -> bool:
    """Return True if `metadata.txt`'s changelog= block contains `<version>`.

    Matches the indented `    <version> - <title>` line. Returns ``False``
    cleanly when the key is absent, has an empty value, or has no matching
    version entry — the caller is responsible for distinguishing those
    failure modes for the user-facing error message.
    """
    if not metadata_path.exists():
        return False  # missing file is reported by read_metadata_version()
    text = metadata_path.read_text(encoding='utf-8', errors='replace')
    block = extract_metadata_changelog_block(text)
    if block is None:
        return False
    target = version.lower()
    for header in METADATA_CHANGELOG_ENTRY.finditer(block):
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


def collect_metadata_changelog_versions(metadata_path: Path) -> list[str]:
    """All version strings declared in metadata.txt's changelog= block."""
    if not metadata_path.exists():
        return []
    text = metadata_path.read_text(encoding='utf-8', errors='replace')
    block = extract_metadata_changelog_block(text)
    if block is None:
        return []
    return sorted(
        {m.group('version').strip() for m in METADATA_CHANGELOG_ENTRY.finditer(block)},
        reverse=True,
    )


def _missing_changelog_md(version: str, found: list[str]) -> str:
    return (
        f"CHANGELOG.md is missing an entry for version {version!r}\n"
        f"  Expected header : `## [{version}]` (optional `- YYYY-MM-DD` suffix)\n"
        f"  Found versions  : {found or '[]'}\n\n"
        f"  To fix, add a section to CHANGELOG.md BEFORE tagging the release,\n"
        f"  and list at least one bullet under ### Fixed / ### Added / ### Changed:\n\n"
        f"## [{version}] - YYYY-MM-DD\n"
        f"### Fixed\n"
        f"- one bullet describing the most important change.\n"
    )


def _missing_metadata_changelog(
    version: str,
    md_found: list[str],
    meta_found: list[str],
    block_exists: bool,
) -> str:
    head = (
        f"metadata.txt changelog= block is missing an entry for version {version!r}.\n"
        f"  In CHANGELOG.md    : {md_found or '[]'}\n"
        f"  In metadata.txt    : {meta_found or '[]'}\n\n"
        f"  QGIS-Django auto-populates the plugins.qgis.org upload form's\n"
        f"  'Changes' textarea from the `changelog=` block in metadata.txt.\n"
        f"  Anything you paste into the upload form is silently overridden\n"
        f"  by that pre-fill on every submission, so this block — not\n"
        f"  CHANGELOG.md — is what controls the user-facing release notes on\n"
        f"  the plugins.qgis.org changelog tab.\n\n"
    )
    if not block_exists:
        # No `changelog=` key at all — the maintainer must create one. The
        # previous "prepend into the existing block" recipe was misleading
        # in this case (caught by code review). The recipe below mirrors the
        # actual metadata.txt indented-continuation format exactly so a
        # developer can paste it verbatim at column 0.
        return head + (
            f"  metadata.txt has no `changelog=` key at all. To fix, add the\n"
            f"  key (and a starter entry) at the bottom of the [general]\n"
            f"  section, following the indented-continuation format used by\n"
            f"  every other multi-line metadata.txt value:\n\n"
            f"changelog=\n"
            f"    {version} - <Short title>\n"
            f"    - First change.\n"
        )
    return head + (
        f"  To fix, prepend a new entry inside the existing `changelog=`,\n"
        f"  block (4-space indent, matching existing style), BEFORE tagging\n"
        f"  the release:\n\n"
        f"changelog=\n"
        f"    {version} - <Short title>\n"
        f"    - First change.\n"
        f"    - Second change.\n\n"
        f"    2.0.X - <Previous title>\n"
        f"    ...\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            'Fail if CHANGELOG.md OR metadata.txt changelog= block is missing '
            'an entry for the version= declared in metadata.txt.'
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
        help='Suppress the success messages; print only on failure.',
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

    md_found = collect_changelog_versions(args.changelog)
    meta_found = collect_metadata_changelog_versions(args.metadata)
    # `read_metadata_version()` already exits 2 on a missing or
    # non-parsable metadata.txt, so by the time we get here the file exists
    # and is non-empty. One read of metadata.txt is enough to detect both
    # "block missing" and "block present but missing version" — distinguish
    # them so the error helper can print the right fix recipe.
    metadata_text = args.metadata.read_text(encoding='utf-8', errors='replace')
    block_exists = METADATA_CHANGELOG_KEY.search(metadata_text) is not None
    failed = False

    if find_changelog_entry(args.changelog, version):
        if not args.quiet:
            print(f"✓ CHANGELOG.md has `## [{version}]` entry.")
    else:
        failed = True
        print(
            '::error ::' + _missing_changelog_md(version, md_found),
            file=sys.stderr,
        )

    if find_metadata_changelog_entry(args.metadata, version):
        if not args.quiet:
            print(f"✓ metadata.txt changelog= block has `{version} - ...` line.")
    else:
        failed = True
        print(
            '::error ::'
            + _missing_metadata_changelog(
                version, md_found, meta_found, block_exists
            ),
            file=sys.stderr,
        )

    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
