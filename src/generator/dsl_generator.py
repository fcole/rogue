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
import time
from typing import Dict, Any, List, Optional, Tuple, Union, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError
from pydantic import ConfigDict
from enum import Enum

from ..shared.utils import load_config, load_secrets
from ..shared.models import MapData, EntityData, GenerationResult
from ..shared.connectivity import check_map_connectivity


class EntityType(str, Enum):
    """Valid entity types for spawning."""
    PLAYER = "player"
    OGRE = "ogre"
    GOBLIN = "goblin"
    SHOP = "shop"
    CHEST = "chest"
    TOMB = "tomb"
    SPIRIT = "spirit"
    HUMAN = "human"


class DSLExecutionError(Exception):
    """Error during DSL program execution."""
    def __init__(self, message: str, command_index: int = None, command: str = None):
        self.command_index = command_index
        self.command = command
        super().__init__(message)


class BaseCommand(BaseModel):
    """Base class for all DSL commands."""
    type: str


class GridCommand(BaseCommand):
    """Initialize the map grid."""
    type: Literal["grid"] = "grid"
    width: int = Field(20, description="Grid width, must be exactly 20")
    height: int = Field(15, description="Grid height, must be exactly 15")


class RoomCommand(BaseCommand):
    """Create a rectangular room."""
    type: Literal["room"] = "room"
    name: str = Field(description="Name of the room")
    x: int = Field(ge=0, le=19, description="Left edge X coordinate (0-19)")
    y: int = Field(ge=0, le=14, description="Top edge Y coordinate (0-14)")
    width: int = Field(ge=1, description="Room width")
    height: int = Field(ge=1, description="Room height")


class DoorOnCommand(BaseCommand):
    """Place a door on a labeled room wall."""
    type: Literal["door_on"] = "door_on"
    room: str = Field(description="Target room name")
    wall: Literal["north", "south", "east", "west"] = Field(description="Wall side")
    at: Optional[Literal["center", "start", "end"]] = Field(default="center", description="Position selector on wall")
    offset: Optional[int] = Field(default=None, ge=0, description="Offset from wall start (excludes corners)")


class ConnectByWallsCommand(BaseCommand):
    """Connect two rooms by specifying wall sides; carves an L/I corridor and places doors."""
    type: Literal["connect_by_walls"] = "connect_by_walls"
    a: str = Field(description="First room name")
    a_wall: Literal["north", "south", "east", "west"]
    b: str = Field(description="Second room name")
    b_wall: Literal["north", "south", "east", "west"]
    style: Literal["L", "I"] = Field("L", description="Corridor style")


class SpawnInCommand(BaseCommand):
    """Spawn an entity within a labeled room region."""
    type: Literal["spawn"] = "spawn"
    entity: EntityType = Field(description="Entity type to spawn")
    in_room: Optional[str] = Field(default=None, alias="in", description="Room name to spawn in")
    at: Optional[Literal["center"]] = Field(default="center", description="Anchor within room")
    dx: int = Field(0, description="X offset from anchor")
    dy: int = Field(0, description="Y offset from anchor")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional entity properties")
    model_config = ConfigDict(populate_by_name=True)


class CorridorCommand(BaseCommand):
    """Create an L-shaped corridor between two points."""
    type: Literal["corridor"] = "corridor"
    x1: int = Field(ge=0, le=19, description="Start X coordinate (0-19)")
    y1: int = Field(ge=0, le=14, description="Start Y coordinate (0-14)")
    x2: int = Field(ge=0, le=19, description="End X coordinate (0-19)")
    y2: int = Field(ge=0, le=14, description="End Y coordinate (0-14)")


class DoorCommand(BaseCommand):
    """Place a door at coordinates."""
    type: Literal["door"] = "door"
    x: int = Field(ge=0, le=19, description="Door X coordinate (0-19)")
    y: int = Field(ge=0, le=14, description="Door Y coordinate (0-14)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional door properties")


