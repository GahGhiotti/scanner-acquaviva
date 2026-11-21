"""Invio dei messaggi tramite il bot Telegram e formato dei post."""

from __future__ import annotations

import html
import time

import requests

from .filtro import normalizza
from .fonti import Articolo


def categoria(art: Articolo, cfg: dict) -> tuple[str, str]:
    """(emoji, nome) della categoria del post, secondo config.yaml."""
    testo = normalizza(f"{art.titolo} {art.parola} {art.etichette}")
    for c in cfg.get("categorie") or []:
        if art.fonte in (c.get("fonti") or []) or getattr(art, "nome_fonte_config", "") in (c.get("fonti") or []):
            return c["emoji"], c["nome"]
        if any(pezzo in art.url for pezzo in (c.get("link") or [])):
            return c["emoji"], c["nome"]
        if any(normalizza(p) in testo for p in (c.get("parole") or [])):
            return c["emoji"], c["nome"]
    d = cfg.get("categoria_predefinita") or {"emoji": "📰", "nome": "Notizie"}
    return d["emoji"], d["nome"]


def post_telegram(art: Articolo, cfg: dict, altri: list[Articolo] | None = None) -> str:
    """Post per il canale Telegram (HTML). Il footer rimanda a WhatsApp.

    "altri" sono gli stessi articoli pubblicati da altri giornali.
    """
    c, g = cfg["canale"], cfg["giunta"]
    e = html.escape
    emoji, nome = categoria(art, cfg)
    anche = ""
    if altri:
        link = " · ".join(f"<a href=\"{e(a.url, quote=True)}\">{e(a.fonte)}</a>" for a in altri)
        anche = f"Anche su: {link}\n"
    return (
        f"{emoji} {e(nome.upper())}\n"
        f"<b>{e(art.titolo)}</b>\n"
        f"🔗 <a href=\"{e(art.url, quote=True)}\">Leggi l'articolo</a>\n"
        f"Fonte: {e(art.fonte)}\n"
        f"{anche}"
        f"\n———\n"
        f"📲 {e(c['nome'])} anche su WhatsApp:\n{e(c['whatsapp'])}\n"
        f"\n🏰 {e(g['nome'])}\n"
        f"Facebook: {e(g['facebook'])}\n"
        f"Instagram: {e(g['instagram'])}"
    )


def post_whatsapp(art: Articolo, cfg: dict) -> str:
    """Stesso post in testo semplice per WhatsApp. Il footer rimanda a Telegram."""
    c, g = cfg["canale"], cfg["giunta"]
    emoji, nome = categoria(art, cfg)
    return (
        f"{emoji} {nome.upper()}\n"
        f"*{art.titolo}*\n"
        f"{art.url}\n"
        f"Fonte: {art.fonte}\n"
        f"\n———\n"
        f"📲 {c['nome']} anche su Telegram:\n{c['telegram']}\n"
        f"\n🏰 {g['nome']}\n"
        f"Facebook: {g['facebook']}\n"
        f"Instagram: {g['instagram']}"
    )


def invia(token: str, chat_id: str, testo: str, anteprima: str | None = None, html_mode: bool = True,
          modifica_id: int | None = None) -> int | None:
    """Invia un messaggio (o modifica quello con id "modifica_id"). Restituisce l'id del messaggio."""
    dati = {"chat_id": chat_id, "text": testo}
    metodo = "sendMessage"
    if modifica_id:
        dati["message_id"] = modifica_id
        metodo = "editMessageText"
    if html_mode:
        dati["parse_mode"] = "HTML"
    if anteprima:
        dati["link_preview_options"] = {"url": anteprima, "prefer_large_media": True}
    else:
        dati["link_preview_options"] = {"is_disabled": True}
    for tentativo in range(4):
        r = requests.post(f"https://api.telegram.org/bot{token}/{metodo}", json=dati, timeout=30)
        if r.status_code == 429:
            attesa = r.json().get("parameters", {}).get("retry_after", 5)
            time.sleep(attesa + 1)
            continue
        if not r.ok:
            raise RuntimeError(f"Telegram ha risposto {r.status_code}: {r.text[:300]}")
        risultato = r.json().get("result")
        return risultato.get("message_id") if isinstance(risultato, dict) else modifica_id
    raise RuntimeError("Telegram: troppi tentativi")
