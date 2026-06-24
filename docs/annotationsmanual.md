# Annotationsmanual des Goldstandards

Dieses Manual dokumentiert die Kriterien und Regeln, nach denen der Goldstandard erstellt und der Abgleich der Modellausgaben aufgelöst wurde. Es macht die Einzelannotation nachvollziehbar. Faktengrundlage je Artikel ist ausschließlich der zugehörige Artikeltext; die Auflösungsregeln sind im Skript `src/aufloesung.py` als Code reproduziert.

## 1 Belegstatus je Feld

Jedes Goldstandard-Feld trägt einen Belegstatus. Er steuert, ob eine Modellangabe als gedeckt, als zulässige Ableitung oder als Halluzination gilt.

- belegt: Der Wert ist wörtlich oder eindeutig im Artikeltext belegt. Eine abweichende Modellangabe ist je nach Art falscher Wert, Präzisionsverlust oder falsche Zuordnung.
- ableitbar: Der Wert ist nicht wörtlich belegt, lässt sich aber zulässig aus dem Text oder aus allgemein zugänglichem Wissen erschließen, etwa die Partei aus der Funktionsbezeichnung „Unionsfraktionschef". Nennt das Modell den ableitbaren Wert, gilt das nicht als Halluzination.
- unbelegt: Der Artikel bietet keine Entsprechung. Unter der lockeren Variante darf das Feld entfallen. Unter der strengen Variante ist es dennoch Pflicht und bildet damit eine eingebaute Halluzinations-Messstelle: Eine vom Modell dennoch gelieferte Angabe ist eine erzwungene Erfindung.

Je Feld werden zusätzlich ein Sollwert, eine Liste zulässiger Alternativwerte (gleichwertige Belege oder dokumentierte konkurrierende Angaben) und bei der strengen Variante der erforderliche Constraint (Enumerationswert, xs:date-Form) festgehalten.

## 2 Regeln zur Auflösung von Zweifelsfällen

Ein Zweifelsfall liegt vor, wenn eine Modellangabe nicht unmittelbar mit dem Goldstandard-Sollwert übereinstimmt, aber auch nicht offensichtlich falsch ist. Die folgenden neun Regeln lösen diese Fälle einheitlich und offengelegt auf. Sie sind im Skript `src/aufloesung.py` reproduziert.

1. A1 — Freitext-Einheit (locker): Eine quellentreue, frei formulierte Einheit im Einheit-Feld der lockeren Variante gilt als korrekt (ok), da die lockere Variante keine Enumeration vorgibt.
2. W1 — Erhebungsstatus im Werttyp-Feld: Ein frei formulierter Erhebungsstatus, der sinnäquivalent zu einem zulässigen Werttyp ist (etwa „prognostiziert", „vorläufig", „Veränderung"), gilt als korrekt.
3. W2 — Größenart im Werttyp-Feld: Steht im Werttyp-Feld stattdessen eine Größenart- oder Beschreibungsangabe (etwa „relativer Wert"), gilt dies als falsche Zuordnung.
4. A3 — Zusatz- oder Kollektivakteur: Nennt das Modell einen zusätzlichen oder kollektiven Akteur, dessen Name im Text belegt ist, gilt der Akteur als korrekt; sein Zitat und seine übrigen Felder werden separat geprüft.
5. B — Zahl im Text (Format-, Skalen- und Vorzeichentoleranz): Ein Kennzahlwert, der nicht wörtlich dem Sollwert entspricht, aber als Zahl im Artikeltext auffindbar ist, gilt als korrekt. Toleriert werden abweichende Schreibweise, Skalierung (Tausender, Millionen) und Vorzeichenlogik.
6. B — wortförmige Angabe: Eine wortförmig belegte Mengenangabe im Wert-Feld (etwa „mehrere hundert", „mehr als zwei Drittel") gilt in der lockeren Variante als korrekt, sofern sie wörtlich im Text steht.
7. B/008 — errechneter Wert (Ableitungs-Unterklasse): Leitet das Modell in Artikel 008 Vorjahres- oder Folgewerte arithmetisch korrekt aus im Text genannten Differenzen ab (etwa 2.931.000 aus 3.008.000 minus 77.000), ohne dass der Wert selbst im Text steht, gilt dies als Halluzination einer eigenen Unterklasse: rechnerisch korrekt, aber quellenungedeckt.
8. B/021 — dokumentierte Zwei-Drittel-Konversion: Die Umrechnung „mehr als zwei Drittel" in 66,67 in Artikel 021 gilt im Rahmen der dokumentierten Gold-Toleranz (66 bis 67) als korrekt; die Überpräzisierung ist vermerkt.
9. C1 — Datumsformat-Toleranz: Ein wertgleiches Datum in abweichendem, nicht-ISO-konformem Format (etwa „08.03.2026" statt „2026-03-08") gilt nicht als Halluzination, sondern als Präzisionsverlust, da der Informationsgehalt unverändert ist. Diese Regel gilt einheitlich für Veröffentlichungs- und Ereignisdatum.

## 3 Hinweise zur Anwendung

Die Regeln A1, W1, A3, B (Zahl im Text), B (wortförmig) und B/021 lösen Zweifelsfälle zugunsten der Korrektheit auf; W2, B/008 und C1 ordnen sie einem inhaltlichen Fehlertyp zu. Wertgleiche, nur unnormalisierte Formen werden nach C1 als Präzisionsverlust und nicht als Halluzination geführt. Eine unabhängig implementierte Gegenprüfung hat diese Auflösungen stichprobenartig kontrolliert und an einzelnen Stellen korrigiert.
