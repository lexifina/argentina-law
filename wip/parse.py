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
import difflib
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

SUFFIXES = ["bis", "ter", "quater", "quinquies", "quinto", "sexies", "septies", "octies", "nonies", "decies"]
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
    return bool(NOTE_RE.search(s)) or s.lower().startswith("(nota infoleg") or bool(NOTE_ANY.search(s))


# any parenthesised note that says what a norm did: "(Segundo y tercer párrafos derogados por art. 3° de la Ley …)"
NOTE_ANY = re.compile(r"^\([^()]{0,80}?\b(?:derogad|sustituid|incorporad|vetad|observad|modificad|suprimid|renumerad)"
                      r"[oa]s?\s+(?:por|como)\b", re.I)


def note_like(x: str) -> bool:
    x = H.strip_links(x)
    return bool(NOTE_RE.search(x) or NOTE_ANY.search(x) or re.match(
        r"^\((?:Inciso|Incisos|Punto|Apartado)\s+\S{1,4}\)\s+(?:sustituid|incorporad|derogad|vetad|observad|modificad)", x, re.I))


INLINE_NOTE_RE = re.compile(r"\s*(\((?:[^()]|\([^()]*\))*\)|\((?:Inciso|Incisos|Punto|Apartado)\s+\S{1,4}\)\s[^()]*(?:\([^()]*\)[^()]*)?\))\s*$")


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
        hd = heading(s) if not s.startswith('"') else None
        if hd and not in_trans:
            num, suf, sub, rest = hd
            key = key_of(num, suf, sub, width)
            label = label_of(num, suf, sub)
            if key in units:  # a repeated heading: keep the first, treat the rest as body
                cur["body"].append(s)
                continue
            cur = units[key] = {"label": label, "kind": "art", "body": [], "notes": []}
            rest = rest.lstrip(".-: ") if re.match(r"^[.\-:\s]+\(", rest) else rest
            if rest:
                if is_note(rest):
                    cur["notes"].append(raw)
                else:
                    while True:  # trailing notes on the heading line: "… (Artículo 306 renumerado …). (…)"
                        mm = INLINE_NOTE_RE.search(rest.rstrip(". "))
                        if not (mm and note_like(mm.group(1))):
                            break
                        cur["notes"].append(mm.group(1))
                        rest = rest.rstrip(". ")[:mm.start()].rstrip()
                        rest = rest if rest.endswith(".") or not rest else rest + "."
                    if rest:
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
        if cur is not None and len(s) < 120 and not s.endswith(".") and len(s.split()) >= 3 and \
                not re.search(r"[a-záéíóúñ\d]", s) and cur["kind"] == "art":
            after_marker = False  # a title's heading in capitals ("DELITOS CONTRA LOS PODERES PUBLICOS …")
            continue
        if after_marker and cur is not None and is_note(raw):
            cur["notes"].append(raw)  # a note on the heading ("(Título incorporado por …)"); the title line follows
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
        if m and note_like(m.group(1)):
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
    60847: ("pub+8", "Ley 25.188, art. 43: its Capítulo IX (reformas al Código Penal) entra en vigencia a los ocho días de su publicación"),
    143873: ("2009-02-26", "Ley 26.394, art. 7: comenzará a regir a los seis meses de su promulgación (promulgada el 26 de agosto de 2008)"),
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
                "ciento ochenta": 180, "ciento veinte": 120}
VIG_RE = re.compile(r"^(?:las\s+disposiciones\s+de\s+)?(?:la\s+|el\s+)?(?:presente\s+(?:ley|decreto|medida)|esta\s+ley)\s+"
                    r"(?:entrar[aá]n?\s+en\s+(?:vigencia|vigor)|regir[aá]n?\b|rige\b|tendr[aá]\s+vigencia|"
                    r"comenzar[aá]\s+a\s+regir|cobrar[aá]\s+vigencia)", re.I)


def auto_rule(nid: int) -> tuple[str, str]:
    """The norm's own vigencia clause, read from the first line of each of its articles (never from quoted text).

    Returns (rule, citation): "pub", "pub+N" or "default" (no clause found). Anything else is "unknown"."""
    r = bulk()[nid]
    label = law_entry(nid)["label"]
    if not amender_articles(nid):
        return "default", f"{label}: its text is not on InfoLEG, so the default rule is used"
    for num, lines in amender_articles(nid):
        t = re.sub(r"^(?:Entrada en vigencia|Entrada en vigor|Vigencia)\s*\.\s*-?\s*", "", lines[0], flags=re.I)
        if not VIG_RE.search(t) and not re.match(r"^salvo disposici[oó]n en contrario,?\s+(?:los\s+art[ií]culos\s+de\s+)?la\s+"
                                                  r"presente\s+ley\s+entrar[aá]n?\s+en\s+vigencia", t, re.I):
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
    if r["tipo_norma"].startswith("Resoluci"):
        return f"resolucion-{organ(r)[0]}-{r['numero_norma']}-{year}"
    return f"{fold(r['tipo_norma']).replace(' ', '-')}-{r['numero_norma']}-{year}"


def organ(r: dict) -> tuple[str, str]:
    o = fold(r["organismo_origen"])
    if "comision bicameral" in o:
        return "cb", "Comisión Bicameral de Monitoreo e Implementación del Código Procesal Penal Federal"
    if "ministerio de justicia" in o:
        return "mj", "Ministerio de Justicia"
    return "x", r["organismo_origen"].title()


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
        if r["tipo_norma"].startswith("Resoluci"):
            label += " (" + ("Comisión Bicameral" if organ(r)[0] == "cb" else organ(r)[1]) + ")"
    title = r["titulo_sumario"].strip()
    if r["titulo_resumido"].strip():
        title += ": " + r["titulo_resumido"].strip()
    return {"label": label, "title": title,
            "kind": "law" if r["tipo_norma"] == "Ley" else "decree",
            "enacted": r["fecha_sancion"] or None, "published": r["fecha_boletin"] or None,
            "url": F.norma_url(nid), "temporary_until": None, "restores": None, "note": None}


# ------------------------------------------------------------------ the amending norms

SUF = r"bis|ter|qu[aá]ter|quinquies|quinto|sexies|septies|octies"
REF = r"(\d+)(?:\s*[°º])?(?:\s+\(?(" + SUF + r")\)?)?(?:\s*\((\d)\))?"   # "268 (2)", "204 ter", "41 quinquies"
ORD = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "quinto": 5, "sexto": 6,
       "septimo": 7, "octavo": 8, "noveno": 9, "decimo": 10, "ultimo": "last", "ultimos": "last"}
ORD_RE = r"(primer|primero|segundo|tercer|tercero|cuarto|quinto|sexto|s[eé]ptimo|octavo|noveno|d[eé]cimo|[uú]ltimos?)"
V_REPLACE = r"(?:Sustit[uú]y[ae]n?se|Reempl[aá]c[ae]n?se|Modif[ií]c[ae]n?se|Modif[ií]qu[ae]n?se|Sustituir|Modificar|Reemplazar)"
V_INSERT = r"(?:Incorp[oó]r[ae]n?se|Agr[eé]gu?[ae]n?se|Incorporar|Agregar)"
V_REPEAL = r"(?:Der[oó]g[ae]n?se|Supr[ií]m[ae]n?se|Derogar|Suprimir)"
V_RENUMBER = r"(?:Renum[eé]r[ae]n?se)"


