"""plugin.py — Main plugin class for LiDAR Relief Visualization.
exports: LidarReliefPlugin
used_by: __init__.py → classFactory
rules:
  Register the Processing provider in initGui(), remove in unload().
  Never perform heavy computation here — this is a lifecycle manager only.
"""

from qgis.core import QgsApplication


class LidarReliefPlugin:
    """Main QGIS plugin class that registers the Processing provider.

    Rules:
        initGui() and unload() are called by QGIS lifecycle.
        Provider must be stored as instance attribute for clean unload.
    """

    def __init__(self, iface):
        """Initialise the plugin.

        Args:
            iface: QgisInterface — the QGIS application interface.
        """
        self.iface = iface
        self.provider = None

    def initGui(self):
        """Register the LiDAR Relief Processing provider with QGIS."""
        from .provider import LidarReliefProvider
        self.provider = LidarReliefProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        """Unregister the Processing provider on plugin unload."""
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
