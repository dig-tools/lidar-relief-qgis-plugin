"""report_generator.py — CIfA-compliant PDF report generation.

exports: generate_report(raster_path, algorithm_name, params, **kwargs) -> dict
         reportlab_available() -> bool

used_by: algorithms/pdf_report_algorithm.py
         batch pipeline (post-processing step)

rules:
  Uses ReportLab (pure Python, OSGeo4W-safe).
  NOT WeasyPrint (requires system C libs, breaks on Windows).
  Reports follow CIfA standards for archaeological remote sensing.
"""

import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        Image,
        PageBreak,
    )
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.lib.enums import TA_CENTER

    _REPORTLAB_AVAILABLE = True
except ImportError:
    _REPORTLAB_AVAILABLE = False


def reportlab_available() -> bool:
    """Check if ReportLab is installed and importable."""
    return _REPORTLAB_AVAILABLE


def check_dependencies() -> None:
    """Raise ImportError with clear instructions if ReportLab missing."""
    if not _REPORTLAB_AVAILABLE:
        raise ImportError(
            "PDF report generation requires 'reportlab'.\n\n"
            "Install it via the OSGeo4W Shell:\n"
            "  pip install reportlab\n\n"
            "Or via your system terminal:\n"
            "  pip install reportlab"
        )


