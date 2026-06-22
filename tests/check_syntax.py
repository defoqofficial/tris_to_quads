"""Syntax validation for core modules (no bpy required for structure check)."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODULES = [
    "__init__.py",
    "operators/convert.py",
    "ui/panel.py",
    "core/mesh_graph.py",
    "core/front.py",
    "core/edge_recovery.py",
    "core/side_edge.py",
    "core/seams.py",
    "core/smoothing.py",
    "core/qmorph.py",
    "cleanup/edge_ops.py",
    "cleanup/valence.py",
]


def check_syntax(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))


def main() -> int:
    errors = 0
    for rel in MODULES:
        path = ROOT / rel
        try:
            check_syntax(path)
            print(f"OK  {rel}")
        except SyntaxError as exc:
            print(f"ERR {rel}: {exc}", file=sys.stderr)
            errors += 1
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
