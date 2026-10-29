"""Batch 9 of the Argentine record: writes corpus.d/91-batch9.json from the InfoLEG cache only.

    python -X utf8 batch9/parse_batch9.py            # writes ../corpus.d/91-batch9.json (atomically)
    python -X utf8 batch9/parse_batch9.py report     # replay report per act
    python -X utf8 batch9/parse_batch9.py --dry      # writes batch9/.tmp/91-batch9.json instead
    python -X utf8 batch9/parse_batch9.py report ley-23661    # one act only, nothing written

It reuses the replay engine of ../parse.py through ../batch8/common_batches.py: the act's text as enacted
(norma.htm), every amending norm's own text replayed in order of entry into force, and the result checked against
InfoLEG's consolidated text (texact.htm). This file adds only the acts' registry entries and set-up, and the decisions.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "batch8"))
import common_batches as C  # noqa: E402

PART = ROOT / "corpus.d" / "91-batch9.json"
TAG = "Batch 9"

ACTS = [
    {
        "slug": "ley-23661",
        "short": "SNSS",
        "id": 63,
        "title": "Ley 23.661 del Sistema Nacional del Seguro de Salud",
        "start": r"^CAPITULO I$",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?23\.?661)",
    },
    {
        "slug": "ley-17418",
        "short": "LS",
        "id": 39520,
        "title": "Ley 17.418 de Seguros",
        "start": r"^TITULO I$",
        "end": r"^(?:ONGANIA\.?$|Antecedentes Normativos)",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?17\.?418|[Ll]ey\s+de\s+Seguros)",
    },
    {
        "slug": "ley-27275", "short": "LAIP", "id": 265949,
        "title": "Ley 27.275 de Derecho de Acceso a la Información Pública",
        "start": r"^TÍTULO PRELIMINAR$", "end": r"^DADA EN LA SALA", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?27\.?275)",
    },
    {
        "slug": "ley-23592", "short": "LAD", "id": 20465,
        "title": "Ley 23.592 de Actos Discriminatorios",
        "start": r"^ART[IÍ]CULO 1\s*[°º]\s*\.?-?\s*Quien", "end": r"^DADA EN LA SALA", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?23\.?592)",
    },
    {
        "slug": "ley-25520", "short": "LIN", "id": 70496,
        "title": "Ley 25.520 de Inteligencia Nacional",
        "start": r"^T[ií]tulo I$", "end": r"^DADA EN LA SALA", "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?25\.?520|[Ll]ey\s+de\s+Inteligencia\s+Nacional)",
    },
]

SETUP = {
    "ley-23661": {
        "first_day": None, "first_law": "ley-23661", "base_published": "1989-01-20",
        "drop_lines": [r"^Disposiciones transitorias$"],  # chapter IX's title; split_units would stop splitting articles
        "note": ("Ley 23.661 as enacted (sancionada 1988-12-29, promulgada 1989-01-05, B.O. 1989-01-20). No vigencia "
                 "clause: in force from the ninth day after publication (Código Civil art. 2)."),
    },
    "ley-17418": {
        # art. 163: "regirá a partir de los seis meses de su promulgación" (promulgated 1967-08-30)
        "base_from_texact": True,
        "first_day": "1968-03-01", "first_law": "ley-17418", "base_published": "1967-09-06",
        "drop_lines": [r"^DISPOSICIONES FINALES Y TRANSITORIAS$"],
        "note": ("Ley 17.418 as enacted by the de facto government (30 August 1967, B.O. 1967-09-06). Art. 163: it "
                 "\"regirá a partir de los seis meses de su promulgación\", that is from 1 March 1968."),
    },
    "ley-27275": {"first_day": "2017-09-29", "first_law": "ley-27275", "base_published": "2016-09-29",
                  "note": "Ley 27.275 as enacted (B.O. 2016-09-29). Art. 38: \"Las disposiciones de la presente ley entrarán en vigencia al año de su publicación en el Boletín Oficial\"."},
    "ley-23592": {"first_day": None, "first_law": "ley-23592", "base_published": "1988-09-05",
                  # Ley 24.782 inserted arts. 4 and 5, so the closing article ("de forma", art. 4) became art. 6, as
                  # Ley 25.608 art. 2 says ("el actual artículo 6º -de forma-"), which moves it to art. 7 before its
                  # art. 1 adds a new art. 6
                  "overrides": {
                      (42477, 1): [{"op": "renumber", "pairs": [("art-004", "art-006")], "order": -1},
                                   {"op": "insert", "keys": ["art-004"]}],
                      (75734, 2): [{"op": "renumber", "pairs": [("art-006", "art-007")], "order": -1}],
                  },
                  "note": "Ley 23.592 as enacted (sancionada 1988-08-03, promulgada 1988-08-23, B.O. 1988-09-05). No vigencia clause: in force from the ninth day after publication (Código Civil art. 2)."},
    "ley-25520": {"first_day": None, "first_law": "ley-25520", "base_published": "2001-12-06",
                  "overrides": {
                      (422011, 19): [{"op": "insert", "keys": ["art-010-nonies"], "label": "Art. 10 nonies"}],
                      # DNU 614/2024 art. 21: "Renumérase el artículo 15 ter … como artículo 15 quater"
                      (401512, 21): [{"op": "renumber", "pairs": [("art-015-ter", "art-015-quater")]}],
                  },
                  "note": "Ley 25.520 as enacted (sancionada 2001-11-27, promulgada 2001-12-03, B.O. 2001-12-06)."},
}

C.ART_NO_DOT.add(20465)

IN_FORCE: dict[int, tuple[str, str]] = {
    # DNU 746/2017 (in force 2017-09-27, its art. 17) amended Ley 27.275 two days before the law itself took effect;
    # its changes to the law apply from the law's own entry into force
    279940: ("2017-09-29", "DNU 746/2017, art. 17: a partir del día siguiente al de su publicación (2017-09-27); its changes to Ley 27.275 apply from that law's entry into force, 2017-09-29 (art. 38)"),
    273023: ("2017-09-29", "Decreto 206/2017, art. 4: entrará en vigencia el 29 de septiembre de 2017"),
    418438: ("pub+180", "Ley 27.797, art. 34: a partir de los ciento ochenta (180) días de la fecha de su publicación"),
    25031: ("pub", "Ley 24.515, art. 19: entrará en vigencia el día de su promulgación; the record dates it by its publication (B.O. 1995-08-03), the first day its text was public"),
    310413: ("2018-05-21", "Decreto 471/2018, art. 14: regirá a partir del 21 de mayo de 2018"),
}


def decisions(rep: dict) -> list[str]:
    return [
        f"{TAG} (corpus.d/91-batch9.json, built by tools/batch9/parse_batch9.py with the replay engine of tools/parse.py and the helpers of tools/batch8/common_batches.py and tools/batch4/parse_batch4.py): Leyes 23.661, 17.418, 27.275, 23.592 and 25.520, each from InfoLEG's text as enacted (norma.htm), with every amending norm InfoLEG's consolidated text names replayed from that norm's own text and the result checked against texact.htm.",
        "Ley 23.661 (Sistema Nacional del Seguro de Salud): in force 1989-01-29 (B.O. 1989-01-20 + 9 days, no vigencia clause). The title of chapter IX (\"Disposiciones transitorias\") is dropped as a heading. Amendments by DNU 70/2023 follow InfoLEG's consolidated text; court rulings on DNU 70/2023 are not modelled.",
        "Ley 17.418 (Seguros): a law of the de facto government (30 August 1967, B.O. 1967-09-06). Art. 163 says it \"regirá a partir de los seis meses de su promulgación\"; six months from 30 August 1967 run out at the end of February 1968 (Código Civil arts. 25 and 26), so the first version is dated 1968-03-01. The heading \"DISPOSICIONES FINALES Y TRANSITORIAS\" is dropped. InfoLEG's two transcriptions of art. 163 differ (\"quedar n\" / \"quedan\"); the consolidated wording is used. Its only change of words is art. 11, by DNU 27/2018 and again by Ley 27.444 (2018); the Ley de Navegación 20.094 and Ley 20.091 regulate insurance without rewriting it.",
        "Ley 27.275 (Acceso a la Información Pública): in force 2017-09-29, one year after publication (art. 38). Decreto 206/2017 (in force 2017-09-29, its art. 4) and Ley 27.797 (in force 180 days after publication, its art. 34) are replayed from their own texts. DNU 746/2017 (in force 2017-09-27, its art. 17) amended the law two days before the law took effect; its changes are dated 2017-09-29, the law's own first day, and follow the first version as a separate commit.",
        "Ley 23.592 (Actos Discriminatorios): in force 1988-09-14 (B.O. 1988-09-05 + 9 days). Ley 24.782 (1997) inserted arts. 4 and 5, so the closing article (\"Comuníquese al Poder Ejecutivo\", art. 4) became art. 6, as Ley 25.608 art. 2 states (\"el actual artículo 6º -de forma-\"); Ley 25.608 (2002) moved it to art. 7 and added a new art. 6. The renumbering of 1997 is credited to Ley 24.782. Headings written \"Art 4°.-\" (without a period) are read as headings.",
        "Ley 25.520 (Inteligencia Nacional): in force 2001-12-15 (B.O. 2001-12-06 + 9 days). DNU 614/2024 art. 21 renumbers art. 15 ter as 15 quater before its art. 23 gives a new art. 15 ter; DNU 941/2025 (B.O. 2026-01-02) adds arts. 10 bis to 10 nonies. Both are replayed as InfoLEG's consolidated text shows them; their treatment by Congress under Ley 26.122 is not modelled.",
        "Leyes 26.831 (Mercado de Capitales), 25.246 (Lavado de Activos) and 26.522 (Servicios de Comunicación Audiovisual) were tried and are not in this batch: their replays still differ from InfoLEG's consolidated text in 3 to 9 articles (partial changes the reader does not yet place).",
    ]


def main(argv: list[str]) -> None:
    C.run(argv, ACTS, SETUP, IN_FORCE, PART, HERE, TAG, decisions)


if __name__ == "__main__":
    main(sys.argv[1:])
