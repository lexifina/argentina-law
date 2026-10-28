"""Batch 5 of the Argentine record (gitlaw-AR-batch5): writes corpus.d/60-batch5.json from the InfoLEG cache only.

    python -X utf8 batch5/parse_batch5.py            # writes ../corpus.d/60-batch5.json (atomically)
    python -X utf8 batch5/parse_batch5.py report     # replay report per act
    python -X utf8 batch5/parse_batch5.py --dry      # writes batch5/.tmp/60-batch5.json instead

It reuses the replay engine of ../parse.py and the batch-4 helpers of ../batch4/parse_batch4.py (imported, not
copied): the act's text as enacted (norma.htm), every amending norm's own text replayed in order of entry into force,
and the result checked against InfoLEG's consolidated text (texact.htm). This file adds only the acts' registry
entries and set-up, and the decisions.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "batch4"))
import acts as A  # noqa: E402
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402
import parse_batch4 as B4  # noqa: E402

PART = ROOT / "corpus.d" / "60-batch5.json"

ACTS = [
    {
        "slug": "ley-23551",
        "short": "LAS",
        "id": 20993,
        "title": "Ley 23.551 de Asociaciones Sindicales",
        "start": r"^TITULO PRELIMINAR$",
        "end": r"^Dada en la Sala",
        "texact": True,
        "target": r"(?:[Ll]ey\s*(?:N[°º]\s*)?23\.?551|[Ll]ey\s+de\s+Asociaciones\s+Sindicales)",
    },
    {
        "slug": "ley-26657",
        "short": "LNSM",
        "id": 175977,
        "title": "Ley 26.657 Nacional de Salud Mental",
        "start": r"^LEY NACIONAL DE SALUD MENTAL$",
        "end": r"^DADA EN LA SALA",
        "texact": False,  # InfoLEG has no consolidated text: it records no change to the act's words
    },
    {
        "slug": "ley-25164",
        "short": "LMEP",
        "id": 60458,
        "title": "Ley 25.164 Marco de Regulación de Empleo Público Nacional",
        "start": r"^ANEXO$",
        "end": r"^Antecedentes Normativos",
        "texact": True,
        "target": (r"(?:[Ll]ey\s*(?:N[°º]\s*)?25\.?164|[Ll]ey\s+Marco\s+de\s+Regulaci[oó]n\s+del?\s+Empleo\s+"
                   r"P[uú]blico)"),
    },
]

SETUP = {
    "ley-23551": {
        # art. 65: "La presente ley entrará en vigencia al día siguiente de su publicación" (B.O. 1988-04-22)
        "first_day": "1988-04-23", "first_law": "ley-23551", "base_published": "1988-04-22",
        # the names of the act's chapters ("VI. - De la inscripción") are headings, not text
        "drop_lines": [r"^[IVXL]+\.? - [A-Z][^.]*$"],
        "note": ("Ley 23.551 as enacted (sancionada 1988-03-23, promulgada 1988-04-14, B.O. 1988-04-22). Art. 65: "
                 "\"La presente ley entrará en vigencia al día siguiente de su publicación\"."),
    },
    "ley-26657": {
        "first_day": None, "first_law": "ley-26657", "base_published": "2010-12-03",
        # the names of the chapters, printed under each "Capítulo" line, are headings
        "note": ("Ley 26.657 as enacted (sancionada 2010-11-25, promulgada 2010-12-02 by Decreto 1855/2010, B.O. "
                 "2010-12-03). It has no vigencia clause: in force from the ninth day after publication (Código Civil "
                 "art. 2)."),
    },
    "ley-25164": {
        "first_day": None, "first_law": "ley-25164", "base_published": "1999-10-08",
        "drop_lines": [r"^PROHIBICIONES$"],  # the name of chapter V, printed after the chapter's own heading line
        # Ley 27.742 art. 53 replaces "el primer párrafo" of art. 12 but quotes two paragraphs, the second being the
        # old second paragraph again; InfoLEG's consolidated text reads both as replacing the first two
        "overrides": {(401266, 53): [{"op": "lines", "action": "replace", "keys": ["art-012"], "paras": [1, 2],
                                             "text_fix": [(r"^Art[ií]culo 12:\s*", "")]}]},
        "note": ("Ley 25.164 as enacted (sancionada 1999-09-15, promulgada de hecho 1999-10-06, B.O. 1999-10-08): the six "
                 "articles of the law and the Ley Marco de Regulación de Empleo Público Nacional it approves as its "
                 "Anexo. No vigencia clause: in force from the ninth day after publication (Código Civil art. 2)."),
    },
}

IN_FORCE: dict[int, tuple[str, str]] = {}

# units printed outside the act's slice, added to every version: (act slug, key, label, kind, start, end) on norma.htm
EXTRA = {
    # Ley 25.164: the law's own six articles, before the Anexo that holds the Ley Marco
    "ley-25164": [("ley-art-%03d" % n, "Ley 25.164, art. %d" % n, "art",
                   r"^ARTICULO %dº - " % n, r"^(ARTICULO %dº - |DADA EN LA SALA)" % (n + 1)) for n in range(1, 7)],
}

_replay = P.replay


# articles of another code quoted inside an amending article of the act: (act slug, quoted unit key, host unit key)
QUOTED = {"ley-26657": [("art-152-ter", "art-042"), ("art-482", "art-043")]}


def replay(act: dict) -> dict:
    r = _replay(act)
    for quoted, host in QUOTED.get(act["slug"], []):
        for v in r["versions"]:  # "Artículo 152 ter: …" is the Código Civil article art. 42 inserts: its words, not a unit
            q = v["state"].pop(quoted)
            v["state"][host]["body"] = v["state"][host]["body"] + [f"{q['label'].replace('Art.', 'Artículo')}: {q['body'][0]}"] + q["body"][1:]
    for key, label, kind, start, end in EXTRA.get(act["slug"], []):
        L = [H.strip_links(l) for l in H.lines(F.cached(F.norma_url(act["id"])))]
        i = next(n for n, l in enumerate(L) if re.match(start, l))
        j = next(n for n, l in enumerate(L) if n > i and re.match(end, l))
        body = [re.sub(start, "", L[i])] + L[i + 1:j]
        for v in r["versions"]:
            v["state"][key] = {"label": label, "kind": kind, "body": body}
    return r


def build() -> tuple[dict, list[dict]]:
    A.ACTS[:] = [a for a in A.ACTS if a["slug"] not in SETUP] + ACTS
    P.ACT_SETUP.update(SETUP)
    P.IN_FORCE.update(IN_FORCE)
    P.replay = replay
    P.apply_lines = B4.apply_lines
    P.act_lines = B4.act_lines
    corpus, reports = P.build_corpus(set(SETUP))
    order = {a["slug"]: i for i, a in enumerate(ACTS)}
    acts = sorted(corpus["acts"], key=lambda a: order[a["slug"]])
    rep = {r["act"]: r for r in reports}
    used = sorted({n for r in reports for n in r["nids"]}, key=lambda n: (P.bulk()[n]["fecha_boletin"], n))
    decisions = [
        "Batch 5 (corpus.d/60-batch5.json, built by tools/batch5/parse_batch5.py with the replay engine of tools/parse.py and the helpers of tools/batch4/parse_batch4.py): each act from InfoLEG's text as enacted (norma.htm), with every amending norm InfoLEG's consolidated text names replayed from that norm's own text and the result checked against texact.htm.",
        "Batch 5 in-force dates of the amending norms: " + "; ".join(f"{P.rule_of(n)[1]} -> {P.in_force(n)}" for n in used) + ".",
    ]
    decisions += [
        "InfoLEG terms (checked 2026-10-28 for batch 5): servicios.infoleg.gob.ar/robots.txt and www.infoleg.gob.ar/robots.txt answer 404 (no robots rules); the site footer reads \"Los contenidos de infoleg.gob.ar están licenciados bajo Creative Commons Reconocimiento 2.5 Argentina License\" and its \"Acerca de\" page calls InfoLEG a database \"de acceso libre y gratuito\"; no ai-input or anti-scraping signal. But InfoLEG's \"Aviso Legal\" (https://www.infoleg.gob.ar/?page_id=762, linked from every verNorma.do page) says the opposite: \"Se prohíbe el enlace de la Web, total o parcialmente, aún citando la fuente, sin la autorización del Ministerio de Justicia de la Nación instrumentada por escrito, como así también su inclusión en bases de datos particulares, comerciales o no\", and under PROPIEDAD INTELECTUAL that the site's contents \"y los textos actualizados\" are protected by Ley 11.723 and that \"Su reproducción total o parcial, exceptuando el uso estrictamente personal\" is penalised. Batch 5 stopped fetching InfoLEG on finding it (96 requests through fetch.py, plus 5 plain curl reads of the two robots.txt, the home page, \"Acerca de\" and the Aviso Legal) and leaves its part unverified (no 60-batch5.PUBLISH) until the user settles the conflict.",
        "Ley 23.551 (Asociaciones Sindicales): in force 1988-04-23 (art. 65, the day after publication). The names of its chapters (\"VI. - De la inscripción\") are headings and are not kept. Arts. 20 bis and 20 ter were added by DNU 70/2023 arts. 87-88 (in force 2023-12-30 by the default rule, as for the other acts) and replaced by Ley 27.802 (2026); court rulings that suspended the labour chapter of DNU 70/2023 are not modelled, and the record follows InfoLEG's consolidated text, as for the Ley de Contrato de Trabajo. Decreto 342/2025 (InfoLEG class \"Reglamentario\"; its art. 4 gives account to the Comisión Bicameral Permanente) replaced inciso 4° of art. 56; the paragraph that followed the old inciso 4° goes with it, as in InfoLEG's consolidated text.",
        "Ley 26.657 (Salud Mental): one version. InfoLEG serves no consolidated text (texact.htm answers \"No se pudo acceder al archivo solicitado\") and its list of related norms (verVinculos) holds only regulations, resolutions and complementary laws (Decreto 603/2013, Ley 27.130), none that changes the act's words. In force 2010-12-12 (B.O. 2010-12-03 + 9 days, no vigencia clause). Arts. 42 and 43 amend the Código Civil; the articles they quote (152 ter, 482) are kept inside arts. 42 and 43, not as units of this act.",
        "Ley 25.164 (Empleo Público): the record holds the law's own six articles (files ley-art-001 to ley-art-006, never amended) and the Ley Marco it approves as its Anexo (art-001 to art-045). In force 1999-10-17 (B.O. 1999-10-08 + 9 days). Amended by DNU 585/2024 art. 10 (art. 2, in force on publication 2024-07-05) and Ley 27.742 arts. 52-61 (in force 2024-07-09). Ley 27.742 art. 53 replaces \"el primer párrafo\" of art. 12 but quotes two paragraphs, the second being the old second paragraph with a comma added; both are applied as replacing the first two paragraphs, as InfoLEG's consolidated text reads it. The name of chapter V (\"PROHIBICIONES\") is a heading.",
    ]
    for slug in rep:
        r = rep[slug]
        if slug in ("ley-26657",):
            continue
        decisions.append(f"{slug}: replay vs texact: {len(r['mismatches'])} word mismatches; reconciled to InfoLEG's wording from the last norm its note names: {', '.join(r['reconciled']) or 'none'}; typography-only: {', '.join(r['typography']) or 'none'}; transcription: {', '.join(r['transcription']) or 'none'}.")
    part = {"laws": corpus["laws"], "acts": acts, "decisions": decisions,
            "ai_use": ["Batch 5: none at data-build time; parse_batch5.py is deterministic code written with Claude Code (claude-opus-5-5)."]}
    return part, reports


def main(argv: list[str]) -> None:
    part, reports = build()
    for r in reports:
        print(f"== {r['act']}: {len(r['ops'])} ops, {len(r['mismatches'])} mismatches, typography {r['typography']}, "
              f"transcription {r['transcription']}, reconciled {r['reconciled']}, not applied {len(r['not_applied'])}")
        if "report" in argv:
            for o in r["ops"] + ["NOT APPLIED " + x for x in r["not_applied"]] + ["HEADING " + x for x in r["headings"]] \
                    + ["FROM NOTES " + x for x in r.get("from_notes", [])]:
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
