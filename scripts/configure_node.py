#!/usr/bin/env python3
"""Configure only the dedicated Lab4 installations; never format HDFS here."""
import argparse
import ipaddress
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent


def xml(path, values):
    root = Element("configuration")
    for name, value in values.items():
        prop = SubElement(root, "property")
        SubElement(prop, "name").text = name
        SubElement(prop, "value").text = str(value)
    indent(root)
    ElementTree(root).write(path, encoding="unicode", xml_declaration=True)


def configure(master_ip, worker_ip, role, nodes, prefix=Path("/opt"), home=Path("/home/ubuntu")):
    for value in (master_ip, worker_ip):
        ipaddress.IPv4Address(value)
    conf = prefix / "hadoop/etc/hadoop"
    spark = prefix / "spark/conf"
    conf.mkdir(parents=True, exist_ok=True)
    spark.mkdir(parents=True, exist_ok=True)
    state = home / f"lab4-state/{nodes}-nodes"
    for path in (state / "nn", state / "dn", state / "yarn-local", state / "yarn-logs",
                 state / "spark-work", home / "lab4-events"):
        path.mkdir(parents=True, exist_ok=True)
    xml(conf / "core-site.xml", {"fs.defaultFS": "hdfs://lab4-master:9000"})
    xml(conf / "hdfs-site.xml", {
        "dfs.replication": 1, "dfs.blocksize": 4194304,
        "dfs.namenode.name.dir": str(state / "nn"), "dfs.datanode.data.dir": str(state / "dn"),
        "dfs.namenode.http-address": "lab4-master:9870",
        "dfs.namenode.datanode.registration.ip-hostname-check": "false"})
    xml(conf / "mapred-site.xml", {
        "mapreduce.framework.name": "yarn",
        "mapreduce.jobhistory.address": "lab4-master:10020",
        "mapreduce.jobhistory.webapp.address": "lab4-master:19888",
        "mapreduce.application.classpath": "$HADOOP_MAPRED_HOME/share/hadoop/mapreduce/*:$HADOOP_MAPRED_HOME/share/hadoop/mapreduce/lib/*",
        "mapreduce.map.memory.mb": 512, "mapreduce.map.java.opts": "-Xmx256m",
        "mapreduce.reduce.memory.mb": 512, "mapreduce.reduce.java.opts": "-Xmx256m",
        "yarn.app.mapreduce.am.resource.mb": 512,
        "yarn.app.mapreduce.am.command-opts": "-Xmx256m",
        "mapreduce.map.speculative": "false", "mapreduce.reduce.speculative": "false"})
    xml(conf / "yarn-site.xml", {
        "yarn.resourcemanager.hostname": "lab4-master",
        "yarn.nodemanager.hostname": "lab4-" + role,
        "yarn.nodemanager.aux-services": "mapreduce_shuffle",
        "yarn.nodemanager.resource.memory-mb": 2048,
        "yarn.nodemanager.resource.cpu-vcores": 2,
        "yarn.scheduler.minimum-allocation-mb": 256,
        "yarn.scheduler.maximum-allocation-mb": 2048,
        "yarn.scheduler.maximum-allocation-vcores": 2,
        "yarn.nodemanager.vmem-check-enabled": "false",
        "yarn.nodemanager.local-dirs": str(state / "yarn-local"),
        "yarn.nodemanager.log-dirs": str(state / "yarn-logs"),
        "yarn.nodemanager.env-whitelist": "JAVA_HOME,HADOOP_COMMON_HOME,HADOOP_HDFS_HOME,HADOOP_CONF_DIR,CLASSPATH_PREPEND_DISTCACHE,HADOOP_YARN_HOME,HADOOP_HOME,PATH,LANG,TZ,HADOOP_MAPRED_HOME"})
    xml(conf / "capacity-scheduler.xml", {
        "yarn.scheduler.capacity.root.queues": "default",
        "yarn.scheduler.capacity.root.default.capacity": 100,
        "yarn.scheduler.capacity.root.default.maximum-capacity": 100,
        "yarn.scheduler.capacity.resource-calculator": "org.apache.hadoop.yarn.util.resource.DominantResourceCalculator"})
    (conf / "hadoop-env.sh").write_text(
        "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64\n"
        "export HADOOP_HOME=/opt/hadoop\nexport HADOOP_MAPRED_HOME=/opt/hadoop\n"
        "export HADOOP_HEAPSIZE_MAX=256\nexport YARN_HEAPSIZE=256\n")
    workers = "lab4-master\n" + ("lab4-worker\n" if nodes == 2 else "")
    (conf / "workers").write_text(workers)
    (spark / "workers").write_text(workers)
    (spark / "spark-env.sh").write_text(
        "export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64\n"
        "export HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop\n"
        "export SPARK_MASTER_HOST=lab4-master\n"
        f"export SPARK_LOCAL_IP={master_ip if role == 'master' else worker_ip}\n"
        "export SPARK_WORKER_CORES=2\nexport SPARK_WORKER_MEMORY=1536m\n"
        "export SPARK_DAEMON_MEMORY=128m\nexport PYSPARK_PYTHON=/usr/bin/python3\n"
        f"export SPARK_WORKER_DIR={state / 'spark-work'}\n")
    (home / "lab4-topology").write_text(str(nodes) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("master_ip")
    p.add_argument("worker_ip")
    p.add_argument("role", choices=["master", "worker"])
    p.add_argument("nodes", type=int, choices=[1, 2])
    a = p.parse_args()
    configure(a.master_ip, a.worker_ip, a.role, a.nodes)
