"""Build corpus.json for Argentina from the InfoLEG cache only (gitlaw-AR).

    python -X utf8 parse.py            # writes corpus.json
    python -X utf8 parse.py report     # replay report per act (what changed, by whom, mismatches)

Method (InfoLEG keeps no intermediate versions):
  1. the act as enacted: its norma.htm (texto original);
  2. today's text: its texact.htm (texto actualizado), whose per-article notes name the amending
     norm ("Artículo sustituido por art. 3° de la Ley N° 27.363 B.O. 26/6/2017. Vigencia: …") and
     link to it;
  3. replay: every amending norm's own norma.htm is read, its instructions aimed at this act
     ("Sustitúyese el artículo N … por el siguiente: …", "Incorpórase como artículo N …",
     "Derógase el artículo N …") are applied in in-force order to the original;
  4. the replayed final text is compared with texact.htm unit by unit; every mismatch is recorded.
No network access here: everything comes from .cache/ (fetch.py).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import acts as A  # noqa: E402
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402

RETRIEVED = "2026-10-28"
BULK_NORMAS = ("https://datos.jus.gob.ar/dataset/d9a963ea-8b1d-4ca3-9dd9-07a4773e8c23/resource/"
               "bf0ec116-ad4e-4572-a476-e57167a84403/download/base-infoleg-normativa-nacional.zip")
BULK_MODIF = ("https://datos.jus.gob.ar/dataset/d9a963ea-8b1d-4ca3-9dd9-07a4773e8c23/resource/"
              "dea3c247-5a5d-408f-a224-39ae0f8eb371/download/base-complementaria-infoleg-normas-modificatorias.zip")

# ------------------------------------------------------------------ text splitting

SUFFIXES = ["bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "nonies", "decies"]
SUF_RE = "|".join(SUFFIXES) + r"|qu[aá]ter"
ART_RE = re.compile(
    r"^(?:ART[IÍ]CULO|Art[ií]culo|ARTÍCULO|Art\.)\s*(\d+)\s*(?:[°º]|o\b)?\s*\.?\s*(" + SUF_RE + r")?\s*[°º]?"
    r"\s*(?:\.\s*-|\.-|,\s*-|-|:|\.|$)\s*(.*)$", re.I)
ORDINALS = ["primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "septima", "octava", "novena",
            "decima", "undecima", "duodecima", "decimotercera", "decimocuarta", "decimoquinta",
            "decimosexta", "decimoseptima"]
TRANS_RE = re.compile(r"^(" + "|".join(ORDINALS) + r")\s*\.\s*-?\s*(.*)$", re.I)
MARKER_RE = re.compile(
    r"^(LIBRO|PRIMERA PARTE|SEGUNDA PARTE|PARTE\b|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|PAR[AÁ]GRAFO|"
    r"DISPOSICIONES TRANSITORIAS|AUTORIDADES DE LA NACI)", re.I)
NOTE_RE = re.compile(
    r"^\(?\s*(?:(?:Art[ií]culo|Arts?\.|Inciso|Incisos|Inc\.|P[aá]rrafo|[UÚ]ltimo p[aá]rrafo|Primer p[aá]rrafo|"
    r"Segundo p[aá]rrafo|Tercer p[aá]rrafo|Punto|Apartado|Expresi[oó]n|T[eé]rmino|Denominaci[oó]n|Ap\.|"
    r"Texto|Nota|Capítulo|Cap[ií]tulo|Secci[oó]n|T[ií]tulo|Libro|Par[aá]grafo|Rubro|Frase|Palabra|Vocablo|Ep[ií]grafe)"
    r"[^)]*?(?:sustituid|incorporad|derogad|vetad|observad|modificad|suprimid|reemplazad|agregad|abrogad|"
    r"prorrogad|suspendid|declarad|vigencia|Infoleg|B\.O\.)|Nota Infoleg)", re.I)


def fold(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def unit_key(num: int, suf: str | None) -> str:
    k = f"art-{num:04d}" if num >= 1000 or False else f"art-{num:03d}"
    if suf:
        k += "-" + fold(suf)
    return k


def is_note(line: str) -> bool:
    s = H.strip_links(line).strip()
    if not s.startswith("(") and not s.lower().startswith("nota infoleg") and not s.startswith("- Art"):
        # an item whose whole text was replaced by a note: "2. (Punto vetado por …)"
        m = re.match(r"^[a-z0-9]{1,3}[.)]\s*(\(.*\))\s*$", s, re.I)
        return bool(m and NOTE_RE.search(m.group(1)))
    return bool(NOTE_RE.search(s)) or s.lower().startswith("(nota infoleg")


INLINE_NOTE_RE = re.compile(r"\s*(\((?:[^()]|\([^()]*\))*\))\s*$")


def act_lines(nid: int, page: str, start: str, end: str) -> tuple[list[str], str, str]:
    url = F.norma_url(nid, page)
    b = F.cached(url)
    if b is None:
        raise SystemExit(f"not cached: {url} (run fetch.py acts)")
    L = H.lines(b)
    i = next(i for i, l in enumerate(L) if re.search(start, H.strip_links(l)))
    j = next((j for j in range(i + 1, len(L)) if re.search(end, H.strip_links(L[j]))), len(L))
    return L[i:j], url, hashlib.sha256(b).hexdigest()


def split_units(lines: list[str], *, width: int = 3, transitorias: bool = False) -> dict[str, dict]:
    """Ordered units: key -> {label, kind, body: [lines], notes: [lines]}."""
    units: dict[str, dict] = {}
    cur = None
    after_marker = False
    in_trans = False
    for raw in lines:
        s = H.strip_links(raw)
        if re.match(r"^PRE[AÁ]MBULO$", s, re.I):
            cur = units.setdefault("preambulo", {"label": "Preámbulo", "kind": "preamble", "body": [], "notes": []})
            after_marker = False
            continue
        if MARKER_RE.match(s) and len(s) < 90 and not s.endswith("."):
            if re.match(r"^DISPOSICIONES TRANSITORIAS", s, re.I):
                in_trans = True
            after_marker = True
            continue
        m = ART_RE.match(s)
        if m and not in_trans:
            num, suf, rest = int(m.group(1)), m.group(2), m.group(3).strip()
            key = (f"art-{num:0{width}d}") + (f"-{fold(suf)}" if suf else "")
            label = f"Art. {num}" + (f" {fold(suf)}" if suf else "")
            if key in units:  # a repeated heading: keep the first, treat the rest as body
                cur["body"].append(s)
                continue
            cur = units[key] = {"label": label, "kind": "art", "body": [], "notes": []}
            if rest:
                if is_note(rest):
                    cur["notes"].append(raw)
                else:
                    cur["body"].append(rest)
            after_marker = False
            continue
        if transitorias and in_trans:
            t = TRANS_RE.match(fold(s))
            if t:
                n = ORDINALS.index(t.group(1).lower()) + 1
                key = f"disp-transitoria-{n:02d}"
                cur = units[key] = {"label": f"Disposición transitoria {s.split('.')[0].strip().lower()}",
                                    "kind": "transitional", "body": [], "notes": []}
                rest = s[len(s.split('.')[0]) + 1:].strip().lstrip("-").strip()
                if rest:
                    cur["body"].append(rest)
                after_marker = False
                continue
        if after_marker and not re.search(r"[.;:,]$", s) and len(s) < 120:
            after_marker = False  # the heading's title line
            continue
        after_marker = False
        if cur is None:
            continue
        if is_note(raw):
            cur["notes"].append(raw)
            continue
        m = INLINE_NOTE_RE.search(raw)
        if m and NOTE_RE.search(m.group(1)):
            cur["notes"].append(m.group(1))
            s = H.strip_links(raw[:m.start()]).strip()
        cur["body"].append(s)
    return units


def render(key: str, u: dict) -> str:
    head = f"# {u['label']}"
    body = [b for b in u["body"] if b]
    return "\n".join([head] + body) + "\n"


def norm_cmp(t: str) -> str:
    """Comparison form: typography and case folded (publisher noise is not a change)."""
    t = fold(t)
    t = t.replace('"', "").replace("'", "").replace("`", "")
    t = re.sub(r"[°º]", "o", t)
    t = re.sub(r"\s*([.,;:()\-])\s*", r"\1", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


# ------------------------------------------------------------------ the bulk index (types, numbers, dates)

_bulk: dict[int, dict] | None = None


def bulk() -> dict[int, dict]:
    global _bulk
    if _bulk is None:
        _bulk = {}
        b = F.cached(BULK_NORMAS)
        if b:
            z = zipfile.ZipFile(io.BytesIO(b))
            with z.open(z.namelist()[0]) as f:
                for row in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")):
                    _bulk[int(row["id_norma"])] = {k: row[k] for k in (
                        "tipo_norma", "numero_norma", "clase_norma", "organismo_origen", "fecha_sancion",
                        "fecha_boletin", "titulo_resumido", "titulo_sumario", "texto_original", "texto_actualizado")}
    return _bulk


def modifiers(nid: int) -> list[dict]:
    """Norms InfoLEG lists as modifying or complementing `nid` (from its verVinculos page)."""
    b = F.cached(F.vinculos_url(nid, 2))
    if not b:
        return []
    s = H.decode(b)
    out = []
    for m in re.finditer(r"verNorma\.do[^\"]*?[?&]id=(\d+)\">(.*?)</a>(.*?)</tr>", s, re.S):
        cells = re.sub(r"<[^>]+>", "|", m.group(3))
        txt = re.sub(r"\s+", " ", H.html.unescape(cells)) if hasattr(H, "html") else cells
        out.append({"id": int(m.group(1)), "name": re.sub(r"\s+", " ", re.sub(r"<[^>]+>|&nbsp;", " ", m.group(2))).strip(),
                    "row": re.sub(r"[|\s]+", " ", txt).strip()})
    return out


# ------------------------------------------------------------------ notes in texact

NOTE_PARSE = re.compile(
    r"(?P<what>[^()]*?)\s+(?P<verb>sustituid[oa]s?|incorporad[oa]s?|derogad[oa]s?|vetad[oa]s?|observad[oa]s?|"
    r"modificad[oa]s?|suprimid[oa]s?|abrogad[oa]s?|reemplazad[oa]s?|agregad[oa]s?)\s+por\s+"
    r"(?P<art>(?:el\s+)?(?:arts?\.|art[ií]culos?)\s*[^⟦]*?)?\s*(?:de la|del)?\s*"
    r"(?P<type>Ley|Decreto(?:\s+de\s+Necesidad\s+y\s+Urgencia)?|Decreto-Ley|DNU|Resoluci[oó]n|Acordada|Fallo)\s*"
    r"(?:N[°º]\s*)?(?P<num>[\d.]+(?:/\d+)?)\s*(?:⟦(?P<id>\d+)⟧)?\s*(?:B\.\s*O\.\s*(?P<bo>\d{1,2}/\d{1,2}/\d{2,4}))?"
    r"(?P<tail>[^()]*)", re.I)


def parse_note(raw: str) -> list[dict]:
    out = []
    for m in NOTE_PARSE.finditer(raw):
        bo = None
        if m.group("bo"):
            d, mo, y = (int(x) for x in m.group("bo").split("/"))
            y = y + 1900 if y < 100 and y > 30 else (y + 2000 if y < 100 else y)
            bo = dt.date(y, mo, d).isoformat()
        tail = m.group("tail") or ""
        vig = re.search(r"Vigencia:\s*(.*)", tail, re.I)
        out.append({"what": H.strip_links(m.group("what")).strip(" (.-"), "verb": m.group("verb").lower(),
                    "art": (m.group("art") or "").strip(), "type": m.group("type"), "num": m.group("num"),
                    "id": int(m.group("id")) if m.group("id") else None, "bo": bo,
                    "vigencia": vig.group(1).strip() if vig else None})
    return out


if __name__ == "__main__":
    import build_corpus  # noqa: F401  (the corpus assembly lives in build_corpus.main)
    build_corpus.main(sys.argv[1:])
