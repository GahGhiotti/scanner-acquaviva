from pathlib import Path

import yaml

from scanner.filtro import Filtro, normalizza
from scanner.fonti import estrai_istanze

PAROLE = yaml.safe_load((Path(__file__).parent.parent / "config" / "keywords.yaml").read_text(encoding="utf-8"))
f = Filtro(PAROLE)


def test_normalizza_apostrofi_e_accenti():
    assert normalizza("Cà Martino") == normalizza("Ca' Martino") == normalizza("CA’ MARTINO") == " ca martino "


def test_istanza_21_dal_titolo():
    titolo = ("Istanza d'Arengo n.21 del 04-10-2026 - Al fine di procedere con l’asfaltatura e la messa "
              "in sicurezza del tratto stradale “Rio Re – Cà Martino – Cà Amadore”")
    assert f.controlla(titolo, sammarinese=True) is not None


def test_istanza_21_dal_testo():
    testo = ("Nell'anno 2019, all'interno del territorio del Castello di Acquaviva, è stata espropriata "
             "una porzione di terreno sito in località Gaviano")
    assert f.controlla(testo, sammarinese=True) == "castello di acquaviva"


def test_acquaviva_delle_fonti_scartata():
    assert f.controlla("Incidente ad Acquaviva delle Fonti, due feriti", sammarinese=False) is None
    assert f.controlla("Acquaviva delle Fonti: festa patronale a San Marino di Bitonto", sammarinese=True) is None


def test_gualdicciolo_basta_da_solo():
    assert f.controlla("Lavori stradali a Gualdicciolo", sammarinese=False) == "gualdicciolo"


def test_acquaviva_da_giornale_sammarinese():
    assert f.controlla("Nuovo parco giochi ad Acquaviva", sammarinese=True) == "acquaviva"


def test_acquaviva_da_giornale_italiano_serve_contesto():
    assert f.controlla("Concerto ad Acquaviva", sammarinese=False) is None
    assert f.controlla("San Marino, concerto ad Acquaviva", sammarinese=False) == "acquaviva"


def test_parole_deboli():
    assert f.controlla("Italo, nuove tratte per l'estate", sammarinese=False) is None
    assert f.controlla("Treno Italo in ritardo, disagi per i sammarinesi", sammarinese=True) is None
    assert f.controlla("San Marino: gara al poligono di tiro", sammarinese=True) == "poligono di tiro"


def test_parola_intera():
    assert f.controlla("San Marino: italiano e matematica", sammarinese=True) is None


def test_estrai_istanze_da_html():
    html = """<table><tr id="riga1"><td></td><td>04/10/2026</td>
    <td><div id="card_17195707">Istanza d'Arengo n.21 del 04-10-2026 - Rio Re</div></td>
    <td>Istanza d'Arengo</td><td><a href="/on-line/home/lavori-consiliari/consultazione-archivi/scheda17195707.html?tornalista=1">x</a></td></tr>
    <tr id="riga2"><td></td><td>13/11/2026</td><td><div id="card_1">Progetto di legge</div></td>
    <td>Progetto di Legge</td><td><a href="/scheda1.html">x</a></td></tr></table>"""
    ist = estrai_istanze(html, {"nome": "Consiglio Grande e Generale"},
                         "https://www.consigliograndeegenerale.sm/on-line/home/lavori-consiliari/consultazione-archivi.html")
    assert len(ist) == 1
    assert ist[0].url.endswith("scheda17195707.html")
    assert f.controlla(ist[0].titolo, True) == "rio re"


def test_indirizzo_di_chi_firma_non_conta():
    from scanner.fonti import togli_dati_personali
    testo = ("Il sottoscritto Mario Rossi, nato a San Marino il 1 gennaio 1960, residente in via Gualdicciolo "
             "n. 12, Acquaviva, chiede che venga migliorata la Superstrada.")
    assert f.controlla(togli_dati_personali(testo), sammarinese=True) is None
    assert f.controlla(togli_dati_personali("Lavori nel Castello di Acquaviva"), True) == "castello di acquaviva"


def test_italo_nome_proprio_non_conta():
    assert f.controlla("San Marino, firmato: Italo Bianchi", sammarinese=True) is None


