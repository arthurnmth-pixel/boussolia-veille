#!/usr/bin/env python3
"""Collecte automatique de la veille Boussolia -> data/veille.json
Aucune dépendance : bibliothèque standard Python uniquement.
On ne stocke que titre, source, date et lien (jamais le texte des articles)."""
import json, re, sys, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

OUT = Path(__file__).parent / "data" / "veille.json"
MAX_PER_AXE = 25
MAX_AGE_DAYS = 10

# Une recherche par rubrique (Google Actualités, flux RSS public).
# Modifiez librement les mots-clés ; "when:7d" limite aux 7 derniers jours.
AXES = {
    "Concurrence": '(MAIF OR Macif OR Groupama OR AXA OR Allianz OR MAAF OR GMF OR MGEN OR Matmut) assurance when:7d',
    "Réglementation": 'assurance (ACPR OR Orias OR décret OR réglementation OR DDA OR "France Assureurs") when:7d',
    "Produits & usages": 'assurance (auto OR habitation OR mutuelle OR prévoyance OR "RC pro") tarifs OR garanties when:7d',
    "Marché & économie": 'assurance (sinistralité OR "catastrophes naturelles" OR résultats OR marché) France when:7d',
    "Digital & IA": 'assurance ("intelligence artificielle" OR cyber OR fraude OR insurtech) when:7d',
}
# Flux RSS directs supplémentaires, si vous en connaissez : ("Rubrique", "https://…/rss")
EXTRA_FEEDS = []

HOT = re.compile(r"décret|acpr|sanction|amende|réforme|hausse|fraude|cyber|résiliation|loi\b", re.I)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Boussolia-Veille/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()

def parse(xml_bytes, axe):
    items = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        source = (it.findtext("source") or "").strip()
        if not source and " - " in title:           # format Google : « Titre - Média »
            title, source = title.rsplit(" - ", 1)
        elif source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        try:
            date = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            date = datetime.now(timezone.utc)
        items.append({
            "axe": axe, "title": title.strip(), "source": source or "Source non précisée",
            "date": date.date().isoformat(), "url": link,
            "prio": "À lire" if HOT.search(title) else "À suivre",
            "_ts": date.timestamp(),
        })
    return items

def main():
    feeds = [(axe, "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "fr", "gl": "FR", "ceid": "FR:fr"})) for axe, q in AXES.items()] + EXTRA_FEEDS
    allitems, ok = [], 0
    for axe, url in feeds:
        try:
            allitems += parse(fetch(url), axe); ok += 1
        except Exception as e:
            print(f"[avertissement] {axe}: {e}", file=sys.stderr)
    if not ok or not allitems:
        print("Aucune donnée récupérée : l'ancien veille.json est conservé.", file=sys.stderr)
        return 0
    now = datetime.now(timezone.utc).timestamp()
    seen, final, per = set(), [], {}
    for x in sorted(allitems, key=lambda x: -x["_ts"]):
        key = re.sub(r"\W+", "", x["title"].lower())[:80]
        if key in seen or now - x["_ts"] > MAX_AGE_DAYS * 86400:
            continue
        if per.get(x["axe"], 0) >= MAX_PER_AXE:
            continue
        seen.add(key); per[x["axe"]] = per.get(x["axe"], 0) + 1
        final.append({k: v for k, v in x.items() if k != "_ts"})
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"generated": datetime.now(timezone.utc).isoformat(), "items": final},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(final)} articles écrits dans {OUT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
