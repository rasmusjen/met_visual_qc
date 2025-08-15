"""Run test suite using the current Python interpreter.

Usage:
  python scripts\run_tests.py

This will try to import pytest and run tests programmatically; if pytest isn't importable,
it will shell out to `sys.executable -m pytest -q` which uses the same interpreter.
"""
import sys
import subprocess

try:
    import pytest
    # run pytest programmatically; exit code will reflect test result
    errno = pytest.main(["-q"])  # -q for concise output
    raise SystemExit(errno)
except Exception:
    # fallback to subprocess invocation so we can leverage `-m pytest`
    cmd = [sys.executable, "-m", "pytest", "-q"]
    print("Falling back to: {}".format(" ".join(cmd)))
    rc = subprocess.call(cmd)
    raise SystemExit(rc)