class SpawnCommand(BaseCommand):
    """Spawn an entity at coordinates."""
    type: Literal["spawn"] = "spawn"
    entity: EntityType = Field(description="Entity type to spawn")
    x: int = Field(ge=0, le=19, description="Spawn X coordinate (0-19)")
    y: int = Field(ge=0, le=14, description="Spawn Y coordinate (0-14)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional entity properties")


class WaterAreaCommand(BaseCommand):
    """Create a water area."""
    type: Literal["water_area"] = "water_area"
    x: int = Field(ge=0, le=19, description="Center X coordinate (0-19)")
    y: int = Field(ge=0, le=14, description="Center Y coordinate (0-14)")
    shape: Literal["circle", "rectangle"] = Field("circle", description="Shape of water area")
    radius: int = Field(3, ge=1, description="Radius for circle shape")
    width: int = Field(6, ge=1, description="Width for rectangle shape")
    height: int = Field(4, ge=1, description="Height for rectangle shape")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional water properties")


class RiverCommand(BaseCommand):
    """Create a river through multiple points."""
    type: Literal["river"] = "river"
    points: List[Tuple[int, int]] = Field(description="List of [x, y] coordinate pairs")
    width: int = Field(2, ge=1, description="River width")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional river properties")


class CheckpointCommand(BaseCommand):
    """Create a checkpoint for visualization and verification."""
    type: Literal["checkpoint"] = "checkpoint"
    name: str = Field(description="Checkpoint name")
    verify_connectivity: bool = Field(False, description="Check map connectivity")
    verify_entities: bool = Field(False, description="Check entity placement")
    full_verification: bool = Field(False, description="Run all verification checks")
    stats: bool = Field(False, description="Show map statistics")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Optional checkpoint properties")


# Union type for all commands
DSLCommand = Union[
    GridCommand,
    RoomCommand,
    DoorOnCommand,
    ConnectByWallsCommand,
    SpawnInCommand,
    WaterAreaCommand,
    RiverCommand,
    CheckpointCommand
]


class DSLProgram(BaseModel):
    """Complete DSL program with list of commands."""
    commands: List[DSLCommand] = Field(description="List of DSL commands to execute")


