"""Testlauf: article_001 und article_002 × beide Schemavarianten ×
1 Wiederholung — ein kleiner Vorlauf, um die Pipeline end-to-end zu prüfen,
bevor der Volllauf startet.

Umfang: 4 Erstversuche plus maximal 12 Korrektur-Requests. Ergebnisse:
  runs/testlauf_v1/          Roh-XMLs jeder Iteration
  results/testlauf_v1_attempts.csv / _iterations.csv
"""

from __future__ import annotations

from google import genai

import config
import pipeline
from corpus_loader import KORPUS_DIR, parse_artikel
from corpus_manifest import ERWARTUNG

LAUF_ID = "testlauf_v1"

ZIELE = [
    ("001", "article_001_tagesschau_fdp_parteitag.txt"),
    ("002", "article_002_tagesschau_bafoeg.txt"),
]
VARIANTEN = ["locker", "streng"]
WIEDERHOLUNGEN = 1


def main() -> None:
    client = genai.Client(api_key=config.lade_api_key())
    print(f"Testlauf {LAUF_ID} — Modell {config.MODELL}, Temp {config.TEMPERATUR}")
    print(f"Umfang: {len(ZIELE)} Artikel x {len(VARIANTEN)} Varianten x "
          f"{WIEDERHOLUNGEN} Wiederholung = {len(ZIELE)*len(VARIANTEN)} Versuche "
          f"(max. {len(ZIELE)*len(VARIANTEN)*(1+pipeline.MAX_KORREKTUREN)} Requests)\n")

    attempt_rows, iteration_rows = [], []
    for aid, dateiname in ZIELE:
        pfad = KORPUS_DIR / dateiname
        artikel = parse_artikel(pfad)
        artikel_roh = pfad.read_text(encoding="utf-8")
        situation = ERWARTUNG[aid]["situation"]
        for variante in VARIANTEN:
            for w in range(1, WIEDERHOLUNGEN + 1):
                print(f">> article_{aid} ({situation}) — {variante} — Wdh {w}")
                erg = pipeline.fuehre_versuch_aus(
                    client, artikel, situation, variante, w, LAUF_ID, artikel_roh)
                a = erg.attempt_row
                print(f"   Erstversuch: gueltig={a['erstversuch_gueltig']} "
                      f"(Fehler: {a['erstversuch_fehleranzahl']} "
                      f"[{a['erstversuch_fehlertypen']}]) | "
                      f"Korrekturen: {a['korrekturiterationen']} | "
                      f"final gueltig={a['final_gueltig']} ({a['abbruchgrund']})")
                attempt_rows.append(a)
                iteration_rows.extend(erg.iteration_rows)

    pipeline.schreibe_csv(config.RESULTS_DIR / f"{LAUF_ID}_attempts.csv",
                          attempt_rows, pipeline.ATTEMPT_FELDER)
    pipeline.schreibe_csv(config.RESULTS_DIR / f"{LAUF_ID}_iterations.csv",
                          iteration_rows, pipeline.ITERATION_FELDER)

    print(f"\nCSV geschrieben: results/{LAUF_ID}_attempts.csv "
          f"({len(attempt_rows)} Versuche), results/{LAUF_ID}_iterations.csv "
          f"({len(iteration_rows)} Iterationen)")
    print(f"Roh-XMLs: runs/{LAUF_ID}/")


if __name__ == "__main__":
    main()
