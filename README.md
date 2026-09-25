# EE542 Lab 4 — Hadoop and Spark

Word count, character frequency, and global min/max word frequency using Hadoop
Streaming and PySpark, with one-node and two-node benchmarks on the same HDFS input.

## Code structure

```text
Hadoop-and-Spark/
├── hadoop/                         # Hadoop Streaming implementations
│   ├── wordcount_mapper.py         # Emit (word, 1) pairs
│   ├── wordcount_reducer.py        # Sum counts; also used as a combiner
│   ├── char_mapper.py              # Count characters using Unicode keys
│   ├── char_reducer.py             # Reuse the sum reducer for characters
│   └── minmax_reducer.py           # Find global min/max from word counts
├── spark/                          # PySpark implementations
│   ├── jobs.py                     # Shared counting and min/max logic
│   ├── spark_wordcount.py          # Word count entry point
│   ├── spark_charcount.py          # Character count entry point
│   └── spark_minmax.py             # Min/max word frequency entry point
├── scripts/
│   ├── cluster.py                  # Laptop SSH deployment and cluster control
│   ├── install_node.sh             # Install Java, Hadoop and Spark
│   ├── configure_node.py           # Generate one/two-node configurations
│   ├── env.sh                      # Set runtime paths and environment variables
│   ├── node_service.sh             # Initialize HDFS; start/stop node services
│   ├── prepare_data.py             # Download books; generate corpus and answers
│   ├── load_hdfs.py                # Upload all input or a shard to HDFS
│   ├── run_hadoop.sh               # Submit one Hadoop task
│   ├── run_spark.sh                # Submit one Spark task
│   ├── benchmark.py               # Repeat tasks, measure time and verify outputs
│   ├── collect_participation.py    # Record successful tasks by host
│   ├── summarize.py               # Summarize timing CSVs
│   └── plot_results.py             # Plot timing comparisons as PNG/SVG
├── tests/
│   ├── test_jobs.py               # Five counting and aggregation tests
│   └── test_validation.py         # Two output-validation and configuration tests
├── config/
│   └── cluster.example.json       # Placeholder SSH/node configuration
├── benchmark-results/
│   ├── README.md                  # Measurement provenance and limitations
│   ├── hadoop-1n/timings.csv       # One-node Hadoop measurements
│   ├── hadoop-2n/timings.csv       # Two-node Hadoop measurements
│   ├── hadoop-2n-initial/timings.csv # Retained initial two-node Hadoop suite
│   ├── spark-1n/timings.csv        # One-node Spark measurements
│   └── spark-2n/timings.csv        # Two-node Spark measurements
├── README.md                      # Setup and experiment instructions
├── .gitignore                     # Exclude credentials and generated files
└── LICENSE                        # MIT license
```

Local-only directories: `.local/` (connection state), `data/` (inputs and reference
answers), and `results/` (logs and outputs). These are excluded from Git.
See [measurement notes](benchmark-results/README.md) for the recorded results' limitations.

Words are case-sensitive with punctuation retained. Characters include spaces/tabs
but exclude newlines. Min/max refers to word frequency; ties use lexicographic order.

## Setup

Use two dedicated Ubuntu 22.04 x86_64 nodes (`ubuntu` user with sudo), reachable by
SSH and each other's private IP. Both must remain reachable in one-node mode.
The installer sets up Java 11, Hadoop 3.3.6 and Spark 3.5.1; no custom compilation is needed.
Allow SSH from your IP and internal traffic between the nodes.

Run these commands from the repository root on your laptop:

```bash
python3 -m unittest discover -s tests -v
mkdir -p .local
cp config/cluster.example.json .local/cluster.json
```

Edit the copied configuration with both nodes' addresses and your SSH key path.
Set matching values below, verify each host fingerprint before accepting it, then deploy:

```bash
KEY="$HOME/.ssh/lab4-key.pem"
MASTER_IP="REPLACE_WITH_MASTER_PUBLIC_IP"
WORKER_IP="REPLACE_WITH_WORKER_PUBLIC_IP"
chmod 600 "$KEY"
for IP in "$MASTER_IP" "$WORKER_IP"; do
  ssh -i "$KEY" -o StrictHostKeyChecking=ask -o UserKnownHostsFile="$PWD/.local/known_hosts" ubuntu@"$IP" exit
done
python3 scripts/cluster.py deploy
```

