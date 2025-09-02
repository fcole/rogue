import json
import click
from pathlib import Path
from typing import List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

"""CLI entrypoint with lazy imports for optional providers."""
from ..generator.smart_positioning_generator import SmartPositioningGenerator
from ..verifier.map_verifier import MapVerifier
from ..shared.models import MapData
from ..shared.utils import visualize_map, load_config
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
@click.option("--verbose", "-v", is_flag=True, help="Show detailed LLM conversation and generation steps")
@click.option("--use-ollama-tools", is_flag=True, help="Use Ollama tool-based generator (local, guarantees constraints)")
@click.option("--use-tools", is_flag=True, help="Use Claude tool-based generator (Anthropic)")
@click.option("--use-smart-positioning", is_flag=True, help="Use smart positioning generator (easier for LLMs)")
@click.option("--use-dsl", is_flag=True, help="Use DSL-based generator (structured commands, efficient)")
@click.option("--use-claude-dsl", is_flag=True, help="Use DSL-based generator with Claude (Anthropic)")
@click.option("--use-gemini-dsl", is_flag=True, help="Use DSL-based generator with Gemini (Google)")
@click.option("--ollama-endpoint", type=str, help="Override Ollama endpoint, e.g., http://host.docker.internal:11434")
def generate(prompts, prompt, output, example, visualize, verbose, use_ollama_tools, use_tools, use_smart_positioning, use_dsl, use_claude_dsl, use_gemini_dsl, ollama_endpoint):
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
    
    # Optional endpoint override for Ollama
    if ollama_endpoint:
        import os
        os.environ["OLLAMA_ENDPOINT"] = ollama_endpoint

    # Determine generator type (lazy import to avoid optional deps unless needed)
    if use_smart_positioning:
        generator_type = "Smart positioning"
        generator = SmartPositioningGenerator()
    else:
        # Choose explicit via flags first
        if use_dsl:
            from ..generator.dsl_generator import DSLMapGenerator
            generator_type = "DSL-based"
            generator = DSLMapGenerator(verbose=verbose)
        elif use_claude_dsl:
            from ..generator.dsl_generator import DSLMapGenerator
            generator_type = "DSL-based (Claude)"
            generator = DSLMapGenerator(provider="anthropic", verbose=verbose)
        elif use_gemini_dsl:
            from ..generator.dsl_generator import DSLMapGenerator
            generator_type = "DSL-based (Gemini)"
            generator = DSLMapGenerator(provider="gemini", verbose=verbose)
        elif use_ollama_tools:
            from ..generator.ollama_tool_generator import OllamaToolBasedGenerator
            generator_type = "Ollama tool-based"
            generator = OllamaToolBasedGenerator()
        elif use_tools:
            from ..generator.tool_based_generator import ToolBasedMapGenerator
            generator_type = "Claude tool-based"
            generator = ToolBasedMapGenerator()
        else:
            # Default from config: prefer provider in generator.json
            try:
                cfg = load_config("generator.json")
                provider = (cfg.get("llm", {}).get("provider") or "ollama").lower()
            except Exception:
                provider = "ollama"
            if provider == "anthropic":
                try:
                    from ..generator.tool_based_generator import ToolBasedMapGenerator
                    generator_type = "Claude tool-based"
                    generator = ToolBasedMapGenerator()
                except Exception as e:
                    console.print(f"[yellow]Falling back to Ollama tool-based generator: {e}[/yellow]")
                    from ..generator.ollama_tool_generator import OllamaToolBasedGenerator
                    generator_type = "Ollama tool-based"
                    generator = OllamaToolBasedGenerator()
            else:
                from ..generator.ollama_tool_generator import OllamaToolBasedGenerator
                generator_type = "Ollama tool-based"
                generator = OllamaToolBasedGenerator()
    
    # Include model details when available (e.g., Ollama/Anthropic generators)
    model_info = ""
    try:
        if hasattr(generator, "model") and getattr(generator, "model"):
            model_info = f" (model: {getattr(generator, 'model')})"
    except Exception:
        pass
    console.print(
        f"[green]Generating maps for {len(prompts_list)} prompts using {generator_type} generator{model_info}...[/green]"
    )
    
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

    # Show error details for failed generations
    failed_results = [r for r in results["results"] if r.error_message]
    if failed_results:
        console.print(f"\n[red]Error Details:[/red]")
        for result in failed_results:
            console.print(f"  • Map {result.prompt_index}: {result.error_message[:100]}{'...' if len(result.error_message) > 100 else ''}")

    console.print(f"Results saved to: {results_file}")


@main.command()
@click.option("--maps", "-m", type=click.Path(exists=True), help="Directory containing generated maps")
@click.option("--prompts", "-p", type=click.Path(exists=True), help="File containing original prompts")
@click.option("--results", type=click.Path(exists=True), help="Generation results JSON file")
@click.option("--output", "-o", type=click.Path(), default="data/verification", help="Output directory")
@click.option("--example", is_flag=True, help="Verify example maps (must run generate --example first)")
@click.option("--ollama-endpoint", type=str, help="Override Ollama endpoint for verifier LLM")
@click.option("--verifier-provider", type=click.Choice(["ollama", "anthropic", "gemini"]), help="Override LLM provider for verifier.")
def verify(maps, prompts, results, output, example, ollama_endpoint, verifier_provider):
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
    
    # Optional endpoint override for verifier
    if ollama_endpoint:
        import os
        os.environ["OLLAMA_ENDPOINT"] = ollama_endpoint

    console.print(f"[green]Verifying {len(test_cases)} maps...[/green]")
    
    # Create verifier and verify maps
    verifier = MapVerifier(provider=verifier_provider)
    
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
        
        # Check for critical entity failures (like missing player)
        critical_entity_failures = []
        for entity_type, check in result.quantitative_checks.get("entity_counts", {}).items():
            if check.get("critical", False) and not check.get("passed", True):
                critical_entity_failures.append(f"NO {entity_type.upper()}")
        
        if critical_entity_failures:
            issues.extend(critical_entity_failures)
        
        if not result.quantitative_checks.get("connectivity", {}).get("passed", True):
            issues.append("connectivity")
        # Flag entity overlap if detected
        if not result.quantitative_checks.get("entity_placement", {}).get("entity_overlap", {}).get("passed", True):
            issues.append("entity_overlap")
        # Flag unknown entities if any
        if result.quantitative_checks.get("unknown_entities", {}).get("count", 0) > 0:
            issues.append("unknown_entities")
        
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
