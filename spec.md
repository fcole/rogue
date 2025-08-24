# Roguelike Map Generation and Verification System Specification

## Overview

This system consists of two main components:
1. **Map Generator**: Converts text prompts to structured map representations using an online LLM
2. **Map Verifier**: Validates that structured maps match their original prompts using a local LLM

## System Architecture

```
Text Prompts → [Map Generator] → Structured Maps
                                       ↓
Original Prompts + Structured Maps → [Map Verifier] → Validation Results
```

## Core Data Structures

### Map Specification (v1.0)

```json
{
  "metadata": {
    "version": "1.0",
    "prompt": "original text prompt",
    "generated_at": "ISO timestamp",
    "generator_model": "claude-3-sonnet",
    "width": 20,
    "height": 15
  },
  "tiles": [
    ["wall", "wall", "wall", "floor", "floor"],
    ["wall", "floor", "floor", "floor", "wall"],
    ...
  ],
  "entities": [
    {
      "id": "ogre_1",
      "type": "ogre",
      "x": 5,
      "y": 3,
      "properties": {
        "health": 30,
        "aggressive": true
      }
    },
    {
      "id": "shop_1",
      "type": "shop",
      "x": 18,
      "y": 13,
      "properties": {
        "shopkeeper": "dwarf",
        "inventory": ["sword", "potion"]
      }
    }
  ],
  "regions": [
    {
      "id": "main_hall",
      "type": "room",
      "bounds": {"x1": 2, "y1": 2, "x2": 8, "y2": 6},
      "properties": {
        "lighting": "bright",
        "description": "A grand hall with high ceilings"
      }
    }
  ]
}
```

### Tile Types (Extensible)

**Core Types (v1.0)**:
- `wall`: Impassable barrier
- `floor`: Basic walkable terrain
- `door`: Passable connection between areas
- `water`: Passable but slow terrain

**Future Extensions**:
- `locked_door` (requires key)
- `destructible_wall` (can be broken)
- `lava` (damages player)
- `trap` (hidden hazard)
- `stairs_up`/`stairs_down`

### Entity Types (Extensible)

**Core Types (v1.0)**:
- `player`: Player starting position
- `ogre`: Basic enemy
- `goblin`: Weaker enemy
- `shop`: Trading post
- `chest`: Contains items

**Future Extensions**:
- `key` (unlocks doors)
- `potion` (consumable item)
- `weapon` (equipment)
- `npc` (non-player character)

## Script 1: Map Generator

### Purpose
Convert natural language prompts into structured map representations using an online LLM service.

### Input Format
```json
{
  "prompts": [
    "a dense maze with three ogres and a shop in the corner",
    "an open field with a small pond and two goblins",
    "a dungeon room with a locked chest behind destructible walls"
  ],
  "config": {
    "default_size": {"width": 20, "height": 15},
    "api_key": "sk-...",
    "model": "claude-3-sonnet-20240229",
    "temperature": 0.7
  }
}
```

### Processing Pipeline

1. **Prompt Analysis**: Extract key requirements from each prompt
   - Map size hints
   - Entity types and quantities
   - Terrain features
   - Spatial relationships

2. **LLM Generation**: Send structured prompt to online LLM
   ```
   Generate a roguelike map for: "{original_prompt}"
   
   Output format: JSON matching the provided schema
   Requirements:
   - Map size: {width}x{height}
   - Include all requested entities
   - Ensure map is fully connected (all floor tiles reachable)
   - Place entities logically based on prompt
   ```

3. **Post-Processing**: Validate and clean generated JSON
   - Schema validation
   - Connectivity checks
   - Bounds validation
   - Default property assignment

### Output Format
```json
{
  "results": [
    {
      "prompt_index": 0,
      "status": "success",
      "map": { /* structured map object */ },
      "generation_time": 2.3,
      "warnings": []
    }
  ],
  "summary": {
    "total_prompts": 3,
    "successful": 2,
    "failed": 1,
    "average_time": 2.1
  }
}
```

### Error Handling
- Invalid JSON → Retry with clearer instructions
- Schema violations → Attempt automatic fixes
- Impossible requests → Mark as failed with reason
- API failures → Exponential backoff retry

## Script 2: Map Verifier

### Purpose
Validate that structured maps match their original text prompts using a local LLM.

