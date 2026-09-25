#!/usr/bin/env python3
"""Sum sorted Streaming keys with constant auxiliary memory; also a combiner."""
import sys

previous = None
total = 0
for line in sys.stdin:
    key, value = line.rstrip("\n").split("\t")
    if previous is not None and key != previous:
        print(f"{previous}\t{total}")
        total = 0
    previous = key
    total += int(value)
if previous is not None:
    print(f"{previous}\t{total}")
