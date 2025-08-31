"""
DSL-based map generator with selective checkpointing for efficient token usage.

The DSL supports:
- Basic map construction (grid, rooms, corridors, doors)
- Entity placement 
- Water features
- Strategic checkpointing with selective verification
- Error recovery and debugging

Example DSL program:
```
grid(20, 15)
room("main", 2, 2, 16, 8)
room("side", 16, 10, 4, 4)
checkpoint("rooms_placed")

corridor(18, 8, 18, 10)
door(18, 9)
checkpoint("connected", verify_connectivity=True)

spawn(player, 10, 5)
spawn(ogre, 18, 12)
checkpoint("complete", full_verification=True)
```
"""

import json
import logging
import re
import time
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime

from ..shared.utils import load_config, load_secrets
from ..shared.models import MapData, EntityData, GenerationResult
from ..shared.connectivity import check_map_connectivity


class DSLExecutionError(Exception):
    """Error during DSL program execution."""
    def __init__(self, message: str, line_number: int = None, command: str = None):
        self.line_number = line_number
        self.command = command
        super().__init__(message)


class DSLMapBuilder:
    """Executes DSL commands to build a roguelike map."""
    
    def __init__(self, width: int = 20, height: int = 15):
        self.target_width = width
        self.target_height = height
        self.grid: Optional[List[List[str]]] = None
        self.entities: Dict[str, List[EntityData]] = {}
        self.checkpoints: Dict[str, Dict[str, Any]] = {}
        self.last_checkpoint = None
        
    def execute_command(self, command: str, args: List[Any], kwargs: Dict[str, Any]) -> str:
        """Execute a single DSL command."""
        if command == "grid":
            return self._cmd_grid(*args, **kwargs)
        elif command == "room":
            return self._cmd_room(*args, **kwargs)
        elif command == "corridor":
            return self._cmd_corridor(*args, **kwargs)
        elif command == "door":
            return self._cmd_door(*args, **kwargs)
        elif command == "spawn":
            return self._cmd_spawn(*args, **kwargs)
        elif command == "water_area":
            return self._cmd_water_area(*args, **kwargs)
        elif command == "river":
            return self._cmd_river(*args, **kwargs)
        elif command == "checkpoint":
            return self._cmd_checkpoint(*args, **kwargs)
        else:
            raise DSLExecutionError(f"Unknown command: {command}")
    
    def _cmd_grid(self, width: int, height: int) -> str:
        """Initialize grid: grid(20, 15)"""
        if width != self.target_width or height != self.target_height:
            raise DSLExecutionError(f"Grid must be {self.target_width}x{self.target_height}, got {width}x{height}")
        
        self.grid = [['#' for _ in range(width)] for _ in range(height)]
        
        # Create interior space
        for i in range(1, height - 1):
            for j in range(1, width - 1):
                self.grid[i][j] = '.'
        
        return f"Created {width}x{height} grid"
    
    def _cmd_room(self, name: str, x: int, y: int, width: int, height: int) -> str:
        """Create room: room("tavern", 2, 2, 10, 8)"""
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        
        if not self._validate_bounds(x, y, width, height):
            raise DSLExecutionError(f"Room '{name}' at ({x},{y}) size {width}x{height} exceeds bounds")
        
        # Place room walls and floor
        for i in range(y, y + height):
            for j in range(x, x + width):
                if i == y or i == y + height - 1:  # Top/bottom walls
                    self.grid[i][j] = '#'
                elif j == x or j == x + width - 1:  # Side walls  
                    self.grid[i][j] = '#'
                else:  # Interior floor
                    self.grid[i][j] = '.'
        
        return f"Created room '{name}' at ({x},{y}) size {width}x{height}"
    
    def _cmd_corridor(self, x1: int, y1: int, x2: int, y2: int) -> str:
        """Create corridor: corridor(10, 5, 15, 8)"""
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        
        # Simple L-shaped corridor
        start_x, end_x = min(x1, x2), max(x1, x2)
        for x in range(start_x, end_x + 1):
            if self._in_bounds(x, y1):
                self.grid[y1][x] = '.'
        
        start_y, end_y = min(y1, y2), max(y1, y2)
        for y in range(start_y, end_y + 1):
            if self._in_bounds(x2, y):
                self.grid[y][x2] = '.'
        
        return f"Created corridor from ({x1},{y1}) to ({x2},{y2})"
    
    def _cmd_door(self, x: int, y: int, **properties) -> str:
        """Place door: door(10, 5) or door(10, 5, locked=true)"""
        if not self.grid or not self._in_bounds(x, y):
            raise DSLExecutionError(f"Invalid door coordinates ({x},{y})")

        self.grid[y][x] = '+'
        return f"Placed door at ({x},{y})"
    
    def _cmd_spawn(self, entity_type: str, x: int, y: int, **properties) -> str:
        """Spawn entity: spawn(player, 10, 5) or spawn(ogre, 5, 8, hp=50)"""
        if not self.grid or not self._in_bounds(x, y):
            raise DSLExecutionError(f"Invalid spawn coordinates ({x},{y})")
        
        # Normalize entity type
        entity_type = self._normalize_entity_type(entity_type)
        if not entity_type:
            raise DSLExecutionError(f"Unknown entity type: {entity_type}")
        
        # Check if position is on floor or door
        if self.grid[y][x] not in ['.', '+']:
            return f"Warning: {entity_type} spawned at ({x},{y}) not on floor/door tile"
        
        if entity_type not in self.entities:
            self.entities[entity_type] = []
        
        self.entities[entity_type].append(EntityData(
            x=x, y=y, properties=properties
        ))
        
        return f"Spawned {entity_type} at ({x},{y})"
    
    def _cmd_water_area(self, x: int, y: int, shape: str = "circle", radius: int = 3,
                       width: int = 6, height: int = 4, **properties) -> str:
        """Create water area: water_area(10, 8, "circle", radius=4)"""
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        
        if shape.lower() == "circle":
            for yy in range(y - radius, y + radius + 1):
                for xx in range(x - radius, x + radius + 1):
                    if (0 < xx < self.target_width - 1 and 
                        0 < yy < self.target_height - 1 and
                        (xx - x) ** 2 + (yy - y) ** 2 <= radius ** 2):
                        self.grid[yy][xx] = '~'
        elif shape.lower() == "rectangle":
            x0, y0 = x - width // 2, y - height // 2
            for yy in range(y0, y0 + height):
                for xx in range(x0, x0 + width):
                    if 0 < xx < self.target_width - 1 and 0 < yy < self.target_height - 1:
                        self.grid[yy][xx] = '~'
        else:
            raise DSLExecutionError(f"Unknown water shape: {shape}")
        
        return f"Created {shape} water area at ({x},{y})"
    
    def _cmd_river(self, points: List[Tuple[int, int]], width: int = 2, **properties) -> str:
        """Create river: river([(5,5), (10,8), (15,12)], width=3)"""
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        
        if len(points) < 2:
            raise DSLExecutionError("River requires at least 2 points")
        
        half_width = max(0, (width - 1) // 2)
        
        def draw_line(x0, y0, x1, y1):
            # Bresenham's line algorithm with width
            dx = abs(x1 - x0)
            dy = -abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx + dy
            x, y = x0, y0
            
            while True:
                for oy in range(-half_width, half_width + 1):
                    for ox in range(-half_width, half_width + 1):
                        nx, ny = x + ox, y + oy
                        if 0 < nx < self.target_width - 1 and 0 < ny < self.target_height - 1:
                            self.grid[ny][nx] = '~'
                
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
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            draw_line(x0, y0, x1, y1)
        
        return f"Created river through {len(points)} points with width {width}"
    
    def _cmd_checkpoint(self, name: str, verify_connectivity: bool = False,
                       verify_entities: bool = False, full_verification: bool = False,
                       stats: bool = False, **properties) -> str:
        """Create checkpoint: checkpoint("rooms_done", verify_connectivity=True)"""
        if not self.grid:
            raise DSLExecutionError("Cannot checkpoint without grid")
        
        # Store checkpoint state
        checkpoint_data = {
            "grid_state": [row[:] for row in self.grid],  # Deep copy
            "entities_state": dict(self.entities),  # Copy entities
            "timestamp": datetime.now().isoformat()
        }
        
        # Build checkpoint report
        report = [f"📍 CHECKPOINT: {name}"]
        
        # Always show map visualization
        report.append("\nMap:")
        report.append(self._get_grid_visualization())
        
        # Optional statistics
        if stats or full_verification:
            wall_count = sum(row.count('#') for row in self.grid)
            floor_count = sum(row.count('.') for row in self.grid)
            door_count = sum(row.count('+') for row in self.grid)
            water_count = sum(row.count('~') for row in self.grid)
            
            report.append(f"\nStats: {wall_count} walls, {floor_count} floors, {door_count} doors, {water_count} water")
        
        # Optional connectivity check
        if verify_connectivity or full_verification:
            tiles_str = '\n'.join(''.join(row) for row in self.grid)
            connected = check_map_connectivity(tiles_str, self.target_width, self.target_height)
            status = "✅ CONNECTED" if connected else "❌ NOT CONNECTED"
            report.append(f"\nConnectivity: {status}")
        
        # Optional entity verification
        if verify_entities or full_verification:
            total_entities = sum(len(entities) for entities in self.entities.values())
            has_player = len(self.entities.get("player", [])) == 1
            player_status = "✅ PLAYER PRESENT" if has_player else "❌ NO PLAYER"
            report.append(f"\nEntities: {total_entities} total, {player_status}")
        
        # Store checkpoint
        self.checkpoints[name] = checkpoint_data
        self.last_checkpoint = name
        
        return "\n".join(report)
    
    def _normalize_entity_type(self, entity_type: str) -> Optional[str]:
        """Normalize entity type names."""
        if not entity_type:
            return None
        
        t = str(entity_type).strip().lower()
        if t in {"player", "ogre", "goblin", "shop", "chest", "tomb", "spirit", "human"}:
            return t
        
        synonyms = {
            "ghost": "spirit", "customer": "human", "merchant": "shop",
            "store": "shop", "treasure": "chest"
        }
        return synonyms.get(t)
    
    def _validate_bounds(self, x: int, y: int, width: int, height: int) -> bool:
        """Check if rectangle fits within grid bounds."""
        return (x >= 0 and y >= 0 and 
                x + width <= self.target_width and 
                y + height <= self.target_height)
    
    def _in_bounds(self, x: int, y: int) -> bool:
        """Check if coordinates are within grid bounds."""
        return (0 <= x < self.target_width and 
                0 <= y < self.target_height)
    
    def _get_grid_visualization(self) -> str:
        """Get ASCII visualization of current grid."""
        if not self.grid:
            return "No grid created"
        
        lines = []
        for row in self.grid:
            lines.append(''.join(row))
        return '\n'.join(lines)
    
    def to_map_data(self, map_id: str, prompt: str) -> MapData:
        """Convert to MapData format."""
        if not self.grid:
            raise ValueError("No grid created")
        
        tiles = '\n'.join(''.join(row) for row in self.grid)
        
        # Count tiles
        wall_count = sum(row.count('#') for row in self.grid)
        floor_count = sum(row.count('.') for row in self.grid)
        door_count = sum(row.count('+') for row in self.grid)
        water_count = sum(row.count('~') for row in self.grid)
        
        # Check connectivity
        connectivity_verified = check_map_connectivity(tiles, self.target_width, self.target_height)
        
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
                "water_count": water_count,
                "connectivity_verified": connectivity_verified,
                "checkpoints_used": list(self.checkpoints.keys()),
                "generation_method": "dsl"
            },
            generated_at=datetime.now().isoformat()
        )


