#!/usr/bin/env python3
"""
Simple runner script for the roguelike testing system.
Activates virtual environment and runs commands.
"""
import subprocess
import sys
from pathlib import Path


def run_command(cmd):
    """Run command with virtual environment activated."""
    venv_python = Path(".venv/bin/python")
    if not venv_python.exists():
        print("Virtual environment not found. Run: uv venv && uv pip install ...")
        return 1
    
    full_cmd = f"PYTHONPATH=. {venv_python} -m src.cli.main {cmd}"
    return subprocess.call(full_cmd, shell=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run.py <command>")
        print("Examples:")
        print("  python run.py 'generate --example --visualize'  # Run 10-prompt test suite")
        print("  python run.py 'verify --example'")
        print("  python run.py 'report'")
        print("  python run.py 'generate --prompt \"custom prompt\"'  # Single custom prompt")
        print("\nOr run the full test suite:")
        print("  python test_suite.py")
        sys.exit(1)
    
    cmd = " ".join(sys.argv[1:])
    sys.exit(run_command(cmd))