def dethousand(s: str) -> str:
    """"Artículo 1.204 bis" -> "Artículo 1204 bis" (the thousands dot of article numbers)."""
    return re.sub(r"\b(\d{1,2})\.(\d{3})\b", r"\1\2", s)


def dehead(s: str) -> str:
    """Drop only the thousands dot of a leading article number ("Artículo 1.196: …"), keeping the rest as written."""
    m = re.match(r"^\"?((?:ART[IÍ]CULO|Art[ií]culo|Art\.)\s*\d{1,2})\.(\d{3})", s)
    return s[:m.end(1)] + s[m.end(1) + 1:] if m else s


def heading(s: str) -> tuple[int, str | None, str | None, str] | None:
    """An article heading at the start of a line: (number, suffix word, "(n)" sub-number, rest of the line)."""
    s = dehead(s.lstrip('"\''))
    s = re.sub(r"^((?:ART[IÍ]CULO|Art[ií]culo)\s*\d+)\s*:\s*(" + SUF + r")\s*:", r"\1 \2:", s)
    sub = None
    m0 = re.match(r"^((?:ART[IÍ]CULO|Art[ií]culo|Art\.)\s*\d+\s*[°º]?)\s*\((\d)\)", s)
    if m0:
        sub = m0.group(2)
        s = m0.group(1) + s[m0.end():]
    m = ART_RE.match(s)
    if not m:
        return None
    rest = m.group(3).strip()
    if re.fullmatch(r"[.…\s]*", rest):
        rest = ""
    return int(m.group(1)), m.group(2), sub, rest


def key_of(num: int, suf: str | None, sub: str | None, width: int) -> str:
    return f"art-{num:0{width}d}" + (f"-{fold(suf)}" if suf else "") + (f"-{sub}" if sub else "")


def label_of(num: int, suf: str | None, sub: str | None) -> str:
    return f"Art. {num}" + (f" {fold(suf)}" if suf else "") + (f" ({sub})" if sub else "")


def label_from_key(k: str) -> str:
    m = re.fullmatch(r"art-0*(\d+)(?:-([a-z]+))?(?:-(\d))?", k)
    return label_of(int(m.group(1)), m.group(2), m.group(3)) if m else k


def amender_articles(nid: int) -> list[tuple[int, list[str]]]:
    """The amending norm's own articles, in order: (number, [first line after the heading, following lines…]).

    An article starts at a heading whose number is the next one expected (1, 2, 3 …); headings inside the quoted or
    unquoted new text ("Artículo 700 bis: …") have other numbers and stay in the body."""
    b = F.cached(F.norma_url(nid))
    if b is None:
        raise SystemExit(f"not cached: amender {nid} (run fetch.py amenders)")
    out, expect, cur, base = [], 1, None, 0
    for raw in H.lines(b):
        s = H.strip_links(raw)
        if re.match(r"^ANEXO\s+([IVX]+|\d+)\s*$", s) and expect > 1:
            base, expect = base + 1000, 1  # an annex numbers its own articles again from 1
            cur = None
            continue
        m = ART_RE.match(dehead(s)) if not s.startswith('"') else None
        waiting = cur is not None and len(cur) == 1 and cur[0].rstrip().endswith(":")  # "… por el siguiente:" and no text yet
        if m and int(m.group(1)) == expect and not m.group(2) and not waiting:
            cur = [m.group(3).strip()]
            out.append((base + expect, cur))
            expect += 1
            continue
        if cur is not None:
            cur.append(s)
    return out


def clean_body(body: list[str]) -> list[str]:
    """The new wording given after an instruction, as lines: quotes, notes and the amending law's own headings and
    closing formulas removed. Article headings inside it are kept (see split_articles)."""
    body = ['"' + b[1:] if i == 0 and b.startswith("'") else b for i, b in enumerate(body)]
    out, quoted = [], bool(body) and body[0].startswith('"')
    for i, s in enumerate(body):
        if MARKER_RE.match(s) and not s.startswith('"') and not quoted and heading(s) is None:
            if out:
                break
            continue  # a chapter or title heading introducing the new articles
        if re.match(r"^(DADA EN LA SALA|Comun[ií]quese|- ?REGISTRAD)", s, re.I):
            break
        if is_note(s):
            continue
        s = s.strip()
        end = quoted and bool(re.search(r'["\'][.;]?$', s)) and not (i == 0 and len(s) < 3)
        if s.startswith('"') and (i == 0 or quoted):  # Spanish style reopens the quote on each paragraph
            s = s[1:].lstrip()
        if end:
            s = re.sub(r'\s*["\']([.;]?)$', r"\1", s)
        out.append(s)
        if end:
            break
    return [s for s in out if s]


def new_text(body: list[str]) -> list[str]:
    """The new wording of one article: the heading of the article itself removed."""
    out = clean_body(body)
    if out:
        h = heading(out[0])
        if h:
            rest = h[3].lstrip("-– ").strip()
            out = ([rest] if rest else []) + out[1:]
    return out


def split_articles(body: list[str], width: int) -> list[tuple[str, str, list[str]]]:
    """New articles given one after another ("Artículo 213 ter: … Artículo 213 quater: …"): [(key, label, lines)]."""
    lines = clean_body(body)
    first = next((i for i, l in enumerate(lines[:3]) if heading(l)), None)
    if first is None:
        return []
    lines = lines[first:]
    out = []
    for s in lines:
        h = heading(s)
        if h and not re.match(r"^(inciso|\d)", s, re.I):
            num, suf, sub, rest = h
            out.append((key_of(num, suf, sub, width), label_of(num, suf, sub), [rest] if rest else []))
        elif out:
            out[-1][2].append(s.strip('"'))
    return out


def refs(s: str, width: int) -> list[str]:
    """Article references in an instruction: "artículos 303, 304 y 305", "artículo 268 (2)", "art. 107"."""
    s = re.sub(r"(incisos?|inc\.)\s*\d+\s*[°º]?\)?(?:\s*(?:,|y)\s*\d+\s*[°º]?\)?(?=\s*(?:,|y|del|de)\b))*", " ", dethousand(s), flags=re.I)
    return [key_of(int(n), suf, sub, width) for n, suf, sub in re.findall(REF, s)]


def item_no(line: str) -> str | None:
    """The number or letter of an item ("1º …", "2) …", "3. …", "Inciso 6: …", "d) …")."""
    m = re.match(r"^(?:inciso\s+)?(\d+)\s*(?:[º°]\.?|\)|\.(?!\d)|-|:)|^([a-z])\)", line.strip('"'), re.I)
    return (m.group(1) or m.group(2).lower()) if m else None


def ordinals(s: str) -> list:
    return [ORD[fold(w)] for w in re.findall(ORD_RE, s, re.I)]


