#!/usr/bin/env python3
"""
Test script for the Ollama tool-based generator.
Run this to verify the local LLM integration works.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from generator.ollama_tool_generator import OllamaToolBasedGenerator
from rich.console import Console

console = Console()

def test_ollama_generator():
    """Test the Ollama tool-based generator."""
    console.print("🧪 Testing Ollama Tool-Based Generator", style="bold blue")
    console.print("=" * 50)
    
    try:
        # Create generator
        console.print("📦 Creating OllamaToolBasedGenerator...")
        generator = OllamaToolBasedGenerator()
        console.print("✅ Generator created successfully")
        
        # Test configuration
        console.print(f"🔧 Configuration:")
        console.print(f"   • Model: {generator.model}")
        console.print(f"   • Endpoint: {generator.ollama_endpoint}")
        console.print(f"   • Temperature: {generator.temperature}")
        console.print(f"   • Tools available: {len(generator.tools)}")
        
        # Test simple map generation
        console.print("\n🎯 Testing map generation...")
        test_prompt = "a small room with one ogre"
        
        result = generator.generate_maps([test_prompt])
        
        if result["summary"]["successful"] > 0:
            console.print("✅ Map generation successful!")
            console.print(f"   • Generated: {result['summary']['successful']} maps")
            console.print(f"   • Average time: {result['summary']['average_time']:.2f}s")
            
            # Show first result details
            first_result = result["results"][0]
            if first_result.map_data:
                console.print(f"   • Map dimensions: {first_result.map_data.width}x{first_result.map_data.height}")
                console.print(f"   • Entities: {len(first_result.map_data.entities)} types")
                for entity_type, entities in first_result.map_data.entities.items():
                    console.print(f"     - {entity_type.value}: {len(entities)}")
        else:
            console.print("❌ Map generation failed")
            for result in result["results"]:
                if result.error_message:
                    console.print(f"   • Error: {result.error_message}")
        
    except Exception as e:
        console.print(f"❌ Test failed: {e}", style="red")
        console.print("\n🔍 Troubleshooting tips:")
        console.print("   1. Make sure Ollama is running: ollama serve")
        console.print("   2. Check if the model is downloaded: ollama list")
        console.print("   3. Verify Ollama endpoint is accessible")
        console.print("   4. Check the model supports function calling")
        return False
    
    return True

def check_ollama_status():
    """Check if Ollama is running and accessible."""
    console.print("\n🔍 Checking Ollama status...")
    
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            console.print("✅ Ollama is running and accessible")
            console.print(f"   • Available models: {len(models)}")
            for model in models[:3]:  # Show first 3
                console.print(f"     - {model.get('name', 'Unknown')}")
            if len(models) > 3:
                console.print(f"     ... and {len(models) - 3} more")
            return True
        else:
            console.print("❌ Ollama responded with error status")
            return False
    except Exception as e:
        console.print(f"❌ Cannot connect to Ollama: {e}")
        return False

if __name__ == "__main__":
    console.print("🚀 Ollama Tool Generator Test Suite", style="bold green")
    
    # Check Ollama status first
    if not check_ollama_status():
        console.print("\n💡 Please start Ollama first:")
        console.print("   ollama serve")
        console.print("\n   Then download a model with function calling support:")
        console.print("   ollama pull deepseek-coder:33b-instruct")
        sys.exit(1)
    
    # Run the test
    success = test_ollama_generator()
    
    if success:
        console.print("\n🎉 All tests passed! You can now use:")
        console.print("   python -m src.cli.main generate --example --use-ollama-tools")
    else:
        console.print("\n💥 Tests failed. Check the error messages above.")
        sys.exit(1)
