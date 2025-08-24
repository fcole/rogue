import json
from pathlib import Path
from typing import Dict, Any, Tuple, List
from .models import MapData, TileType, EntityType


def load_config(config_file: str) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    config_path = Path("config") / config_file
    with open(config_path, "r") as f:
        return json.load(f)


def load_secrets() -> Dict[str, str]:
    """Load secrets from config/secrets.json."""
    secrets_path = Path("config") / "secrets.json"
    with open(secrets_path, "r") as f:
        return json.load(f)


def validate_map_dimensions(tiles: str, width: int, height: int) -> tuple[bool, list[str]]:
    """Check if map dimensions match expected width and height."""
    errors = []
    lines = tiles.strip().split('\n')
    
    if len(lines) != height:
        errors.append(f"Expected {height} rows, got {len(lines)}")
    
    for i, line in enumerate(lines):
        if len(line) != width:
            errors.append(f"Row {i}: expected {width} chars, got {len(line)}")
    
    return len(errors) == 0, errors


def validate_map_connectivity(tiles: str, width: int, height: int) -> bool:
    """Check if all floor tiles are reachable from each other."""
    lines = tiles.strip().split('\n')
    if len(lines) != height:
        return False
    
    # Check dimensions first - if any row has wrong length, can't check connectivity
    for y, line in enumerate(lines):
        if len(line) != width:
            return False
    
    # Find first floor tile
    start = None
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char == '.':  # floor tile
                start = (x, y)
                break
        if start:
            break
    
    if not start:
        return False  # No floor tiles
    
    # BFS to find all reachable floor tiles
    visited = set()
    queue = [start]
    visited.add(start)
    
    while queue:
        x, y = queue.pop(0)
        
        # Check all 4 directions
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < width and 0 <= ny < height and 
                (nx, ny) not in visited and lines[ny][nx] == '.'):
                visited.add((nx, ny))
                queue.append((nx, ny))
    
    # Count total floor tiles
    total_floors = sum(line.count('.') for line in lines)
    return len(visited) == total_floors


def visualize_map(map_data: MapData) -> str:
    """Convert map to human-readable format with entity markers."""
    lines = map_data.tiles.strip().split('\n')
    
    # Create entity position lookup
    entity_positions = {}
    for entity_type, entity_list in map_data.entities.items():
        for entity in entity_list:
            pos = (entity.x, entity.y)
            if pos not in entity_positions:
                entity_positions[pos] = []
            entity_positions[pos].append(entity_type)
    
    # Build visualization
    result = []
    result.append(f"Map Layout ({map_data.width}x{map_data.height}):")
    
    for y, line in enumerate(lines):
        display_line = ""
        for x, char in enumerate(line):
            if (x, y) in entity_positions:
                # Show entity marker instead of tile
                entities = entity_positions[(x, y)]
                if EntityType.PLAYER in entities:
                    display_line += "@"
                elif EntityType.OGRE in entities:
                    display_line += "O"
                elif EntityType.GOBLIN in entities:
                    display_line += "G"
                elif EntityType.SHOP in entities:
                    display_line += "S"
                elif EntityType.CHEST in entities:
                    display_line += "C"
                else:
                    display_line += char
            else:
                display_line += char
        result.append(display_line)
    
    # Add entity summary
    if map_data.entities:
        result.append("\nEntities:")
        for entity_type, entity_list in map_data.entities.items():
            positions = [f"({e.x},{e.y})" for e in entity_list]
            result.append(f"- {len(entity_list)}x {entity_type.value}: {', '.join(positions)}")
    
    return '\n'.join(result)


def count_tiles(tiles: str) -> Dict[str, int]:
    """Count occurrences of each tile type."""
    counts = {
        'wall': tiles.count('#'),
        'floor': tiles.count('.'),
        'door': tiles.count('+'),
        'water': tiles.count('~')
    }
    return counts