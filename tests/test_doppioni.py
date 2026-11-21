from pathlib import Path

import yaml

from scanner.doppioni import priorita, stessa_notizia
from scanner.fonti import Articolo
from scanner.telegram import post_telegram

CFG = yaml.safe_load((Path(__file__).parent.parent / "config" / "config.yaml").read_text(encoding="utf-8"))


def test_stessa_notizia_titoli_diversi():
    a = ("Sessant’anni del Sacchificio Industriale Sammarinese la Repubblica di San Marino celebra "
         "una storia di industria, innovazione e impresa")
    b = "San Marino, quattro francobolli per i 60 anni del Sacchificio Industriale Sammarinese"
    assert stessa_notizia(a, b)


def test_notizie_diverse_non_unite():
    assert not stessa_notizia("Virtus-Tre Fiori 2-1, decide Rossi", "Virtus-Fiorentino 4-5 nel posticipo")
    assert not stessa_notizia("Chiusura di strada Gaviano per lavori", "Festa di fine estate ad Acquaviva")


def test_priorita():
    assert priorita("San Marino RTV", CFG) < priorita("Insider", CFG) < priorita("Google News", CFG)


def test_post_con_altre_fonti():
    rtv = Articolo("Titolo", "https://rtv/x", "San Marino RTV", True)
    ins = Articolo("Altro titolo", "https://insider/y", "Insider", True)
    t = post_telegram(rtv, CFG, [ins])
    assert "Fonte: San Marino RTV\nAnche su: <a href=\"https://insider/y\">Insider</a>\n" in t
