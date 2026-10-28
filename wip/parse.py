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
ORDINAL_LABELS = ["primera", "segunda", "tercera", "cuarta", "quinta", "sexta", "séptima", "octava", "novena",
                  "décima", "undécima", "duodécima", "decimotercera", "decimocuarta", "decimoquinta",
                  "decimosexta", "decimoséptima"]
TRANS_RE = re.compile(r"^(" + "|".join(o[:-1] + "[ao]" for o in ORDINALS) + r")\s*\.\s*-?\s*(.*)$", re.I)  # "Undécimo." is masculine in the source
MARKER_RE = re.compile(
    r"^(LIBRO|PRIMERA PARTE|SEGUNDA PARTE|PARTE\b|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|PAR[AÁ]GRAFO|"
    r"DISPOSICIONES TRANSITORIAS|DISPOSICIONES COMPLEMENTARIAS|AUTORIDADES DE LA NACI)", re.I)
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
                    while True:  # trailing notes on the heading line: "… (Artículo 306 renumerado …). (…)"
                        mm = INLINE_NOTE_RE.search(rest.rstrip(". "))
                        if not (mm and NOTE_RE.search(mm.group(1))):
                            break
                        cur["notes"].append(mm.group(1))
                        rest = rest.rstrip(". ")[:mm.start()].rstrip()
                        rest = rest if rest.endswith(".") else rest + "."
                    cur["body"].append(rest)
            after_marker = False
            continue
        if transitorias and in_trans:
            t = TRANS_RE.match(fold(s))
            if t:
                n = [o[:-1] for o in ORDINALS].index(t.group(1).lower()[:-1]) + 1
                key = f"disp-transitoria-{n:02d}"
                cur = units[key] = {"label": f"Disposición transitoria {ORDINAL_LABELS[n - 1]}",
                                    "kind": "transitional", "body": [], "notes": []}
                rest = s[len(s.split('.')[0]) + 1:].strip().lstrip("-").strip()
                if rest:
                    cur["body"].append(rest)
                after_marker = False
                continue
        if re.match(r"^DADA EN LA SALA", s):  # the closing formula of the constituent convention
            cur = units["cierre"] = {"label": "Cierre", "kind": "closing", "body": [s], "notes": []}
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




# ------------------------------------------------------------------ dates

INFOLEG = "https://servicios.infoleg.gob.ar/infolegInternet"
CCYC_TEXACT = F.norma_url(235975, "texact.htm")
LEY340_ART2 = f"{INFOLEG}/anexos/105000-109999/109481/texactley340_preliminar_tituloI.htm"


def plus(day: str, n: int) -> str:
    return (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()


# In-force rule of each amending norm, read by hand from the norm's own text (its vigencia article) and from the
# "Vigencia:" in InfoLEG's note on the amended article. "pub" = the day of publication in the Boletín Oficial,
# "pub+1" = the day after, "default" = no vigencia clause: the day after the eighth day following publication
# (Código Civil art. 2; from 2015-08-01 CCyC arts. 5 and 6), i.e. publication + 9 days.
IN_FORCE = {
    136483: ("default", "Ley 26.343 has no vigencia clause"),
    265453: ("pub", "Ley 27.271, art. 25: rige desde su publicación en el Boletín Oficial"),
    276135: ("default", "Ley 27.363 has no vigencia clause (its art. 3 is about application to pending situations)"),
    310084: ("default", "Ley 27.440 has no vigencia clause for its Title on the Code"),
    319068: ("pub", "Decreto 62/2019, art. 6: a partir de la fecha de su publicación"),
    339378: ("pub+1", "Ley 27.551, art. 23: a partir del día siguiente al de su publicación"),
    345233: ("default", "Ley 27.586 has no vigencia clause"),
    345235: ("default", "Ley 27.587 has no vigencia clause"),
    391456: ("pub+1", "Ley 27.737, art. 12: a partir del día siguiente al de su publicación"),
    395521: ("default", "Decreto 70/2023 (DNU) has no vigencia clause"),
    406267: ("pub", "Decreto 1017/2024, art. 22: a partir del día de su publicación"),
    412944: ("pub", "Decreto 338/2025, art. 12: a partir del día de su publicación"),
    422008: ("pub", "Ley 27.799, art. 45: a partir del día de su publicación"),
}


def in_force(nid: int) -> str:
    pub = bulk()[nid]["fecha_boletin"]
    rule = rule_of(nid)[0]
    m = re.fullmatch(r"pub\+(\d+)", rule)
    if m:
        return plus(pub, int(m.group(1)))
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", rule):
        return rule
    return {"pub": pub, "default": plus(pub, 9)}[rule]


NUMBER_WORDS = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
                "nueve": 9, "diez": 10, "quince": 15, "veinte": 20, "treinta": 30, "sesenta": 60, "noventa": 90,
                "ciento ochenta": 180}
