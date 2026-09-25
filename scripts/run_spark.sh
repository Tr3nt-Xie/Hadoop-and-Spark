#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/scripts/env.sh"
JOB=${1:?wordcount, charcount or minmax}
INPUT=${2:?HDFS input URI}
OUTPUT=${3:?new HDFS output URI}
NODES=${4:?1 or 2}
[[ $NODES == 1 || $NODES == 2 ]] || exit 2
case "$JOB" in wordcount|charcount|minmax) ;; *) exit 2;; esac
spark-submit --master spark://lab4-master:7077 --deploy-mode client \
  --driver-memory 512m --executor-memory 1g --executor-cores 2 \
  --total-executor-cores "$((NODES * 2))" \
  --conf spark.executor.cores=2 --conf spark.dynamicAllocation.enabled=false \
  --conf spark.eventLog.enabled=true --conf spark.eventLog.dir=file:///home/ubuntu/lab4-events \
  --conf spark.driver.host=lab4-master \
  --conf spark.hadoop.mapreduce.input.fileinputformat.split.maxsize=4194304 \
  --py-files "$ROOT/spark/jobs.py" "$ROOT/spark/spark_${JOB}.py" \
  --input "$INPUT" --output "$OUTPUT" --partitions 4
