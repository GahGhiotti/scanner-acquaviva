"""Riconosce la stessa notizia pubblicata da giornali diversi con titoli diversi.

Due titoli sono "la stessa notizia" se condividono almeno 3 parole significative
e queste sono almeno la metà delle parole del titolo più corto.
Esempio: "Sessant'anni del Sacchificio Industriale Sammarinese..." e
"San Marino, quattro francobolli per i 60 anni del Sacchificio Industriale
Sammarinese" condividono anni, sacchificio, industriale, sammarinese.
"""

from __future__ import annotations

from .filtro import normalizza

# Parole troppo comuni per dire qualcosa sulla notizia.
COMUNI = set(
    """
    della delle dello degli dalla dalle dallo dagli nella nelle nello negli sulla sulle sullo sugli
    alla alle allo agli come anche oggi domani ieri dopo prima sono stato stata stati state essere
    fare fatto fatta questo questa questi queste quello quella quelli quelle loro molto tutti tutte
    ogni contro verso senza sotto sopra dove quando mentre perche presso nuovo nuova nuovi nuove
    marino repubblica titano acquaviva castello giunta notizie news video foto
    """.split()
)


def parole_significative(titolo: str) -> set[str]:
    return {p for p in normalizza(titolo).split() if len(p) >= 4 and p not in COMUNI}


def stessa_notizia(titolo_a: str, titolo_b: str) -> bool:
    a, b = parole_significative(titolo_a), parole_significative(titolo_b)
    if not a or not b:
        return False
    comuni = len(a & b)
    return comuni >= 3 and comuni / min(len(a), len(b)) >= 0.5


def priorita(nome_fonte: str, cfg: dict) -> int:
    """Più basso = più importante. Le fonti non in elenco (es. Google News) vanno in fondo."""
    ordine = cfg.get("priorita_fonti") or []
    return ordine.index(nome_fonte) if nome_fonte in ordine else len(ordine)
