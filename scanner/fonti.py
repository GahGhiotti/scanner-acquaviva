"""Lettura delle fonti: feed RSS, pagine degli articoli e istanze d'arengo."""

from __future__ import annotations

import email.utils
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 scanner-acquaviva",
    "Accept-Language": "it-IT,it;q=0.9",
}
TIMEOUT = 45


@dataclass
class Articolo:
    titolo: str
    url: str
    fonte: str
    sammarinese: bool
    testo: str = ""
    data: datetime | None = None
    # Funzione che, se serve, recupera il testo completo (pagina o PDF).
    testo_completo: Callable[[], str] | None = field(default=None, repr=False)
    controlla_eta: bool = True
    fonte_nuova: bool = False
    parola: str = ""
    nome_fonte_config: str = ""
    # Categorie del feed (es. "Sport", "Calcio") e inizio della descrizione: servono a scegliere la categoria del post.
    etichette: str = ""


def scarica(url: str) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r


def testo_da_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()
    corpo = soup.find("article") or soup.find("main") or soup.body or soup
    return corpo.get_text(" ", strip=True)


def leggi_pagina(url: str) -> str:
    try:
        r = scarica(url)
        return testo_da_html(r.text)[:30000]
    except Exception as e:  # una pagina che non si apre non deve fermare lo scanner
        print(f"    pagina non leggibile: {url} ({e})")
        return ""


# ---------------------------------------------------------------- RSS


def _figlio(item, nome: str) -> str:
    for c in item:
        tag = c.tag.split("}")[-1]
        if tag == nome:
            return (c.text or "").strip()
    return ""


def _data(s: str) -> datetime | None:
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def leggi_rss(fonte: dict) -> list[Articolo]:
    articoli = []
    urls = fonte["url"] if isinstance(fonte["url"], list) else [fonte["url"]]
    for url in urls:
        try:
            r = scarica(url)
            radice = ET.fromstring(r.content)
        except Exception as e:
            print(f"  ! feed non leggibile: {url} ({e})")
            continue
        items = [el for el in radice.iter() if el.tag.split("}")[-1] in ("item", "entry")]
        for it in items:
            titolo = _figlio(it, "title")
            link = _figlio(it, "link")
            if not link:  # Atom
                for c in it:
                    if c.tag.split("}")[-1] == "link" and c.get("href"):
                        link = c.get("href")
                        break
            if not titolo or not link:
                continue
            descr = _figlio(it, "description") or _figlio(it, "summary")
            contenuto = _figlio(it, "encoded") or _figlio(it, "content")
            testo = BeautifulSoup(f"{descr} {contenuto}", "lxml").get_text(" ", strip=True)
            nome_fonte = fonte["nome"]
            if fonte.get("google_news"):
                giornale = _figlio(it, "source")
                if giornale:
                    nome_fonte = giornale
                    if titolo.endswith(" - " + giornale):
                        titolo = titolo[: -len(" - " + giornale)]
                testo = ""  # la descrizione di Google News ripete solo il titolo
            categorie_rss = " ".join(
                (c.text or "").strip() for c in it if c.tag.split("}")[-1] == "category" and c.text
            )
            art = Articolo(
                titolo=titolo,
                url=link,
                fonte=nome_fonte,
                etichette=f"{categorie_rss} {testo[:300]}",
                sammarinese=bool(fonte.get("sammarinese")),
                testo=testo,
                data=_data(_figlio(it, "pubDate") or _figlio(it, "published") or _figlio(it, "updated")),
            )
            if fonte.get("leggi_articolo"):
                art.testo_completo = (lambda u=link: leggi_pagina(u))
            articoli.append(art)
    return articoli


# ---------------------------------------------------------------- Istanze d'arengo

ARCHIVIO = "https://www.consigliograndeegenerale.sm/on-line/home/lavori-consiliari/consultazione-archivi.html"
Q = "#doppiapici;"  # il sito codifica così le virgolette


def _decodifica(r: requests.Response) -> str:
    return r.content.decode("cp1252", errors="replace")


def _senza_query(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def testo_pdf(url: str) -> str:
    """Testo di un PDF: prima il testo vero, poi l'OCR se il PDF è una scansione."""
    try:
        r = scarica(url)
    except Exception as e:
        print(f"    PDF non scaricabile: {url} ({e})")
        return ""
    with tempfile.TemporaryDirectory() as d:
        pdf = Path(d) / "doc.pdf"
        pdf.write_bytes(r.content)
        return testo_da_file_pdf(pdf)


def testo_da_file_pdf(pdf: Path) -> str:
    try:
        testo = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, timeout=120
        ).stdout
    except Exception as e:
        print(f"    pdftotext non disponibile ({e})")
        testo = ""
    if len(testo.strip()) >= 200:
        return testo
    # Scansione: OCR pagina per pagina (massimo 5 pagine).
    try:
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(
                ["pdftoppm", "-r", "300", "-l", "5", "-png", str(pdf), str(Path(d) / "p")],
                check=True, capture_output=True, timeout=300,
            )
            pagine = []
            for img in sorted(Path(d).glob("p*.png")):
                out = subprocess.run(
                    ["tesseract", str(img), "stdout", "-l", "ita"],
                    capture_output=True, text=True, timeout=300,
                )
                pagine.append(out.stdout)
            return "\n".join(pagine)
    except Exception as e:
        print(f"    OCR non riuscito ({e})")
        return testo


