"""
Alternative positioning systems for map generation that are easier for LLMs to use.
"""
from typing import Tuple, Optional, Dict, Any, List
import re


class GridReferencePositioning:
    """Grid reference positioning system (like chess notation)."""
    
    def __init__(self, width: int = 20, height: int = 15):
        self.width = width
        self.height = height
        self.column_labels = [chr(65 + i) for i in range(width)]  # A, B, C, D...
        self.row_labels = [str(i + 1) for i in range(height)]     # 1, 2, 3, 4...
        
    def grid_ref_to_coords(self, grid_ref: str) -> Optional[Tuple[int, int]]:
        """Convert grid reference (e.g., 'B3') to coordinates."""
        match = re.match(r'^([A-Z])(\d+)$', grid_ref.upper())
        if not match:
            return None
            
        col, row = match.groups()
        col_idx = ord(col) - 65  # A=0, B=1, etc.
        row_idx = int(row) - 1   # 1=0, 2=1, etc.
        
        if 0 <= col_idx < self.width and 0 <= row_idx < self.height:
            return (col_idx, row_idx)
        return None
    
    def coords_to_grid_ref(self, x: int, y: int) -> str:
        """Convert coordinates to grid reference."""
        if 0 <= x < self.width and 0 <= y < self.height:
            return f"{self.column_labels[x]}{self.row_labels[y]}"
        return f"INVALID({x},{y})"
    
    def get_grid_overview(self) -> str:
        """Get a visual overview of the grid reference system."""
        overview = "Grid Reference System:\n"
        overview += "Columns: " + " ".join(self.column_labels) + "\n"
        overview += "Rows: " + " ".join(self.row_labels) + "\n\n"
        
        # Show a few example references
        examples = [
            (0, 0, "A1"), (9, 0, "J1"), (19, 0, "T1"),
            (0, 7, "A8"), (9, 7, "J8"), (19, 7, "T8"),
            (0, 14, "A15"), (9, 14, "J15"), (19, 14, "T15")
        ]
        
        overview += "Example References:\n"
        for x, y, ref in examples:
            overview += f"  {ref} = ({x},{y})\n"
        
        return overview


class RelativePositioning:
    """Relative positioning system using landmarks and directions."""
    
    def __init__(self, grid_builder):
        self.grid_builder = grid_builder
        self.landmarks: Dict[str, Tuple[int, int]] = {}
        
    def add_landmark(self, name: str, x: int, y: int):
        """Add a named landmark for relative positioning."""
        self.landmarks[name] = (x, y)
    
    def get_relative_position(self, description: str) -> Optional[Tuple[int, int]]:
        """Parse relative position descriptions."""
        description = description.lower().strip()
        
        # Pattern: "X tiles [direction] of [landmark]"
        direction_pattern = r'(\d+)\s*tiles?\s*(north|south|east|west|up|down|left|right)\s*of\s*([a-zA-Z0-9_]+)'
        match = re.search(direction_pattern, description)
        
        if match:
            distance = int(match.group(1))
            direction = match.group(2)
            landmark = match.group(3)
            
            if landmark in self.landmarks:
                base_x, base_y = self.landmarks[landmark]
                
                # Calculate new position based on direction
                if direction in ['north', 'up']:
                    return (base_x, base_y - distance)
                elif direction in ['south', 'down']:
                    return (base_x, base_y + distance)
                elif direction in ['east', 'right']:
                    return (base_x + distance, base_y)
                elif direction in ['west', 'left']:
                    return (base_x - distance, base_y)
        
        # Pattern: "center of [landmark]"
        center_pattern = r'center\s+of\s+([a-zA-Z0-9_]+)'
        match = re.search(center_pattern, description)
        if match:
            landmark = match.group(1)
            if landmark in self.landmarks:
                return self.landmarks[landmark]
        
        return None
    
    def get_available_landmarks(self) -> str:
        """Get list of available landmarks for relative positioning."""
        if not self.landmarks:
            return "No landmarks available. Use add_landmark() to create them."
        
        result = "Available landmarks for relative positioning:\n"
        for name, (x, y) in self.landmarks.items():
            result += f"  {name}: ({x},{y})\n"
        return result