def generate_report(
    raster_path: str,
    output_path: str,
    algorithm_name: str = "Unknown",
    algorithm_params: Optional[dict] = None,
    plugin_version: str = "",
    metadata: Optional[dict] = None,
    title: str = "LiDAR Relief Visualization Report",
    author: str = "",
    site_name: str = "",
    include_histogram: bool = True,
    include_stats: bool = True,
    include_map_preview: bool = False,
) -> dict:
    """Generate a CIfA-compliant PDF report for an algorithm output.

    The report includes:
      - Title page with site and processing metadata
      - Algorithm parameters (full serialization for reproducibility)
      - Input DEM metadata (CRS, resolution, extent, source)
      - Histogram statistics with percentile bands
      - Processing timestamp and plugin version
      - Optional map preview image

    Args:
        raster_path: Path to the output raster file.
        output_path: Path for the generated PDF.
        algorithm_name: Display name of the algorithm used.
        algorithm_params: Dict of parameter name → value.
        plugin_version: Plugin version string (read from metadata.txt via get_version()).
        metadata: Dict with optional metadata fields:
            - crs: CRS authority string
            - resolution: Pixel resolution
            - extent: (xmin, ymin, xmax, ymax)
            - source_dem: Source DEM filename
            - nodata: Nodata value
        title: Report title.
        author: Report author / organisation.
        site_name: Site or project name.
        include_histogram: If True, compute and embed histogram.
        include_stats: If True, include band statistics.
        include_map_preview: If True, render and embed a scaled map preview.

    Returns:
        dict with:
            - 'output_path': path to generated PDF
            - 'page_count': number of pages
            - 'size_bytes': file size

    Raises:
        ImportError: If ReportLab is not installed.
        RuntimeError: If report generation fails.
    """
    check_dependencies()

    algorithm_params = algorithm_params or {}
    metadata = metadata or {}

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=title,
        author=author or "LiDAR Relief Visualization Plugin",
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "CoverTitle",
            fontSize=24,
            leading=30,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#2c3e50"),
        )
    )
    styles.add(
        ParagraphStyle(
            "CoverSubtitle",
            fontSize=14,
            leading=18,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#7f8c8d"),
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionHead",
            fontSize=16,
            leading=20,
            spaceBefore=16,
            spaceAfter=8,
            textColor=colors.HexColor("#2c3e50"),
            borderWidth=0,
            borderColor=colors.HexColor("#3498db"),
            borderPadding=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "Field",
            fontSize=10,
            leading=14,
            spaceAfter=2,
            textColor=colors.HexColor("#555555"),
        )
    )
    styles.add(
        ParagraphStyle(
            "TableCell", fontSize=9, leading=11, textColor=colors.black, wordWrap="CJK"
        )
    )
    styles.add(
        ParagraphStyle(
            "Mono",
            fontSize=8,
            leading=10,
            spaceAfter=2,
            fontName="Courier",
            leftIndent=8,
        )
    )
    styles.add(
        ParagraphStyle(
            "Footer",
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#aaaaaa"),
        )
    )

    story = []
    page_count = [0]

    def add_header_footer(canvas, doc):
        page_count[0] += 1
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#aaaaaa"))
        canvas.drawString(20 * mm, 12 * mm, title)
        canvas.drawRightString(
            A4[0] - 20 * mm,
            12 * mm,
            f"Page {page_count[0]} | {datetime.now().strftime('%Y-%m-%d')}",
        )
        # Draw a thin line
        canvas.setStrokeColor(colors.HexColor("#dddddd"))
        canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
        canvas.restoreState()

    # ── Cover Page ────────────────────────────────────────────────────

    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph(title, styles["CoverTitle"]))
    if site_name:
        story.append(Paragraph(f"Site: {site_name}", styles["CoverSubtitle"]))
    story.append(Spacer(1, 10 * mm))
    story.append(
        Paragraph(f"Algorithm: <b>{algorithm_name}</b>", styles["CoverSubtitle"])
    )
    if author:
        story.append(Paragraph(f"Author: {author}", styles["CoverSubtitle"]))
    story.append(Spacer(1, 5 * mm))
    story.append(
        Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles["CoverSubtitle"],
        )
    )
    if plugin_version:
        story.append(
            Paragraph(f"Plugin version: {plugin_version}", styles["CoverSubtitle"])
        )

    # Decorative line
    story.append(Spacer(1, 15 * mm))
    story.append(_colored_line())

    story.append(Spacer(1, 10 * mm))
    story.append(
        Paragraph(
            "This report was automatically generated by the "
            "LiDAR Relief Visualization QGIS Plugin. It documents the "
            "processing parameters, input data provenance, and output "
            "statistics required for CIfA-compliant archaeological "
            "remote sensing survey reporting.",
            ParagraphStyle(
                "Abstract",
                fontSize=10,
                leading=14,
                alignment=TA_CENTER,
                textColor=colors.HexColor("#555555"),
            ),
        )
    )

    story.append(PageBreak())

    # ── 1. Processing Parameters ──────────────────────────────────────

    story.append(Paragraph("1. Processing Parameters", styles["SectionHead"]))
    story.append(Spacer(1, 4 * mm))

    param_data = [["Parameter", "Value"]]
    param_data.append(["Algorithm", Paragraph(algorithm_name, styles["TableCell"])])
    param_data.append(
        ["Plugin Version", Paragraph(plugin_version or "—", styles["TableCell"])]
    )
    param_data.append(
        [
            "Processing Date",
            Paragraph(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), styles["TableCell"]
            ),
        ]
    )

    for key, value in sorted(algorithm_params.items()):
        display_key = key.replace("_", " ").replace("-", " ").title()
        display_val = str(value) if value is not None else "—"
        param_data.append([display_key, Paragraph(display_val, styles["TableCell"])])

    param_table = Table(param_data, colWidths=[80 * mm, 100 * mm])
    param_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8f9fa")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(param_table)

    # ── 2. Input Data ─────────────────────────────────────────────────

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("2. Input Data Metadata", styles["SectionHead"]))
    story.append(Spacer(1, 4 * mm))

    meta_data = [["Property", "Value"]]
    meta_data.append(
        ["Source Raster", Paragraph(os.path.basename(raster_path), styles["TableCell"])]
    )

    meta_fields = [
        ("CRS", metadata.get("crs", "—")),
        ("Resolution", metadata.get("resolution", "—")),
        ("Extent (xmin, ymin, xmax, ymax)", str(metadata.get("extent", "—"))),
        ("Source DEM", metadata.get("source_dem", "—")),
        ("Nodata Value", str(metadata.get("nodata", "—"))),
    ]
    for label, value in meta_fields:
        meta_data.append([label, Paragraph(str(value), styles["TableCell"])])

    meta_table = Table(meta_data, colWidths=[80 * mm, 100 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8f9fa")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)

    # ── 3. Statistics & Histogram ─────────────────────────────────────

    # Compute stats if EITHER stats or histogram is requested. The
    # previous code only computed stats when `include_stats=True`,
    # which meant `include_histogram=True, include_stats=False`
    # silently produced no histogram (the `if include_histogram and stats:`
    # branch was never entered).
    if include_stats or include_histogram:
        stats = _compute_raster_stats(raster_path)

        if stats:
            story.append(Spacer(1, 8 * mm))
            story.append(Paragraph("3. Output Statistics", styles["SectionHead"]))
            story.append(Spacer(1, 4 * mm))

            stat_data = [["Statistic", "Value"]]

            def fmt(k):
                return f"{stats[k]:.4f}" if k in stats else "—"

            stat_rows = [
                ("Min", fmt("min")),
                ("Max", fmt("max")),
                ("Mean", fmt("mean")),
                ("Std Dev", fmt("std")),
                ("P5", fmt("p5")),
                ("P25", fmt("p25")),
                ("P50 (Median)", fmt("p50")),
                ("P75", fmt("p75")),
                ("P85", fmt("p85")),
                ("Valid Pixels", str(stats.get("valid_pixels", "—"))),
                ("Nodata Pixels", str(stats.get("nodata_pixels", "—"))),
            ]
            for label, value in stat_rows:
                stat_data.append([label, Paragraph(str(value), styles["TableCell"])])

            stat_table = Table(stat_data, colWidths=[80 * mm, 100 * mm])
            stat_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                        (
                            "ROWBACKGROUNDS",
                            (0, 1),
                            (-1, -1),
                            [colors.white, colors.HexColor("#f8f9fa")],
                        ),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            # Only render the stats table if include_stats is set;
            # otherwise we computed stats just to feed the histogram.
            if include_stats:
                story.append(stat_table)

        # Histogram (if requested and we have stats)
        if include_histogram and stats:
            story.append(Spacer(1, 6 * mm))
            try:
                # Use a unique temp filename to prevent collisions when
                # multiple reports are generated in the same directory
                # (batch mode). The previous code used the fixed name
                # '_histogram.png' which two concurrent reports would
                # clobber.
                import tempfile
                import uuid

                hist_dir = os.path.dirname(output_path) or "."
                hist_path = os.path.join(
                    hist_dir, f"_histogram_{uuid.uuid4().hex[:8]}.png"
                )
                rendered = _generate_histogram_image(
                    raster_path, output_dir=hist_dir, out_path=hist_path
                )
                if rendered and os.path.exists(rendered):
                    story.append(
                        Paragraph(
                            "Figure 1: Pixel value distribution",
                            styles["Field"],
                        )
                    )
                    story.append(Spacer(1, 2 * mm))
                    img = Image(rendered, width=160 * mm, height=80 * mm)
                    story.append(img)
            except Exception as e:
                logger.warning("Histogram generation failed: %s", e)

    # ── 4. Certification ──────────────────────────────────────────────

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph("4. Certification", styles["SectionHead"]))
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            "I confirm that the processing parameters, input data sources, "
            "and methodological steps documented in this report accurately "
            "describe the workflow used to generate the attached visualization.",
            styles["Field"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Signed: ___________________________    Date: _______________",
            styles["Field"],
        )
    )
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "This report conforms to the Chartered Institute for "
            "Archaeologists (CIfA) standards for geophysical and remote "
            "sensing survey reporting.",
            ParagraphStyle(
                "Disclaimer",
                fontSize=8,
                leading=10,
                textColor=colors.HexColor("#999999"),
            ),
        )
    )

    # Build PDF
    try:
        doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {e}") from e
    finally:
        # Clean up the histogram temp file if one was created.
        # We use a glob pattern because the filename includes a unique
        # UUID prefix to avoid collisions in batch mode.
        if include_histogram:
            import glob as _glob

            hist_dir = os.path.dirname(output_path) or "."
            for hist_file in _glob.glob(
                os.path.join(hist_dir, "_histogram_*.png")
            ):
                try:
                    os.remove(hist_file)
                except OSError:
                    pass

    size_bytes = os.path.getsize(output_path)

    return {
        "output_path": output_path,
        "page_count": page_count[0],
        "size_bytes": size_bytes,
    }


