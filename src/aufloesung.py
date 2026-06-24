"""Konsolidierte Zweifelsfall-Auflösung: klassifiziert die beim Goldstandard-
Vergleich als 'zweifelsfall' markierten Felder regelbasiert in ok,
falsche_zuordnung oder halluzination.

Regeln (dokumentiert in der Spalte 'aufloesung'):
  A1  einheit-Freitext (locker)            -> ok
  A2  werttyp-Erhebungsstatus-Freitext     -> ok        (W1)
  A2b werttyp-Größenart-Freitext           -> falsche_zuordnung (W2)
  A3  Kollektiv-/Zusatzakteur, Name im Text-> ok
  B   kennzahlen.wert nicht im Gold:
        Zahl im Artikeltext (Format-/Skalen-/VORZEICHEN-tolerant) -> ok
        wortförmig belegt ('mehrere hundert' u. ä.)               -> ok
        sonst                                                     -> halluzination
        Sonderfall 008: errechnete Vorjahres-/Folgewerte          -> halluzination
                        (Ableitungs-Unterklasse, Arithmetik geprüft)

Aufruf: python aufloesung.py <lauf_id>
liest  results/<lauf_id>_uf3_findings.csv
schreibt results/<lauf_id>_uf3_findings_final_v2.csv
"""

from __future__ import annotations

import re
import sys

import pandas as pd

import config
from corpus_loader import KORPUS_DIR, lade_korpus

STATUS_OK = ('unverändert', 'geschätzt', 'erwartet', 'gerechnet', 'vorgesehen',
             'prognostiziert', 'änderung', 'erhöhung', 'prognose', 'schätzung',
             'erwartung', 'plan', 'ziel', 'ist', 'absolut', 'aktuell',
             'gemessen', 'alt', 'vorjahr', 'vormonat', 'bisher', 'endgültig',
             'vorläufig', 'veränderung', 'differenz', 'anstieg', 'rückgang',
             'saison', 'hochrechnung', 'beschluss', 'beschlossen',
             'angekündigt', 'real', 'nominal', 'stand', 'meldung', 'fakt')
# 'relativ'/'prozentual' sind grenzwertig (eher W2) und werden konservativ
# unter W2 (Größenart) geführt.
WORTFOERMIG = ('mehrere hundert', 'mehr als zwei drittel', 'jeder zweite')
ERRECHNET_008 = {'2931000', '977000', '3951000', '646000'}
SKAL = (1, 1e3, 1e6, 1e9, 1e12)


def num(s):
    m = re.search(r'-?[\d.,]+', str(s) or '')
    if not m:
        return None
    z = m.group(0)
    if ',' in z:
        z = z.replace('.', '').replace(',', '.')
    elif z.count('.') > 1 or ('.' in z and len(z.split('.')[-1]) == 3):
        z = z.replace('.', '')
    try:
        return float(z)
    except ValueError:
        return None


def zahlen_im_text(t):
    out = set()
    for tok in re.findall(r'\d[\d.,]*', t):
        n = num(tok)
        if n is not None:
            out.add(n)
    return out


def main(lauf_id: str) -> None:
    df = pd.read_csv(config.RESULTS_DIR / f"{lauf_id}_uf3_findings.csv")
    df['feldklasse'] = df['feld'].map(lambda f: re.sub(r'\[[^\]]*\]', '', str(f)))
    df['kategorie_final'] = df['kategorie']
    df['aufloesung'] = ''

    texte = {int(a.artikel_id): (KORPUS_DIR / a.dateiname).read_text(encoding='utf-8')
             for a in lade_korpus()}
    textzahlen = {k: zahlen_im_text(v) for k, v in texte.items()}

    for i, r in df[df.kategorie == 'zweifelsfall'].iterrows():
        k, mwl = r['feldklasse'], str(r['modellwert']).lower().strip()
        aid = int(r['artikel_id'])
        if k == 'kennzahlen.einheit':
            df.loc[i, ['kategorie_final', 'aufloesung']] = \
                ['ok', 'A1: Freitext-Einheit quellentreu (locker)']
        elif k == 'kennzahlen.werttyp':
            if any(w in mwl for w in STATUS_OK):
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['ok', 'W1: Erhebungsstatus-Freitext sinnäquivalent']
            else:
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['falsche_zuordnung',
                     'W2: Werttyp-Feld mit Größenart-/Beschreibungstext gefüllt']
        elif k == 'akteure':
            df.loc[i, ['kategorie_final', 'aufloesung']] = \
                ['ok', 'A3: Zusatz-/Kollektivakteur, Name im Text; '
                       'Zitat/Inhalt separat geprüft']
        elif k == 'kennzahlen.wert':
            m = num(r['modellwert'])
            if any(w in mwl for w in WORTFOERMIG):
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['ok', 'B: wortförmige Angabe wörtlich im Text (locker)']
            elif str(r['modellwert']).strip().lstrip('-').split('.')[0] in ERRECHNET_008 and aid == 8:
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['halluzination', 'B/008: errechneter Wert — arithmetisch '
                     'korrekt, im Text nicht genannt (Ableitungs-Unterklasse)']
            elif m is not None and any(
                    abs(abs(m) - t * s) < 1e-6 * max(1, abs(t * s))
                    or abs(abs(m) * s - t) < 1e-6 * max(1, abs(t))
                    for t in textzahlen[aid] for s in SKAL):
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['ok', 'B: Zahl im Artikeltext belegt '
                           '(Format-/Skalen-/Vorzeichentoleranz)']
            elif abs((m or 0) - 66.67) < 0.01 and aid == 21:
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['ok', 'B/021: dokumentierte Zwei-Drittel-Konversion '
                           '(Gold-Toleranz 66–67, Überpräzisierung vermerkt)']
            else:
                df.loc[i, ['kategorie_final', 'aufloesung']] = \
                    ['halluzination',
                     'B: Zahl im Artikeltext NICHT auffindbar (Textabgleich)']

    df.to_csv(config.RESULTS_DIR / f"{lauf_id}_uf3_findings_final_v2.csv",
              index=False)

    hart = df[df.kategorie_final != 'ok']
    print(f"Befunde gesamt: {len(df)} | ok: {(df.kategorie_final=='ok').sum()} "
          f"| hart: {len(hart)} | offene Zweifelsfälle: "
          f"{(df.kategorie_final=='zweifelsfall').sum()}")
    print(hart.groupby(['kategorie_final', 'schemavariante']).size()
          .unstack(fill_value=0).to_string())
    betroffen = hart[['artikel_id', 'schemavariante', 'wiederholung']].drop_duplicates()
    for var in ('locker', 'streng'):
        b = len(betroffen[betroffen.schemavariante == var])
        print(f"Gültig-aber-falsch ({var}): {b}/72 = {b/72:.1%}")
    print(f"Gesamt: {len(betroffen)}/144 = {len(betroffen)/144:.1%}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "volllauf_v3")
