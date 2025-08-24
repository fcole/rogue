import json
import click
from pathlib import Path
from typing import List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ..generator.map_generator import MapGenerator
from ..verifier.map_verifier import MapVerifier
from ..shared.models import MapData
from ..shared.utils import visualize_map
from .report import report


console = Console()


@click.group()
def main():
    """Roguelike Map Generation and Verification System"""
    pass


@main.command()
@click.option("--prompts", "-p", type=click.Path(exists=True), help="File containing prompts (one per line)")
@click.option("--prompt", help="Single prompt to generate")
@click.option("--output", "-o", type=click.Path(), default="data/generated", help="Output directory")
@click.option("--example", is_flag=True, help="Run with example prompts")
@click.option("--visualize", is_flag=True, help="Print visual representation of maps")
def generate(prompts, prompt, output, example, visualize):
    """Generate roguelike maps from text prompts."""
    
    # Determine prompts to use
    if example:
        # Load test suite prompts
        test_suite_file = Path("tests/fixtures/prompts/test_suite.txt")
        if test_suite_file.exists():
            with open(test_suite_file, 'r') as f:
                prompts_list = [line.strip() for line in f if line.strip()]
        else:
            # Fallback to original simple examples
            prompts_list = [
                "a small room with one ogre",
                "an open field with two goblins", 
                "a dense maze with three ogres and a shop in the corner"
            ]
    elif prompt:
        prompts_list = [prompt]
    elif prompts:
        with open(prompts, 'r') as f:
            prompts_list = [line.strip() for line in f if line.strip()]
    else:
        console.print("[red]Error: Must specify --prompts, --prompt, or --example[/red]")
        return
    
    console.print(f"[green]Generating maps for {len(prompts_list)} prompts...[/green]")
    
    # Create generator and generate maps
    generator = MapGenerator()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Generating maps...", total=None)
        results = generator.generate_maps(prompts_list)
        progress.update(task, completed=True)
    
    # Create output directory
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save results
    results_file = output_path / "generation_results.json"
    
    # Convert results to JSON-serializable format
    json_results = {
        "results": [],
        "summary": results["summary"]
    }
    
    for result in results["results"]:
        result_dict = {
            "prompt_index": result.prompt_index,
            "status": result.status,
            "generation_time": result.generation_time,
            "warnings": result.warnings,
            "error_message": result.error_message
        }
        
        if result.map_data:
            # Save individual map file
            map_file = output_path / f"map_{result.prompt_index:03d}.json"
            with open(map_file, 'w') as f:
                json.dump(result.map_data.model_dump(), f, indent=2, default=str)
            result_dict["map_file"] = str(map_file)
            
            # Visualize if requested
            if visualize:
                console.print(f"\n[bold]Map {result.prompt_index}: {prompts_list[result.prompt_index]}[/bold]")
                console.print(visualize_map(result.map_data))
        
        json_results["results"].append(result_dict)
    
    # Save summary results
    with open(results_file, 'w') as f:
        json.dump(json_results, f, indent=2)
    
    # Display summary
    summary = results["summary"]
    console.print(f"\n[green]Generation Complete![/green]")
    console.print(f"Total prompts: {summary['total_prompts']}")
    console.print(f"Successful: {summary['successful']}")
    console.print(f"Failed: {summary['failed']}")
    console.print(f"Average time: {summary['average_time']:.2f}s")
    console.print(f"Results saved to: {results_file}")


@main.command()
@click.option("--maps", "-m", type=click.Path(exists=True), help="Directory containing generated maps")
@click.option("--prompts", "-p", type=click.Path(exists=True), help="File containing original prompts")
@click.option("--results", type=click.Path(exists=True), help="Generation results JSON file")
@click.option("--output", "-o", type=click.Path(), default="data/verification", help="Output directory")
@click.option("--example", is_flag=True, help="Verify example maps (must run generate --example first)")
def verify(maps, prompts, results, output, example):
    """Verify that generated maps match their prompts."""
    
    test_cases = []
    
    if example or not (maps and prompts):
        # Load from generation results
        results_file = Path("data/generated/generation_results.json") if example else Path(results) if results else None
        if not results_file or not results_file.exists():
            console.print("[red]Error: No generation results found. Run 'generate --example' first.[/red]")
            return
        
        with open(results_file, 'r') as f:
            gen_results = json.load(f)
        
        for result in gen_results["results"]:
            if result["status"] == "success" and "map_file" in result:
                with open(result["map_file"], 'r') as f:
                    map_data = json.load(f)
                
                test_cases.append({
                    "test_id": f"test_{result['prompt_index']:03d}",
                    "prompt": map_data["prompt"],
                    "map": map_data
                })
    else:
        # Load from separate files
        with open(prompts, 'r') as f:
            prompts_list = [line.strip() for line in f if line.strip()]
        
        maps_path = Path(maps)
        for i, prompt in enumerate(prompts_list):
            map_file = maps_path / f"map_{i:03d}.json"
            if map_file.exists():
                with open(map_file, 'r') as f:
                    map_data = json.load(f)
                
                test_cases.append({
                    "test_id": f"test_{i:03d}",
                    "prompt": prompt,
                    "map": map_data
                })
    
    if not test_cases:
        console.print("[red]Error: No test cases found to verify[/red]")
        return
    
    console.print(f"[green]Verifying {len(test_cases)} maps...[/green]")
    
    # Create verifier and verify maps
    verifier = MapVerifier()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Verifying maps...", total=None)
        verification_results = verifier.verify_maps(test_cases)
        progress.update(task, completed=True)
    
    # Create output directory and save results
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results_file = output_path / "verification_results.json"
    
    # Convert to JSON-serializable format
    json_results = {
        "results": [r.model_dump() for r in verification_results["results"]],
        "summary": verification_results["summary"]
    }
    
    with open(results_file, 'w') as f:
        json.dump(json_results, f, indent=2, default=str)
    
    # Display results table
    table = Table(title="Verification Results")
    table.add_column("Test ID", style="cyan")
    table.add_column("Score", style="magenta")
    table.add_column("Passed", style="green")
    table.add_column("Issues", style="red")
    
    for result in verification_results["results"]:
        issues = []
        
        # Check for dimension errors (critical - should appear first)
        if not result.quantitative_checks.get("dimension_errors", {}).get("passed", True):
            issues.append("DIMENSION ERRORS")
        
        if not result.quantitative_checks.get("connectivity", {}).get("passed", True):
            issues.append("connectivity")
        
        entity_issues = sum(1 for check in result.quantitative_checks.get("entity_counts", {}).values()
                           if not check.get("passed", True))
        if entity_issues > 0:
            issues.append(f"{entity_issues} entity issues")
        
        table.add_row(
            result.test_id,
            f"{result.overall_score:.1f}",
            "✓" if result.passed else "✗",
            ", ".join(issues) if issues else "none"
        )
    
    console.print(table)
    
    # Display summary
    summary = verification_results["summary"]
    console.print(f"\n[green]Verification Complete![/green]")
    console.print(f"Total tests: {summary['total_tests']}")
    console.print(f"Passed: {summary['passed']}")
    console.print(f"Failed: {summary['failed']}")
    console.print(f"Average score: {summary['average_score']:.1f}")
    if summary['common_failures']:
        console.print(f"Common failures: {', '.join(summary['common_failures'])}")
    console.print(f"Results saved to: {results_file}")


main.add_command(report)


if __name__ == "__main__":
    main()