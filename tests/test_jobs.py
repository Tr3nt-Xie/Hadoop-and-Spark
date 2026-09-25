"""Exercise the actual Streaming programs with partitioned/shuffled input."""
import collections
import itertools
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "spark"))
from jobs import extremes_merge


def program(name, data):
    return subprocess.check_output([sys.executable, str(ROOT / "hadoop" / name)],
                                   input=data, text=True, encoding="utf-8")


def pipeline(mapper, reducer, text):
    # Two mapper processes, local combiners, then a merged shuffle.
    lines = text.splitlines(keepends=True)
    shuffled = []
    for chunk in (lines[::2], lines[1::2]):
        mapped = program(mapper, "".join(chunk))
        combined = program(reducer, "".join(sorted(mapped.splitlines(keepends=True))))
        shuffled.extend(combined.splitlines(keepends=True))
    return program(reducer, "".join(sorted(shuffled)))


class JobsTest(unittest.TestCase):
    def test_word_semantics(self):
        text = "Hello hello Hello!\n世界 世界\t🙂\r\n\nHello 世界\n"
        result = pipeline("wordcount_mapper.py", "wordcount_reducer.py", text)
        actual = {k: int(v) for k, v in (line.split("\t") for line in result.splitlines())}
        self.assertEqual(actual, dict(collections.Counter(text.split())))

    def test_chars_preserve_whitespace_and_unicode(self):
        text = "a a\t🙂\r\n世界\n\nA\n"
        result = pipeline("char_mapper.py", "char_reducer.py", text)
        actual = {k: int(v) for k, v in (line.split("\t") for line in result.splitlines())}
        expected = collections.Counter(c for line in text.splitlines() for c in line)
        self.assertEqual(actual, {f"U+{ord(c):04X}": n for c, n in expected.items()})

    def test_minmax_global_and_ties(self):
        text = "z z\na a\nb\nc\n"
        counts = pipeline("wordcount_mapper.py", "wordcount_reducer.py", text)
        self.assertEqual(program("minmax_reducer.py", counts), "MIN\tb\t1\nMAX\ta\t2\n")

    def test_empty(self):
        for mapper, reducer in [("wordcount_mapper.py", "wordcount_reducer.py"),
                                ("char_mapper.py", "char_reducer.py")]:
            self.assertEqual(pipeline(mapper, reducer, ""), "")
        self.assertEqual(program("minmax_reducer.py", ""), "")

    def test_spark_extremes_merge_order_independent(self):
        pairs = [("z", 7), ("a", 7), ("b", 1), ("c", 1)]
        for permutation in itertools.permutations(pairs):
            acc = None
            for p in permutation:
                acc = extremes_merge(acc, (p, p))
            self.assertEqual(acc, (("b", 1), ("a", 7)))


if __name__ == "__main__":
    unittest.main()
