#!/usr/bin/env python3
"""Run on the master. Save durations, output hashes and full correctness checks.

No failed run is silently discarded. Time includes framework startup/submission,
all job stages and output persistence, but excludes preflight and result validation.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def shell(command):
    return subprocess.check_output(["bash", "-c", "source scripts/env.sh; " + command],
                                   cwd=ROOT, text=True, encoding="utf-8", stderr=subprocess.STDOUT)


def json_url(url):
    with urlopen(url, timeout=15) as response:
        return json.load(response)


def verify_output(job, content, expected):
    actual = {}
    for line in content.splitlines():
        fields = line.split("\t")
        key = fields[0]
        if key in actual:
            raise ValueError("Duplicate output key: " + repr(key))
        if job == "minmax":
            if len(fields) != 3:
                raise ValueError("Invalid min/max output")
            actual[key] = [fields[1], int(fields[2])]
        else:
            if len(fields) != 2:
                raise ValueError("Invalid count output")
            actual[key] = int(fields[1])
    if actual != expected:
        raise ValueError(f"Output mismatch: {len(actual)} actual keys; {len(expected)} expected keys")
    canonical = json.dumps(actual, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--framework", choices=["hadoop", "spark"], required=True)
    p.add_argument("--nodes", type=int, choices=[1, 2], required=True)
    p.add_argument("--data", type=Path, default=ROOT / "data")
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--jobs", nargs="+", choices=["wordcount", "charcount", "minmax"],
                   default=["wordcount", "charcount", "minmax"])
    a = p.parse_args()
    if a.repetitions < 1:
        p.error("--repetitions must be positive")
    # This path is deliberately fixed to avoid confusing local files with HDFS.
    input_uri = "hdfs://lab4-master:9000/gutenberg"
    expected = json.loads((a.data / "expected.json").read_text(encoding="utf-8"))
    manifest = (a.data / "manifest.json").read_bytes()
    run_id = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + f"-{a.framework}-{a.nodes}n"
    out = ROOT / "results" / run_id
    out.mkdir(parents=True)
    (out / "manifest.json").write_bytes(manifest)
    hdfs_report = shell("hdfs dfsadmin -report")
    (out / "hdfs-report.txt").write_text(hdfs_report)
    if f"Live datanodes ({a.nodes})" not in hdfs_report:
        raise SystemExit("HDFS node count mismatch")
    # Compare HDFS names/lengths/checksums to the exact local bytes before timing.
    import shlex
    input_check = shell("hdfs dfs -ls /gutenberg")
    (out / "input-list.txt").write_text(input_check)
    entries = json.loads(manifest)["files"]
    listed_names = {line.split()[-1].rsplit("/", 1)[-1] for line in input_check.splitlines() if line.startswith("-")}
    if listed_names != {entry["name"] for entry in entries}:
        raise SystemExit("HDFS input file list differs from manifest")
    for entry in entries:
        command = "source scripts/env.sh; hdfs dfs -cat " + shlex.quote("/gutenberg/" + entry["name"])
        raw = subprocess.check_output(["bash", "-c", command], cwd=ROOT)
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise SystemExit("HDFS input bytes differ: " + entry["name"])
    for attempt in range(30):
        if a.framework == "spark":
            cluster = json_url("http://lab4-master:8080/json/")
            live = [w for w in cluster["workers"] if w["state"] == "ALIVE"]
            hosts = {w["host"] for w in live}
        else:
            cluster = json_url("http://lab4-master:8088/ws/v1/cluster/nodes")
            live = [n for n in (cluster.get("nodes") or {}).get("node", []) if n["state"] == "RUNNING"]
            hosts = {n["nodeHostName"] for n in live}
        if len(hosts) == a.nodes:
            break
        time.sleep(2)
    else:
        raise SystemExit("Compute worker count mismatch")
    (out / "cluster.json").write_text(json.dumps(cluster, indent=2))
    (out / "system.txt").write_text(shell("uname -a; free -m; df -h /; java -version; python3 --version; jps"))
    fields = ["framework", "nodes", "job", "repetition", "seconds", "exit_code", "verified", "output_sha256", "output_uri"]
    with (out / "timings.csv").open("w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fields)
        writer.writeheader()
        # Do not drop first-run startup costs or claim OS caches have been cleared.
        for repetition in range(1, a.repetitions + 1):
            for job in a.jobs:
                output_uri = f"hdfs://lab4-master:9000/lab4-results/{run_id}/{job}-{repetition}"
                command = ["bash", str(ROOT / f"scripts/run_{a.framework}.sh"), job, input_uri, output_uri]
                if a.framework == "spark":
                    command.append(str(a.nodes))
                log_path = out / f"{job}-{repetition}.log"
                print(f"START {a.framework} {a.nodes} nodes {job} repetition {repetition}", flush=True)
                with log_path.open("w") as log:
                    start = time.perf_counter()
                    try:
                        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
                        exit_code = result.returncode
                    except subprocess.TimeoutExpired:
                        # Hadoop/YARN apps may survive client timeout: stop suite, inspect cluster.
                        exit_code = 124
                    elapsed = time.perf_counter() - start
                row = dict(framework=a.framework, nodes=a.nodes, job=job, repetition=repetition,
                           seconds=round(elapsed, 6), exit_code=exit_code, verified=False,
                           output_sha256="", output_uri=output_uri)
                error = None
                if exit_code == 0:
                    try:
                        content = shell("hdfs dfs -cat " + shlex.quote(output_uri + "/part-*") + " 2>/dev/null")
                        (out / f"{job}-{repetition}.tsv").write_text(content, encoding="utf-8")
                        row["output_sha256"] = verify_output(job, content, expected[job])
                        row["verified"] = True
                    except (ValueError, subprocess.CalledProcessError) as exc:
                        error = str(exc)
                writer.writerow(row)
                csvfile.flush()
                print(json.dumps(row), flush=True)
                if exit_code or error:
                    raise SystemExit(error or f"Job failed: {exit_code}; inspect {log_path} and active cluster applications")
    print("COMPLETED " + str(out), flush=True)


if __name__ == "__main__":
    main()
