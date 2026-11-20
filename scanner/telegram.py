"""Invio dei messaggi tramite il bot Telegram e formato dei post."""

from __future__ import annotations

import html
import time

import requests

from .fonti import Articolo


def post_telegram(art: Articolo, cfg: dict) -> str:
    """Post per il canale Telegram (HTML). Il footer rimanda a WhatsApp."""
    c, g = cfg["canale"], cfg["giunta"]
    e = html.escape
    return (
        f"📰 <b>{e(art.titolo)}</b>\n"
        f"🔗 <a href=\"{e(art.url, quote=True)}\">Leggi l'articolo</a>\n"
        f"Fonte: {e(art.fonte)}\n"
        f"\n———\n"
        f"📲 {e(c['nome'])} anche su WhatsApp:\n{e(c['whatsapp'])}\n"
        f"\n🏰 {e(g['nome'])}\n"
        f"Facebook: {e(g['facebook'])}\n"
        f"Instagram: {e(g['instagram'])}"
    )


def post_whatsapp(art: Articolo, cfg: dict) -> str:
    """Stesso post in testo semplice per WhatsApp. Il footer rimanda a Telegram."""
    c, g = cfg["canale"], cfg["giunta"]
    return (
        f"📰 *{art.titolo}*\n"
        f"{art.url}\n"
        f"Fonte: {art.fonte}\n"
        f"\n———\n"
        f"📲 {c['nome']} anche su Telegram:\n{c['telegram']}\n"
        f"\n🏰 {g['nome']}\n"
        f"Facebook: {g['facebook']}\n"
        f"Instagram: {g['instagram']}"
    )


def invia(token: str, chat_id: str, testo: str, anteprima: str | None = None, html_mode: bool = True) -> None:
    dati = {"chat_id": chat_id, "text": testo}
    if html_mode:
        dati["parse_mode"] = "HTML"
    if anteprima:
        dati["link_preview_options"] = {"url": anteprima, "prefer_large_media": True}
    else:
        dati["link_preview_options"] = {"is_disabled": True}
    for tentativo in range(4):
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=dati, timeout=30)
        if r.status_code == 429:
            attesa = r.json().get("parameters", {}).get("retry_after", 5)
            time.sleep(attesa + 1)
            continue
        if not r.ok:
            raise RuntimeError(f"Telegram ha risposto {r.status_code}: {r.text[:300]}")
        return
    raise RuntimeError("Telegram: troppi tentativi")