class ZonePositioning:
    """Zone-based positioning system."""
    
    def __init__(self, width: int = 20, height: int = 15):
        self.width = width
        self.height = height
        self.zones = self._create_zones()
    
    def _create_zones(self) -> Dict[str, Dict[str, Any]]:
        """Create logical zones for the map."""
        zones = {
            "northwest": {"x_range": (0, 9), "y_range": (0, 7), "center": (4, 3)},
            "northeast": {"x_range": (10, 19), "y_range": (0, 7), "center": (14, 3)},
            "southwest": {"x_range": (0, 9), "y_range": (8, 14), "center": (4, 11)},
            "southeast": {"x_range": (10, 19), "y_range": (8, 14), "center": (14, 11)},
            "center": {"x_range": (5, 14), "y_range": (3, 11), "center": (9, 7)},
            "north": {"x_range": (0, 19), "y_range": (0, 4), "center": (9, 2)},
            "south": {"x_range": (0, 19), "y_range": (10, 14), "center": (9, 12)},
            "east": {"x_range": (15, 19), "y_range": (0, 14), "center": (17, 7)},
            "west": {"x_range": (0, 4), "y_range": (0, 14), "center": (2, 7)}
        }
        return zones
    
    def get_zone_position(self, zone_name: str, position: str = "center") -> Optional[Tuple[int, int]]:
        """Get a position within a specified zone."""
        zone_name = zone_name.lower()
        if zone_name not in self.zones:
            return None
        
        zone = self.zones[zone_name]
        
        if position == "center":
            return zone["center"]
        elif position == "random":
            import random
            x = random.randint(zone["x_range"][0], zone["x_range"][1])
            y = random.randint(zone["y_range"][0], zone["y_range"][1])
            return (x, y)
        elif position in ["north", "top"]:
            return (zone["center"][0], zone["y_range"][0])
        elif position in ["south", "bottom"]:
            return (zone["center"][0], zone["y_range"][1])
        elif position in ["east", "right"]:
            return (zone["x_range"][1], zone["center"][1])
        elif position in ["west", "left"]:
            return (zone["x_range"][0], zone["center"][1])
        
        return zone["center"]
    
    def get_zone_overview(self) -> str:
        """Get overview of available zones."""
        result = "Available zones for positioning:\n"
        for zone_name, zone_info in self.zones.items():
            x_range = zone_info["x_range"]
            y_range = zone_info["y_range"]
            center = zone_info["center"]
            result += f"  {zone_name}: x({x_range[0]}-{x_range[1]}) y({y_range[0]}-{y_range[1]}) center{center}\n"
        return result


class SmartPositioning:
    """Combined positioning system that tries multiple approaches."""
    
    def __init__(self, grid_builder, width: int = 20, height: int = 15):
        self.grid_builder = grid_builder
        self.grid_ref = GridReferencePositioning(width, height)
        self.relative = RelativePositioning(grid_builder)
        self.zones = ZonePositioning(width, height)
        
    def parse_position(self, position_input: str) -> Optional[Tuple[int, int]]:
        """Try to parse a position using multiple positioning systems."""
        # Try grid reference first (most precise)
        if re.match(r'^[A-Z]\d+$', position_input.upper()):
            coords = self.grid_ref.grid_ref_to_coords(position_input)
            if coords:
                return coords
        
        # Try relative positioning
        coords = self.relative.get_relative_position(position_input)
        if coords:
            return coords
        
        # Try zone positioning
        zone_match = re.match(r'^([a-zA-Z]+)(?:\s+([a-zA-Z]+))?$', position_input.lower())
        if zone_match:
            zone_name = zone_match.group(1)
            position = zone_match.group(2) or "center"
            coords = self.zones.get_zone_position(zone_name, position)
            if coords:
                return coords
        
        # Try raw coordinates as fallback
        coord_match = re.match(r'^\(?(\d+)\s*,\s*(\d+)\)?$', position_input)
        if coord_match:
            x, y = int(coord_match.group(1)), int(coord_match.group(2))
            if 0 <= x < self.grid_ref.width and 0 <= y < self.grid_ref.height:
                return (x, y)
        
        return None
    
    def get_positioning_help(self) -> str:
        """Get comprehensive help for all positioning systems."""
        help_text = "=== SMART POSITIONING SYSTEM ===\n\n"
        
        help_text += "1. GRID REFERENCES (Recommended):\n"
        help_text += "   Use letters and numbers like 'B3', 'J8', 'T15'\n"
        help_text += self.grid_ref.get_grid_overview() + "\n"
        
        help_text += "2. RELATIVE POSITIONING:\n"
        help_text += "   '3 tiles north of player', 'center of room1'\n"
        help_text += self.relative.get_available_landmarks() + "\n"
        
        help_text += "3. ZONE POSITIONING:\n"
        help_text += "   'northwest', 'center', 'east center'\n"
        help_text += self.zones.get_zone_overview() + "\n"
        
        help_text += "4. RAW COORDINATES (fallback):\n"
        help_text += "   Use (x,y) format like (5,7) or 5,7\n"
        
        return help_text

