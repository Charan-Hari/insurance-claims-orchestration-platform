"""Assemble the Operations Portal demo GIF from captured PNG frames.

Run ``node scripts/capture-demo.mjs`` first to produce ``docs/demo/frames``.
The GIF is downscaled and colour-quantised so it stays small enough to embed
directly in the repository README.

Usage:
    python scripts/build-demo-gif.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FRAME_DIR = ROOT / "docs" / "demo" / "frames"
OUTPUT = ROOT / "docs" / "demo" / "operations-portal-demo.gif"

TARGET_WIDTH = 1000
FRAME_DURATION_MS = 140
MAX_COLORS = 128


def load_frames() -> list[Image.Image]:
    """Loads, resizes, and quantises every captured frame in order."""
    paths = sorted(FRAME_DIR.glob("frame-*.png"))
    if not paths:
        raise SystemExit(f"No frames found in {FRAME_DIR}. Run scripts/capture-demo.mjs first.")

    frames: list[Image.Image] = []
    for path in paths:
        with Image.open(path) as source:
            image = source.convert("RGB")
            ratio = TARGET_WIDTH / image.width
            size = (TARGET_WIDTH, max(1, round(image.height * ratio)))
            frames.append(image.resize(size, Image.LANCZOS).quantize(colors=MAX_COLORS, method=Image.MEDIANCUT))
    return frames


def main() -> int:
    frames = load_frames()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )

    # Raw frames are a build artifact, not a deliverable.
    shutil.rmtree(FRAME_DIR, ignore_errors=True)

    size_mb = OUTPUT.stat().st_size / 1_048_576
    print(f"Wrote {OUTPUT.relative_to(ROOT)} ({len(frames)} frames, {size_mb:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