VIG_RE = re.compile(r"(presente\s+(?:ley|decreto)|esta\s+ley|la\s+ley)\b.{0,60}?\b(vigencia|vigor|regir[aá]|rige)", re.I)


def auto_rule(nid: int) -> tuple[str, str]:
    """The norm's own vigencia clause, read from the first line of each of its articles (never from quoted text).

    Returns (rule, citation): "pub", "pub+N" or "default" (no clause found). Anything else is "unknown"."""
    r = bulk()[nid]
    label = law_entry(nid)["label"]
    for num, lines in amender_articles(nid):
        t = lines[0]
        if not VIG_RE.search(t):
            continue
        f = fold(t)
        if re.search(r"dia siguiente", f):
            return "pub+1", f"{label}, art. {num}: a partir del día siguiente al de su publicación"
        m = re.search(r"a los\s+([a-z ]+?)\s*(?:\(\d+\)\s*)?dias?\s+(?:corridos\s+)?(?:de|desde|contados)", f)
        if m and m.group(1).strip() in NUMBER_WORDS:
            n = NUMBER_WORDS[m.group(1).strip()]
            return f"pub+{n}", f"{label}, art. {num}: a los {m.group(1).strip()} días de su publicación"
        if re.search(r"(desde|a partir de)\s+(el dia de\s+|la fecha de\s+|el momento de\s+)?su publicacion", f) or \
                re.search(r"dia de su publicacion", f):
            return "pub", f"{label}, art. {num}: desde su publicación"
        return "unknown", f"{label}, art. {num}: {t[:200]}"
    return "default", f"{label} has no vigencia clause"


def rule_of(nid: int) -> tuple[str, str]:
    return IN_FORCE.get(nid) or auto_rule(nid)


# ------------------------------------------------------------------ laws

def law_key(nid: int) -> str:
    r = bulk()[nid]
    if r["tipo_norma"] == "Ley":
        return f"ley-{r['numero_norma']}"
    year = (r["fecha_sancion"] or r["fecha_boletin"])[:4]
    return f"{fold(r['tipo_norma']).replace(' ', '-')}-{r['numero_norma']}-{year}"


def thousands(n: str) -> str:
    return f"{int(n):,}".replace(",", ".") if n.isdigit() else n


def law_entry(nid: int) -> dict:
    r = bulk()[nid]
    if r["tipo_norma"] == "Ley":
        label = f"Ley {thousands(r['numero_norma'])}"
    else:
        year = (r["fecha_sancion"] or r["fecha_boletin"])[:4]
        # a decree of necessity and urgency is cited "DNU 70/2023"
        label = f"{'DNU' if r['clase_norma'] == 'DNU' else r['tipo_norma']} {r['numero_norma']}/{year}"
    title = r["titulo_sumario"].strip()
    if r["titulo_resumido"].strip():
        title += ": " + r["titulo_resumido"].strip()
    return {"label": label, "title": title,
            "kind": "law" if r["tipo_norma"] == "Ley" else "decree",
            "enacted": r["fecha_sancion"] or None, "published": r["fecha_boletin"] or None,
            "url": F.norma_url(nid), "temporary_until": None, "restores": None, "note": None}


# ------------------------------------------------------------------ the amending norms

SUF_WORDS = r"(?:\s+(bis|ter|qu[aá]ter|quinquies))?"
NUM_IN = r"(\d{1,2}\.\d{3}|\d+)"


def dethousand(s: str) -> str:
    """"Artículo 1.204 bis" -> "Artículo 1204 bis" (the thousands dot of article numbers)."""
    return re.sub(r"\b(\d{1,2})\.(\d{3})\b", r"\1\2", s)


