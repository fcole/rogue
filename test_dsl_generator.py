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
from src.generator.dsl_generator import DSLMapGenerator, DSLMapBuilder, DSLParser, CheckpointCommand

def test_parser():
    """Test the JSON DSL parser with various commands."""
    print("🔍 Testing JSON DSL Parser...")
    
    parser = DSLParser()
    test_programs = [
        # Basic commands
        '{"commands": [{"type": "grid", "width": 20, "height": 15}]}',
        '{"commands": [{"type": "room", "name": "tavern", "x": 2, "y": 2, "width": 10, "height": 8}]}',
        '{"commands": [{"type": "door_on", "room": "tavern", "wall": "north", "at": "center"}]}',
        '{"commands": [{"type": "spawn", "entity": "player", "in": "tavern", "at": "center"}]}',
        '{"commands": [{"type": "spawn", "entity": "ogre", "in": "tavern", "dx": 1, "properties": {"hp": 50, "aggressive": true}}]}',
        
        # Water features
        '{"commands": [{"type": "water_area", "x": 10, "y": 8, "shape": "circle", "radius": 4}]}',
        '{"commands": [{"type": "river", "points": [[5, 5], [10, 8], [15, 12]], "width": 3}]}',
        
        # Checkpoints
        '{"commands": [{"type": "checkpoint", "name": "test"}]}',
        '{"commands": [{"type": "checkpoint", "name": "connected", "verify_connectivity": true, "stats": true}]}',
        '{"commands": [{"type": "checkpoint", "name": "complete", "full_verification": true}]}',
    ]
    
    for program_json in test_programs:
        try:
            commands = parser.parse_program(program_json)
            command = commands[0]
            print(f"✅ {command.type} command -> {command.model_dump()}")
        except Exception as e:
            print(f"❌ {program_json[:50]}... -> Error: {e}")
    
    print()

def test_builder():
    """Test the JSON DSL map builder with a complete program."""
    print("🏗️  Testing JSON DSL Builder...")
    
    test_program_json = '''{
  "commands": [
    {"type": "grid", "width": 20, "height": 15},
    {"type": "room", "name": "main_hall", "x": 2, "y": 2, "width": 12, "height": 8},
    {"type": "room", "name": "side_room", "x": 15, "y": 10, "width": 4, "height": 4},
    {"type": "door_on", "room": "main_hall", "wall": "east", "at": "end"},
    {"type": "connect_by_walls", "a": "main_hall", "a_wall": "east", "b": "side_room", "b_wall": "west", "style": "L"},
    {"type": "checkpoint", "name": "rooms_created", "stats": true},
    {"type": "checkpoint", "name": "connected", "verify_connectivity": true},
    {"type": "water_area", "x": 8, "y": 12, "shape": "circle", "radius": 2},
    {"type": "spawn", "entity": "player", "in": "main_hall", "at": "center"},
    {"type": "spawn", "entity": "ogre", "in": "side_room", "dx": 1},
    {"type": "spawn", "entity": "chest", "in": "main_hall", "dx": -2, "dy": -1},
    {"type": "checkpoint", "name": "complete", "full_verification": true}
  ]
}'''
    
    try:
        parser = DSLParser()
        builder = DSLMapBuilder()
        
        commands = parser.parse_program(test_program_json)
        print(f"📝 Parsed {len(commands)} commands")
        
        checkpoint_count = 0
        for i, command in enumerate(commands):
            result = builder.execute_command(command)
            
            if isinstance(command, CheckpointCommand):
                checkpoint_count += 1
                print(f"\n{result}\n")
            else:
                print(f"Command {i}: {result}")
        
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
    
    # Simulate what Claude might generate (JSON format)
    mock_dsl_program_json = '''{
  "commands": [
    {"type": "grid", "width": 20, "height": 15},
    {"type": "room", "name": "treasure_room", "x": 5, "y": 5, "width": 8, "height": 6},
    {"type": "door_on", "room": "treasure_room", "wall": "north", "at": "center"},
    {"type": "checkpoint", "name": "room_placed"},
    {"type": "spawn", "entity": "player", "in": "treasure_room", "at": "center"},
    {"type": "spawn", "entity": "chest", "in": "treasure_room", "dx": -1},
    {"type": "spawn", "entity": "ogre", "in": "treasure_room", "dx": 1},
    {"type": "checkpoint", "name": "entities_placed", "verify_entities": true},
    {"type": "checkpoint", "name": "final", "full_verification": true}
  ]
}'''
    
    try:
        commands = parser.parse_program(mock_dsl_program_json)
        checkpoint_outputs = []
        
        for command in commands:
            result = builder.execute_command(command)
            if isinstance(command, CheckpointCommand):
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
    print("  python test_dsl_generator.py --real-api --provider gemini     # Use Gemini")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test DSL Map Generator")
    parser.add_argument("--real-api", action="store_true", help="Run tests with real API calls (Ollama or Anthropic)")
    parser.add_argument("--provider", choices=["ollama", "anthropic", "gemini"], default="ollama", 
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
