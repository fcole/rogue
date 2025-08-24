import json
import click
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from ..shared.models import MapData
from ..shared.utils import visualize_map


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
                </div>
                <div class="summary-card">
                    <h3>Verification Score</h3>
                    <div class="value">{ver_data['summary']['average_score']:.1f}/10</div>
                </div>
                <div class="summary-card">
                    <h3>Avg Gen Time</h3>
                    <div class="value">{gen_data['summary']['average_time']:.1f}s</div>
                </div>
            </div>
            
            <p style="text-align: center; color: #7f8c8d; margin-bottom: 30px;">
                Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </p>
    """
    
    # Process each map
    for gen_result in gen_data["results"]:
        if gen_result["status"] != "success":
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
                        <div class="entity-legend">
                            <strong>Legend:</strong> # = wall, . = floor, + = door, ~ = water<br>
                            <strong>Entities:</strong> @ = player, O = ogre, G = goblin, S = shop, C = chest
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
                                {gen_result['generation_time']:.2f} seconds
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