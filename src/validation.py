"""Validierungsmodul: XSD-Prüfung mit xmlschema und
Klassifikation der FORMALEN Fehler nach der Taxonomie:

  - wohlgeformtheit : XML nicht parsebar (Syntaxfehler)
  - struktur        : Elementstruktur verletzt (fehlende/unerwartete/zu wenige
                      Elemente, Reihenfolge, minOccurs; ebenso Verletzungen von
                      Identity-Constraints wie xs:key — Dokumentstruktur-Ebene)
  - typ_facette     : Wert verletzt Typ oder Facette (xs:date, xs:decimal,
                      Enumeration, minInclusive/maxInclusive, Pattern)

Zuordnungsregeln:
  XMLSchemaChildrenValidationError            -> struktur
  Meldungen zu Identity-Constraints/xs:key    -> struktur
  alle übrigen Validierungs-/Decode-Fehler    -> typ_facette

Inhaltliche Fehler (falscher Wert, Präzisionsverlust, falsche Zuordnung,
Halluzination, Auslassung) sind NICHT maschinell prüfbar und werden erst
beim Goldstandard-Vergleich bewertet.

Validiert wird IMMER gegen die Original-XSDs (inkl. Annotation — diese hat
keinen Einfluss auf die Validierung).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache

import xmlschema
from xmlschema.validators.exceptions import XMLSchemaChildrenValidationError

try:
    from . import config
except ImportError:
    import config


@dataclass
class Validierungsergebnis:
    wohlgeformt: bool
    gueltig: bool
    fehleranzahl: int
    fehlertypen: list[str] = field(default_factory=list)   # dedupliziert, sortiert
    fehler: list[dict] = field(default_factory=list)        # [{kategorie, meldung}]

    @property
    def fehlertext_fuer_korrektur(self) -> str:
        """formatiert die Validatorfehler für den Korrekturprompt."""
        zeilen = []
        for i, f in enumerate(self.fehler, 1):
            zeilen.append(f"{i}. [{f['kategorie']}] {f['meldung']}")
        return "\n".join(zeilen)


@lru_cache(maxsize=8)
def lade_schema(situation: str, variante: str) -> xmlschema.XMLSchema:
    dateiname = f"situation_{situation.lower()}_{variante}.xsd"
    return xmlschema.XMLSchema(str(config.SCHEMA_DIR / dateiname))


def _klassifiziere(err: Exception) -> str:
    if isinstance(err, XMLSchemaChildrenValidationError):
        return "struktur"
    meldung = str(err).lower()
    if "duplicated value" in meldung or "identity constraint" in meldung \
            or "key " in meldung[:40]:
        return "struktur"
    return "typ_facette"


def _kuerze(meldung: str, max_len: int = 600) -> str:
    """kürzt xmlschema-Meldungen (enthalten oft das ganze Element) auf ein
    fürs Protokoll und den Korrekturprompt handhabbares Maß."""
    eine_zeile = " ".join(meldung.split())
    return eine_zeile[:max_len] + (" […]" if len(eine_zeile) > max_len else "")


def validiere(xml_text: str, situation: str, variante: str) -> Validierungsergebnis:
    # Stufe 1: Wohlgeformtheit
    try:
        ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return Validierungsergebnis(
            wohlgeformt=False, gueltig=False, fehleranzahl=1,
            fehlertypen=["wohlgeformtheit"],
            fehler=[{"kategorie": "wohlgeformtheit",
                     "meldung": _kuerze(f"XML nicht wohlgeformt: {exc}")}],
        )

    # Stufe 2: XSD-Validierung (alle Fehler einsammeln)
    schema = lade_schema(situation, variante)
    fehler = []
    for err in schema.iter_errors(xml_text):
        kategorie = _klassifiziere(err)
        grund = getattr(err, "reason", None) or str(err)
        pfad = getattr(err, "path", "") or ""
        fehler.append({"kategorie": kategorie,
                       "meldung": _kuerze(f"{pfad}: {grund}" if pfad else grund)})

    return Validierungsergebnis(
        wohlgeformt=True,
        gueltig=not fehler,
        fehleranzahl=len(fehler),
        fehlertypen=sorted({f["kategorie"] for f in fehler}),
        fehler=fehler,
    )