def dehead(s: str) -> str:
    """Drop only the thousands dot of a leading article number ("Artículo 1.196: …"), keeping the rest as written."""
    m = re.match(r"^\"?((?:ART[IÍ]CULO|Art[ií]culo|Art\.)\s*\d{1,2})\.(\d{3})", s)
    return s[:m.end(1)] + s[m.end(1) + 1:] if m else s


def amender_articles(nid: int) -> list[tuple[int, list[str]]]:
    """The amending norm's own articles, in order: (number, [first line after the heading, following lines…]).

    An article starts at a heading whose number is the next one expected (1, 2, 3 …); headings inside the quoted or
    unquoted new text ("Artículo 700 bis: …") have other numbers and stay in the body."""
    b = F.cached(F.norma_url(nid))
    if b is None:
        raise SystemExit(f"not cached: amender {nid} (run fetch.py amenders)")
    out, expect, cur = [], 1, None
    for raw in H.lines(b):
        s = H.strip_links(raw)
        m = ART_RE.match(dehead(s)) if not s.startswith('"') else None
        if m and int(m.group(1)) == expect and not m.group(2):
            cur = [m.group(3).strip()]
            out.append((expect, cur))
            expect += 1
            continue
        if cur is not None:
            cur.append(s)
    return out


def new_text(body: list[str]) -> list[str]:
    """The new wording given after an instruction: quotes, the article heading and trailing headings removed."""
    out, quoted = [], bool(body) and body[0].startswith('"')
    for i, s in enumerate(body):
        if MARKER_RE.match(s) and not s.startswith('"') and (not quoted or i == 0 or not out):
            break
        if re.match(r"^(DADA EN LA SALA|Comun[ií]quese|- REGISTRAD)", s, re.I):
            break
        if is_note(s):
            continue
        s = s.strip()
        end = quoted and bool(re.search(r'"[.;]?$', s))
        if i == 0 and s.startswith('"'):
            s = s[1:]
        if end:
            s = re.sub(r'\s*"([.;]?)$', r"\1", s)
        out.append(s)
        if end:
            break
    if out:
        m = ART_RE.match(dehead(out[0]))
        if m:
            rest = m.group(3).strip()
            out = ([rest] if rest else []) + out[1:]
    return [s for s in out if s]


def unit_key_w(num: int, suf: str | None, width: int) -> str:
    return f"art-{num:0{width}d}" + (f"-{fold(suf)}" if suf else "")


def keys_in(s: str, width: int) -> list[str]:
    s = dethousand(s)
    return [unit_key_w(int(n), suf, width) for n, suf in re.findall(r"(\d+)" + SUF_WORDS, s)]


def instruction(text: str, body: list[str], target: str, width: int) -> dict | None:
    """What one article of an amending norm does to the act, or None if it does not address it."""
    t = dethousand(text)
    if not re.search(target, t, re.I):
        return None
    head = re.split(r"\s+del?\s+(?:la\s+)?(?:" + target + ")", t, maxsplit=1, flags=re.I)[0]
    if not re.search(r"(Sustit[uú]y|Reempl[aá]c|Modif[ií]c|Modif[ií]qu|Der[oó]g|Incorp[oó]r|Agr[eé]gu?|Supr[ií]m)[ae]n?se\b", head, re.I):
        return None  # the article only mentions the act
    m = re.search(r"Der[oó]g[ae]se\s+el\s+[uú]ltimo\s+p[aá]rrafo\s+del\s+art[ií]culo\s+(\d+)" + SUF_WORDS, head, re.I)
    if m:
        return {"op": "drop_last_paragraph", "keys": [unit_key_w(int(m.group(1)), m.group(2), width)]}
    m = re.search(r"Incorp[oó]r[ae]se\s+como\s+inciso\s+([a-z])\)\s+del\s+art[ií]culo\s+(\d+)" + SUF_WORDS, head, re.I)
    if m:
        return {"op": "add_item", "keys": [unit_key_w(int(m.group(2)), m.group(3), width)], "text": new_text(body)}
    if re.search(r"p[aá]rrafo|inciso|apartado|ep[ií]grafe|punto", head, re.I):
        return {"op": "unknown", "keys": keys_in(head, width), "instruction": text}
    m = re.search(r"Der[oó]g[ae]n?se\s+(?:el|los)\s+art[ií]culos?\s+(.*)$", head, re.I)
    if m:
        return {"op": "repeal", "keys": keys_in(m.group(1), width)}
    if re.search(r"Incorp[oó]r[ae]se|Agr[eé]gu?[ae]se", head, re.I):
        m = re.search(r"art[ií]culo\s+(\d+)" + SUF_WORDS, head, re.I)
        if m:
            return {"op": "insert", "keys": [unit_key_w(int(m.group(1)), m.group(2), width)], "text": new_text(body)}
    m = re.search(r"(?:Sustit[uú]y[ae]se|Reempl[aá]c[ae]se|Modif[ií]c[ae]se|Modif[ií]qu[ae]se)\s+(?:el\s+)?(?:texto\s+del\s+)?"
                  r"art[ií]culo\s+(\d+)" + SUF_WORDS, head, re.I)
    if m:
        return {"op": "replace", "keys": [unit_key_w(int(m.group(1)), m.group(2), width)], "text": new_text(body)}
    return {"op": "unknown", "keys": keys_in(head, width), "instruction": text}