class DSLParser:
    """Parses DSL programs into executable commands."""
    
    def parse_program(self, program: str) -> List[Tuple[int, str, List[Any], Dict[str, Any]]]:
        """Parse DSL program into (line_num, command, args, kwargs) tuples."""
        commands = []
        lines = program.strip().split('\n')
        
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            try:
                command, args, kwargs = self._parse_line(line)
                commands.append((line_num, command, args, kwargs))
            except Exception as e:
                raise DSLExecutionError(f"Parse error: {e}", line_num, line)
        
        return commands
    
    def _parse_line(self, line: str) -> Tuple[str, List[Any], Dict[str, Any]]:
        """Parse a single DSL line."""
        # Match function call pattern: command(args...)
        match = re.match(r'^(\w+)\s*\((.*)\)\s*$', line)
        if not match:
            raise ValueError(f"Invalid syntax: {line}")
        
        command = match.group(1)
        args_str = match.group(2).strip()
        
        if not args_str:
            return command, [], {}
        
        # Parse arguments (simple implementation)
        args, kwargs = self._parse_arguments(args_str)
        return command, args, kwargs
    
    def _parse_arguments(self, args_str: str) -> Tuple[List[Any], Dict[str, Any]]:
        """Parse function arguments."""
        args = []
        kwargs = {}
        
        # Split arguments (simple parsing - could be improved)
        parts = []
        current = ""
        paren_level = 0
        bracket_level = 0
        in_string = False
        string_char = None
        
        for char in args_str:
            if not in_string and char in ['"', "'"]:
                in_string = True
                string_char = char
            elif in_string and char == string_char:
                in_string = False
                string_char = None
            elif not in_string:
                if char == '(':
                    paren_level += 1
                elif char == ')':
                    paren_level -= 1
                elif char == '[':
                    bracket_level += 1
                elif char == ']':
                    bracket_level -= 1
                elif char == ',' and paren_level == 0 and bracket_level == 0:
                    parts.append(current.strip())
                    current = ""
                    continue
            
            current += char
        
        if current.strip():
            parts.append(current.strip())
        
        # Parse each part
        for part in parts:
            if '=' in part and not any(part.startswith(q) for q in ['"', "'", '[']):
                # Keyword argument
                key, value = part.split('=', 1)
                kwargs[key.strip()] = self._parse_value(value.strip())
            else:
                # Positional argument
                args.append(self._parse_value(part))
        
        return args, kwargs
    
    def _parse_value(self, value_str: str) -> Any:
        """Parse a single value."""
        value_str = value_str.strip()
        
        # String literals
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]
        
        # List literals (simplified)
        if value_str.startswith('[') and value_str.endswith(']'):
            inner = value_str[1:-1].strip()
            if not inner:
                return []
            
            # Parse list of tuples for river points: [(5,5), (10,8)]
            if '(' in inner:
                items = []
                parts = inner.split('),')
                for part in parts:
                    part = part.strip().rstrip(')')
                    if part.startswith('('):
                        part = part[1:]
                    coords = [int(x.strip()) for x in part.split(',')]
                    items.append(tuple(coords))
                return items
            else:
                return [self._parse_value(item.strip()) for item in inner.split(',')]
        
        # Boolean literals
        if value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        
        # Numeric literals
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Bare identifiers (for entity types)
        return value_str


