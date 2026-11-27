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


def test_silenzio_notturno():
    from datetime import datetime
    from scanner.__main__ import e_notte
    cfg = {"silenzio_notturno": {"dalle": 22, "alle": 7}}
    assert e_notte(cfg, datetime(2026, 11, 21, 23, 30))
    assert e_notte(cfg, datetime(2026, 11, 21, 3, 0))
    assert e_notte(cfg, datetime(2026, 11, 21, 6, 59))
    assert not e_notte(cfg, datetime(2026, 11, 21, 7, 0))
    assert not e_notte(cfg, datetime(2026, 11, 21, 21, 59))
    assert not e_notte({}, datetime(2026, 11, 21, 3, 0))


def test_post_whatsapp_ha_entrambi_i_canali():
    from scanner.telegram import post_whatsapp
    t = post_whatsapp(Articolo("Titolo", "https://rtv/x", "San Marino RTV", True), CFG)
    assert "WhatsApp: https://whatsapp.com/channel/" in t
    assert "Telegram: https://t.me/acquavivanews" in t
