"""Test-suite wide setup.

Puts ``src/`` on ``sys.path`` so ``import agro_mirai...`` works without a
packaging/install step — consistent with how ``tools/seed_ndvi_cache.py``
resolves the package. No project package manager has been introduced yet
(Module 01 doctrine); this keeps the test suite runnable with a plain
``pytest`` invocation.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# tests must not hit Open-Meteo through the lazy weather refresh
os.environ.setdefault("AGRO_WEATHER_REFRESH", "0")
