"""Extraktionsschritt der Pipeline.

- Prompt-Konstruktion aus den Vorlagen in prompts/
- XSD-Einbettung OHNE xs:annotation-Block: Die Annotationen der Schemas
  dokumentieren das Forschungsdesign (eingebaute Messstellen) und dürfen dem
  Untersuchungsmodell nicht gezeigt werden, sonst verfälschen sie das Ergebnis.
  Die XSD-Dateien selbst bleiben unverändert; validiert wird gegen das Original.
- Gemini-Aufruf via google-genai mit Mindestabstand zwischen Requests
  und Retry-Logik für transiente Fehler (429/500/503).
- Bereinigung umschließender Markdown-Codefences: entfernt werden
  ausschließlich die ```-Fences (mit optionalem Sprach-Tag), sonst nichts.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

from google import genai
from google.genai import errors, types

try:
    from . import config
except ImportError:
    import config

PROMPTVERSIONEN = {
    "A": "extraktion_a",
    "B": "extraktion_b",
    "C": "extraktion_c",
}
KORREKTUR_PROMPTVERSION = "korrektur"

_ANNOTATION_RE = re.compile(r"\s*<xs:annotation>.*?</xs:annotation>", re.DOTALL)
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n(.*?)\n?```\s*$", re.DOTALL)

# Zeitpunkt des letzten Requests (modulglobal) für den Mindestabstand
_letzter_request: float = 0.0


def lade_xsd_fuer_prompt(situation: str, variante: str) -> str:
    """liest das Original-XSD und entfernt den xs:annotation-Block für die
    Prompt-Einbettung (Forschungs-Doku bleibt dem Modell verborgen)."""
    dateiname = f"situation_{situation.lower()}_{variante}.xsd"
    roh = (config.SCHEMA_DIR / dateiname).read_text(encoding="utf-8")
    return _ANNOTATION_RE.sub("", roh)


def lade_promptvorlage(name: str) -> str:
    return (config.PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def baue_extraktionsprompt(situation: str, variante: str, artikel_roh: str) -> str:
    vorlage = lade_promptvorlage(PROMPTVERSIONEN[situation])
    xsd = lade_xsd_fuer_prompt(situation, variante)
    # .replace statt .format: Artikel-/XSD-Text kann geschweifte Klammern enthalten
    return vorlage.replace("{xsd}", xsd).replace("{artikel}", artikel_roh)


def baue_korrekturprompt(situation: str, variante: str, artikel_roh: str,
                         xml_bisher: str, fehlertext: str) -> str:
    vorlage = lade_promptvorlage(KORREKTUR_PROMPTVERSION)
    xsd = lade_xsd_fuer_prompt(situation, variante)
    return (vorlage
            .replace("{fehler}", fehlertext)
            .replace("{xsd}", xsd)
            .replace("{artikel}", artikel_roh)
            .replace("{xml}", xml_bisher))


def bereinige_codefences(text: str) -> tuple[str, bool]:
    """entfernt genau einen umschließenden Markdown-Codefence (```), falls
    vorhanden. Rückgabe: (bereinigter Text, wurde_bereinigt)."""
    gestutzt = text.strip()
    m = _FENCE_RE.match(gestutzt)
    if m:
        return m.group(1).strip(), True
    return gestutzt, False


@dataclass
class ApiAntwort:
    text: str
    codefence_entfernt: bool
    modell_antwort: str          # von der API gemeldete Modellversion
    prompt_tokens: int | None
    output_tokens: int | None
    thoughts_tokens: int | None  # Denk-Tokens (Thinking-Modelle, abgerechnet)
    dauer_s: float
    versuche: int                # API-Versuche inkl. Retries


def rufe_modell(client: genai.Client, prompt: str) -> ApiAntwort:
    """ein Request an das gepinnte Modell, mit Mindestabstand und Retries."""
    global _letzter_request

    letzter_fehler: Exception | None = None
    for versuch in range(1, config.MAX_RETRIES + 1):
        # Rate-Limit: Mindestabstand zum letzten Request einhalten
        wartezeit = config.MIN_ABSTAND_SEKUNDEN - (time.time() - _letzter_request)
        if wartezeit > 0:
            time.sleep(wartezeit)
        _letzter_request = time.time()

        t0 = time.time()
        try:
            antwort = client.models.generate_content(
                model=config.MODELL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=config.TEMPERATUR,
                ),
            )
            dauer = time.time() - t0
            roh = antwort.text or ""
            text, fence = bereinige_codefences(roh)
            um = getattr(antwort, "usage_metadata", None)
            return ApiAntwort(
                text=text,
                codefence_entfernt=fence,
                modell_antwort=getattr(antwort, "model_version", "") or config.MODELL,
                prompt_tokens=getattr(um, "prompt_token_count", None) if um else None,
                output_tokens=getattr(um, "candidates_token_count", None) if um else None,
                thoughts_tokens=getattr(um, "thoughts_token_count", None) if um else None,
                dauer_s=round(dauer, 2),
                versuche=versuch,
            )
        except (errors.ServerError, errors.ClientError) as exc:
            # transiente Fehler (429 Rate-Limit, 500, 503) -> Backoff und Retry
            code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
            if code in (429, 500, 503) and versuch < config.MAX_RETRIES:
                letzter_fehler = exc
                time.sleep(min(config.RETRY_BACKOFF_SEKUNDEN * (2 ** (versuch - 1)),
                               config.RETRY_BACKOFF_MAX_SEKUNDEN))
                continue
            raise
    raise RuntimeError(f"Alle {config.MAX_RETRIES} API-Versuche fehlgeschlagen: "
                       f"{letzter_fehler}")
