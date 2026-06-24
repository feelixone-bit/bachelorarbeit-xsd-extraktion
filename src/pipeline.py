"""Pipeline-Orchestrierung:
Erstversuch -> Validierung -> Korrekturschleife (max. MAX_KORREKTUREN
Iterationen) -> Protokollierung.

Protokolliert wird je Versuch (attempts-CSV) und zusätzlich je Iteration
(iterations-CSV). Roh-XMLs jeder Iteration werden unter runs/<lauf_id>/
archiviert.

Designentscheidung Korrekturschleife:
Der Korrekturprompt enthält neben Validatorfehlern und bisherigem XML auch
Artikeltext und XSD. Begründung: Ohne Artikelzugriff wäre jede inhaltliche
Korrektur zwangsläufig Raterei — die Frage, ob das Modell Werte erfindet, nur
um den Validator zu befriedigen, obwohl es die Quelle sieht, ist nur mit
Artikelzugriff sauber messbar; zudem entspricht dies einem realistischen
Produktiv-Workflow.
"""

from __future__ import annotations

import csv
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from google import genai

try:
    from . import config, extraction, validation
    from .corpus_loader import Artikel
except ImportError:
    import config, extraction, validation
    from corpus_loader import Artikel

MAX_KORREKTUREN = 3
XSD_VERSION = "v1"

ATTEMPT_FELDER = [
    "lauf_id", "zeitstempel", "artikel_id", "situation", "schemavariante",
    "xsd_version", "promptversion", "korrektur_promptversion",
    "modell_gepinnt", "modell_antwort", "temperatur", "wiederholung",
    "erstversuch_gueltig", "erstversuch_wohlgeformt",
    "erstversuch_fehleranzahl", "erstversuch_fehlertypen",
    "korrekturiterationen", "final_gueltig", "abbruchgrund",
    "inhaltliche_fehler",          # leer; wird später beim Goldstandard-Vergleich befüllt
    "requests_gesamt", "dauer_gesamt_s",
]

ITERATION_FELDER = [
    "lauf_id", "zeitstempel", "artikel_id", "situation", "schemavariante",
    "wiederholung", "iteration",   # 0 = Erstversuch, 1..3 = Korrektur
    "modell_antwort", "dauer_s", "prompt_tokens", "output_tokens",
    "thoughts_tokens", "api_versuche", "codefence_entfernt",
    "wohlgeformt", "gueltig", "fehleranzahl", "fehlertypen",
    "fehler_meldungen", "xml_datei",
]


@dataclass
class VersuchErgebnis:
    attempt_row: dict
    iteration_rows: list[dict] = field(default_factory=list)


def _xml_dateiname(artikel_id: str, variante: str, wiederholung: int,
                   iteration: int) -> str:
    return f"article_{artikel_id}_{variante}_w{wiederholung}_iter{iteration}.xml"


