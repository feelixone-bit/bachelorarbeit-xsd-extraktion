# Korpus — Manifest und Nachladen

Der Artikelkorpus besteht aus 24 Nachrichtenartikeln von tagesschau.de. Die **Volltexte sind aus urheberrechtlichen Gründen nicht Teil dieses Repositorys** — es handelt sich um fremdes, geschütztes Material. Stattdessen liegt hier ein Manifest mit den Metadaten, das eine reproduzierbare Wiederherstellung erlaubt.

## `corpus_manifest.csv`

Eine Zeile je Artikel mit:

| Spalte | Bedeutung |
|---|---|
| `artikel_id` | laufende ID (001–024) |
| `situation` | Schemasituation A, B oder C |
| `quelle` | Herausgeber (tagesschau.de) |
| `url` | Quell-URL des Artikels |
| `abrufdatum` | Datum des ursprünglichen Abrufs (ISO) |

## Korpus nachladen

```powershell
python src/korpus_nachladen.py
```

Das Skript ruft jede URL aus dem Manifest ab, extrahiert den Haupttext mit [trafilatura](https://trafilatura.readthedocs.io/) und legt pro Artikel eine Datei `article_<id>_nachgeladen.txt` mit Metadatenkopf in diesem Ordner ab.

**Hinweis:** Die nachgeladene Fassung entspricht der trafilatura-Extraktion, nicht der manuell bereinigten Korpusfassung der Arbeit. Beide unterscheiden sich an Randstellen (Boilerplate-Reste, erhaltene Zwischenüberschriften); dieser Unterschied ist im `trafilatura_demonstrator` quantifiziert. Online verfügbare Artikel können sich zudem seit dem Abrufdatum geändert haben oder nicht mehr erreichbar sein.

Die vollständigen, manuell bereinigten Originaltexte sowie der darauf aufbauende Goldstandard liegen der den Prüfern übergebenen, nicht öffentlichen digitalen Anlage bei.
