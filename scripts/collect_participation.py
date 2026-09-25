#!/usr/bin/env python3
"""Capture successful task hosts after a suite, outside its measured durations."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def get(url):
    with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=20) as response:
        return json.load(response)


def collect(directory, framework):
    results = {}
    for log in sorted(directory.glob("*.log")):
        text = log.read_text()
        hosts = Counter()
        evidence = []
        if framework == "hadoop":
            ids = sorted(set(re.findall(r"\bjob_\d+_\d+\b", text)))
            if not ids:
                raise RuntimeError("No Hadoop job ID in " + str(log))
            for job in ids:
                base = "http://lab4-master:19888/ws/v1/history/mapreduce/jobs/" + job
                for attempt in range(30):
                    try:
                        tasks = get(base + "/tasks")["tasks"]["task"]
                        break
                    except URLError:
                        if attempt == 29:
                            raise
                        time.sleep(2)
                for task in tasks:
                    attempts = get(base + "/tasks/" + task["id"] + "/attempts")
                    for item in attempts["taskAttempts"]["taskAttempt"]:
                        evidence.append(item)
                        if item["state"] == "SUCCEEDED":
                            hosts[item["nodeHttpAddress"].rsplit(":", 1)[0]] += 1
        else:
            context = json.loads(next(line.split("LAB4_CONTEXT ", 1)[1]
                                      for line in text.splitlines() if "LAB4_CONTEXT " in line))
            ids = [context["application_id"]]
            event_path = Path.home() / "lab4-events" / ids[0]
            for line in event_path.read_text().splitlines():
                event = json.loads(line)
                if event["Event"] == "SparkListenerTaskEnd":
                    item = event["Task Info"]
                    evidence.append({"stage": event["Stage ID"], "task": item,
                                     "reason": event["Task End Reason"]})
                    if event["Task End Reason"].get("Reason") == "Success":
                        hosts[item["Host"]] += 1
        if not hosts:
            raise RuntimeError("No successful task hosts in " + str(log))
        results[log.stem] = {"application_or_job_ids": ids, "successful_tasks_by_host": dict(hosts),
                             "attempts": evidence}
    if not results:
        raise RuntimeError("No run logs in " + str(directory))
    (directory / "participation.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({k: v["successful_tasks_by_host"] for k, v in results.items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--framework", choices=["hadoop", "spark"], required=True)
    args = parser.parse_args()
    collect(args.directory, args.framework)