def fuehre_versuch_aus(client: genai.Client, artikel: Artikel, situation: str,
                       variante: str, wiederholung: int, lauf_id: str,
                       artikel_roh: str) -> VersuchErgebnis:
    """führt einen vollständigen Versuch aus: Erstversuch + Korrekturschleife.

    artikel_roh = vollständiger Korpusdateitext (inkl. Metadatenkopf), der dem
    Modell vorgelegt wird.
    """
    lauf_dir = config.RUNS_DIR / lauf_id
    lauf_dir.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    iteration_rows: list[dict] = []

    basis = {
        "lauf_id": lauf_id,
        "artikel_id": artikel.artikel_id,
        "situation": situation,
        "schemavariante": variante,
        "wiederholung": wiederholung,
    }

    # ---- Iteration 0: Erstversuch ------------------------------------------
    prompt = extraction.baue_extraktionsprompt(situation, variante, artikel_roh)
    antwort = extraction.rufe_modell(client, prompt)
    ergebnis = validation.validiere(antwort.text, situation, variante)
    requests = 1

    xml_name = _xml_dateiname(artikel.artikel_id, variante, wiederholung, 0)
    (lauf_dir / xml_name).write_text(antwort.text, encoding="utf-8")

    def _iter_row(iteration: int, a: extraction.ApiAntwort,
                  v: validation.Validierungsergebnis, datei: str) -> dict:
        return {
            **basis,
            "zeitstempel": datetime.now().isoformat(timespec="seconds"),
            "iteration": iteration,
            "modell_antwort": a.modell_antwort,
            "dauer_s": a.dauer_s,
            "prompt_tokens": a.prompt_tokens,
            "output_tokens": a.output_tokens,
            "thoughts_tokens": a.thoughts_tokens,
            "api_versuche": a.versuche,
            "codefence_entfernt": a.codefence_entfernt,
            "wohlgeformt": v.wohlgeformt,
            "gueltig": v.gueltig,
            "fehleranzahl": v.fehleranzahl,
            "fehlertypen": "|".join(v.fehlertypen),
            "fehler_meldungen": " || ".join(f["meldung"] for f in v.fehler)[:2000],
            "xml_datei": f"runs/{lauf_id}/{datei}",
        }

    iteration_rows.append(_iter_row(0, antwort, ergebnis, xml_name))
    erst_ergebnis = ergebnis
    erst_antwort = antwort

    # ---- Korrekturschleife (max. MAX_KORREKTUREN) --------------------------
    korrekturen = 0
    xml_aktuell = antwort.text
    while not ergebnis.gueltig and korrekturen < MAX_KORREKTUREN:
        korrekturen += 1
        prompt = extraction.baue_korrekturprompt(
            situation, variante, artikel_roh, xml_aktuell,
            ergebnis.fehlertext_fuer_korrektur)
        antwort = extraction.rufe_modell(client, prompt)
        ergebnis = validation.validiere(antwort.text, situation, variante)
        requests += 1
        xml_aktuell = antwort.text

        xml_name = _xml_dateiname(artikel.artikel_id, variante, wiederholung,
                                  korrekturen)
        (lauf_dir / xml_name).write_text(antwort.text, encoding="utf-8")
        iteration_rows.append(_iter_row(korrekturen, antwort, ergebnis, xml_name))

    # ---- Terminierung dokumentieren ----------------------------------------
    if ergebnis.gueltig:
        abbruchgrund = ("gueltig_im_erstversuch" if korrekturen == 0
                        else f"gueltig_nach_korrektur_{korrekturen}")
    else:
        abbruchgrund = "max_korrekturen_erreicht"

    attempt_row = {
        **basis,
        "zeitstempel": datetime.now().isoformat(timespec="seconds"),
        "xsd_version": XSD_VERSION,
        "promptversion": extraction.PROMPTVERSIONEN[situation],
        "korrektur_promptversion": extraction.KORREKTUR_PROMPTVERSION,
        "modell_gepinnt": config.MODELL,
        "modell_antwort": erst_antwort.modell_antwort,
        "temperatur": config.TEMPERATUR,
        "erstversuch_gueltig": erst_ergebnis.gueltig,
        "erstversuch_wohlgeformt": erst_ergebnis.wohlgeformt,
        "erstversuch_fehleranzahl": erst_ergebnis.fehleranzahl,
        "erstversuch_fehlertypen": "|".join(erst_ergebnis.fehlertypen),
        "korrekturiterationen": korrekturen,
        "final_gueltig": ergebnis.gueltig,
        "abbruchgrund": abbruchgrund,
        "inhaltliche_fehler": "",
        "requests_gesamt": requests,
        "dauer_gesamt_s": round(time.time() - t_start, 1),
    }
    return VersuchErgebnis(attempt_row=attempt_row, iteration_rows=iteration_rows)


def schreibe_csv(pfad: Path, rows: list[dict], felder: list[str]) -> None:
    """schreibt/erweitert eine Ergebnis-CSV (Append, Header nur einmal)."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    neu = not pfad.exists()
    with pfad.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=felder)
        if neu:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)
