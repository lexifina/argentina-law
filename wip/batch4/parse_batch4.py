"""Batch 4 of the Argentine record (gitlaw-AR-batch4): writes corpus.d/50-batch4.json from the InfoLEG cache only.

    python -X utf8 batch4/parse_batch4.py            # writes ../corpus.d/50-batch4.json (atomically)
    python -X utf8 batch4/parse_batch4.py report     # replay report per act
    python -X utf8 batch4/parse_batch4.py --dry      # writes batch4/.tmp/50-batch4.json instead

It reuses the replay engine of ../parse.py (imported, not copied): the act's text as enacted (norma.htm), every
amending norm's own text replayed in order of entry into force, and the result checked against InfoLEG's
consolidated text (texact.htm). This file only adds the acts' registry entries and set-up, and the decisions.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import acts as A  # noqa: E402
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402

PART = ROOT / "corpus.d" / "50-batch4.json"

ACTS = [
    {
        "slug": "ley-26061",
        "short": "LPINNA",
        "id": 110778,
        "title": "Ley 26.061 de Protección Integral de los Derechos de las Niñas, Niños y Adolescentes",
        "start": r"^TITULO I$",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?26\.?061)",
    },
    {
        "slug": "ley-25675",
        "short": "LGA",
        "id": 79980,
        "title": "Ley 25.675 General del Ambiente",
        "start": r"^ARTICULO 1º - La presente ley establece",
        "end": r"^DADA EN LA SALA",
        "texact": False,  # InfoLEG has no consolidated text: it records no change to the act's words
    },
    {
        "slug": "ley-26485",
        "short": "LPIM",
        "id": 152155,
        "title": ("Ley 26.485 de Protección Integral para Prevenir, Sancionar y Erradicar la Violencia contra las "
                  "Mujeres en los Ámbitos en que Desarrollen sus Relaciones Interpersonales"),
        "start": r"^TITULO I$",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?26\.?485)",
    },
]

SETUP = {
    "ley-26061": {
        "first_day": None, "first_law": "ley-26061", "base_published": "2005-10-26",
        "note": ("Ley 26.061 as enacted (sancionada 2005-09-28, promulgada de hecho 2005-10-21, B.O. 2005-10-26). It has "
                 "no vigencia clause: in force from the ninth day after publication (Código Civil art. 2)."),
    },
    "ley-25675": {
        "first_day": None, "first_law": "ley-25675", "base_published": "2002-11-28",
        # the titles of the act's sections, printed between articles: headings, not text
        "drop_lines": [r"^(?:Principios de la política ambiental|Presupuesto mínimo|Competencia judicial|"
                       r"Instrumentos de la política y la gestión ambiental|Ordenamiento ambiental|"
                       r"Evaluación de impacto ambiental|Educación ambiental|Información ambiental|Participación ciudadana|"
                       r"Seguro ambiental y fondo de restauración|Sistema Federal Ambiental|"
                       r"Ratificación de acuerdos federales|Autogestión|Daño ambiental|Del Fondo de Compensación Ambiental)$"],
        # Decreto 2413/2002 arts. 1-4 ("Obsérvase …"), applied to the bill's text in norma.htm
        "vetoed_words": [
            ("art-003", r"de orden público, operativas y se utilizarán", "de orden público, y se utilizarán"),
            ("art-019", r"derecho a ser consultada y a opinar", "derecho a opinar"),
            ("art-029", r"\s*Se presume iuris tantum la responsabilidad del autor del daño ambiental, si existen "
                        r"infracciones a las normas ambientales administrativas\.", ""),
            # InfoLEG's transcription reads "en su Sentencia" and "expresamente su consideración"
            ("art-032", r"\s*Asimismo, en su [Ss]entencia, de acuerdo a las reglas de la sana crítica, el juez podrá "
                        r"extender su fallo a cuestiones no sometidas expresamente (?:a )?su consideración por las partes\.", ""),
        ],
        "note": ("Ley 25.675 as promulgated by Decreto 2413/2002 (B.O. 2002-11-28), which vetoed (\"observó\") the word "
                 "\"operativas\" in art. 3, the words \"a ser consultada y\" in art. 19, the last sentence of art. 29 and "
                 "a sentence of art. 32: that text never took effect and is not shown. No vigencia clause: in force from "
                 "the ninth day after publication (Código Civil art. 2). Anexos I (Acta Constitutiva del COFEMA) and II "
                 "(Pacto Federal Ambiental), ratified by art. 25, are kept as two files."),
    },
    "ley-26485": {
        "first_day": "2009-04-14", "first_law": "ley-26485", "base_published": "2009-04-14",
        # instructions the generic reader misplaces: art. 11 repeats the item letters under each numbered point
        # ("inciso a) del punto 3"), so those changes are scoped to the point ("within" … "until", see apply_lines);
        # art. 26 numbers its sub-items "a.2.", "a.8.", which are placed by position
        "overrides": {
            (322870, 1): [{"op": "lines", "action": "insert", "keys": ["art-006"], "items": ["g"]}],
            (322870, 3): [{"op": "lines", "action": "replace", "keys": ["art-011"], "items": ["a"],
                           "within": r"^3\.-", "until": r"^4\.-"}],
            (322870, 4): [{"op": "lines", "action": "insert", "keys": ["art-011"], "items": ["f"],
                           "within": r"^5\.2\.", "until": r"^5\.3\."}],
            (333514, 3): [{"op": "lines", "action": "insert", "keys": ["art-005"], "items": ["6"]}],
            # Ley 27.533's text on InfoLEG ends inciso h) with a stray closing quote ("… entre otros.'")
            (333514, 4): [{"op": "lines", "action": "insert", "keys": ["art-006"], "items": ["h"], "text_fix": [(r"'$", "")]}],
            # inciso o) of art. 9 has two paragraphs since Ley 27.501; Ley 27.736 replaces both
            (391774, 5): [{"op": "lines", "action": "replace", "keys": ["art-009"], "paras": [1, 2],
                           "within": r"^ñ\)", "until": r"^p\)", "check": r"^o\)"}],
            (356020, 3): [{"op": "lines", "action": "replace", "keys": ["art-011"], "items": ["a"],
                           "within": r"^5\.1\.", "until": r"^5\.2\."}],
            # inciso i) has two paragraphs: placed after inciso h), the 9th line of the article
            (391774, 4): [{"op": "lines", "action": "insert_after", "keys": ["art-006"], "paras": [9], "check": r"^h\)"}],
            (391774, 6): [{"op": "lines", "action": "replace", "keys": ["art-011"], "items": ["f"],
                           "within": r"^3\.-", "until": r"^4\.-"}],
            (391774, 7): [{"op": "lines", "action": "insert", "keys": ["art-011"], "items": ["g"],
                           "within": r"^3\.-", "until": r"^4\.-"}],
            (391774, 10): [{"op": "lines", "action": "replace", "keys": ["art-026"], "paras": [4], "check": r"^a\.2\."}],
            (391774, 11): [{"op": "lines", "action": "insert_after", "keys": ["art-026"], "paras": [9], "check": r"^a\.7\."}],
            (391774, 12): [{"op": "lines", "action": "insert_after", "keys": ["art-026"], "paras": [10], "check": r"^a\.8\."}],
        },
        "note": ("Ley 26.485 as enacted (sancionada 2009-03-11, promulgada de hecho 2009-04-01, B.O. 2009-04-14). Art. "
                 "44: \"La ley entrará en vigencia a partir de su publicación en el Boletín Oficial\"."),
    },
}

ANNEXES = {
    # ley-25675: the two annexes its art. 25 ratifies, from norma.htm (InfoLEG gives no consolidated text)
    "ley-25675": [("anexo-1", "Anexo I", r"^ANEXO I$", r"^ANEXO II$"), ("anexo-2", "Anexo II", r"^ANEXO II$", None)],
}

_replay = P.replay
_apply_lines = P.apply_lines


def apply_lines(body: list[str], o: dict) -> list[str] | None:
    """parse.apply_lines, plus two keys for batch 4's overrides: "within"/"until" (regexes) limit the change to the
    lines of one numbered point of the article; "check" (regex) must match the paragraph a positional change targets; "text_fix" [(regex, replacement)] corrects
    a transcription slip in the amending norm's text on InfoLEG."""
    if o.get("text_fix"):
        o = dict(o, text=[re.sub(pat, rep, l) for l in o["text"] for pat, rep in o["text_fix"]])
    if "within" not in o:
        if "check" in o and not (o["paras"][0] <= len(body) and re.match(o["check"], body[o["paras"][0] - 1])):
            return None
        return _apply_lines(body, o)
    h = next((i for i, l in enumerate(body) if re.match(o["within"], l)), None)
    if h is None:
        return None
    e = next((i for i in range(h + 1, len(body)) if re.match(o["until"], body[i])), len(body))
    if "check" in o and not (o["paras"][0] <= e - h - 1 and re.match(o["check"], body[h + o["paras"][0]])):
        return None
    seg = _apply_lines(body[h + 1:e], o)
    return None if seg is None else body[:h + 1] + seg + body[e:]


