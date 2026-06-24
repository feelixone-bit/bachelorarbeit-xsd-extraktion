"""Schema-Smoke-Test: laedt und kompiliert alle sechs XSD-Dateien mit
xmlschema. Jedes XSD muss eigenstaendig kompilierbar sein (analog
XmlSchemaSet.Compile).

Erfolgreich = XMLSchema-Objekt baut ohne Exception, schema.built == True.
Ausgegeben werden zusaetzlich Wurzelelement und Top-Level-Constraints.
"""

from __future__ import annotations

from pathlib import Path

import xmlschema

SCHEMA_DIR = (Path(__file__).resolve().parents[1] / "schemas")

ERWARTETE_XSDS = [
    "situation_a_locker.xsd",
    "situation_a_streng.xsd",
    "situation_b_locker.xsd",
    "situation_b_streng.xsd",
    "situation_c_locker.xsd",
    "situation_c_streng.xsd",
]


def kompiliere(pfad: Path) -> dict:
    """versucht, ein XSD zu laden/kompilieren. Liefert Befund-dict."""
    ergebnis = {"datei": pfad.name, "ok": False, "wurzel": None,
                "gebaut": False, "fehler": None}
    try:
        schema = xmlschema.XMLSchema(str(pfad))
        ergebnis["ok"] = True
        ergebnis["gebaut"] = schema.built
        # Wurzelelement(e)
        wurzeln = list(schema.elements.keys())
        ergebnis["wurzel"] = wurzeln[0] if wurzeln else None
    except Exception as exc:  # noqa: BLE001 - Smoke-Test soll jeden Fehler melden
        ergebnis["fehler"] = f"{type(exc).__name__}: {exc}"
    return ergebnis


def _main() -> None:
    print(f"xmlschema-Version: {xmlschema.__version__}")
    print(f"Schemaordner: {SCHEMA_DIR}\n")

    befunde = []
    for name in ERWARTETE_XSDS:
        pfad = SCHEMA_DIR / name
        if not pfad.exists():
            befunde.append({"datei": name, "ok": False, "wurzel": None,
                            "gebaut": False, "fehler": "Datei nicht gefunden"})
            continue
        befunde.append(kompiliere(pfad))

    kopf = f"{'XSD-Datei':<28}  {'kompiliert':<10}  {'Wurzelelement':<18}"
    print(kopf)
    print("-" * len(kopf))
    for b in befunde:
        status = "OK" if (b["ok"] and b["gebaut"]) else "FEHLER"
        print(f"{b['datei']:<28}  {status:<10}  {str(b['wurzel']):<18}")
        if b["fehler"]:
            print(f"    -> {b['fehler']}")

    erfolg = sum(1 for b in befunde if b["ok"] and b["gebaut"])
    print(f"\nSmoke-Test: {erfolg}/{len(ERWARTETE_XSDS)} XSDs kompilieren.")
    if erfolg != len(ERWARTETE_XSDS):
        raise SystemExit(1)


if __name__ == "__main__":
    _main()
