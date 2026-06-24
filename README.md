# XSD-gesteuerte Informationsextraktion aus Nachrichtenartikeln

Code und Daten zur Bachelorarbeit *„LLM im Journalismus — Konzeption und Evaluation eines XSD-gesteuerten Workflows zur formal validierten Informationsextraktion aus Nachrichtenartikeln"* (Felix Spangenberg, Universität der Bundeswehr München, 2026).

## Worum es geht

Die Pipeline extrahiert aus deutschsprachigen Nachrichtenartikeln strukturierte Informationen als XML und prüft sie **formal gegen ein XML-Schema (XSD)**. Ein großes Sprachmodell (Google Gemini) erhält den Artikel zusammen mit dem passenden XSD und erzeugt ein XML-Dokument; dieses wird gegen das Schema validiert, und bei Verstößen läuft eine begrenzte Korrekturschleife. Anschließend werden die formal gültigen Ausgaben inhaltlich gegen einen manuell erstellten Goldstandard verglichen.

Untersucht werden vier Fragen:

- **UF1** — Wie oft ist der *erste* Extraktionsversuch bereits formal gültig, und welche Fehlertypen treten auf?
- **UF2** — Wie zuverlässig konvergiert die Korrekturschleife, und verändert sie dabei Inhalte?
- **UF3** — Wie oft ist eine formal gültige Ausgabe inhaltlich falsch (gegen den Goldstandard)?
- **UF4** — Wie wirkt sich die Schemastrenge aus? Jede Situation existiert in einer **lockeren** und einer **strengen** XSD-Variante.

Der Korpus umfasst 24 tagesschau.de-Artikel in drei Situationstypen: **A** (politischer Konfliktbericht), **B** (Wirtschafts-/Kennzahlenmeldung), **C** (Ereignis-/Wahlbericht).

## Repository-Struktur

```
src/        Pipeline-Module und ausführbare Skripte
prompts/    Extraktions- und Korrekturprompts (je Situation)
schemas/    sechs XSD-Schemata (Situation A/B/C × locker/streng)
corpus/     Korpus-Manifest und Nachladeskript (keine Volltexte, s. u.)
docs/       Annotationsmanual des Goldstandards
requirements.txt / requirements.lock.txt
```

Wichtige Module in `src/`:

| Datei | Funktion |
|---|---|
| `config.py` | zentrale Konfiguration (Modell, Temperatur, Pfade, API-Key) |
| `corpus_loader.py` / `corpus_manifest.py` | Korpus laden und gegen Erwartungswerte prüfen |
| `extraction.py` | Prompt-Aufbau und Gemini-Aufruf |
| `validation.py` | XSD-Validierung und Fehlerklassifikation |
| `pipeline.py` | Erstversuch → Validierung → Korrekturschleife je Versuch |
| `run_volllauf.py` / `run_testlauf.py` | Lauf-Skripte (24×2×3 bzw. kleiner Vorlauf) |
| `test_korrekturschleife.py` | gezielter Funktionstest der Korrekturschleife |
| `auswertung.py` | Kennzahlen UF1/UF2/UF4 aus den Ergebnis-CSVs |
| `goldvergleich.py` | feldweiser Vergleich gegen den Goldstandard (UF3) |
| `aufloesung.py` | regelbasierte Auflösung der Zweifelsfälle |
| `vollstaendigkeitsmass.py` | Kernobjekt-Recall (Auslassungsmaß) |
| `trafilatura_demonstrator.py` | Vergleich trafilatura vs. manuelle Korpusbereinigung |
| `korpus_nachladen.py` | Korpus aus dem Manifest reproduzierbar nachladen |
| `schema_smoke_test.py` / `api_test.py` | Smoke-Tests für Schemas und API |

## Ausführen

```powershell
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
```

(Unter Linux/macOS analog mit `python3 -m venv venv` und `source venv/bin/activate`.) Für exakt reproduzierbare Versionen `requirements.lock.txt` statt `requirements.txt` installieren.

Der Gemini-API-Schlüssel wird ausschließlich aus einer `.env` im Repository-Wurzelverzeichnis gelesen und nie in Code oder Git gespeichert:

```
GEMINI_API_KEY=dein_schlüssel
```

Alle Skripte werden aus dem Wurzelverzeichnis gestartet, z. B.:

```powershell
./venv/Scripts/python.exe src/schema_smoke_test.py   # alle 6 XSDs kompilieren (ohne Daten/Key lauffähig)
./venv/Scripts/python.exe src/korpus_nachladen.py     # Korpus aus dem Manifest nachladen
./venv/Scripts/python.exe src/api_test.py             # API-Anbindung prüfen (Key nötig)
./venv/Scripts/python.exe src/run_volllauf.py         # vollständiger Lauf (Korpus + Key nötig)
./venv/Scripts/python.exe src/auswertung.py volllauf_v3
```

## Daten- und Codeverfügbarkeit

Öffentlich in diesem Repository: der gesamte **Code**, die **Prompts**, die **Schemata**, das **Korpus-Manifest** samt Nachladeskript und das **Annotationsmanual**.

Nicht im öffentlichen Repository, da sie urheberrechtlich geschützte Artikelinhalte enthalten: die Korpus-**Volltexte**, der **Goldstandard**, die archivierten **Roh-XML-Ausgaben** (`runs/volllauf_v3/`) und die **Ergebnis-CSVs**. Diese liegen vollständig der den Prüferinnen und Prüfern übergebenen, nicht öffentlichen digitalen Anlage bei. Auswertungsskripte wie `auswertung.py`, `goldvergleich.py`, `aufloesung.py` und `vollstaendigkeitsmass.py` benötigen diese Daten und sind daher nur mit der Anlage (bzw. einem nachgeladenen Korpus) voll lauffähig.

## Urheberrecht zum Korpus

Der Korpus besteht aus Artikeln von tagesschau.de — fremdes, geschütztes Material. Es werden **keine Volltexte** veröffentlicht, sondern nur ein Manifest (ID, Situation, Quelle, URL, Abrufdatum) und ein Skript, das den Korpus aus den Quell-URLs reproduzierbar nachlädt (siehe `corpus/README.md`). Die Rechte an den Artikeln verbleiben bei den jeweiligen Rechteinhabern.

## Zitation

> Spangenberg, F. (2026): *LLM im Journalismus — Konzeption und Evaluation eines XSD-gesteuerten Workflows zur formal validierten Informationsextraktion aus Nachrichtenartikeln.* Bachelorarbeit, Universität der Bundeswehr München.

## Lizenz

Code und Dokumentation stehen unter der MIT-Lizenz (siehe `LICENSE`). Die Lizenz erstreckt sich **nicht** auf die Korpusartikel, die nicht Teil des Repositorys sind.
