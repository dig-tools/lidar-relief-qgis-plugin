"""styling.py — Auto-styling for QGIS output layers.
exports: ReliefLayerPostProcessor
used_by: algorithms/*
"""

from qgis.core import (
    QgsProcessingLayerPostProcessorInterface,
    QgsRasterBandStats,
    QgsRasterLayer,
    QgsSingleBandGrayRenderer,
    QgsContrastEnhancement,
)


class ReliefLayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Post-processor to automatically style relief outputs."""

    def __init__(self, layer_name: str, stretch_type="stddev"):
        super().__init__()
        self.layer_name = layer_name
        self.stretch_type = stretch_type

    def postProcessLayer(self, layer: QgsRasterLayer, context, feedback):
        """Apply styling to the output layer."""
        if not isinstance(layer, QgsRasterLayer):
            return

        if self.layer_name:
            layer.setName(self.layer_name)

        # Standard Deviation stretch for single band raster
        if layer.bandCount() == 1:
            provider = layer.dataProvider()
            stats = provider.bandStatistics(1, QgsRasterBandStats.All)

            renderer = QgsSingleBandGrayRenderer(provider, 1)
            contrast_enhancement = QgsContrastEnhancement(provider.dataType(1))

            if self.stretch_type == "stddev":
                contrast_enhancement.setContrastEnhancementAlgorithm(
                    QgsContrastEnhancement.StretchToMinimumMaximum
                )
                # 2 std dev
                min_val = max(stats.minimumValue, stats.mean - 2 * stats.stdDev)
                max_val = min(stats.maximumValue, stats.mean + 2 * stats.stdDev)
                contrast_enhancement.setMinimumValue(min_val)
                contrast_enhancement.setMaximumValue(max_val)
            else:
                contrast_enhancement.setContrastEnhancementAlgorithm(
                    QgsContrastEnhancement.StretchToMinimumMaximum
                )
                contrast_enhancement.setMinimumValue(stats.minimumValue)
                contrast_enhancement.setMaximumValue(stats.maximumValue)

            renderer.setContrastEnhancement(contrast_enhancement)
            layer.setRenderer(renderer)
            layer.triggerRepaint()
