import sys
import os

# Ensure `src/` is on sys.path so tests can import the package when run from the repo root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'src')
if SRC not in sys.path:
    sys.path.insert(0, SRC)
