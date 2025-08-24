import json
import time
from typing import List, Dict, Any
from ..shared.models import MapData, GenerationResult, EntityType, EntityData
from ..shared.llm_client import LLMClient
from ..shared.utils import load_config, validate_map_connectivity, count_tiles


class MapGenerator:
    def __init__(self, config_file: str = "generator.json"):
        self.config = load_config(config_file)
        llm_config = self.config["llm"].copy()
        provider = llm_config.pop("provider")
        self.llm = LLMClient.create(provider, **llm_config)

    def generate_maps(self, prompts: List[str]) -> Dict[str, Any]:
        """Generate maps for multiple prompts."""
        results = []
        total_time = 0
        
        for i, prompt in enumerate(prompts):
            start_time = time.time()
            result = self._generate_single_map(prompt, i)
            generation_time = time.time() - start_time
            result.generation_time = generation_time
            total_time += generation_time
            results.append(result)
        
        # Summary
        successful = len([r for r in results if r.status == "success"])
        summary = {
            "total_prompts": len(prompts),
            "successful": successful,
            "failed": len(prompts) - successful,
            "average_time": total_time / len(prompts) if prompts else 0
        }
        
        return {
            "results": results,
            "summary": summary
        }

    def _generate_single_map(self, prompt: str, index: int) -> GenerationResult:
        """Generate a single map from a prompt."""
        try:
            # Create the generation prompt
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(prompt)
            
            # Query LLM
            response = self.llm.query(user_prompt, system_prompt)
            
            # Parse JSON response
            map_data = self._parse_llm_response(response, prompt, f"map_{index:03d}")
            
            # Validate the map
            warnings = self._validate_map(map_data)
            
            return GenerationResult(
                prompt_index=index,
                status="success",
                map_data=map_data,
                generation_time=0,  # Will be set by caller
                warnings=warnings
            )
            
        except Exception as e:
            return GenerationResult(
                prompt_index=index,
                status="failed",
                map_data=None,
                generation_time=0,
                warnings=[],
                error_message=str(e)
            )

    def _build_system_prompt(self) -> str:
        return """You are a roguelike map generator. Generate maps as JSON objects with the following structure:

{
  "width": 20,
  "height": 15,
  "tiles": [
    "####################",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "#..................#",
    "####################"
  ],
  "entities": {
    "ogre": [{"x": 5, "y": 3}],
    "goblin": [{"x": 10, "y": 7}],
    "shop": [{"x": 18, "y": 13}]
  }
}

CRITICAL DIMENSION REQUIREMENTS:
- The "tiles" field MUST be an array of exactly {height} strings
- Each string in the array MUST be exactly {width} characters long
- NO EXCEPTIONS - wrong dimensions will cause automatic failure
- Count characters carefully: "####################" = exactly 20 characters
- Example: For 20x15 map, you need 15 strings, each exactly 20 characters

Tile characters:
- # = wall (used for boundaries and obstacles)
- . = floor (walkable space)
- + = door (connections between areas)  
- ~ = water (special terrain)

Available entity types: player, ogre, goblin, shop, chest

STRICT RULES:
1. Each row must be EXACTLY {width} characters - count carefully!
2. Must have EXACTLY {height} rows in the tiles array
3. All floor tiles must be connected (reachable from each other)
4. Place entities only on floor tiles (.) - never on walls (#)
5. Surround the entire map with walls (#) on all borders
6. Include all entities mentioned in the prompt
7. Verify your character count before responding

Example of correct 20-character row: "####################" (count: 1,2,3...20 ✓)
Example of incorrect row: "###################" (count: 1,2,3...19 ✗)"""

    def _build_user_prompt(self, prompt: str) -> str:
        width = self.config["map_defaults"]["width"]
        height = self.config["map_defaults"]["height"]
        
        return f"""Generate a {width}x{height} roguelike map for: "{prompt}"

CRITICAL: Use the ARRAY format for tiles, NOT a single string!
- "tiles": ["row1", "row2", "row3", ...] ✓ CORRECT
- "tiles": "row1\\nrow2\\nrow3..." ✗ WRONG

Each of the {height} strings in the tiles array must be exactly {width} characters.

COMMON ERROR TO AVOID: When creating repeating patterns, count carefully!
- "#....##....##....##" = 19 chars ✗ TOO SHORT
- "#....##....##....###" = 20 chars ✓ CORRECT

Return only valid JSON matching the specified format. No additional text."""

    def _parse_llm_response(self, response: str, prompt: str, map_id: str) -> MapData:
        """Parse LLM response into MapData object."""
        try:
            # Extract JSON from response (in case there's extra text)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response)
            
            # Handle both old format (string with \n) and new format (array of strings)
            tiles_data = data.get("tiles", "")
            if isinstance(tiles_data, list):
                # New format: array of strings
                tiles_string = '\n'.join(tiles_data)
            else:
                # Old format: single string with \n separators
                tiles_string = tiles_data
            
            # Convert entities dict to our format
            entities = {}
            for entity_type, entity_list in data.get("entities", {}).items():
                if entity_type in [e.value for e in EntityType]:
                    entities[EntityType(entity_type)] = [
                        EntityData(x=e["x"], y=e["y"], properties=e.get("properties", {}))
                        for e in entity_list
                    ]
            
            # Calculate metadata
            tile_counts = count_tiles(tiles_string)
            metadata = {
                "wall_count": tile_counts["wall"],
                "floor_count": tile_counts["floor"],
                "connectivity_verified": validate_map_connectivity(
                    tiles_string, data["width"], data["height"]
                )
            }
            
            return MapData(
                id=map_id,
                prompt=prompt,
                width=data["width"],
                height=data["height"],
                tiles=tiles_string,  # Store as string for compatibility
                entities=entities,
                metadata=metadata
            )
            
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")
        except KeyError as e:
            raise Exception(f"Missing required field: {str(e)}")

    def _validate_map(self, map_data: MapData) -> List[str]:
        """Validate generated map and return warnings."""
        warnings = []
        
        # Check map dimensions first
        lines = map_data.tiles.strip().split('\n')
        
        # Check if we have the right number of rows
        if len(lines) != map_data.height:
            warnings.append(f"Map has {len(lines)} rows, expected {map_data.height}")
        
        # Check if each row has the right number of columns
        dimension_errors = []
        for i, line in enumerate(lines):
            if len(line) != map_data.width:
                dimension_errors.append(f"Row {i} has {len(line)} chars, expected {map_data.width}")
        
        if dimension_errors:
            warnings.append(f"Map dimension errors: {'; '.join(dimension_errors[:3])}" + 
                          (f" (+{len(dimension_errors)-3} more)" if len(dimension_errors) > 3 else ""))
        
        # Only check connectivity if dimensions are correct (avoid crashes)
        if not dimension_errors:
            if not map_data.metadata.get("connectivity_verified", False):
                warnings.append("Map tiles are not fully connected")
        else:
            warnings.append("Skipping connectivity check due to dimension errors")
        
        # Check entity placement (with bounds checking)
        for entity_type, entity_list in map_data.entities.items():
            for entity in entity_list:
                if entity.y >= len(lines):
                    warnings.append(f"{entity_type.value} at ({entity.x},{entity.y}) outside map bounds (y >= {len(lines)})")
                elif entity.x >= len(lines[entity.y]):
                    warnings.append(f"{entity_type.value} at ({entity.x},{entity.y}) outside row bounds (x >= {len(lines[entity.y])})")
                elif lines[entity.y][entity.x] != '.':
                    warnings.append(f"{entity_type.value} at ({entity.x},{entity.y}) not on floor tile")
        
        # Check map borders (only if dimensions are correct)
        if not dimension_errors and lines:
            top_bottom_walls = all(c == '#' for c in lines[0]) and all(c == '#' for c in lines[-1])
            side_walls = all(len(line) > 0 and line[0] == '#' and line[-1] == '#' for line in lines)
            if not (top_bottom_walls and side_walls):
                warnings.append("Map is not properly surrounded by walls")
        
        return warnings