class DSLMapGenerator:
    """Map generator using DSL approach with selective checkpointing."""
    
    def __init__(self, provider: str = None, verbose: bool = False):
        self.config = load_config("generator.json")
        try:
            self.secrets = load_secrets()
        except Exception:
            self.secrets = {}
        
        # Use provided provider or fall back to config default
        if provider is None:
            provider = self.config.get("llm", {}).get("provider", "ollama")
        
        # Create LLM client using the factory method
        try:
            from ..shared.llm_client import LLMClient
            if provider == "anthropic":
                # For Anthropic, we need the API key
                api_key = self.secrets.get("anthropic_api_key")
                if not api_key:
                    raise RuntimeError("Missing Anthropic API key in config/secrets.json")
                self.client = LLMClient.create("anthropic", 
                                             model=self.config.get("anthropic", {}).get("model", "claude-3-5-sonnet-20241022"),
                                             temperature=self.config.get("anthropic", {}).get("temperature", 0.7))
            else:
                # Default to Ollama
                self.client = LLMClient.create("ollama",
                                             model=self.config.get("ollama", {}).get("model", "deepseek-coder:33b-instruct"),
                                             endpoint=self.config.get("ollama", {}).get("endpoint", "http://localhost:11434"),
                                             temperature=self.config.get("ollama", {}).get("temperature", 0.2))
        except Exception as e:
            raise RuntimeError(f"Failed to create LLM client for provider '{provider}': {e}")
        
        self.provider = provider
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        self.parser = DSLParser()
    
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
                generation_time=0.0,
                warnings=[],
                error_message=None,
                map_data=map_data
            )
        except Exception as e:
            self.logger.error(f"Failed to generate map {index}: {e}")
            return GenerationResult(
                prompt_index=index,
                status="failed",
                generation_time=0.0,
                warnings=[],
                error_message=str(e),
                map_data=None
            )
    
    def generate_map(self, prompt: str, map_id: str) -> MapData:
        """Generate a map using DSL approach."""
        self.logger.info(f"Generating map {map_id} with DSL: {prompt}")
        
        # System prompt for DSL generation
        system_prompt = """You are a roguelike map generator that creates maps using a Domain Specific Language (DSL).

DSL COMMANDS:
- grid(width, height) - Initialize map (must be exactly 20, 15)
- room(name, x, y, width, height) - Create rectangular room
- corridor(x1, y1, x2, y2) - Connect two points with L-shaped corridor  
- door(x, y) - Place door at coordinates
- spawn(entity_type, x, y, **properties) - Place entity (player, ogre, goblin, shop, chest)
- water_area(x, y, shape, radius=3, width=6, height=4) - Create water ("circle" or "rectangle")
- river(points, width=2) - Create river through points: [(x1,y1), (x2,y2), ...]
- checkpoint(name, verify_connectivity=False, verify_entities=False, full_verification=False, stats=False)

CHECKPOINTING STRATEGY:
Use checkpoints strategically to debug and verify your work:
- After placing basic structure: checkpoint("structure_done")
- After ensuring connectivity: checkpoint("connected", verify_connectivity=True) 
- After placing entities: checkpoint("entities_done", verify_entities=True)
- Final check: checkpoint("complete", full_verification=True)

CRITICAL REQUIREMENTS:
1. Every map MUST have exactly one player: spawn(player, x, y)
2. All areas must be connected (use corridor/door commands)
3. Grid must be exactly 20x15: grid(20, 15)

EXAMPLE PROGRAM:
```
grid(20, 15)
room("main", 2, 2, 12, 8) 
room("side", 15, 10, 4, 4)
checkpoint("rooms_placed")

corridor(14, 6, 15, 6)
corridor(15, 6, 17, 6)
corridor(17, 6, 17, 10)
checkpoint("connected", verify_connectivity=True)

spawn(player, 8, 6)
spawn(ogre, 17, 12)
checkpoint("complete", full_verification=True)
```

Generate a complete DSL program for the requested map. Use checkpoints wisely to verify your work without overusing tokens."""

        user_prompt = f'Create a DSL program for: "{prompt}"'
        
        max_iterations = 5
        iteration = 0
        
        while iteration < max_iterations:
            try:
                # Get DSL program from LLM
                program_text = self.client.query(user_prompt, system_prompt)
                
                # Show conversation if verbose mode is enabled
                if self.verbose:
                    response_type = "Retry" if iteration > 0 else "LLM"
                    print(f"\n🤖 {response_type} Response (Iteration {iteration + 1}):")
                    print("=" * 60)
                    if iteration == 0:
                        print(f"System Prompt: {system_prompt[:200]}...")
                    print(f"User Prompt: {user_prompt}")
                    print(f"Response: {program_text}")
                    print("=" * 60)
                
                # Extract DSL code from response (handle code blocks)
                if "```" in program_text:
                    # Find code block
                    start = program_text.find("```")
                    if start != -1:
                        start = program_text.find("\n", start) + 1
                        end = program_text.find("```", start)
                        if end != -1:
                            program_text = program_text[start:end].strip()
                
                # Execute DSL program
                builder = DSLMapBuilder()
                execution_result = self._execute_dsl_program(program_text, builder)
                
                # Check if we need to retry based on execution result
                if "❌" in execution_result:  # Error indicators in checkpoint output
                    user_prompt = f"""The DSL program had issues:

{execution_result}

Please fix the program and try again. Original request: "{prompt}"

Previous program:
```
{program_text}
```"""
                    

                    
                    iteration += 1
                    continue
                
                # Success - convert to MapData
                return builder.to_map_data(map_id, prompt)
                
            except DSLExecutionError as e:
                error_msg = f"DSL execution error at line {e.line_number}: {e}"
                if e.command:
                    error_msg += f"\nCommand: {e.command}"
                
                user_prompt = f"""DSL execution failed:

{error_msg}

Please fix the program. Original request: "{prompt}"

Previous program:
```
{program_text}
```"""
                iteration += 1
                continue
                
            except Exception as e:
                self.logger.error(f"Unexpected error generating map {map_id}: {e}")
                iteration += 1
                continue
        
        # Fallback - create minimal valid map
        self.logger.warning(f"Map generation failed after {max_iterations} iterations, using fallback")
        builder = DSLMapBuilder()
        fallback_program = """
grid(20, 15)
room("main", 2, 2, 16, 11)
door(10, 2)
spawn(player, 10, 7)
checkpoint("fallback", full_verification=True)
"""
        self._execute_dsl_program(fallback_program, builder)
        return builder.to_map_data(map_id, prompt)
    
    def _execute_dsl_program(self, program: str, builder: DSLMapBuilder) -> str:
        """Execute a DSL program and return checkpoint output."""
        commands = self.parser.parse_program(program)
        checkpoint_outputs = []
        
        for line_num, command, args, kwargs in commands:
            try:
                result = builder.execute_command(command, args, kwargs)
                
                # Collect checkpoint outputs for feedback
                if command == "checkpoint":
                    checkpoint_outputs.append(result)
                    
            except DSLExecutionError as e:
                e.line_number = line_num
                e.command = f"{command}({', '.join(map(str, args))}, {', '.join(f'{k}={v}' for k, v in kwargs.items())})"
                raise e
        
        return "\n\n".join(checkpoint_outputs) if checkpoint_outputs else "Program executed successfully (no checkpoints)"


# Example usage and testing
if __name__ == "__main__":
    # Test the DSL parser
    parser = DSLParser()
    
    test_program = '''
    grid(20, 15)
    room("tavern", 2, 2, 10, 8)
    room("kitchen", 12, 2, 6, 6)
    checkpoint("rooms_placed", stats=True)
    corridor(10, 5, 12, 5)
    door(4, 9)
    checkpoint("connected", verify_connectivity=True)
    spawn(player, 6, 5)
    spawn(ogre, 15, 4)
    water_area(8, 12, "circle", radius=2)
    river([(1, 10), (5, 12), (10, 14)], width=2)
    checkpoint("complete", full_verification=True)
    '''
    
    try:
        commands = parser.parse_program(test_program)
        print("Parsed commands:")
        for line_num, command, args, kwargs in commands:
            print(f"Line {line_num}: {command}({args}, {kwargs})")
        
        # Test execution
        builder = DSLMapBuilder()
        for line_num, command, args, kwargs in commands:
            result = builder.execute_command(command, args, kwargs)
            if command == "checkpoint":
                print(f"\n{result}\n")
    
    except Exception as e:
        print(f"Error: {e}")