def replay(act: dict) -> dict:
    r = _replay(act)
    for key, label, start, end in ANNEXES.get(act["slug"], []):
        L = [H.strip_links(l) for l in H.lines(F.cached(F.norma_url(act["id"])))]
        i = next(n for n, l in enumerate(L) if re.match(start, l))
        j = next((n for n, l in enumerate(L) if n > i and end and re.match(end, l)), len(L))
        for v in r["versions"]:
            v["state"][key] = {"label": label, "kind": "annex", "body": L[i + 1:j]}
    return r


def build() -> tuple[dict, list[dict]]:
    A.ACTS[:] = [a for a in A.ACTS if a["slug"] not in SETUP] + ACTS
    P.ACT_SETUP.update(SETUP)
    P.replay = replay
    P.apply_lines = apply_lines
    corpus, reports = P.build_corpus(set(SETUP))
    order = {a["slug"]: i for i, a in enumerate(ACTS)}
    acts = sorted(corpus["acts"], key=lambda a: order[a["slug"]])
    rep = {r["act"]: r for r in reports}
    used = sorted({n for r in reports for n in r["nids"]}, key=lambda n: (P.bulk()[n]["fecha_boletin"], n))
    decisions = [
        "Batch 4 (corpus.d/50-batch4.json, built by tools/batch4/parse_batch4.py with the replay engine of tools/parse.py): Ley 26.061, Ley 25.675 and Ley 26.485, each from InfoLEG's text as enacted (norma.htm), with every amending norm InfoLEG's consolidated text names replayed from that norm's own text and the result checked against texact.htm.",
        "Batch 4 in-force dates of the amending norms: " + "; ".join(f"{P.rule_of(n)[1]} -> {P.in_force(n)}" for n in used) + ".",
        "Ley 26.061: in force 2005-11-04 (B.O. 2005-10-26 + 9 days; no vigencia clause). Its arts. 73 to 75 amend the Código Civil and the Código Procesal Civil y Comercial and are kept as the act's own words; changes to those codes are not changes to this act. Its Reglamentación (Decreto 415/2006, Decreto 1086/2024) is not part of the act. "
        + f"Replay vs texact: {len(rep['ley-26061']['mismatches'])} word mismatches.",
        "Ley 25.675: InfoLEG serves no consolidated text (texact.htm answers \"No se pudo acceder al archivo solicitado\") and lists no norm that changes its words, only norms that complement or regulate it (checked: Leyes 26.331, 26.639, 27.279, 27.431, 27.520 and 27.621 cite it without amending it). The record is one version: the bill as promulgated by Decreto 2413/2002, without the four passages that decree vetoed (art. 3 \"operativas\", art. 19 \"a ser consultada y\", the last sentence of art. 29 and the second-to-last sentence of art. 32), in force 2002-12-07. Removing \"operativas\" leaves \"de orden público, y se utilizarán\": the comma before it is kept as printed. Art. 35 (\"Comuníquese al Poder Ejecutivo\") is kept, as in the other acts that end at \"DADA EN LA SALA\".",
        "Ley 26.485: in force on its publication day, 2009-04-14 (art. 44). "
        + f"Replay vs texact: {len(rep['ley-26485']['mismatches'])} word mismatches; partial changes reconciled to InfoLEG's wording from the last norm its note names: {', '.join(rep['ley-26485']['reconciled']) or 'none'}; typography-only: {', '.join(rep['ley-26485']['typography']) or 'none'}. InfoLEG's \"Antecedentes Normativos\" links its entry for Ley 27.501 to the act itself (id 152155); Ley 27.501 is found by its number (id 322870).",
    ]
    part = {"laws": corpus["laws"], "acts": acts, "decisions": decisions,
            "ai_use": ["Batch 4: none at data-build time; parse_batch4.py is deterministic code written with Claude Code (claude-opus-5-5)."]}
    return part, reports


def main(argv: list[str]) -> None:
    part, reports = build()
    for r in reports:
        print(f"== {r['act']}: {len(r['ops'])} ops, {len(r['mismatches'])} mismatches, typography {r['typography']}, "
              f"transcription {r['transcription']}, reconciled {r['reconciled']}, not applied {len(r['not_applied'])}")
        if "report" in argv:
            for o in r["ops"] + ["NOT APPLIED " + x for x in r["not_applied"]] + ["HEADING " + x for x in r["headings"]]:
                print("  ", o)
        for m in r["mismatches"]:
            print("   MISMATCH", m)
    out = HERE / ".tmp" / PART.name if "--dry" in argv else PART
    out.parent.mkdir(exist_ok=True)
    P.write_json(out, part)
    for a in part["acts"]:
        print(a["slug"], len(a["versions"]), "versions", [v["from"] for v in a["versions"]])
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