def _colored_line() -> Drawing:
    """A decorative colored line for the cover page."""
    d = Drawing(160 * mm, 2 * mm)
    d.add(
        Rect(
            0,
            0,
            160 * mm,
            2 * mm,
            fillColor=colors.HexColor("#3498db"),
            strokeColor=None,
        )
    )
    return d


def _compute_raster_stats(raster_path: str) -> dict:
    """Compute band statistics for a raster file.

    Uses GDAL to extract min, max, mean, std, and percentiles.

    Args:
        raster_path: Path to the raster file.

    Returns:
        dict with statistics or empty dict on failure.
    """
    try:
        from osgeo import gdal
        import numpy as np

        ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
        if ds is None:
            return {}

        band = ds.GetRasterBand(1)
        array = band.ReadAsArray()
        nodata = band.GetNoDataValue()

        ds = None

        if array is None or array.size == 0:
            return {}

        # Mask nodata
        if nodata is not None:
            mask = np.isclose(array, nodata, rtol=1e-5)
            valid = array[~mask]
        else:
            valid = array.flatten()

        if len(valid) == 0:
            return {}

        valid_float = valid.astype(np.float64)
        sorted_vals = np.sort(valid_float)

        return {
            "min": float(np.min(valid_float)),
            "max": float(np.max(valid_float)),
            "mean": float(np.mean(valid_float)),
            "std": float(np.std(valid_float)),
            "p5": float(sorted_vals[int(len(sorted_vals) * 0.05)]),
            "p25": float(sorted_vals[int(len(sorted_vals) * 0.25)]),
            "p50": float(sorted_vals[int(len(sorted_vals) * 0.50)]),
            "p75": float(sorted_vals[int(len(sorted_vals) * 0.75)]),
            "p95": float(sorted_vals[int(len(sorted_vals) * 0.95)]),
            "valid_pixels": int(len(valid_float)),
            "nodata_pixels": int(array.size - len(valid_float)),
        }
    except Exception as e:
        logger.warning("Statistics computation failed: %s", e)
        return {}


