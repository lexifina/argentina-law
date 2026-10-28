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
    {
        "slug": "ley-24449",
        "short": "LNT",
        "id": 818,
        "title": "Ley 24.449 de Tránsito",
        "start": r"^TITULO I$",
        "end": r"^DADA EN LA SALA",
        "texact": True,
        "target": r"(?:[Ll]ey\s+(?:Nacional\s+)?de\s+Tr[aá]nsito|[Ll]ey\s*(?:N[°º]\s*)?24\.?449)",
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
    "ley-24449": {
        # Decreto 779/1995 art. 2: the law and its reglamentación "entrarán en vigencia el 1° de Diciembre de 1995"
        "first_day": "1995-12-01", "first_law": "ley-24449", "base_published": "1995-02-10",
        # the laws and decrees InfoLEG's consolidated text names (notes and "Antecedentes Normativos"); its
        # verVinculos list (1,533 norms) holds no other law or decree that changes the act's words
        "amenders": [42480, 68751, 91608, 102148, 140098, 305055, 305736, 311585, 327260, 345366, 383043, 414868, 417102],
        # the name of Title IX ("DISPOSICIONES TRANSITORIAS Y COMPLEMENTARIAS") is a heading; parse.split_units would
        # otherwise read the articles after it as transitional provisions
        "drop_lines": [r"^DISPOSICIONES TRANSITORIAS Y COMPLEMENTARIAS$"],
        # Decreto 179/1995 arts. 1-10 ("Obsérvase …"), applied to the bill's text in norma.htm; the remaining words
        # are those InfoLEG's consolidated text prints ("coches de bebés, y demás", "la cédula, de identificación")
        "vetoed": {"art-011": r"^d\) Doce años para circular", "art-013": r"^c\) A partir de la edad de 65 años",
                   "art-014": r"^6\.[34]\. Conducción (?:en área urbana de tránsito medio|nocturna)\.$",
                   "art-033": r"^f\) Los automotores homologados", "art-050": r"^El desarrollo de velocidades superiores"},
        "vetoed_words": [
            ("art-014", r",\s*otorgada por profesional médico habilitado\.$", "."),
            ("art-015", r"\s*acreditado por profesional competente;$", ";"),
            ("art-038", r"rodados propulsados por menores de 10 años ", ""),
            ("art-040", r"vencida o no, o documento ", ""),
            ("art-094", r"\s*nuevas, que con respecto a la legislación reemplazada crea esta ley\.$", "."),
        ],
        "overrides": {
            # "inciso 11 bis)": the definitions are lettered and InfoLEG's text of Ley 25.965 reads "ll" as "11"
            (102148, 1): [{"op": "lines", "action": "insert", "keys": ["art-005"], "after_line": r"^ll\) ",
                           "text_fix": [(r"^11 bis\)", "ll bis)")]}],
            # "Artículo 40 bis) Requisitos …": the new article's heading is closed by a bracket (text set in build())
            (102148, 7): [{"op": "insert", "keys": ["art-040-bis"], "label": "Art. 40 bis"}],
            # Ley 25.965 art. 6: inciso d) of art. 49 (two paragraphs) after inciso c) and the paragraph that closes it
            (102148, 6): [{"op": "lines", "action": "insert", "keys": ["art-049"], "after_line": r"^En zona rural se estacionará"}],
            # Ley 26.363 art. 31: "apartados 7 y 8 del inciso c)" of art. 72, whose incisos a), b), c), e) each number
            # their apartados from 1
            (140098, 31): [{"op": "lines", "action": "insert", "keys": ["art-072"], "items": ["7", "8"],
                            "within": r"^c\) A los vehículos", "until": r"^d\) "}],
            # Ley 26.363 art. 33: incisos m) to y) of art. 77 ("ñ" has no letter before it in parse.apply_lines)
            (140098, 33): [{"op": "lines", "action": "insert", "keys": ["art-077"], "after_line": r"^l\) Las que, por excederse"}],
            # Ley 27.445 art. 23 enacts again the inciso z) of art. 77 that DNU 27/2018 art. 51 had added, in the same words
            (311585, 23): [{"op": "lines", "action": "replace", "keys": ["art-077"], "items": ["z"]}],
            # Ley 24.788 writes the new inciso as "Inciso a): …"; InfoLEG's consolidated text and later laws write "a)"
            (42480, 17): [{"op": "lines", "action": "replace", "keys": ["art-048"], "items": ["a"],
                           "text_fix": [(r"^Inciso a\):\s*", "a) ")]}],
            # Decreto 461/2025 art. 34 repeals, among many other norms, "el artículo 96 de la Ley N° 24.449"
            (414868, 34): [{"op": "repeal", "keys": ["art-096"]}],
            # Decreto 627/2025 art. 1 restores the provisions Decreto 461/2025 had repealed, replaced or amended
            (417102, 1): [{"op": "restore", "keys": ["art-002", "art-002-bis", "art-096"], "undoes": "decreto-461-2025"}],
        },
        "note": ("Ley 24.449 as promulgated by Decreto 179/1995 (B.O. 1995-02-10), which vetoed (\"observó\") parts of "
                 "arts. 11, 13, 14, 15, 33, 38, 40, 50 and 94 of the bill: that text never took effect and is not shown. Art. "
                 "94 left its entry into force to its reglamentación; Decreto 779/1995 art. 2 set it at 1 December 1995."),
    },
}

