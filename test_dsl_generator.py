#!/usr/bin/env python3
"""
Test script for the DSL-based map generator.

This script demonstrates the DSL approach with selective checkpointing
and can be used to compare token efficiency against the tool-based approach.
"""

import sys
import json
import time
import argparse
from src.generator.dsl_generator import DSLMapGenerator, DSLMapBuilder, DSLParser

def test_parser():
    """Test the DSL parser with various commands."""
    print("🔍 Testing DSL Parser...")
    
    parser = DSLParser()
    test_programs = [
        # Basic commands
        'grid(20, 15)',
        'room("tavern", 2, 2, 10, 8)',
        'corridor(10, 5, 15, 8)',
        'door(10, 5)',
        'spawn(player, 8, 6)',
        'spawn(ogre, 15, 4, hp=50, aggressive=true)',
        
        # Water features
        'water_area(10, 8, "circle", radius=4)',
        'river([(5, 5), (10, 8), (15, 12)], width=3)',
        
        # Checkpoints
        'checkpoint("test")',
        'checkpoint("connected", verify_connectivity=true, stats=true)',
        'checkpoint("complete", full_verification=true)',
    ]
    
    for program in test_programs:
        try:
            commands = parser.parse_program(program)
            line_num, command, args, kwargs = commands[0]
            print(f"✅ {program} -> {command}({args}, {kwargs})")
        except Exception as e:
            print(f"❌ {program} -> Error: {e}")
    
    print()

