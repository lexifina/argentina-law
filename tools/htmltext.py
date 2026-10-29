"""InfoLEG HTML -> clean paragraph lines, with links to other norms kept as markers.

Shared by parse.py and the probes. Reads bytes only; no network.
"""
from __future__ import annotations

import html
import re

LINK = "⟦{}⟧"  # ⟦id⟧ appended after a link to verNorma.do?id=N
LINK_RE = re.compile("⟦(\\d+)⟧")

_BLOCK = re.compile(r"<\s*(br|/p|p|/div|div|/tr|tr|/li|li|/h\d|h\d|/table|table|/blockquote|blockquote)\b[^>]*>", re.I)
_A = re.compile(r"<a\b[^>]*href=\"[^\"]*verNorma\.do[^\"]*?[?&]id=(\d+)[^\"]*\"[^>]*>(.*?)</a\s*>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")


def decode(b: bytes) -> str:
    head = b[:4000].decode("latin-1").lower()
    if "charset=utf-8" in head and "charset=iso-8859-1" not in head:
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            pass
    try:
        s = b.decode("cp1252")
    except UnicodeDecodeError:
        s = b.decode("latin-1")
    return s


def norm_chars(s: str) -> str:
    s = s.replace("\xa0", " ").replace("​", "").replace("﻿", "").replace("­", "")
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("«", '"').replace("»", '"').replace("″", '"')
    s = s.replace("—", "-").replace("–", "-").replace("‒", "-").replace("‐", "-").replace("‑", "-")
    s = s.replace("…", "...")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def lines(b: bytes, *, keep_links: bool = True) -> list[str]:
    s = decode(b)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<(script|style|head)\b.*?</\1\s*>", " ", s, flags=re.S | re.I)
    s = re.sub(r"\s+", " ", s)
    if keep_links:
        s = _A.sub(lambda m: m.group(2) + LINK.format(m.group(1)), s)
    s = _BLOCK.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    out = []
    for ln in s.split("\n"):
        ln = norm_chars(ln)
        if ln:
            out.append(ln)
    return out


def strip_links(s: str) -> str:
    return LINK_RE.sub("", s)
