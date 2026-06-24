"""Auswertungsmodul — UF1, UF2 und UF4 aus den Ergebnis-CSVs eines Laufs.

  UF1 (Erstversuchs-Konformität): Anteil formal gültiger Erstversuche,
      Fehlertypen-Verteilung — gesamt, je Schemavariante, je Situation.
  UF2 (Korrekturschleife): Konvergenzrate, Verteilung der benötigten
      Iterationen, Terminierungsgründe. (Inhaltliche Nebenwirkungen der
      Korrektur werden in der UF3-/Goldstandard-Auswertung bewertet.)
  UF4 (Schemastrenge): direkte Gegenüberstellung locker vs. streng über
      die UF1-/UF2-Kennzahlen.

UF3 (gültig, aber falsch) erfordert den Feldvergleich gegen den Goldstandard
und ist in einem separaten Modul vorgesehen (goldvergleich.py).

Aufruf:  python auswertung.py <lauf_id>     (z. B. volllauf_v3)
Ausgabe: results/<lauf_id>_auswertung.md (Tabellen, für den Ergebnisbericht)
         und Konsolen-Echo.
"""

from __future__ import annotations

import sys

import pandas as pd

import config


def lade(lauf_id: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    attempts = pd.read_csv(config.RESULTS_DIR / f"{lauf_id}_attempts.csv")
    iterations = pd.read_csv(config.RESULTS_DIR / f"{lauf_id}_iterations.csv")
    # Bool-Spalten robust einlesen (CSV speichert True/False als Text)
    for sp in ("erstversuch_gueltig", "erstversuch_wohlgeformt", "final_gueltig"):
        attempts[sp] = attempts[sp].astype(str).str.lower().eq("true")
    for sp in ("wohlgeformt", "gueltig", "codefence_entfernt"):
        iterations[sp] = iterations[sp].astype(str).str.lower().eq("true")
    return attempts, iterations


def _md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=True)