def test_builder():
    """Test the DSL map builder with a complete program."""
    print("🏗️  Testing DSL Builder...")
    
    test_program = '''
    # Create basic grid
    grid(20, 15)
    
    # Create rooms
    room("main_hall", 2, 2, 12, 8)
    room("side_room", 15, 10, 4, 4)
    checkpoint("rooms_created", stats=true)
    
    # Connect rooms
    corridor(14, 6, 15, 6)
    corridor(15, 6, 17, 6)  
    corridor(17, 6, 17, 10)
    door(17, 9)
    checkpoint("connected", verify_connectivity=true)
    
    # Add water feature
    water_area(8, 12, "circle", radius=2)
    
    # Spawn entities
    spawn(player, 8, 6)
    spawn(ogre, 17, 12)
    spawn(chest, 5, 5)
    checkpoint("complete", full_verification=true)
    '''
    
    try:
        parser = DSLParser()
        builder = DSLMapBuilder()
        
        commands = parser.parse_program(test_program)
        print(f"📝 Parsed {len(commands)} commands")
        
        checkpoint_count = 0
        for line_num, command, args, kwargs in commands:
            result = builder.execute_command(command, args, kwargs)
            
            if command == "checkpoint":
                checkpoint_count += 1
                print(f"\n{result}\n")
            else:
                print(f"Line {line_num}: {result}")
        
        print(f"🎯 Completed with {checkpoint_count} checkpoints")
        
        # Test conversion to MapData
        map_data = builder.to_map_data("test_001", "a main hall with side room and water feature")
        print(f"📊 Final map: {map_data.width}x{map_data.height}, {len(map_data.entities)} entity types")
        
    except Exception as e:
        print(f"❌ Builder test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()

def test_generator_mock():
    """Test the generator without making API calls."""
    print("🤖 Testing DSL Generator (mock mode)...")
    
    # Test just the DSL execution part
    builder = DSLMapBuilder() 
    parser = DSLParser()
    
    # Simulate what Claude might generate
    mock_dsl_program = '''
    grid(20, 15)
    room("treasure_room", 5, 5, 8, 6)
    checkpoint("room_placed")
    
    spawn(player, 9, 8)
    spawn(chest, 7, 7)
    spawn(ogre, 11, 7)
    checkpoint("entities_placed", verify_entities=true)
    
    checkpoint("final", full_verification=true)
    '''
    
    try:
        commands = parser.parse_program(mock_dsl_program)
        checkpoint_outputs = []
        
        for line_num, command, args, kwargs in commands:
            result = builder.execute_command(command, args, kwargs)
            if command == "checkpoint":
                checkpoint_outputs.append(result)
        
        print("Checkpoint outputs:")
        for i, output in enumerate(checkpoint_outputs, 1):
            print(f"\n--- Checkpoint {i} ---")
            print(output)
        
        # Show final map data
        map_data = builder.to_map_data("mock_001", "treasure room with ogre guardian")
        print(f"\n🎮 Generated map with {sum(len(entities) for entities in map_data.entities.values())} entities")
        print(f"📈 Metadata: {map_data.metadata}")
        
    except Exception as e:
        print(f"❌ Generator mock test failed: {e}")
        import traceback
        traceback.print_exc()

def compare_token_efficiency():
    """Demonstrate token efficiency compared to tool-based approach."""
    print("⚡ Token Efficiency Comparison...")
    
    # Simulate tool-based approach token count
    tool_based_messages = [
        "User: Create a tavern with ogre",
        "Assistant: I'll create this map step by step...",
        "Tool: create_grid(20, 15)",
        "Result: Created 20x15 grid... [20x15 ASCII map]",
        "Tool: place_room(2, 2, 12, 8)", 
        "Result: Placed room... [20x15 ASCII map]",
        "Tool: place_door(8, 2)",
        "Result: Placed door... [20x15 ASCII map]",
        "Tool: place_entity('player', 8, 6)",
        "Result: Placed player... [20x15 ASCII map]", 
        "Tool: place_entity('ogre', 5, 5)",
        "Result: Placed ogre... [20x15 ASCII map]",
        "Tool: get_grid_status()",
        "Result: Grid status... [20x15 ASCII map + stats]"
    ]
    
    # Simulate DSL approach
    dsl_messages = [
        "User: Create a tavern with ogre",
        "Assistant: I'll create this using DSL...",
        """DSL Program:
grid(20, 15)
room("tavern", 2, 2, 12, 8)
door(8, 2)
checkpoint("structure_done")
spawn(player, 8, 6)
spawn(ogre, 5, 5)
checkpoint("complete", full_verification=true)""",
        """Checkpoint 1 - structure_done:
[20x15 ASCII map]

Checkpoint 2 - complete:  
[20x15 ASCII map]
Stats: connectivity ✅, entities ✅"""
    ]
    
    # Rough token estimation (very approximate)
    tool_tokens = sum(len(msg.split()) * 1.3 for msg in tool_based_messages)  # +30% for repetitive maps
    dsl_tokens = sum(len(msg.split()) * 1.1 for msg in dsl_messages)  # +10% for structured output
    
    efficiency_gain = ((tool_tokens - dsl_tokens) / tool_tokens) * 100
    
    print(f"📊 Estimated token usage:")
    print(f"   Tool-based approach: ~{tool_tokens:.0f} tokens")
    print(f"   DSL approach: ~{dsl_tokens:.0f} tokens")
    print(f"   Efficiency gain: ~{efficiency_gain:.1f}% reduction")
    print(f"   💡 Key savings: Fewer map visualizations, more structured communication")

def main():
    """Run all tests."""
    print("🧪 DSL Map Generator Test Suite\n")
    
    test_parser()
    test_builder()
    test_generator_mock()
    compare_token_efficiency()
    
    print("\n✨ All tests completed!")
    print("\nTo test with real API calls:")
    print("  python test_dsl_generator.py --real-api                    # Use Ollama (default)")
    print("  python test_dsl_generator.py --real-api --provider ollama  # Use Ollama explicitly")
    print("  python test_dsl_generator.py --real-api --provider anthropic  # Use Anthropic")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test DSL Map Generator")
    parser.add_argument("--real-api", action="store_true", help="Run tests with real API calls (Ollama or Anthropic)")
    parser.add_argument("--provider", choices=["ollama", "anthropic"], default="ollama", 
                       help="Choose LLM provider (default: ollama)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed LLM conversation")
    args = parser.parse_args()

    if args.real_api:
        print(f"🚀 Testing with real {args.provider.upper()} API...")
        try:
            generator = DSLMapGenerator(provider=args.provider, verbose=args.verbose)
            prompts = ["a simple tavern with one ogre"]
            
            start_time = time.time()
            results = generator.generate_maps(prompts)
            elapsed = time.time() - start_time
            
            print(f"⏱️  Generation took {elapsed:.2f}s")
            print(f"📈 Results: {results['summary']}")

            # Show error details if generation failed
            if results['results'] and results['results'][0].error_message:
                print(f"❌ Generation failed: {results['results'][0].error_message}")

            if results['results'] and results['results'][0].map_data:
                map_data = results['results'][0].map_data
                print(f"🗺️  Generated map: {map_data.width}x{map_data.height}")
                print(f"🎮 Entities: {sum(len(e) for e in map_data.entities.values())}")
                print(f"📋 Checkpoints used: {map_data.metadata.get('checkpoints_used', [])}")
                
                # Show the map
                from src.shared.utils import visualize_map
                print("\nFinal map:")
                print(visualize_map(map_data))
                
        except Exception as e:
            print(f"❌ Real API test failed: {e}")
            if args.provider == "anthropic":
                print("Make sure you have valid Anthropic API key in config/secrets.json")
            else:
                print("Make sure Ollama is running: ollama serve")
                # Get the model from config
                from src.shared.utils import load_config
                config = load_config("generator.json")
                ollama_model = config.get("ollama", {}).get("model", "deepseek-coder:33b-instruct")
                print(f"And you have the required model: ollama pull {ollama_model}")
    else:
        main()