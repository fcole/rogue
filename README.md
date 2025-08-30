# Roguelike Testing System

A system for generating and verifying roguelike maps using LLMs.

## Quick Start

1. Set up environment: `uv venv && source .venv/bin/activate && uv pip install pydantic click rich structlog requests jsonschema anthropic`
2. Ensure Ollama is running (if using local LLM): `ollama serve`
3. Run full test suite: `python test_suite.py`
4. View HTML report: Open `data/report.html` in browser

## Individual Commands

- Generate maps: `python run.py 'generate --example --visualize'` (runs 10-prompt test suite)
- Use Claude tools (Anthropic): `python run.py 'generate --example --use-tools'`
- Use Ollama tools (local): `python run.py 'generate --example --use-ollama-tools'`
- Verify maps: `python run.py 'verify --example'`
- Generate report: `python run.py 'report'`
- Custom prompt: `python run.py 'generate --prompt "your custom map description"'`

## Components

- **Generator**: Converts text prompts to structured maps using Anthropic's Claude or local Ollama LLM
- **Verifier**: Validates maps match prompts using local Ollama LLM
- **Tool-Based Generator**: Guarantees map constraints using function calling (Claude or Ollama)

## Configuration

- `config/generator.json`: Map generation settings
- `config/verifier.json`: Verification settings  
- `config/secrets.json`: API keys (gitignored)

## Local LLM Integration

For local map generation using Ollama:

1. **Install Ollama**: `curl -fsSL https://ollama.ai/install.sh | sh`
2. **Download model**: `ollama pull deepseek-coder:33b-instruct` (or any model with function-calling)
3. **Start service**: `ollama serve`
4. **Test integration**: `python test_ollama_generator.py`
5. **Generate maps**: `python run.py 'generate --example --use-ollama-tools'`

See `OLLAMA_SETUP.md` for detailed setup instructions.
