#!/usr/bin/env python3
"""
Explore the NPC sprite sheet to help identify good enemy sprites.
Creates a test map showing different ranges of NPC sprites.
"""

from pathlib import Path
import json
import subprocess
import sys

# Test different GID ranges to show different areas of the NPC sprite sheet
TEST_ENEMY_RANGES = {
    'goblin_candidates': list(range(3000, 3050)),  # Early sprites (likely goblins)
    'ogre_candidates': list(range(3100, 3150)),    # Mid-range sprites (likely larger creatures)
    'spirit_candidates': list(range(3200, 3250)),  # Later sprites (likely ethereal)
}

def create_test_map_json(map_id, enemies):
    """Create a test JSON file with enemies at specific positions."""
    test_data = {
        "id": f"test_{map_id}",
        "prompt": f"Test map for {map_id}",
        "width": 20,
        "height": 15,
        "tiles": "####################\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n#..................#\n####################",
        "entities": {
            "player": [{"x": 1, "y": 1, "properties": {}}],
        },
        "metadata": {
            "wall_count": 72,
            "floor_count": 208,
            "door_count": 0,
            "water_count": 0,
            "connectivity_verified": True,
            "generated_at": "test"
        }
    }

    # Add enemies in a grid pattern - use different GIDs for each position
    enemy_entities = {}
    x, y = 3, 2
    for i, gid in enumerate(enemies[:50]):  # Show up to 50 sprites
        ent_type = map_id.replace('_candidates', '')
        if ent_type not in enemy_entities:
            enemy_entities[ent_type] = []

        # Create individual enemy types with different GIDs
        individual_ent_type = f"{ent_type}_{i}"

        enemy_entities[individual_ent_type] = [{
            "x": x,
            "y": y,
            "properties": {"test_gid": gid}
        }]

        x += 2
        if x >= 18:
            x = 3
            y += 2
            if y >= 13:
                break

    test_data["entities"].update(enemy_entities)

    # Write test JSON
    output_path = Path("data/generated") / f"test_{map_id}.json"
    with open(output_path, 'w') as f:
        json.dump(test_data, f, indent=2)

    return output_path

def main():
    """Generate test maps for different enemy types."""
    print("Exploring NPC sprite sheet...")
    print("NPC sheet: 48 columns x 30 rows = 1440 tiles")
    print("GID range: 3000-4439 (3000 + 1440 - 1)")
    print()

    # Temporarily modify enemy GIDs for testing
    original_gids = {}
    try:
        # Import and modify the enemy GIDs temporarily
        sys.path.insert(0, '.')
        import scripts.ascii_to_tmx as tmx_module

        # Backup original GIDs
        original_gids = tmx_module.ENEMY_GIDS.copy()

        for test_name, gids in TEST_ENEMY_RANGES.items():
            print(f"Creating test map for {test_name}...")
            print(f"Testing GIDs: {gids[0]} to {gids[-1]}")
            print(f"This covers rows {((gids[0]-3000)//48)} to {((gids[-1]-3000)//48)} in the sprite sheet")
            print()

            # Create test JSON
            json_path = create_test_map_json(test_name, gids)

            # Temporarily set enemy GIDs for this test - set each enemy to use a different GID
            ent_type = test_name.replace('_candidates', '')
            for i, gid in enumerate(gids[:50]):  # Set up to 50 different GIDs
                individual_ent_type = f"{ent_type}_{i}"
                tmx_module.ENEMY_GIDS[individual_ent_type] = gid

            # Generate TMX using the proper palette learning function
            tmx_path = Path("data/tmx") / f"test_{test_name}.tmx"
            palette = tmx_module.learn_from_examples()
            tmx_module.ascii_to_tmx(str(json_path), "data/tmx", palette)

            # Render
            render_path = Path("data/renders") / f"test_{test_name}.png"
            subprocess.run([
                sys.executable, "scripts/render_tmx.py",
                str(tmx_path), "--out", "data/renders"
            ], check=True)

            print(f"✅ Generated {render_path}")
            print("Look at this image to see what sprites are in this GID range")
            print()

        print("\n" + "="*60)
        print("SUMMARY:")
        print("Check these test images to identify good enemy sprites:")
        for test_name in TEST_ENEMY_RANGES.keys():
            print(f"  - data/renders/test_{test_name}.png")
        print("\nOnce you identify good GIDs, update ENEMY_GIDS in scripts/ascii_to_tmx.py")

    finally:
        # Restore original GIDs
        if original_gids:
            tmx_module.ENEMY_GIDS.update(original_gids)

if __name__ == "__main__":
    main()
