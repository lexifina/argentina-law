"""Batch 11 of the Argentine record: writes corpus.d/93-batch11.json from the InfoLEG cache only.

    python -X utf8 batch11/parse_batch11.py            # writes ../corpus.d/93-batch11.json (atomically)
    python -X utf8 batch11/parse_batch11.py report     # replay report per act
    python -X utf8 batch11/parse_batch11.py --dry      # writes batch11/.tmp/93-batch11.json instead
    python -X utf8 batch11/parse_batch11.py report ley-26522    # one act only, nothing written

It reuses the replay engine of ../parse.py through ../batch8/common_batches.py: the act's text as enacted
(norma.htm), every amending norm's own text replayed in order of entry into force, and the result checked against
InfoLEG's consolidated text (texact.htm). This file adds only the acts' registry entries and set-up, and the decisions.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "batch8"))
import common_batches as C  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402

PART = ROOT / "corpus.d" / "93-batch11.json"
TAG = "Batch 11"

ACTS = [
    {
        "slug": "ley-26522", "short": "LSCA", "id": 158649,
        "title": "Ley 26.522 de Servicios de Comunicación Audiovisual",
        "start": r"^TITULO I$", "end": r"^DADA EN LA SALA", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?26\.?522|[Ll]ey\s+de\s+Servicios\s+de\s+Comunicaci[oó]n\s+Audiovisual)",
    },
    {
        "slug": "ley-25246", "short": "LEA", "id": 62977,
        "title": "Ley 25.246 de Encubrimiento y Lavado de Activos de Origen Delictivo",
        "start": r"^CAPITULO I$", "end": r"^(?:DADA EN LA SALA|-\s*REGISTRADO BAJO)", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?25\.?246)",
    },
    {
        "slug": "ley-11723", "short": "LPI", "id": 42755,
        "title": "Ley 11.723 de Propiedad Intelectual",
        "start": r"^Art[ií]culo 1\s*°", "end": r"^Dada en la Sala", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?11\.?723)",
    },
    {
        "slug": "ley-26831", "short": "LMC", "id": 206592,
        "title": "Ley 26.831 de Mercado de Capitales",
        "start": r"^TITULO PRELIMINAR$", "end": r"^DADA EN LA SALA", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?26\.?831|[Ll]ey\s+de\s+Mercado\s+de\s+Capitales)",
    },
]


# ---------------------------------------------------------------- Ley 26.522: the bill's notes and footnotes
# Ley 26.522 was published with the bill's explanatory notes ("NOTA artículo 34 …") after many articles and with
# numbered footnotes naming who proposed a wording ("propuestas55" … "55 Se han recibido múltiples aportes …").
# They are commentary on the bill, not provisions: they are left out of the record, on both InfoLEG pages alike.
FOOTREF = re.compile(r"(?<=[a-záéíóúñ)])\d{1,3}(?=[.:,;)]|\s|$)")


def _lsca_filter(L: list[str], page: str) -> list[str]:
    out, skip = [], False
    for raw in L:
        s = H.strip_links(raw)
        # a note ends at the next article heading or title heading; the notes quote foreign laws' articles in
        # lower case ("artículo 75. Cuantificación …"), which are not headings of this act
        if (P.ART_RE.match(s) and s[:1] == "A") or (P.MARKER_RE.match(s) and s[:1].isupper() and len(s) < 90
                                                     and not s.endswith(".")):
            skip = False
        elif re.match(r"^NOTA\s+art[ií]culos?\b", s, re.I) or re.match(r"^_{3,}\s*$", s):
            skip = True
        if skip:
            continue
        out.append(FOOTREF.sub("", raw) if not P.is_note(raw) else raw)
    return out


def _lea_filter(L: list[str], page: str) -> list[str]:
    """Ley 25.246's consolidated text prints the replaced expressions' notes inline at the end of the line, and one
    slip ("a lMinisterio …"); its own NOTE lines stay notes."""
    if page == "norma.htm":
        return L
    L = [re.sub(r"\s*\(Expresi[oó]n\s+\"[^\"]*\",?\s+sustituida\b.*\)\s*$", "", l) for l in L]
    return [l.replace("presentar a lMinisterio de Hacienda y Finanzas Públicas ,", "presentar al Ministerio de Hacienda y Finanzas Públicas,")
            for l in L]


C.LINE_FILTERS[158649] = _lsca_filter
C.LINE_FILTERS[62977] = _lea_filter
# Ley 25.246 arts. 2 to 4 enact arts. 277 to 279 of the Código Penal by quoting them: kept inside the act's article
C.QUOTED["ley-25246"] = [("art-277", "art-002"), ("art-278", "art-003"), ("art-279", "art-004")]


def _quoted_text(nid: int, art: int, item: str) -> list[str]:
    """The new words of item `item` of article `art` of norm `nid` when given inline in quotes
    ('f) Sustitúyese el inciso a) … por el siguiente: "a) Aportes …".')."""
    lines = next(ls for n, ls in P.amender_articles(nid) if n == art)
    line = next(H.strip_links(l) for l in lines if H.strip_links(l).startswith(item + ")"))
    return [re.search(r'por el siguiente:\s*"(.*)"\.?$', line).group(1)]


def _sub(*pairs):
    return [(re.escape(a), b) for a, b in pairs]


MIN_JUS = "Ministerio de Justicia y Derechos Humanos"
MIN_HAC = "Ministerio de Hacienda y Finanzas Públicas"

# Ley 27.440, art. 218: in Ley 26.831 "persona de existencia visible"/"persona física" is to be read "persona
# humana" and the Ministry of Economy (any of its names) "Ministerio de Finanzas"; InfoLEG's consolidated text of
# Ley 26.831 applies it to the words (for Ley 25.246 InfoLEG prints it only as a note, and so does this record).
LMC_WORDS = [
    (r"\bpersonas de existencia visible\b", "personas humanas"), (r"\bpersona de existencia visible\b", "persona humana"),
    (r"\bpersonas físicas\b", "personas humanas"), (r"\bpersona física\b", "persona humana"),
    (r"\bMinisterio de Economía y Finanzas Públicas\b", "Ministerio de Finanzas"),
    (r"\bMinisterio de Economía y Producción\b", "Ministerio de Finanzas"),
    (r"\bMinisterio de Economía\b", "Ministerio de Finanzas"),
]


def _keys_with(nid: int, start: str, end: str, pats, pages=("norma.htm", "texact.htm")) -> list[str]:
    keys = []
    for page in pages:
        T, _, _ = C.act_lines(nid, page, start, end)
        for k, u in P.split_units(T, width=3).items():
            if k not in keys and any(re.search(p, " ".join(u["body"])) for p, _ in pats):
                keys.append(k)
    return keys


LPI_WORDS = [(r"\bdiscos fonográficos\b", "fonogramas")]


def _inline_after(nid: int, art: int, rx: str) -> str:
    line = H.strip_links(next(ls for n, ls in P.amender_articles(nid) if n == art)[0])
    return re.split(rx, line, maxsplit=1)[1].strip().rstrip('"').strip()


def _lpi_36() -> list[str]:
    lines = [H.strip_links(l) for l in next(ls for n, ls in P.amender_articles(85126) if n == 1)]
    first = re.split(r'siguiente forma:\s*"\s*Art\.\s*36\.\s*-+\s*', lines[0], maxsplit=1)[1]
    return [first] + [l.strip().rstrip('"').strip() for l in lines[1:] if l.strip()]


def _lpi_filter(L: list[str], page: str) -> list[str]:
    """Ley 11.723's consolidated text prints some notes inline at the end of a line or as a line of the article."""
    if page == "norma.htm":
        return L
    L = [re.sub(r"\s*\((?:P[aá]rrafo|[UÚ]ltima parte)[^()]*(?:incorporad|sustituid)[^()]*\)\.?\s*$", "", l) for l in L]
    return [l for l in L if not re.match(r"^\(Por art\. 1° inciso 12 de la Ley N° 24\.286\b.*\)\.?$", H.strip_links(l))]


