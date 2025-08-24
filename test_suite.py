#!/usr/bin/env python3
"""
Comprehensive test suite runner for the roguelike testing system.
Runs generation, verification, and report generation in sequence.
"""
import subprocess
import sys
from pathlib import Path
import time


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
    print("🏰 Roguelike Testing System - Full Test Suite")
    print("=" * 50)
    
    # Step 1: Generate maps from test suite
    if run_command("generate --example --visualize", "Generating maps from test suite") != 0:
        sys.exit(1)
    
    # Step 2: Verify all generated maps
    if run_command("verify --example", "Verifying generated maps") != 0:
        sys.exit(1)
    
    # Step 3: Generate HTML report
    if run_command("report", "Generating HTML report") != 0:
        sys.exit(1)
    
    print("\n🎉 Full test suite completed successfully!")
    print(f"📊 View results: file://{Path('data/report.html').absolute()}")
    
    # Show quick summary
    try:
        import json
        with open("data/generated/generation_results.json", 'r') as f:
            gen_data = json.load(f)
        with open("data/verification/verification_results.json", 'r') as f:
            ver_data = json.load(f)
        
        print("\n📈 Quick Summary:")
        print(f"   • Maps generated: {gen_data['summary']['successful']}/{gen_data['summary']['total_prompts']}")
        print(f"   • Average score: {ver_data['summary']['average_score']:.1f}/10")
        print(f"   • Maps passed: {ver_data['summary']['passed']}/{ver_data['summary']['total_tests']}")
        print(f"   • Average gen time: {gen_data['summary']['average_time']:.1f}s")
        
    except Exception as e:
        print(f"   (Could not load summary: {e})")


if __name__ == "__main__":
    main()