def uf1_erstversuch(attempts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """UF1: Erstversuchs-Konformität und Fehlertypen."""
    out: dict[str, pd.DataFrame] = {}

    def quote(gruppe) -> pd.DataFrame:
        g = attempts.groupby(gruppe).agg(
            versuche=("erstversuch_gueltig", "size"),
            gueltig=("erstversuch_gueltig", "sum"),
            fehler_gesamt=("erstversuch_fehleranzahl", "sum"),
        )
        g["quote_gueltig"] = (g["gueltig"] / g["versuche"]).round(3)
        return g

    out["gesamt"] = quote(lambda _: "alle")
    out["je_variante"] = quote("schemavariante")
    out["je_situation"] = quote(["situation", "schemavariante"])

    # Fehlertypen-Verteilung (Erstversuche): aufgesplittete Mehrfachtypen
    ft = attempts["erstversuch_fehlertypen"].fillna("").astype(str)
    typen = (attempts.assign(erstversuch_fehlertypen=ft)
             .loc[ft != "", ["schemavariante", "erstversuch_fehlertypen"]]
             .assign(typ=lambda d: d["erstversuch_fehlertypen"].str.split("|"))
             .explode("typ"))
    if len(typen):
        out["fehlertypen"] = (typen.groupby(["schemavariante", "typ"])
                              .size().rename("anzahl").to_frame())
    else:
        out["fehlertypen"] = pd.DataFrame({"anzahl": []})
    return out


def uf2_korrekturschleife(attempts: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """UF2: Konvergenz der Korrekturschleife."""
    out: dict[str, pd.DataFrame] = {}
    korrigiert = attempts[~attempts["erstversuch_gueltig"]]
    out["konvergenz"] = pd.DataFrame({
        "wert": {
            "versuche_gesamt": len(attempts),
            "erstversuch_ungueltig": len(korrigiert),
            "final_gueltig_nach_korrektur":
                int(korrigiert["final_gueltig"].sum()),
            "nicht_konvergiert (max erreicht)":
                int((~attempts["final_gueltig"]).sum()),
        }})
    out["iterationen_verteilung"] = (attempts.groupby(
        ["schemavariante", "korrekturiterationen"]).size()
        .rename("anzahl").to_frame())
    out["abbruchgruende"] = (attempts.groupby(
        ["schemavariante", "abbruchgrund"]).size()
        .rename("anzahl").to_frame())
    return out


def uf4_schemastrenge(attempts: pd.DataFrame) -> pd.DataFrame:
    """UF4: locker vs. streng kompakt."""
    g = attempts.groupby("schemavariante").agg(
        versuche=("erstversuch_gueltig", "size"),
        erstversuch_gueltig=("erstversuch_gueltig", "sum"),
        fehler_im_erstversuch=("erstversuch_fehleranzahl", "sum"),
        korrekturiterationen_summe=("korrekturiterationen", "sum"),
        final_gueltig=("final_gueltig", "sum"),
    )
    g["erstversuchsquote"] = (g["erstversuch_gueltig"] / g["versuche"]).round(3)
    g["finalquote"] = (g["final_gueltig"] / g["versuche"]).round(3)
    return g


def betriebskennzahlen(iterations: pd.DataFrame) -> pd.DataFrame:
    """Requests, Tokens, Dauer, Codefences — Betriebs- und Kostennachweis."""
    return pd.DataFrame({
        "wert": {
            "requests (Iterationen gesamt)": len(iterations),
            "codefence_entfernt (Anteil)":
                round(float(iterations["codefence_entfernt"].mean()), 3),
            "prompt_tokens_summe": int(iterations["prompt_tokens"].fillna(0).sum()),
            "output_tokens_summe": int(iterations["output_tokens"].fillna(0).sum()),
            "thoughts_tokens_summe":
                int(iterations.get("thoughts_tokens",
                                   pd.Series(dtype=float)).fillna(0).sum()),
            "dauer_mittel_s": round(float(iterations["dauer_s"].mean()), 1),
            "dauer_max_s": float(iterations["dauer_s"].max()),
        }})


def main(lauf_id: str) -> None:
    attempts, iterations = lade(lauf_id)
    teile: list[str] = [f"# Auswertung {lauf_id} (UF1/UF2/UF4)\n",
                        f"Versuche: {len(attempts)}, Iterationen: "
                        f"{len(iterations)}. Quelle: results/{lauf_id}_*.csv\n"]

    uf1 = uf1_erstversuch(attempts)
    teile.append("## UF1 — Erstversuchs-Konformität\n")
    teile.append("### Gesamt\n" + _md(uf1["gesamt"]) + "\n")
    teile.append("### Je Schemavariante\n" + _md(uf1["je_variante"]) + "\n")
    teile.append("### Je Situation × Variante\n" + _md(uf1["je_situation"]) + "\n")
    teile.append("### Formale Fehlertypen (Erstversuche)\n"
                 + _md(uf1["fehlertypen"]) + "\n")

    uf2 = uf2_korrekturschleife(attempts)
    teile.append("## UF2 — Korrekturschleife\n")
    teile.append("### Konvergenz\n" + _md(uf2["konvergenz"]) + "\n")
    teile.append("### Iterationen-Verteilung\n"
                 + _md(uf2["iterationen_verteilung"]) + "\n")
    teile.append("### Terminierung\n" + _md(uf2["abbruchgruende"]) + "\n")

    teile.append("## UF4 — Schemastrenge (locker vs. streng)\n"
                 + _md(uf4_schemastrenge(attempts)) + "\n")

    teile.append("## Betriebskennzahlen\n"
                 + _md(betriebskennzahlen(iterations)) + "\n")

    bericht = "\n".join(teile)
    ziel = config.RESULTS_DIR / f"{lauf_id}_auswertung.md"
    ziel.write_text(bericht, encoding="utf-8")
    print(bericht)
    print(f"\ngeschrieben: {ziel}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "volllauf_v3")
