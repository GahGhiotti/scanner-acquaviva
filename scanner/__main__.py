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
from .doppioni import priorita, stessa_notizia
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
        inizio = time.monotonic()
        try:
            if fonte["tipo"] == "rss":
                trovati = F.leggi_rss(fonte)
            elif fonte["tipo"] == "ordinanze":
                trovati = F.leggi_ordinanze(fonte, datetime.now(timezone.utc).year)
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
        nuova = f"fonte:{nome}" not in memoria.ultimo
        for art in trovati:
            art.nome_fonte_config = nome
            art.fonte_nuova = nuova  # fonte appena aggiunta: al primo giro non pubblica
        memoria.ultimo[f"fonte:{nome}"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        durata = time.monotonic() - inizio
        print(f"- {nome}: {len(trovati)} elementi letti in {durata:.0f} s" + (" (fonte nuova: semina)" if nuova else ""))
        tutti.extend(trovati)
    return tutti


def in_dizionario(art: F.Articolo) -> dict:
    return {"titolo": art.titolo, "url": art.url, "fonte": art.fonte,
            "nome_fonte_config": art.nome_fonte_config, "parola": art.parola}


def da_dizionario(d: dict) -> F.Articolo:
    return F.Articolo(d["titolo"], d["url"], d["fonte"], True,
                      parola=d.get("parola", ""), nome_fonte_config=d.get("nome_fonte_config", ""))


def test_messaggio(cfg: dict) -> int:
    """Verifica i segreti: il bot scrive in privato a Gah un esempio di post per WhatsApp."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    privato = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "")
    print("TELEGRAM_BOT_TOKEN:", "presente" if token else "MANCANTE")
    print("TELEGRAM_CHAT_ID:", "presente" if os.environ.get("TELEGRAM_CHAT_ID") else "MANCANTE")
    print("TELEGRAM_ADMIN_CHAT_ID:", "presente" if privato else "MANCANTE")
    if not (token and privato):
        return 1
    esempio = F.Articolo(
        "Esempio: Virtus-Tre Fiori 2-1", "https://www.sanmarinortv.sm/sport", "San Marino RTV", True, parola="virtus"
    )
    try:
        invia(token, privato, "✅ Test riuscito: d'ora in poi ricevi qui la versione per WhatsApp di ogni post.", html_mode=False)
        invia(token, privato, post_whatsapp(esempio, cfg), html_mode=False)
    except Exception as e:
        print(f"Invio non riuscito: {e}")
        return 1
    print("Messaggio di prova inviato.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prova", action="store_true", help="non invia e non salva")
    ap.add_argument("--semina", action="store_true", help="segna tutto come visto senza pubblicare")
    ap.add_argument("--test-messaggio", action="store_true", help="manda un messaggio di prova in privato")
    args = ap.parse_args()

    if args.test_messaggio:
        return test_messaggio(carica_yaml("config.yaml"))

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

    # Le fonti presenti fin dal primo giro (20/11/2026) sono già state seminate.
    if memoria.inizializzata and not any(k.startswith("fonte:") for k in memoria.ultimo):
        for n in ("San Marino RTV", "GiornaleSM", "Insider", "Libertas", "Google News", "Consiglio Grande e Generale"):
            memoria.ultimo[f"fonte:{n}"] = "2026-11-20T14:44:12+00:00"

    articoli = raccogli(cfg, memoria, forza_arengo=semina or args.prova)
    limite_eta = datetime.now(timezone.utc) - timedelta(days=cfg.get("eta_massima_giorni", 3))

    t0 = time.monotonic()
    da_pubblicare: list[tuple[F.Articolo, str]] = []
    visti_ora: set[str] = set()
    for art in articoli:
        if memoria.gia_visto(art.url, art.titolo) or art.url in visti_ora:
            continue
        visti_ora.add(art.url)
        if semina or (art.fonte_nuova and not args.prova):
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
            art.parola = parola
            da_pubblicare.append((art, f"{parola}: {estratto(testo, parola)}"))

    print(f"Controllo degli articoli finito in {time.monotonic() - t0:.0f} s")
    da_pubblicare.sort(key=lambda x: x[0].data or datetime.min.replace(tzinfo=timezone.utc))
    massimo = cfg.get("max_post_per_giro", 10)
    if len(da_pubblicare) > massimo:
        print(f"Trovati {len(da_pubblicare)} articoli: ne pubblico {massimo}, gli altri al prossimo giro.")
        for art, _ in da_pubblicare[massimo:]:
            memoria.dimentica(art.url, art.titolo)
        da_pubblicare = da_pubblicare[:massimo]

    print(f"\nDa pubblicare: {len(da_pubblicare)}")
    # Le fonti più importanti per prime: se la stessa notizia arriva da più giornali,
    # il post è quello della fonte principale e gli altri compaiono come "Anche su".
    da_pubblicare.sort(key=lambda x: priorita(x[0].nome_fonte_config, cfg))
    adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for art, motivo in da_pubblicare:
        print(f"  [{motivo}] {art.fonte}: {art.titolo}\n    {art.url}")
        gia = next(
            (p for p in memoria.pubblicati if any(stessa_notizia(a["titolo"], art.titolo) for a in p["articoli"])),
            None,
        )
        if gia:
            gia["articoli"].append(in_dizionario(art))
            gia["articoli"].sort(key=lambda a: priorita(a.get("nome_fonte_config", ""), cfg))
            print(f"    stessa notizia di un post già uscito: aggiungo la fonte \"{art.fonte}\" a quel post")
            if args.prova:
                continue
            articoli_post = [da_dizionario(a) for a in gia["articoli"]]
            principale = articoli_post[0]
            try:
                invia(token, canale, post_telegram(principale, cfg, articoli_post[1:]),
                      anteprima=principale.url, modifica_id=gia["id"])
            except Exception as e:  # es. post cancellato a mano: non riprovare all'infinito
                print(f"  ! non riesco a modificare il post esistente ({e})")
            time.sleep(cfg.get("pausa_messaggi", 3))
            continue
        if args.prova:
            memoria.pubblicati.append({"id": None, "data": adesso, "articoli": [in_dizionario(art)]})
            continue
        try:
            mid = invia(token, canale, post_telegram(art, cfg), anteprima=art.url)
            memoria.pubblicati.append({"id": mid, "data": adesso, "articoli": [in_dizionario(art)]})
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
