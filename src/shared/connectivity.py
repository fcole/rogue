"""
Shared connectivity checking utilities for roguelike maps.
Ensures consistent connectivity validation across generator and verifier.
"""
from typing import List, Dict, Any, Tuple, Set


def check_map_connectivity(tiles: str, width: int, height: int) -> bool:
    """
    Check if a map is fully connected (all floor and door tiles are reachable).
    
    Args:
        tiles: String representation of the map with newlines
        width: Map width
        height: Map height
    
    Returns:
        True if all accessible tiles are connected, False otherwise
    """
    lines = tiles.strip().split('\n')
    
    # Validate dimensions
    if len(lines) != height:
        return False
    
    # Check dimensions first - if any row has wrong length, can't check connectivity
    for y, line in enumerate(lines):
        if len(line) != width:
            return False
    
    # Find first accessible tile (floor or door)
    start = None
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char in ['.', '+']:  # floor OR door
                start = (x, y)
                break
        if start:
            break
    
    if not start:
        return False  # No accessible tiles
    
    # BFS to find all reachable accessible tiles
    visited: Set[Tuple[int, int]] = set()
    queue = [start]
    visited.add(start)
    
    while queue:
        x, y = queue.pop(0)
        
        # Check all 4 directions
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < width and 0 <= ny < height and 
                (nx, ny) not in visited and lines[ny][nx] in ['.', '+']):
                visited.add((nx, ny))
                queue.append((nx, ny))
    
    # Count total accessible tiles (floors + doors)
    total_accessible = sum(line.count('.') + line.count('+') for line in lines)
    return len(visited) == total_accessible


def count_reachable_tiles(tiles: str, width: int, height: int) -> int:
    """
    Count how many accessible tiles (floors + doors) are reachable from the first accessible tile.
    
    Args:
        tiles: String representation of the map with newlines
        width: Map width
        height: Map height
    
    Returns:
        Number of reachable accessible tiles
    """
    lines = tiles.strip().split('\n')
    
    if not lines or len(lines) != height:
        return 0
    
    # Find first accessible tile (floor or door)
    start = None
    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char in ['.', '+']:  # floor OR door
                start = (x, y)
                break
        if start:
            break
    
    if not start:
        return 0
    
    # Flood fill to count reachable tiles
    visited: Set[Tuple[int, int]] = set()
    stack = [start]
    reachable_count = 0
    
    while stack:
        x, y = stack.pop()
        if (x, y) in visited:
            continue
            
        visited.add((x, y))
        if lines[y][x] in ['.', '+']:  # floor OR door
            reachable_count += 1
            
            # Add neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < width and 
                    0 <= ny < height and 
                    (nx, ny) not in visited and
                    lines[ny][nx] in ['.', '+']):  # floor OR door
                    stack.append((nx, ny))
    
    return reachable_count


def find_isolated_regions(tiles: str, width: int, height: int) -> List[Dict[str, Any]]:
    """
    Find isolated regions in the map.
    
    Args:
        tiles: String representation of the map with newlines
        width: Map width
        height: Map height
    
    Returns:
        List of isolated regions with their properties
    """
    lines = tiles.strip().split('\n')
    
    if not lines or len(lines) != height:
        return []
    
    # Find all accessible tiles (floors + doors)
    accessible_tiles = []
    for y in range(height):
        for x in range(width):
            if lines[y][x] in ['.', '+']:  # floor OR door
                accessible_tiles.append((x, y))
    
    if not accessible_tiles:
        return []
    
    # Find connected components using flood fill
    visited: Set[Tuple[int, int]] = set()
    regions = []
    
    for start_x, start_y in accessible_tiles:
        if (start_x, start_y) in visited:
            continue
        
        # Flood fill from this tile
        region_tiles = []
        stack = [(start_x, start_y)]
        
        while stack:
            x, y = stack.pop()
            if (x, y) in visited or lines[y][x] not in ['.', '+']:
                continue
            
            visited.add((x, y))
            region_tiles.append((x, y))
            
            # Add neighbors
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if (0 <= nx < width and 
                    0 <= ny < height and 
                    lines[ny][nx] in ['.', '+'] and 
                    (nx, ny) not in visited):
                    stack.append((nx, ny))
        
        if region_tiles:
            # Calculate region center and size
            center_x = sum(x for x, y in region_tiles) // len(region_tiles)
            center_y = sum(y for x, y in region_tiles) // len(region_tiles)
            
            regions.append({
                'tiles': region_tiles,
                'center_x': center_x,
                'center_y': center_y,
                'size': len(region_tiles)
            })
    
    # Return regions sorted by size (largest first)
    return sorted(regions, key=lambda r: r['size'], reverse=True)


def get_connectivity_stats(tiles: str, width: int, height: int) -> Dict[str, Any]:
    """
    Get detailed connectivity statistics for a map.
    
    Args:
        tiles: String representation of the map with newlines
        width: Map width
        height: Map height
    
    Returns:
        Dictionary with connectivity statistics
    """
    total_accessible = sum(line.count('.') + line.count('+') for line in tiles.strip().split('\n'))
    reachable = count_reachable_tiles(tiles, width, height)
    isolated_regions = find_isolated_regions(tiles, width, height)
    
    return {
        'total_accessible': total_accessible,
        'reachable': reachable,
        'isolated': total_accessible - reachable,
        'connectivity_percentage': (reachable / total_accessible * 100) if total_accessible > 0 else 0,
        'fully_connected': reachable == total_accessible,
        'isolated_regions': isolated_regions,
        'region_count': len(isolated_regions)
    }
