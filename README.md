# Roguelike Testing System

A system for generating and verifying roguelike maps using LLMs.

## Quick Start

1. Set up environment: `uv venv && source .venv/bin/activate && uv pip install pydantic click rich structlog requests jsonschema anthropic`
2. Ensure Ollama is running with llama3.1:8b: `ollama serve`
3. Run full test suite: `python test_suite.py`
4. View HTML report: Open `data/report.html` in browser

## Individual Commands

- Generate maps: `python run.py 'generate --example --visualize'` (runs 10-prompt test suite)
- Verify maps: `python run.py 'verify --example'`
- Generate report: `python run.py 'report'`
- Custom prompt: `python run.py 'generate --prompt "your custom map description"'`

## Components

- **Generator**: Converts text prompts to structured maps using Anthropic's Claude
- **Verifier**: Validates maps match prompts using local Ollama LLM

## Configuration

- `config/generator.json`: Map generation settings
- `config/verifier.json`: Verification settings  
- `config/secrets.json`: API keys (gitignored)