def test_contenuto_su_vie_e_abitanti_resta():
    from scanner.fonti import togli_dati_personali
    testo = "La via Rivo Fontanelle è gravata dal traffico. Gli abitanti di Gualdicciolo chiedono un intervento."
    assert f.controlla(togli_dati_personali(testo), sammarinese=True) == "gualdicciolo"


def test_virtus():
    assert f.controlla("Campionato: Virtus-Tre Fiori 2-1", sammarinese=True) == "virtus"
    assert f.controlla("Virtus Bike, grande festa per la granfondo", sammarinese=True) is None
    assert f.controlla("Basket, la Virtus Bologna vince", sammarinese=False) is None


def test_estrai_ordinanze():
    from scanner.fonti import estrai_ordinanze
    html = ('<a href="/pub1/InterniSM/dam/jcr:abc/Ordinanza%20n.224-2026.pdf" '
            'aria-label="Ordinanza n.224-2026 Festa di fine estate4 settembre 2026 (opens in a new tab)">x</a>')
    o = estrai_ordinanze(html, {"nome": "Ordinanze Affari Interni"}, "https://www.interni.sm/x.html")
    assert len(o) == 1
    assert o[0].titolo == "Ordinanza n.224-2026 – Festa di fine estate – 4 settembre 2026"
    assert o[0].url.startswith("https://www.interni.sm/pub1/")
    testo = "Vista la richiesta della Giunta di Castello di Acquaviva, chiusura di Strada Molino Genga"
    assert f.controlla(testo, True) == "castello di acquaviva"


def test_bocce_e_scuole():
    assert f.controlla("Bocce: la Società Bocciofila Montecerreto vince il torneo", sammarinese=False) is not None
    # da un giornale sammarinese basta "Acquaviva"
    assert f.controlla("Festa di Natale alla scuola dell'infanzia di Acquaviva", sammarinese=True) == "acquaviva"
    # da un giornale italiano no: potrebbe essere Acquaviva Picena o delle Fonti
    assert f.controlla("Festa di Natale alla scuola dell'infanzia di Acquaviva", sammarinese=False) is None
    assert f.controlla("San Marino, recita alla scuola Il Faro Bianco", sammarinese=True) == "faro bianco"


def test_scuole_e_chiesa():
    assert f.controlla("San Marino: open day al nido Bruco Verde", sammarinese=True) == "bruco verde"
    assert f.controlla("Recita di Natale alla scuola dell'infanzia Il Girotondo, San Marino", sammarinese=True) is not None
    assert f.controlla("Concerto nella chiesa di Sant'Andrea Apostolo, San Marino", sammarinese=True) is not None
    # senza riferimenti a San Marino non conta (ci sono tante chiese di Sant'Andrea)
    assert f.controlla("Restauro della chiesa di Sant'Andrea Apostolo a Venezia", sammarinese=False) is None
    # "girotondo" da solo è una parola comune
    assert f.controlla("San Marino, un girotondo in piazza per la pace", sammarinese=True) is None


def test_post_telegram_link_corto():
    from scanner.fonti import Articolo
    from scanner.telegram import post_telegram
    cfg = yaml.safe_load((Path(__file__).parent.parent / "config" / "config.yaml").read_text(encoding="utf-8"))
    url = "https://news.google.com/rss/articles/CBMiAAA?oc=5&x=<1>"
    t = post_telegram(Articolo("Virtus & Fiorentino", url, "Calcio a 5 Anteprima", False), cfg)
    assert "<a href=\"https://news.google.com/rss/articles/CBMiAAA?oc=5&amp;x=&lt;1&gt;\">Leggi l'articolo</a>" in t
    assert "<b>Virtus &amp; Fiorentino</b>" in t
    assert t.startswith("⚽ SPORT · CALCIO\n")
    assert "\nhttps://news.google.com" not in t


