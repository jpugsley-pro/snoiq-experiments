# tests/conftest.py
import sys
from pathlib import Path

# Add REPO ROOT to sys.path so 'src' (a package) is importable as 'src.*'
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
