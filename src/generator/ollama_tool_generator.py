"""
Ollama-based tool generator that uses function calling to guarantee constraints.
Compatible with the existing ToolBasedMapGenerator interface.
"""
import json
import os
import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import requests

from ..shared.utils import load_config, load_secrets
from ..shared.models import MapData, EntityData, GenerationResult


class OllamaGridBuilder:
    """Builds a roguelike map grid through Ollama function calls, ensuring dimensional constraints."""
    
    def __init__(self, width: int = 20, height: int = 15):
        self.target_width = width
        self.target_height = height
        self.grid: Optional[List[List[str]]] = None
        self.entities: Dict[str, List[EntityData]] = {}
        self.metadata: Dict[str, Any] = {}
        
    def create_grid(self, width: int, height: int) -> str:
        """Initialize a new grid with specified dimensions."""
        if width != self.target_width or height != self.target_height:
            return f"Error: Grid must be exactly {self.target_width}x{self.target_height}, got {width}x{height}"
        
        # Initialize with all walls
        self.grid = [['#' for _ in range(width)] for _ in range(height)]
        
        # Create interior space (will be refined by other tools)
        for i in range(1, height - 1):
            for j in range(1, width - 1):
                self.grid[i][j] = '.'
                
        return f"Created {width}x{height} grid with border walls"
    
    def place_room(self, x: int, y: int, width: int, height: int) -> str:
        """Create a rectangular room with walls and floor."""
        if not self.grid:
            return "Error: Must create grid first"
            
        if not self._validate_bounds(x, y, width, height):
            return f"Error: Room at ({x},{y}) size {width}x{height} exceeds grid bounds"
        
        # Place room walls and floor
        for i in range(y, y + height):
            for j in range(x, x + width):
                if i == y or i == y + height - 1:  # Top/bottom walls
                    self.grid[i][j] = '#'
                elif j == x or j == x + width - 1:  # Side walls  
                    self.grid[i][j] = '#'
                else:  # Interior floor
                    self.grid[i][j] = '.'
        
        return f"Placed {width}x{height} room at ({x},{y})"
    
    def place_door(self, x: int, y: int) -> str:
        """Place a door at the specified coordinates."""
        if not self.grid or not self._in_bounds(x, y):
            return f"Error: Invalid coordinates ({x},{y})"
        
        self.grid[y][x] = '+'
        return f"Placed door at ({x},{y})"
    
    def place_corridor(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """Create a corridor between two points."""
        if not self.grid:
            return "Error: Must create grid first"
        
        # Simple L-shaped corridor
        # Horizontal segment
        start_x, end_x = min(x1, x2), max(x1, x2)
        for x in range(start_x, end_x + 1):
            if self._in_bounds(x, y1):
                self.grid[y1][x] = '.'
        
        # Vertical segment  
        start_y, end_y = min(y1, y2), max(y1, y2)
        for y in range(start_y, end_y + 1):
            if self._in_bounds(x2, y):
                self.grid[y][x2] = '.'
                
        return f"Created corridor from ({x1},{y1}) to ({x2},{y2})"
    
    def place_entity(self, entity_type: str, x: int, y: int, properties: Optional[Dict] = None) -> str:
        """Place an entity at the specified coordinates."""
        if not self.grid or not self._in_bounds(x, y):
            return f"Error: Invalid coordinates ({x},{y})"

        # Treat door-like entity requests as a request to place a door tile
        et_lower = str(entity_type).strip().lower() if entity_type else ""
        if et_lower in {"door", "locked_door", "doorway"}:
            self.grid[y][x] = '+'
            # Record door metadata (e.g., locked) without polluting entities
            door_meta = {"x": x, "y": y}
            if et_lower == "locked_door" or (properties or {}).get("locked"):
                door_meta["locked"] = True
            self.metadata.setdefault("doors", []).append(door_meta)
            return f"Placed door at ({x},{y})"

        # Treat pond/water/lake as water tiles centered at (x,y)
        if et_lower in {"pond", "water", "lake"}:
            size = 3
            if properties and isinstance(properties, dict):
                size = int(properties.get("size", properties.get("radius", 3)) or 3)
                size = max(1, min(size, 6))  # clamp
            # Create a filled blob of '~' tiles within bounds
            half = size // 2
            for dy in range(-half, half + 1):
                for dx in range(-half, half + 1):
                    ny, nx = y + dy, x + dx
                    if self._in_bounds(nx, ny) and 0 < ny < self.target_height-1 and 0 < nx < self.target_width-1:
                        self.grid[ny][nx] = '~'
            self.metadata.setdefault("water_areas", []).append({"cx": x, "cy": y, "size": size, "source": et_lower})
            return f"Placed water area around ({x},{y}) size {size}"

        # Normalize/validate entity type against supported set
        norm = self._normalize_entity_type(entity_type)
        if not norm:
            # Track unknown entity types to help debugging
            self.metadata.setdefault("unknown_entities", []).append(entity_type)
            return f"Warning: Unknown entity type '{entity_type}' ignored"

        # Check if position is on floor
        if self.grid[y][x] != '.':
            return f"Warning: Entity {norm} placed at ({x},{y}) not on floor tile"

        if norm not in self.entities:
            self.entities[norm] = []

        self.entities[norm].append(EntityData(
            x=x, y=y, properties=properties or {}
        ))

        return f"Placed {norm} at ({x},{y})"
    
    def place_multiple_entities(self, entities: List[Dict[str, Any]]) -> str:
        """Place multiple entities at once for efficiency."""
        if not self.grid:
            return "Error: Must create grid first"

        results = []
        for entity_data in entities:
            raw_type = entity_data["entity_type"]
            entity_type = self._normalize_entity_type(raw_type)
            # Handle door-like entity requests inline
            rt_lower = str(raw_type).strip().lower() if raw_type else ""
            if rt_lower in {"door", "locked_door", "doorway"}:
                x = entity_data["x"]
                y = entity_data["y"]
                if not self._in_bounds(x, y):
                    results.append(f"Error: Invalid coordinates ({x},{y}) for door")
                    continue
                self.grid[y][x] = '+'
                door_meta = {"x": x, "y": y}
                if rt_lower == "locked_door" or entity_data.get("properties", {}).get("locked"):
                    door_meta["locked"] = True
                self.metadata.setdefault("doors", []).append(door_meta)
                results.append(f"Placed door at ({x},{y})")
                continue
            if rt_lower in {"pond", "water", "lake"}:
                x = entity_data["x"]
                y = entity_data["y"]
                if not self._in_bounds(x, y):
                    results.append(f"Error: Invalid coordinates ({x},{y}) for water")
                    continue
                size = 3
                props = entity_data.get("properties", {}) or {}
                try:
                    size = int(props.get("size", props.get("radius", 3)) or 3)
                except Exception:
                    size = 3
                size = max(1, min(size, 6))
                half = size // 2
                for dy in range(-half, half + 1):
                    for dx in range(-half, half + 1):
                        ny, nx = y + dy, x + dx
                        if self._in_bounds(nx, ny) and 0 < ny < self.target_height-1 and 0 < nx < self.target_width-1:
                            self.grid[ny][nx] = '~'
                self.metadata.setdefault("water_areas", []).append({"cx": x, "cy": y, "size": size, "source": rt_lower})
                results.append(f"Placed water area around ({x},{y}) size {size}")
                continue
            if not entity_type:
                self.metadata.setdefault("unknown_entities", []).append(raw_type)
                results.append(f"Warning: Unknown entity type '{raw_type}' ignored")
                continue
            x = entity_data["x"]
            y = entity_data["y"]
            properties = entity_data.get("properties", {})

            if not self._in_bounds(x, y):
                results.append(f"Error: Invalid coordinates ({x},{y}) for {entity_type}")
                continue

            # Check if position is on floor
            if self.grid[y][x] != '.':
                results.append(f"Warning: {entity_type} at ({x},{y}) not on floor tile")

            if entity_type not in self.entities:
                self.entities[entity_type] = []
            
            self.entities[entity_type].append(EntityData(
                x=x, y=y, properties=properties
            ))
            
            results.append(f"Placed {entity_type} at ({x},{y})")

        return "; ".join(results)

    def _normalize_entity_type(self, entity_type: str) -> Optional[str]:
        """Map various synonyms to the supported entity types.

        Supported: player, ogre, goblin, shop, chest
        Common synonyms we map:
          - shopkeeper/merchant/store -> shop
          - boss -> ogre
        Returns normalized lowercase name or None if unsupported.
        """
        if not entity_type:
            return None
        t = str(entity_type).strip().lower()
        synonyms = {
            "shopkeeper": "shop",
            "merchant": "shop",
            "store": "shop",
            "seller": "shop",
            "trader": "shop",
            "boss": "ogre",
            "ghost": "spirit",
            "ghosts": "spirit",
            "spirits": "spirit",
            "tombs": "tomb",
            "customer": "human",
            "customers": "human",
            "shopper": "human",
            "shoppers": "human",
            "patron": "human",
            "patrons": "human",
            "villager": "human",
            "villagers": "human",
        }
        if t in {"player", "ogre", "goblin", "shop", "chest", "tomb", "spirit", "human"}:
            return t
        if t in synonyms:
            return synonyms[t]
        return None
    
    def get_grid_status(self) -> str:
        """Get current grid dimensions and tile counts."""
        if not self.grid:
            return "No grid created yet"
        
        height = len(self.grid)
        width = len(self.grid[0]) if self.grid else 0
        
        wall_count = sum(row.count('#') for row in self.grid)
        floor_count = sum(row.count('.') for row in self.grid)
        door_count = sum(row.count('+') for row in self.grid)
        
        return f"Grid: {width}x{height}, Walls: {wall_count}, Floors: {floor_count}, Doors: {door_count}"

    def _set_water(self, x: int, y: int):
        if 0 < x < self.target_width - 1 and 0 < y < self.target_height - 1:
            self.grid[y][x] = '~'

    def place_water_area(self, cx: int, cy: int, shape: str = "circle", radius: int = 3, width: int = 6, height: int = 4) -> str:
        if not self.grid:
            return "Error: Must create grid first"
        shape = (shape or "circle").lower()
        if shape == "circle" or shape == "blob":
            r = max(1, radius)
            for yy in range(cy - r, cy + r + 1):
                for xx in range(cx - r, cx + r + 1):
                    if 0 <= xx < self.target_width and 0 <= yy < self.target_height:
                        if (xx - cx) * (xx - cx) + (yy - cy) * (yy - cy) <= r * r:
                            self._set_water(xx, yy)
        elif shape == "rectangle":
            w, h = max(1, width), max(1, height)
            x0, y0 = cx - w // 2, cy - h // 2
            for yy in range(y0, y0 + h):
                for xx in range(x0, x0 + w):
                    if 0 <= xx < self.target_width and 0 <= yy < self.target_height:
                        self._set_water(xx, yy)
        elif shape == "ellipse":
            a, b = max(1, width // 2), max(1, height // 2)
            for yy in range(cy - b, cy + b + 1):
                for xx in range(cx - a, cx + a + 1):
                    if 0 <= xx < self.target_width and 0 <= yy < self.target_height:
                        if ((xx - cx) * (xx - cx)) / (a * a + 1e-6) + ((yy - cy) * (yy - cy)) / (b * b + 1e-6) <= 1.0:
                            self._set_water(xx, yy)
        else:
            return f"Error: Unknown water shape '{shape}'"
        self.metadata.setdefault("water_areas", []).append({"cx": cx, "cy": cy, "shape": shape, "radius": radius, "width": width, "height": height})
        return f"Placed water area at ({cx},{cy}) shape {shape}"

    def place_river_path(self, points: List[Dict[str, int]], width: int = 2) -> str:
        if not self.grid:
            return "Error: Must create grid first"
        if not points or len(points) < 2:
            return "Error: River requires at least 2 points"
        w = max(1, min(int(width), 7))
        half = max(0, (w - 1) // 2)

        def draw_line(x0, y0, x1, y1):
            dx = abs(x1 - x0)
            dy = -abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx + dy
            x, y = x0, y0
            while True:
                for oy in range(-half, half + 1):
                    for ox in range(-half, half + 1):
                        nx, ny = x + ox, y + oy
                        if 0 <= nx < self.target_width and 0 <= ny < self.target_height:
                            self._set_water(nx, ny)
                if x == x1 and y == y1:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x += sx
                if e2 <= dx:
                    err += dx
                    y += sy

        for i in range(len(points) - 1):
            x0, y0 = int(points[i]["x"]), int(points[i]["y"])
            x1, y1 = int(points[i + 1]["x"]), int(points[i + 1]["y"])
            draw_line(x0, y0, x1, y1)
        self.metadata.setdefault("rivers", []).append({"points": points, "width": w})
        return f"Placed river of width {w} along {len(points)} points"
    
    def _validate_bounds(self, x: int, y: int, width: int, height: int) -> bool:
        """Check if a rectangle fits within grid bounds."""
        return (x >= 0 and y >= 0 and 
                x + width <= self.target_width and 
                y + height <= self.target_height)
    
    def _in_bounds(self, x: int, y: int) -> bool:
        """Check if coordinates are within grid bounds."""
        return (0 <= x < self.target_width and 
                0 <= y < self.target_height)
    
    def to_map_data(self, map_id: str, prompt: str) -> MapData:
        """Convert grid to MapData format."""
        if not self.grid:
            raise ValueError("No grid created")
        
        # Convert grid to tile string
        tiles = '\n'.join(''.join(row) for row in self.grid)
        
        # Count tiles for metadata
        wall_count = sum(row.count('#') for row in self.grid)
        floor_count = sum(row.count('.') for row in self.grid)
        door_count = sum(row.count('+') for row in self.grid)
        
        # Verify connectivity (simple check)
        connectivity_verified = self._check_basic_connectivity()
        # Base metadata plus any collected runtime metadata
        meta = {
            "wall_count": wall_count,
            "floor_count": floor_count,
            "door_count": door_count,
            "connectivity_verified": connectivity_verified
        }
        if self.metadata:
            try:
                meta.update(self.metadata)
            except Exception:
                pass

        return MapData(
            id=map_id,
            prompt=prompt,
            width=self.target_width,
            height=self.target_height,
            tiles=tiles,
            entities=self.entities,
            metadata=meta,
            generated_at=datetime.now().isoformat()
        )
    
    def _check_basic_connectivity(self) -> bool:
        """Basic connectivity check - ensure there are accessible floor tiles."""
        if not self.grid:
            return False
        
        # Convert grid to tiles string for shared connectivity check
        tiles_str = '\n'.join(''.join(row) for row in self.grid)
        from ..shared.connectivity import check_map_connectivity
        return check_map_connectivity(tiles_str, len(self.grid[0]), len(self.grid))


class OllamaToolBasedGenerator:
    """Map generator using Ollama function calling for guaranteed constraints."""
    
    def __init__(self, config_file: str = "generator.json"):
        self.config = load_config(config_file)
        self.logger = logging.getLogger(__name__)
        
        # Ollama configuration
        cfg_endpoint = self.config.get("ollama", {}).get("endpoint", "http://localhost:11434")
        cfg_model = self.config.get("ollama", {}).get("model", "deepseek-coder:33b-instruct")
        self.ollama_endpoint = os.getenv("OLLAMA_ENDPOINT", cfg_endpoint)
        self.model = os.getenv("OLLAMA_MODEL", cfg_model)
        self.temperature = self.config.get("ollama", {}).get("temperature", 0.3)
        
        # Tool definitions in Ollama function-calling format (OpenAI-compatible)
        base_tools = [
            {
                "name": "create_grid",
                "description": "Initialize a new grid with specified dimensions (must be exactly 20x15)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer", "const": 20},
                        "height": {"type": "integer", "const": 15}
                    },
                    "required": ["width", "height"]
                }
            },
            {
                "name": "place_water_area",
                "description": "Create a water area ('~' tiles) with a given shape centered at (cx,cy)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cx": {"type": "integer", "minimum": 0, "maximum": 19},
                        "cy": {"type": "integer", "minimum": 0, "maximum": 14},
                        "shape": {"type": "string", "enum": ["circle", "rectangle", "ellipse", "blob"], "default": "circle"},
                        "radius": {"type": "integer", "minimum": 1, "maximum": 9, "default": 3},
                        "width": {"type": "integer", "minimum": 1, "maximum": 19, "default": 6},
                        "height": {"type": "integer", "minimum": 1, "maximum": 14, "default": 4}
                    },
                    "required": ["cx", "cy"]
                }
            },
            {
                "name": "place_river_path",
                "description": "Create a river by drawing water along a path of points with a given width",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "points": {
                            "type": "array",
                            "minItems": 2,
                            "items": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}
                        },
                        "width": {"type": "integer", "minimum": 1, "maximum": 7, "default": 2}
                    },
                    "required": ["points"]
                }
            },
            {
                "name": "place_room", 
                "description": "Create a rectangular room with walls and floor",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "minimum": 0, "maximum": 19},
                        "y": {"type": "integer", "minimum": 0, "maximum": 14}, 
                        "width": {"type": "integer", "minimum": 3, "maximum": 18},
                        "height": {"type": "integer", "minimum": 3, "maximum": 13}
                    },
                    "required": ["x", "y", "width", "height"]
                }
            },
            {
                "name": "place_door",
                "description": "Place a door at specific coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "minimum": 0, "maximum": 19},
                        "y": {"type": "integer", "minimum": 0, "maximum": 14}
                    },
                    "required": ["x", "y"]
                }
            },
            {
                "name": "place_corridor",
                "description": "Create a corridor between two points",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x1": {"type": "integer", "minimum": 0, "maximum": 19},
                        "y1": {"type": "integer", "minimum": 0, "maximum": 14},
                        "x2": {"type": "integer", "minimum": 0, "maximum": 19},
                        "y2": {"type": "integer", "minimum": 0, "maximum": 14}
                    },
                    "required": ["x1", "y1", "x2", "y2"]
                }
            },
            {
                "name": "place_entity",
                "description": "Place an entity (goblin, shop, chest, player) at coordinates",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string", 
                            "enum": ["player", "ogre", "goblin", "shop", "chest"]
                        },
                        "x": {"type": "integer", "minimum": 0, "maximum": 19},
                        "y": {"type": "integer", "minimum": 0, "maximum": 14},
                        "properties": {"type": "object"}
                    },
                    "required": ["entity_type", "x", "y"]
                }
            },
            {
                "name": "place_multiple_entities",
                "description": "Place multiple entities at once for efficiency",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "entity_type": {
                                        "type": "string",
                                        "enum": ["player", "ogre", "goblin", "shop", "chest"]
                                    },
                                    "x": {"type": "integer", "minimum": 0, "maximum": 19},
                                    "y": {"type": "integer", "minimum": 0, "maximum": 14},
                                    "properties": {"type": "object"}
                                },
                                "required": ["entity_type", "x", "y"]
                            }
                        }
                    },
                    "required": ["entities"]
                }
            },
            {
                "name": "get_grid_status",
                "description": "Get current grid status including dimensions and tile counts",
                "parameters": {"type": "object", "properties": {}}
            }
        ]

        # Wrap tools with type:function for Ollama /api/chat compatibility
        self.tools = [{
            "type": "function",
            "function": t
        } for t in base_tools]
    
    def generate_maps(self, prompts: List[str]) -> Dict[str, Any]:
        """Generate maps for multiple prompts (interface compatibility with ToolBasedMapGenerator)."""
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
            map_id = f"map_{index:03d}"
            map_data = self.generate_map(prompt, map_id)
            
            return GenerationResult(
                prompt_index=index,
                status="success",
                generation_time=0.0,  # Will be set by caller
                warnings=[],
                error_message=None,
                map_data=map_data
            )
            
        except Exception as e:
            self.logger.error(f"Failed to generate map {index}: {e}")
            return GenerationResult(
                prompt_index=index,
                status="failed",
                generation_time=0.0,  # Will be set by caller
                warnings=[],
                error_message=str(e),
                map_data=None
            )
    
    def generate_map(self, prompt: str, map_id: str) -> MapData:
        """Generate a map using Ollama function calling."""
        self.logger.info(f"Generating map {map_id} with Ollama tools: {prompt}")
        
        builder = OllamaGridBuilder()
        executed_tool_calls: List[str] = []
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a tool-using map builder. Always respond by calling the provided tools. "
                    "Do not write prose. The first step must be create_grid with width=20 and height=15."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prompt: {prompt}\n"
                    "Goals: Build a connected 20x15 map, then place exactly one player on a floor or door tile. "
                    "Use place_room/place_door/place_corridor to ensure connectivity."
                ),
            },
        ]
        
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            try:
                # Call Ollama with function calling
                response = self._call_ollama_with_functions(messages)
                
                # Add Ollama's response to conversation
                if response.get("content"):
                    messages.append({
                        "role": "assistant", 
                        "content": response["content"]
                    })
                
                # Check if Ollama wants to use tools
                if response.get("tool_calls"):
                    # Execute tool calls and summarize results back plainly
                    summary_lines = []
                    for tool_call in response["tool_calls"]:
                        result = self._execute_tool(
                            tool_call["name"],
                            tool_call.get("args", {}),
                            builder,
                        )
                        if not str(result).startswith("Error"):
                            executed_tool_calls.append(tool_call["name"])
                        summary_lines.append(
                            f"{tool_call['name']}({tool_call.get('args', {})}) -> {result}"
                        )

                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "TOOL RESULTS:\n" + "\n".join(summary_lines) + "\nContinue building using tools."
                            ),
                        }
                    )
                    
                    iteration += 1
                    continue
                    
                else:
                    # No tool calls returned. Try a one-time pseudo-tool nudge to kickstart create_grid.
                    if iteration == 0 and not builder.grid:
                        pseudo = self._call_ollama_pseudo_tools(
                            messages
                            + [{
                                "role": "user",
                                "content": "Emit a JSON tool call to create_grid with width 20 and height 15.",
                            }]
                        )
                        pseudo_calls = pseudo.get("tool_calls", [])
                        if pseudo_calls:
                            summary_lines = []
                            for tool_call in pseudo_calls:
                                result = self._execute_tool(
                                    tool_call["name"], tool_call.get("args", {}), builder
                                )
                                if not str(result).startswith("Error"):
                                    executed_tool_calls.append(tool_call["name"])
                                summary_lines.append(
                                    f"{tool_call['name']}({tool_call.get('args', {})}) -> {result}"
                                )
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "TOOL RESULTS:\n" + "\n".join(summary_lines) + "\nContinue building using tools."
                                    ),
                                }
                            )
                            iteration += 1
                            continue
                    # Done with tool calls
                    break
                    
            except Exception as e:
                self.logger.error(f"Error during Ollama tool-based generation: {e}")
                raise
        
        if iteration >= max_iterations:
            self.logger.warning(f"Map generation hit iteration limit for {map_id}")
        
        # Check connectivity and give LLM a chance to fix issues
        if not builder._check_basic_connectivity():
            print(f"\n🔍 CONNECTIVITY DEBUG: Map {map_id} has connectivity issues")
            
            # Log detailed connectivity analysis (handle uninitialized grid)
            if builder.grid:
                total_accessible_before = sum(row.count('.') + row.count('+') for row in builder.grid)
                reachable_before = self._count_reachable_tiles(builder.grid)
            else:
                total_accessible_before = 0
                reachable_before = 0
            print(f"📊 Connectivity analysis: {reachable_before}/{total_accessible_before} tiles reachable")
            
            # Send connectivity warning with specific guidance
            connectivity_warning = self._generate_connectivity_warning(builder)
            print(f"⚠️ Connectivity warning: {connectivity_warning}")
            
            messages.append({
                "role": "user",
                "content": f"""⚠️ CONNECTIVITY WARNING: Your map has isolated areas that cannot be reached!

{connectivity_warning}

Use place_corridor() or place_door() to connect separated regions. Fix this connectivity issue and continue building."""
            })
            
            # Give LLM another chance to fix connectivity
            try:
                print(f"🤖 Sending connectivity fix request to LLM...")
                response = self._call_ollama_with_functions(messages) # Re-call Ollama to get updated messages
                print(f"📨 LLM response received")
                
                # Process any tool calls to fix connectivity
                tool_calls = response.get("tool_calls", []) # Extract tool calls from the new response
                if tool_calls:
                    print("🔧 Processing tool calls for connectivity fix...")
                    for tool_call in tool_calls:
                        print(f"🛠️ Tool call: {tool_call['name']} with input: {tool_call['args']}") # Use tool_call['args'] for arguments
                        result = self._execute_tool(
                            tool_call['name'],
                            tool_call['args'],
                            builder
                        )
                        print(f"✅ Tool execution result: {result}")
                
                # Check if connectivity was fixed (recompute totals after tool actions)
                new_reachable = self._count_reachable_tiles(builder.grid)
                total_accessible_after = (
                    sum(row.count('.') + row.count('+') for row in builder.grid)
                    if builder.grid else 0
                )
                print(f"📊 After fix attempt: {new_reachable}/{total_accessible_after} tiles reachable")
                
                if builder._check_basic_connectivity():
                    print(f"🎉 Map {map_id} connectivity fixed successfully by LLM")
                    messages.append({
                        "role": "user",
                        "content": "✅ Excellent! You've successfully fixed the connectivity issues. Your map is now fully connected."
                    })
                else:
                    print(f"❌ Map {map_id} still has connectivity issues after LLM fix attempt")
                    print(f"📊 Connectivity check failed: {new_reachable}/{total_accessible_after} tiles reachable")
                
            except Exception as e:
                print(f"💥 LLM failed to fix connectivity: {e}")
                import traceback
                print(f"📚 Full traceback: {traceback.format_exc()}")
        
        # Check for player placement and give LLM feedback if missing
        if not builder.entities.get("player"):
            print(f"\n🎮 PLAYER PLACEMENT DEBUG: Map {map_id} is missing a player entity!")
            
            messages.append({
                "role": "user",
                "content": f"""🎮 CRITICAL: Your map is missing a player entity!

Every roguelike map MUST have exactly one player entity for the player to start the game.

CURRENT STATUS:
- Map has {len(builder.entities.get('ogre', []))} ogres
- Map has {len(builder.entities.get('goblin', []))} goblins  
- Map has {len(builder.entities.get('shop', []))} shops
- Map has {len(builder.entities.get('chest', []))} chests
- ❌ Map has 0 players (REQUIRED!)

ACTION REQUIRED:
Use place_entity("player", x, y) to place a player at valid coordinates (x,y) on a floor tile (.) or door tile (+).

EXAMPLE:
place_entity("player", 10, 7)  # Places player at center of map

This is a critical requirement - maps without players are unplayable!"""
            })
            
            # Give LLM a chance to add the player
            try:
                print(f"🤖 Sending player placement request to LLM...")
                response = self._call_ollama_with_functions(messages) # Re-call Ollama to get updated messages
                print(f"📨 LLM response received")
                
                # Process any tool calls to add player
                tool_calls = response.get("tool_calls", []) # Extract tool calls from the new response
                if tool_calls:
                    print("🔧 Processing tool calls for player placement...")
                    for tool_call in tool_calls:
                        print(f"🛠️ Tool call: {tool_call['name']} with input: {tool_call['args']}") # Use tool_call['args'] for arguments
                        result = self._execute_tool(
                            tool_call['name'],
                            tool_call['args'],
                            builder
                        )
                        print(f"✅ Tool execution result: {result}")
                
                # Check if player was added
                if builder.entities.get("player"):
                    print(f"🎉 Map {map_id} player added successfully by LLM")
                    messages.append({
                        "role": "user",
                        "content": "✅ Excellent! You've successfully added a player entity. Your map is now playable."
                    })
                else:
                    print(f"❌ Map {map_id} still missing player after LLM fix attempt")
                    print(f"⚠️ WARNING: This map will fail verification due to missing player!")
                
            except Exception as e:
                print(f"💥 LLM failed to add player: {e}")
                print(f"⚠️ WARNING: This map will fail verification due to missing player!")
        
        # Attach tool call stats
        try:
            builder.metadata["executed_tool_calls"] = executed_tool_calls
            builder.metadata["tool_call_count"] = len(executed_tool_calls)
        except Exception:
            pass

        # Convert builder result to MapData
        try:
            return builder.to_map_data(map_id, prompt)
        except ValueError as e:
            self.logger.error(f"Failed to create map data: {e}")
            # Fallback - create a minimal valid map
            builder.create_grid(20, 15)
            builder.place_room(2, 2, 16, 11)
            builder.place_door(10, 2)
            return builder.to_map_data(map_id, prompt)
    
    def _call_ollama_with_functions(self, messages: List[Dict]) -> Dict[str, Any]:
        """Call Ollama with function calling support."""
        try:
            url = f"{self.ollama_endpoint}/api/chat"
            
            # Convert messages to Ollama format
            ollama_messages = []
            for msg in messages:
                if msg["role"] == "user":
                    ollama_messages.append({
                        "role": "user",
                        "content": msg["content"]
                    })
                elif msg["role"] == "assistant":
                    ollama_messages.append({
                        "role": "assistant",
                        "content": msg["content"]
                    })
            
            payload = {
                "model": self.model,
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature
                },
                "tools": self.tools,
                "tool_choice": "required"
            }
            
            response = requests.post(url, json=payload, timeout=120)
            try:
                response.raise_for_status()
            except requests.HTTPError as http_err:
                # Fallback to OpenAI-compatible endpoint if /api/chat is missing
                if response.status_code == 404:
                    oai_url = f"{self.ollama_endpoint}/v1/chat/completions"
                    # OpenAI-compatible payload
                    oai_payload = {
                        "model": self.model,
                        "messages": [
                            {"role": m["role"], "content": m["content"]}
                            for m in ollama_messages
                        ],
                        "tools": self.tools,
                        "tool_choice": "auto",
                        "temperature": self.temperature,
                        "stream": False,
                    }
                    oai_resp = requests.post(oai_url, json=oai_payload, timeout=120)
                    oai_resp.raise_for_status()
                    oai = oai_resp.json()
                    choice = (oai.get("choices") or [{}])[0]
                    msg = choice.get("message", {})
                    tool_calls = msg.get("tool_calls", [])
                    content = msg.get("content", "")
                    norm_calls = []
                    for tc in tool_calls or []:
                        fn = tc.get("function", {})
                        name = fn.get("name")
                        args = fn.get("arguments")
                        if isinstance(args, str):
                            import json as _json
                            try:
                                args = _json.loads(args)
                            except Exception:
                                args = {}
                        if name:
                            norm_calls.append({"name": name, "args": args or {}})
                    return {"content": content, "tool_calls": norm_calls}
                raise
            
            result = response.json()
            
            # Parse Ollama's function calling response
            if "message" in result:
                message = result["message"]
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])
                norm_calls: List[Dict[str, Any]] = []
                # 1) Normalize native tool_calls if present
                for tc in tool_calls or []:
                    name = tc.get("name") or (tc.get("function") or {}).get("name")
                    args = tc.get("args") or (tc.get("function") or {}).get("arguments")
                    if isinstance(args, str):
                        import json as _json
                        try:
                            args = _json.loads(args)
                        except Exception:
                            args = {}
                    if name:
                        norm_calls.append({"name": name, "args": args or {}})
                # 2) Heuristic: some models return a single function call as JSON in content
                if not norm_calls and isinstance(content, str):
                    import json as _json
                    text = content.strip()
                    try:
                        if text and (text[0] == '{' and text[-1] == '}'):
                            obj = _json.loads(text)
                            name = obj.get("name") or (obj.get("function") or {}).get("name")
                            args = obj.get("args") or obj.get("arguments") or (obj.get("function") or {}).get("arguments")
                            if isinstance(args, str):
                                try:
                                    args = _json.loads(args)
                                except Exception:
                                    args = {}
                            if name:
                                norm_calls.append({"name": name, "args": args or {}})
                        elif text and text[0] == '[' and text[-1] == ']':
                            arr = _json.loads(text)
                            for item in arr:
                                name = item.get("name") or (item.get("function") or {}).get("name")
                                args = item.get("args") or item.get("arguments") or (item.get("function") or {}).get("arguments")
                                if isinstance(args, str):
                                    try:
                                        args = _json.loads(args)
                                    except Exception:
                                        args = {}
                                if name:
                                    norm_calls.append({"name": name, "args": args or {}})
                    except Exception:
                        pass
                return {"content": content, "tool_calls": norm_calls}
            else:
                return {"content": result.get("response", ""), "tool_calls": []}
                
        except Exception as e:
            # Last resort: pseudo-tool mode via /api/generate
            try:
                return self._call_ollama_pseudo_tools(messages)
            except Exception:
                raise Exception(f"Ollama API error: {str(e)}")

    def _call_ollama_pseudo_tools(self, messages: List[Dict]) -> Dict[str, Any]:
        """Simulate tool use over /api/generate by asking for JSON tool calls.

        Returns a dict with keys: content, tool_calls (list of {name,args}).
        """
        import json as _json
        url = f"{self.ollama_endpoint}/api/generate"

        # Flatten chat history
        convo = []
        for m in messages:
            role = m.get("role")
            content = m.get("content")
            if isinstance(content, list):
                content = _json.dumps(content)
            convo.append(f"[{role}] {content}")
        base = "\n".join(convo)

        tool_schema = [
            {"name": t["function"]["name"], "parameters": t["function"].get("parameters", {})}
            for t in self.tools
        ]

        instruction = (
            "Emit ONLY a JSON array of tool calls to execute next. "
            "Each item must be an object with 'name' (function name) and 'args' (object). "
            "Use these tools: " + _json.dumps(tool_schema) + ". No prose. JSON array only."
        )

        payload = {
            "model": self.model,
            "prompt": base + "\n\n" + instruction,
            "stream": False,
            "options": {"temperature": self.temperature},
        }

        r = requests.post(url, json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        text = (data.get("response") or "").strip()

        # Extract first JSON array
        tool_calls: List[Dict[str, Any]] = []
        try:
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                arr = _json.loads(text[start:end+1])
                for item in arr:
                    name = item.get("name")
                    args = item.get("args", {})
                    if isinstance(args, str):
                        try:
                            args = _json.loads(args)
                        except Exception:
                            args = {}
                    if name:
                        tool_calls.append({"name": name, "args": args})
        except Exception:
            pass

        return {"content": text, "tool_calls": tool_calls}
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any], builder: OllamaGridBuilder) -> str:
        """Execute a tool call on the grid builder."""
        try:
            # Light argument normalization for robustness
            if tool_name == "place_water_area":
                ti = dict(tool_input or {})
                if "cx" not in ti and "x" in ti:
                    ti["cx"] = ti.pop("x")
                if "cy" not in ti and "y" in ti:
                    ti["cy"] = ti.pop("y")
                shape = (ti.get("shape") or "circle").lower()
                if shape not in {"circle", "rectangle", "ellipse", "blob"}:
                    ti["shape"] = "circle"
                tool_input = ti
            elif tool_name == "place_river_path":
                ti = dict(tool_input or {})
                pts = ti.get("points") or []
                norm_pts = []
                for p in pts:
                    if "x" in p and "y" in p:
                        norm_pts.append({"x": int(p["x"]), "y": int(p["y"])})
                    elif "cx" in p and "cy" in p:
                        norm_pts.append({"x": int(p["cx"]), "y": int(p["cy"])})
                if norm_pts:
                    ti["points"] = norm_pts
                tool_input = ti
            if tool_name == "create_grid":
                return builder.create_grid(**tool_input)
            elif tool_name == "place_room":
                return builder.place_room(**tool_input)
            elif tool_name == "place_door":
                return builder.place_door(**tool_input)
            elif tool_name == "place_corridor":
                return builder.place_corridor(**tool_input)
            elif tool_name == "place_entity":
                return builder.place_entity(**tool_input)
            elif tool_name == "place_multiple_entities":
                return builder.place_multiple_entities(**tool_input)
            elif tool_name == "get_grid_status":
                return builder.get_grid_status()
            elif tool_name == "place_water_area":
                return builder.place_water_area(**tool_input)
            elif tool_name == "place_river_path":
                return builder.place_river_path(**tool_input)
            else:
                return f"Error: Unknown tool '{tool_name}'"
                
        except Exception as e:
            self.logger.error(f"Tool execution error: {e}")
            return f"Error executing {tool_name}: {str(e)}"

    def _count_reachable_tiles(self, grid: List[List[str]]) -> int:
        if not grid:
            return 0
        tiles_str = '\n'.join(''.join(row) for row in grid)
        from ..shared.connectivity import count_reachable_tiles
        return count_reachable_tiles(tiles_str, len(grid[0]), len(grid))

    def _find_isolated_regions(self, grid: List[List[str]]) -> List[Dict[str, Any]]:
        if not grid:
            return []
        tiles_str = '\n'.join(''.join(row) for row in grid)
        from ..shared.connectivity import find_isolated_regions
        return find_isolated_regions(tiles_str, len(grid[0]), len(grid))

    def _generate_connectivity_warning(self, builder: OllamaGridBuilder) -> str:
        if not builder.grid:
            return "Grid not created yet. Use create_grid(20,15) first."
        regions = self._find_isolated_regions(builder.grid)
        if not regions:
            return "No specific isolated regions found."
        warning = "Found these isolated areas:\n"
        for i, region in enumerate(regions[:3]):
            warning += f"- Region {i+1}: {region['size']} floor tiles around ({region['center_x']}, {region['center_y']})\n"
        warning += "\nSUGGESTIONS TO FIX:\n"
        warning += "1. Use place_door(x,y) to create doorways between rooms\n"
        warning += "2. Use place_corridor(x1,y1,x2,y2) to connect separated areas\n"
        warning += "3. Ensure every room has at least one connection to other areas\n"
        return warning
