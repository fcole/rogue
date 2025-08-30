#!/usr/bin/env python3
"""
Demonstration of the smart positioning system for map generation.
This shows how LLMs can use intuitive positioning instead of raw coordinates.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.generator.positioning_system import SmartPositioning, GridReferencePositioning, RelativePositioning, ZonePositioning
from src.generator.smart_positioning_generator import SmartPositioningGridBuilder


def demo_grid_references():
    """Demonstrate grid reference positioning (like chess notation)."""
    print("=== GRID REFERENCE POSITIONING ===")
    print("This is like chess notation - much easier for LLMs to understand!")
    
    grid_ref = GridReferencePositioning(20, 15)
    
    # Show the grid overview
    print(grid_ref.get_grid_overview())
    
    # Demonstrate conversions
    examples = [
        ("A1", (0, 0)),
        ("J8", (9, 7)),
        ("T15", (19, 14)),
        ("B3", (1, 2)),
        ("K10", (10, 9))
    ]
    
    print("\nGrid Reference Examples:")
    for ref, expected in examples:
        coords = grid_ref.grid_ref_to_coords(ref)
        reverse = grid_ref.coords_to_grid_ref(*coords) if coords else "INVALID"
        print(f"  {ref} → {coords} → {reverse}")
    
    print("\nLLM can now say 'place room at B3' instead of 'place room at (1,2)'!")


def demo_relative_positioning():
    """Demonstrate relative positioning from landmarks."""
    print("\n=== RELATIVE POSITIONING ===")
    print("LLMs can position things relative to existing elements!")
    
    # Create a mock grid builder for demonstration
    class MockGridBuilder:
        pass
    
    relative = RelativePositioning(MockGridBuilder())
    
    # Add some landmarks
    relative.add_landmark("player", 5, 7)
    relative.add_landmark("room1", 10, 8)
    relative.add_landmark("shop", 15, 3)
    
    print(relative.get_available_landmarks())
    
    # Demonstrate relative positioning
    examples = [
        "3 tiles north of player",
        "2 tiles east of room1", 
        "center of shop",
        "5 tiles south of player"
    ]
    
    print("\nRelative Positioning Examples:")
    for desc in examples:
        coords = relative.get_relative_position(desc)
        print(f"  '{desc}' → {coords}")
    
    print("\nLLM can now say 'place door 2 tiles east of room1' instead of calculating coordinates!")


def demo_zone_positioning():
    """Demonstrate zone-based positioning."""
    print("\n=== ZONE POSITIONING ===")
    print("LLMs can use intuitive zone names instead of coordinates!")
    
    zones = ZonePositioning(20, 15)
    print(zones.get_zone_overview())
    
    # Demonstrate zone positioning
    examples = [
        ("northwest", "center"),
        ("center", "center"),
        ("east", "center"),
        ("southeast", "random"),
        ("north", "top")
    ]
    
    print("\nZone Positioning Examples:")
    for zone, position in examples:
        coords = zones.get_zone_position(zone, position)
        print(f"  '{zone} {position}' → {coords}")
    
    print("\nLLM can now say 'place room in northwest' instead of 'place room at (4,3)'!")


def demo_smart_positioning():
    """Demonstrate the combined smart positioning system."""
    print("\n=== SMART POSITIONING SYSTEM ===")
    print("Combines all approaches for maximum flexibility!")
    
    class MockGridBuilder:
        pass
    
    smart = SmartPositioning(MockGridBuilder(), 20, 15)
    
    # Add some landmarks for relative positioning
    smart.relative.add_landmark("player", 5, 7)
    smart.relative.add_landmark("main_room", 10, 8)
    
    # Demonstrate all positioning methods
    examples = [
        "B3",                    # Grid reference
        "center",                # Zone
        "northwest",             # Zone
        "3 tiles north of player",  # Relative
        "center of main_room",   # Relative
        "(5,7)",                 # Raw coordinates (fallback)
        "5,7"                    # Raw coordinates (fallback)
    ]
    
    print("\nSmart Positioning Examples:")
    for pos_input in examples:
        coords = smart.parse_position(pos_input)
        print(f"  '{pos_input}' → {coords}")
    
    print("\n" + smart.get_positioning_help())


def demo_map_building():
    """Demonstrate building a map with smart positioning."""
    print("\n=== MAP BUILDING WITH SMART POSITIONING ===")
    print("Let's build a simple map using intuitive positioning!")
    
    builder = SmartPositioningGridBuilder(20, 15)
    
    print("1. Creating grid...")
    result = builder.create_grid(20, 15)
    print(result)
    
    print("\n2. Placing main room in center...")
    result = builder.place_room("center", 8, 6, "main_room")
    print(result)
    
    print("\n3. Placing player in main room...")
    result = builder.place_entity("player", "center of main_room")
    print(result)
    
    print("\n4. Placing a smaller room in northwest...")
    result = builder.place_room("northwest", 5, 4, "storage")
    print(result)
    
    print("\n5. Placing door between rooms...")
    result = builder.place_door("J6")  # Grid reference
    print(result)
    
    print("\n6. Placing corridor to connect areas...")
    result = builder.place_corridor("center of storage", "center of main_room")
    print(result)
    
    print("\n7. Adding some entities...")
    result = builder.place_entity("chest", "northwest")
    print(result)
    
    result = builder.place_entity("goblin", "3 tiles east of player")
    print(result)
    
    print("\n8. Final map status...")
    result = builder.get_grid_status()
    print(result)


def main():
    """Run all demonstrations."""
    print("🎮 SMART POSITIONING SYSTEM DEMONSTRATION")
    print("=" * 50)
    print("This system makes it much easier for LLMs to specify positions!")
    print()
    
    demo_grid_references()
    demo_relative_positioning()
    demo_zone_positioning()
    demo_smart_positioning()
    demo_map_building()
    
    print("\n" + "=" * 50)
    print("🎯 KEY BENEFITS FOR LLMs:")
    print("✅ No more coordinate math!")
    print("✅ Intuitive positioning (like 'northwest', 'B3')")
    print("✅ Relative positioning from landmarks")
    print("✅ Multiple positioning systems in one")
    print("✅ Better connectivity and logical placement")
    print("✅ Reduced errors in door placement")
    print()
    print("🚀 Try it with: python -m src.cli.main generate --use-smart-positioning --example")


if __name__ == "__main__":
    main()


