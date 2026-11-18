"""Build a light/dark comparison sheet of brand proposals.

Usage: python3 preview.py <proposals_dir>
Each sub-directory of <proposals_dir> must hold the PNG set made by render.cjs.
Writes <proposals_dir>/preview.png (one row per proposal, light then dark).
"""

# ruff: noqa: INP001  (a script run by path from docs/brand, not part of a package)
from pathlib import Path
import sys

from PIL import Image

CELL_W, CELL_H = 780, 500


def build(root: Path) -> Path:
    """Compose the preview sheet.

    Args:
        root (Path): Directory holding one sub-directory per proposal.

    Returns:
        Path: Path of the written preview image.

    """
    names = sorted(p.name for p in root.iterdir() if (p / "icon@2x.png").exists())
    sheet = Image.new("RGB", (CELL_W * 2, CELL_H * len(names)), "white")
    for row, name in enumerate(names):
        for col, (bg, logo) in enumerate((("#FFFFFF", "logo@2x.png"), ("#1C1C1E", "dark_logo@2x.png"))):
            cell = Image.new("RGB", (CELL_W, CELL_H), bg)
            icon = Image.open(root / name / "icon@2x.png").resize((220, 220), Image.LANCZOS)
            cell.paste(icon, ((CELL_W - 220) // 2, 20), icon)
            wordmark = Image.open(root / name / logo)
            wordmark = wordmark.resize((int(wordmark.width * 0.45), int(wordmark.height * 0.45)), Image.LANCZOS)
            cell.paste(wordmark, ((CELL_W - wordmark.width) // 2, 270), wordmark)
            sheet.paste(cell, (col * CELL_W, row * CELL_H))
    out = root / "preview.png"
    sheet.save(out)
    return out


if __name__ == "__main__":
    sys.stdout.write(f"{build(Path(sys.argv[1]))}\n")
