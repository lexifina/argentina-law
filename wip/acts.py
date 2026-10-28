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
]


def all_ids() -> list[int]:
    return [a["id"] for a in ACTS]


def by_slug(slug: str) -> dict:
    return next(a for a in ACTS if a["slug"] == slug)
