"""Batch 10 of the Argentine record: writes corpus.d/92-batch10.json from the InfoLEG cache only.

    python -X utf8 batch10/parse_batch10.py            # writes ../corpus.d/92-batch10.json (atomically)
    python -X utf8 batch10/parse_batch10.py report     # replay report per act
    python -X utf8 batch10/parse_batch10.py --dry      # writes batch10/.tmp/92-batch10.json instead

It reuses the replay engine of ../parse.py and the batch-4/5 helpers (imported, not copied): the act's text as enacted
(norma.htm), every amending norm's own text replayed in order of entry into force, and the result checked against
InfoLEG's consolidated text (texact.htm). This file adds only the acts' registry entries and set-up, and the decisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "batch4"))
sys.path.insert(0, str(ROOT / "batch8"))
import parse as P  # noqa: E402
import common_batches as C  # noqa: E402

PART = ROOT / "corpus.d" / "92-batch10.json"
TAG = "Batch 10"

ACTS = [
    {
        "slug": "ley-25871",
        "short": "LM",
        "id": 92016,
        "title": "Ley 25.871 de Migraciones",
        "start": r"^TITULO PRELIMINAR$",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?25\.?871|[Ll]ey\s+de\s+Migraciones)",
    },
    {
        "slug": "ley-23737",
        "short": "LE",
        "id": 138,
        "title": "Ley 23.737 de Tenencia y Tráfico de Estupefacientes",
        "start": r"^Art[ií]culo 1\s*[°º]\s*-\s*Reempl",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?23\.?737)",
    },
    {
        "slug": "ley-23660",
        "short": "LOS",
        "id": 62,
        "title": "Ley 23.660 de Obras Sociales",
        "start": r"^Art(?:\.|[ií]culo)\s*1\s*[°º]\s*-\s*Quedan comprendidos",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?23\.?660)",
    },
    {
        "slug": "ley-24013",
        "short": "LNE",
        "id": 412,
        "title": "Ley 24.013 Nacional de Empleo",
        "start": r"^TITULO I$",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?24\.?013|[Ll]ey\s+Nacional\s+de\s+Empleo)",
    },
]

SETUP = {
    "ley-25871": {
        "first_day": "2004-01-21", "first_law": "ley-25871", "base_published": "2004-01-21",
        # DNU 138/2021 repealed DNU 70/2017 and (art. 2) restored the text it had changed; InfoLEG's consolidated
        # text no longer links it
        "extra_amenders": [347595],
        "overrides": {
            (271245, 9): [],  # a chapter heading (Capítulo I bis of Título V): headings are not kept
            (271245, 18): [{"op": "insert", "keys": ["art-069-nonies"], "label": "Art. 69 nonies"}],
            (271245, 19): [{"op": "insert", "keys": ["art-069-decies"], "label": "Art. 69 decies"}],
            (271245, 20): [{"op": "insert", "keys": ["art-069-undecies"], "label": "Art. 69 undecies"}],
            (347595, 1): [],  # "Derógase el Decreto N° 70 …": the restoration is art. 2
            (347595, 2): [{"op": "restore", "undoes": "decreto-70-2017", "keys": [
                "art-020", "art-020-bis", "art-029", "art-054", "art-062", "art-062-bis", "art-063", "art-069",
                "art-069-bis", "art-069-ter", "art-069-quater", "art-069-quinquies", "art-069-sexies", "art-069-septies",
                "art-069-octies", "art-069-nonies", "art-069-decies", "art-069-undecies", "art-070", "art-074-bis",
                "art-082", "art-086", "art-089-bis", "art-090"]}],
            # inciso ñ) after inciso n) ("ñ" has no letter before it in parse.apply_lines)
            (413297, 6): [{"op": "lines", "action": "insert", "keys": ["art-023"], "after_line": r"^n\) "}],
        },
        "note": ("Ley 25.871 as enacted (sancionada 2003-12-17, promulgada de hecho 2004-01-20, B.O. 2004-01-21). Art. "
                 "122: \"La presente ley entrará en vigencia a partir de su publicación\"."),
    },
    "ley-23737": {
        "first_day": None, "first_law": "ley-23737", "base_published": "1989-10-11",
        # articles never amended whose words InfoLEG transcribes differently in norma.htm and texact.htm
        "base_from_texact": True,
        "overrides": {
            # Ley 24.424 art. 9 spells the new article "31 quinques"
            (800, 9): [{"op": "insert", "keys": ["art-031-quinquies"], "label": "Art. 31 quinquies"}],
            # Ley 27.319 art. 19 ("Deróguense los artículos 31 bis … 33 bis de la ley 23.737")
            (268004, 19): [{"op": "repeal", "keys": ["art-031-bis", "art-031-ter", "art-031-quater", "art-031-quinquies",
                                                     "art-031-sexies", "art-033", "art-033-bis"]}],
        },
        "note": ("Ley 23.737 as enacted (sancionada 1989-09-21, promulgada de hecho 1989-10-10, B.O. 1989-10-11). No "
                 "vigencia clause: in force from the ninth day after publication (Código Civil art. 2)."),
    },
    "ley-23660": {
        "base_from_texact": True,
        "first_day": None, "first_law": "ley-23660", "base_published": "1989-01-20",
        "note": ("Ley 23.660 as enacted (sancionada 1988-12-29, promulgada 1989-01-05 by Decreto 15/1989, B.O. "
                 "1989-01-20). No vigencia clause: in force from the ninth day after publication (Código Civil art. 2)."),
    },
    "ley-24013": {
        "base_from_texact": True,
        # Decreto 2565/1991 arts. 2-7 ("Obsérvase …"), applied to the bill's text in norma.htm
        "vetoed": {"art-032": None, "art-147": None, "art-148": None,
                   "art-145": r"^(?:3\. Una contribución del medio|4 Un aporte del medio)",
                   "art-150": r"^El pago de las prestaciones, la recaudación de los aportes",
                   "art-152": r"^Dicha prestación se financiará con los recursos"},
        # the epigraph of art. 153, printed after art. 152; InfoLEG's consolidated text has none
        "drop_lines": [r"^Indemnización por despido injustificado\.$"],
        # the second paragraph of art. 112: InfoLEG's consolidated text writes "90" where norma.htm has "noventa (90)"
        "transcription": {"art-112": "noventa (90) / 90 in the second paragraph", "art-152": "sesenta (60), noventa (90) / 60, 90"},
        "overrides": {
            # Ley 25.013 art. 21: "Deróganse los artículos: 18, inciso b, 31 última parte, 28 a 40 y 43 a 65 de la
            # Ley Nº 24.013" (art. 32 was vetoed and never in force; "31 última parte" is its second sentence)
            (53159, 21): [{"op": "lines", "action": "delete", "keys": ["art-018"], "items": ["b"]},
                          {"op": "lines", "action": "replace", "keys": ["art-031"], "paras": [1], "text": [
                              "Los contratos de trabajo que se celebren bajo las modalidades reguladas en este capítulo, "
                              "salvo el contrato de trabajo de temporada, deberán instrumentarse por escrito y entregarse "
                              "copias al trabajador y a la asociación sindical que lo represente, en el plazo de treinta "
                              "(30) días."]},
                          {"op": "repeal", "keys": ["art-%03d" % n for n in [28, 29, 30] + list(range(33, 41)) + list(range(43, 66))]}],
            # DNU 70/2023 art. 53 and Ley 27.742 art. 99: "Deróganse los artículos 8° a 17 y 120, inciso a)"
            (395521, 53): [{"op": "repeal", "keys": ["art-%03d" % n for n in range(8, 18)]},
                           {"op": "lines", "action": "delete", "keys": ["art-120"], "items": ["a"]}],
            (401266, 99): [{"op": "repeal", "keys": ["art-%03d" % n for n in range(8, 18)]},
                           {"op": "lines", "action": "delete", "keys": ["art-120"], "items": ["a"]}],
            # inciso i) of art. 114 (whose incisos read "a." to "h." since Decreto 90/2023), after inciso h.
            (395521, 64): [{"op": "lines", "action": "insert", "keys": ["art-114"], "after_line": r"^h\. No reiniciación",
                            "text": ["i) Extinción por mutuo acuerdo de las partes en los términos del artículo 241 de la Ley N° 20.744"]}],
            (423680, 99): [{"op": "lines", "action": "replace", "keys": ["art-114"], "items": ["i"]}],
        },
        "first_day": None, "first_law": "ley-24013", "base_published": "1991-12-17",
        "note": ("Ley 24.013 as promulgated in part by Decreto 2565/1991 (B.O. 1991-12-17). No vigencia clause: in force "
                 "from the ninth day after publication (Código Civil art. 2)."),
    },
}

IN_FORCE: dict[int, tuple[str, str]] = {
    379858: ("2023-06-01", "DNU 90/2023, art. 14: a partir del primer día del cuarto mes posterior a su publicación (B.O. 2023-02-24)"),
    401319: ("2024-08-01", "DNU 600/2024, art. 6: el primer día del mes siguiente al de su publicación (B.O. 2024-07-10)"),
}

# Ley 23.737 arts. 1-4, 35 and 38 enact articles of the Código Penal, Ley 10.903 and Ley 20.655 by quoting them
C.QUOTED["ley-23737"] = [("art-204", "art-001"), ("art-204-bis", "art-002"), ("art-204-ter", "art-003"),
                         ("art-204-quater", "art-004"), ("art-018-bis", "art-035")]
# Ley 20.655's art. 26 bis (quoted in art. 38); Ley 24.424 later gave Ley 23.737 an art. 26 bis of its own
C.QUOTED_BASE["ley-23737"] = [("art-026-bis", "art-038", "1995-01-18")]
C.RESTORES["decreto-138-2021"] = "decreto-70-2017"


def decisions(rep: dict) -> list[str]:
    return [
        f"{TAG} (corpus.d/92-batch10.json, built by tools/batch10/parse_batch10.py with the replay engine of tools/parse.py and the helpers of tools/batch8/common_batches.py and tools/batch4/parse_batch4.py): Leyes 25.871, 23.737, 23.660 and 24.013, each from InfoLEG's text as enacted (norma.htm), with every amending norm InfoLEG's consolidated text names replayed from that norm's own text and the result checked against texact.htm. Articles never amended whose words InfoLEG transcribes differently in norma.htm and texact.htm take the consolidated wording from the first version (listed as transcription below, with the share of words in common).",
        "Ley 25.871 (Migraciones): in force on publication, 2004-01-21 (art. 122). DNU 70/2017 (in force 2017-01-31, its art. 28) replaced or added arts. 20, 20 bis, 29, 54, 62, 62 bis, 63, 69 to 69 undecies, 70, 74 bis, 82, 86 and 89 bis and repealed art. 90; its art. 9 only adds a chapter heading (headings are not kept). DNU 138/2021 (in force on publication, 2021-03-05, art. 4) repealed DNU 70/2017 and in its art. 2 restored \"la vigencia de las normas modificadas, sustituidas o derogadas\" by it: those articles return to their earlier words (or go, if DNU 70/2017 had added them), credited to DNU 138/2021, which carries `restores`. InfoLEG's consolidated text no longer links DNU 138/2021; it is replayed from its own text. DNU 366/2025 art. 6 adds inciso ñ) to art. 23, placed after inciso n). Decreto 616/2010 is the act's reglamentación and changes none of its words. Arts. 69 nonies, decies and undecies are file names art-069-nonies, art-069-decies and art-069-undecies.",
        "Ley 23.737 (Estupefacientes): in force 1989-10-20 (B.O. 1989-10-11 + 9 days). Its arts. 1-4, 35, 38 and 40 enact articles of the Código Penal (204, 204 bis, 204 ter, 204 quater, 77), of Ley 10.903 (18 bis) and of Ley 20.655 (25, 26, 26 bis) by quoting them: the quoted articles are kept inside the act's own article, not as units of this act. Ley 24.424 (1995) gave the act an art. 26 bis of its own; Ley 20.655's quoted art. 26 bis stays in art. 38. Ley 24.424 art. 9 spells the new article \"31 quinques\" (file art-031-quinquies). Ley 27.319 art. 19 (\"Deróguense los artículos 31 bis, 31 ter, 31 quáter, 31 quinquies, 31 sexies, 33 y 33 bis de la ley 23.737\") is applied as written. Ley 23.975 fixed the fines in pesos without rewriting them (InfoLEG's Nota) and repealed art. 45.",
        "Ley 23.660 (Obras Sociales): in force 1989-01-29 (B.O. 1989-01-20 + 9 days, no vigencia clause). Amendments by DNU 70/2023 to its labour-related articles follow InfoLEG's consolidated text, as for the other acts; court rulings that suspended parts of DNU 70/2023 are not modelled. DNU 600/2024 is in force 2024-08-01 (its art. 6: the first day of the month after publication).",
        "Ley 24.013 (Empleo), first version: the bill as promulgated by Decreto 2565/1991 (B.O. 1991-12-17), less what its arts. 2 to 7 vetoed: art. 32, points 3 and 4 of art. 145 inc. a), arts. 147 and 148, the second paragraph of art. 150 and the third paragraph of art. 152; in force 1991-12-26. The epigraph \"Indemnización por despido injustificado.\" printed after art. 152 is dropped as a heading. Ley 25.013 art. 21 repeals arts. 28 to 40 and 43 to 65, inciso b) of art. 18 and \"31 última parte\", read as the second sentence of art. 31. DNU 70/2023 art. 53 repealed arts. 8 to 17 and inciso a) of art. 120 (in force 2023-12-30, default rule); Ley 27.742 art. 99 repealed the same provisions again and changes no words; InfoLEG's note on art. 120 names Ley 27.742. DNU 90/2023 is in force 2023-06-01 (its art. 14: the first day of the fourth month after publication); it rewrote art. 114, whose incisos read \"a.\" to \"h.\", so inciso i) (DNU 70/2023 art. 64, enacted again in fuller words by Ley 27.802 art. 99) is placed after inciso h. The second paragraph of art. 112 and arts. 152 differ between norma.htm (\"noventa (90)\", \"sesenta (60)\") and texact.htm (\"90\", \"60\"): InfoLEG's consolidated wording is used from the article's last change (art. 112: DNU 90/2023; art. 152: the first version).",
    ]


def main(argv: list[str]) -> None:
    C.run(argv, ACTS, SETUP, IN_FORCE, PART, HERE, TAG, decisions)


if __name__ == "__main__":
    main(sys.argv[1:])
