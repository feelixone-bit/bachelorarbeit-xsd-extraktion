"""Erwartungswerte fuer den Korpus-Konsistenzcheck.

Die Tabelle stammt aus dem Auswahlprotokoll des Korpus und dient
ausschliesslich dem Abgleich Korpus <-> Protokoll. Inhaltliche Fakten der
Artikel stammen NICHT aus dieser Tabelle, sondern aus den Korpusdateien
selbst (Faktendisziplin).

Pro Artikel:
- situation: A | B | C  (manuelle Zuordnung laut Auswahlprotokoll)
- iso:       Veroeffentlichungsdatum (ISO) laut Auswahlprotokoll
- woerter:   gemessene Wortzahl laut Auswahlprotokoll (Toleranz beim Check)
"""

# situation, iso-datum, gemessene wortzahl
ERWARTUNG = {
    # Situation A - Politischer Konfliktbericht
    "002": {"situation": "A", "iso": "2026-05-31", "woerter": 426},
    "003": {"situation": "A", "iso": "2026-05-22", "woerter": 738},
    "004": {"situation": "A", "iso": "2026-05-18", "woerter": 885},
    "005": {"situation": "A", "iso": "2026-05-13", "woerter": 620},
    "006": {"situation": "A", "iso": "2025-11-13", "woerter": 640},
    "007": {"situation": "A", "iso": "2026-06-06", "woerter": 396},
    "019": {"situation": "A", "iso": "2026-05-21", "woerter": 931},
    "020": {"situation": "A", "iso": "2026-03-05", "woerter": 405},
    # Situation B - Wirtschafts-/Kennzahlenmeldung
    "008": {"situation": "B", "iso": "2026-04-30", "woerter": 319},
    "009": {"situation": "B", "iso": "2026-05-07", "woerter": 776},
    "010": {"situation": "B", "iso": "2026-06-02", "woerter": 492},
    "011": {"situation": "B", "iso": "2026-06-11", "woerter": 241},
    "012": {"situation": "B", "iso": "2026-04-29", "woerter": 485},
    "013": {"situation": "B", "iso": "2026-04-01", "woerter": 355},
    "014": {"situation": "B", "iso": "2026-05-21", "woerter": 492},
    "021": {"situation": "B", "iso": "2026-02-11", "woerter": 497},
    # Situation C - Ereignis-/Wahlbericht
    "001": {"situation": "C", "iso": "2026-05-31", "woerter": 633},
    "015": {"situation": "C", "iso": "2025-12-05", "woerter": 482},
    "016": {"situation": "C", "iso": "2025-12-05", "woerter": 733},
    "017": {"situation": "C", "iso": "2026-06-11", "woerter": 458},
    "018": {"situation": "C", "iso": "2025-12-07", "woerter": 834},
    "022": {"situation": "C", "iso": "2026-03-08", "woerter": 910},
    "023": {"situation": "C", "iso": "2026-03-22", "woerter": 413},
    "024": {"situation": "C", "iso": "2026-05-13", "woerter": 741},
}

# Zuordnung Situation -> Schemadateien (schemas/, je locker + streng)
SCHEMA_DATEIEN = {
    "A": ("situation_a_locker.xsd", "situation_a_streng.xsd"),
    "B": ("situation_b_locker.xsd", "situation_b_streng.xsd"),
    "C": ("situation_c_locker.xsd", "situation_c_streng.xsd"),
}