def _generate_histogram_image(
    raster_path: str,
    output_dir: str,
    out_path: Optional[str] = None,
    bins: int = 100,
) -> Optional[str]:
    """Generate a histogram image for embedding in the PDF.

    Uses GDAL + NumPy to compute the histogram and ReportLab to
    render it as a bar chart image.

    Args:
        raster_path: Path to the raster file.
        output_dir: Directory to save the histogram image (ignored if
            ``out_path`` is provided).
        out_path: Explicit output path. If provided, overrides the
            default ``_histogram.png`` filename in ``output_dir``.
            Use this to avoid filename collisions in batch mode.
        bins: Number of histogram bins.

    Returns:
        Path to the generated PNG image, or None on failure.
    """
    from reportlab.graphics.shapes import Drawing, Rect, Line, String

    try:
        from reportlab.graphics import renderPM
    except ImportError:
        renderPM = None
        logger.warning(
            "reportlab.graphics.renderPM is not available — histogram "
            "image will not be embedded in the PDF. Install Pillow "
            "(pip install pillow) to enable histogram rendering."
        )
    from osgeo import gdal
    import numpy as np

    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        return None

    band = ds.GetRasterBand(1)
    array = band.ReadAsArray()
    nodata = band.GetNoDataValue()
    ds = None

    if array is None or array.size == 0:
        return None

    # Mask nodata
    if nodata is not None:
        mask = np.isclose(array, nodata, rtol=1e-5)
        valid = array[~mask]
    else:
        valid = array.flatten()

    if len(valid) == 0:
        return None

    # Compute histogram
    hist, edges = np.histogram(valid.astype(np.float64), bins=bins)
    # Normalize
    hist = hist.astype(np.float64)
    if hist.max() > 0:
        hist = hist / hist.max()

    # Render as a simple bar chart using ReportLab graphics
    width, height = 600, 300
    margin_l, margin_b = 50, 40
    chart_w = width - margin_l - 20
    chart_h = height - margin_b - 20
    bar_w = chart_w / len(hist)

    d = Drawing(width, height)

    # Background
    d.add(Rect(0, 0, width, height, fillColor=colors.white, strokeColor=None))

    # Bars
    for i, val in enumerate(hist):
        bar_h = val * chart_h
        x = margin_l + i * bar_w
        y = margin_b
        d.add(
            Rect(
                x,
                y,
                max(bar_w * 0.8, 1),
                max(bar_h, 1),
                fillColor=colors.HexColor("#3498db"),
                strokeColor=None,
            )
        )

    # Axis labels
    d.add(
        Line(
            margin_l,
            margin_b,
            margin_l,
            margin_b + chart_h,
            strokeColor=colors.HexColor("#333333"),
            strokeWidth=1,
        )
    )
    d.add(
        Line(
            margin_l,
            margin_b,
            margin_l + chart_w,
            margin_b,
            strokeColor=colors.HexColor("#333333"),
            strokeWidth=1,
        )
    )

    # Min/max labels
    d.add(
        String(
            margin_l, margin_b - 12, f"{edges[0]:.2f}", fontSize=8, fontName="Helvetica"
        )
    )
    d.add(
        String(
            margin_l + chart_w - 30,
            margin_b - 12,
            f"{edges[-1]:.2f}",
            fontSize=8,
            fontName="Helvetica",
        )
    )

    if out_path is None:
        hist_path = os.path.join(output_dir, "_histogram.png")
    else:
        hist_path = out_path
    if renderPM is not None:
        renderPM.drawToFile(d, hist_path, fmt="PNG")
    else:
        # Without renderPM we can't actually produce the PNG — return
        # None so the caller knows there's no image to embed.
        return None
    return hist_path