def parse_head(head: str, full: str, body: list[str], width: int) -> list[dict]:
    """Operations from one instruction. `head` is the text before the act's name, `full` the whole first line."""
    h = re.sub(r"\s+", " ", head).strip(" -,")
    hf = fold(h)
    ops: list[dict] = []
    if re.search(r"penas de multa", hf):
        return [{"op": "fines"}]
    if re.search(V_RENUMBER, h, re.I):
        m = re.search(V_RENUMBER + r"\s+(?:el|los)\s+art[ií]culos?\s+(.+?)\s+(?:del\s+C[oó]digo[^,]*?,?\s+)?como\s+art[ií]culos?\s+"
                      r"(.+?)(?:\s*,?\s*respectivamente|\s+e\s+incorp|\.|$)", dethousand(full), re.I)
        if m:
            a, b = refs(m.group(1), width), refs(m.group(2), width)
            if len(a) == len(b):
                ops.append({"op": "renumber", "pairs": list(zip(a, b))})
        arts = split_articles(body, width)
        ops += [{"op": "insert", "keys": [k], "label": lab, "text": t} for k, lab, t in arts]
        return ops or [{"op": "unknown"}]
    if re.search(r"r[uú]brica|denominaci[oó]n|ep[ií]grafe", h, re.I) or (re.search(r"r[uú]brica|denominaci[oó]n|ep[ií]grafe", full, re.I) and not re.search(r"art[ií]culo\s+\d", h, re.I)) or \
            (re.search(r"\bt[ií]tulo\b|\bcap[ií]tulo\b", h, re.I) and not re.search(r"art[ií]culo", h, re.I)
             and not split_articles(body, width)):
        return [{"op": "heading"}]
    # composite: "Modifícase el Código Penal de la siguiente manera: 1. Incorpórase … 2. Sustitúyese …"
    if not re.search(r"art[ií]culo|art\.|inciso|p[aá]rrafo", h, re.I) and body and \
            re.match(r"^\d+\s*\.\s*" + r"(?:" + V_REPLACE + "|" + V_INSERT + "|" + V_REPEAL + ")", body[0], re.I):
        parts, cur = [], None
        for s in body:
            if re.match(r"^\d+\s*\.\s*(?:" + V_REPLACE + "|" + V_INSERT + "|" + V_REPEAL + ")", s, re.I):
                cur = [re.sub(r"^\d+\s*\.\s*", "", s)]
                parts.append(cur)
            elif cur is not None:
                cur.append(s)
        for p in parts:
            ops += parse_head(p[0], p[0], p[1:], width)
        return ops
    # new articles given one after another, with no article named in the instruction
    if re.search(V_INSERT, h, re.I) and not re.search(r"art[ií]culo\s+\d|inciso|p[aá]rrafo", h, re.I):
        arts = split_articles(body, width)
        if arts:
            return [{"op": "insert", "keys": [k], "label": lab, "text": t} for k, lab, t in arts]
    # repeals, possibly several clauses: "Deróganse el artículo 78 bis y el inciso 1º del artículo 117 bis"
    if re.search(V_REPEAL, h, re.I):
        rest = re.split(V_REPEAL, h, maxsplit=1, flags=re.I)[1]
        clauses = re.split(r"\s+y\s+(?=(?:el|la|los|las)\s)|,\s*(?=(?:el|la|los|las)\s)", rest)
        for c in clauses:
            c = c.strip()
            m = re.search(r"incisos?\s+(.+?)\s+del\s+art[ií]culo\s+" + REF, c, re.I)
            if m:
                ks = refs("artículo " + c[m.start(2):], width)[:1]
                items = re.findall(r"(\d+)", m.group(1)) or re.findall(r"\b([a-z])\)", m.group(1))
                ops.append({"op": "lines", "action": "delete", "keys": ks, "items": items})
                continue
            m = re.search(ORD_RE + r"(?:\s+y\s+" + ORD_RE + r")?\s+p[aá]rrafos?\s+del\s+art[ií]culo\s+" + REF, c, re.I)
            if m:
                ks = refs(c[c.lower().index("art"):], width)[:1]
                ops.append({"op": "lines", "action": "delete", "keys": ks, "paras": ordinals(c[:m.end(2) or m.end(1)])})
                continue
            if re.search(r"art[ií]culos?|art\.", c, re.I):
                ops.append({"op": "repeal", "keys": refs(c, width)})
                continue
            ops.append({"op": "unknown"})
        return ops
    text = new_text(body)
    # items (incisos)
    m = re.search(r"incisos?\s+(.+?)\s+(?:(?:del|al)\s+)?art[ií]culo\s+" + REF, h, re.I)
    if m:
        ks = refs("artículo " + h[m.start(2):], width)[:1]
        items = re.findall(r"(\d+)", m.group(1)) or re.findall(r"\b([a-z])\)", m.group(1))
        action = "insert" if re.search(V_INSERT, h, re.I) else "replace" if re.search(V_REPLACE, h, re.I) else None
        if action:
            return [{"op": "lines", "action": action, "keys": ks, "items": items, "text": clean_body(body)}]
    # paragraphs
    m = re.search(r"(?:p[aá]rrafos?\s+" + ORD_RE + r"(?:\s+y\s+" + ORD_RE + r")?|" + ORD_RE + r"(?:\s+y\s+" + ORD_RE +
                  r")?\s+p[aá]rrafos?)\s+(?:del|al)\s+(?:art[ií]culo|art\.)\s*" + REF, h, re.I)
    if m:
        ks = refs(re.search(r"(?:art[ií]culo|art\.)\s*.*$", h[m.start():], re.I).group(0), width)[:1]
        paras = ordinals(h[m.start():m.end()].split("del")[0].split("al artículo")[0])
        after = bool(re.search(r"a\s+continuaci[oó]n\s+del", h, re.I))
        if re.search(V_INSERT, h, re.I):
            action = "insert_after" if after else "insert"
        elif re.search(V_REPLACE, h, re.I):
            action = "replace"
        else:
            action = None
        if action:
            return [{"op": "lines", "action": action, "keys": ks, "paras": paras, "text": text}]
    m = re.search(V_REPLACE + r"\s+(?:el\s+)?(?:art[ií]culo|art\.)\s*" + REF + r"\s+in\s+fine", h, re.I)
    if m:  # "Sustitúyese el artículo 80 in fine": its last paragraph
        k = key_of(int(m.group(1)), m.group(2), m.group(3), width)
        return [{"op": "lines", "action": "replace", "keys": [k], "paras": ["last"], "text": text}]
    # whole articles
    if re.search(V_INSERT, h, re.I):
        m = re.search(r"(?:como\s+)?(?:nuevo\s+)?art[ií]culo\s+" + REF, h, re.I)
        arts = split_articles(body, width)
        if m:
            k = key_of(int(m.group(1)), m.group(2), m.group(3), width)
            return [{"op": "insert", "keys": [k], "label": label_of(int(m.group(1)), m.group(2), m.group(3)), "text": text}]
        if arts:
            return [{"op": "insert", "keys": [k], "label": lab, "text": t} for k, lab, t in arts]
    m = re.search(V_REPLACE + r"\s+(?:(?:al|el|como)\s+)?(?:texto\s+del\s+)?(?:art[ií]culo|art\.)\s*" + REF, h, re.I)
    if m:
        k = key_of(int(m.group(1)), m.group(2), m.group(3), width)
        return [{"op": "replace", "keys": [k], "label": label_of(int(m.group(1)), m.group(2), m.group(3)), "text": text}]
    return [{"op": "unknown"}]


