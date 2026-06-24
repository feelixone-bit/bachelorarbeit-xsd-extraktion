"""Volllauf: 24 Artikel x 2 Schemavarianten x 3 Wiederholungen
= 144 Erstversuche plus Korrekturiterationen.

Robustheit:
- CSVs werden INKREMENTELL nach jedem Versuch geschrieben (Absturz-/
  Abbruchsicherheit; Teilergebnisse bleiben erhalten).
- RESUME: Bereits in der attempts-CSV protokollierte Kombinationen
  (artikel_id, schemavariante, wiederholung) werden beim Neustart
  übersprungen — der Lauf kann nach Unterbrechung fortgesetzt werden.
- Rate-Limit/Retry: siehe extraction.rufe_modell.

Ausgaben: runs/volllauf_v3/ (Roh-XMLs je Iteration),
results/volllauf_v3_attempts.csv / _iterations.csv.
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import datetime

from google import genai

import config
import pipeline
from corpus_loader import KORPUS_DIR, lade_korpus, pruefe_konsistenz
from corpus_manifest import ERWARTUNG

LAUF_ID = "volllauf_v3"
VARIANTEN = ["locker", "streng"]
WIEDERHOLUNGEN = 3


def lade_erledigte() -> set[tuple[str, str, int]]:
    """liest bereits protokollierte Versuche für Resume."""
    pfad = config.RESULTS_DIR / f"{LAUF_ID}_attempts.csv"
    if not pfad.exists():
        return set()
    erledigt = set()
    with pfad.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            erledigt.add((row["artikel_id"], row["schemavariante"],
                          int(row["wiederholung"])))
    return erledigt


def main() -> None:
    # Vorab-Konsistenzcheck des Korpus (Abbruch bei Befund)
    artikel_liste = lade_korpus()
    befund = pruefe_konsistenz(artikel_liste)
    if befund["fehler"]:
        print("ABBRUCH: Korpus-Konsistenzcheck fehlgeschlagen:")
        for f in befund["fehler"]:
            print("  -", f)
        sys.exit(1)

    client = genai.Client(api_key=config.lade_api_key())
    erledigt = lade_erledigte()

    gesamt = len(artikel_liste) * len(VARIANTEN) * WIEDERHOLUNGEN
    print(f"Volllauf {LAUF_ID} — Modell {config.MODELL}, Temp {config.TEMPERATUR}")
    print(f"Design: {len(artikel_liste)} Artikel x {len(VARIANTEN)} Varianten x "
          f"{WIEDERHOLUNGEN} Wiederholungen = {gesamt} Versuche")
    if erledigt:
        print(f"RESUME: {len(erledigt)} Versuche bereits protokolliert, "
              f"werden übersprungen.")
    print(f"Start: {datetime.now().isoformat(timespec='seconds')}\n", flush=True)

    t_start = time.time()
    zaehler = 0
    fehlgeschlagen = []

    for artikel in artikel_liste:
        aid = artikel.artikel_id
        situation = ERWARTUNG[aid]["situation"]
        pfad = KORPUS_DIR / artikel.dateiname
        artikel_roh = pfad.read_text(encoding="utf-8")

        for variante in VARIANTEN:
            for w in range(1, WIEDERHOLUNGEN + 1):
                zaehler += 1
                if (aid, variante, w) in erledigt:
                    continue
                kennung = f"[{zaehler:3d}/{gesamt}] article_{aid} ({situation}) {variante} w{w}"
                try:
                    erg = pipeline.fuehre_versuch_aus(
                        client, artikel, situation, variante, w, LAUF_ID,
                        artikel_roh)
                except Exception as exc:  # noqa: BLE001 - Lauf soll weiterlaufen
                    print(f"{kennung}  FEHLER: {type(exc).__name__}: "
                          f"{str(exc)[:160]}", flush=True)
                    fehlgeschlagen.append((aid, variante, w, str(exc)[:200]))
                    continue

                # inkrementell protokollieren
                pipeline.schreibe_csv(
                    config.RESULTS_DIR / f"{LAUF_ID}_attempts.csv",
                    [erg.attempt_row], pipeline.ATTEMPT_FELDER)
                pipeline.schreibe_csv(
                    config.RESULTS_DIR / f"{LAUF_ID}_iterations.csv",
                    erg.iteration_rows, pipeline.ITERATION_FELDER)

                a = erg.attempt_row
                print(f"{kennung}  erst_gueltig={a['erstversuch_gueltig']} "
                      f"fehler={a['erstversuch_fehleranzahl']}"
                      f"[{a['erstversuch_fehlertypen']}] "
                      f"korr={a['korrekturiterationen']} "
                      f"final={a['final_gueltig']}", flush=True)

    dauer_min = (time.time() - t_start) / 60
    print(f"\nVolllauf beendet: {datetime.now().isoformat(timespec='seconds')} "
          f"({dauer_min:.1f} Min)")
    if fehlgeschlagen:
        print(f"NICHT abgeschlossene Versuche: {len(fehlgeschlagen)} — "
              f"Skript erneut starten (Resume) oder Fehler prüfen:")
        for aid, variante, w, msg in fehlgeschlagen:
            print(f"  - {aid}/{variante}/w{w}: {msg}")
    else:
        print("Alle Versuche abgeschlossen und protokolliert.")


if __name__ == "__main__":
    main()
