"""Gezielter End-to-End-Test der Korrekturschleife.

Hintergrund: Im Testlauf testlauf_v1 waren alle 4 Erstversuche formal gültig,
die Korrekturschleife wurde daher nie durchlaufen. Dieser Test injiziert in
ein gültiges Erstversuchs-XML (article_002, streng) drei typische formale
Fehler (Enum-Verstoß, Datumsformat, xs:key-Dublette) und prüft, ob der
Korrekturpfad (Fehlertext -> Korrekturprompt -> Modell -> Re-Validierung)
zu einem gültigen XML konvergiert. Umfang: maximal 3 API-Requests.

Ausgaben: runs/test_korrektur_v1/ (XMLs) — reiner Funktionstest, die CSVs
des Testlaufs bleiben unberührt.
"""

from __future__ import annotations

from google import genai

import config
import extraction
import validation
from corpus_loader import KORPUS_DIR

LAUF_DIR = config.RUNS_DIR / "test_korrektur_v1"
MAX_ITER = 3


def main() -> None:
    client = genai.Client(api_key=config.lade_api_key())
    artikel_roh = (KORPUS_DIR / "article_002_tagesschau_bafoeg.txt").read_text(
        encoding="utf-8")

    basis_xml = (config.RUNS_DIR / "testlauf_v1" /
                 "article_002_streng_w1_iter0.xml").read_text(encoding="utf-8")

    # Drei formale Fehler injizieren:
    # 1) Enum-Verstoss: CSU -> "CSU-Partei" (ungueltig)
    # 2) Datumsformat: ISO -> deutsches Format (xs:date-Typfehler)
    # 3) xs:key-Dublette: zweiter Akteur erhaelt denselben Namen wie der erste
    kaputt = (basis_xml
              .replace(">CSU<", ">CSU-Partei<", 1)
              .replace(">2026-05-31<", ">31.05.2026<", 1)
              .replace("<name>Wiebke Esdar</name>",
                       "<name>Dorothee Bär</name>", 1))

    LAUF_DIR.mkdir(parents=True, exist_ok=True)
    (LAUF_DIR / "iter0_injiziert.xml").write_text(kaputt, encoding="utf-8")

    erg = validation.validiere(kaputt, "A", "streng")
    print(f"Injiziertes XML: gueltig={erg.gueltig}, Fehler={erg.fehleranzahl}, "
          f"Typen={erg.fehlertypen}")
    for f in erg.fehler:
        print(f"   - [{f['kategorie']}] {f['meldung'][:140]}")
    assert not erg.gueltig, "Injektion fehlgeschlagen - XML ist noch gueltig"

    xml_aktuell = kaputt
    for iteration in range(1, MAX_ITER + 1):
        print(f"\n>> Korrekturiteration {iteration}")
        prompt = extraction.baue_korrekturprompt(
            "A", "streng", artikel_roh, xml_aktuell,
            erg.fehlertext_fuer_korrektur)
        antwort = extraction.rufe_modell(client, prompt)
        erg = validation.validiere(antwort.text, "A", "streng")
        xml_aktuell = antwort.text
        (LAUF_DIR / f"iter{iteration}.xml").write_text(xml_aktuell,
                                                       encoding="utf-8")
        print(f"   gueltig={erg.gueltig}, Fehler={erg.fehleranzahl}, "
              f"Typen={erg.fehlertypen}, Dauer={antwort.dauer_s}s, "
              f"Fence={antwort.codefence_entfernt}")
        if erg.gueltig:
            print(f"\nKorrekturschleife KONVERGIERT nach {iteration} "
                  f"Iteration(en).")
            break
    else:
        print(f"\nKorrekturschleife NICHT konvergiert nach {MAX_ITER} "
              f"Iterationen (Terminierung dokumentiert).")

    # Inhaltliche Nebenwirkungs-Sichtpruefung (UF2): Hat die Korrektur die
    # injizierten Stellen plausibel repariert oder Werte veraendert?
    if erg.gueltig:
        print("\nSichtpruefung der reparierten Stellen:")
        for marker in (">CSU<", ">2026-05-31<", "<name>Wiebke Esdar</name>"):
            print(f"   {marker!r} wiederhergestellt: {marker in xml_aktuell}")


if __name__ == "__main__":
    main()