def instruction(text: str, body: list[str], target: str, width: int, implicit: bool = False) -> list[dict] | None:
    """What one article of an amending norm does to the act, or None if it does not address it."""
    mi = re.search(r":\s*([\"'](?:ART[IÍ]CULO|Art[ií]culo).+)$", text)
    if mi:
        body, text = [mi.group(1)] + list(body), text[:mi.start() + 1]
    t = dethousand(text)
    t = re.sub(r"\s+de\s+la\s+ley\s+(?:N[°º]\s*)?11179\s*,?\s*(?=C[oó]digo Penal)", " del ", t, flags=re.I)
    t = re.sub(r"\s+de\s+la\s+ley\s+(?:N[°º]\s*)?11179\b", " del Código Penal", t, flags=re.I) if "Penal" in target else t
    VERB = r"(?:(Sustit[uú]y|Reempl[aá]c|Modif[ií]c|Modif[ií]qu|Der[oó]g|Incorp[oó]r|Agr[eé]gu?|Supr[ií]m|Renum[eé]r)[ae]n?se|^(?:Incorporar|Sustituir|Derogar|Modificar|Reemplazar|Agregar|Suprimir))\b"
    if not re.search(target, t, re.I) and implicit and re.search(VERB, t, re.I) and re.search(r"art[ií]culo", t, re.I) and \
            not re.search(r"\b(?:ley|decreto|c[oó]digo|r[eé]gimen)\b", t, re.I):
        # a norm that amends only this act ("Incorpórase el artículo 127 ter."): its articles need not name it
        return [dict(o, instruction=text) for o in parse_head(t, t, body, width)]
    if not re.search(target, t, re.I):
        # an article whose own first line is only an epigraph, with numbered instructions below it
        subs = [i for i, l in enumerate(body) if re.match(r"^\d+\s*[.)-]\s*" + VERB, l, re.I) and re.search(target, l, re.I)]
        if not subs or re.search(VERB, t, re.I):
            return None
        ops = []
        for j, i in enumerate(subs):
            end = subs[j + 1] if j + 1 < len(subs) else len(body)
            ops += instruction(re.sub(r"^\d+\s*[.)-]\s*", "", body[i]), body[i + 1:end], target, width) or []
        return ops
    groups = [i for i, l in enumerate(body) if re.match(r"^ART[IÍ]CULO\s+\d+(?:\s+(?:" + SUF + r"))?\s*[°º]?$", l)]
    if groups and re.search(r"siguientes\s+modificaciones", t, re.I):
        ops = []
        for j, i in enumerate(groups):
            end = groups[j + 1] if j + 1 < len(groups) else len(body)
            art = re.sub(r"^ART[IÍ]CULO\s+", "", body[i]).strip(" °º")
            if i + 1 >= end:
                continue
            ins = body[i + 1]
            if re.search(r"inciso|p[aá]rrafo", ins, re.I):
                ins = re.sub(r"((?:incisos?\s+[\d°º\s,y]+?|p[aá]rrafo\s+\w+|\w+\s+p[aá]rrafo))(\s+(?:el|la|los|por)\b)",
                             r"\1 del artículo " + art + r"\2", ins, count=1, flags=re.I)
            else:
                ins = re.sub(r"^(\w+)\s+", r"\1 el artículo " + art + " ", ins, count=1)
            ops += parse_head(ins, ins, body[i + 2:end], width)
        return ops
    mv = re.search(VERB, t, re.I)
    if mv:
        t = t[mv.start():]
    head = re.split(r"\s+(?:del?|al)\s+(?:la\s+)?(?:" + target + ")", t, maxsplit=1, flags=re.I)[0]
    if not re.search(VERB, head, re.I):
        return None  # the article only mentions the act
    if re.search(r"\b(?:de|del)\s+(?:la\s+)?(?:ley|decreto)(?:\s+N[°º])?\s*\d", head, re.I):
        return None  # it amends another norm and only mentions the act
    ops = parse_head(head, t, body, width)
    for o in ops:
        o["instruction"] = text
    return ops


def repealed_in_texact(u: dict) -> bool:
    """InfoLEG keeps a repealed article as its heading, at most its epigraph, and a note "(Artículo derogado por …)"."""
    b = body_of(u)
    notes = " ".join(H.strip_links(n) for n in u.get("notes", []))
    if re.search(r"(?:Art[ií]culo|Cap[ií]tulo\s+\S+|T[ií]tulo\s+\S+)\s+derogad", notes, re.I) and len(b) <= 1:
        return True
    return bool(re.search(r"derogad", notes, re.I)) and (not b or (len(b) == 1 and len(b[0]) < 90 and b[0].endswith(".")
                                                                   and not re.search(r"\b(ser[aá]|deber[aá]|tendr[aá])\b", b[0])))


def amenders_of(act: dict) -> list[int]:
    """The norms to replay: those named in the act's consolidated-text notes or listed by InfoLEG as modifying it, that
    are laws or decrees, took effect after the base text, and are cached."""
    if "amenders" in act:
        return act["amenders"]
    B = bulk()
    T = H.lines(F.cached(F.norma_url(act["id"], "texact.htm")))  # the whole page, with "Antecedentes Normativos"
    ids = {int(x) for l in T for x in H.LINK_RE.findall(l)} | {m["id"] for m in modifiers(act["id"])}
    plain = [H.strip_links(l) for l in T]
    if "Antecedentes Normativos" in plain:  # earlier amendments, named by number only
        laws_by_no = {}
        for k, r in B.items():
            if r["tipo_norma"] == "Ley":
                laws_by_no.setdefault(r["numero_norma"], k)
        for l in plain[plain.index("Antecedentes Normativos"):]:
            for n in re.findall(r"Ley\s*N?[°º]?\s*([\d.]+)", l):
                if n.replace(".", "") in laws_by_no:
                    ids.add(laws_by_no[n.replace(".", "")])
    since = act["base_published"]
    out = [i for i in sorted(ids) if i in B and B[i]["tipo_norma"] in ("Ley", "Decreto")
           and (B[i]["fecha_boletin"] or "") > since and F.cached(F.norma_url(i)) is not None]
    return out


def amendments(act: dict, ids: list[int]) -> list[dict]:
    """Every instruction aimed at `act` in the norms `ids`, with the law's key and in-force day, in force order."""
    out = []
    overrides = act.get("overrides", {})
    for nid in ids:
        for num, lines in amender_articles(nid):
            if (nid, num) in overrides:
                ops = [dict(o, instruction=lines[0]) for o in overrides[(nid, num)]]
                for o in ops:
                    if o["op"] in ("insert", "replace") and "text" not in o:
                        o["text"] = new_text(lines[1:])
            else:
                implicit = bool(re.search(act["target"], bulk()[nid]["titulo_sumario"] + " " + bulk()[nid]["titulo_resumido"], re.I))
                ops = instruction(lines[0], lines[1:], act["target"], act.get("width", 3), implicit) or []
            for i, op in enumerate(ops):
                op.update({"nid": nid, "law": law_key(nid), "from": in_force(nid), "art": num, "sub": i})
                out.append(op)
    out.sort(key=lambda o: (o["from"], o.get("order", 0), bulk()[o["nid"]]["fecha_boletin"], o["nid"], o["art"], o["sub"]))
    return out