def leggi_arengo(fonte: dict, anno: int) -> list[Articolo]:
    descr = (
        f"+{Q}Istanza d'Arengo{Q} AND -{Q}Permuta-Assegnazione{Q}"
        f" AND -{Q}Provvedimenti in materia di cittadinanza{Q}"
    )
    params = {
        "P0_path": "/home/tomcat/indicizzazione/indexarchivio",
        "P0_paginazione": "120",
        "P0_maxresults": "120",
        "P0_pagina": "1",
        "indicericerca": "-1",
        "P0_orderBy": "index_lucene,data_presentazione_ordered",
        "P0_order": "asc,desc",
        "P0_title": "",
        "idCardLevel": "17000628",
        "P0_description": descr,
        "P0_data_presentazione_gg": "",
        "P0_data_presentazione_mm": "",
        "P0_data_presentazione_aa": str(anno),
        "P0_presentatori": "",
    }
    r = requests.get(ARCHIVIO, params=params, headers=HEADERS, timeout=90)
    r.raise_for_status()
    return estrai_istanze(_decodifica(r), fonte, r.url)


def estrai_istanze(html: str, fonte: dict, base_url: str = ARCHIVIO) -> list[Articolo]:
    soup = BeautifulSoup(html, "lxml")
    articoli = []
    for tr in soup.find_all("tr", id=re.compile(r"^riga")):
        celle = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        if not any("Istanza d'Arengo" in c for c in celle):
            continue
        a = tr.find("a", href=re.compile(r"scheda\d+"))
        div = tr.find("div", id=re.compile(r"^card_"))
        if not a or not div:
            continue
        titolo = div.get_text(" ", strip=True)
        scheda = _senza_query(urljoin(base_url, a["href"]))
        art = Articolo(
            titolo=titolo,
            url=scheda,
            fonte=fonte.get("nome", "Consiglio Grande e Generale"),
            sammarinese=True,
            testo=titolo,
            controlla_eta=False,
        )
        art.testo_completo = (lambda u=scheda: _testo_istanza(u))
        articoli.append(art)
    return articoli


def _testo_istanza(scheda_url: str) -> str:
    try:
        r = scarica(scheda_url)
    except Exception as e:
        print(f"    scheda non leggibile: {scheda_url} ({e})")
        return ""
    soup = BeautifulSoup(_decodifica(r), "lxml")
    # Solo il PDF dell'istanza stessa: le schede possono collegare anche documenti
    # comuni a più istanze (relazioni, risposte), che darebbero risultati sbagliati.
    link = soup.find_all("a", href=re.compile(r"documento\d+"))
    propri = [a for a in link if "istanza" in (a.get("title") or "").lower()] or link[:1]
    testi = [testo_pdf(urljoin(scheda_url, a["href"])) for a in propri]
    return togli_dati_personali("\n".join(testi))


DATI_PERSONALI = re.compile(
    r"(?i)\b(resident\w*|nat[oa]\s+a|domiciliat\w*|indirizzo|tel\.?|e-?mail)\b"
)


def togli_dati_personali(testo: str) -> str:
    """Nelle istanze toglie indirizzi e dati di chi firma.

    Senza questo, un'istanza firmata da chi abita a Gualdicciolo verrebbe
    pubblicata anche se parla d'altro. Toglie i 150 caratteri dopo parole
    come "residente", "nato a", "domiciliato".
    """
    pezzi, inizio = [], 0
    for m in DATI_PERSONALI.finditer(testo):
        if m.start() < inizio:
            continue
        pezzi.append(testo[inizio:m.start()])
        inizio = m.end() + 150
    pezzi.append(testo[inizio:])
    return " ".join(pezzi)


# ---------------------------------------------------------------- Ordinanze (Segreteria Affari Interni)

ORDINANZE = "https://www.interni.sm/pub1/InterniSM/Ordinanze/Ordinanze{anno}.html"


def leggi_ordinanze(fonte: dict, anno: int) -> list[Articolo]:
    """Ordinanze di chiusura strade e simili: il testo si legge dal PDF."""
    r = scarica(ORDINANZE.format(anno=anno))
    return estrai_ordinanze(r.text, fonte, r.url)


def estrai_ordinanze(html: str, fonte: dict, base_url: str) -> list[Articolo]:
    soup = BeautifulSoup(html, "lxml")
    articoli, visti = [], set()
    for a in soup.find_all("a", href=re.compile(r"Ordinanza.*\.pdf", re.I)):
        url = urljoin(base_url, a["href"])
        if url in visti:
            continue
        visti.add(url)
        titolo = (a.get("aria-label") or a.get_text(" ", strip=True)).replace("(opens in a new tab)", "").strip()
        titolo = re.sub(r"(\S)(\d{1,2} \w+ \d{4})$", r"\1 – \2", titolo)
        titolo = re.sub(r"^(Ordinanza n\.\s?\d+-\d{4})\s*", r"\1 – ", titolo)
        art = Articolo(
            titolo=titolo, url=url, fonte=fonte.get("nome", "Segreteria Affari Interni"),
            sammarinese=True, testo=titolo, controlla_eta=False,
        )
        art.testo_completo = (lambda u=url: testo_pdf(u))
        articoli.append(art)
    return articoli
