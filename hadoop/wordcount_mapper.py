#!/usr/bin/env python3
"""Preserve the handout's case-sensitive, whitespace-separated words."""
import sys

for line in sys.stdin:
    for word in line.split():
        print(f"{word}\t1")
