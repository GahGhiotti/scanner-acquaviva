"""Elenco degli articoli già visti, salvato in data/seen.json."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .filtro import normalizza

GIORNI_MEMORIA = 180


def chiavi(url: str, titolo: str) -> list[str]:
    """Un articolo è "già visto" se coincide il link oppure il titolo.

    Il titolo serve a non ripubblicare la stessa notizia arrivata sia dal
    giornale sia da Google News.
    """
    return ["u:" + url.strip(), "t:" + normalizza(titolo).strip()]


class Memoria:
    def __init__(self, percorso: Path):
        self.percorso = percorso
        if percorso.exists():
            dati = json.loads(percorso.read_text(encoding="utf-8"))
        else:
            dati = {}
        self.visti: dict[str, str] = dati.get("visti", {})
        self.ultimo: dict[str, str] = dati.get("ultimo", {})
        self.inizializzata: bool = dati.get("inizializzata", False)

    def gia_visto(self, url: str, titolo: str) -> bool:
        return any(k in self.visti for k in chiavi(url, titolo))

    def segna(self, url: str, titolo: str) -> None:
        oggi = datetime.now(timezone.utc).date().isoformat()
        for k in chiavi(url, titolo):
            self.visti[k] = oggi

    def dimentica(self, url: str, titolo: str) -> None:
        for k in chiavi(url, titolo):
            self.visti.pop(k, None)

    def ore_da(self, nome: str) -> float:
        if nome not in self.ultimo:
            return float("inf")
        prima = datetime.fromisoformat(self.ultimo[nome])
        return (datetime.now(timezone.utc) - prima).total_seconds() / 3600

    def segna_giro(self, nome: str) -> None:
        self.ultimo[nome] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def salva(self) -> None:
        limite = (datetime.now(timezone.utc) - timedelta(days=GIORNI_MEMORIA)).date().isoformat()
        self.visti = {k: v for k, v in self.visti.items() if v >= limite}
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        dati = {"inizializzata": self.inizializzata, "ultimo": self.ultimo, "visti": dict(sorted(self.visti.items()))}
        self.percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