# in-force rules read by hand where parse.auto_rule cannot classify the norm's own clause (added to parse.IN_FORCE)
IN_FORCE = {
    42480: ("default", "Ley 24.788, art. 22 is about where it applies (art. 17 only where provinces adhere under art. 91 "
                       "of Ley 24.449), not when; no vigencia date, so the default rule"),
}

ANNEXES = {
    # ley-25675: the two annexes its art. 25 ratifies, from norma.htm (InfoLEG gives no consolidated text)
    "ley-25675": [("anexo-1", "Anexo I", r"^ANEXO I$", r"^ANEXO II$"), ("anexo-2", "Anexo II", r"^ANEXO II$", None)],
}

_replay = P.replay
_act_lines = P.act_lines


def act_lines(nid: int, page: str, start: str, end: str):
    """parse.act_lines, plus two layout fixes in InfoLEG's consolidated text of Ley 24.449: a note closed by ")."
    is not read as a note by parse.split_units, and "ARTICULO 40 bis)" is not read as a heading."""
    L, url, sha = _act_lines(nid, page, start, end)
    if nid == 818 and page == "texact.htm":
        L = [re.sub(r"(\((?:[^()]|\([^()]*\))*(?:sustituid|incorporad|vetad|derogad)[oa]s?\s+por\b(?:[^()]|\([^()]*\))*\))\.$", r"\1", l)
             for l in L]
        L = [re.sub(r"^(ARTICULO 40 bis)\)", r"\1.-", l) for l in L]
    return L, url, sha


_apply_lines = P.apply_lines


