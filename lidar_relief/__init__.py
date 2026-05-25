"""__init__.py — QGIS plugin entry point for LiDAR Relief Visualization.
exports: classFactory(iface) -> LidarReliefPlugin
used_by: QGIS plugin loader → classFactory
rules:
  classFactory is the only public contract — QGIS calls it on plugin load.
  Never import heavy dependencies at module level; defer to plugin.py.
"""


def classFactory(iface):
    """Create and return the plugin instance.

    Args:
        iface: QgisInterface — the QGIS application interface.

    Returns:
        LidarReliefPlugin instance.

    Rules:
        Must return a valid plugin object with initGui() and unload() methods.
    """
    from .plugin import LidarReliefPlugin
    return LidarReliefPlugin(iface)
