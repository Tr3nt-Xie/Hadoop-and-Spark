# Recorded measurements

These CSVs preserve measurements taken September 24, 2026 (Los Angeles time;
September 24–25 UTC). They are copied unchanged from the local experiment evidence.
They have not been rerun as part of preparing this upload package.

| Directory | Role | Rows |
|---|---|---:|
| `hadoop-1n` | Selected one-node Hadoop suite | 9 |
| `spark-1n` | Selected one-node Spark suite | 9 |
| `hadoop-2n` | Selected two-node Hadoop suite | 9 |
| `spark-2n` | Selected two-node Spark suite | 9 |
| `hadoop-2n-initial` | Complete retained initial two-node Hadoop suite | 9 |

Every CSV records framework, active node count, job, repetition, elapsed seconds,
exit status, verification status, canonical output SHA256 and HDFS output URI.
All 45 records report exit status zero and full output verification. The output hashes
allow comparison; the CSV flags alone are not a substitute for the full raw outputs
and logs, which are retained locally outside this package.

The input was 35,949,956 bytes in 42 files: three unique Gutenberg books repeated
14 times, including their notices. Word count produced 48,097 distinct keys and
character count produced 112. Both machines were Ubuntu 22.04 x86_64 `t2.medium`
instances with 2 vCPUs and 4 GiB RAM, using Java 11, Hadoop 3.3.6 and Spark 3.5.1.

The initial two-node Hadoop suite was retained in full because the master approached
a low T2 CPU-credit balance. The entire suite was repeated after a master stop/start;
the selected suite was not uniformly faster. Low credits do not by themselves prove
throttling. Initial observations must not be silently discarded or mixed with the
selected three-repetition groups.

Other limitations: the corpus is small and repetitive; runs were sequential rather
than randomized; OS caches were not cleared and validation can warm them; task
placement and data locality varied; control services shared master resources; and
YARN's ApplicationMaster consumed resources that differ from Spark's scheduling
overhead. These results describe this lab setup, not universal framework performance.
