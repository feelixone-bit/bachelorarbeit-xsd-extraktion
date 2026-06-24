"""Vollständigkeitsmaß (Kernobjekt-Recall).

Misst, wie viele der im Goldstandard belegten Kernobjekte je Artikel in den
final gültigen Modellausgaben tatsächlich auftauchen — als Ergänzung zum
feldweisen Präzisionsvergleich, der Auslassungen nicht erfasst.

Kernobjekt-Identifikator je Situation:
- A: die Namen der gelisteten Akteure
- B: die belegten Kennzahlwerte (kennzahlen.liste[*].wert)
- C: die Personen der gelisteten Ergebnisse (ergebnisse.liste[*].person)

Der Abgleich ist mengenbasiert (robuster gegen wertgleiche Kennzahlen): Namen
über Teilstring-Übereinstimmung, Kennzahlwerte über Format-, Skalen- und
Vorzeichentoleranz. Fehlt der Identifikator eines Kernobjekts in der Ausgabe,
zählt das als Auslassung.

Eingaben (Skript aus dem Repository-Wurzelverzeichnis ausführen):
  goldstandard/article_*.yaml   Goldstandard je Artikel
  runs/volllauf_v3/*.xml        archivierte Modellausgaben je Iteration
"""

import yaml, glob, re, os
from collections import defaultdict
import xml.etree.ElementTree as ET
GOLD="goldstandard"; RUNS="runs/volllauf_v3"; SKAL=(1,1e3,1e6,1e9,1e12)

def num(s):
    m=re.search(r'-?[\d.,]+', str(s) or '')
    if not m: return None
    z=m.group(0)
    if ',' in z: z=z.replace('.','').replace(',','.')
    elif z.count('.')>1 or ('.' in z and len(z.split('.')[-1])==3): z=z.replace('.','')
    try: return float(z)
    except: return None

def nt(s): return re.sub(r'\s+',' ',str(s or '')).strip().lower()

# Gold-Kernobjekte je Artikel
gold_core={}
for fp in sorted(glob.glob(f"{GOLD}/article_*.yaml")):
    g=yaml.safe_load(open(fp,encoding='utf-8')); aid=int(g['meta']['artikel_id'])
    sit=g['meta']['situation']; F=g['felder']; items=[]
    if sit=='A':
        for a in F['akteure']['liste']:
            nm=a.get('name',{}).get('sollwert')
            if nm: items.append(('name',nt(nm),[]))
    elif sit=='B':
        for k in F['kennzahlen']['liste']:
            w=k.get('wert',{})
            if isinstance(w,dict) and w.get('sollwert') is not None and w.get('status','belegt')=='belegt':
                alts=[num(x) for x in (w.get('alternativen') or [])]
                items.append(('num',num(w['sollwert']),[a for a in alts if a is not None]))
    elif sit=='C':
        for e in F.get('ergebnisse',{}).get('liste',[]):
            p=e.get('person',{})
            if isinstance(p,dict) and p.get('sollwert') and p.get('status','belegt')=='belegt':
                items.append(('name',nt(p['sollwert']),[]))
    gold_core[aid]=(sit,items)

# finale XML je Versuch (höchste Iteration)
finals={}
for fp in glob.glob(f"{RUNS}/*.xml"):
    m=re.match(r'article_(\d+)_(locker|streng)_w(\d)_iter(\d+)\.xml', os.path.basename(fp))
    if not m: continue
    aid,var,w,it=int(m[1]),m[2],int(m[3]),int(m[4]); key=(aid,var,w)
    if key not in finals or it>finals[key][0]: finals[key]=(it,fp)

def model_ids(sit, root):
    onum=set(); oname=set()
    if sit=='A':
        for n in root.iter('name'): oname.add(nt(n.text))
    elif sit=='B':
        for k in root.iter('kennzahl'):
            wv=k.find('wert')
            if wv is not None:
                n=num(wv.text)
                if n is not None: onum.add(n)
    elif sit=='C':
        for p in root.iter('person'): oname.add(nt(p.text))
        for n in root.iter('name'): oname.add(nt(n.text))
    return onum,oname

def present(kind,ident,alts,mnum,mname):
    if kind=='name':
        return any(ident and (ident in x or x in ident) for x in mname if x)
    for c in [ident]+list(alts):
        if c is None: continue
        for mv in mnum:
            for s in SKAL:
                if abs(abs(mv)-abs(c)*s)<1e-6*max(1,abs(c)*s) or abs(abs(mv)*s-abs(c))<1e-6*max(1,abs(c)):
                    return True
    return False

agg=defaultdict(lambda:[0,0,0,0])
for (aid,var,w),(it,fp) in finals.items():
    sit,items=gold_core[aid]
    if not items: continue
    root=ET.parse(fp).getroot()
    mnum,mname=model_ids(sit,root)
    miss=sum(0 if present(k,i,a,mnum,mname) else 1 for (k,i,a) in items)
    agg[var][0]+=len(items); agg[var][1]+=miss; agg[var][2]+=1; agg[var][3]+=(1 if miss>0 else 0)


# Ergebnis als Tabelle ausgeben (locker / streng / gesamt)
def _anteil(zaehler, nenner):
    return f"{zaehler / nenner:.1%}" if nenner else "n/a"

print(f"{'Variante':<8} {'Kernobjekte':>11} {'ausgelassen':>11} {'Anteil':>8}  "
      f"Ausgaben mit >=1 Auslassung")
gesamt = [0, 0, 0, 0]
for var in sorted(agg):
    kern, miss, ausg, ausg_miss = agg[var]
    gesamt = [gesamt[i] + agg[var][i] for i in range(4)]
    print(f"{var:<8} {kern:>11} {miss:>11} {_anteil(miss, kern):>8}  "
          f"{ausg_miss}/{ausg} = {_anteil(ausg_miss, ausg)}")
kern, miss, ausg, ausg_miss = gesamt
print(f"{'gesamt':<8} {kern:>11} {miss:>11} {_anteil(miss, kern):>8}  "
      f"{ausg_miss}/{ausg} = {_anteil(ausg_miss, ausg)}")
