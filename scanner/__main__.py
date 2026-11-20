"""Scanner Acquaviva Notizie.

Uso:
    python -m scanner              giro normale: cerca e pubblica
    python -m scanner --prova      cerca e mostra cosa pubblicherebbe, senza inviare né salvare
    python -m scanner --semina     segna come visto tutto ciò che c'è ora, senza pubblicare
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import fonti as F
from .filtro import Filtro, estratto
from .memoria import Memoria
from .telegram import invia, post_telegram, post_whatsapp

RADICE = Path(__file__).resolve().parent.parent


def carica_yaml(nome: str) -> dict:
    return yaml.safe_load((RADICE / "config" / nome).read_text(encoding="utf-8"))


def raccogli(cfg: dict, memoria: Memoria, forza_arengo: bool) -> list[F.Articolo]:
    tutti: list[F.Articolo] = []
    for fonte in cfg["fonti"]:
        nome = fonte["nome"]
        try:
            if fonte["tipo"] == "rss":
                trovati = F.leggi_rss(fonte)
            elif fonte["tipo"] == "arengo":
                ore = memoria.ore_da("arengo")
                if not forza_arengo and ore < fonte.get("ogni_ore", 20):
                    print(f"- {nome}: controllate {ore:.0f} ore fa, salto")
                    continue
                anno = datetime.now(timezone.utc).year
                trovati = F.leggi_arengo(fonte, anno)
                memoria.segna_giro("arengo")
            else:
                print(f"- {nome}: tipo sconosciuto {fonte['tipo']!r}")
                continue
        except Exception as e:  # una fonte rotta non ferma le altre
            print(f"! {nome}: errore ({e})")
            continue
        print(f"- {nome}: {len(trovati)} elementi letti")
        tutti.extend(trovati)
    return tutti


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prova", action="store_true", help="non invia e non salva")
    ap.add_argument("--semina", action="store_true", help="segna tutto come visto senza pubblicare")
    args = ap.parse_args()

    cfg = carica_yaml("config.yaml")
    filtro = Filtro(carica_yaml("keywords.yaml"))
    memoria = Memoria(RADICE / "data" / "seen.json")
    # Al primo giro vero non si pubblica nulla: si segna come visto ciò che esiste già.
    semina = args.semina or (not memoria.inizializzata and not args.prova)
    if semina:
        print("MODALITÀ SEMINA: segno come già visto tutto ciò che esiste ora, senza pubblicare.")

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    canale = os.environ.get("TELEGRAM_CHAT_ID", "")
    privato = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")  # facoltativo: copia per WhatsApp
    if not args.prova and not semina and not (token and canale):
        print("Mancano i segreti TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID.")
        return 1

    articoli = raccogli(cfg, memoria, forza_arengo=semina or args.prova)
    limite_eta = datetime.now(timezone.utc) - timedelta(days=cfg.get("eta_massima_giorni", 3))

    da_pubblicare: list[tuple[F.Articolo, str]] = []
    visti_ora: set[str] = set()
    for art in articoli:
        if memoria.gia_visto(art.url, art.titolo) or art.url in visti_ora:
            continue
        visti_ora.add(art.url)
        if semina:
            memoria.segna(art.url, art.titolo)
            continue
        if art.controlla_eta and art.data and art.data < limite_eta:
            memoria.segna(art.url, art.titolo)
            continue
        testo = f"{art.titolo}\n{art.testo}"
        parola = filtro.controlla(testo, art.sammarinese)
        if not parola and art.testo_completo:
            time.sleep(0.5)
            testo = f"{art.titolo}\n{art.testo_completo()}"
            parola = filtro.controlla(testo, art.sammarinese)
        memoria.segna(art.url, art.titolo)
        if parola:
            da_pubblicare.append((art, f"{parola}: {estratto(testo, parola)}"))

    da_pubblicare.sort(key=lambda x: x[0].data or datetime.min.replace(tzinfo=timezone.utc))
    massimo = cfg.get("max_post_per_giro", 10)
    if len(da_pubblicare) > massimo:
        print(f"Trovati {len(da_pubblicare)} articoli: ne pubblico {massimo}, gli altri al prossimo giro.")
        for art, _ in da_pubblicare[massimo:]:
            memoria.dimentica(art.url, art.titolo)
        da_pubblicare = da_pubblicare[:massimo]

    print(f"\nDa pubblicare: {len(da_pubblicare)}")
    for art, parola in da_pubblicare:
        print(f"  [{parola}] {art.fonte}: {art.titolo}\n    {art.url}")
        if args.prova:
            continue
        try:
            invia(token, canale, post_telegram(art, cfg), anteprima=art.url)
            if privato:
                invia(token, privato, post_whatsapp(art, cfg), html_mode=False)
        except Exception as e:
            print(f"  ! invio non riuscito, riprovo al prossimo giro ({e})")
            memoria.dimentica(art.url, art.titolo)
        time.sleep(cfg.get("pausa_messaggi", 3))

    if args.prova:
        print("\nProva finita: nessun messaggio inviato, memoria non salvata.")
        return 0
    memoria.inizializzata = True
    memoria.salva()
    print("Memoria salvata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
