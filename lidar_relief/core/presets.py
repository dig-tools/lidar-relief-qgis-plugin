"""presets.py — Research-validated parameter presets by archaeological terrain context.
exports: PRESETS dict, get_preset(context_name) -> dict
used_by: algorithms/batch_algorithm.py
rules: Data-only module. No computation. Values from peer-reviewed literature.
  get_preset returns a deep copy so callers can mutate it without
  corrupting the canonical preset.
"""
import copy


PRESETS = {
    "flat_agricultural": {
        "svf": {"search_radius": 20, "num_directions": 16, "noise_level": 1},
        "openness": {"search_radius": 15, "num_directions": 16},
        "slrm": {"trend_radius": 20},
        "local_dominance": {"min_rad": 10, "max_rad": 20, "observer_height": 1.7},
    },
    "forested": {
        "svf": {"search_radius": 10, "num_directions": 16, "noise_level": 3},
        "openness": {"search_radius": 5, "num_directions": 16},
        "slrm": {"trend_radius": 12},
        "local_dominance": {"min_rad": 5, "max_rad": 15, "observer_height": 1.5},
    },
    "upland_steep": {
        "svf": {"search_radius": 5, "num_directions": 16, "noise_level": 2},
        "openness": {"search_radius": 5, "num_directions": 16},
        "slrm": {"trend_radius": 8},
        "local_dominance": {"min_rad": 5, "max_rad": 10, "observer_height": 1.0},
    },
    "coastal": {
        "svf": {"search_radius": 15, "num_directions": 32, "noise_level": 1},
        "openness": {"search_radius": 10, "num_directions": 32},
        "slrm": {"trend_radius": 25},
        "local_dominance": {"min_rad": 15, "max_rad": 30, "observer_height": 2.0},
    },
}


def get_preset(context_name: str) -> dict:
    """Return parameter dict for the given terrain context name.

    Returns a deep copy so callers can freely mutate the returned dict
    (e.g. overriding individual parameters) without corrupting the
    canonical preset definition in ``PRESETS``.
    """
    if context_name not in PRESETS:
        raise ValueError(
            f"Unknown preset context: {context_name!r}. "
            f"Valid options: {list(PRESETS.keys())}"
        )
    return copy.deepcopy(PRESETS[context_name])
