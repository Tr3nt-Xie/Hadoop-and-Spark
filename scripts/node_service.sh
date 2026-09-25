#!/usr/bin/env bash
# Individual daemon control avoids copying a private SSH key onto either EC2.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
source "$ROOT/scripts/env.sh"
ACTION=${1:?format, hdfs-start, hadoop-start, spark-start, stop-compute, stop, status}
ROLE=${2:?master or worker}
[[ $ROLE == master || $ROLE == worker ]] || exit 2
case "$ACTION" in
  format)
    [[ $ROLE == master ]]
    NODES=$(cat "$HOME/lab4-topology")
    [[ $NODES == 1 || $NODES == 2 ]]
    NN="$HOME/lab4-state/$NODES-nodes/nn"
    if [[ ! -f $NN/current/VERSION ]]; then
      # Refuse to overwrite any directory left by an incomplete initialization.
      [[ -z $(ls -A "$NN") ]] || { echo 'Nonempty NameNode directory; inspect manually' >&2; exit 1; }
      hdfs namenode -format -nonInteractive
    fi ;;
  hdfs-start)
    [[ $ROLE != master ]] || hdfs --daemon start namenode
    hdfs --daemon start datanode ;;
  hadoop-start)
    [[ $ROLE != master ]] || mapred --daemon start historyserver
    [[ $ROLE != master ]] || yarn --daemon start resourcemanager
    yarn --daemon start nodemanager ;;
  spark-start)
    [[ $ROLE != master ]] || "$SPARK_HOME/sbin/start-master.sh"
    "$SPARK_HOME/sbin/start-worker.sh" spark://lab4-master:7077 ;;
  stop-compute|stop)
    [[ $ROLE != master ]] || mapred --daemon stop historyserver
    "$SPARK_HOME/sbin/stop-worker.sh"
    [[ $ROLE != master ]] || "$SPARK_HOME/sbin/stop-master.sh"
    yarn --daemon stop nodemanager
    [[ $ROLE != master ]] || yarn --daemon stop resourcemanager
    if [[ $ACTION == stop ]]; then
      hdfs --daemon stop datanode
      [[ $ROLE != master ]] || hdfs --daemon stop namenode
    fi ;;
  status)
    hostname; uname -r; free -m; df -h /; jps
    [[ $ROLE != master ]] || hdfs dfsadmin -report ;;
  *) exit 2;;
esac
