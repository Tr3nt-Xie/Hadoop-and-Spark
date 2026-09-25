"""Shared PySpark implementations. The cluster is selected by spark-submit."""
import argparse
import json
from collections import Counter


def extremes_merge(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0], key=lambda p: (p[1], p[0])),
            min(a[1], b[1], key=lambda p: (-p[1], p[0])))


def run(job):
    from pyspark import SparkContext
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--partitions", type=int, default=4)
    args = parser.parse_args()
    with SparkContext(appName="Lab4-" + job) as sc:
        print("LAB4_CONTEXT " + json.dumps({"application_id": sc.applicationId,
              "master": sc.master, "default_parallelism": sc.defaultParallelism}))
        lines = sc.textFile(args.input, minPartitions=args.partitions)
        if job == "charcount":
            pairs = lines.flatMap(lambda line: [(f"U+{ord(c):04X}", n)
                                               for c, n in Counter(line).items()])
        else:
            pairs = lines.flatMap(lambda line: line.split()).map(lambda word: (word, 1))
        counts = pairs.reduceByKey(lambda a, b: a + b, numPartitions=args.partitions)
        if job == "minmax":
            result = counts.aggregate(None, lambda acc, p: extremes_merge(acc, (p, p)),
                                      extremes_merge)
            records = [] if result is None else [
                f"MIN\t{result[0][0]}\t{result[0][1]}",
                f"MAX\t{result[1][0]}\t{result[1][1]}"]
            sc.parallelize(records, 1).saveAsTextFile(args.output)
        else:
            counts.map(lambda p: f"{p[0]}\t{p[1]}").saveAsTextFile(args.output)
