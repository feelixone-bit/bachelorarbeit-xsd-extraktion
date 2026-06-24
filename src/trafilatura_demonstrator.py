"""Demonstrator zum Vergleich der trafilatura-Extraktion mit der manuellen
Korpusbereinigung.

Ruft die Original-URL eines Artikels ab, extrahiert den Haupttext mit
trafilatura und stellt ihn der bereinigten Korpusfassung gegenueber:
Boilerplate-Reste, erhaltene Zwischenueberschriften, Wortzahl, Anfang/Ende.

Der Korpus bleibt unangetastet — das Skript liest die Korpusdatei nur zum
Vergleich und schreibt seine Ausgaben ausschliesslich nach demonstrator/.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import trafilatura

try:
    from .corpus_loader import KORPUS_DIR, parse_artikel
except ImportError:
    from corpus_loader import KORPUS_DIR, parse_artikel

AUSGABE_DIR = Path(__file__).resolve().parents[1] / "demonstrator"

# Zwei Beispiele: article_002 (Situation A) und article_010 (Situation B)
ZIELE = {
    "002": "article_002_tagesschau_bafoeg.txt",
    "010": "article_010_tagesschau_inflation_mai.txt",
}


def wortzahl(text: str) -> int:
    return len(text.split())


def finde_zwischenueberschriften(art_text: str) -> list[str]:
    """heuristik: kurze Zeilen ohne Satzendzeichen zwischen Absaetzen =
    Artikel-Zwischenueberschriften (im Korpus bewusst erhalten)."""
    ueberschriften = []
    for zeile in art_text.splitlines():
        z = zeile.strip()
        if not z:
            continue
        # kurz, kein Satzpunkt am Ende, keine reine Zahl
        if (len(z) <= 70 and not z.endswith((".", ":", "!", "?", "\""))
                and not z[0].isdigit() and " " in z):
            ueberschriften.append(z)
    return ueberschriften


def extrahiere(html: str, mit_formatierung: bool) -> str:
    """trafilatura-Extraktion mit fuer Nachrichtenartikel sinnvollen Optionen."""
    return trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        include_images=False,
        include_links=False,
        include_formatting=mit_formatierung,
        favor_precision=True,
        output_format="txt",
    ) or ""


def vergleiche(aid: str, korpus_text: str, traf_text: str) -> dict:
    """liefert Vergleichskennzahlen und qualitative Differenzen."""
    k_woerter = wortzahl(korpus_text)
    t_woerter = wortzahl(traf_text)

    # Zwischenueberschriften des Korpus: kommen sie im trafilatura-Output vor?
    ueberschriften = finde_zwischenueberschriften(korpus_text)
    traf_norm = re.sub(r"\s+", " ", traf_text)
    fehlende_ueberschr = [u for u in ueberschriften
                          if re.sub(r"\s+", " ", u) not in traf_norm]

    # grobe Boilerplate-Indikatoren im trafilatura-Output, die der Korpus
    # bewusst entfernt hat
    boilerplate_marker = [
        "Mehr zum Thema", "Mehr zu diesem Thema", "Über dieses Thema",
        "Dieser Artikel", "tagesschau24", "Sendung:", "Diese Nachricht",
        "Teilen", "Zur optimierten Darstellung", "Datenschutz",
    ]
    gefundene_boiler = [m for m in boilerplate_marker if m in traf_text]

    # Erster und letzter Satz des Korpus im trafilatura-Output? (Vollstaendigkeit)
    erster_satz = korpus_text.split(".")[0][:60]
    letzte_woerter = " ".join(korpus_text.split()[-8:])
    anfang_da = re.sub(r"\s+", " ", erster_satz).strip() in traf_norm
    ende_da = re.sub(r"\s+", " ", letzte_woerter).strip() in traf_norm

    return {
        "aid": aid,
        "korpus_woerter": k_woerter,
        "traf_woerter": t_woerter,
        "delta_woerter": t_woerter - k_woerter,
        "ueberschriften_gesamt": len(ueberschriften),
        "ueberschriften_fehlend": fehlende_ueberschr,
        "boilerplate_gefunden": gefundene_boiler,
        "anfang_erhalten": anfang_da,
        "ende_erhalten": ende_da,
    }


def _main() -> None:
    AUSGABE_DIR.mkdir(exist_ok=True)
    befunde = []

    for aid, dateiname in ZIELE.items():
        art = parse_artikel(KORPUS_DIR / dateiname)
        print(f"=== article_{aid} — {art.titel}")
        print(f"    URL: {art.url}")

        html = trafilatura.fetch_url(art.url)
        if not html:
            print("    ABRUF FEHLGESCHLAGEN/BLOCKIERT — Befund dokumentieren.")
            befunde.append({"aid": aid, "abruf": False})
            continue

        traf_text = extrahiere(html, mit_formatierung=False)
        traf_text_fmt = extrahiere(html, mit_formatierung=True)

        # Rohausgaben archivieren (nur unter demonstrator/)
        (AUSGABE_DIR / f"article_{aid}_trafilatura.txt").write_text(
            traf_text, encoding="utf-8")
        (AUSGABE_DIR / f"article_{aid}_trafilatura_formatiert.txt").write_text(
            traf_text_fmt, encoding="utf-8")
        (AUSGABE_DIR / f"article_{aid}_html_laenge.txt").write_text(
            f"HTML-Bytes: {len(html)}\n", encoding="utf-8")

        b = vergleiche(aid, art.text, traf_text)
        befunde.append({"aid": aid, "abruf": True, **b})

        print(f"    HTML-Bytes: {len(html)}")
        print(f"    Woerter Korpus / trafilatura: {b['korpus_woerter']} / "
              f"{b['traf_woerter']}  (Delta {b['delta_woerter']:+d})")
        print(f"    Zwischenueberschriften: {b['ueberschriften_gesamt']} im "
              f"Korpus, davon im trafilatura-Output fehlend: "
              f"{len(b['ueberschriften_fehlend'])}")
        if b["ueberschriften_fehlend"]:
            for u in b["ueberschriften_fehlend"]:
                print(f"        - fehlt: {u!r}")
        print(f"    Boilerplate-Marker im trafilatura-Output: "
              f"{b['boilerplate_gefunden'] or 'keine der geprueften'}")
        print(f"    Artikelanfang erhalten: {b['anfang_erhalten']}; "
              f"Artikelende erhalten: {b['ende_erhalten']}")
        print()

    print("Rohausgaben gespeichert unter:", AUSGABE_DIR)
    return befunde


if __name__ == "__main__":
    _main()
