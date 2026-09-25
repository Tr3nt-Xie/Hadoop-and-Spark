#!/usr/bin/env python3
"""Use the same sum-by-key reducer for character counts."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name("wordcount_reducer.py")), run_name="__main__")
