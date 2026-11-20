import requests, re, pathlib
from urllib.parse import urljoin
from bs4 import BeautifulSoup
out = pathlib.Path("sonda/out"); out.mkdir(parents=True, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
log = []
def get(u):
    r = requests.get(u, headers=H, timeout=60); log.append(f"{r.status_code} {len(r.content)} {r.url}"); return r
home = get("https://www.interni.sm/")
(out/"home.html").write_bytes(home.content)
s = BeautifulSoup(home.content, "lxml")
cand = sorted({urljoin(home.url, a["href"]) for a in s.find_all("a", href=True) if "ordinanz" in (a["href"]+a.get_text()).lower()})
log += ["CAND " + c for c in cand]
for i, c in enumerate(cand[:6]):
    try:
        r = get(c); (out/f"p{i}.html").write_bytes(r.content)
        ss = BeautifulSoup(r.content, "lxml")
        pdfs = [urljoin(r.url, a["href"]) for a in ss.find_all("a", href=True) if ".pdf" in a["href"].lower()]
        log.append(f"  pdf in p{i}: {len(pdfs)}"); log += ["   " + p for p in pdfs[:8]]
        subs = sorted({urljoin(r.url, a["href"]) for a in ss.find_all("a", href=True) if "ordinanz" in (a["href"]+a.get_text()).lower()})
        log += ["   SUB " + x for x in subs[:30]]
    except Exception as e:
        log.append(f"ERR {c} {e}")
(out/"log.txt").write_text("\n".join(log))
