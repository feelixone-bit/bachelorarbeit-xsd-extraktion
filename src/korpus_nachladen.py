"""Lädt den Artikelkorpus aus dem Manifest nach.

Der Volltext-Korpus selbst ist aus urheberrechtlichen Gründen nicht Teil des
Repositorys (siehe corpus/README.md). Dieses Skript stellt ihn aus den im
Manifest hinterlegten Quell-URLs wieder her: Es ruft jede Seite ab, extrahiert
den Haupttext mit trafilatura und legt pro Artikel eine Textdatei mit
Metadatenkopf unter corpus/ ab.

Hinweis: Das Ergebnis entspricht der trafilatura-Extraktion, nicht der manuell
bereinigten Korpusfassung der Arbeit. Beide unterscheiden sich an Randstellen
(Boilerplate-Reste, Zwischenüberschriften); der Vergleich ist im
trafilatura_demonstrator dokumentiert.

Aufruf (aus dem Repository-Wurzelverzeichnis):
    python src/korpus_nachladen.py
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import trafilatura

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"
MANIFEST = CORPUS_DIR / "corpus_manifest.csv"
ABSTAND_SEKUNDEN = 1.0  # höflicher Mindestabstand zwischen den Abrufen


def extrahiere(html: str) -> str:
    """Haupttext mit für Nachrichtenartikel sinnvollen Optionen extrahieren."""
    return trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        include_images=False,
        include_links=False,
        favor_precision=True,
        output_format="txt",
    ) or ""


def lade_manifest() -> list[dict]:
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    eintraege = lade_manifest()
    print(f"Manifest: {len(eintraege)} Artikel — Abruf nach {CORPUS_DIR}\n")
    fehlgeschlagen = []

    for e in eintraege:
        aid, url = e["artikel_id"], e["url"]
        html = trafilatura.fetch_url(url)
        if not html:
            print(f"  {aid}  ABRUF FEHLGESCHLAGEN/BLOCKIERT: {url}")
            fehlgeschlagen.append(aid)
            continue

        text = extrahiere(html)
        kopf = (f"Artikel-ID: {aid}\n"
                f"Situation: {e['situation']}\n"
                f"Quelle: {e['quelle']}\n"
                f"URL: {url}\n"
                f"Abrufdatum (Original): {e['abrufdatum']}\n")
        ziel = CORPUS_DIR / f"article_{aid}_nachgeladen.txt"
        ziel.write_text(kopf + "\nArtikeltext:\n" + text, encoding="utf-8")
        print(f"  {aid}  ok  ({len(text.split())} Wörter)")
        time.sleep(ABSTAND_SEKUNDEN)

    print(f"\nFertig. {len(eintraege) - len(fehlgeschlagen)}/{len(eintraege)} "
          f"Artikel nachgeladen.")
    if fehlgeschlagen:
        print(f"Nicht abrufbar: {', '.join(fehlgeschlagen)} — Skript erneut "
              f"starten oder URL im Manifest prüfen.")


if __name__ == "__main__":
    main()
