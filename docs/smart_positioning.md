# Smart Positioning System for Map Generation

## Overview

The Smart Positioning System addresses a key challenge in LLM-based map generation: **making it easier for LLMs to specify positions without dealing with raw x,y coordinates**.

Traditional coordinate-based systems (like `place_door(5, 7)`) can be error-prone for LLMs, leading to:
- Connectivity issues
- Doors placed in illogical locations
- Rooms overlapping or extending beyond bounds
- Difficulty maintaining spatial relationships

## The Solution: Multiple Positioning Approaches

Instead of forcing LLMs to work with raw coordinates, the system provides **four intuitive positioning methods**:

### 1. Grid References (Chess Notation)
**Format**: `A1`, `B3`, `J8`, `T15`

- **Columns**: A, B, C, D... (A=0, B=1, etc.)
- **Rows**: 1, 2, 3, 4... (1=0, 2=1, etc.)
- **Example**: `B3` = column B (1), row 3 (2) = coordinates (1,2)

**LLM Usage**: `place_room("B3", 5, 4)` instead of `place_room(1, 2, 5, 4)`

### 2. Zone Positioning
**Format**: `northwest`, `center`, `east center`

Predefined zones with intuitive names:
- **Cardinal zones**: `north`, `south`, `east`, `west`
- **Corner zones**: `northwest`, `northeast`, `southwest`, `southeast`
- **Center zone**: `center`

**LLM Usage**: `place_room("northwest", 5, 4)` instead of calculating coordinates

### 3. Relative Positioning
**Format**: `3 tiles north of player`, `center of room1`

Position elements relative to existing landmarks:
- **Directional**: `X tiles [direction] of [landmark]`
- **Centered**: `center of [landmark]`
- **Landmarks**: Automatically created for rooms, player, etc.

**LLM Usage**: `place_door("2 tiles east of main_room")` for logical connectivity

### 4. Raw Coordinates (Fallback)
**Format**: `(5,7)` or `5,7`

Still available as a fallback for precise positioning when needed.

## Benefits for LLMs

### 🎯 **Eliminates Coordinate Math**
- No more calculating `(x+width-1, y+height-1)` for room bounds
- No more counting tiles for relative positioning
- Intuitive spatial reasoning

### 🔗 **Better Connectivity**
- `place_corridor("center of room1", "center of room2")` is more logical
- `place_door("east wall of main_room")` ensures proper placement
- Relative positioning maintains spatial relationships

### 🚫 **Reduced Errors**
- Zone positioning prevents out-of-bounds placement
- Grid references are easier to validate
- Relative positioning adapts to map changes

### 🧠 **Natural Language**
- LLMs can use spatial reasoning: "place shop in northwest corner"
- Intuitive descriptions: "door between the two rooms"
- Contextual placement: "chest near the player"

## Example Usage

### Before (Raw Coordinates)
```python
# LLM had to calculate these coordinates manually
place_room(5, 3, 6, 4)           # Main room
place_room(1, 1, 4, 3)           # Storage room  
place_door(5, 5)                  # Door placement
place_corridor(3, 2, 5, 5)       # Corridor connection
place_entity("player", 7, 4)      # Player placement
```

### After (Smart Positioning)
```python
# Much more intuitive and logical
place_room("center", 6, 4, "main_room")           # Main room in center
place_room("northwest", 4, 3, "storage")          # Storage in northwest
place_door("between storage and main_room")        # Logical door placement
place_corridor("center of storage", "center of main_room")  # Connect centers
place_entity("player", "center of main_room")      # Player in room center
```

## Implementation Details

### Grid Reference System
```python
# 20x15 grid creates references A1 through T15
# A1 = (0,0), J8 = (9,7), T15 = (19,14)
```

### Zone Definitions
```python
zones = {
    "northwest": {"x_range": (0, 9), "y_range": (0, 7), "center": (4, 3)},
    "center": {"x_range": (5, 14), "y_range": (3, 11), "center": (9, 7)},
    "southeast": {"x_range": (10, 19), "y_range": (8, 14), "center": (14, 11)}
}
```

### Automatic Landmark Creation
- **Rooms**: Automatically become landmarks when created
- **Player**: Becomes landmark for relative positioning
- **Custom**: Can add custom landmarks as needed

## CLI Integration

The smart positioning system is available as a new generator option:

```bash
# Use smart positioning generator
python -m src.cli.main generate --use-smart-positioning --example

# Compare with traditional generators
python -m src.cli.main generate --example  # Claude tool-based
python -m src.cli.main generate --use-ollama-tools --example  # Ollama tool-based
```

## Tool Schema Changes

### Traditional Tools
```json
{
    "name": "place_room",
    "properties": {
        "x": {"type": "integer", "minimum": 0, "maximum": 19},
        "y": {"type": "integer", "minimum": 0, "maximum": 14}
    }
}
```

### Smart Positioning Tools
```json
{
    "name": "place_room",
    "properties": {
        "position": {"type": "string", "description": "Smart position (e.g., 'B3', 'center', 'northwest')"}
    }
}
```

## Future Enhancements

### Advanced Relative Positioning
- **Path-based**: "along the corridor from room1 to room2"
- **Wall-based**: "north wall of main_room"
- **Corner-based**: "northeast corner of storage"

### Dynamic Zone Creation
- **Room-based zones**: "near the entrance", "far from the player"
- **Custom zones**: "dangerous area", "safe zone"

### Visual Grid Overlay
- **Structured light gray codes** (as you suggested)
- **Visual reference system** for even easier positioning
- **Interactive positioning** with visual feedback

## Conclusion

The Smart Positioning System transforms map generation from a coordinate-calculating exercise into an intuitive spatial reasoning task. LLMs can now focus on **what** they want to build rather than **where** to place it mathematically.

This should significantly improve:
- **Connectivity**: Logical door and corridor placement
- **Accuracy**: Reduced coordinate errors
- **Efficiency**: Faster map generation
- **Quality**: More coherent and playable maps

The system maintains backward compatibility while providing a much more natural interface for LLMs to work with spatial concepts.


