#!/usr/bin/env python3
"""Load a disjoint corpus shard from each active node, outside benchmark timing."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shards", type=int, choices=[1, 2], required=True)
    p.add_argument("--shard", type=int, choices=[0, 1], required=True)
    p.add_argument("--data", type=Path, default=Path("data"))
    a = p.parse_args()
    if a.shard >= a.shards:
        p.error("shard must be less than shards")
    manifest = json.loads((a.data / "manifest.json").read_text())
    selected = [a.data / "corpus" / entry["name"] for index, entry in enumerate(manifest["files"])
                if index % a.shards == a.shard]
    if not selected or not all(path.is_file() for path in selected):
        raise SystemExit("Required local corpus files are missing")
    subprocess.run(["hdfs", "dfsadmin", "-safemode", "wait"], check=True)
    subprocess.run(["hdfs", "dfs", "-mkdir", "-p", "/gutenberg"], check=True)
    # No overwrite flag: accidentally rerunning a shard must not replace existing data.
    subprocess.run(["hdfs", "dfs", "-put", *map(str, selected), "/gutenberg/"], check=True)
    print(f"Loaded {len(selected)} files from shard {a.shard}/{a.shards}")


if __name__ == "__main__":
    main()
