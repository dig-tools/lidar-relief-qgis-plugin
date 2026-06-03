"""web_viewer.py — Interactive web map viewer generation.

exports: generate_web_viewer(cog_path, output_dir, **kwargs) -> dict
         generate_viewer_html(cog_filename, **kwargs) -> str

used_by: algorithms/cog_export_algorithm.py → generate_web_viewer
         batch pipeline for automated web publishing

rules:
  Generates a self-contained HTML page with MapLibre GL JS.
  COG is loaded directly via the maplibre-cog-protocol plugin.
  Output can be uploaded to any static hosting (GitHub Pages, S3, etc.).
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# MapLibre GL JS version for CDN loading
_MAPLIBRE_VERSION = "4.7.1"
_COG_PROTOCOL_VERSION = "0.0.2"


def generate_web_viewer(
    cog_path: str,
    output_dir: str,
    title: str = "LiDAR Relief Visualization",
    description: str = "",
    center: Optional[tuple[float, float]] = None,
    zoom: Optional[float] = None,
    min_zoom: float = 2,
    max_zoom: float = 22,
    attribution: str = "LiDAR Relief Visualization QGIS Plugin",
    dark_mode: bool = True,
    opacity: float = 1.0,
) -> dict:
    """Generate a complete web viewer package for a COG file.

    Creates:
        - output_dir/index.html     — MapLibre web viewer
        - output_dir/config.json    — Viewer configuration (machine-readable)

    Args:
        cog_path: Path to the Cloud-Optimized GeoTIFF.
        output_dir: Directory to write the viewer files into.
        title: Page title and map heading.
        description: Optional description text below title.
        center: (lon, lat) map center. Auto-detected from COG if None.
        zoom: Initial zoom level. Auto-computed if None.
        min_zoom: Minimum zoom level.
        max_zoom: Maximum zoom level.
        attribution: Attribution string for the map.
        dark_mode: Use dark background style.
        opacity: Initial raster layer opacity (0.0–1.0).

    Returns:
        dict with:
            - 'index_html': path to generated index.html
            - 'config_json': path to config.json
            - 'cog_path': the source COG path
            - 'center': (lon, lat) used
            - 'zoom': zoom level used

    Note:
        The COG file must be served via HTTPS for the web viewer to work.
        The HTML file references the COG by relative path (same directory).
    """
    os.makedirs(output_dir, exist_ok=True)

    cog_filename = os.path.basename(cog_path)

    # Try to read COG metadata for auto-centering
    if center is None or zoom is None:
        try:
            import rasterio

            with rasterio.open(cog_path) as src:
                bounds = src.bounds
                if center is None:
                    center = (
                        (bounds.left + bounds.right) / 2.0,
                        (bounds.bottom + bounds.top) / 2.0,
                    )
                if zoom is None:
                    # Approximate zoom from raster width
                    width_px = src.width
                    # Rough zoom heuristic: wider = zoomed out
                    zoom = max(min_zoom, min(16, 14 - (width_px / 5000)))
        except Exception:
            if center is None:
                center = (0.0, 0.0)
            if zoom is None:
                zoom = 8

    centre_lon, centre_lat = center

    # Provide default description mentioning the COG file
    if not description:
        description = (
            f"Visualization generated from <code>{cog_filename}</code>"
        )

    # Generate HTML
    html = _generate_viewer_html(
        cog_filename=cog_filename,
        title=title,
        description=description,
        center_lon=centre_lon,
        center_lat=centre_lat,
        zoom=zoom,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        attribution=attribution,
        dark_mode=dark_mode,
        opacity=opacity,
    )

    # Generate config JSON
    config = {
        "version": "1.0",
        "title": title,
        "description": description,
        "cog": cog_filename,
        "center": [centre_lon, centre_lat],
        "zoom": zoom,
        "min_zoom": min_zoom,
        "max_zoom": max_zoom,
        "attribution": attribution,
        "dark_mode": dark_mode,
        "opacity": opacity,
    }

    index_path = os.path.join(output_dir, "index.html")
    config_path = os.path.join(output_dir, "config.json")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return {
        "index_html": index_path,
        "config_json": config_path,
        "cog_path": cog_path,
        "center": (centre_lon, centre_lat),
        "zoom": zoom,
    }


def _generate_viewer_html(
    cog_filename: str,
    title: str,
    description: str,
    center_lon: float,
    center_lat: float,
    zoom: float,
    min_zoom: float,
    max_zoom: float,
    attribution: str,
    dark_mode: bool,
    opacity: float,
) -> str:
    """Generate the MapLibre GL JS HTML string.

    The viewer uses the COG protocol plugin to load the Cloud-Optimized
    GeoTIFF directly in the browser without a tile server.
    """
    style = (
        "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
        if dark_mode
        else "https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png"
    )
    style_attr = (
        "CARTO (dark)" if dark_mode else "CARTO (light)"
    )

    # Min/max zoom for COG display: constrain to avoid requesting
    # tiles outside the raster's resolution
    cog_min_zoom = 0
    cog_max_zoom = max_zoom

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_escape_html(title)}</title>
<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@{_MAPLIBRE_VERSION}/dist/maplibre-gl.css" />
<script src="https://unpkg.com/maplibre-gl@{_MAPLIBRE_VERSION}/dist/maplibre-gl.js"></script>
<script src="https://unpkg.com/@maplibre/maplibre-gl-cog-protocol@{_COG_PROTOCOL_VERSION}/dist/index.umd.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
  #map {{ width: 100vw; height: 100vh; }}
  .info {{ position: absolute; top: 16px; left: 16px; z-index: 10;
           background: rgba(0,0,0,0.8); color: #fff; padding: 12px 16px;
           border-radius: 8px; max-width: 400px;
           box-shadow: 0 2px 8px rgba(0,0,0,0.3);
           pointer-events: none; }}
  .info h1 {{ font-size: 18px; margin-bottom: 4px; }}
  .info p {{ font-size: 13px; opacity: 0.8; line-height: 1.4; }}
  .info code {{ font-size: 12px; background: rgba(255,255,255,0.1); padding: 2px 4px; border-radius: 3px; }}
  .controls {{ position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%);
               z-index: 10; background: rgba(0,0,0,0.75); color: #fff;
               padding: 8px 16px; border-radius: 8px; font-size: 13px;
               display: flex; gap: 12px; align-items: center;
               pointer-events: none; }}
  .controls label {{ display: flex; align-items: center; gap: 6px; cursor: pointer; pointer-events: all; }}
  .controls input[type=range] {{ width: 100px; cursor: pointer; pointer-events: all; }}
  .maplibregl-ctrl-attrib {{ font-size: 11px !important; }}
</style>
</head>
<body>
<div class="info">
  <h1>{_escape_html(title)}</h1>
  <p>{description}</p>
</div>
<div id="map"></div>
<div class="controls">
  <label>Opacity: <input type="range" id="opacity" min="0" max="1" step="0.05" value="{opacity}" /></label>
  <span id="coord-display">—</span>
</div>
<script>
  const map = new maplibregl.Map({{
    container: 'map',
    style: '{style}',
    center: [{center_lon}, {center_lat}],
    zoom: {zoom},
    minZoom: {min_zoom},
    maxZoom: {max_zoom},
    attributionControl: true,
  }});

  map.addControl(new maplibregl.NavigationControl(), 'top-right');

  // Register the COG protocol plugin
  map.on('style.load', () => {{
    map.addSource('relief', {{
      type: 'raster',
      tiles: ['cog://{_escape_html(cog_filename)}' + '?minzoom={cog_min_zoom}&maxzoom={cog_max_zoom}'],
      tileSize: 512,
      attribution: '{_escape_html(attribution)}'
    }});
    map.addLayer({{
      id: 'relief-layer',
      type: 'raster',
      source: 'relief',
      paint: {{ 'raster-opacity': {opacity} }}
    }});
  }});

  // Opacity slider
  document.getElementById('opacity').addEventListener('input', (e) => {{
    map.setPaintProperty('relief-layer', 'raster-opacity', parseFloat(e.target.value));
  }});

  // Coordinate display on mousemove
  map.on('mousemove', (e) => {{
    const lng = e.lngLat.lng.toFixed(5);
    const lat = e.lngLat.lat.toFixed(5);
    document.getElementById('coord-display').textContent = `Lng {{lng}}  Lat {{lat}}`;
  }});

  // Share link button
  map.addControl(new (class {{
    onAdd(map) {{
      const btn = document.createElement('button');
      btn.className = 'maplibregl-ctrl-icon';
      btn.innerHTML = '🔗';
      btn.style.fontSize = '18px';
      btn.style.cursor = 'pointer';
      btn.style.padding = '4px 8px';
      btn.style.background = '#fff';
      btn.style.border = 'none';
      btn.style.borderRadius = '4px';
      btn.title = 'Copy share link';
      btn.onclick = () => {{
        const url = new URL(window.location);
        url.searchParams.set('zoom', map.getZoom().toFixed(1));
        url.searchParams.set('lat', map.getCenter().lat.toFixed(5));
        url.searchParams.set('lng', map.getCenter().lng.toFixed(5));
        navigator.clipboard.writeText(url.toString());
        btn.textContent = '✓';
        setTimeout(() => {{ btn.innerHTML = '🔗'; }}, 2000);
      }};
      return btn;
    }}
    onRemove() {{}}
  }}(), 'top-right');
</script>
</body>
</html>"""


def _escape_html(text: str) -> str:
    """Escape special characters for safe HTML embedding."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