def test_categorie():
    from scanner.fonti import Articolo
    from scanner.telegram import categoria
    cfg = yaml.safe_load((Path(__file__).parent.parent / "config" / "config.yaml").read_text(encoding="utf-8"))
    def cat(titolo, url="https://x/a", fonte="San Marino RTV", parola=""):
        a = Articolo(titolo, url, fonte, True)
        a.nome_fonte_config = fonte
        a.parola = parola
        return categoria(a, cfg)[1]
    assert cat("Ordinanza n.224-2026 – Festa di fine estate", fonte="Ordinanze Affari Interni") == "Viabilità"
    assert cat("Istanza d'Arengo n.21 – Rio Re", fonte="Consiglio Grande e Generale") == "Istanze d'Arengo"
    assert cat("Virtus-Tre Fiori 2-1") == "Sport · Calcio"
    assert cat("La Bocciofila Montecerreto vince") == "Sport · Bocce"
    assert cat("Gara al crossodromo della Baldasserona") == "Sport · Motori"
    assert cat("Atletica, buoni risultati", url="https://www.sanmarinortv.sm/sport/altri-c19/x") == "Sport"
    assert cat("Recita al nido Bruco Verde") == "Scuola"
    assert cat("Nuovo parco giochi ad Acquaviva") == "Notizie"


def test_categoria_da_descrizione_e_categorie_rss():
    from scanner.fonti import Articolo
    from scanner.telegram import categoria
    cfg = yaml.safe_load((Path(__file__).parent.parent / "config" / "config.yaml").read_text(encoding="utf-8"))
    a = Articolo("San Marino Academy, gli Under 22 ripartono contro la Libertas", "https://insider.sm/x", "Insider", True,
                 etichette="Sport Dopo due settimane di pausa, gli Under 22 della San Marino Academy tornano in campo")
    assert categoria(a, cfg)[1] == "Sport · Calcio"
    b = Articolo("Atletica, buoni risultati", "https://insider.sm/y", "Insider", True, etichette="Sport")
    assert categoria(b, cfg)[1] == "Sport"


def test_indirizzo_insider_non_conta():
    pie_di_pagina = "Insider.sm – Via Rivo Fontanelle 125 – 47892 Acquaviva (RSM)"
    assert f.controlla("Borsa, giornata positiva. " + pie_di_pagina, sammarinese=True) is None
    assert f.controlla("Si gioca allo stadio di Acquaviva. " + pie_di_pagina, sammarinese=True) == "acquaviva"


def test_sport_conta_la_squadra():
    # partita di altre squadre allo stadio di Acquaviva: no
    assert f.controlla("Tre Fiori-Libertas 1-1, si gioca allo stadio di Acquaviva", True, sportivo=True) is None
    # squadra di casa: sì, ovunque giochi
    assert f.controlla("Virtus-Tre Fiori 2-1 a Serravalle", True, sportivo=True) == "virtus"
    assert f.controlla("Bocce: la Bocciofila Montecerreto vince a Rimini, San Marino", False, sportivo=True) is not None
    # Nazionale e Academy solo se giocano ad Acquaviva
    assert f.controlla("Under 22 della San Marino Academy, si gioca allo stadio di Acquaviva", True, sportivo=True)
    assert f.controlla("San Marino Academy, trasferta a Forlì", True, sportivo=True) is None
    assert f.controlla("Futsal, la Nazionale si allena ad Acquaviva", True, sportivo=True)
    assert f.controlla("Calcio, la Nazionale gioca a Serravalle", True, sportivo=True) is None
    # luoghi forti valgono anche nello sport
    assert f.controlla("Rally, prova speciale da Gualdicciolo a Montecerreto", True, sportivo=True) is not None
    # Virtus Bike: no, a meno che la gara passi per Acquaviva
    assert f.controlla("Virtus Bike, granfondo a Domagnano", True, sportivo=True) is None
    assert f.controlla("Virtus Bike, la granfondo passa per Acquaviva e Gualdicciolo", True, sportivo=True)
    assert f.controlla("Virtus Bike, il percorso attraversa Acquaviva", True, sportivo=True) == "acquaviva"
    # eventi non ufficiali ad Acquaviva: sì
    assert f.controlla("Partita di beneficenza allo stadio di Acquaviva", True, sportivo=True)
    assert f.controlla("Nazionale cantanti in campo ad Acquaviva per la raccolta fondi", True, sportivo=True)
    assert f.controlla("Partita di beneficenza a Serravalle", True, sportivo=True) is None
