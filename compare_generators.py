#!/usr/bin/env python3
"""
Compare DSL generator vs Ollama tool-based generator.

This script runs both generators on the same prompts and compares:
- Generation time
- Success rate
- Map quality metrics
"""

import sys
import time
import argparse
from typing import List, Dict, Any

def compare_generators(prompts: List[str], use_ollama_dsl: bool = True):
    """Compare DSL generator vs tool-based generator."""
    
    print("🔍 Comparing DSL Generator vs Tool-Based Generator\n")
    
    # Import generators
    try:
        from src.generator.dsl_generator import DSLMapGenerator
        from src.generator.ollama_tool_generator import OllamaToolBasedGenerator
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return
    
    # Test prompts
    test_prompts = prompts or [
        "a simple tavern with one ogre",
        "a dungeon with three rooms connected by corridors",
        "a forest clearing with a small pond"
    ]
    
    print(f"📝 Testing with {len(test_prompts)} prompts:")
    for i, prompt in enumerate(test_prompts, 1):
        print(f"  {i}. {prompt}")
    print()
    
    # Test DSL Generator
    print("🤖 Testing DSL Generator...")
    dsl_results = []
    dsl_times = []
    
    try:
        dsl_generator = DSLMapGenerator(provider="ollama")
        
        for i, prompt in enumerate(test_prompts):
            print(f"  Generating prompt {i+1}...")
            start_time = time.time()
            
            try:
                result = dsl_generator.generate_maps([prompt])
                generation_time = time.time() - start_time
                
                if result['results'] and result['results'][0].status == "success":
                    dsl_results.append("✅")
                    dsl_times.append(generation_time)
                    print(f"    ✅ Success in {generation_time:.2f}s")
                else:
                    dsl_results.append("❌")
                    dsl_times.append(generation_time)
                    print(f"    ❌ Failed in {generation_time:.2f}s")
                    
            except Exception as e:
                dsl_results.append("❌")
                dsl_times.append(0)
                print(f"    ❌ Error: {e}")
                
    except Exception as e:
        print(f"  ❌ DSL Generator setup failed: {e}")
        dsl_results = ["❌"] * len(test_prompts)
        dsl_times = [0] * len(test_prompts)
    
    print()
    
    # Test Tool-Based Generator
    print("🔧 Testing Ollama Tool-Based Generator...")
    tool_results = []
    tool_times = []
    
    try:
        tool_generator = OllamaToolBasedGenerator()
        
        for i, prompt in enumerate(test_prompts):
            print(f"  Generating prompt {i+1}...")
            start_time = time.time()
            
            try:
                result = tool_generator.generate_maps([prompt])
                generation_time = time.time() - start_time
                
                if result['results'] and result['results'][0].status == "success":
                    tool_results.append("✅")
                    tool_times.append(generation_time)
                    print(f"    ✅ Success in {generation_time:.2f}s")
                else:
                    tool_results.append("❌")
                    tool_times.append(generation_time)
                    print(f"    ❌ Failed in {generation_time:.2f}s")
                    
            except Exception as e:
                tool_results.append("❌")
                tool_times.append(0)
                print(f"    ❌ Error: {e}")
                
    except Exception as e:
        print(f"  ❌ Tool-Based Generator setup failed: {e}")
        tool_results = ["❌"] * len(test_prompts)
        dsl_times = [0] * len(test_prompts)
    
    print()
    
    # Print comparison results
    print("📊 Comparison Results:")
    print("=" * 60)
    print(f"{'Prompt':<40} {'DSL':<8} {'Tool':<8}")
    print("-" * 60)
    
    for i, prompt in enumerate(test_prompts):
        prompt_short = prompt[:37] + "..." if len(prompt) > 40 else prompt
        print(f"{prompt_short:<40} {dsl_results[i]:<8} {tool_results[i]:<8}")
    
    print("-" * 60)
    
    # Success rates
    dsl_success = sum(1 for r in dsl_results if r == "✅")
    tool_success = sum(1 for r in tool_results if r == "✅")
    
    print(f"Success Rate: DSL {dsl_success}/{len(test_prompts)} ({dsl_success/len(test_prompts)*100:.1f}%)")
    print(f"Success Rate: Tool {tool_success}/{len(test_prompts)} ({tool_success/len(test_prompts)*100:.1f}%)")
    
    # Average times (excluding failures)
    dsl_avg_time = sum(t for t, r in zip(dsl_times, dsl_results) if r == "✅") / max(dsl_success, 1)
    tool_avg_time = sum(t for t, r in zip(tool_times, tool_results) if r == "✅") / max(tool_success, 1)
    
    print(f"Avg Time: DSL {dsl_avg_time:.2f}s, Tool {tool_avg_time:.2f}s")
    
    if dsl_success > 0 and tool_success > 0:
        speed_diff = ((tool_avg_time - dsl_avg_time) / tool_avg_time) * 100
        if speed_diff > 0:
            print(f"🚀 DSL is {speed_diff:.1f}% faster")
        else:
            print(f"🐌 DSL is {abs(speed_diff):.1f}% slower")

def main():
    parser = argparse.ArgumentParser(description="Compare DSL vs Tool-Based generators")
    parser.add_argument("--prompts", nargs="+", help="Custom test prompts")
    parser.add_argument("--ollama-dsl", action="store_true", default=True, 
                       help="Use Ollama for DSL generator (default: True)")
    
    args = parser.parse_args()
    
    compare_generators(args.prompts, args.ollama_dsl)

if __name__ == "__main__":
    main()
