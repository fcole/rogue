"""
Ollama-based tool generator that uses function calling to guarantee constraints.
Compatible with the existing ToolBasedMapGenerator interface.
"""
import json
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
        
        # Check if position is on floor
        if self.grid[y][x] != '.':
            return f"Warning: Entity {entity_type} placed at ({x},{y}) not on floor tile"
        
        if entity_type not in self.entities:
            self.entities[entity_type] = []
        
        self.entities[entity_type].append(EntityData(
            x=x, y=y, properties=properties or {}
        ))
        
        return f"Placed {entity_type} at ({x},{y})"
    
    def place_multiple_entities(self, entities: List[Dict[str, Any]]) -> str:
        """Place multiple entities at once for efficiency."""
        if not self.grid:
            return "Error: Must create grid first"
        
        results = []
        for entity_data in entities:
            entity_type = entity_data["entity_type"]
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
        
        return MapData(
            id=map_id,
            prompt=prompt,
            width=self.target_width,
            height=self.target_height,
            tiles=tiles,
            entities=self.entities,
            metadata={
                "wall_count": wall_count,
                "floor_count": floor_count,
                "door_count": door_count,
                "connectivity_verified": connectivity_verified
            },
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
        self.ollama_endpoint = self.config.get("ollama", {}).get("endpoint", "http://localhost:11434")
        self.model = self.config.get("ollama", {}).get("model", "deepseek-coder:33b-instruct")
        self.temperature = self.config.get("ollama", {}).get("temperature", 0.3)
        
        # Tool definitions in Ollama function calling format
        self.tools = [
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
        
        messages = [{
            "role": "user",
            "content": f"""Create a roguelike map for this prompt: "{prompt}"

CRITICAL REQUIREMENTS - READ CAREFULLY:

🎮 PLAYER PLACEMENT (ALWAYS REQUIRED):
- EVERY map MUST have exactly ONE player entity
- Use place_entity("player", x, y) to place the player
- Player must be on a floor tile (.) or door tile (+)
- Maps without players are unplayable and will fail verification!

🔗 CONNECTIVITY IS CRITICAL:
- Every floor tile (.) must be reachable from every other floor tile
- After placing each room, think: 'How does someone get here?'
- Use place_corridor(x1,y1,x2,y2) to connect separated areas
- Use place_door(x,y) to create doorways between rooms

AVOID THESE MISTAKES:
❌ Don't create walled-off 'ponds' or 'islands' without connections
❌ Don't place rooms without doors or corridors
❌ Don't forget to place a player entity (CRITICAL!)
✅ DO connect every room to the main area with doors or corridors
✅ DO always place exactly one player entity

BUILDING STEPS:
1. First create_grid(20, 15) to initialize 
2. Use place_room to create rooms for the scene
3. Use place_door and place_corridor to connect spaces
4. Use place_entity to add characters and objects
5. ALWAYS use place_entity("player", x, y) to add a player
6. Finish efficiently - avoid unnecessary status checks

CONNECTIVITY EXAMPLES:
✅ GOOD: Rooms connected by doors/corridors
❌ BAD: Isolated rooms with no connections

If you create a 'pond' or 'separate area', add a corridor or door to connect it!

Build a map that matches the prompt creatively while ensuring proper connectivity AND player placement."""
        }]
        
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
                    tool_results = []
                    
                    for tool_call in response["tool_calls"]:
                        result = self._execute_tool(
                            tool_call["name"],
                            tool_call["args"],
                            builder
                        )
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_call_id": tool_call["id"],
                            "content": result
                        })
                    
                    # Send tool results back to Ollama
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })
                    
                    iteration += 1
                    continue
                    
                else:
                    # Ollama is done with tool calls
                    break
                    
            except Exception as e:
                self.logger.error(f"Error during Ollama tool-based generation: {e}")
                raise
        
        if iteration >= max_iterations:
            self.logger.warning(f"Map generation hit iteration limit for {map_id}")
        
        # Check connectivity and give LLM a chance to fix issues
        if not builder._check_basic_connectivity():
            print(f"\n🔍 CONNECTIVITY DEBUG: Map {map_id} has connectivity issues")
            
            # Log detailed connectivity analysis
            total_accessible = sum(row.count('.') + row.count('+') for row in builder.grid)
            reachable_count = self._count_reachable_tiles(builder.grid)
            print(f"📊 Connectivity analysis: {reachable_count}/{total_accessible} tiles reachable")
            
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
                
                # Check if connectivity was fixed
                new_reachable = self._count_reachable_tiles(builder.grid)
                print(f"📊 After fix attempt: {new_reachable}/{total_accessible} tiles reachable")
                
                if builder._check_basic_connectivity():
                    print(f"🎉 Map {map_id} connectivity fixed successfully by LLM")
                    messages.append({
                        "role": "user",
                        "content": "✅ Excellent! You've successfully fixed the connectivity issues. Your map is now fully connected."
                    })
                else:
                    print(f"❌ Map {map_id} still has connectivity issues after LLM fix attempt")
                    print(f"📊 Connectivity check failed: {new_reachable}/{total_accessible} tiles reachable")
                
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
                "tool_choice": "auto"
            }
            
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            
            # Parse Ollama's function calling response
            if "message" in result:
                message = result["message"]
                content = message.get("content", "")
                tool_calls = message.get("tool_calls", [])
                
                return {
                    "content": content,
                    "tool_calls": tool_calls
                }
            else:
                return {"content": result.get("response", ""), "tool_calls": []}
                
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any], builder: OllamaGridBuilder) -> str:
        """Execute a tool call on the grid builder."""
        try:
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
            else:
                return f"Error: Unknown tool '{tool_name}'"
                
        except Exception as e:
            self.logger.error(f"Tool execution error: {e}")
            return f"Error executing {tool_name}: {str(e)}"
