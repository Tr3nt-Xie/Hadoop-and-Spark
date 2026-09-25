#!/usr/bin/env python3
"""Download three books from a listed Gutenberg mirror; create reproducible input.

The benchmark corpus repeats complete books, explicitly recorded in manifest.json.
This enlarges the input without presenting duplicates as additional unique books.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen

BOOKS = [
    (1342, "Pride and Prejudice", "https://gutenberg.pglaf.org/1/3/4/1342/1342-0.txt"),
    (1661, "The Adventures of Sherlock Holmes", "https://gutenberg.pglaf.org/1/6/6/1661/1661-0.txt"),
    (2701, "Moby Dick", "https://gutenberg.pglaf.org/2/7/0/2701/2701-0.txt"),
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, default=Path("data"))
    p.add_argument("--minimum-mib", type=int, default=32)
    a = p.parse_args()
    if a.minimum_mib < 1:
        p.error("--minimum-mib must be positive")
    if a.output.exists():
        raise SystemExit("Output exists; choose a new directory to preserve its manifest")
    original = a.output / "original"
    corpus = a.output / "corpus"
    original.mkdir(parents=True)
    corpus.mkdir()
    texts, sources = [], []
    for book_id, title, url in BOOKS:
        with urlopen(url, timeout=60) as response:
            raw = response.read()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
        if "PROJECT GUTENBERG" not in text.upper() or len(raw) < 10000:
            raise SystemExit("Unexpected book response: " + url)
        if not text.endswith("\n"):
            text += "\n"
        (original / f"pg{book_id}.txt").write_bytes(raw)
        texts.append(text)
        sources.append({"id": book_id, "title": title, "url": url,
                        "download_sha256": hashlib.sha256(raw).hexdigest(), "download_bytes": len(raw)})
        time.sleep(2)
    original_bytes = sum(len(t.encode("utf-8")) for t in texts)
    repeats = (a.minimum_mib * 1048576 + original_bytes - 1) // original_bytes
    files = []
    for copy in range(repeats):
        for (book_id, _, _), text in zip(BOOKS, texts):
            name = f"pg{book_id}-copy{copy:03d}.txt"
            raw = text.encode("utf-8")
            (corpus / name).write_bytes(raw)
            files.append({"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    words, chars = Counter(), Counter()
    for text in texts:
        for line in text.split("\n"):
            words.update(line.split())
            chars.update(f"U+{ord(c):04X}" for c in line)
    words = {k: v * repeats for k, v in words.items()}
    chars = {k: v * repeats for k, v in chars.items()}
    low = min(words, key=lambda k: (words[k], k))
    high = min(words, key=lambda k: (-words[k], k))
    expected = {"wordcount": words, "charcount": chars,
                "minmax": {"MIN": [low, words[low]], "MAX": [high, words[high]]}}
    (a.output / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    manifest = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "unique_books": 3, "copies_per_book": repeats,
                "total_bytes": sum(f["bytes"] for f in files), "sources": sources, "files": files,
                "normalization": "UTF-8, remove BOM, CRLF/CR to LF, append final LF; retain Gutenberg headers/licenses",
                "word_rule": "case-sensitive str.split(), punctuation retained",
                "char_rule": "Unicode code points including spaces/tabs, excluding LF record delimiters"}
    (a.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"bytes": manifest["total_bytes"], "files": len(files), "copies_per_book": repeats}))


if __name__ == "__main__":
    main()
