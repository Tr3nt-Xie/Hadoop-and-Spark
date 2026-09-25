#!/usr/bin/env python3
"""Laptop controller; all SSH keys stay on the laptop. No AWS lifecycle calls."""
import argparse
import ipaddress
import json
import pathlib
import shlex
import subprocess
import tarfile
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["deploy", "sync", "configure", "start", "stop-compute", "stop", "status", "exec", "download"])
    p.add_argument("--config", default=str(ROOT / ".local/cluster.json"))
    p.add_argument("--nodes", type=int, choices=[1, 2], default=1)
    p.add_argument("--framework", choices=["hadoop", "spark"], default="hadoop")
    p.add_argument("--role", choices=["master", "worker"], default="master")
    p.add_argument("command", nargs="?")
    a = p.parse_intermixed_args()
    c = json.loads(pathlib.Path(a.config).read_text())
    for role in ("master", "worker"):
        for key in ("private_ip", "public_ip"):
            ipaddress.IPv4Address(c[role][key])
    known = pathlib.Path(c["known_hosts"]).expanduser()
    if not known.is_absolute():
        known = ROOT / known
    opts = ["-i", str(pathlib.Path(c["key_path"]).expanduser()),
            "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
            "-o", "UserKnownHostsFile=" + str(known), "-o", "ConnectTimeout=15"]

    def ssh(role, command, capture=False):
        return subprocess.run(["ssh", *opts, "ubuntu@" + c[role]["public_ip"], command],
                              check=True, text=True, capture_output=capture)

    def service(role, action):
        ssh(role, f"bash ~/Hadoop-and-Spark/scripts/node_service.sh {action} {role}")

    active = ["master"] + (["worker"] if a.nodes == 2 else [])
    if a.action in ("deploy", "sync"):
        with tempfile.TemporaryDirectory() as tmp:
            package = pathlib.Path(tmp) / "lab4.tar.gz"
            with tarfile.open(package, "w:gz") as tar:
                for name in ("hadoop", "spark", "scripts", "tests"):
                    tar.add(ROOT / name, arcname=name,
                            filter=lambda member: None if "__pycache__" in member.name else member)
            for role in ("master", "worker"):
                subprocess.run(["scp", *opts, str(package),
                                "ubuntu@" + c[role]["public_ip"] + ":/home/ubuntu/lab4.tar.gz"], check=True)
                command = "mkdir -p ~/Hadoop-and-Spark && tar -xzf ~/lab4.tar.gz -C ~/Hadoop-and-Spark"
                if a.action == "deploy":
                    command += " && bash ~/Hadoop-and-Spark/scripts/install_node.sh"
                ssh(role, command)
    elif a.action == "configure":
        # Stop old daemons before changing directories or topology.
        for role in ("master", "worker"):
            service(role, "stop")
        for role in ("master", "worker"):
            hosts = f"{c['master']['private_ip']} lab4-master\n{c['worker']['private_ip']} lab4-worker\n"
            # Only replace lines carrying our two dedicated host aliases.
            command = "sudo sed -i '/[[:space:]]lab4-master\\([[:space:]]\\|$\\)/d; /[[:space:]]lab4-worker\\([[:space:]]\\|$\\)/d' /etc/hosts"
            ssh(role, command + " && printf %s " + shlex.quote(hosts) + " | sudo tee -a /etc/hosts >/dev/null")
            ssh(role, f"python3 ~/Hadoop-and-Spark/scripts/configure_node.py {c['master']['private_ip']} {c['worker']['private_ip']} {role} {a.nodes}")
        service("master", "format")
    elif a.action == "start":
        # HDFS may already be up when switching compute frameworks.
        for role in active:
            running = ssh(role, "jps", capture=True).stdout
            if "DataNode" not in running:
                service(role, "hdfs-start")
        for _ in range(30):
            report = ssh("master", "source ~/Hadoop-and-Spark/scripts/env.sh; hdfs dfsadmin -report", capture=True).stdout
            if f"Live datanodes ({a.nodes})" in report:
                break
            time.sleep(2)
        else:
            raise SystemExit("HDFS live node count did not match topology")
        for role in ("master", "worker"):
            service(role, "stop-compute")
        for role in active:
            service(role, a.framework + "-start")
    elif a.action in ("stop", "stop-compute", "status"):
        for role in ("master", "worker"):
            service(role, a.action)
    elif a.action == "exec":
        if not a.command:
            p.error("exec requires a shell command")
        ssh(a.role, "cd ~/Hadoop-and-Spark && source scripts/env.sh && bash -c " + shlex.quote(a.command))
    elif a.action == "download":
        dest = ROOT / "results" / time.strftime("download-%Y%m%dT%H%M%SZ", time.gmtime())
        dest.mkdir(parents=True)
        subprocess.run(["scp", *opts, "-r", "ubuntu@" + c["master"]["public_ip"]
                        + ":/home/ubuntu/Hadoop-and-Spark/results", str(dest)], check=True)
        subprocess.run(["scp", *opts, "-r", "ubuntu@" + c["master"]["public_ip"]
                        + ":/home/ubuntu/lab4-events", str(dest)], check=True)
        print(dest)


if __name__ == "__main__":
    main()
