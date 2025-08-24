# Ollama Tool-Based Generator Setup

This guide explains how to set up and use the new Ollama tool-based generator for local map generation.

## Prerequisites

- **GPU**: RTX 5090 or equivalent (8GB+ VRAM recommended)
- **RAM**: 16GB+ system RAM
- **Storage**: 20GB+ free space for models

## Installation

### 1. Install Ollama

```bash
# Download and install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve
```

### 2. Download Recommended Models

For your RTX 5090, these models provide the best balance of performance and function calling support:

```bash
# High performance models with good function calling
ollama pull deepseek-coder:33b-instruct-q4_K_M    # Best overall
ollama pull qwen2.5:72b-q4_K_M                     # Very good reasoning
ollama pull llama3.1:70b-instruct-q4_K_M           # Balanced performance
ollama pull codellama:34b-instruct-q4_K_M          # Coding focused
```

**Recommended starting model**: `deepseek-coder:33b-instruct`

### 3. Verify Installation

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# List downloaded models
ollama list
```

## Configuration

The generator is configured in `config/generator.json`:

```json
{
  "llm": {
    "provider": "ollama",
    "model": "deepseek-coder:33b-instruct",
    "temperature": 0.3
  },
  "ollama": {
    "endpoint": "http://localhost:11434",
    "model": "deepseek-coder:33b-instruct",
    "temperature": 0.3
  }
}
```

## Usage

### Command Line Interface

```bash
# Generate maps using Ollama tool-based generator
python -m src.cli.main generate --example --use-ollama-tools

# Generate with custom prompts
python -m src.cli.main generate --prompt "a dungeon with three goblins" --use-ollama-tools

# Generate with prompt file
python -m src.cli.main generate --prompts my_prompts.txt --use-ollama-tools
```

### Test the Integration

```bash
# Run the test suite to verify everything works
python test_ollama_generator.py
```

## How It Works

### 1. Tool-Based Generation
The Ollama generator uses the same tool-calling approach as the Claude version:

- **create_grid**: Initialize 20x15 grid
- **place_room**: Create rectangular rooms
- **place_door**: Add doors for connections
- **place_corridor**: Create pathways
- **place_entity**: Add characters and objects
- **get_grid_status**: Check current state

### 2. Constraint Guarantees
Like the Claude version, this ensures:
- ✅ Exact dimensions (20x15)
- ✅ Valid entity placement
- ✅ Proper connectivity
- ✅ No out-of-bounds errors

### 3. Local Processing
All generation happens locally:
- 🚀 No API calls or internet required
- 🔒 No data sent to external services
- 💰 No per-token costs
- ⚡ Lower latency for development

## Performance Tuning

### Model Selection

| Model | VRAM Usage | Speed | Quality | Function Calling |
|-------|------------|-------|---------|------------------|
| `deepseek-coder:33b-instruct` | ~8GB | Fast | High | Excellent |
| `qwen2.5:72b-q4_K_M` | ~12GB | Medium | Very High | Good |
| `llama3.1:70b-instruct` | ~10GB | Medium | High | Good |
| `codellama:34b-instruct` | ~8GB | Fast | High | Excellent |

### Temperature Settings

```json
{
  "ollama": {
    "temperature": 0.1,  // More deterministic
    "temperature": 0.3,  // Balanced (recommended)
    "temperature": 0.7   // More creative
  }
}
```

### Batch Processing

For multiple prompts, the generator processes them sequentially. You can optimize by:

```python
# Process multiple prompts efficiently
generator = OllamaToolBasedGenerator()
results = generator.generate_maps([
    "a small room with one ogre",
    "an open field with two goblins",
    "a dense maze with three ogres"
])
```

## Troubleshooting

### Common Issues

#### 1. "Cannot connect to Ollama"
```bash
# Check if Ollama is running
ollama serve

# Verify endpoint
curl http://localhost:11434/api/tags
```

#### 2. "Model not found"
```bash
# List available models
ollama list

# Download the model
ollama pull deepseek-coder:33b-instruct
```

#### 3. "Function calling not supported"
Some models don't support function calling. Use these verified models:
- `deepseek-coder:33b-instruct`
- `codellama:34b-instruct`
- `llama3.1:70b-instruct`

#### 4. "Out of memory"
```bash
# Use smaller quantization
ollama pull deepseek-coder:33b-instruct-q4_K_M

# Or smaller model
ollama pull deepseek-coder:7b-instruct
```

### Performance Issues

#### Slow Generation
- Use smaller models for faster generation
- Reduce temperature for more deterministic output
- Check GPU utilization with `nvidia-smi`

#### High Memory Usage
- Use quantized models (q4_K_M, q5_K_M)
- Close other GPU applications
- Monitor with `nvidia-smi -l 1`

## Comparison with Claude Version

| Feature | Claude Tool Generator | Ollama Tool Generator |
|---------|----------------------|----------------------|
| **API Calls** | Required | None |
| **Cost** | Per-token | Free |
| **Latency** | Network dependent | Local |
| **Function Calling** | Native support | Model dependent |
| **Model Quality** | Very high | High |
| **Customization** | Limited | Full control |
| **Offline Use** | No | Yes |

## Advanced Usage

### Custom Tool Definitions

You can modify the tools in `src/generator/ollama_tool_generator.py`:

```python
# Add custom tools
self.tools.append({
    "name": "place_trap",
    "description": "Place a trap at coordinates",
    "parameters": {
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "trap_type": {"type": "string", "enum": ["pit", "arrow", "poison"]}
        },
        "required": ["x", "y", "trap_type"]
    }
})
```

### Integration with Existing Pipeline

The Ollama generator is fully compatible with your existing verification and reporting pipeline:

```bash
# Full workflow with Ollama
python -m src.cli.main generate --example --use-ollama-tools
python -m src.cli.main verify --example
python -m src.cli.main report
```

## Next Steps

1. **Test the integration**: Run `python test_ollama_generator.py`
2. **Try different models**: Experiment with various Ollama models
3. **Customize tools**: Add new tools for specific map features
4. **Optimize performance**: Tune temperature and model parameters
5. **Integrate into workflow**: Use in your regular map generation pipeline

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify Ollama is running and accessible
3. Ensure your model supports function calling
4. Check GPU memory and utilization
5. Review the test script output for specific errors
