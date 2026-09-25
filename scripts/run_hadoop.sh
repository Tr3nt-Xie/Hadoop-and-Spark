#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/scripts/env.sh"
JOB=${1:?wordcount, charcount or minmax}
INPUT=${2:?HDFS input path}
OUTPUT=${3:?new HDFS output path}
PARTITIONS=${4:-4}
[[ $PARTITIONS =~ ^[1-9][0-9]*$ ]] || exit 2
case "$JOB" in wordcount|minmax) MAPPER=wordcount_mapper.py; REDUCER=wordcount_reducer.py;;
    charcount) MAPPER=char_mapper.py; REDUCER=char_reducer.py;; *) exit 2;; esac
if hdfs dfs -test -e "$OUTPUT"; then echo "Output exists: $OUTPUT" >&2; exit 2; fi
JARS=("$HADOOP_HOME"/share/hadoop/tools/lib/hadoop-streaming-*.jar)
[[ ${#JARS[@]} == 1 && -f ${JARS[0]} ]]
COUNT_OUTPUT=$OUTPUT
[[ $JOB != minmax ]] || COUNT_OUTPUT=${OUTPUT}_counts
cd "$ROOT/hadoop"
hadoop jar "${JARS[0]}" \
  -D mapreduce.job.name="Lab4-$JOB" \
  -D mapreduce.job.reduces="$PARTITIONS" \
  -D mapreduce.input.fileinputformat.split.maxsize=4194304 \
  -files "$MAPPER,$REDUCER$( [[ $REDUCER != char_reducer.py ]] || printf ',wordcount_reducer.py')" \
  -input "$INPUT" -output "$COUNT_OUTPUT" \
  -mapper "python3 $MAPPER" -combiner "python3 $REDUCER" -reducer "python3 $REDUCER" \
  -cmdenv PYTHONIOENCODING=utf-8
if [[ $JOB == minmax ]]; then
  hadoop jar "${JARS[0]}" -D mapreduce.job.name=Lab4-minmax-final \
    -D mapreduce.job.reduces=1 -files minmax_reducer.py \
    -input "$COUNT_OUTPUT" -output "$OUTPUT" -mapper /bin/cat \
    -reducer 'python3 minmax_reducer.py' -cmdenv PYTHONIOENCODING=utf-8
fi
