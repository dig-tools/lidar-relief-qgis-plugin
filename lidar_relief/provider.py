"""provider.py — QGIS Processing provider for LiDAR Relief plugin.
exports: LidarReliefProvider
used_by: __init__.py → initProcessing (plugin entry point)
rules:
  provider id must be 'lidar_relief'
  provider name must be 'LiDAR Relief'
  loadAlgorithms registers all algorithm classes
"""

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithms.hillshade_algorithm import HillshadeAlgorithm
from .algorithms.slrm_algorithm import SlrmAlgorithm
from .algorithms.svf_algorithm import SvfAlgorithm
from .algorithms.slope_algorithm import SlopeAlgorithm
from .algorithms.batch_algorithm import BatchAlgorithm
from .algorithms.openness_algorithm import OpennessAlgorithm
from .algorithms.mstp_algorithm import MstpAlgorithm
from .algorithms.blend_algorithm import BlendAlgorithm


class LidarReliefProvider(QgsProcessingProvider):
    """Processing provider that groups all LiDAR Relief algorithms."""

    def id(self):
        return 'lidar_relief'

    def name(self):
        return 'LiDAR Relief'

    def longName(self):
        return 'LiDAR Relief Visualisation Tools'

    def icon(self):
        import os
        icon_path = os.path.join(os.path.dirname(__file__), 'resources', 'icon.png')
        return QIcon(icon_path)

    def loadAlgorithms(self):
        """Register all algorithm instances.

        Rules:
            Every new algorithm class must be added here.
        """
        self.addAlgorithm(HillshadeAlgorithm())
        self.addAlgorithm(SlrmAlgorithm())
        self.addAlgorithm(SvfAlgorithm())
        self.addAlgorithm(SlopeAlgorithm())
        self.addAlgorithm(BatchAlgorithm())
        self.addAlgorithm(OpennessAlgorithm())
        self.addAlgorithm(MstpAlgorithm())
        self.addAlgorithm(BlendAlgorithm())
