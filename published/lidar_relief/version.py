"""version.py — single source of truth for the plugin version string.

exports: get_version() -> str
used_by: algorithms/* (PDF report, recipe IO), tests/*, anyone needing the version

rules:
  Read version from metadata.txt ONCE and cache it. Never hardcode the
  version in source files — always import from here.
"""

import os
from functools import lru_cache

_CACHE = None


@lru_cache(maxsize=1)
def get_version() -> str:
    """Return the plugin version as declared in metadata.txt.

    Reads metadata.txt at import time (once, cached). Falls back to
    '0.0.0+unknown' if the file can't be found or parsed — this should
    never happen in a packaged plugin, but keeps imports safe in odd
    test environments.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    # metadata.txt lives two levels up from this module
    # (lidar_relief/version.py -> lidar_relief/metadata.txt)
    metadata_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "metadata.txt"
    )

    version = "0.0.0+unknown"
    try:
        with open(metadata_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("version="):
                    version = line.split("=", 1)[1].strip()
                    break
    except OSError:
        pass

    _CACHE = version
    return version