class DSLMapBuilder:
    """Executes DSL commands to build a roguelike map."""
    
    def __init__(self, width: int = 20, height: int = 15):
        self.target_width = width
        self.target_height = height
        self.grid: Optional[List[List[str]]] = None
        self.labels: Optional[List[List[set]]] = None
        self.entities: Dict[str, List[EntityData]] = {}
        self.checkpoints: Dict[str, Dict[str, Any]] = {}
        self.last_checkpoint = None
        
    def execute_command(self, command: DSLCommand) -> str:
        """Execute a single DSL command from Pydantic model."""
        if isinstance(command, GridCommand):
            return self._cmd_grid(command.width, command.height)
        elif isinstance(command, RoomCommand):
            return self._cmd_room(command.name, command.x, command.y, command.width, command.height)
        elif isinstance(command, DoorOnCommand):
            return self._cmd_door_on(command.room, command.wall, command.at, command.offset)
        elif isinstance(command, ConnectByWallsCommand):
            return self._cmd_connect_by_walls(command.a, command.a_wall, command.b, command.b_wall, command.style)
        elif isinstance(command, SpawnInCommand):
            return self._cmd_spawn_in(command.entity, command.in_room, command.at, command.dx, command.dy, **command.properties)
        elif isinstance(command, WaterAreaCommand):
            return self._cmd_water_area(command.x, command.y, command.shape, command.radius,
                                       command.width, command.height, **command.properties)
        elif isinstance(command, RiverCommand):
            return self._cmd_river(command.points, command.width, **command.properties)
        elif isinstance(command, CheckpointCommand):
            return self._cmd_checkpoint(command.name, command.verify_connectivity,
                                       command.verify_entities, command.full_verification,
                                       command.stats, **command.properties)
        else:
            raise DSLExecutionError(f"Unknown command type: {type(command)}")
    
    def _cmd_grid(self, width: int, height: int) -> str:
        """Initialize grid: grid(20, 15)"""
        if width != self.target_width or height != self.target_height:
            raise DSLExecutionError(f"Grid must be {self.target_width}x{self.target_height}, got {width}x{height}")
        
        self.grid = [['#' for _ in range(width)] for _ in range(height)]
        self.labels = [[set() for _ in range(width)] for _ in range(height)]
        
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
        
        # Place room walls and floor with labels
        for i in range(y, y + height):
            for j in range(x, x + width):
                self._clear_room_labels(j, i)
                if i == y or i == y + height - 1:
                    self.grid[i][j] = '#'
                    self._add_label(j, i, f"room:{name}")
                    side = "north" if i == y else "south"
                    self._add_label(j, i, f"wall:{side}")
                    idx = j - x
                    self._add_label(j, i, f"wall_index:{idx}")
                elif j == x or j == x + width - 1:
                    self.grid[i][j] = '#'
                    self._add_label(j, i, f"room:{name}")
                    side = "west" if j == x else "east"
                    self._add_label(j, i, f"wall:{side}")
                    idx = i - y
                    self._add_label(j, i, f"wall_index:{idx}")
                else:
                    self.grid[i][j] = '.'
                    self._add_label(j, i, f"room:{name}")
                    self._add_label(j, i, "interior")
        
        return f"Created room '{name}' at ({x},{y}) size {width}x{height}"
    
    def _cmd_door_on(self, room: str, wall: str, at: Optional[str], offset: Optional[int]) -> str:
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        coords = self._get_room_wall_coords(room, wall)
        if not coords:
            raise DSLExecutionError(f"Room '{room}' or wall '{wall}' not found")
        valid = coords[1:-1] if len(coords) > 2 else []
        if not valid:
            raise DSLExecutionError(f"Wall too short for door on {room}.{wall}")
        if offset is not None:
            if offset <= 0 or offset >= len(coords)-1:
                raise DSLExecutionError(f"Invalid offset {offset} for {room}.{wall}; valid 1..{len(coords)-2}")
            idx = offset
        elif at == "start":
            idx = 1
        elif at == "end":
            idx = len(coords)-2
        else:
            idx = (len(coords)-1)//2
            if idx == 0:
                idx = 1
            if idx >= len(coords)-1:
                idx = len(coords)-2
        x, y = coords[idx]
        self.grid[y][x] = '+'
        return f"Placed door_on {room}.{wall} at ({x},{y})"

    def _cmd_connect_by_walls(self, a: str, a_wall: str, b: str, b_wall: str, style: str = "L") -> str:
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        a_coords = self._get_room_wall_coords(a, a_wall)
        b_coords = self._get_room_wall_coords(b, b_wall)
        if not a_coords or not b_coords:
            a_len = len(a_coords)
            b_len = len(b_coords)
            raise DSLExecutionError(
                f"Could not find walls to connect: {a}.{a_wall} length {a_len}, {b}.{b_wall} length {b_len}. "
                f"Choose a different wall side with length >= 1 or increase room size."
            )

        # Choose a safe index on each wall. Prefer a non-corner center when possible; otherwise clamp in-bounds.
        def pick_idx(coords: List[Tuple[int, int]]) -> int:
            n = len(coords)
            if n <= 1:
                return 0
            # tentative center
            idx = (n - 1) // 2
            # prefer non-corner when available
            if n >= 3:
                idx = max(1, min(idx, n - 2))
            else:
                idx = min(idx, n - 1)
            return idx

        ax, ay = a_coords[pick_idx(a_coords)]
        bx, by = b_coords[pick_idx(b_coords)]
        self.grid[ay][ax] = '+'
        self.grid[by][bx] = '+'
        def outside(x, y, wall_side):
            if wall_side == "north":
                return (x, y-1)
            if wall_side == "south":
                return (x, y+1)
            if wall_side == "west":
                return (x-1, y)
            return (x+1, y)
        sx, sy = outside(ax, ay, a_wall)
        tx, ty = outside(bx, by, b_wall)
        def carve_line(x0, y0, x1, y1):
            start_x, end_x = (x0, x1) if x0 <= x1 else (x1, x0)
            for x in range(start_x, end_x + 1):
                if self._in_bounds(x, y0):
                    self.grid[y0][x] = '.'
            start_y, end_y = (y0, y1) if y0 <= y1 else (y1, y0)
            for y in range(start_y, end_y + 1):
                if self._in_bounds(x1, y):
                    self.grid[y][x1] = '.'
        if style == "I":
            carve_line(sx, sy, tx, ty)
        else:
            midx, midy = tx, sy
            carve_line(sx, sy, midx, midy)
            carve_line(midx, midy, tx, ty)
        return f"Connected {a}.{a_wall} to {b}.{b_wall}"

    def _cmd_spawn_in(self, entity_type: EntityType, in_room: Optional[str], at: Optional[str], dx: int, dy: int, **properties) -> str:
        if not self.grid:
            raise DSLExecutionError("Must create grid first")
        entity_type_str = entity_type.value
        if in_room:
            interior = self._get_room_interior_coords(in_room)
            if not interior:
                raise DSLExecutionError(f"Room '{in_room}' has no interior for spawning")
            minx = min(p[0] for p in interior)
            maxx = max(p[0] for p in interior)
            miny = min(p[1] for p in interior)
            maxy = max(p[1] for p in interior)
            cx = (minx + maxx) // 2
            cy = (miny + maxy) // 2
            best = min(interior, key=lambda p: abs(p[0]-cx)+abs(p[1]-cy))
            x, y = best[0] + dx, best[1] + dy
            if not self._in_bounds(x, y) or self.grid[y][x] not in ['.', '+']:
                x, y = best
        else:
            x, y = self.target_width//2, self.target_height//2
            if self.grid[y][x] not in ['.', '+']:
                found = False
                for yy in range(1, self.target_height-1):
                    for xx in range(1, self.target_width-1):
                        if self.grid[yy][xx] in ['.', '+']:
                            x, y = xx, yy
                            found = True
                            break
                    if found:
                        break
        if entity_type_str not in self.entities:
            self.entities[entity_type_str] = []
        self.entities[entity_type_str].append(EntityData(x=x, y=y, properties=properties))
        return f"Spawned {entity_type_str} at ({x},{y})"
    
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

    # Label helpers
    def _add_label(self, x: int, y: int, label: str):
        if self.labels is not None and self._in_bounds(x, y):
            self.labels[y][x].add(label)

    def _clear_room_labels(self, x: int, y: int):
        if self.labels is None:
            return
        to_remove = {lab for lab in self.labels[y][x] if lab.startswith('room:') or lab.startswith('wall:') or lab.startswith('wall_index:') or lab == 'interior'}
        self.labels[y][x] -= to_remove

    def _get_room_wall_coords(self, room: str, wall: str) -> List[Tuple[int, int]]:
        coords: List[Tuple[int, int]] = []
        if self.labels is None:
            return coords
        for yy in range(self.target_height):
            for xx in range(self.target_width):
                labs = self.labels[yy][xx]
                if f"room:{room}" in labs and f"wall:{wall}" in labs:
                    coords.append((xx, yy))
        if wall in ("north", "south"):
            coords.sort(key=lambda p: p[0])
        else:
            coords.sort(key=lambda p: p[1])
        return coords

    def _get_room_interior_coords(self, room: str) -> List[Tuple[int, int]]:
        coords: List[Tuple[int, int]] = []
        if self.labels is None:
            return coords
        for yy in range(self.target_height):
            for xx in range(self.target_width):
                labs = self.labels[yy][xx]
                if f"room:{room}" in labs and 'interior' in labs and self.grid[yy][xx] in ['.', '+']:
                    coords.append((xx, yy))
        return coords
    
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
    """Parses JSON DSL programs using Pydantic validation."""
    
    def parse_program(self, program_json: str) -> List[DSLCommand]:
        """Parse JSON DSL program into validated command objects."""
        try:
            # Parse JSON
            program_data = json.loads(program_json)
            
            # Validate against Pydantic model
            dsl_program = DSLProgram(**program_data)
            
            return dsl_program.commands
            
        except json.JSONDecodeError as e:
            raise DSLExecutionError(f"Invalid JSON: {e}")
        except ValidationError as e:
            # Format Pydantic validation errors for better feedback
            error_details = []
            for error in e.errors():
                location = " -> ".join(str(x) for x in error['loc'])
                error_details.append(f"{location}: {error['msg']}")
            raise DSLExecutionError(f"Validation errors:\n" + "\n".join(error_details))


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
                # Default to Ollama (prefer DSL-specific model if provided)
                ollama_cfg = self.config.get("ollama", {})
                model = ollama_cfg.get("dsl_model") or ollama_cfg.get("model", "qwen3-coder:30b")
                self.client = LLMClient.create(
                    "ollama",
                    model=model,
                    endpoint=ollama_cfg.get("endpoint", "http://localhost:11434"),
                    temperature=ollama_cfg.get("temperature", 0.2),
                )
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
        
        # System prompt for JSON DSL generation (labels; door_on/connect_by_walls; region spawns)
        system_prompt = """You are a roguelike map generator that creates maps using JSON commands.

RESPOND WITH JSON ONLY in this format:
{"commands": [list_of_command_objects]}

COMMANDS:
- {"type": "grid", "width": 20, "height": 15} - Initialize 20x15 map
- {"type": "room", "name": "string", "x": int, "y": int, "width": int, "height": int} - Create room (labels tiles: room:<name>, wall:<side>, interior)
- {"type": "door_on", "room": "name", "wall": "north|south|east|west", "at": "center|start|end", "offset": int} - Place a door on a room wall (no raw coordinates)
- {"type": "connect_by_walls", "a": "roomA", "a_wall": "east", "b": "roomB", "b_wall": "west", "style": "L|I"} - Place doors on both walls and carve corridor
- {"type": "spawn", "entity": "string", "in": "room", "at": "center", "dx": 0, "dy": 0} - Spawn in a room region
- {"type": "water_area", "x": int, "y": int, "shape": "circle|rectangle", "radius": int} - Water (optional)
- {"type": "river", "points": [[x,y], [x,y], ...], "width": int} - River path (optional)
- {"type": "checkpoint", "name": "string", "verify_connectivity": false, "full_verification": false} - Checkpoint

ENTITY TYPES: player, ogre, goblin, shop, chest, tomb, spirit, human

CRITICAL RULES:
1. MUST have exactly one "player" spawn
2. Grid MUST be 20x15
3. Only use door_on/connect_by_walls for doors; do NOT place doors by raw coordinates
4. Use checkpoints: after structure, after connectivity (verify_connectivity=true), final (full_verification=true)
5. Bounds (0-indexed): x in [0,19], y in [0,14]; rooms must fit: x+width<=20, y+height<=15
6. door_on offset hint: do not use 0; valid offsets are 1..(wall_length-2). Prefer at:"center" when unsure.
7. Entities must not overlap; ensure each entity is on a distinct tile (use at:"center" with small dx/dy for variety).
8. Minimum room size for door_on: rooms should be at least 3x3 so each wall has a non-corner tile; if a wall is too short, either choose a different wall or increase room size.
9. connect_by_walls places doors automatically on both walls; do not also add a separate door_on for the same connection.
10. Do not model 1-tile-thick corridors as rooms needing door_on; use connect_by_walls to create connections.

EXAMPLE:
{
  "commands": [
    {"type": "grid", "width": 20, "height": 15},
    {"type": "room", "name": "tavern", "x": 4, "y": 3, "width": 10, "height": 6},
    {"type": "room", "name": "hall", "x": 12, "y": 6, "width": 6, "height": 5},
    {"type": "door_on", "room": "tavern", "wall": "north", "at": "center"},
    {"type": "connect_by_walls", "a": "tavern", "a_wall": "east", "b": "hall", "b_wall": "west", "style": "L"},
    {"type": "checkpoint", "name": "structure"},
    {"type": "spawn", "entity": "player", "in": "tavern", "at": "center"},
    {"type": "spawn", "entity": "goblin", "in": "hall", "dx": 1},
    {"type": "checkpoint", "name": "connected", "verify_connectivity": true},
    {"type": "checkpoint", "name": "complete", "full_verification": true}
  ]
}

Generate valid JSON only."""

        user_prompt = f'Create a DSL program for: "{prompt}"'
        
        # Honor configured retry count
        max_iterations = int(self.config.get("llm", {}).get("max_retries", 3))
        iteration = 0
        # Track last successfully executed (but possibly constraint-violating) program
        last_successful_builder: Optional[DSLMapBuilder] = None
        last_successful_program_json: Optional[str] = None
        last_checkpoint_output: Optional[str] = None
        
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
                
                # Clean up response - extract JSON from any markdown formatting
                program_json = program_text.strip()
                if "```" in program_json:
                    # Find JSON code block
                    start = program_json.find("```")
                    if start != -1:
                        # Skip past the opening ```json or just ```
                        start = program_json.find("\n", start)
                        if start == -1:
                            start = program_json.find("```") + 3
                        else:
                            start += 1
                        end = program_json.find("```", start)
                        if end != -1:
                            program_json = program_json[start:end].strip()
                
                # Execute JSON DSL program
                builder = DSLMapBuilder()
                execution_result = self._execute_dsl_program(program_json, builder)
                # Remember the last successfully executed program regardless of checkpoint issues
                last_successful_builder = builder
                last_successful_program_json = program_json
                last_checkpoint_output = execution_result
                
                # If checkpoints indicated issues, or no checkpoints provided, trigger a surgical retry
                issues_detected = "❌" in execution_result
                no_checkpoints = len(builder.checkpoints) == 0
                if issues_detected or no_checkpoints:
                    # Build compact, constraint-focused retry prompt without ASCII map noise
                    reason = "no checkpoints were provided" if no_checkpoints else "checkpoint verification reported issues"
                    user_prompt = f"""The JSON DSL program needs correction because {reason}.

Constraints (restate precisely):
- Grid must be 20x15.
- Coordinates are 0-indexed. x in [0,19], y in [0,14].
- Rooms must fit entirely: x + width <= 20, y + height <= 15.
- Include both checkpoints: one with verify_connectivity=true and the final with full_verification=true.
- Make the minimal change necessary: only adjust offending command(s); keep all other commands identical.
 - For doors, use door_on(room, wall, at/offset) or connect_by_walls only. Do not add door_on if connect_by_walls already connects those rooms.
 - Rooms for door_on should be at least 3x3 so walls have non-corner tiles; if a wall is too short, pick a different wall or increase the room size.

Return JSON only.

Previous JSON:
```json
{program_json}
```"""
                    iteration += 1
                    continue
                
                # Success - convert to MapData
                return builder.to_map_data(map_id, prompt)
                
            except DSLExecutionError as e:
                error_msg = f"JSON DSL execution error: {e}"
                if e.command_index is not None:
                    error_msg += f" (at command index {e.command_index})"
                if e.command:
                    error_msg += f"\nCommand: {e.command}"

                # Log the specific error for debugging
                print(f"❌ JSON DSL Error (Iteration {iteration + 1}): {error_msg}")

                user_prompt = f"""JSON DSL execution failed with the following error:

{error_msg}

Constraints (restate precisely):
- Grid must be 20x15.
- Coordinates are 0-indexed. x in [0,19], y in [0,14].
- Rooms must fit entirely: x + width <= 20, y + height <= 15.
- Use door_on(room, wall, at/offset) or connect_by_walls only for doors/corridors.
- Include both checkpoints: one with verify_connectivity=true and the final with full_verification=true.
- Make the minimal change necessary: only adjust offending command(s); keep all other commands identical.
 - Do not add door_on when connect_by_walls already places doors; avoid redundant door placements.
 - Ensure rooms used with door_on are at least 3x3; if a wall is too short, increase room size or choose a different wall.

Return JSON only. Original request: "{prompt}"

Previous JSON:
```json
{program_json}
```"""
                iteration += 1
                continue

            except Exception as e:
                error_msg = f"Unexpected error generating map {map_id}: {e}"
                self.logger.error(error_msg)
                # Also print to console for visibility
                print(f"❌ Unexpected Error (Iteration {iteration + 1}): {e}")
                iteration += 1
                continue
        
        # If we executed at least one program but constraints weren't satisfied, return the last map as-is
        if last_successful_builder is not None:
            print(f"⚠️  Proceeding with last generated map despite constraint issues after {max_iterations} attempts")
            return last_successful_builder.to_map_data(map_id, prompt)

        # Fallback - create minimal valid map (only when DSL could not be executed at all)
        self.logger.warning(f"Map generation failed after {max_iterations} iterations, using fallback")
        print(f"⚠️  All {max_iterations} attempts failed, using minimal fallback map")
        builder = DSLMapBuilder()
        fallback_program_json = """{
  "commands": [
    {"type": "grid", "width": 20, "height": 15},
    {"type": "room", "name": "main", "x": 2, "y": 2, "width": 16, "height": 11},
    {"type": "door_on", "room": "main", "wall": "north", "at": "center"},
    {"type": "spawn", "entity": "player", "in": "main", "at": "center"},
    {"type": "checkpoint", "name": "fallback", "full_verification": true}
  ]
}"""
        self._execute_dsl_program(fallback_program_json, builder)
        return builder.to_map_data(map_id, prompt)
    
    def _execute_dsl_program(self, program_json: str, builder: DSLMapBuilder) -> str:
        """Execute a JSON DSL program and return checkpoint output."""
        commands = self.parser.parse_program(program_json)
        checkpoint_outputs = []
        
        for command_index, command in enumerate(commands):
            try:
                result = builder.execute_command(command)
                
                # Collect checkpoint outputs for feedback
                if isinstance(command, CheckpointCommand):
                    checkpoint_outputs.append(result)
                    
            except DSLExecutionError as e:
                e.command_index = command_index
                # Provide a JSON-formatted command for clearer fixes
                try:
                    e.command = f"{command.type}({json.dumps(command.model_dump())})"
                except Exception:
                    e.command = f"{command.type}({command.model_dump()})"
                raise e
        
        return "\n\n".join(checkpoint_outputs) if checkpoint_outputs else "Program executed successfully (no checkpoints)"


