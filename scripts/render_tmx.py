#!/usr/bin/env python3
"""
Render a Tiled .tmx map (orthogonal, single image tileset) to a PNG using Pillow.

Usage:
  python scripts/render_tmx.py data/tmx/map_000.tmx --out data/renders

Notes:
- Assumes a single <tileset> with an <image> referenced by the TMX.
- Supports multiple <layer> elements in draw order.
- Ignores <objectgroup> and flip flags (no flips used by our exporter).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from PIL import Image
except Exception as e:
    print("Pillow is required. Install with: uv pip install Pillow", file=sys.stderr)
    raise


def _parse_csv_layer(layer: ET.Element, width: int, height: int) -> list[list[int]]:
    data = layer.find("data")
    assert data is not None and data.get("encoding") == "csv", "Only CSV encoded layers are supported"
    raw = re.split(r"[\s,]+", data.text.strip())
    nums = [int(x) for x in raw if x]
    assert len(nums) == width * height, f"Layer {layer.get('name')} has wrong tile count"
    return [nums[i*width:(i+1)*width] for i in range(height)]


def render_tmx(tmx_path: Path, out_dir: Path) -> Path:
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    width = int(root.get("width"))
    height = int(root.get("height"))
    tw = int(root.get("tilewidth"))
    th = int(root.get("tileheight"))

    # Tileset image
    ts = root.find("tileset")
    assert ts is not None, "No tileset found"
    firstgid = int(ts.get("firstgid"))
    columns = int(ts.get("columns"))
    img_el = ts.find("image")
    assert img_el is not None, "Tileset <image> missing"
    ts_img_path = (tmx_path.parent / img_el.get("source")).resolve()

    sheet = Image.open(ts_img_path).convert("RGBA")

    # Prepare canvas
    canvas = Image.new("RGBA", (width * tw, height * th), (0, 0, 0, 0))

    # Draw layers in file order
    for layer in root.findall("layer"):
        grid = _parse_csv_layer(layer, width, height)
        for y in range(height):
            for x in range(width):
                gid = grid[y][x]
                if gid <= 0:
                    continue
                local = gid - firstgid
                if local < 0:
                    continue
                sx = (local % columns) * tw
                sy = (local // columns) * th
                tile = sheet.crop((sx, sy, sx + tw, sy + th))
                canvas.alpha_composite(tile, (x * tw, y * th))

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (tmx_path.stem + ".png")
    canvas.save(out_path)
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tmx", nargs="+", type=Path, help="Input TMX files")
    p.add_argument("--out", type=Path, default=Path("data/renders"), help="Output directory")
    args = p.parse_args(argv)

    wrote = []
    for t in args.tmx:
        wrote.append(render_tmx(t, args.out))
    print(f"Rendered {len(wrote)} map(s) → {args.out}")
    for pth in wrote:
        print(" -", pth)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

