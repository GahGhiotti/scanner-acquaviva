import requests, pathlib
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
out = pathlib.Path("sonda/out"); out.mkdir(parents=True, exist_ok=True)
pagine = {
 "smrtv1.html": "https://www.sanmarinortv.sm/news/politica-c2/ex-tiro-a-volo-al-via-l-iter-della-legge-di-iniziativa-popolare-a299096",
 "giornalesm.html": "https://giornalesm.com/le-cinque-principali-notizie-della-mattina-italia-di-mercoledi-18-novembre-2026/",
 "libertas.html": "https://www.libertas.sm/san-marino-al-via-lo-screening-per-la-diagnosi-precoce-del-tumore-al-polmone/",
 "insider.html": "https://insider.sm/san-marino-academy-gli-under-22-ripartono-contro-la-libertas/",
}
for n, u in pagine.items():
    try:
        r = requests.get(u, headers=H, timeout=60); (out/n).write_bytes(r.content)
    except Exception as e:
        (out/(n+".err")).write_text(str(e))