# Example usage and testing
if __name__ == "__main__":
    # Test the JSON DSL parser
    parser = DSLParser()
    
    test_program_json = '''{
  "commands": [
    {"type": "grid", "width": 20, "height": 15},
    {"type": "room", "name": "tavern", "x": 2, "y": 2, "width": 10, "height": 8},
    {"type": "room", "name": "kitchen", "x": 12, "y": 2, "width": 6, "height": 6},
    {"type": "checkpoint", "name": "rooms_placed", "stats": true},
    {"type": "corridor", "x1": 10, "y1": 5, "x2": 12, "y2": 5},
    {"type": "door", "x": 4, "y": 9},
    {"type": "checkpoint", "name": "connected", "verify_connectivity": true},
    {"type": "spawn", "entity": "player", "x": 6, "y": 5},
    {"type": "spawn", "entity": "ogre", "x": 15, "y": 4},
    {"type": "water_area", "x": 8, "y": 12, "shape": "circle", "radius": 2},
    {"type": "river", "points": [[1, 10], [5, 12], [10, 14]], "width": 2},
    {"type": "checkpoint", "name": "complete", "full_verification": true}
  ]
}'''
    
    try:
        commands = parser.parse_program(test_program_json)
        print("Parsed commands:")
        for i, command in enumerate(commands):
            print(f"Command {i}: {command.type} - {command.model_dump()}")
        
        # Test execution
        builder = DSLMapBuilder()
        for command in commands:
            result = builder.execute_command(command)
            if isinstance(command, CheckpointCommand):
                print(f"\n{result}\n")
    
    except Exception as e:
        print(f"Error: {e}")