def amendments(act: dict, ids: list[int]) -> list[dict]:
    """Every instruction aimed at `act` in the norms `ids`, with the law's key and in-force day, in force order."""
    out = []
    for nid in ids:
        for num, lines in amender_articles(nid):
            op = instruction(lines[0], lines[1:], act["target"], act.get("width", 3))
            if op:
                op.update({"nid": nid, "law": law_key(nid), "from": in_force(nid), "art": num})
                out.append(op)
    out.sort(key=lambda o: (o["from"], bulk()[o["nid"]]["fecha_boletin"], o["nid"], o["art"]))
    return out


# ------------------------------------------------------------------ comparison

def loose(lines: list[str]) -> str:
    """Words only: what is left when punctuation, case, accents and spacing are ignored."""
    return " ".join(re.findall(r"[a-z0-9]+", fold(" ".join(lines))))


def body_of(u: dict | None) -> list[str]:
    return [b for b in (u or {}).get("body", []) if b]


# ------------------------------------------------------------------ the replay

def replay(act: dict) -> dict:
    """Replay the amending norms on the act as enacted. Returns versions, the laws used and a report."""
    width = act.get("width", 3)
    L, url0, sha0 = act_lines(act.get("base_id", act["id"]), "norma.htm", act["start"], act["end"])
    state = {k: {"label": u["label"], "kind": u["kind"], "body": body_of(u)}
             for k, u in split_units(L, width=width, transitorias=act.get("transitorias", False)).items()}
    report = {"act": act["slug"], "ops": [], "mismatches": [], "typography": [], "transcription": []}
    for key, drop in act.get("vetoed", {}).items():
        if drop is None:
            state.pop(key, None)
        else:
            state[key]["body"] = [b for b in state[key]["body"] if not re.match(drop, b)]
    versions = [{"from": act["first_day"], "source_url": url0, "sha256": sha0, "state": {k: dict(v) for k, v in state.items()},
                 "credits": {}, "laws": [act["first_law"]]}]
    ops = amendments(act, act.get("amenders", [])) if act.get("texact") else []
    report["nids"] = sorted({o["nid"] for o in ops})
    for day in sorted({o["from"] for o in ops}):
        day_ops = [o for o in ops if o["from"] == day]
        credits: dict[str, list[str]] = {}
        for o in day_ops:
            for k in o["keys"]:
                before = state.get(k)
                if o["op"] in ("replace", "insert"):
                    num = int(re.search(r"\d+", k).group(0))
                    suf = k.split("-")[2] if k.count("-") == 2 else None
                    state[k] = {"label": f"Art. {num}" + (f" {suf}" if suf else ""), "kind": "art", "body": list(o["text"])}
                elif o["op"] == "repeal":
                    state.pop(k, None)
                elif o["op"] == "drop_last_paragraph" and before:
                    state[k] = dict(before, body=before["body"][:-1])
                elif o["op"] == "add_item" and before:
                    state[k] = dict(before, body=before["body"] + list(o["text"]))
                else:
                    report["mismatches"].append(f"{k}: {o['law']} art. {o['art']}: instruction not understood: {o.get('instruction', '')[:160]}")
                    continue
                if state.get(k) != before:
                    credits.setdefault(k, [])
                    if o["law"] not in credits[k]:
                        credits[k].append(o["law"])
                report["ops"].append(f"{day} {o['law']} art. {o['art']}: {o['op']} {k}")
        nids = sorted({o["nid"] for o in day_ops}, key=lambda n: (bulk()[n]["fecha_boletin"], n))
        b = F.cached(F.norma_url(nids[0]))
        versions.append({"from": day, "source_url": F.norma_url(nids[0]), "sha256": hashlib.sha256(b).hexdigest(),
                         "state": {k: dict(v) for k, v in state.items()}, "credits": credits,
                         "laws": [law_key(n) for n in nids]})
    # today's official text: InfoLEG's texto actualizado
    if act.get("texact"):
        T, turl, tsha = act_lines(act["id"], "texact.htm", act["start"], act["end"])
        tex = {k: u for k, u in split_units(T, width=width, transitorias=act.get("transitorias", False)).items() if body_of(u)}
        report["texact"] = {"url": turl, "sha256": tsha}
        final = versions[-1]["state"]
        for k in sorted(set(final) | set(tex)):
            a, t = body_of(final.get(k)), body_of(tex.get(k))
            if a == t:
                continue
            if not a or not t:
                report["mismatches"].append(f"{k}: {'only in texact' if t else 'only in the replay'}")
                continue
            if loose(a) != loose(t):
                if k in act.get("transcription", {}):
                    report["transcription"].append(k)
                else:
                    report["mismatches"].append(f"{k}: words differ from texact")
                    continue
            else:
                report["typography"].append(k)
            # same words (or a known InfoLEG transcription error in norma.htm): take texact's wording from the
            # version in which the unit last changed onwards, so today's file is the official consolidated text
            last = max(i for i, v in enumerate(versions) if i == 0 or k in v["credits"])
            for v in versions[last:]:
                v["state"][k] = dict(v["state"][k], body=list(t))
    return {"versions": versions, "report": report}


