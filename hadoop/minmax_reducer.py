#!/usr/bin/env python3
"""Second job: globally reduce already aggregated word counts (one reducer).

Ties choose the lexicographically smallest word for reproducible results.
"""
import sys

smallest = largest = None
for line in sys.stdin:
    word, value = line.rstrip("\n").split("\t")
    item = (int(value), word)
    if smallest is None or item < smallest:
        smallest = item
    if largest is None or (-item[0], item[1]) < (-largest[0], largest[1]):
        largest = item
if smallest is not None:
    print(f"MIN\t{smallest[1]}\t{smallest[0]}")
    print(f"MAX\t{largest[1]}\t{largest[0]}")
