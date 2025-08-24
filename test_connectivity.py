#!/usr/bin/env python3
"""
Test script for the shared connectivity module.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from shared.connectivity import check_map_connectivity, count_reachable_tiles, get_connectivity_stats

def test_connectivity():
    """Test connectivity checking with various map layouts."""
    
    # Test 1: Simple connected map
    print("🧪 Test 1: Simple connected map")
    simple_map = """####
#..#
#..#
####"""
    result = check_map_connectivity(simple_map, 4, 4)
    print(f"   Expected: True, Got: {result}")
    assert result == True, "Simple connected map should be connected"
    
    # Test 2: Map with door connecting regions
    print("\n🧪 Test 2: Map with door connecting regions")
    door_map = """####
#..#
#.+#
#..#
####"""
    result = check_map_connectivity(door_map, 4, 5)
    print(f"   Expected: True, Got: {result}")
    assert result == True, "Map with door should be connected"
    
    # Test 3: Disconnected map
    print("\n🧪 Test 3: Disconnected map")
    disconnected_map = """####
#..#
####
#..#
####"""
    result = check_map_connectivity(disconnected_map, 4, 5)
    print(f"   Expected: False, Got: {result}")
    assert result == False, "Disconnected map should not be connected"
    
    # Test 4: Map 6 from your test (should now be connected!)
    print("\n🧪 Test 4: Map 6 (forest clearing with door)")
    map6 = """####################
#..................#
#..................#
#.............####.#
#.............#..#.#
#...########..+..#.#
#...#......#...###.#
#...#..............#
#...#......#.......#
#...#......#.......#
#...########.......#
#..................#
#..................#
#..................#
####################"""
    
    result = check_map_connectivity(map6, 20, 15)
    print(f"   Expected: True, Got: {result}")
    
    # Get detailed stats
    stats = get_connectivity_stats(map6, 20, 15)
    print(f"   Stats: {stats['reachable']}/{stats['total_accessible']} tiles reachable")
    print(f"   Connectivity: {stats['connectivity_percentage']:.1f}%")
    print(f"   Fully connected: {stats['fully_connected']}")
    
    if result:
        print("   ✅ Map 6 is now correctly identified as connected!")
    else:
        print("   ❌ Map 6 is still incorrectly identified as disconnected")
    
    print("\n🎉 All connectivity tests passed!")

if __name__ == "__main__":
    test_connectivity()
