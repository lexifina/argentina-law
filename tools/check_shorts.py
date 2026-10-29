"""Fails (exit 1) if two acts of the merged Argentine record (corpus.json + corpus.d/*.json) share a short name.

    python -X utf8 check_shorts.py

Commit subjects name acts by their short, so each short must be unique (compared case-insensitively). Parts written
by batch8/common_batches.run are checked the same way before they are written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def clashes() -> list[str]:
    seen: dict[str, str] = {}
    out = []
    for f in [ROOT / "corpus.json"] + sorted((ROOT / "corpus.d").glob("*.json")):
        if not f.exists():
            continue
        for a in json.loads(f.read_text(encoding="utf-8")).get("acts", []):
            k = a["short"].casefold()
            here = f"{a['slug']} ({f.name})"
            if k in seen:
                out.append(f"short {a['short']!r}: {seen[k]} and {here}")
            else:
                seen[k] = here
    return out


if __name__ == "__main__":
    bad = clashes()
    for b in bad:
        print(b)
    print(f"{len(bad)} duplicate short names")
    sys.exit(1 if bad else 0)