### Input Format
```json
{
  "test_cases": [
    {
      "prompt": "a dense maze with three ogres",
      "map": { /* structured map object */ },
      "test_id": "test_001"
    }
  ],
  "config": {
    "local_model": "llama3.1:8b",
    "backend": "ollama",
    "endpoint": "http://localhost:11434",
    "verification_strictness": "medium"
  }
}
```

### Verification Pipeline

1. **Map Analysis**: Extract quantitative features
   - Entity counts by type
   - Wall-to-floor ratio
   - Connectivity metrics
   - Spatial distribution analysis

2. **Text-to-Visual Conversion**: Generate human-readable representation
   ```
   Map Layout (20x15):
   ####################
   #..................#
   #..O.......O.......#
   #..................#
   #........S.........#
   ####################
   
   Entities:
   - 3x Ogre (O) at positions: (3,2), (12,2)
   - 1x Shop (S) at position: (9,4)
   
   Statistics:
   - Wall coverage: 45%
   - Open area: 55%
   - Connectivity: Fully connected
   ```

3. **LLM Verification**: Query local model for semantic matching
   ```
   Original request: "a dense maze with three ogres"
   
   Generated map analysis:
   {visual_representation}
   
   Evaluation criteria:
   1. Does this map match the request? (YES/NO)
   2. What aspects match well? (list)
   3. What aspects don't match? (list)
   4. Overall confidence score (1-10)
   
   Respond in JSON format only.
   ```

4. **Rule-Based Validation**: Programmatic checks
   - Exact entity counts
   - Required entity types present
   - Map size constraints
   - Connectivity requirements

### Verification Categories

**Quantitative Checks** (Rule-based):
- Entity counts: "three ogres" → exactly 3 ogre entities
- Positioning: "corner" → entity in corner quadrant
- Size: "small room" → area < threshold

**Qualitative Checks** (LLM-based):
- Density: "dense maze" vs "open field"
- Atmosphere: "dark dungeon" vs "bright meadow"
- Logical placement: entities in sensible locations

**Consistency Checks** (Hybrid):
- Map connectivity
- Entity placement validity
- Terrain logic (e.g., shops not in lava)

### Output Format
```json
{
  "results": [
    {
      "test_id": "test_001",
      "overall_score": 8.5,
      "passed": true,
      "verification_details": {
        "quantitative": {
          "entity_counts": {"ogre": {"expected": 3, "actual": 3, "passed": true}},
          "map_density": {"expected": "high", "actual": 0.65, "passed": true}
        },
        "qualitative": {
          "maze_like": {"score": 9, "comment": "Well-structured maze paths"},
          "atmosphere": {"score": 8, "comment": "Appropriately challenging feel"}
        },
        "consistency": {
          "connectivity": {"passed": true},
          "entity_placement": {"passed": true, "warnings": []}
        }
      },
      "llm_response": {
        "matches_request": true,
        "confidence": 8.5,
        "positive_aspects": ["correct ogre count", "maze-like structure"],
        "negative_aspects": ["could be slightly denser"]
      },
      "processing_time": 1.2
    }
  ],
  "summary": {
    "total_tests": 10,
    "passed": 8,
    "failed": 2,
    "average_score": 7.8,
    "common_failures": ["entity placement", "density interpretation"]
  }
}
```

## Local LLM Integration

### Ollama Setup
```bash
# Install and run ollama
ollama pull llama3.1:8b
ollama serve
```

### Model Requirements
- **Minimum**: 7B parameter model (llama3.1:7b)
- **Recommended**: 8B+ parameter model for better reasoning
- **Memory**: 8GB+ RAM for smooth operation
- **Alternative models**: mistral:7b, codellama:7b

### API Integration
- REST API calls to local endpoint
- Streaming vs batch processing options
- Error handling for model unavailability
- Fallback to smaller models if needed

## Configuration and Extensibility

### Map Schema Evolution
- Version field in metadata for backward compatibility
- New tile/entity types added to type registries
- Property validation schemas per type
- Migration utilities for schema updates

### Verification Rule Engine
```json
{
  "rules": {
    "entity_count_exact": {"weight": 1.0, "critical": true},
    "entity_count_approximate": {"weight": 0.7, "critical": false},
    "spatial_relationship": {"weight": 0.8, "critical": false},
    "atmosphere_match": {"weight": 0.6, "critical": false}
  }
}
```

### Performance Considerations
- Batch processing for multiple maps
- Caching of LLM responses
- Parallel processing where possible
- Progress tracking for long-running operations

This specification provides a solid foundation that can be incrementally extended with new features while maintaining backward compatibility and clear separation of concerns between generation and verification.