def apply_lines(body: list[str], o: dict) -> list[str] | None:
    """parse.apply_lines, plus two keys for batch 4's overrides: "within"/"until" (regexes) limit the change to the
    lines of one numbered point of the article; "check" (regex) must match the paragraph a positional change
    targets; "after_line" (regex) places the new lines after the first line it matches; "text_fix" [(regex,
    replacement)] corrects
    a transcription slip in the amending norm's text on InfoLEG."""
    if o.get("text_fix"):
        o = dict(o, text=[re.sub(pat, rep, l) for l in o["text"] for pat, rep in o["text_fix"]])
    if "after_line" in o:  # new lines placed after the first line that matches
        i = next((i for i, l in enumerate(body) if re.match(o["after_line"], l)), None)
        return None if i is None else body[:i + 1] + list(o["text"]) + body[i + 1:]
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
    P.IN_FORCE.update(IN_FORCE)
    P.replay = replay
    P.apply_lines = apply_lines
    P.act_lines = act_lines
    # Ley 25.965 art. 7: "Artículo 40 bis) Requisitos …" -> the new article's words, its heading removed
    lines = next(ls for n, ls in P.amender_articles(102148) if n == 7)
    SETUP["ley-24449"]["overrides"][(102148, 7)][0]["text"] = P.new_text(
        [re.sub(r"^(Artículo 40 bis)\)", r"\1.-", lines[1])] + lines[2:])
    corpus, reports = P.build_corpus(set(SETUP))
    order = {a["slug"]: i for i, a in enumerate(ACTS)}
    acts = sorted(corpus["acts"], key=lambda a: order[a["slug"]])
    rep = {r["act"]: r for r in reports}
    used = sorted({n for r in reports for n in r["nids"]}, key=lambda n: (P.bulk()[n]["fecha_boletin"], n))
    decisions = [
        "Batch 4 (corpus.d/50-batch4.json, built by tools/batch4/parse_batch4.py with the replay engine of tools/parse.py): Ley 26.061, Ley 25.675, Ley 26.485 and Ley 24.449, each from InfoLEG's text as enacted (norma.htm), with every amending norm InfoLEG's consolidated text names replayed from that norm's own text and the result checked against texact.htm.",
        "Ley 27.430 (tax reform of 2017): not built. Almost all of its text is instructions amending other laws (the Ley de Impuesto a las Ganancias, the IVA law, Ley 11.683 and others), and its own later changes are Ley 27.799's amounts in the Régimen Penal Tributario it enacted as art. 279, whose articles are quoted inside art. 279 and are partly unnumbered (\"Artículo s/nº\"). A record of 27.430 would show the history of other acts; Ley 24.449 (Tránsito) was built instead.",
        "Batch 4 in-force dates of the amending norms: " + "; ".join(f"{P.rule_of(n)[1]} -> {P.in_force(n)}" for n in used) + ".",
        "Ley 26.061: in force 2005-11-04 (B.O. 2005-10-26 + 9 days; no vigencia clause). Its arts. 73 to 75 amend the Código Civil and the Código Procesal Civil y Comercial and are kept as the act's own words; changes to those codes are not changes to this act. Its Reglamentación (Decreto 415/2006, Decreto 1086/2024) is not part of the act. "
        + f"Replay vs texact: {len(rep['ley-26061']['mismatches'])} word mismatches.",
        "Ley 25.675: InfoLEG serves no consolidated text (texact.htm answers \"No se pudo acceder al archivo solicitado\") and lists no norm that changes its words, only norms that complement or regulate it (checked: Leyes 26.331, 26.639, 27.279, 27.431, 27.520 and 27.621 cite it without amending it). The record is one version: the bill as promulgated by Decreto 2413/2002, without the four passages that decree vetoed (art. 3 \"operativas\", art. 19 \"a ser consultada y\", the last sentence of art. 29 and the second-to-last sentence of art. 32), in force 2002-12-07. Removing \"operativas\" leaves \"de orden público, y se utilizarán\": the comma before it is kept as printed. Art. 35 (\"Comuníquese al Poder Ejecutivo\") is kept, as in the other acts that end at \"DADA EN LA SALA\".",
        "Ley 26.485: in force on its publication day, 2009-04-14 (art. 44). "
        + f"Replay vs texact: {len(rep['ley-26485']['mismatches'])} word mismatches; partial changes reconciled to InfoLEG's wording from the last norm its note names: {', '.join(rep['ley-26485']['reconciled']) or 'none'}; typography-only: {', '.join(rep['ley-26485']['typography']) or 'none'}. InfoLEG's \"Antecedentes Normativos\" links its entry for Ley 27.501 to the act itself (id 152155); Ley 27.501 is found by its number (id 322870).",
        "Ley 26.485, placing partial changes: art. 11 repeats the item letters under each numbered point, so \"inciso a) del punto 3\" (Ley 27.501 art. 3), \"inciso f) del punto 5.2\" (Ley 27.501 art. 4), \"inciso a) del punto 5.1\" (DNU 744/2021 art. 3) and \"incisos f) and g) del punto 3\" (Ley 27.736 arts. 6-7) are applied within that point only; art. 26's sub-items a.2, a.8 and a.9 (Ley 27.736 arts. 10-12), the two-paragraph inciso o) of art. 9 (Ley 27.736 art. 5) and the two-paragraph inciso i) of art. 6 (Ley 27.736 art. 4) are placed by position, each checked against the line it follows or replaces. InfoLEG's text of Ley 27.533 ends the new inciso h) of art. 6 with a stray closing quote, which is dropped.",
        "DNU 744/2021: its own art. 4 puts it in force \"a partir del día siguiente al de su publicación\" (B.O. 2021-10-29), so 2021-10-30; InfoLEG's note on art. 11 of Ley 26.485 says \"a partir del día de su publicación\". The decree's text is followed.",
        "Ley 24.449 (Tránsito), first version: the bill as promulgated by Decreto 179/1995 (B.O. 1995-02-10), less what its arts. 1 to 10 vetoed: art. 11 inc. d), art. 13 inc. c), in art. 14 inc. a) the words \"otorgada por profesional médico habilitado\" of point 3 and points 6.3 and 6.4, in art. 15 inc. f) \"acreditado por profesional competente\", art. 33 inc. f), in art. 38 \"rodados propulsados por menores de 10 años\", in art. 40 inc. b) \"vencida o no, o documento\", the last paragraph of art. 50 and in art. 94 \"nuevas, que con respecto a la legislación reemplazada crea esta ley\". The words left are those InfoLEG's consolidated text prints (\"coches de bebés, y demás\", \"la cédula, de identificación\"). In force 1995-12-01: art. 94 left the date to the reglamentación, and Decreto 779/1995 art. 2 (B.O. 1995-11-29, InfoLEG id 30389) set \"el 1° de Diciembre de 1995\"; Decreto 779/1995 itself changes no word of the act and gets no commit.",
        "Ley 24.449, amending norms: those InfoLEG's consolidated text names in its notes and \"Antecedentes Normativos\" (Leyes 24.788, 25.456, 25.857, 25.965, 26.363, 27.425, 27.445, 27.510, 27.603, 27.714; DNU 27/2018; Decreto 461/2025; DNU 627/2025). Its verVinculos page lists 1,533 related norms; the laws and decrees among them that say they modify Ley 24.449 are the same, and Ley 26.938 only complements it. Changes to its reglamentación (Decreto 779/1995 and its amendments) are not changes to the act. "
        + f"Replay vs texact: {len(rep['ley-24449']['mismatches'])} word mismatches; reconciled to InfoLEG's wording from the last norm its note names: {', '.join(rep['ley-24449']['reconciled']) or 'none'} (InfoLEG's consolidated text reads \"ta\" for \"la\" once in art. 6 as written by Ley 26.363, and its wording is kept); typography-only: {', '.join(rep['ley-24449']['typography']) or 'none'}.",
        "Ley 24.449, placing partial changes: Ley 25.965's \"inciso 11 bis)\" of art. 5 is \"ll bis)\" (the definitions are lettered a) to z) with ch, ll and ñ; InfoLEG's transcription of Ley 25.965 has the digits \"11\", its consolidated text \"ll bis)\") and goes after inciso ll); its art. 6 adds inciso d) of art. 49 after the closing paragraph of inciso c); its art. 7 heads the new art. 40 bis \"Artículo 40 bis)\", read as a heading. Ley 26.363 art. 31 adds apartados 7 and 8 to inciso c) of art. 72 (not to the other incisos' lists) and art. 33 adds incisos m) to y) of art. 77 after inciso l). Ley 24.788 writes the new inciso a) of art. 48 as \"Inciso a): …\"; it is written \"a) …\" as in later laws and the consolidated text. Ley 27.445 art. 23 enacts again, in the same words, inciso z) of art. 77 added by DNU 27/2018 art. 51; it changes no words. Ley 26.363 art. 24 only renames a chapter (headings are not kept). Ley 24.788 art. 22 is about where the law applies, not when, so the default in-force rule is used. The name of Title IX is dropped as a heading. InfoLEG's consolidated text closes some notes with \").\"; they are read as notes.",
        "Ley 24.449 and Decreto 461/2025: the delegated Decreto 461/2025 (B.O. and in force 2025-07-08, art. 37) replaced art. 2, added art. 2 bis and, in art. 34, repealed art. 96. Both chambers rejected it under Ley 26.122 (Resolución 94/2025 of the Cámara de Diputados and Resolución 55/2025 of the Senado, both B.O. 2025-08-25); DNU 627/2025 (B.O. and in force 2025-09-03, art. 5) notes that a rejection repeals the decree without reviving what it changed, and its art. 1 restored the provisions the decree had repealed, replaced or amended. Following InfoLEG (\"Vigencia restituida\", \"Texto Original restituido por art. 1° del Decreto N° 627/2025\"), arts. 2 and 96 return to their earlier words and art. 2 bis goes, credited to DNU 627/2025, which carries `restores`. The two resolutions change no words themselves and get no commit.",
    ]
    if "decreto-627-2025" in corpus["laws"]:
        corpus["laws"]["decreto-627-2025"]["restores"] = "decreto-461-2025"
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