C.LINE_FILTERS[42755] = _lpi_filter


def _tex_line(nid: int, key: str, i: int) -> str:
    a = next(a for a in ACTS if a["id"] == nid)
    T, _, _ = C.act_lines(nid, "texact.htm", a["start"], a["end"])
    return P.body_of(P.split_units(T, width=3)[key])[i]


SETUP = {
    "ley-26522": {
        "first_day": None, "first_law": "ley-26522", "base_published": "2009-10-10",
        "overrides": {
            # Ley 27.078 art. 88: "Sustitúyese el Capítulo III del Título II de la ley 26.522" (arts. 18 and 19)
            (239771, 88): [{"op": "articles", "action": "replace"}],
            # DNU 267/2015 art. 22 repeals four definitions of art. 4 (InfoLEG keeps the defined term, with a note,
            # and its words removed), art. 31 inc. c), art. 43, art. 44 inc. e), art. 48, the second paragraph of
            # art. 55 and arts. 73, 158 and 161
            (257461, 22): [
                {"op": "lines", "action": "drop_match", "keys": ["art-004"], "patterns": [
                    r"^Radiodifusión por suscripción(?: con uso de espectro radioeléctrico| mediante vínculo físico)?:",
                    r"^Servicio de radiodifusión televisiva a pedido o a demanda:"]},
                {"op": "lines", "action": "delete", "keys": ["art-031"], "items": ["c"]},
                {"op": "repeal", "keys": ["art-043"]},
                {"op": "lines", "action": "delete", "keys": ["art-044"], "items": ["e"]},
                {"op": "repeal", "keys": ["art-048"]},
                {"op": "lines", "action": "delete", "keys": ["art-055"], "paras": [2]},
                {"op": "repeal", "keys": ["art-073", "art-158", "art-161"]},
            ],
            # Ley 27.802 art. 215: "Deróganse, a partir del 1º de enero de 2028, los incisos a) y c) del artículo 97
            # y el inciso a) del artículo 136" (a change still to come: the future branch)
            (423680, 215): [
                {"op": "lines", "action": "delete", "keys": ["art-097"], "items": ["a", "c"], "at": "2028-01-01"},
                {"op": "lines", "action": "delete", "keys": ["art-136"], "items": ["a"], "at": "2028-01-01"},
            ],
        },
        "note": "Ley 26.522 as enacted (sancionada and promulgada 2009-10-10, B.O. 2009-10-10). No vigencia clause: in force from the ninth day after publication (Código Civil art. 2).",
    },
    "ley-25246": {
        "first_day": None, "first_law": "ley-25246", "base_published": "2000-05-10",
        # Decreto 370/2000 promulgated the law with these words observed (printed in bold by InfoLEG)
        "vetoed_words": [
            ("art-278", r"^2\) El que por temeridad o imprudencia grave.*$", ""),
            ("art-279", r"\s*No será punible el encubrimiento de un delito de esa índole, cuando se cometiere por imprudencia, en el sentido del artículo 278, inciso 2;?", ""),
            ("art-279", r"\s*En el caso del artículo 278, inciso 2, la pena será de uno \(1\) a cinco \(5\) años de inhabilitación;?", ""),
            ("art-010", r" y percibirán una remuneración equivalente a la de un Juez de Primera Instancia\.", "."),
            ("art-010", r" de la Cámara Nacional de Apelaciones en lo Criminal y Correccional,", ","),
            ("art-012", r"la Inspección General de Justicia, ", ""),
            ("art-023", r" en el sentido del artículo 278, inc\. 2\) del Código Penal,", ","),
            ("art-028", r"^Cuando corresponda la competencia federal o nacional el Fiscal", "El Fiscal"),
            ("art-028", r"; en los restantes casos de igual modo actuarán los funcionarios del Ministerio Fiscal que corresponda\.", "."),
            ("art-028", r", o en su caso, el de la provincia respectiva\.", "."),
        ],
        "overrides": {
            # Decreto 1500/2001 art. 2: inciso c) of art. 9 with its closing paragraph
            (70091, 2): [{"op": "lines", "action": "replace", "keys": ["art-009"], "block": (r"^c\) Los nombres", None),
                          "to_end": True}],
            # Ley 27.260 art. 92: expressions replaced in arts. 5 and 9, and art. 27 inc. a)
            (263691, 92): [
                {"op": "lines", "action": "words", "keys": ["art-005"], "words": _sub(
                    (f"en jurisdicción del {MIN_JUS} de la Nación", f"en jurisdicción del {MIN_HAC} de la Nación"))},
                {"op": "lines", "action": "words", "keys": ["art-009"], "words": _sub(
                    (f"a propuesta del {MIN_JUS}", f"a propuesta del {MIN_HAC} de la Nación"),
                    (f"en el ámbito del {MIN_JUS}", f"en el ámbito del {MIN_HAC} de la Nación"),
                    (f"presentar al {MIN_JUS}", f"presentar al {MIN_HAC}"),
                    (f"el {MIN_JUS} elevará", f"el {MIN_HAC} elevará"),
                    # the law reads "el Ministro de Justicia …"; InfoLEG applies inc. e) to it all the same
                    ("el Ministro de Justicia y Derechos Humanos elevará", f"el {MIN_HAC} elevará"))},
                {"op": "lines", "action": "replace", "keys": ["art-027"], "items": ["a"],
                 "text": _quoted_text(263691, 92, "f")},
            ],
            # Decreto 2/2017 art. 5
            (270227, 5): [{"op": "lines", "action": "words", "keys": ["art-005"], "words": _sub(
                (f"en jurisdicción del {MIN_HAC} de la Nación", "en jurisdicción del Ministerio de Finanzas"))}],
            # DNU 27/2018 art. 163 and Ley 27.446 art. 12: inciso c) of art. 21 (the article's last item) with the
            # paragraphs that follow it
            (305736, 163): [{"op": "lines", "action": "replace", "keys": ["art-021"], "block": (r"^c[.)] Abstenerse", None),
                             "to_end": True}],
            (311583, 12): [{"op": "lines", "action": "replace", "keys": ["art-021"], "block": (r"^c[.)] Abstenerse", None),
                            "to_end": True}],
            # Ley 27.446 art. 10 repeals art. 13 inc. 4, which DNU 27/2018 art. 161 had already repealed
            (311583, 10): [{"op": "skip"}],
            # Ley 27.739 arts. 5 and 7: observed by Decreto 254/2024 (printed in bold on InfoLEG)
            (397355, 5): [{"op": "skip"}], (397355, 7): [{"op": "skip"}],
        },
        "note": "Ley 25.246 as promulgated in part by Decreto 370/2000 (B.O. 2000-05-10).",
    },
    "ley-11723": {
        "first_day": None, "first_law": "ley-11723", "base_published": "1933-09-30",
        "drop_lines": [r"^DISPOSICIONES TRANSITORIAS$"],
        "extra_amenders": [37242],          # Decreto-Ley 1.224/1958, art. 26: repeals arts. 69 and 70
        "note_only": {85122: r"12\.063"},  # Decreto-Ley 12.063/1957 (arts. 5 and 84): no text on InfoLEG
        # InfoLEG's 1933 transcription and its consolidated text differ in many small slips: an article no norm
        # changed takes the consolidated wording from the first version on (listed as transcription)
        "base_from_texact": True,
        # Decreto-Ley 12.063/1957 replaced arts. 5 and 84 (InfoLEG's "Antecedentes Normativos"); InfoLEG serves no
        # text of it and Ley 24.870 replaced both again in 1997: a commit with no change of words marks it
        "steps": [{"nid": 85122, "from": "1957-10-20", "units": [5, 84],
                   "note": "Decreto-Ley 12.063/1957 replaced arts. 5 and 84 of Ley 11.723; InfoLEG serves no text of it, so the wording it gave them (in force until Ley 24.870 replaced both in 1997) is not shown."}],
        "overrides": {
            # Decreto-Ley 1.224/1958, art. 26: "Derógase la Ley Nº 12.227 [y] los artículos 69 y 70 de la Ley Nº 11.723"
            (37242, 26): [{"op": "repeal", "keys": ["art-069", "art-070"]}],
            # Ley 17.753, art. 1: art. 36 replaced, its new text starting inline after "de la siguiente forma:"
            (85126, 1): [{"op": "replace", "keys": ["art-036"], "label": "Art. 36", "text": _lpi_36()}],
            # Ley 26.285, art. 1: "Incorpórase a la Ley Nº 11.723, artículo 36 in fine, el parágrafo siguiente"
            (132226, 1): [{"op": "lines", "action": "insert", "keys": ["art-036"], "paras": ["last"]}],
            # Ley 20.098, art. 1: the final paragraph of art. 36 (added in 1969 by Ley 18.453, whose text InfoLEG
            # does not serve) in the words of Ley 20.098, given inline after "como sigue:"
            (85127, 1): [{"op": "lines", "action": "insert", "keys": ["art-036"], "paras": ["last"],
                          "text": [_inline_after(85127, 1, r'como sigue:\s*"\s*')]}],
            # Ley 23.741, art. 1: "discos fonográficos" read "fonogramas" in the law; art. 2 adds art. 72 bis
            (142, 1): [{"op": "lines", "action": "words", "words": LPI_WORDS,
                        "keys": _keys_with(42755, r"^Art[ií]culo 1\s*°", r"^Dada en la Sala", LPI_WORDS, pages=("norma.htm",))}],
            (142, 2): [{"op": "insert", "keys": ["art-072-bis"], "label": "Art. 72 bis"}],
            # Leyes 23.974 and 24.286 fix the fines of arts. 73 and 74 (point 12 of their art. 1): the first in
            # australes, a credit with no change of words (as for the Código Penal); the second in pesos, written into
            # the articles by InfoLEG's consolidated text
            (373, 1): [{"op": "fines", "keys": ["art-073", "art-074"], "amount_note": True, "body": []}],
            (684, 1): [{"op": "lines", "action": "replace", "keys": ["art-073"], "paras": [1], "text": [_tex_line(42755, "art-073", 0)]},
                       {"op": "lines", "action": "replace", "keys": ["art-074"], "paras": [1], "text": [_tex_line(42755, "art-074", 0)]}],
            # Ley 25.036, art. 5: "Incorpórase como artículo 57, in fine, …": words added at the end of the article
            (54178, 5): [{"op": "lines", "action": "append_to", "keys": ["art-057"], "paras": ["last"],
                          "text_fix": [(r"^Artículo 57, in fine:\s*", "")]}],
        },
        "note": "Ley 11.723 as enacted (sancionada 1933-09-26, B.O. 1933-09-30). No vigencia clause: in force from the ninth day after publication (Código Civil art. 2).",
    },
    "ley-26831": {
        "first_day": "2013-01-27", "first_law": "ley-26831", "base_published": "2012-12-28",
        # the title of Chapter I of Title II, printed between arts. 27 and 28
        "drop_lines": [r"^Mercados\. Garantías\. Agentes de liquidación y compensación\.", r"^Tribunales arbitrales\.$"],
        "overrides": {
            (310084, 218): [{"op": "lines", "action": "words", "words": LMC_WORDS,
                             "keys": _keys_with(206592, r"^TITULO PRELIMINAR$", r"^DADA EN LA SALA", LMC_WORDS)}],
        },
        "note": ("Ley 26.831 as enacted (sancionada 2012-11-29, promulgada 2012-12-27, B.O. 2012-12-28). Art. 155: in "
                 "force \"a los treinta (30) días corridos de su publicación\", that is 2013-01-27."),
    },
}

