"""Decide se un testo parla del Castello di Acquaviva."""

import re
import unicodedata


def normalizza(testo: str) -> str:
    """Minuscole, senza accenti né apostrofi, parole separate da un solo spazio.

    "Cà Martino", "Ca' Martino" e "CA MARTINO" diventano tutti " ca martino ".
    Gli spazi ai bordi permettono di cercare solo parole intere.
    """
    testo = unicodedata.normalize("NFKD", testo or "")
    testo = "".join(c for c in testo if not unicodedata.combining(c)).lower()
    testo = re.sub(r"[^a-z0-9]+", " ", testo)
    return " " + " ".join(testo.split()) + " "


class Filtro:
    def __init__(self, parole: dict):
        def lista(chiave):
            valori = [normalizza(p) for p in (parole.get(chiave) or [])]
            return [v for v in valori if v.strip()]

        self.forti = lista("forti")
        self.acquaviva = lista("acquaviva")
        self.deboli = lista("deboli")
        self.contesto = lista("contesto")
        self.esclusioni = lista("esclusioni")

    def controlla(self, testo: str, sammarinese: bool) -> str | None:
        """Restituisce la parola che ha fatto scattare la pubblicazione, oppure None."""
        t = normalizza(testo)
        for frase in self.esclusioni:
            while frase in t:
                t = t.replace(frase, " ")

        for parola in self.forti:
            if parola in t:
                return parola.strip()

        contesto = any(c in t for c in self.contesto)

        for parola in self.acquaviva:
            if parola in t and (sammarinese or contesto):
                return parola.strip()

        if contesto:
            for parola in self.deboli:
                if parola in t:
                    return parola.strip()
        return None
