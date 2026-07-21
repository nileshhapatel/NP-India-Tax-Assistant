from pathlib import Path
import ast

def test_python_files_parse():
    root = Path(__file__).parents[1]
    ignore_dirs = {'.venv', 'node_modules', '.git', '__pycache__'}
    for path in root.rglob("*.py"):
        # skip virtualenvs, node modules and git metadata
        if any(p in ignore_dirs for p in path.parts):
            continue
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