# ------------------------------------------------------------------ comparison

def loose(lines: list[str]) -> str:
    """Words only: what is left when punctuation, case, accents and spacing are ignored."""
    return " ".join(re.findall(r"[a-z0-9]+", fold(" ".join(lines))))


def body_of(u: dict | None) -> list[str]:
    return [b for b in (u or {}).get("body", []) if b]


def fine_keys(o: dict, width: int) -> list[str]:
    """Articles of the Código Penal whose fines a fines-update law sets ("… establecidas por los artículos 94, 99 inciso
    1º … del Código Penal")."""
    ks = []
    for s in o.get("body", []):
        for m in re.finditer(r"art[ií]culos?\.?\s+(.+?)\s+del\s+C[oó]digo\s+Penal", s, re.I):
            seg = re.sub(r"(?:primer|segundo|tercer|[uú]ltimo)\s+p[aá]rrafo\s+del\s+", "", m.group(1), flags=re.I)
            for k in refs(seg, width):
                if k not in ks:
                    ks.append(k)
    return ks


# ------------------------------------------------------------------ the replay

def apply_lines(body: list[str], o: dict) -> list[str] | None:
    """A change to some lines of an article (items or paragraphs). None if it cannot be placed."""
    body, new = list(body), list(o.get("text", []))
    if "items" in o:
        new = [re.sub(r"^Art[ií]culo\s+\d+\s*,\s*(?=inciso)", "", l, flags=re.I) for l in new]  # "Artículo 163, inciso 1°- …"
        new = [l for l in new if not (heading(l) and not item_no(l))]
        idx = {item_no(l): i for i, l in reversed(list(enumerate(body))) if item_no(l)}
        if o["action"] == "delete":
            pos = [idx.get(it) for it in o["items"]]
            if None in pos:
                return None
            return [l for i, l in enumerate(body) if i not in pos]
        if o["action"] == "replace":
            last = None
            for line in new:
                it = item_no(line)
                if it is None and last is not None:  # a paragraph that continues the item just replaced
                    last += 1
                    body.insert(last, line)
                    continue
                it = it or (o["items"][0] if len(o["items"]) == 1 else None)
                idx = {item_no(l): j for j, l in reversed(list(enumerate(body))) if item_no(l)}
                if it not in idx:
                    return None
                body[idx[it]] = line
                last = idx[it]
            return body
        if o["action"] == "insert":
            for n_, line in enumerate(new):
                it = item_no(line)
                if it is None and len(new) == len(o["items"]):
                    it = o["items"][n_]
                    line = f"{it}. {line}"  # the item's number, from the instruction ("como inciso 10")
                it = it or o["items"][0]
                prev = str(int(it) - 1) if it.isdigit() else chr(ord(it) - 1)
                if prev in idx:
                    # after the previous item's line and any lines that continue it (not items, not a closing paragraph)
                    i = idx[prev] + 1
                    body.insert(i, line)
                    idx = {item_no(l): j for j, l in reversed(list(enumerate(body))) if item_no(l)}
                else:
                    return None
            return body
    if "paras" in o:
        n = len(body)
        pos = [n if p == "last" else p for p in o["paras"]]
        if o["action"] == "delete":
            if any(p < 1 or p > n for p in pos):
                return None
            return [l for i, l in enumerate(body, 1) if i not in pos]
        if o["action"] == "replace":
            if any(p < 1 or p > n for p in pos):
                return None
            if len(new) == len(pos):
                for p, line in zip(pos, new):
                    body[p - 1] = line
                return body
            return body[:pos[0] - 1] + new + body[pos[-1]:]
        if o["action"] == "insert":
            p = o["paras"][0]
            if p == "last":
                return body + new
            if p - 1 > n:
                return None
            return body[:p - 1] + new + body[p - 1:]
        if o["action"] == "insert_after":
            p = pos[0]
            if p > n:
                return None
            return body[:p] + new + body[p:]
    return None


