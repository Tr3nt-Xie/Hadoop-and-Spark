#!/usr/bin/env bash
# Extension experiment: how do Hadoop and Spark scale with input size?
#
# The graded suite used 36 MB. At that size every job is dominated by fixed
# cost (YARN ApplicationMaster, one JVM plus one Python process per map task,
# Spark application start-up), so it cannot show where the frameworks differ
# in throughput. This runs the same three jobs at 256 MiB and 1 GiB on one
# and two nodes, one repetition each, with the same verification as
# benchmark.py, and leaves every run directory under results/ on the master.
#
# Run from the repository root on the laptop, after `cluster.py deploy` and
# with .local/cluster.json filled in:
#   bash scripts/extension_scaling.sh            # sizes 256 1024
#   SIZES="256" REPS=1 bash scripts/extension_scaling.sh
set -euo pipefail
SIZES=${SIZES:-256 1024}
REPS=${REPS:-1}
C="python3 scripts/cluster.py"
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a .local/extension.log; }
mkdir -p .local

for SIZE in $SIZES; do
  DATA=data-${SIZE}m
  log "=== ${SIZE} MiB: generating $DATA on both nodes (deterministic, same mirror and repeat count)"
  $C exec "test -d $DATA || python3 scripts/prepare_data.py --output $DATA --minimum-mib $SIZE"
  $C exec --role worker "test -d $DATA || python3 scripts/prepare_data.py --output $DATA --minimum-mib $SIZE"
  M=$($C exec "python3 -c \"import json;m=json.load(open('$DATA/manifest.json'));print(m['total_bytes'],len(m['files']),sorted(f['sha256'] for f in m['files'])[0][:16])\"" | tail -1)
  W=$($C exec --role worker "python3 -c \"import json;m=json.load(open('$DATA/manifest.json'));print(m['total_bytes'],len(m['files']),sorted(f['sha256'] for f in m['files'])[0][:16])\"" | tail -1)
  log "manifest master: $M | worker: $W"
  [ "$M" = "$W" ] || { log "!! datasets differ between nodes; stopping"; exit 1; }

  for NODES in 1 2; do
    log "--- ${SIZE} MiB, ${NODES} node(s): Hadoop"
    $C configure --nodes $NODES
    $C start --nodes $NODES --framework hadoop
    $C exec "source scripts/env.sh; hdfs dfs -rm -r -f -skipTrash /gutenberg /lab4-results >/dev/null 2>&1; true"
    if [ $NODES = 1 ]; then
      $C exec "python3 scripts/load_hdfs.py --shards 1 --shard 0 --data $DATA"
    else
      $C exec "python3 scripts/load_hdfs.py --shards 2 --shard 0 --data $DATA"
      $C exec --role worker "python3 scripts/load_hdfs.py --shards 2 --shard 1 --data $DATA"
    fi
    $C exec "python3 scripts/benchmark.py --framework hadoop --nodes $NODES --data $DATA --repetitions $REPS" | tee -a .local/extension.log
    log "--- ${SIZE} MiB, ${NODES} node(s): Spark"
    $C start --nodes $NODES --framework spark
    $C exec "python3 scripts/benchmark.py --framework spark --nodes $NODES --data $DATA --repetitions $REPS" | tee -a .local/extension.log
  done
done
log "=== done; fetch with: python3 scripts/cluster.py download"
