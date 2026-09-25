#!/usr/bin/env python3
"""Summarize verified actual runs only; never synthesize missing measurements."""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
import statistics

p = argparse.ArgumentParser()
p.add_argument("paths", nargs="+", type=Path, help="Exact timings.csv files to include")
a = p.parse_args()
groups = defaultdict(list)
for path in a.paths:
    with path.open() as f:
        for row in csv.DictReader(f):
            if row["exit_code"] != "0" or row["verified"] != "True":
                raise SystemExit("Unverified run in " + str(path))
            groups[(row["framework"], int(row["nodes"]), row["job"])].append(float(row["seconds"]))
print("| Framework | Nodes | Job | Runs | Median seconds | Min | Max |")
print("|---|---:|---|---:|---:|---:|---:|")
for (framework, nodes, job), values in sorted(groups.items()):
    print(f"| {framework} | {nodes} | {job} | {len(values)} | {statistics.median(values):.3f} | {min(values):.3f} | {max(values):.3f} |")
