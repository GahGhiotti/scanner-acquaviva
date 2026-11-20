# Scanner Acquaviva Notizie

Ogni ora controlla i giornali sammarinesi, i giornali italiani (tramite Google News) e le istanze d'arengo del Consiglio Grande e Generale. Le notizie sul Castello di Acquaviva le pubblica sul canale Telegram **Acquaviva Notizie**.

Gira gratis su GitHub Actions: non serve nessun computer acceso.

## Come funziona

1. Ogni ora, al minuto 17, GitHub avvia lo scanner.
2. Lo scanner legge le fonti elencate in `config/config.yaml`.
3. Ogni articolo nuovo passa dal filtro delle parole chiave (`config/keywords.yaml`). Se il feed non basta, legge anche la pagina dell'articolo. Le istanze d'arengo scansionate vengono lette con l'OCR.
4. Gli articoli che passano il filtro vengono pubblicati sul canale Telegram.
5. Lo scanner si ricorda cosa ha già visto (`data/seen.json`), così non pubblica mai due volte la stessa notizia.

Al **primo giro** non pubblica niente: segna come già visto tutto ciò che esiste in quel momento, per non inondare il canale di notizie vecchie.

## Cose che puoi fare da solo

**Cambiare le parole chiave.** Apri `config/keywords.yaml` → icona della matita → modifica → **Commit changes**. Il file spiega quali parole bastano da sole e quali hanno bisogno di un contesto.

**Cambiare nome del canale, link o firma.** Stesso procedimento con `config/config.yaml`.

**Fare una prova senza pubblicare.** Scheda **Actions** → *Scanner Acquaviva Notizie* → **Run workflow** → modalità `prova`. Apri l'esecuzione e il passaggio *Scansione*: vedi cosa verrebbe pubblicato e quale parola l'ha fatto scattare.

**Mettere in pausa lo scanner.** Scheda **Actions** → *Scanner Acquaviva Notizie* → menu `...` → **Disable workflow**. Per riattivarlo: **Enable workflow**.

**Ricevere in privato la versione per WhatsApp (facoltativo).** Scrivi `/start` al bot su Telegram, poi trova il tuo ID personale come hai fatto per il canale. Salvalo come segreto `TELEGRAM_ADMIN_CHAT_ID`: da quel momento, dopo ogni post sul canale, il bot ti manda in privato il testo pronto da incollare su WhatsApp.

## Segreti necessari

In *Settings → Secrets and variables → Actions*:

| Nome | Cosa contiene |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Il token dato da BotFather |
| `TELEGRAM_CHAT_ID` | L'ID numerico del canale (inizia con `-100`) |
| `TELEGRAM_ADMIN_CHAT_ID` | Facoltativo: il tuo ID personale, per la copia WhatsApp |

## Per chi modifica il codice

- `scanner/fonti.py`: lettura di feed RSS, pagine e istanze d'arengo (con OCR).
- `scanner/filtro.py`: regole delle parole chiave.
- `scanner/telegram.py`: formato dei post e invio.
- `scanner/memoria.py`: articoli già visti.
- Test: `python -m pytest -q tests`. Prova locale: `python -m scanner --prova`.
