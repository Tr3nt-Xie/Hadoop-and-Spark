#!/usr/bin/env bash
# Run as ubuntu on a dedicated Ubuntu 22.04 x86_64 Lab4 node.
set -euo pipefail
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 22.04 && $(uname -m) == x86_64 ]]
[[ $(id -un) == ubuntu ]]
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y openjdk-11-jdk python3 curl rsync
mkdir -p "$HOME/lab4-downloads" "$HOME/lab4-events" "$HOME/lab4-state"
cd "$HOME/lab4-downloads"
fetch_unpack() {
  local url=$1 name=$2 directory=$3 target=$4
  if [[ -e $target ]]; then
    [[ $(readlink -f "$target") == "/opt/$directory" ]] || {
      echo "Refusing to replace existing $target" >&2; exit 1;
    }
    return
  fi
  curl --fail --location --retry 3 --output "$name" "$url/$name"
  curl --fail --location --retry 3 --output "$name.sha512" "$url/$name.sha512"
  python3 - "$name" <<'PY'
import hashlib, pathlib, re, sys
p = pathlib.Path(sys.argv[1])
expected = re.findall(r'\b[0-9a-fA-F]{128}\b', p.with_name(p.name + '.sha512').read_text())
h = hashlib.sha512()
with p.open('rb') as f:
    for block in iter(lambda: f.read(1048576), b''):
        h.update(block)
if len(expected) != 1 or h.hexdigest() != expected[0].lower():
    raise SystemExit('SHA512 mismatch: ' + p.name)
print('SHA512 verified:', p.name)
PY
  sudo tar -xzf "$name" -C /opt
  sudo chown -R ubuntu:ubuntu "/opt/$directory"
  sudo ln -s "/opt/$directory" "$target"
}
fetch_unpack https://archive.apache.org/dist/hadoop/common/hadoop-3.3.6 \
  hadoop-3.3.6.tar.gz hadoop-3.3.6 /opt/hadoop
fetch_unpack https://archive.apache.org/dist/spark/spark-3.5.1 \
  spark-3.5.1-bin-hadoop3.tgz spark-3.5.1-bin-hadoop3 /opt/spark
java -version
python3 --version