IN_FORCE: dict[int, tuple[str, str]] = {
    273023: ("2017-09-29", "Decreto 206/2017, art. 4: entrará en vigencia el 29 de septiembre de 2017"),
    310413: ("2018-05-21", "Decreto 471/2018, art. 14: regirá a partir del 21 de mayo de 2018"),
    257461: ("pub", "DNU 267/2015, art. 34: regirán desde la fecha de su publicación en el Boletín Oficial"),
    85122: ("default", "Decreto-Ley 12.063/1957: its text is not on InfoLEG, so the default rule is used"),
    270227: ("2017-01-02", "Decreto 2/2017, art. 8: entra en vigencia a partir de la fecha de su dictado (2 de enero de 2017)"),
}


def decisions(rep: dict) -> list[str]:
    return [
        f"{TAG} (corpus.d/93-batch11.json, built by tools/batch11/parse_batch11.py with the replay engine of tools/parse.py and the helpers of tools/batch8/common_batches.py and tools/batch4/parse_batch4.py): Leyes 26.522, 25.246, 11.723 and 26.831, each from InfoLEG's text as enacted (norma.htm), with every amending norm InfoLEG's consolidated text names replayed from that norm's own text and the result checked against texact.htm. Articles never amended whose words InfoLEG transcribes differently in norma.htm and texact.htm take the consolidated wording from the first version (listed as transcription below, with the share of words in common).",
        "Vetoes printed in bold. When InfoLEG prints a norm with \"(Nota Infoleg: Los textos en negrita fueron observados …)\", the bold words were vetoed and never took effect; the replay reads the bold spans of the page. Ley 27.739 (B.O. 2024-03-15; Decreto 254/2024 observed parts of it): its arts. 5 and 7 (amending arts. 5 and 9 inc. g) of Ley 25.246) and its art. 40 (\"entrará en vigencia a los treinta (30) días corridos\") were vetoed, so Ley 27.739 is in force on the default day, 2024-03-24 (publication + 9 days), for every act it amends, including the Código Penal (whose record had used 2024-04-14 before this batch).",
        "Ley 26.522 (Servicios de Comunicación Audiovisual): in force 2009-10-19 (no vigencia clause). The law was published with the bill's explanatory notes (\"NOTA artículo N …\") after many articles and with numbered footnotes naming who proposed a wording (\"propuestas55\" … \"55 Se han recibido …\"). They are commentary on the bill, not provisions: notes, footnotes and footnote numbers are left out on both InfoLEG pages alike. Ley 27.078 art. 88 replaced Chapter III of Title II (arts. 18 and 19). DNU 267/2015 is in force on publication, 2016-01-04 (its art. 34); its art. 22 repealed four definitions of art. 4 (\"párrafos 34 a 36 y 40\": InfoLEG keeps each defined term as a bare line with a note; the record removes the definition line), art. 31 inc. c), art. 43, art. 44 inc. e), art. 48, the second paragraph of art. 55 and arts. 73, 158 and 161; its art. 32 repealed arts. 10, 11, 13, 14, 15 and 16. Ley 27.802 art. 215 repeals incisos a) and c) of art. 97 and inciso a) of art. 136 \"a partir del 1º de enero de 2028\": a future version, kept off the main branch until that day (today's text is checked against InfoLEG without it).",
        "Ley 25.246 (Encubrimiento y Lavado de Activos), first version: the law as promulgated in part by Decreto 370/2000, less the words it observed (bold on InfoLEG): art. 278 inc. 2) of the Código Penal as quoted in art. 3, two sentences of art. 279 as quoted in art. 4, the judge's salary and the court named in art. 10, \"la Inspección General de Justicia\" in art. 12, the reference to art. 278 inc. 2 in art. 23 inc. 2, and three phrases of art. 28 (\"Cuando corresponda la competencia federal o nacional\" opened the article; the record starts it at \"El Fiscal General\"). Its arts. 2 to 4 enact arts. 277 to 279 of the Código Penal by quoting them: the quoted articles are kept inside the act's own article (the vetoes apply to their words). Decreto 1500/2001 art. 2 replaced inciso c) of art. 9 with its closing paragraph. Ley 27.260 art. 92 incs. a) to e) replaced expressions naming the Ministerio de Justicia y Derechos Humanos in arts. 5 and 9 (art. 9 inc. g) reads \"el Ministro de Justicia\", which InfoLEG replaces all the same, and so does the record); inc. f) replaced art. 27 inc. a). Decreto 2/2017 art. 5 replaced the ministry in art. 5, in force on the day it was signed, 2017-01-02 (its art. 8). DNU 27/2018 art. 161 and Ley 27.446 art. 10 both repeal art. 13 inc. 4 (the second is a credit-free repetition); DNU 27/2018 art. 163 and Ley 27.446 art. 12 replace inciso c) of art. 21 with the paragraphs that follow it. Ley 27.440 art. 218 (\"persona humana\", \"Ministerio de Finanzas\") and DNU 8/2023 art. 14 (\"MINISTERIO DE JUSTICIA\") are reading rules that InfoLEG prints only as notes on this law; the record does the same.",
        "Ley 11.723 (Propiedad Intelectual): in force 1933-10-09 (B.O. 1933-09-30, no vigencia clause). The line \"DISPOSICIONES TRANSITORIAS\" before art. 84 is a heading (not kept). Decreto-Ley 12.063/1957 replaced arts. 5 and 84, but InfoLEG serves no text of it (only its record) and Ley 24.870 replaced both again in 1997: a commit with no change of words marks it on its default day, 1957-10-20, and the 1957-1997 wording of arts. 5 and 84 is not shown (the 1933 wording stays until 1997). Decreto-Ley 1.224/1958 art. 26 repealed arts. 69 and 70. Ley 17.753 (1968) replaced art. 36 (its new text begins on the instruction line). Ley 18.453 (1969) added a last paragraph to art. 36 and Ley 20.098 (1973) replaced that paragraph: InfoLEG serves no text of Ley 18.453, so the paragraph appears in 1973, in the words of Ley 20.098. Ley 26.285 (2007) added paragraphs at the end of art. 36; Ley 27.588 (2020) replaced the article. Art. 74 bis, added by Ley 17.567 (1968), replaced by Ley 21.338 (1976) and repealed by Ley 23.077 (1984), is not shown: InfoLEG serves the text of neither law. Ley 23.741 art. 1 replaced \"discos fonográficos\" by \"fonogramas\" throughout the law (its art. 2 adds art. 72 bis, which keeps \"discos fonográficos\" as InfoLEG prints it). The fines of arts. 73 and 74: Ley 23.974 (1991, australes) is a credit with no change of words, as for the Código Penal; Ley 24.286 (1994, pesos) is written into the articles as InfoLEG's consolidated text does. Ley 25.036 art. 5 (\"artículo 57, in fine\") adds a sentence at the end of art. 57.",
        "Ley 26.831 (Mercado de Capitales): in force 2013-01-27 (art. 155: thirty days after publication). The title of Chapter I of Title II, printed between arts. 27 and 28, is a heading (not kept); Ley 27.440 art. 46 renamed it. Ley 27.440 art. 218 (in force 2018-05-20, default rule) says that in Ley 26.831 \"persona de existencia visible\" and \"persona física\" are to be read \"persona humana\" and the Ministry of Economy (any of its names) \"Ministerio de Finanzas\"; InfoLEG's consolidated text of Ley 26.831 applies it to the words, and so does the record, on that day.",
    ]


def main(argv: list[str]) -> None:
    C.run(argv, ACTS, SETUP, IN_FORCE, PART, HERE, TAG, decisions)


if __name__ == "__main__":
    main(sys.argv[1:])
