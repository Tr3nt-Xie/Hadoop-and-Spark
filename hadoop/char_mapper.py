#!/usr/bin/env python3
"""Count Unicode code points, including spaces/tabs, excluding record endings.

U+XXXX keys prevent whitespace characters from corrupting Streaming's TSV.
Per-line aggregation reduces emitted records without changing the counts.
"""
import sys
from collections import Counter

for line in sys.stdin:
    for char, count in Counter(line.rstrip("\r\n")).items():
        print(f"U+{ord(char):04X}\t{count}")
