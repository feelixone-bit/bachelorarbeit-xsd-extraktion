"""UF3-Goldstandard-Vergleich: automatisierter Feldvergleich der final
gültigen XMLs gegen die Goldstandard-YAMLs, plus Abgleich mit den je Artikel
erwarteten Halluzinationsstellen.

Ansatz: Automatisch entscheidbare Checks werden hart klassifiziert, alles
Übrige als 'zweifelsfall' für die manuelle Nachbewertung markiert
(automatisierter Feldvergleich plus manuelle Nachbewertung).

Automatische Checks:
  alle  : artikelmetadaten (titel exakt, quelle, datum vs. Gold)
  A     : Akteursname im Artikeltext? · Zitat VERBATIM im Artikeltext?
          · Partei vs. Gold (sollwert/streng_enum/alternativen)
          · Zitat vorhanden, obwohl Gold 'unbelegt' (erwartete Halluzination)
  B     : Kennzahl-Wert numerisch gegen Gold-Liste (inkl. Skalenfaktoren
          10^3/6/9/12 für Mio/Mrd-Normalisierung und Alternativen);
          bei Treffer: Einheit/Werttyp/Bezugszeitraum/Quelle vs. Gold
  C     : Ereignisdatum vs. Gold (sollwert+alternativen) · Ort vs. Gold
          · Ergebnis-Person im Text? · Prozentwert gegen belegte Gold-Prozente
          · Beteiligten-Name im Text?

Inhaltliche Fehlertaxonomie: halluzination, falscher_wert,
falsche_zuordnung, praezisionsverlust, auslassung — plus 'zweifelsfall'
(nur Arbeitskategorie, wird manuell aufgelöst).

Ausgabe: results/<lauf_id>_uf3_findings.csv (eine Zeile je Befund) und
Konsolen-Zusammenfassung.
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata

import xmlschema
import yaml

import config
import validation
from corpus_loader import KORPUS_DIR, lade_korpus
from corpus_manifest import ERWARTUNG


# --------------------------------------------------------------- Normalisierung
def norm_text(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    t = t.replace("„", '"').replace("“", '"').replace("”", '"')
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"\s+", " ", t).strip().lower()
    return t


_QUOTE_CHARS = re.compile(r"[\"'‚‛‹›«»]")
_DT_DE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def verbatim_im_text(zitat: str, artikel_norm: str) -> bool:
    """Verbatim-Check; typografische/gerade Anführungszeichen werden auf
    BEIDEN Seiten vollständig entfernt — sonst erzeugen vom Modell
    mitgelieferte Anführungszeichen im Zitatwert Fehlalarme."""
    z = _QUOTE_CHARS.sub("", norm_text(zitat)).strip(" .,!?:;")
    a = _QUOTE_CHARS.sub("", artikel_norm)
    return bool(z) and z in a


def iso_daten(s: str) -> set[str]:
    """extrahiert ALLE Datumsangaben (ISO und deutsches Format, auch
    Spannen) als ISO-Set — Format-Varianz ist damit keine Wertabweichung."""
    out = set(re.findall(r"\d{4}-\d{2}-\d{2}", s or ""))
    for d, m, y in _DT_DE.findall(s or ""):
        out.add(f"{y}-{int(m):02d}-{int(d):02d}")
    return out


def name_im_text(name: str, artikel_norm: str) -> bool:
    """Nachname genügt (Artikel nennen oft nur 'Spahn')."""
    teile = [w for w in re.split(r"\s+", norm_text(name)) if len(w) > 2]
    return bool(teile) and teile[-1] in artikel_norm


def num(wert) -> float | None:
    """robuste Zahlextraktion: toleriert Einheiten-Anhänge ('59 Prozent'),
    deutsches Komma und Tausenderpunkte ('3.008.000')."""
    s = str(wert or "").strip()
    m = re.search(r"-?[\d.,]+", s)
    if not m:
        return None
    z = m.group(0)
    if "," in z:                       # deutsches Format: Punkt=Tausender
        z = z.replace(".", "").replace(",", ".")
    elif z.count(".") > 1:             # nur Tausenderpunkte
        z = z.replace(".", "")
    try:
        return float(z)
    except ValueError:
        return None


SKALEN = (1.0, 1e3, 1e6, 1e9, 1e12)


def zahlen_match(modell, gold_werte: list) -> bool:
    m = num(modell)
    if m is None:
        return False
    for g in gold_werte:
        gn = num(g)
        if gn is None:
            continue
        for s in SKALEN:
            if abs(m - gn * s) < 1e-6 * max(1.0, abs(gn * s)) \
                    or abs(m * s - gn) < 1e-6 * max(1.0, abs(gn)):
                return True
    return False


# ------------------------------------------------------------------- Vergleich
class Vergleicher:
    def __init__(self, lauf_id: str):
        self.lauf_id = lauf_id
        self.findings: list[dict] = []

    def melde(self, basis: dict, feld: str, kategorie: str, befund: str,
              modellwert, erwartung) -> None:
        self.findings.append({
            **basis, "feld": feld, "kategorie": kategorie, "befund": befund,
            "modellwert": str(modellwert)[:200],
            "erwartung": str(erwartung)[:200],
        })

    # ---- gemeinsame Checks ---------------------------------------------------
    def check_metadaten(self, basis, d, gold) -> None:
        gm = gold["felder"]["artikelmetadaten"]
        md = d.get("artikelmetadaten") or {}
        if norm_text(md.get("titel", "")) != norm_text(gm["titel"]["sollwert"]):
            self.melde(basis, "artikelmetadaten.titel", "falscher_wert",
                       "Titel weicht vom Metadatenkopf ab",
                       md.get("titel"), gm["titel"]["sollwert"])
        datum = str(md.get("veroeffentlichungsdatum", ""))
        soll = gm["veroeffentlichungsdatum"]["sollwert"]
        gefunden = iso_daten(datum)
        if soll in gefunden:
            if datum.strip() != soll and basis["schemavariante"] == "streng":
                # locker: keine Formatvorgabe -> wertgleiches Datum ist KEIN
                # inhaltlicher Fehler (sonst Confound mit der Schemastrenge)
                self.melde(basis, "artikelmetadaten.veroeffentlichungsdatum",
                           "praezisionsverlust",
                           "Datum wertgleich, aber Nicht-ISO-Format", datum, soll)
        else:
            self.melde(basis, "artikelmetadaten.veroeffentlichungsdatum",
                       "falscher_wert", "Datum weicht ab", datum, soll)

    # ---- Situation A ----------------------------------------------------------
    def check_a(self, basis, d, gold, artikel_norm) -> None:
        gold_akteure = {norm_text(a["name"]["sollwert"]): a
                        for a in gold["felder"]["akteure"]["liste"]}
        for ak in ((d.get("akteure") or {}).get("akteur") or []):
            name = ak.get("name") or ""
            fbasis = f"akteure[{name}]"
            if not name_im_text(name, artikel_norm):
                self.melde(basis, fbasis + ".name", "halluzination",
                           "Akteursname nicht im Artikeltext", name, "-")
                continue
            g = gold_akteure.get(norm_text(name))
            zitat = ak.get("zitat")
            if zitat:
                if not verbatim_im_text(zitat, artikel_norm):
                    erwartet = bool(g) and g["zitat"]["status"] == "unbelegt"
                    self.melde(basis, fbasis + ".zitat", "halluzination",
                               "Zitat nicht verbatim im Artikeltext"
                               + (" (Gold: unbelegt — erwartete Messstelle)"
                                  if erwartet else " (Glättung/Erfindung)"),
                               zitat, "verbatim erforderlich")
            elif g and g["zitat"]["status"] == "belegt" \
                    and basis["schemavariante"] == "streng":
                self.melde(basis, fbasis + ".zitat", "auslassung",
                           "belegtes Zitat fehlt", "-", g["zitat"]["sollwert"])
            partei = ak.get("partei_oder_organisation")
            if g and partei is not None:
                gp = g["partei_oder_organisation"]
                zulaessig = {norm_text(str(gp.get("sollwert")))} \
                    | {norm_text(str(x)) for x in (gp.get("alternativen") or [])} \
                    | {norm_text(str(gp.get("streng_enum", "")))}
                pn = norm_text(str(partei))
                ok = pn in zulaessig or any(
                    z and len(z) > 2 and (z in pn or pn in z) for z in zulaessig)
                if not ok:
                    self.melde(basis, fbasis + ".partei", "falsche_zuordnung",
                               "Partei/Organisation weicht von Gold ab",
                               partei, sorted(zulaessig))
            if g is None:
                self.melde(basis, fbasis, "zweifelsfall",
                           "Akteur nicht im Gold-Kern (Zusatzakteur? manuell prüfen)",
                           name, "-")

    # ---- Situation B ----------------------------------------------------------
    def check_b(self, basis, d, gold, artikel_norm) -> None:
        gold_kz = gold["felder"]["kennzahlen"]["liste"]
        for kz in ((d.get("kennzahlen") or {}).get("kennzahl") or []):
            wert = kz.get("wert")
            bez = str(kz.get("bezeichnung", ""))[:60]
            fbasis = f"kennzahlen[{bez}]"
            # ALLE wertgleichen Gold-Kennzahlen als Kandidaten: ein
            # Erst-Treffer-Mapping erzeugt Fehlalarme bei wertgleichen
            # Kennzahlen (z. B. dreimal 2,0 in Artikel 010).
            kandidaten = [g for g in gold_kz if zahlen_match(
                wert, [g["wert"].get("sollwert")]
                + list(g["wert"].get("alternativen") or []))]
            if not kandidaten:
                self.melde(basis, fbasis + ".wert", "zweifelsfall",
                           "Wert keiner Gold-Kennzahl zuordenbar (manuell prüfen)",
                           wert, "-")
                continue
            locker = basis["schemavariante"] == "locker"

            def _aequiv(feldname, mvn, menge):
                if feldname == "zahlenquelle":
                    return any(z and (z in mvn or mvn in z) for z in menge)
                if feldname == "bezugszeitraum":
                    return any(z and z in mvn for z in menge)
                if feldname == "einheit":
                    woerter = {"prozent": "prozent", "%": "prozent",
                               "euro": "euro", "eur": "euro", "€": "euro",
                               "personen": "personen", "menschen": "personen",
                               "stück": "stueck", "stueck": "stueck"}
                    return any(w in mvn and e in menge for w, e in woerter.items())
                return False

            for feldname in ("einheit", "werttyp", "bezugszeitraum", "zahlenquelle"):
                mv = kz.get(feldname)
                if mv is None:
                    continue
                mvn = norm_text(str(mv))
                ok = False
                nachbewertung = None   # Gold-Kommentar verlangt manuelle Nachbewertung
                for g in kandidaten:
                    gf = g.get(feldname) or {}
                    soll = gf.get("sollwert")
                    if soll is None:
                        ok, nachbewertung = True, None
                        break
                    zul_soll = {norm_text(str(soll))}
                    zul_alt = {norm_text(str(x))
                               for x in (gf.get("alternativen") or [])}
                    if mvn in zul_soll or _aequiv(feldname, mvn, zul_soll):
                        ok, nachbewertung = True, None
                        break
                    if mvn in zul_alt or _aequiv(feldname, mvn, zul_alt):
                        ok = True
                        komm = str(gf.get("kommentar", "")).lower()
                        if "präzisionsverlust" in komm or "nachbewert" in komm:
                            nachbewertung = g     # weiter: evtl. Soll-Treffer
                if ok:
                    if nachbewertung is not None:
                        self.melde(basis, f"{fbasis}.{feldname}",
                                   "praezisionsverlust",
                                   f"Gold-Nachbewertung: nur tolerierte "
                                   f"Alternative (Kennzahl: "
                                   f"{nachbewertung['bezeichnung'][:50]})",
                                   mv, nachbewertung[feldname].get("sollwert"))
                    continue
                referenz = kandidaten[0]
                zulaessig = set()
                for g in kandidaten:
                    gf = g.get(feldname) or {}
                    if gf.get("sollwert") is not None:
                        zulaessig.add(norm_text(str(gf["sollwert"])))
                    zulaessig |= {norm_text(str(x))
                                  for x in (gf.get("alternativen") or [])}
                if locker and feldname in ("einheit", "werttyp"):
                    self.melde(basis, f"{fbasis}.{feldname}", "zweifelsfall",
                               f"{feldname} (Freitext) nicht automatisch "
                               f"zuordenbar (Kennzahl: {referenz['bezeichnung'][:50]})",
                               mv, sorted(zulaessig))
                else:
                    kategorie = ("praezisionsverlust"
                                 if feldname in ("einheit", "bezugszeitraum")
                                 else "falsche_zuordnung")
                    self.melde(basis, f"{fbasis}.{feldname}", kategorie,
                               f"{feldname} weicht von Gold ab (bei allen "
                               f"wertgleichen Kennzahlen, z. B. "
                               f"{referenz['bezeichnung'][:50]})",
                               mv, sorted(zulaessig))

    # ---- Situation C ----------------------------------------------------------
    def check_c(self, basis, d, gold, artikel_norm) -> None:
        ge = gold["felder"]["ereignisdatum"]
        zulaessig = {str(ge.get("sollwert"))} | {str(x) for x in
                                                 (ge.get("alternativen") or [])}
        datum = str(d.get("ereignisdatum", ""))
        gefunden = iso_daten(datum)
        if datum and not gefunden:
            # kein Datum extrahierbar (z. B. "am Abend", nur locker möglich)
            self.melde(basis, "ereignisdatum", "praezisionsverlust",
                       "Ereignisdatum nur als unscharfe Textform (quellentreu, "
                       "kein Datumswert)", datum, sorted(zulaessig))
        elif gefunden and not gefunden <= zulaessig:
            self.melde(basis, "ereignisdatum", "halluzination",
                       "Ereignisdatum weder Gold-Sollwert noch zulässige Ableitung",
                       datum, sorted(zulaessig))
        elif gefunden and datum.strip() not in zulaessig                 and basis["schemavariante"] == "streng":
            # locker: wertgleiche Formatvarianten/Spannen sind quellentreu und
            # KEIN inhaltlicher Fehler (z. B. 018-Spanne)
            self.melde(basis, "ereignisdatum", "praezisionsverlust",
                       "Ereignisdatum wertgleich, aber Nicht-ISO-Format oder "
                       "Spanne", datum, sorted(zulaessig))
        go = gold["felder"]["ort"]
        ort = d.get("ort")
        if ort and go.get("sollwert") is None \
                and norm_text(str(ort)) not in {norm_text(str(x)) for x in
                                                (go.get("alternativen") or [])}:
            self.melde(basis, "ort", "halluzination",
                       "Ort angegeben, im Artikel aber nicht genannt", ort, None)
        gold_prozente = set()
        for g in gold["felder"]["ergebnisse"]["liste"]:
            p = (g.get("prozent") or {}).get("sollwert")
            if p is not None:
                gold_prozente.add(float(str(p).replace(",", ".")))
        for erg in ((d.get("ergebnisse") or {}).get("ergebnis") or []):
            person = erg.get("person")
            if person and not name_im_text(str(person), artikel_norm):
                self.melde(basis, "ergebnisse.person", "halluzination",
                           "Ergebnis-Person nicht im Artikeltext", person, "-")
            p = num(erg.get("prozent"))
            if p is not None and gold_prozente and p not in gold_prozente:
                self.melde(basis, "ergebnisse.prozent", "falscher_wert",
                           "Prozentwert nicht unter den belegten Gold-Prozenten",
                           p, sorted(gold_prozente))
        for b in ((d.get("beteiligte") or {}).get("beteiligter") or []):
            nm = b.get("name")
            if nm and not name_im_text(str(nm), artikel_norm):
                self.melde(basis, "beteiligte.name", "halluzination",
                           "Beteiligten-Name nicht im Artikeltext", nm, "-")


def main(lauf_id: str) -> None:
    artikel_map = {a.artikel_id: a for a in lade_korpus()}
    v = Vergleicher(lauf_id)

    # final gültige XMLs: letzte Iteration je Versuch mit gueltig=True
    finale: dict[tuple, dict] = {}
    with (config.RESULTS_DIR / f"{lauf_id}_iterations.csv").open(
            encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["artikel_id"], row["schemavariante"], row["wiederholung"])
            if row["gueltig"].lower() == "true":
                if key not in finale or int(row["iteration"]) > int(
                        finale[key]["iteration"]):
                    finale[key] = row

    geprueft = 0
    for (aid, variante, w), row in sorted(finale.items()):
        situation = ERWARTUNG[aid]["situation"]
        gold = yaml.safe_load((config.GOLDSTANDARD_DIR /
                               f"article_{aid}.yaml").read_text(encoding="utf-8"))
        artikel = artikel_map[aid]
        artikel_roh = (KORPUS_DIR / artikel.dateiname).read_text(encoding="utf-8")
        artikel_norm = norm_text(artikel_roh)
        xml_text = (config.PIPELINE_DIR / row["xml_datei"]).read_text(
            encoding="utf-8")
        schema = validation.lade_schema(situation, variante)
        d = schema.to_dict(xml_text)
        basis = {"lauf_id": lauf_id, "artikel_id": aid, "situation": situation,
                 "schemavariante": variante, "wiederholung": w,
                 "iteration": row["iteration"]}
        v.check_metadaten(basis, d, gold)
        if situation == "A":
            v.check_a(basis, d, gold, artikel_norm)
        elif situation == "B":
            v.check_b(basis, d, gold, artikel_norm)
        else:
            v.check_c(basis, d, gold, artikel_norm)
        geprueft += 1

    felder = ["lauf_id", "artikel_id", "situation", "schemavariante",
              "wiederholung", "iteration", "feld", "kategorie", "befund",
              "modellwert", "erwartung"]
    ziel = config.RESULTS_DIR / f"{lauf_id}_uf3_findings.csv"
    with ziel.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=felder)
        wr.writeheader()
        wr.writerows(v.findings)

    # Zusammenfassung
    from collections import Counter
    print(f"Geprüfte final gültige XMLs: {geprueft}")
    print(f"Befunde gesamt: {len(v.findings)}  -> {ziel.name}")
    print("\nBefunde je Kategorie x Variante:")
    c = Counter((f_["kategorie"], f_["schemavariante"]) for f_ in v.findings)
    for (kat, var), n in sorted(c.items()):
        print(f"  {kat:<20} {var:<8} {n}")
    betroffen = {(f_["artikel_id"], f_["schemavariante"], f_["wiederholung"])
                 for f_ in v.findings if f_["kategorie"] != "zweifelsfall"}
    print(f"\nVersuche mit >=1 hartem Befund (ohne Zweifelsfälle): "
          f"{len(betroffen)}/{geprueft} "
          f"({len(betroffen)/geprueft:.1%}) — vorläufige Gültig-aber-falsch-Quote")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "volllauf_v3")