def unit_out(u: dict) -> dict:
    return {"label": u["label"], "kind": u["kind"], "text": "\n".join([f"# {u['label']}"] + u["body"]) + "\n"}


# ------------------------------------------------------------------ the corpus

COUNTRY = {
    "code": "AR", "name": "Argentina", "slug": "argentina", "lang": "es",
    "tz": "America/Argentina/Buenos_Aires", "future_branch": "futuro",
    "publisher": {"name": "InfoLEG (Ministerio de Justicia de la Nación)", "email": "infoleg@infoleg.invalid"},
    "default_in_force_rule": {
        "text": ("Código Civil y Comercial art. 5: \"Las leyes rigen después del octavo día de su publicación oficial, "
                 "o desde el día que ellas determinen\", counted under art. 6 (the day of publication is excluded), so a "
                 "norm without its own vigencia clause is in force from the ninth day after its publication in the "
                 "Boletín Oficial. Before 1 August 2015 the same rule was Código Civil (Ley 340) art. 2, as replaced by "
                 "Ley 16.504: \"serán obligatorias después de los ocho días siguientes al de su publicación oficial\". "
                 "A norm's own vigencia clause overrides the rule."),
        "source": CCYC_TEXACT},
    "licence_note": ("Fuente: InfoLEG - Información Legislativa, Ministerio de Justicia de la Nación "
                     "(https://www.infoleg.gob.ar). Base de datos InfoLEG en datos.jus.gob.ar, licencia Creative Commons "
                     "Attribution 4.0."),
}

CONSTITUTION_LAWS = {
    "constitucion-1853": {"label": "Constitución de 1853", "title": "Constitución de la Confederación Argentina, sancionada en 1853"},
    "reforma-1860": {"label": "Reforma constitucional de 1860", "title": "Reforma de la Constitución de 1860"},
    "reforma-1866": {"label": "Reforma constitucional de 1866", "title": "Reforma de la Constitución de 1866"},
    "reforma-1898": {"label": "Reforma constitucional de 1898", "title": "Reforma de la Constitución de 1898"},
    "reforma-1957": {"label": "Reforma constitucional de 1957", "title": "Reforma de la Constitución de 1957"},
    "reforma-1994": {"label": "Reforma constitucional de 1994",
                     "title": ("Texto ordenado de la Constitución Nacional sancionado por la Convención Nacional "
                               "Constituyente (Santa Fe, 22 de agosto de 1994)"),
                     "enacted": "1994-08-22", "published": "1994-08-23", "url": F.norma_url(804)},
}

