"""The acts built for Argentina, by InfoLEG id (gitlaw-AR).

start/end are regexes on the cleaned lines of both norma.htm and texact.htm: the act's
own text runs from the first line matching `start` (inclusive) to the first later line
matching `end` (exclusive).
"""
from __future__ import annotations

ACTS = [
    {
        "slug": "constitucion",
        "short": "CN",
        "id": 804,
        "title": "Constitución de la Nación Argentina",
        "start": r"^PRE[AÁ]MBULO$",
        "end": r"^ART[IÍ]CULO 2\s*[º°]",
        "texact": False,  # InfoLEG publishes only the text of Ley 24.430 (no texact.htm)
    },
    {
        "slug": "codigo-civil-y-comercial",
        "short": "CCyC",
        "id": 235975,
        "title": "Código Civil y Comercial de la Nación",
        "start": r"^TITULO PRELIMINAR$",
        "end": r"^ANEXO II$",
        "texact": True,
        "target": r"C[oó]digo Civil y Comercial",
    },
    {
        "slug": "ley-25326",
        "short": "LPDP",
        "id": 64790,
        "title": "Ley 25.326 de Protección de los Datos Personales",
        "start": r"^Cap[ií]tulo I$",
        "end": r"^(DADA EN LA SALA|- Art[ií]culo 47 vetado)",
        "texact": True,
        "target": r"[Ll]ey\s*(N[°º]\s*)?25\.?326",
    },
    {
        "slug": "codigo-penal",
        "short": "CP",
        "id": 16546,
        "title": "Código Penal de la Nación Argentina (Ley 11.179, texto ordenado 1984)",
        # norma.htm of 16546 is the code of 1921; the oldest full text InfoLEG has of the code as later amended is
        # the texto ordenado approved by Decreto 3992/1984 (id 38033), which is the base of the replay
        "base_id": 38033,
        "start": r"(?i)^art[ií]culo 1\s*[º°]\s*\.?\s*-?\s*Este c[oó]digo",
        "end": r"^(INDICE DE ORDENAMIENTO|Antecedentes Normativos)$",
        "texact": True,
        "target": r"C[oó]digo Penal",
    },
    {
        "slug": "ley-20744",
        "short": "LCT",
        "id": 25552,
        "title": "Ley de Contrato de Trabajo (Ley 20.744, texto ordenado 1976)",
        # the texto ordenado approved by Decreto 390/1976 (id 229909) is the base of the replay
        "base_id": 229909,
        "start": r"(?i)^art[ií]culo 1\s*[º°]\s*\.?\s*-?\s*Fuentes de regulaci",
        "end": r"^(Antecedentes Normativos)$",
        "texact": True,
        "target": r"(?:Ley\s+de\s+Contrato\s+de\s+Trabajo|R[eé]gimen\s+de\s+Contrato\s+de\s+Trabajo|[Ll]ey\s*(?:N[°º]\s*)?20\.?744)",
    },
    {
        "slug": "codigo-procesal-penal-federal",
        "short": "CPPF",
        "id": 239340,
        "title": "Código Procesal Penal Federal (Ley 27.063, texto ordenado 2019)",
        # the code is Anexo I of Ley 27.063; the base is the texto ordenado approved by Decreto 118/2019 (id 319681)
        "base_id": 319681,
        "start": r"^ART[IÍ]CULO 1\s*[º°]\s*\.?-?\s*Juicio previo",
        "end": r"^ANEXO II$",
        "texact": True,
        "target": r"C[oó]digo\s+Procesal\s+Penal\s+Federal",
    },
]


def all_ids() -> list[int]:
    return [a["id"] for a in ACTS]


def by_slug(slug: str) -> dict:
    return next(a for a in ACTS if a["slug"] == slug)
