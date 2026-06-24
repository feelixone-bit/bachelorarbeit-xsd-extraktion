"""Zentrale Pipeline-Konfiguration: gepinnter Modellstring, Temperatur und
Rate-Limit-/Retry-Parameter.

Modell (gemini-2.5-flash) und Temperatur sind feste Versuchsparameter und
werden über alle Läufe konstant gehalten. Der API-Schlüssel wird zur Laufzeit
aus der .env gelesen und steht nie im Code oder in Git.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --- Pfade -----------------------------------------------------------------
PIPELINE_DIR = Path(__file__).resolve().parents[1]
PROJEKT_DIR = PIPELINE_DIR
KORPUS_DIR = PIPELINE_DIR / "corpus"
SCHEMA_DIR = PIPELINE_DIR / "schemas"
PROMPTS_DIR = PIPELINE_DIR / "prompts"
GOLDSTANDARD_DIR = PIPELINE_DIR / "goldstandard"
RUNS_DIR = PIPELINE_DIR / "runs"
RESULTS_DIR = PIPELINE_DIR / "results"
ENV_PFAD = PIPELINE_DIR / ".env"

# --- Modell- und Generierungsparameter (gepinnt) ---------------------------
MODELL = "models/gemini-2.5-flash"
TEMPERATUR = 1.0  # fest für alle Läufe

# --- Rate-Limit-/Retry-Parameter (Paid Tier 1) ------------------------------
# Tier-1-Limits liegen weit über dem Bedarf des Volllaufs; die Generierungs-
# zeit (15–20 s, Thinking-Modell) dominiert. Moderater Mindestabstand als
# Höflichkeitspuffer; Retries fangen Warteschlangen-Ausreißer (>100 s) und
# transiente Fehler ab.
MIN_ABSTAND_SEKUNDEN = 2.0
MAX_RETRIES = 7                  # für transiente Fehler (429, 500, 503)
RETRY_BACKOFF_SEKUNDEN = 8       # Basis-Wartezeit, exponentiell erhöht
RETRY_BACKOFF_MAX_SEKUNDEN = 120 # Deckel je Wartezeit (lange 503-Wellen
                                 # können mehrere Minuten andauern)


def lade_api_key() -> str:
    """lädt GEMINI_API_KEY aus der .env (nie aus Code/Git)."""
    load_dotenv(ENV_PFAD)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit(f"GEMINI_API_KEY nicht gefunden in {ENV_PFAD}")
    return key
