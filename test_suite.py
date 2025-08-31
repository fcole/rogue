#!/usr/bin/env python3
"""
Comprehensive test suite runner for the roguelike testing system.
Runs generation, verification, and report generation in sequence.
"""
import subprocess
import sys
import argparse
from pathlib import Path
import time
import logging

# Enable detailed logging to see what's happening during connectivity fixes
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def run_command(cmd, description):
    """Run command with virtual environment activated."""
    print(f"\n🔄 {description}...")
    
    venv_python = Path(".venv/bin/python")
    if not venv_python.exists():
        print("❌ Virtual environment not found. Run: uv venv && uv pip install ...")
        return 1
    
    full_cmd = f"PYTHONPATH=. {venv_python} -m src.cli.main {cmd}"
    
    start_time = time.time()
    result = subprocess.call(full_cmd, shell=True)
    duration = time.time() - start_time
    
    if result == 0:
        print(f"✅ {description} completed in {duration:.1f}s")
    else:
        print(f"❌ {description} failed")
    
    return result


def main():
    """Run the complete test suite workflow."""
    parser = argparse.ArgumentParser(description="Roguelike Testing System")
    parser.add_argument("--generate", action="store_true", help="Generate maps from test suite")
    parser.add_argument("--verify", action="store_true", help="Verify generated maps")
    parser.add_argument("--report", action="store_true", help="Generate HTML report")
    # Generator selection
    parser.add_argument(
        "--generator",
        choices=["default", "ollama", "claude", "smart", "dsl"],
        default="default",
        help="Choose generator: default (config), ollama (Ollama tool-based), claude (Anthropic tool-based), smart (smart positioning), dsl (DSL-based)",
    )
    parser.add_argument(
        "--ollama-endpoint",
        type=str,
        help="Optional Ollama endpoint override (e.g., http://host.docker.internal:11434)",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Print visual representation of maps during generation",
    )
    args = parser.parse_args()
    
    # If no specific steps are requested, run the complete suite
    if not any([args.generate, args.verify, args.report]):
        args.generate = True
        args.verify = True
        args.report = True
        print("🏰 Roguelike Testing System - Full Test Suite")
    else:
        steps = []
        if args.generate: steps.append("Generation")
        if args.verify: steps.append("Verification") 
        if args.report: steps.append("Reporting")
        print(f"🔧 Roguelike Testing System - {', '.join(steps)}")
    
    print("=" * 50)
    
    # Step 1: Generate maps from test suite
    if args.generate:
        gen_flags = ["generate", "--example"]
        if args.visualize:
            gen_flags.append("--visualize")
        if args.generator == "ollama":
            gen_flags.append("--use-ollama-tools")
        elif args.generator == "claude":
            gen_flags.append("--use-tools")
        elif args.generator == "smart":
            gen_flags.append("--use-smart-positioning")
        elif args.generator == "dsl":
            gen_flags.append("--use-dsl")
        if args.ollama_endpoint:
            gen_flags += ["--ollama-endpoint", args.ollama_endpoint]

        if run_command(" ".join(gen_flags), "Generating maps from test suite") != 0:
            sys.exit(1)
    
    # Step 2: Verify all generated maps
    if args.verify:
        ver_flags = ["verify", "--example"]
        if args.ollama_endpoint:
            ver_flags += ["--ollama-endpoint", args.ollama_endpoint]
        if run_command(" ".join(ver_flags), "Verifying generated maps") != 0:
            sys.exit(1)
    
    # Step 3: Generate HTML report
    if args.report:
        if run_command("report", "Generating HTML report") != 0:
            sys.exit(1)
    
    print("\n🎉 Test suite completed successfully!")
    
    # Show appropriate summary based on what was run
    if args.verify and args.report:
        print(f"📊 View results: file://{Path('data/report.html').absolute()}")
        
        try:
            import json
            with open("data/verification/verification_results.json", 'r') as f:
                ver_data = json.load(f)
            
            print("\n📈 Verification Summary:")
            print(f"   • Maps verified: {ver_data['summary']['total_tests']}")
            print(f"   • Maps passed: {ver_data['summary']['passed']}")
            print(f"   • Average score: {ver_data['summary']['average_score']:.1f}/10")
            
        except Exception as e:
            print(f"   (Could not load verification summary: {e})")
    
    elif args.generate and args.verify:
        try:
            import json
            with open("data/generated/generation_results.json", 'r') as f:
                gen_data = json.load(f)
            with open("data/verification/verification_results.json", 'r') as f:
                ver_data = json.load(f)
            
            print("\n📈 Quick Summary:")
            print(f"   • Maps generated: {gen_data['summary']['total_prompts']}")
            print(f"   • Average score: {ver_data['summary']['average_score']:.1f}/10")
            print(f"   • Maps passed: {ver_data['summary']['passed']}/{ver_data['summary']['total_tests']}")
            print(f"   • Average gen time: {gen_data['summary']['average_time']:.1f}s")
            
        except Exception as e:
            print(f"   (Could not load summary: {e})")
    
    elif args.generate:
        print("\n✅ Generation completed successfully!")
    
    elif args.verify:
        print("\n✅ Verification completed successfully!")
        print(f"📊 View results: file://{Path('data/report.html').absolute()}")
        
        try:
            import json
            with open("data/verification/verification_results.json", 'r') as f:
                ver_data = json.load(f)
            
            print("\n📈 Verification Summary:")
            print(f"   • Maps verified: {ver_data['summary']['total_tests']}")
            print(f"   • Maps passed: {ver_data['summary']['passed']}")
            print(f"   • Average score: {ver_data['summary']['average_score']:.1f}/10")
            
        except Exception as e:
            print(f"   (Could not load verification summary: {e})")
    
    elif args.report:
        print(f"\n✅ Report generation completed successfully!")
        print(f"📊 View results: file://{Path('data/report.html').absolute()}")


if __name__ == "__main__":
    main()
