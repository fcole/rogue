#!/usr/bin/env python3
"""
Convert generated ASCII maps (data/generated/map_*.json) to Tiled .tmx files
using the DawnLike 16x16 tileset and the visual style from the example
quadplay/examples/rpg/castle.tmx (for walls/floors) and a simple water fill.

Current scope:
- Supported ASCII: '#', '.', '+', '~'
- One floor variant (learned from castle Base layer most-common tile)
- Walls: 4-neighbor mask autotiling learned from castle Walls layer
- Doors ('+'): clear walls at that position (no door sprite yet)
- Water ('~'): simple fill tile (picked from world.tmx common ground tile)

Outputs .tmx files to data/tmx/<map_id>.tmx

This keeps logic minimal and data-driven so we can easily refine the palette
later (e.g., add real door sprites, water edge autotiling, multiple floors).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple


TILESET_IMAGE = os.path.join("quadplay", "sprites", "dawnlike-level-16x16.png")
TILESET_COLUMNS = 48
TILESET_TILECOUNT = 2784
TILE_SIZE = 16

# Enemy sprites from dawnlike-npcs-16x16.png
# NPC tileset starts at firstgid 3000 to avoid conflicts with level tiles
# Based on typical DawnLike sprite sheet organization:
# - Goblins: usually in early positions (green humanoids)
# - Ogres: larger creatures, often in middle sections
# - Spirits/Ghosts: ethereal creatures, often in later sections
ENEMY_GIDS = {
    'goblin': 3581,   # Row 1, Column 24 (likely goblin area)
    'ogre': 3037,     # Row 2, Column 12 (likely large creature area)
    'spirit': 3619,   # Row 3, Column 16 (likely ethereal area)
}

# NPC tileset constants
NPC_TILESET_FIRSTGID = 3000
NPC_TILESET_IMAGE = os.path.join("quadplay", "sprites", "dawnlike-npcs-16x16.png")
NPC_TILESET_COLUMNS = 48  # 768/16 = 48 columns
NPC_TILESET_TILECOUNT = 1440  # 48 * 30 = 1440 total tiles

CASTLE_TMX = os.path.join("quadplay", "examples", "rpg", "castle.tmx")
WORLD_TMX = os.path.join("quadplay", "examples", "rpg", "world.tmx")


@dataclass
class LearnedPalette:
    floor_gid: int
    water_gid: int
    wall_mask_to_gid: Dict[int, int]


def _parse_tmx_layer_grid(layer: ET.Element, width: int, height: int) -> List[List[int]]:
    data = layer.find("data")
    assert data is not None and data.get("encoding") == "csv", "TMX layers must be CSV-encoded"
    raw = re.split(r"[\s,]+", data.text.strip())
    ints = [int(x) for x in raw if x]
    assert len(ints) == width * height, f"Unexpected tile count in layer {layer.get('name')}"
    return [ints[i * width:(i + 1) * width] for i in range(height)]


def learn_from_examples() -> LearnedPalette:
    # Parse castle.tmx to learn walls and pick a floor
    ctree = ET.parse(CASTLE_TMX)
    croot = ctree.getroot()
    Wc, Hc = int(croot.get("width")), int(croot.get("height"))
    layers = {L.get("name"): _parse_tmx_layer_grid(L, Wc, Hc) for L in croot.findall("layer")}

    base = layers.get("Base") or layers.get("Ground")
    walls = layers.get("Walls")
    if walls is None or base is None:
        raise SystemExit("castle.tmx must have 'Base' (or 'Ground') and 'Walls' layers")

    # Floor: choose the most common non-zero tile in the Base layer
    floor_counts = Counter(v for row in base for v in row if v)
    floor_gid, _ = floor_counts.most_common(1)[0]

    # Learn wall bitmask -> gid mapping from the castle 'Walls' layer
    def is_wall_at(x: int, y: int) -> bool:
        return 0 <= x < Wc and 0 <= y < Hc and walls[y][x] != 0

    mask_gid_counts: Counter[Tuple[int, int]] = Counter()
    for y in range(Hc):
        for x in range(Wc):
            gid = walls[y][x]
            if gid == 0:
                continue
            mask = (
                (1 if is_wall_at(x, y - 1) else 0) |
                (2 if is_wall_at(x + 1, y) else 0) |
                (4 if is_wall_at(x, y + 1) else 0) |
                (8 if is_wall_at(x - 1, y) else 0)
            )
            mask_gid_counts[(mask, gid)] += 1

    # For each mask, choose the most common gid seen in the example
    wall_mask_to_gid: Dict[int, int] = {}
    for mask in range(16):
        # gather all candidates for this mask
        candidates = [(gid, c) for (m, gid), c in mask_gid_counts.items() if m == mask]
        if candidates:
            gid = max(candidates, key=lambda t: t[1])[0]
            wall_mask_to_gid[mask] = gid

    # Curated overrides to avoid decorative one-offs (e.g., torches, statues)
    # These IDs come from castle.tmx and correspond to the plain blue/gray wall set
    curated: Dict[int, int] = {
        0b0011: 97,   # corner (N+E)
        0b0110: 1,    # corner (E+S)
        0b1100: 241,  # corner (S+W)
        0b1001: 289,  # corner (W+N)
        0b0101: 49,   # vertical
        0b1010: 145,  # horizontal
        0b1110: 158,  # T (E+S+W)
        0b1101: 49,   # T (N+S+W) -> vertical stem
        0b1011: 145,  # T (N+E+W) -> horizontal stem
        0b0111: 49,   # T (E+S+N) -> vertical stem
        0b0001: 49,   # cap (N)
        0b0010: 145,  # cap (E)
        0b0100: 49,   # cap (S)
        0b1000: 145,  # cap (W)
        0b1111: 145,  # interior
        0b0000: 145,  # isolated
    }

    # Apply curated overrides
    wall_mask_to_gid.update(curated)

    # Provide sensible fallbacks for any remaining missing masks
    # Use the dominant horizontal and vertical tiles if available; else any present gid
    horiz_gid = wall_mask_to_gid.get(0b1010)  # E + W
    vert_gid = wall_mask_to_gid.get(0b0101)   # N + S
    any_gid = next(iter(wall_mask_to_gid.values())) if wall_mask_to_gid else 1
    full_gid = wall_mask_to_gid.get(0b1111, any_gid)

    for mask in range(16):
        if mask not in wall_mask_to_gid:
            if mask in (0b0010, 0b1000, 0b1010):  # E or W or E+W
                wall_mask_to_gid[mask] = horiz_gid or full_gid
            elif mask in (0b0001, 0b0100, 0b0101):  # N or S or N+S
                wall_mask_to_gid[mask] = vert_gid or full_gid
            else:
                wall_mask_to_gid[mask] = full_gid

    # Water: for castle-style ponds, use the blue panel tile seen in castle.tmx
    # (this matches the reference example without shoreline autotiling).
    water_gid = 897

    return LearnedPalette(floor_gid=floor_gid, water_gid=water_gid, wall_mask_to_gid=wall_mask_to_gid)


def ascii_to_tmx(json_path: str, out_dir: str, pal: LearnedPalette) -> str:
    with open(json_path, "r") as f:
        data = json.load(f)

    map_id = data.get("id") or os.path.splitext(os.path.basename(json_path))[0]
    tiles_str: str = data["tiles"]
    width: int = data["width"]
    height: int = data["height"]
    entities = data.get("entities", {})

    # Build char grid
    lines = [line for line in tiles_str.splitlines() if line]
    assert len(lines) == height and all(len(line) == width for line in lines), (
        f"ASCII grid dims mismatch: expected {width}x{height}, got {len(lines[0])}x{len(lines)}"
    )

    # Prepare layers (CSV order: row-major, width*height integers)
    base = [0] * (width * height)
    walls = [0] * (width * height)
    decorations = [0] * (width * height)
    foreground = [0] * (width * height)
    details = [0] * (width * height)  # props like chests/tombs
    enemies = [0] * (width * height)  # enemy sprites

    def idx(x: int, y: int) -> int:
        return y * width + x

    # First pass: place base and mark wall candidates
    wall_bool = [[False] * width for _ in range(height)]
    for y, row in enumerate(lines):
        for x, ch in enumerate(row):
            if ch == '#':
                wall_bool[y][x] = True
            elif ch == '~':
                base[idx(x, y)] = pal.water_gid
            else:
                # '.' or '+' -> floor
                base[idx(x, y)] = pal.floor_gid

    # Second pass: compute wall masks and place tiles
    for y in range(height):
        for x in range(width):
            if not wall_bool[y][x]:
                continue
            def iswall(xx: int, yy: int) -> bool:
                return 0 <= xx < width and 0 <= yy < height and wall_bool[yy][xx]
            mask = (
                (1 if iswall(x, y - 1) else 0) |
                (2 if iswall(x + 1, y) else 0) |
                (4 if iswall(x, y + 1) else 0) |
                (8 if iswall(x - 1, y) else 0)
            )
            walls[idx(x, y)] = pal.wall_mask_to_gid.get(mask, pal.wall_mask_to_gid[0b1111])

    # Doors: place horizontal doors on Walls (1416). For vertical doors, 
    # follow the castle.tmx convention: Decorations=670 at the door cell,
    # and Foreground=718 one tile below as a cap; clear Walls at that cell.
    for y, row in enumerate(lines):
        for x, ch in enumerate(row):
            if ch != '+':
                continue
            # Orientation by neighboring walls in the raw ASCII (wall_bool)
            left = (x - 1 >= 0 and wall_bool[y][x - 1])
            right = (x + 1 < width and wall_bool[y][x + 1])
            up = (y - 1 >= 0 and wall_bool[y - 1][x])
            down = (y + 1 < height and wall_bool[y + 1][x])

            if left or right:
                # Horizontal door
                walls[idx(x, y)] = 1416
            elif up or down:
                # Vertical door: place the top door decal on the upper wall tile,
                # and the cap in the opening. Clear the opening on Walls.
                walls[idx(x, y)] = 0
                decorations[idx(x, y-1)] = 670
                if y < height:
                    foreground[idx(x, y)] = 718
            else:
                # Default to a horizontal-looking single door if isolated
                walls[idx(x, y)] = 1416

    # Place chest/tomb props onto Details layer for visual flavor
    # Use specific sprite IDs that read clearly on the castle floor.
    # Use clearly readable sprites:
    CHEST_GID = 1511  # signboard-like chest surrogate (wooden box on stand)
    TOMB_GID = 1509   # stone slab (tomb-like)
    # Map ASCII if entities are not provided for legacy cases
    char_entity_map = {'C': 'chest', 'T': 'tomb'}
    for y, row in enumerate(lines):
        for x, ch in enumerate(row):
            if ch in char_entity_map:
                details[idx(x, y)] = CHEST_GID if ch == 'C' else TOMB_GID
    # Also mirror from structured entities if present
    for ent_type in ('chest', 'tomb'):
        for ent in (entities or {}).get(ent_type, []) or []:
            ex = int(ent.get('x', 0)); ey = int(ent.get('y', 0))
            if 0 <= ex < width and 0 <= ey < height:
                details[idx(ex, ey)] = CHEST_GID if ent_type == 'chest' else TOMB_GID

    # Place enemy sprites on Enemies layer
    enemy_count = 0
    for ent_type in entities:
        if ent_type in ('goblin', 'ogre', 'spirit') or ent_type.startswith(('goblin_', 'ogre_', 'spirit_')):
            for ent in entities[ent_type]:
                ex = int(ent.get('x', 0)); ey = int(ent.get('y', 0))
                if 0 <= ex < width and 0 <= ey < height:
                    # Handle both regular enemy types and numbered variants (goblin_0, goblin_1, etc.)
                    base_type = ent_type.split('_')[0]  # Extract 'goblin', 'ogre', or 'spirit'
                    if base_type in ENEMY_GIDS:
                        # For numbered variants, use the GID from the test_gid property if available
                        if 'test_gid' in ent.get('properties', {}):
                            gid = int(ent['properties']['test_gid'])
                        else:
                            gid = ENEMY_GIDS[base_type]

                        enemies[idx(ex, ey)] = gid
                        enemy_count += 1
                        print(f"Placed {ent_type} at ({ex}, {ey}) using GID {gid} (local tile: {gid - NPC_TILESET_FIRSTGID})")

    if enemy_count > 0:
        print(f"\nEnemy GID mappings (local tile positions in NPC sheet):")
        for ent_type, gid in ENEMY_GIDS.items():
            local_tile = gid - NPC_TILESET_FIRSTGID
            row = local_tile // NPC_TILESET_COLUMNS
            col = local_tile % NPC_TILESET_COLUMNS
            print(f"  {ent_type}: GID {gid} -> Row {row}, Column {col}")

    # Build TMX XML
    map_el = ET.Element("map", attrib={
        "version": "1.2",
        "tiledversion": "1.2.1",
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "width": str(width),
        "height": str(height),
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "infinite": "0",
        "nextlayerid": "7",
        "nextobjectid": "1",
    })

    tileset_el = ET.SubElement(map_el, "tileset", attrib={
        "firstgid": "1",
        "name": "dawnlike-level-16x16",
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "tilecount": str(TILESET_TILECOUNT),
        "columns": str(TILESET_COLUMNS),
    })
    ET.SubElement(tileset_el, "image", attrib={
        "source": os.path.relpath(TILESET_IMAGE, os.path.dirname(os.path.join(out_dir, f"{map_id}.tmx"))),
        "width": str(TILESET_COLUMNS * TILE_SIZE),
        "height": str((TILESET_TILECOUNT // TILESET_COLUMNS + (1 if TILESET_TILECOUNT % TILESET_COLUMNS else 0)) * TILE_SIZE),
    })

    # Add NPC tileset for enemy sprites
    npc_tileset_el = ET.SubElement(map_el, "tileset", attrib={
        "firstgid": str(NPC_TILESET_FIRSTGID),
        "name": "dawnlike-npcs-16x16",
        "tilewidth": str(TILE_SIZE),
        "tileheight": str(TILE_SIZE),
        "tilecount": str(NPC_TILESET_TILECOUNT),
        "columns": str(NPC_TILESET_COLUMNS),
    })
    ET.SubElement(npc_tileset_el, "image", attrib={
        "source": os.path.relpath(NPC_TILESET_IMAGE, os.path.dirname(os.path.join(out_dir, f"{map_id}.tmx"))),
        "width": str(NPC_TILESET_COLUMNS * TILE_SIZE),
        "height": str((NPC_TILESET_TILECOUNT // NPC_TILESET_COLUMNS + (1 if NPC_TILESET_TILECOUNT % NPC_TILESET_COLUMNS else 0)) * TILE_SIZE),
    })

    def add_layer(layer_id: int, name: str, arr: List[int]):
        layer_el = ET.SubElement(map_el, "layer", attrib={
            "id": str(layer_id),
            "name": name,
            "width": str(width),
            "height": str(height),
        })
        data_el = ET.SubElement(layer_el, "data", attrib={"encoding": "csv"})
        # Write CSV row-major with line breaks per row for readability
        rows = []
        for y in range(height):
            row = arr[y * width:(y + 1) * width]
            rows.append(",".join(str(v) for v in row))
        data_el.text = "\n" + "\n".join(rows) + "\n"

    add_layer(1, "Base", base)
    add_layer(2, "Walls", walls)
    add_layer(3, "Decorations", decorations)
    add_layer(4, "Foreground", foreground)
    add_layer(5, "Details", details)
    add_layer(6, "Enemies", enemies)

    # Objects: export entities as an objectgroup
    objgroup = ET.SubElement(map_el, "objectgroup", attrib={"id": "7", "name": "Objects"})
    next_obj_id = 1
    for etype, items in (entities or {}).items():
        for ent in items:
            x = int(ent.get("x", 0)) * TILE_SIZE
            y = int(ent.get("y", 0)) * TILE_SIZE
            obj = ET.SubElement(objgroup, "object", attrib={
                "id": str(next_obj_id),
                "name": etype,
                "type": etype,
                "x": str(x),
                "y": str(y),
                "width": str(TILE_SIZE),
                "height": str(TILE_SIZE),
            })
            next_obj_id += 1
            # Properties
            props = ent.get("properties") or {}
            if props:
                props_el = ET.SubElement(obj, "properties")
                for k, v in props.items():
                    ET.SubElement(props_el, "property", attrib={"name": str(k), "value": str(v)})

    # Write file
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{map_id}.tmx")
    tree = ET.ElementTree(map_el)
    tree.write(out_path, encoding="UTF-8", xml_declaration=True)
    return out_path


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("inputs", nargs="*", default=sorted(glob.glob("data/generated/map_*.json")),
                   help="Input JSON map files (default: data/generated/map_*.json)")
    p.add_argument("--out", default="data/tmx", help="Output directory for TMX files")
    args = p.parse_args(argv)

    palette = learn_from_examples()
    print(f"Using floor GID {palette.floor_gid}, water GID {palette.water_gid}")
    print("Wall mask mapping (mask -> gid):")
    for m in range(16):
        print(f"  {m:04b} -> {palette.wall_mask_to_gid[m]}")

    wrote = []
    for f in args.inputs:
        out = ascii_to_tmx(f, args.out, palette)
        wrote.append(out)
    print(f"Wrote {len(wrote)} TMX files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
