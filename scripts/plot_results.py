#!/usr/bin/env python3
"""Plot verified timings; requires matplotlib (not needed for cluster execution)."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "results" / "timings.png")
    args = parser.parse_args()
    groups = defaultdict(list)
    for path in args.paths:
        with path.open() as stream:
            for row in csv.DictReader(stream):
                if row["exit_code"] != "0" or row["verified"] != "True":
                    raise SystemExit("Unverified run in " + str(path))
                groups[(row["framework"], int(row["nodes"]), row["job"])].append(float(row["seconds"]))
    jobs = ["wordcount", "charcount", "minmax"]
    expected = {(f, n, j) for f in ["hadoop", "spark"] for n in [1, 2] for j in jobs}
    if set(groups) != expected or any(len(v) != 3 for v in groups.values()):
        raise SystemExit("Expected exactly three verified repetitions in each of twelve groups")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    for nodes, ax in zip([1, 2], axes):
        for framework, offset, color in [("hadoop", -0.19, "#285B9A"), ("spark", 0.19, "#CE6B25")]:
            values = [groups[(framework, nodes, job)] for job in jobs]
            centers = [median(v) for v in values]
            errors = [[m - min(v) for m, v in zip(centers, values)],
                      [max(v) - m for m, v in zip(centers, values)]]
            bars = ax.bar([i + offset for i in range(3)], centers, width=0.36,
                          color=color, label=framework.capitalize(), yerr=errors, capsize=4)
            ax.bar_label(bars, labels=[f"{v:.1f}" for v in centers], padding=5, fontsize=10)
        ax.set_title(f"{nodes} active node" + ("s" if nodes == 2 else ""))
        ax.set_xticks(range(3), ["Word count", "Character count", "Min / max"])
        ax.set_axisbelow(True)
        ax.grid(axis="y", alpha=0.2)
        ax.margins(y=0.20)
    axes[0].set_ylabel("End-to-end elapsed time (seconds)")
    axes[1].legend(frameon=False)
    fig.suptitle("EE542 Lab 4 — measured Hadoop and Spark times", fontsize=16)
    fig.text(0.5, 0.02, "Median of 3 runs; error bars show min–max. 35.95 MB input, 42 files. OS caches were not cleared.",
             ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.065, 1, 0.94))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180)
    fig.savefig(args.output.with_suffix(".svg"))


if __name__ == "__main__":
    main()
