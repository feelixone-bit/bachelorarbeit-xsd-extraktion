"""API-Anbindungstest:
- laedt GEMINI_API_KEY aus der .env (niemals aus Code/Git)
- listet die verfuegbaren Modelle, hebt Flash-Modelle hervor
- sendet EINEN Mini-Request als Funktionsnachweis (minimaler Token-Verbrauch)

Bewusst sparsam: genau ein generate_content-Aufruf, damit das Tagesbudget
nicht unnoetig belastet wird. Der fuer die Laeufe verwendete Modellstring ist
in config.py gepinnt.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ENV_PFAD = Path(__file__).resolve().parents[1] / ".env"


def lade_key() -> str:
    load_dotenv(ENV_PFAD)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit(f"GEMINI_API_KEY nicht gefunden in {ENV_PFAD}")
    return key


def liste_flash_modelle(client: genai.Client) -> list:
    """gibt alle Modelle aus, hebt Flash-Modelle hervor, die generateContent
    unterstuetzen."""
    alle = list(client.models.list())
    flash = []
    print(f"Verfuegbare Modelle insgesamt: {len(alle)}\n")
    print(f"{'Modellname':<45}  generateContent  Flash")
    print("-" * 78)
    for m in alle:
        name = m.name
        methoden = getattr(m, "supported_actions", None) or \
            getattr(m, "supported_generation_methods", []) or []
        kann_generieren = "generateContent" in methoden
        ist_flash = "flash" in name.lower()
        if ist_flash and kann_generieren:
            flash.append(name)
        markerg = "ja" if kann_generieren else "-"
        markerf = "FLASH" if ist_flash else ""
        # nur relevante Zeilen ausgeben (generateContent-faehig), sonst zu lang
        if kann_generieren:
            print(f"{name:<45}  {markerg:<15}  {markerf}")
    print(f"\nFlash-Modelle mit generateContent: {len(flash)}")
    for f in flash:
        print(f"  - {f}")
    return flash


def mini_request(client: genai.Client, modell: str) -> str:
    """ein einziger minimaler Request als Funktionsnachweis."""
    antwort = client.models.generate_content(
        model=modell,
        contents="Antworte mit genau einem Wort: Funktionstest.",
    )
    return (antwort.text or "").strip()


def _main() -> None:
    key = lade_key()
    print(f"GEMINI_API_KEY geladen (Laenge {len(key)}, Praefix {key[:4]}...)\n")
    client = genai.Client(api_key=key)

    flash = liste_flash_modelle(client)

    if not flash:
        print("\nKein Flash-Modell mit generateContent gefunden - "
              "Mini-Request uebersprungen.")
        return

    # bevorzugt das kuerzeste 'flash'-Modell ohne Zusatz-Suffixe fuer den Test
    kandidat = sorted(flash, key=len)[0]
    print(f"\nMini-Request an: {kandidat}")
    try:
        text = mini_request(client, kandidat)
        print(f"Antwort: {text!r}")
        print("\nAPI-Anbindung: FUNKTIONIERT.")
    except Exception as exc:  # noqa: BLE001
        print(f"Mini-Request fehlgeschlagen: {type(exc).__name__}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    _main()