ACT_SETUP = {
    # first_day: in force of the text as enacted; first_law: the law that enacted it
    "constitucion": {"first_day": "1994-08-24", "first_law": "reforma-1994", "transitorias": True,
                     "earlier_laws": ["constitucion-1853", "reforma-1860", "reforma-1866", "reforma-1898", "reforma-1957"],
                     "note": ("The text in force since the 1994 reform (Disposición transitoria decimosexta: \"Esta reforma "
                              "entra en vigencia al día siguiente de su publicación\"; the oath was taken on 24 August "
                              "1994). InfoLEG publishes it as the official text ordered by Ley 24.430 (B.O. 1995-01-10), "
                              "\"sancionada en 1853 con las reformas de los años 1860, 1866, 1898, 1957 y 1994\"; Ley "
                              "24.430 art. 2 confirms that the text includes the second paragraph of art. 77. The text "
                              "of the Constitution has not changed since. Earlier texts (1853-1957) are not on InfoLEG "
                              "and are not shown.")},
    "ley-25326": {"first_day": None, "first_law": "ley-25326", "amenders": [136483],
                  "vetoed": {"art-029": r"^[23]\. ", "art-047": None},
                  "note": ("Ley 25.326 as promulgated by Decreto 995/2000 (B.O. 2000-11-02), which vetoed "
                           "(\"observó\") art. 29 points 2 and 3 and art. 47 of the bill: that text never took effect "
                           "and is not shown. No vigencia clause: in force from the ninth day after publication "
                           "(Código Civil art. 2).")},
    "codigo-civil-y-comercial": {
        "first_day": "2015-08-01", "first_law": "ley-26994", "width": 4,
        "amenders": [265453, 276135, 310084, 319068, 339378, 345233, 345235, 391456, 395521, 406267, 412944, 422008],
        "transcription": {"art-2277": "\"testa-mento\" in norma.htm", "art-2446": "\"Iegitimarios\" in norma.htm"},
        "note": ("The Code approved by Ley 26.994 (B.O. 2014-10-08) as enacted. Ley 26.994 art. 7 set its entry into "
                 "force on 1 January 2016; Ley 27.077 (B.O. 2014-12-19) brought it forward to 1 August 2015.")},
}


def requests_by_host() -> dict[str, int]:
    out: dict[str, int] = {}
    p = F.CACHE / "requests.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                host = re.sub(r"^https?://([^/]+).*$", r"\1", json.loads(line)["url"])
                out[host] = out.get(host, 0) + 1
    return out


def act_order() -> list[dict]:
    return [dict(a, **ACT_SETUP[a["slug"]]) for a in A.ACTS if a["slug"] in ACT_SETUP]


