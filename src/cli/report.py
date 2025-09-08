import json
import click
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from ..shared.models import MapData
from ..shared.utils import visualize_map
import xml.etree.ElementTree as ET
import re

try:
    # Optional dependency for TMX rendering
    from PIL import Image  # type: ignore
except Exception:
    Image = None  # type: ignore


def _parse_csv_layer(layer: ET.Element, width: int, height: int):
    data = layer.find("data")
    assert data is not None and data.get("encoding") == "csv"
    raw = re.split(r"[\s,]+", data.text.strip())
    nums = [int(x) for x in raw if x]
    assert len(nums) == width * height
    return [nums[i*width:(i+1)*width] for i in range(height)]


def _render_tmx_to_png(tmx_path: Path, out_png: Path) -> bool:
    """Render a TMX file to PNG. Returns True on success.

    Supports multiple image tilesets in draw order with CSV layers. If
    Pillow is unavailable, returns False.
    """
    if Image is None:
        return False
    try:
        root = ET.parse(tmx_path).getroot()
        w = int(root.get("width")); h = int(root.get("height"))
        tw = int(root.get("tilewidth")); th = int(root.get("tileheight"))
        # Load all tilesets
        tilesets = []
        for ts in root.findall("tileset"):
            firstgid = int(ts.get("firstgid"))
            cols = int(ts.get("columns"))
            tilecount = int(ts.get("tilecount"))
            img_el = ts.find("image")
            if img_el is None:
                continue
            sheet_path = (tmx_path.parent / img_el.get("source")).resolve()
            sheet = Image.open(sheet_path).convert("RGBA")
            tilesets.append({
                "firstgid": firstgid,
                "columns": cols,
                "tilecount": tilecount,
                "lastgid": firstgid + tilecount - 1,
                "sheet": sheet,
            })

        if not tilesets:
            return False

        # sort by firstgid
        tilesets.sort(key=lambda t: t["firstgid"])

        def find_tileset(gid: int):
            for ts in tilesets:
                if ts["firstgid"] <= gid <= ts["lastgid"]:
                    return ts
            return None

        canvas = Image.new("RGBA", (w * tw, h * th), (0, 0, 0, 0))
        for layer in root.findall("layer"):
            grid = _parse_csv_layer(layer, w, h)
            for yy in range(h):
                for xx in range(w):
                    gid = grid[yy][xx]
                    if gid <= 0:
                        continue
                    ts = find_tileset(gid)
                    if ts is None:
                        continue
                    local = gid - ts["firstgid"]
                    if local < 0 or local >= ts["tilecount"]:
                        continue
                    sx = (local % ts["columns"]) * tw
                    sy = (local // ts["columns"]) * th
                    tile = ts["sheet"].crop((sx, sy, sx + tw, sy + th))
                    canvas.alpha_composite(tile, (xx * tw, yy * th))
        out_png.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(out_png)
        return True
    except Exception:
        return False


def generate_html_report(generation_file: Path, verification_file: Path, output_file: Path):
    """Generate a nicely formatted HTML report."""
    
    # Load data
    with open(generation_file, 'r') as f:
        gen_data = json.load(f)
    
    with open(verification_file, 'r') as f:
        ver_data = json.load(f)
    
    # Create lookup for verification results by test_id
    ver_lookup = {r["test_id"]: r for r in ver_data["results"]}
    
    # Start building HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Roguelike Map Generation Report</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                text-align: center;
                margin-bottom: 30px;
                font-size: 2.5em;
            }}
            .summary {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 40px;
            }}
            .summary-card {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
            }}
            .summary-card h3 {{
                margin: 0 0 10px 0;
                font-size: 1.2em;
            }}
            .summary-card .value {{
                font-size: 2em;
                font-weight: bold;
            }}
            .map-entry {{
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-bottom: 30px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .map-header {{
                background: #34495e;
                color: white;
                padding: 15px;
                font-size: 1.2em;
                font-weight: bold;
            }}
            .map-content {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                padding: 20px;
            }}
            .map-visual {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 0.8em;
                line-height: 1.2;
                white-space: pre;
                overflow-x: auto;
            }}
            .verification-section {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
            }}
            .score-badge {{
                display: inline-block;
                padding: 5px 15px;
                border-radius: 20px;
                font-weight: bold;
                margin-bottom: 10px;
            }}
            .score-excellent {{ background: #27ae60; color: white; }}
            .score-good {{ background: #f39c12; color: white; }}
            .score-poor {{ background: #e74c3c; color: white; }}
            .status-success {{ background: #d4edda; color: #155724; }}
            .status-warning {{ background: #fff3cd; color: #856404; }}
            .status-error {{ background: #f8d7da; color: #721c24; }}
            .details-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 10px;
                margin-top: 15px;
            }}
            .detail-item {{
                background: white;
                padding: 10px;
                border-radius: 4px;
                border-left: 4px solid #3498db;
            }}
            .detail-item strong {{
                display: block;
                color: #2c3e50;
                margin-bottom: 5px;
            }}
            .entity-legend {{
                background: #ecf0f1;
                padding: 10px;
                border-radius: 4px;
                margin-top: 10px;
                font-size: 0.9em;
            }}
            .warnings {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                padding: 10px;
                border-radius: 4px;
                margin-top: 10px;
            }}
            .warnings ul {{
                margin: 5px 0;
                padding-left: 20px;
            }}
            @media (max-width: 768px) {{
                .map-content {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏰 Roguelike Map Generation Report</h1>
            <div class="summary">
                <div class="summary-card">
                    <h3>Total Maps</h3>
                    <div class="value">{gen_data['summary']['total_prompts']}</div>
                </div>
                <div class="summary-card">
                    <h3>Generation Success</h3>
                    <div class="value">{gen_data['summary']['successful']}/{gen_data['summary']['total_prompts']}</div>
                    {f'<div style="font-size: 0.8em; margin-top: 5px;">{gen_data["summary"]["failed"]} failed</div>' if gen_data['summary']['failed'] > 0 else ''}
                </div>
                <div class="summary-card">
                    <h3>Verification Score</h3>
                    <div class="value">{ver_data['summary']['average_score']:.1f}/10</div>
                </div>
                <div class="summary-card">
                    <h3>Avg Gen Time</h3>
                    <div class="value">{gen_data['summary']['average_time']:.1f}s</div>
                </div>
                {f'''<div class="summary-card" style="background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);">
                    <h3>Generation Failures</h3>
                    <div class="value">{gen_data['summary']['failed']}</div>
                    <div style="font-size: 0.8em; margin-top: 5px;">Used fallback maps</div>
                </div>''' if gen_data['summary']['failed'] > 0 else ''}
            </div>
            
            <p style="text-align: center; color: #7f8c8d; margin-bottom: 30px;">
                Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
    """
    
    # Collect failed results for summary
    failed_results = [r for r in gen_data["results"] if r.get("status") != "success"]

    # Process each successful map
    for gen_result in gen_data["results"]:
        if gen_result.get("status") != "success":
            continue

        # Load map data
        map_file = Path(gen_result["map_file"])
        with open(map_file, 'r') as f:
            map_data_dict = json.load(f)

        map_data = MapData(**map_data_dict)

        # Get verification result
        test_id = f"test_{gen_result['prompt_index']:03d}"
        ver_result = ver_lookup.get(test_id, {})

        # Generate map visualization
        visual = visualize_map(map_data)

        # Ensure rendered PNG exists for this map if TMX is present
        rendered_rel = Path("renders") / f"{map_data.id}.png"
        rendered_abs = Path("data") / rendered_rel
        tmx_path = Path("data/tmx") / f"{map_data.id}.tmx"
        if tmx_path.exists():
            need = (not rendered_abs.exists()) or (tmx_path.stat().st_mtime > rendered_abs.stat().st_mtime)
            if need:
                _render_tmx_to_png(tmx_path, rendered_abs)
        has_image = rendered_abs.exists()

        # Determine score class
        score = ver_result.get("overall_score", 0)
        if score >= 8:
            score_class = "score-excellent"
        elif score >= 6:
            score_class = "score-good"
        else:
            score_class = "score-poor"

        # Status class for warnings (dimension errors are most critical)
        warnings = gen_result.get("warnings", [])
        if not warnings:
            status_class = "status-success"
        elif any("dimension errors" in w.lower() for w in warnings):
            status_class = "status-error"  # Dimension errors are critical
        elif any("not fully connected" in w or "not on floor tile" in w for w in warnings):
            status_class = "status-error"
        else:
            status_class = "status-warning"

        html_content += f"""
            <div class="map-entry">
                <div class="map-header">
                    Map {gen_result['prompt_index']}: "{map_data.prompt}"
                </div>
                <div class="map-content">
                    <div>
                        <div class="map-visual">{visual}</div>
                        {f'<div style="margin-top:10px;"><img src="{rendered_rel.as_posix()}" alt="Rendered map {map_data.id}" style="image-rendering: pixelated; border:1px solid #ccc;"/></div>' if has_image else ''}
                        <div class="entity-legend">
                            <strong>Legend:</strong> # = wall, . = floor, + = door, ~ = water<br>
                            <strong>Entities:</strong> @ = player, O = ogre, G = goblin, S = shop, C = chest, T = tomb, X = spirit, H = human
                        </div>
                        {f'<div class="warnings {status_class}"><strong>Warnings:</strong><ul>{"".join(f"<li>{w}</li>" for w in warnings)}</ul></div>' if warnings else ''}
                    </div>
                    <div class="verification-section">
                        <div class="score-badge {score_class}">
                            Score: {score:.1f}/10 {'✓ PASSED' if ver_result.get('passed', False) else '✗ FAILED'}
                        </div>

                        <div class="details-grid">
                            <div class="detail-item">
                                <strong>Generation Time</strong>
                                {gen_result.get('generation_time', 0):.2f} seconds
                            </div>
                            <div class="detail-item">
                                <strong>Verification Time</strong>
                                {ver_result.get('processing_time', 0):.2f} seconds
                            </div>
                            <div class="detail-item">
                                <strong>Map Size</strong>
                                {map_data.width} × {map_data.height}
                            </div>
                            <div class="detail-item">
                                <strong>Connectivity</strong>
                                {'✓ Connected' if ver_result.get('quantitative_checks', {}).get('connectivity', {}).get('passed', False) else '✗ Disconnected'}
                            </div>
                        </div>

                        {_generate_verification_details(ver_result)}

                        {_generate_entity_details(map_data)}
                    </div>
                </div>
            </div>
        """

    # Add failure summary if any failures occurred
    if failed_results:
        html_content += f"""
            <div class="failures-section" style="margin-top: 40px; border-top: 2px solid #e74c3c; padding-top: 30px;">
                <h2 style="color: #e74c3c; text-align: center; margin-bottom: 30px;">❌ Generation Failures</h2>
                <div style="background: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                    <h3 style="color: #721c24; margin-top: 0;">Failed Generations Summary</h3>
                    <p style="margin-bottom: 15px;"><strong>Total Failed:</strong> {len(failed_results)} out of {gen_data['summary']['total_prompts']} attempts</p>
                    <p style="margin-bottom: 20px; color: #721c24;"><em>These maps fell back to minimal valid maps due to generation errors.</em></p>
                </div>

                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px;">
        """

        for failed_result in failed_results:
            error_msg = failed_result.get("error_message") or "Unknown error"
            # Truncate very long error messages for display
            if len(error_msg) > 200:
                error_msg = error_msg[:200] + "..."

            html_content += f"""
                    <div style="background: #fff5f5; border: 1px solid #fed7d7; border-radius: 8px; padding: 20px;">
                        <h4 style="color: #c53030; margin-top: 0; margin-bottom: 10px;">
                            Map {failed_result['prompt_index']}: Failed Generation
                        </h4>
                        <div style="background: #fed7d7; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                            <strong>Error:</strong> {error_msg}
                        </div>
                        <div style="color: #744210;">
                            <strong>Generation Time:</strong> {failed_result.get('generation_time', 0):.2f} seconds<br>
                            <strong>Status:</strong> {failed_result.get('status', 'failed')}
                        </div>
                    </div>
            """

        html_content += """
                </div>
            </div>
        """

    html_content += """
        </div>
    </body>
    </html>
    """
    
    # Write HTML file
    with open(output_file, 'w') as f:
        f.write(html_content)


def _generate_verification_details(ver_result: Dict[str, Any]) -> str:
    """Generate verification details HTML."""
    if not ver_result:
        return ""
    
    html = '<div style="margin-top: 15px;"><strong>Verification Details:</strong>'
    
    # Quantitative checks
    quant_checks = ver_result.get("quantitative_checks", {})
    
    # Show dimension errors first if present (most critical)
    if "dimension_errors" in quant_checks and not quant_checks["dimension_errors"].get("passed", True):
        errors = quant_checks["dimension_errors"].get("errors", [])
        html += f'<div style="margin-top: 10px; padding: 8px; background: #f8d7da; border-left: 4px solid #dc3545;"><strong>🚨 CRITICAL: Dimension Errors</strong><ul>'
        for error in errors[:3]:  # Show first 3 errors
            html += f'<li>{error}</li>'
        if len(errors) > 3:
            html += f'<li>... and {len(errors)-3} more</li>'
        html += '</ul></div>'
    
    if "entity_counts" in quant_checks:
        html += '<div style="margin-top: 10px;"><em>Entity Verification:</em><ul>'
        for entity_type, check in quant_checks["entity_counts"].items():
            status = "✓" if check.get("passed", True) else "✗"
            html += f'<li>{status} {entity_type}: expected {check.get("expected", "?")} got {check.get("actual", "?")}</li>'
        html += '</ul></div>'

    # Entity overlap (critical placement issue)
    try:
        ep = quant_checks.get("entity_placement", {})
        overlap = ep.get("entity_overlap", {})
        if overlap and not overlap.get("passed", True):
            msg = overlap.get("message", "Entities overlap on the same tile.")
            html += (
                '<div style="margin-top: 10px; padding: 10px; background: #fdecea; border-left: 4px solid #e74c3c;">'
                '<strong>⚠️ Entity Overlap Detected</strong>'
                f'<div style="margin-top: 6px;">{msg}</div>'
                '<div style="margin-top: 6px; color: #555; font-size: 0.95em;">'
                'Overlapping entities can make the map unplayable or confusing. '
                'Ensure each entity is placed on a distinct floor/door tile (use small dx/dy offsets when spawning in regions).'
                '</div>'
                '</div>'
            )
    except Exception:
        pass

    # Unknown entities surfaced by verifier
    if "unknown_entities" in quant_checks and quant_checks["unknown_entities"].get("count", 0) > 0:
        ue = quant_checks["unknown_entities"]
        values = ue.get("values", [])
        html += (
            '<div style="margin-top: 10px; padding: 8px; background: #fff3cd; border-left: 4px solid #ffc107;">'
            '<strong>Unknown Entities Detected</strong>'
            f'<div>Count: {ue.get("count", 0)}</div>'
            f'<div>Values: {", ".join(values)}</div>'
            '</div>'
        )
    
    # LLM feedback
    llm_response = ver_result.get("llm_response", {})
    if llm_response.get("positive_aspects"):
        html += f'<div style="margin-top: 10px;"><em>Positive Aspects:</em> {", ".join(llm_response["positive_aspects"])}</div>'
    if llm_response.get("negative_aspects"):
        html += f'<div style="margin-top: 10px;"><em>Areas for Improvement:</em> {", ".join(llm_response["negative_aspects"])}</div>'
    
    html += '</div>'
    return html


def _generate_entity_details(map_data: MapData) -> str:
    """Generate entity details HTML."""
    if not map_data.entities:
        return ""
    
    html = '<div style="margin-top: 15px;"><strong>Entities Placed:</strong><ul>'
    for entity_type, entity_list in map_data.entities.items():
        positions = [f"({e.x},{e.y})" for e in entity_list]
        html += f'<li>{len(entity_list)}× {entity_type.value}: {", ".join(positions)}</li>'
    html += '</ul></div>'
    return html


@click.command()
@click.option("--generation", "-g", type=click.Path(exists=True), 
              default="data/generated/generation_results.json",
              help="Generation results JSON file")
@click.option("--verification", "-v", type=click.Path(exists=True),
              default="data/verification/verification_results.json", 
              help="Verification results JSON file")
@click.option("--output", "-o", type=click.Path(),
              default="data/report.html",
              help="Output HTML file")
def report(generation, verification, output):
    """Generate HTML report from generation and verification results."""
    gen_file = Path(generation)
    ver_file = Path(verification)
    out_file = Path(output)
    
    if not gen_file.exists():
        click.echo(f"Error: Generation file not found: {gen_file}")
        return
    
    if not ver_file.exists():
        click.echo(f"Error: Verification file not found: {ver_file}")
        return
    
    click.echo(f"Generating HTML report...")
    generate_html_report(gen_file, ver_file, out_file)
    
    click.echo(f"✅ Report generated: {out_file.absolute()}")
    click.echo(f"🌐 Open in browser: file://{out_file.absolute()}")


if __name__ == "__main__":
    report()