def replay(act: dict) -> dict:
    """Replay the amending norms on the act as enacted. Returns versions, the laws used and a report."""
    width = act.get("width", 3)
    L, url0, sha0 = act_lines(act.get("base_id", act["id"]), "norma.htm", act["start"], act["end"])
    for pat, repl in act.get("base_fixes", []):
        L = [re.sub(pat, repl, l) for l in L]
    state = {k: {"label": u["label"], "kind": u["kind"], "body": body_of(u)}
             for k, u in split_units(L, width=width, transitorias=act.get("transitorias", False)).items()}
    report = {"act": act["slug"], "ops": [], "mismatches": [], "typography": [], "transcription": [], "reconciled": [],
              "headings": [], "not_applied": []}
    for key, drop in act.get("vetoed", {}).items():
        if drop is None:
            state.pop(key, None)
        else:
            state[key]["body"] = [b for b in state[key]["body"] if not re.match(drop, b)]
    amenders = amenders_of(act) if act.get("texact") else []
    ops = amendments(act, amenders) if amenders else []
    for o in ops:
        if o["op"] == "fines":
            o["body"] = next(l for n, l in amender_articles(o["nid"]) if n == o["art"])[1:]
            o["keys"] = fine_keys(o, width)
    report["base_gaps"], report["from_notes"] = [], []
    if act.get("texact"):
        T0, _, _ = act_lines(act["id"], "texact.htm", act["start"], act["end"])
        tex0 = split_units(T0, width=width, transitorias=act.get("transitorias", False))
        # norms InfoLEG names but whose own text it does not serve ("No se pudo acceder al archivo solicitado"): the
        # change is taken from the note and the consolidated text (a repeal, or the article's whole current text when
        # the note names no other norm)
        unreadable = {n for n in amenders if not amender_articles(n)}
        for k, u in tex0.items():
            named = [int(x) for n in u["notes"] for x in H.LINK_RE.findall(n)]
            for nid in sorted(set(named) & unreadable):
                o = {"nid": nid, "law": law_key(nid), "from": in_force(nid), "art": 0, "sub": 0, "keys": [k],
                     "instruction": " ".join(H.strip_links(n) for n in u["notes"])}
                if repealed_in_texact(u):
                    o["op"] = "repeal"
                elif len(set(named)) == 1 and body_of(u):
                    o.update(op="replace", text=body_of(u), label=u["label"])
                else:
                    continue
                ops.append(o)
                report["from_notes"].append(f"{k}: {o['op']} by {o['law']} (from InfoLEG's note; its text is not on InfoLEG)")
        # an article InfoLEG shows as repealed ("(Artículo derogado por …)", "(Capítulo VIII derogado por …)") that no
        # replayed instruction repeals by its number: repealed on the day of the norm the note names
        for k, u in tex0.items():
            if not repealed_in_texact(u):
                continue
            rep_ids = [n["id"] for raw in u["notes"] for n in parse_note(raw) if n["verb"].startswith("derogad") and n["id"]]
            if not rep_ids or rep_ids[-1] not in bulk():
                continue
            nid = rep_ids[-1]
            if any(o["op"] == "repeal" and k in o.get("keys", []) for o in ops) or nid in unreadable and \
                    any(o.get("art") == 0 and k in o.get("keys", []) for o in ops):
                continue
            if nid not in amenders:
                continue
            ops.append({"nid": nid, "law": law_key(nid), "from": in_force(nid), "art": 0, "sub": 0, "keys": [k], "op": "repeal",
                        "instruction": " ".join(H.strip_links(n) for n in u["notes"])})
            report["from_notes"].append(f"{k}: repeal by {law_key(nid)} (from InfoLEG's note: the article, or its chapter, derogado)")
        ops.sort(key=lambda o: (o["from"], o.get("order", 0), bulk()[o["nid"]]["fecha_boletin"], o["nid"], o["art"], o["sub"]))
        # articles InfoLEG's consolidated text shows with no note that are missing from its transcription of the
        # base text and that no replayed norm adds: in force before the base text; added to the first version
        added = {k for o in ops if o["op"] in ("insert", "replace") for k in o.get("keys", [])} | \
            {b for o in ops if o["op"] == "renumber" for _, b in o["pairs"]}
        if act.get("base_from_texact"):
            for k, u in tex0.items():
                if body_of(u) and not u["notes"] and k not in state and k not in added:
                    state[k] = {"label": u["label"], "kind": u["kind"], "body": body_of(u)}
                    report["base_gaps"].append(k)
    versions = [{"from": act["first_day"], "source_url": url0, "sha256": sha0,
                 "state": {k: dict(v) for k, v in state.items()}, "credits": {}, "laws": [act["first_law"]]}]
    for st in act.get("steps", []):
        ops.append({"op": "step", "nid": st["nid"], "law": law_key(st["nid"]), "from": st["from"], "art": 0, "sub": 0,
                    "units": st.get("units"), "instruction": st["note"]})
    ops.sort(key=lambda o: (o["from"], o.get("order", 0), bulk()[o["nid"]]["fecha_boletin"], o["nid"], o["art"], o["sub"]))
    report["nids"] = sorted({o["nid"] for o in ops if o["op"] not in ("heading", "unknown", "skip")})
    report["fines_nids"] = sorted({o["nid"] for o in ops if o["op"] == "fines"})
    patches = act.get("patches", {})
    renames: list[tuple[int, str, str]] = []  # (index of the version that renumbers, old key, new key)
    worded: set[str] = set()                   # keys whose words a replayed norm set
    for day in sorted({o["from"] for o in ops}):
        day_ops = [o for o in ops if o["from"] == day]
        credits: dict[str, list[str]] = {}
        quiet: dict[str, list[str]] = {}

        def credit(k, law, to=credits):
            to.setdefault(k, [])
            if law not in to[k]:
                to[k].append(law)

        for o in day_ops:
            tag = f"{day} {o['law']} art. {o['art']}"
            if o["op"] == "heading":
                report["headings"].append(f"{tag}: {o['instruction'][:120]}")
                continue
            if o["op"] in ("replace", "insert") and not o.get("text"):
                o["op"] = "skip"  # "Modifícase el artículo 24 … para los casos comprendidos en esta ley": no new words
            if o["op"] in ("unknown", "skip"):
                (report["not_applied"] if o["op"] == "unknown" else report["headings"]).append(
                    f"{tag}: {o['op']}: {o['instruction'][:160]}")
                continue
            if o["op"] == "step":
                ks = sorted(state) if o["units"] is None else [key_of(n, None, None, width) for n in o["units"]]
                for k in ks:
                    if k in state:
                        credit(k, o["law"], quiet)
                report["ops"].append(f"{tag}: in-force step for {'all' if o['units'] is None else len(ks)} provisions")
                continue
            if o["op"] == "fines":
                for k in o["keys"]:
                    if k in state:
                        credit(k, o["law"], quiet)
                report["ops"].append(f"{tag}: fines {' '.join(o['keys'])}")
                continue
            if o["op"] == "renumber":
                moved = {a: state.pop(a) for a, _ in o["pairs"] if a in state}
                for a, b in o["pairs"]:
                    if a in moved:
                        state[b] = dict(moved[a], label=label_from_key(b))
                        renames.append((len(versions), a, b))
                        if a in worded:
                            worded.add(b)
                        credit(a, o["law"])
                        credit(b, o["law"])
                    else:
                        report["not_applied"].append(f"{tag}: renumber {a} -> {b}: {a} not in force")
                report["ops"].append(f"{tag}: renumber {o['pairs']}")
                continue
            for k in o.get("keys", []) or [None]:
                before = state.get(k)
                if k is None:
                    report["not_applied"].append(f"{tag}: {o['op']}: no article: {o['instruction'][:160]}")
                    continue
                if o["op"] in ("replace", "insert"):
                    state[k] = {"label": o.get("label") or label_from_key(k), "kind": "art", "body": list(o["text"])}
                elif o["op"] == "repeal":
                    if k not in state:
                        report["not_applied"].append(f"{tag}: repeal {k}: not in force")
                        continue
                    state.pop(k)
                elif o["op"] == "lines":
                    nb = apply_lines(before["body"], o) if before else None
                    if nb is None:
                        report["not_applied"].append(f"{tag}: {o['action']} {o.get('items') or o.get('paras')} in {k}: "
                                                     f"cannot place it: {o['instruction'][:120]}")
                        continue
                    state[k] = dict(before, body=nb)
                else:
                    continue
                if state.get(k) != before:
                    credit(k, o["law"])
                    worded.add(k)
                report["ops"].append(f"{tag}: {o['op']} {o.get('action', '')} {k}".replace("  ", " "))
        for law, k, pat, rep in [(law_key(n), *x) for n in sorted({o["nid"] for o in day_ops})
                                 for x in patches.get(n, [])]:
            if k in state:
                nb = [re.sub(pat, rep, l) for l in state[k]["body"]]
                if nb != state[k]["body"]:
                    state[k] = dict(state[k], body=nb)
                    report["ops"].append(f"{day} {law}: veto in {k}: {pat!r} -> {rep!r}")
        for k, ls in quiet.items():
            if k not in credits:
                credits[k] = []
            for l in ls:
                if l not in credits[k]:
                    credits[k].append(l)
        nids = sorted({o["nid"] for o in day_ops if o["op"] not in ("heading", "skip", "unknown")},
                      key=lambda n: (bulk()[n]["fecha_boletin"], n))
        if not credits and state == versions[-1]["state"]:
            continue  # nothing in force changed that day (only headings or superseded instructions)
        b = F.cached(F.norma_url(nids[0]))
        versions.append({"from": day, "source_url": F.norma_url(nids[0]), "sha256": hashlib.sha256(b).hexdigest(),
                         "state": {k: dict(v) for k, v in state.items()}, "credits": credits,
                         "laws": [law_key(n) for n in nids]})
    # today's official text: InfoLEG's texto actualizado
    if act.get("texact"):
        T, turl, tsha = act_lines(act["id"], "texact.htm", act["start"], act["end"])
        tex_all = split_units(T, width=width, transitorias=act.get("transitorias", False))
        tex = {k: u for k, u in tex_all.items() if body_of(u) and not repealed_in_texact(u)}
        report["texact"] = {"url": turl, "sha256": tsha}
        final = versions[-1]["state"]
        for k in sorted(set(final) | set(tex)):
            a, t = body_of(final.get(k)), body_of(tex.get(k))
            for plist in patches.values():  # a vetoed word InfoLEG leaves in its text with a note
                for pk, pat, rp in plist:
                    if pk == k:
                        t = [re.sub(pat, rp, l) for l in t]
            if a == t:
                continue
            if not a or not t:
                report["mismatches"].append(f"{k}: {'only in texact' if t else 'only in the replay'}")
                continue
            last = max(i for i, v in enumerate(versions) if i == 0 or k in v["credits"])
            named = {int(x) for n in tex[k]["notes"] for x in H.LINK_RE.findall(n)}
            if loose(a) != loose(t):
                if k in act.get("transcription", {}):
                    report["transcription"].append(k)
                elif k not in worded and act.get("base_from_texact") and all(
                        re.match(r"^\(?\s*(?:Cap[ií]tulo|T[ií]tulo|R[uú]brica|Ep[ií]grafe|Denominaci|Art[ií]culo \S+ renumerado)",
                                 H.strip_links(n), re.I) for n in tex[k]["notes"]):
                    last = 0  # from the first version, under the article's earlier numbers
                    # never amended since the base text (no change replayed, and InfoLEG's consolidated text names
                    # no norm for it): InfoLEG's two transcriptions of the same words differ; take the consolidated one
                    ratio = difflib.SequenceMatcher(None, loose(a).split(), loose(t).split(), autojunk=False).ratio()
                    report["transcription"].append(f"{k} ({ratio:.2f})")
                else:
                    # InfoLEG's consolidated text gives the article as left by the last norm its note names; if the
                    # replay's last change to it was by that norm, take InfoLEG's wording from that change on
                    lastlaws = set(versions[last]["credits"].get(k, [])) if last else set()
                    if last and any(law_key(n) in lastlaws for n in named):
                        report["reconciled"].append(f"{k} ({', '.join(sorted(lastlaws))})")
                    else:
                        report["mismatches"].append(f"{k}: words differ from texact")
                        continue
            else:
                report["typography"].append(k)
            # same words (or a known InfoLEG transcription error in norma.htm): take texact's wording from the
            # version in which the unit last changed onwards, so today's file is the official consolidated text
            cur = k
            for i in range(len(versions) - 1, last - 1, -1):
                if cur in versions[i]["state"]:
                    versions[i]["state"][cur] = dict(versions[i]["state"][cur], body=list(t))
                for (vi, a_, b_) in renames:
                    if vi == i and b_ == cur:
                        cur = a_
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
    "codigo-penal": {
        "first_day": "1985-01-16", "first_law": None, "earlier_ids": [16546, 38033], "base_published": "1985-01-16",
        "base_from_texact": True,
        # InfoLEG's transcription of the texto ordenado heads art. 22 bis "Artículo 20 bis" (art. 20 bis is earlier)
        "base_fixes": [(r"^Artículo 20 bis\. - (Si el hecho ha sido cometido con ánimo de lucro)", r"Artículo 22 bis. - \1"),
                       # it writes "144 tercero", "144 cuarto" for 144 ter, 144 quater (InfoLEG's consolidated text keeps "144 quinto")
                       (r"^Artículo 144 tercero\.", "Artículo 144 ter."), (r"^Artículo 144 cuarto\.", "Artículo 144 quater.")],
        "overrides": {
            # Leyes 26.733 and 26.734 (both B.O. 2011-12-28) each added an art. 306 and renumbered the closing
            # articles 306-308; Decreto 169/2012 (B.O. 2012-02-06) fixed the numbering: 26.734's new article is 306,
            # 26.733's arts. 306-312 are 307-313, and the closing articles are 314-316 (InfoLEG follows it)
            (192139, 3): [{"op": "insert", "keys": ["art-307"]}], (192139, 4): [{"op": "insert", "keys": ["art-308"]}],
            (192139, 5): [{"op": "insert", "keys": ["art-309"]}], (192139, 6): [{"op": "insert", "keys": ["art-310"]}],
            (192139, 7): [{"op": "insert", "keys": ["art-311"]}], (192139, 8): [{"op": "insert", "keys": ["art-312"]}],
            (192139, 9): [{"op": "insert", "keys": ["art-313"]}],
            (192139, 10): [{"op": "renumber", "pairs": [("art-306", "art-314"), ("art-307", "art-315"),
                                                         ("art-308", "art-316")], "order": -1}],
            (192137, 4): [{"op": "skip"}],
            # Decreto 1059/2002 vetoed ("observó") art. 4 of Ley 25.602, which would have added art. 174 bis
            (75212, 4): [{"op": "skip"}],
            **{(193841, n): [{"op": "skip"}] for n in range(1, 9)},
        },
        "patches": {
            # Decreto 14/2021 vetoed ("observó") the word "integral" after "salud" in art. 86 inc. 2 as written by Ley 27.610
            346231: [("art-086", r"\bsalud integral\b", "salud")],
        },
        "note": ("The Código Penal (Ley 11.179 of 1921) in the texto ordenado approved by Decreto 3992/1984 (B.O. "
                 "1985-01-16), the oldest full text of the code as amended that InfoLEG publishes. A texto ordenado "
                 "changes no law; this version is dated by its publication. The amendments of 1921-1984 are in it but "
                 "are not shown one by one.")},
}