def build_corpus(only: set[str] | None = None) -> tuple[dict, list[dict]]:
    laws: dict[str, dict] = {}
    for k, v in CONSTITUTION_LAWS.items():
        laws[k] = {"label": v["label"], "title": v["title"], "kind": "law", "enacted": v.get("enacted"),
                   "published": v.get("published"), "url": v.get("url"), "temporary_until": None, "restores": None,
                   "note": None}
    acts_out, reports, amenders_used = [], [], set()
    for act in act_order():
        if only and act["slug"] not in only:
            continue
        if act["first_day"] is None:
            act["first_day"] = plus(bulk()[act["id"]]["fecha_boletin"], 9)
        if act["first_law"] not in laws:
            laws[act["first_law"]] = law_entry(act["id"])
        for nid in act.get("amenders", []):
            laws[law_key(nid)] = law_entry(nid)
        r = replay(act)
        reports.append(r["report"])
        amenders_used |= set(r["report"]["nids"])
        versions = []
        for i, v in enumerate(r["versions"]):
            out = {"from": v["from"], "source_url": v["source_url"], "sha256": v["sha256"],
                   "units": {k: unit_out(u) for k, u in sorted(v["state"].items())}, "credits": {}}
            if i == 0:
                out["note"] = act["note"]
            else:
                prev = r["versions"][i - 1]["state"]
                for k in sorted(set(prev) | set(v["state"])):
                    if prev.get(k) != v["state"].get(k):
                        out["credits"][k] = v["credits"].get(k, [])
                        if not out["credits"][k]:
                            del out["credits"][k]  # unexplained: committed by the publisher
                if len(v["laws"]) > 1:
                    out["note"] = "Source of this version: " + ", ".join(laws[l]["label"] for l in v["laws"]) + "."
            versions.append(out)
        acts_out.append({"slug": act["slug"], "short": act["short"], "title": act["title"],
                         "url": F.norma_url(act["id"], "texact.htm" if act.get("texact") else "norma.htm"),
                         "first_law": act["first_law"], "earlier_laws": act.get("earlier_laws", []),
                         "versions": versions})
    used = {act["first_law"] for act in acts_out} | {l for act in acts_out for l in act["earlier_laws"]} | \
        {l for act in acts_out for v in act["versions"] for ls in v["credits"].values() for l in ls}
    laws = {k: laws[k] for k in sorted(laws) if k in used}
    hosts = requests_by_host()
    sources = [
        {"name": "InfoLEG - Información Legislativa (Ministerio de Justicia de la Nación)",
         "url": "https://servicios.infoleg.gob.ar/infolegInternet/", "retrieved": RETRIEVED,
         "requests": hosts.get("servicios.infoleg.gob.ar", 0),
         "licence": "Official text, published by the Ministerio de Justicia y Derechos Humanos de la Nación; footer \"Copyright 2005\"; no robots.txt. Attribution: Fuente: InfoLEG.",
         "notes": ("norma.htm (texto original) of each act and of every norm that amends it, texact.htm (texto "
                   "actualizado, today's consolidated text with a note naming the amending norm on each changed "
                   "article), verNorma.do (record) and verVinculos.do (norms that modify or complement it). InfoLEG "
                   "keeps no intermediate versions: they are rebuilt by replaying the amending norms' own texts.")},
        {"name": "Base de datos InfoLEG de normativa nacional (datos.jus.gob.ar)",
         "url": "https://datos.jus.gob.ar/dataset/base-de-datos-legislativos-infoleg", "retrieved": RETRIEVED,
         "requests": hosts.get("datos.jus.gob.ar", 0), "licence": "Creative Commons Attribution 4.0; Fuente https://www.infoleg.gob.ar",
         "notes": "CSV of every national norm (data updated to 2026-09-30): type, number, class (DNU), dates of sanción and Boletín Oficial, titles."},
    ]
    decisions = [
        "Source: InfoLEG only. It keeps the original text (norma.htm) and today's text (texact.htm) of each norm, but no intermediate versions, so every version after the first is rebuilt by applying, in order of entry into force, the instructions of each amending norm as written in that norm's own text on InfoLEG (\"Sustitúyese el artículo N …\", \"Incorpórase …\", \"Derógase …\"). The amending norms are those InfoLEG's notes on texact.htm name for each act.",
        "The replayed text of today is checked against texact.htm article by article; the result for each act is in its README table and in these decisions. Where the words are the same and only typography differs (quotes, case, accents, punctuation, the thousands dot), the texact.htm wording is used from the version in which the article last changed.",
        "In-force dates: a norm's own vigencia clause where it has one; otherwise the default rule (publication in the Boletín Oficial + 9 days: Código Civil art. 2 before 2015-08-01, Código Civil y Comercial arts. 5 and 6 after). Per norm: " + "; ".join(f"{rule_of(n)[1]} -> {in_force(n)}" for n in sorted(amenders_used) if law_key(n) in laws) + ".",
        "Decreto 70/2023 (DNU), published 2023-12-21, has no vigencia clause, so the default rule gives 2023-12-30. The Government and the press announced 29 December 2023 (eight days counted from publication); we keep the statutory count and record the difference here.",
        "Decrees of necessity and urgency (DNU) are kind \"decree\" without temporary_until: under Ley 26.122 a DNU stays in force unless both chambers reject it, and InfoLEG's consolidated text of the retrieval day carries the changes of every DNU here.",
        "Decreto 70/2023 art. 249 abrogated Ley 27.551, but InfoLEG's consolidated text keeps the Code articles that Ley 27.551 wrote and that Decreto 70/2023 did not replace (arts. 1203, 1209, 1222, 1351); we follow InfoLEG.",
        "Units: one file per article (art-NNN; art-NNNN in the Código Civil y Comercial), plus the Preamble, the transitional provisions and the closing formula of the Constitution. Headings of books, titles, chapters, sections and parágrafos are not kept. InfoLEG's notes (\"Artículo sustituido por …\", \"Nota Infoleg: …\") are removed from the text; NBSP, quotes and dashes are normalised.",
        "Código Civil y Comercial: arts. 2277 and 2446 differ in norma.htm only by InfoLEG transcription errors (\"testa-mento\", \"Iegitimarios\"); the first version uses the texact.htm wording. Neither article was amended.",
        "Código Civil y Comercial in force from 2015-08-01: Ley 26.994 art. 7 as replaced by Ley 27.077 (B.O. 2014-12-19). Ley 27.077 changes no word of the Code and gets no commit.",
        "Ley 25.326: the parts vetoed by Decreto 995/2000 (art. 29 points 2 and 3, art. 47) were never in force and are left out of its first version; art. 47 was later enacted by Ley 26.343.",
        "Constitución: a single version, the 1994 text in force from 1994-08-24 (Disposición transitoria decimosexta: in force the day after publication; the Boletín Oficial of 1994-08-23 is not on InfoLEG and that publication day is not checked against a cached source). Its earlier texts are not on InfoLEG. Leyes 27.044 (2014) and 27.700 (2022) gave treaties constitutional hierarchy under art. 75 inc. 22 without changing its words, so they get no commit.",
        "Applicability: Ley 27.551 art. 23 (its changes apply to contracts concluded from its entry into force) and Ley 27.363 art. 3 (applies to pending situations) are recorded in `applies`.",
    ]
    applies = []
    if "ley-27551" in laws:
        applies.append({"law": "ley-27551", "provision": "",
                        "groups": [{"conditions": [{"kind": "commenced_on_or_after", "date": in_force(339378)}],
                                    "set_by": "Ley 27.551, art. 23 (contratos que se celebren a partir de su entrada en vigencia)"}]})
    if "ley-27363" in laws:
        applies.append({"law": "ley-27363", "provision": "",
                        "groups": [{"conditions": [{"kind": "commenced_on_or_after", "date": in_force(276135)}],
                                    "set_by": "Ley 27.363, art. 3"},
                                   {"conditions": [{"kind": "pending_on", "date": in_force(276135)}],
                                    "set_by": "Ley 27.363, art. 3 (situaciones jurídicas pendientes o en curso de ejecución)"}]})
    corpus = {"country": COUNTRY, "sources": sources, "laws": laws, "acts": acts_out, "applies": applies,
              "decisions": decisions,
              "ai_use": ["None at data-build time: fetch.py and parse.py are deterministic code written with Claude Code "
                         "(claude-opus-5-5); no model reads, writes, summarises or corrects legal text."]}
    return corpus, reports


def write_json(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes((json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n").encode("utf-8"))
    import os
    os.replace(tmp, path)


def main(argv: list[str]) -> None:
    only = set(a for a in argv if not a.startswith("-") and a != "report") or None
    corpus, reports = build_corpus(only)
    for r in reports:
        print(f"== {r['act']}: {len(r['ops'])} ops, {len(r['mismatches'])} mismatches, "
              f"{len(r['typography'])} typography-only, transcription {r['transcription']}")
        if "report" in argv:
            for o in r["ops"]:
                print("  ", o)
        for m in r["mismatches"]:
            print("   MISMATCH", m)
    write_json(HERE / ("corpus.json" if "--dry" not in argv else ".tmp-build/corpus.json"), corpus)
    for a in corpus["acts"]:
        print(a["slug"], len(a["versions"]), "versions", [v["from"] for v in a["versions"]])


if __name__ == "__main__":
    main(sys.argv[1:])
