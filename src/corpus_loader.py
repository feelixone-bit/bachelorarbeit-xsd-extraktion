"""Korpus-Loader: parst den Metadatenkopf der 24 Korpusdateien und liefert
strukturierte Artikelobjekte. Zusaetzlich ein Konsistenzcheck gegen die
Erwartungswerte aus dem Auswahlprotokoll (corpus_manifest.ERWARTUNG).

Headerformat (8 Felder):
  Artikel-ID, Quelle, URL, Abrufdatum, Titel, Untertitel/Teaser,
  Veroeffentlichungsdatum_original, Veroeffentlichungsdatum_iso
gefolgt von "Artikeltext:" und dem bereinigten Fliesstext.

Toleranzen:
- "Abrufdatum: Stand: 2026-05-31" (article_002) wird wie "2026-05-31" gelesen.
- Wortzahl wird gemessen; gegen die Protokollangabe nur als WARNUNG verglichen
  (kleine Abweichungen durch Tokenisierung sind zulaessig, keine Fehlerquelle
  fuer die Pipeline).

Der Loader veraendert die Korpusdateien nie (read-only, Faktendisziplin).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    from .corpus_manifest import ERWARTUNG
except ImportError:  # direkter Aufruf ohne Paketkontext
    from corpus_manifest import ERWARTUNG

# Korpusordner relativ zu diesem File: src/ -> ../corpus
KORPUS_DIR = (Path(__file__).resolve().parents[1] / "corpus")

# erkannte Headerfelder (linke Seite vor dem Doppelpunkt)
_HEADER_KEYS = {
    "Artikel-ID": "artikel_id",
    "Quelle": "quelle",
    "URL": "url",
    "Abrufdatum": "abrufdatum",
    "Titel": "titel",
    "Untertitel/Teaser": "untertitel",
    "Veröffentlichungsdatum_original": "datum_original",
    "Veröffentlichungsdatum_iso": "datum_iso",
}

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass
class Artikel:
    artikel_id: str
    dateiname: str
    quelle: str = ""
    url: str = ""
    abrufdatum: str = ""
    titel: str = ""
    untertitel: str = ""
    datum_original: str = ""
    datum_iso: str = ""
    text: str = ""
    fehlende_felder: list[str] = field(default_factory=list)

    @property
    def wortzahl(self) -> int:
        # gemessen am bereinigten Fliesstext (inkl. Zwischenueberschriften)
        return len(self.text.split())


def _parse_iso(rohwert: str) -> str:
    """zieht ein ISO-Datum aus Werten wie 'Stand: 2026-05-31' oder '2026-06-13'."""
    treffer = _ISO_RE.search(rohwert)
    return treffer.group(0) if treffer else rohwert.strip()


def parse_artikel(pfad: Path) -> Artikel:
    """parst eine einzelne Korpusdatei in ein Artikel-Objekt."""
    roh = pfad.read_text(encoding="utf-8")

    # Trennung Header / Fliesstext am ersten "Artikeltext:"
    teile = re.split(r"(?m)^\s*Artikeltext:\s*", roh, maxsplit=1)
    header_block = teile[0]
    text = teile[1].strip() if len(teile) > 1 else ""

    werte: dict[str, str] = {}
    for zeile in header_block.splitlines():
        if ":" not in zeile:
            continue
        label, _, wert = zeile.partition(":")
        label = label.strip()
        if label in _HEADER_KEYS:
            werte[_HEADER_KEYS[label]] = wert.strip()

    art = Artikel(
        artikel_id=werte.get("artikel_id", "").strip(),
        dateiname=pfad.name,
        quelle=werte.get("quelle", ""),
        url=werte.get("url", ""),
        abrufdatum=_parse_iso(werte.get("abrufdatum", "")),
        titel=werte.get("titel", ""),
        untertitel=werte.get("untertitel", ""),
        datum_original=werte.get("datum_original", ""),
        datum_iso=_parse_iso(werte.get("datum_iso", "")),
        text=text,
    )
    art.fehlende_felder = [
        k for k in _HEADER_KEYS.values()
        if not getattr(art, k if k != "untertitel" else "untertitel")
    ]
    return art


def lade_korpus(korpus_dir: Path = KORPUS_DIR) -> list[Artikel]:
    """laedt alle article_*.txt, sortiert nach Artikel-ID."""
    dateien = sorted(korpus_dir.glob("article_*.txt"))
    artikel = [parse_artikel(p) for p in dateien]
    artikel.sort(key=lambda a: a.artikel_id)
    return artikel


def pruefe_konsistenz(artikel: list[Artikel]) -> dict:
    """Konsistenzcheck gegen die Erwartungswerte (corpus_manifest.ERWARTUNG).

    Prueft je Artikel:
      - Artikel-ID konsistent zum Dateinamen (article_<ID>_...)
      - Header vollstaendig (8 Felder)
      - ISO-Datum stimmt mit Protokoll ueberein
      - Wortzahl nahe Protokollwert (Warnung bei Abweichung > 5 %)
    Zusaetzlich: alle 24 erwarteten IDs vorhanden, keine unerwarteten.

    Rueckgabe: dict mit 'fehler' (hart) und 'warnungen' (weich) je ID.
    """
    befund: dict = {"fehler": [], "warnungen": [], "zeilen": []}
    gefundene_ids = set()

    for art in artikel:
        aid = art.artikel_id
        gefundene_ids.add(aid)
        zeile = {"id": aid, "datei": art.dateiname, "situation": None,
                 "iso": art.datum_iso, "woerter": art.wortzahl, "status": "OK"}

        # ID <-> Dateiname
        m = re.match(r"article_(\d{3})_", art.dateiname)
        if not m:
            befund["fehler"].append(f"{art.dateiname}: Dateiname nicht im Schema article_NNN_*")
            zeile["status"] = "FEHLER"
        elif m.group(1) != aid:
            befund["fehler"].append(
                f"{art.dateiname}: Artikel-ID im Header ({aid}) != Dateiname ({m.group(1)})")
            zeile["status"] = "FEHLER"

        # Headervollstaendigkeit
        if art.fehlende_felder:
            befund["fehler"].append(f"{aid}: fehlende Headerfelder: {art.fehlende_felder}")
            zeile["status"] = "FEHLER"

        # Abgleich mit Protokoll
        erw = ERWARTUNG.get(aid)
        if erw is None:
            befund["fehler"].append(f"{aid}: nicht im Auswahlprotokoll erwartet")
            zeile["status"] = "FEHLER"
        else:
            zeile["situation"] = erw["situation"]
            if art.datum_iso != erw["iso"]:
                befund["fehler"].append(
                    f"{aid}: ISO-Datum {art.datum_iso} != Protokoll {erw['iso']}")
                zeile["status"] = "FEHLER"
            # Wortzahltoleranz: 5 %
            soll = erw["woerter"]
            if soll and abs(art.wortzahl - soll) / soll > 0.05:
                befund["warnungen"].append(
                    f"{aid}: Wortzahl gemessen {art.wortzahl} weicht von "
                    f"Protokoll {soll} ab (>5 %)")
                if zeile["status"] == "OK":
                    zeile["status"] = "WARNUNG"

        befund["zeilen"].append(zeile)

    # Vollstaendigkeit der Menge
    erwartete_ids = set(ERWARTUNG.keys())
    fehlend = erwartete_ids - gefundene_ids
    ueberzaehlig = gefundene_ids - erwartete_ids
    if fehlend:
        befund["fehler"].append(f"Fehlende Artikel-IDs im Korpus: {sorted(fehlend)}")
    if ueberzaehlig:
        befund["fehler"].append(f"Unerwartete Artikel-IDs im Korpus: {sorted(ueberzaehlig)}")

    befund["zeilen"].sort(key=lambda z: z["id"])
    return befund


def _main() -> None:
    artikel = lade_korpus()
    print(f"Geladene Korpusdateien: {len(artikel)}\n")
    befund = pruefe_konsistenz(artikel)

    kopf = f"{'ID':>3}  {'Sit':>3}  {'ISO-Datum':<11}  {'Woerter':>7}  Status"
    print(kopf)
    print("-" * len(kopf))
    for z in befund["zeilen"]:
        print(f"{z['id']:>3}  {str(z['situation']):>3}  {z['iso']:<11}  "
              f"{z['woerter']:>7}  {z['status']}")

    print()
    if befund["warnungen"]:
        print("WARNUNGEN:")
        for w in befund["warnungen"]:
            print(f"  - {w}")
    if befund["fehler"]:
        print("\nFEHLER:")
        for f in befund["fehler"]:
            print(f"  - {f}")
        print(f"\nKonsistenzcheck: NICHT bestanden ({len(befund['fehler'])} Fehler).")
    else:
        print(f"Konsistenzcheck: BESTANDEN — 24 Artikel, Header/ISO/ID/Menge ok, "
              f"{len(befund['warnungen'])} Wortzahl-Warnung(en).")


if __name__ == "__main__":
    _main()