ACT_SETUP["ley-20744"] = {
    "first_day": "1976-05-21", "first_law": None, "earlier_ids": [25552, 229909], "base_published": "1976-05-21",
    "base_from_texact": True,
    # Decreto 773/1996 repeals Decreto 1477/1989, which had added an art. 105 bis; that decree is not replayed (InfoLEG
    # does not list it as amending the act), so the repeal has nothing to remove here
    "overrides": {(37882, 1): [{"op": "skip"}]},
    "note": ("The Ley de Contrato de Trabajo (Ley 20.744 of 1974, as amended by Ley 21.297) in the texto ordenado approved "
             "by Decreto 390/1976 (B.O. 1976-05-21), the oldest full text of the act as amended that InfoLEG publishes. A "
             "texto ordenado changes no law; this version is dated by its publication."),
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
        if act["first_law"] and act["first_law"] not in laws:
            laws[act["first_law"]] = law_entry(act["id"])
        for nid in act.get("earlier_ids", []):
            laws[law_key(nid)] = law_entry(nid)
        r = replay(act)
        reports.append(r["report"])
        amenders_used |= set(r["report"]["nids"])
        for nid in r["report"]["nids"]:
            laws[law_key(nid)] = law_entry(nid)
        for st in act.get("steps", []):
            laws[law_key(st["nid"])]["note"] = st["note"]
        for nid in r["report"].get("fines_nids", []):
            laws[law_key(nid)]["note"] = (
                "Fixed new minimum and maximum amounts for the fines of the articles credited here, without rewriting "
                "them. InfoLEG's consolidated text writes in only the amounts in force today, so the words change "
                "only where this is the last norm its notes name for the article.")
        versions = []
        for i, v in enumerate(r["versions"]):
            out = {"from": v["from"], "source_url": v["source_url"], "sha256": v["sha256"]}
            if i == 0:
                out["units"] = {k: unit_out(u) for k, u in sorted(v["state"].items())}
            else:
                # SCHEMA "Large acts": only what differs from the version before ({key: unit, or null to remove})
                pv = r["versions"][i - 1]["state"]
                out["changes"] = {k: (unit_out(v["state"][k]) if k in v["state"] else None)
                                  for k in sorted(set(pv) | set(v["state"]))
                                  if (unit_out(pv[k]) if k in pv else None) != (unit_out(v["state"][k]) if k in v["state"] else None)}
            out["credits"] = {}
            if i == 0:
                out["note"] = act["note"]
            else:
                prev = r["versions"][i - 1]["state"]
                for k in sorted(set(prev) | set(v["state"])):
                    if prev.get(k) != v["state"].get(k) or k in v["credits"]:
                        out["credits"][k] = v["credits"].get(k, [])
                        if not out["credits"][k]:
                            del out["credits"][k]  # unexplained: committed by the publisher
                if len(v["laws"]) > 1:
                    out["note"] = "Source of this version: " + ", ".join(laws[l]["label"] for l in v["laws"]) + "."
            versions.append(out)
        acts_out.append({"slug": act["slug"], "short": act["short"], "title": act["title"],
                         "url": F.norma_url(act["id"], "texact.htm" if act.get("texact") else "norma.htm"),
                         "first_law": act["first_law"],
                         "earlier_laws": act.get("earlier_laws", []) + [law_key(n) for n in act.get("earlier_ids", [])],
                         "versions": versions})
    used = {act["first_law"] for act in acts_out if act["first_law"]} | {l for act in acts_out for l in act["earlier_laws"]} | \
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
    for r in reports:
        if r["act"] == "ley-20744":
            decisions += [
                "Ley de Contrato de Trabajo: InfoLEG's text of Ley 20.744 itself is the act of 1974; the history starts at the texto ordenado approved by Decreto 390/1976 (B.O. 1976-05-21), the oldest full text of the act as amended on InfoLEG, dated by its publication and committed by the publisher as the oldest version available. Every later law or decree InfoLEG names in the consolidated text (its notes and its \"Antecedentes Normativos\"), or lists as modifying the act, is replayed.",
                f"Ley de Contrato de Trabajo, InfoLEG's two transcriptions: {len(r['transcription'])} articles that no replayed norm changed and that the consolidated text shows with no amendment note differ from InfoLEG's transcription of the texto ordenado only by transcription and layout (word-level similarity in brackets, all 0.90 or more): {', '.join(r['transcription'])}. Their consolidated wording is used from the first version.",
                f"Ley de Contrato de Trabajo, partial changes: {len(r['reconciled'])} articles take InfoLEG's consolidated wording from the last norm its note names ({', '.join(r['reconciled'])}).",
                "Ley de Contrato de Trabajo, taken from InfoLEG's notes: " + "; ".join(r["from_notes"]) + ". Ley 24.522 (Concursos y Quiebras) is not served by InfoLEG as text.",
                "Ley de Contrato de Trabajo: Ley 24.576 (1995) added a Chapter VIII to Title II with unnumbered articles (\"Artículo : …\", numbering left to the Executive) and Ley 27.802 (2026) repealed that chapter; neither is shown, because the articles have no numbers to file them under. InfoLEG marks art. 89 as repealed with that chapter, and the record follows it. Decreto 773/1996 repealed Decreto 1477/1989 (an art. 105 bis), which InfoLEG does not list as amending the act; neither is shown.",
                "Ley de Contrato de Trabajo: court rulings on the labour chapter of DNU 70/2023 are not modelled; the record follows InfoLEG's consolidated text, in which Ley 27.742 (2024) and Ley 27.802 (2026) later rewrote most of the same articles.",
            ]
        if r["act"] != "codigo-penal":
            continue
        short = lambda xs: ", ".join(x.split(" ")[0].replace("art-", "").lstrip("0").replace("-", " ") for x in xs)
        decisions += [
            "Código Penal: InfoLEG's text of the code itself (norma.htm of Ley 11.179) is the code of 1921, and the history from 1921 to 1984 runs through de facto laws and restorations it does not publish as texts. The history starts at the texto ordenado approved by Decreto 3992/1984 (B.O. 1985-01-16), the oldest full text of the code as amended on InfoLEG, dated by its publication and committed by the publisher as the oldest version available. Every later norm that InfoLEG names in the consolidated text's notes, or lists as modifying the code, and that is a law or decree published after the texto ordenado, is replayed.",
            f"Código Penal, InfoLEG's two transcriptions: {len(r['transcription'])} articles that no replayed norm changed and that InfoLEG's consolidated text shows with no amendment note differ from InfoLEG's transcription of the texto ordenado only by transcription (word-level similarity in brackets): {', '.join(r['transcription'])}. Their consolidated wording is used from the first version. InfoLEG's transcription of the texto ordenado also heads art. 22 bis \"Artículo 20 bis\" and writes \"144 tercero\", \"144 cuarto\" for arts. 144 ter and 144 quater; those headings are corrected.",
            f"Código Penal, partial changes: where a norm replaced or added an inciso or a paragraph, the replay places it in the article; InfoLEG's consolidated wording of the article is then used from the version of the last norm its note names, when that is the last norm the replay applied to it ({len(r['reconciled'])} articles: {', '.join(r['reconciled'])}). Earlier versions of those articles carry the wording the replay built. Where an instruction gives only an inciso's number (\"Incorpórase como inciso 10 …\") the number is written at the start of the line.",
            "Código Penal, fines: Leyes 23.479 (1987), 23.974 (1991) and 24.286 (1994) fixed new minimum and maximum amounts for the fines of listed articles without rewriting them. Each is credited to the articles it lists in a commit with no words changed; InfoLEG's consolidated text writes in only the amounts of Ley 24.286, which appear from that law's commit in the articles whose last note names it.",
            "Código Penal, norms whose text InfoLEG does not serve (\"No se pudo acceder al archivo solicitado\"): " + "; ".join(r["from_notes"]) + ". In-force dates use the default rule.",
            "Código Penal, numbering in 2012: Leyes 26.733 and 26.734 (both B.O. 2011-12-28) each added an art. 306 and renumbered the closing articles; Decreto 169/2012 (B.O. 2012-02-06) fixed the numbering, which InfoLEG follows. The replay applies that numbering from the two laws' own day: 26.734's article is 306, 26.733's arts. 306 to 312 are 307 to 313, and the closing articles 306 to 308 become 314 to 316 (credited to Ley 26.733 art. 10, as InfoLEG's notes do). Decreto 169/2012 itself changes no words and gets no commit.",
            "Código Penal, vetoes: Decreto 1059/2002 vetoed art. 4 of Ley 25.602 (an art. 174 bis that never took effect); Decreto 14/2021 vetoed the word \"integral\" after \"salud\" in art. 86 inc. 2 as written by Ley 27.610. Both are applied to the laws' texts. Ley 24.390 art. 8 (\"Modifícase el artículo 24 … para los casos comprendidos en esta ley\") gives no new words and is not a change to the text.",
            f"Código Penal, headings: {len(r['headings'])} instructions change only the name of a book, title or chapter, or are superseded; headings are not kept, so they have no commit. They are listed in the replay report of tools/parse.py.",
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