Code is uploaded to `~/Hadoop-and-Spark` on both nodes. Use `cluster.py sync` after
code changes. Private keys and `.local/` stay local and are excluded from Git.

## Data

Generate at least 32 MiB by repeating three Gutenberg books. The script also creates
input hashes and reference answers. For a fresh setup, copy the exact dataset to worker:

```bash
python3 scripts/cluster.py exec 'python3 scripts/prepare_data.py --minimum-mib 32'
mkdir -p .local/shared-data
scp -i "$KEY" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$PWD/.local/known_hosts" -r ubuntu@"$MASTER_IP":/home/ubuntu/Hadoop-and-Spark/data .local/shared-data/
scp -i "$KEY" -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$PWD/.local/known_hosts" -r .local/shared-data/data ubuntu@"$WORKER_IP":/home/ubuntu/Hadoop-and-Spark/
```

Do not merge into an existing worker dataset. Loading below assumes empty HDFS input;
when resuming, check existing data instead of loading it again.

## Run benchmarks

Each benchmark runs all three tasks three times, records elapsed time, and checks
complete outputs against the reference. Replace `EXACT_*_RUN` with the directory
printed by that benchmark. Capture Hadoop participation before switching to Spark.

**One node:**

```bash
python3 scripts/cluster.py configure --nodes 1
python3 scripts/cluster.py start --nodes 1 --framework hadoop
python3 scripts/cluster.py exec 'python3 scripts/load_hdfs.py --shards 1 --shard 0'
python3 scripts/cluster.py exec 'python3 scripts/benchmark.py --framework hadoop --nodes 1'
python3 scripts/cluster.py exec 'python3 scripts/collect_participation.py results/EXACT_HADOOP_1N_RUN --framework hadoop'
python3 scripts/cluster.py start --nodes 1 --framework spark
python3 scripts/cluster.py exec 'python3 scripts/benchmark.py --framework spark --nodes 1'
python3 scripts/cluster.py exec 'python3 scripts/collect_participation.py results/EXACT_SPARK_1N_RUN --framework spark'
```

**Two nodes:** uses a separate HDFS namespace; each node uploads half the files.

```bash
python3 scripts/cluster.py configure --nodes 2
python3 scripts/cluster.py start --nodes 2 --framework hadoop
python3 scripts/cluster.py exec 'python3 scripts/load_hdfs.py --shards 2 --shard 0'
python3 scripts/cluster.py exec --role worker 'python3 scripts/load_hdfs.py --shards 2 --shard 1'
python3 scripts/cluster.py exec 'hdfs fsck /gutenberg -files -blocks -locations'
python3 scripts/cluster.py exec 'python3 scripts/benchmark.py --framework hadoop --nodes 2'
python3 scripts/cluster.py exec 'python3 scripts/collect_participation.py results/EXACT_HADOOP_2N_RUN --framework hadoop'
python3 scripts/cluster.py start --nodes 2 --framework spark
python3 scripts/cluster.py exec 'python3 scripts/benchmark.py --framework spark --nodes 2'
python3 scripts/cluster.py exec 'python3 scripts/collect_participation.py results/EXACT_SPARK_2N_RUN --framework spark'
python3 scripts/cluster.py download
```

Results download to `results/download-*`. Keep failed attempts and check for surviving
applications after timeouts. Record CPU credits on burstable instances; task-host logs
show whether both nodes actually participated.

## Results and shutdown

Summarize the four selected historical suites:

```bash
python3 scripts/summarize.py benchmark-results/hadoop-1n/timings.csv benchmark-results/spark-1n/timings.csv benchmark-results/hadoop-2n/timings.csv benchmark-results/spark-2n/timings.csv
```

Optional: install `matplotlib` in a local virtual environment and pass the same CSVs to
`scripts/plot_results.py` to create `results/timings.png` and `.svg`. Its caption describes
the recorded dataset; update it for new input. Keep the initial Hadoop suite separate.

After downloading and verifying results:

```bash
python3 scripts/cluster.py stop
```

**This stops software services only. Stop EC2 instances separately in AWS; retained
storage can still incur charges.** Update public IPs and verified SSH host entries after
restarts if needed. Reports, group video and submission PDF are separate deliverables.
