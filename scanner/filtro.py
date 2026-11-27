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
        sport = parole.get("sport") or {}
        self.squadre_di_casa = [normalizza(p) for p in sport.get("squadre_di_casa") or []]
        self.ospiti_ammessi = [normalizza(p) for p in sport.get("ospiti_ammessi") or []]
        self.solo_campo = [normalizza(p) for p in sport.get("solo_campo") or []]

    def controlla(self, testo: str, sammarinese: bool, sportivo: bool = False, testa: str = "") -> str | None:
        """Restituisce la parola che ha fatto scattare la pubblicazione, oppure None.

        Con sportivo=True (notizia di sport) "Acquaviva" da sola non basta:
        servono la squadra di casa, oppure un ospite ammesso che gioca ad Acquaviva.
        Contano comunque le località forti (es. un rally che passa da Gualdicciolo).
        "testa" è titolo + prime righe: nello sport squadre e luoghi devono stare lì,
        non solo in fondo all'articolo (classifiche, risultati delle altre partite).
        """
        t = normalizza(testo)
        for frase in self.esclusioni:
            while frase in t:
                t = t.replace(frase, " ")

        if sportivo:
            return self._controlla_sport(t, testa, sammarinese)

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


    def _togli_esclusioni(self, t: str) -> str:
        for frase in self.esclusioni:
            while frase in t:
                t = t.replace(frase, " ")
        return t

    def _controlla_sport(self, t: str, testa: str, sammarinese: bool) -> str | None:
        """Regole per lo sport.

        - squadra di casa (Virtus, Bocciofila Montecerreto) nel titolo o nelle prime righe;
        - ospite ammesso (Nazionale, partite di beneficenza...) nel titolo o nelle prime righe,
          e Acquaviva nominata nell'articolo (si gioca lì);
        - località forte o "Acquaviva" (non come semplice campo di gioco) nel titolo o nelle prime righe.
        """
        h = self._togli_esclusioni(normalizza(testa)) if testa else t
        contesto = any(c in t for c in self.contesto)
        for squadra in self.squadre_di_casa:
            if squadra in h and (sammarinese or contesto):
                return squadra.strip()
        ad_acquaviva = " acquaviva " in t
        for ospite in self.ospiti_ammessi:
            if ospite in h and ad_acquaviva:
                return f"{ospite.strip()} ad acquaviva"
        for frase in self.solo_campo:
            while frase in h:
                h = h.replace(frase, " ")
        for parola in self.forti:
            if parola in h:
                return parola.strip()
        for parola in self.acquaviva:
            if parola in h and parola not in self.squadre_di_casa and (sammarinese or contesto):
                return parola.strip()
        return None


def estratto(testo: str, parola: str, larghezza: int = 70) -> str:
    """Il pezzo di testo intorno alla parola trovata, per capire perché è scattato."""
    t = normalizza(testo)
    i = t.find(" " + parola + " ")
    if i < 0:
        return ""
    return "…" + t[max(0, i - larghezza): i + len(parola) + larghezza].strip() + "…"

