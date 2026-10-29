"""Copy the demo's served assets out of Dhvani-Yantra-main (demo-only).

The server must never read the neighbouring project at runtime, so this
script performs the only read: it copies

- ``Dhvani-Yantra-main/data/audio``   → ``demo/data/static/audio``
- ``Dhvani-Yantra-main/data/gita``    → ``demo/data/static/gita``
- ``Dhvani-Yantra-main/results/P1``   → ``demo/data/static/P1``
- ``Dhvani-Yantra-main/results/P2``   → ``demo/data/static/P2``
- ``Dhvani-Yantra-main/results/P3``   → ``demo/data/static/P3``

Nothing in the source tree is written, renamed or deleted. The copies
land under ``demo/data/``, which ``demo/.gitignore`` excludes, so they
are never committed; their provenance is ``demo/DEMO_DATA.md``.

Usage::

    python -m demo.prepare_demo_static
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT_ROOT / "Dhvani-Yantra-main"
DEST = PROJECT_ROOT / "demo" / "data" / "static"

# (source path, destination name)
TREES = [
    (SOURCE / "data" / "audio", "audio"),
    (SOURCE / "data" / "gita", "gita"),
    (SOURCE / "results" / "P1", "P1"),
    (SOURCE / "results" / "P2", "P2"),
    (SOURCE / "results" / "P3", "P3"),
]


def copy_tree(src: Path, dst: Path) -> int:
    if not src.is_dir():
        print(f"skip: {src} (not found)", file=sys.stderr)
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    files = [p for p in src.rglob("*") if p.is_file()]
    for path in files:
        target = dst / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return len(files)


def main() -> int:
    total = 0
    for src, name in TREES:
        n = copy_tree(src, DEST / name)
        total += n
        print(f"{name:<6} {n:>4} file(s) → {DEST / name}")
    print(f"copied {total} file(s) into {DEST} (gitignored)")
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
