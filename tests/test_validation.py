import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from benchmark import verify_output
from configure_node import configure


class ValidationTest(unittest.TestCase):
    def test_validation_rejects_partial_wrong_and_duplicate_results(self):
        expected = {"a": 2, "b": 1}
        for data in ("a\t2\n", "a\t3\nb\t1\n", "a\t2\na\t2\nb\t1\n"):
            with self.assertRaises(ValueError):
                verify_output("wordcount", data, expected)
        self.assertEqual(verify_output("wordcount", "a\t2\nb\t1\n", expected),
                         verify_output("wordcount", "b\t1\na\t2\n", expected))

    def test_topologies_have_separate_data_and_correct_workers(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefix, home = Path(tmp) / "opt", Path(tmp) / "home"
            nn_paths = []
            for nodes in (1, 2):
                configure("10.0.3.20", "10.0.3.21", "master", nodes, prefix, home)
                conf = prefix / "hadoop/etc/hadoop"
                for filename in ("core-site.xml", "hdfs-site.xml", "mapred-site.xml", "yarn-site.xml"):
                    root = ElementTree.parse(conf / filename)
                    props = {p.findtext("name"): p.findtext("value") for p in root.findall("property")}
                    if filename == "hdfs-site.xml":
                        nn_paths.append(props["dfs.namenode.name.dir"])
                        self.assertEqual(props["dfs.replication"], "1")
                self.assertEqual(len((conf / "workers").read_text().splitlines()), nodes)
            self.assertNotEqual(nn_paths[0], nn_paths[1])


if __name__ == "__main__":
    unittest.main()
