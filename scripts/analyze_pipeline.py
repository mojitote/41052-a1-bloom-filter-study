"""Validate and summarize the separately dated exact-pipeline experiment."""
import argparse,csv,json,math,statistics
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
p=argparse.ArgumentParser();p.add_argument('csv',type=Path);p.add_argument('--out',type=Path,default=Path('figures'));a=p.parse_args();a.out.mkdir(exist_ok=True,parents=True)
rows=list(csv.DictReader(a.csv.open()))
assert len(rows)==4*2*2*4*7*3
seen=set();groups=defaultdict(list);calls={}
for r in rows:
    seed,n,k,rep=map(int,[r['seed'],r['n'],r['k'],r['repeat']]);q=float(r['negative_fraction']);method=r['method']
    assert seed in range(1,5) and n in (20000,200000) and k in (1,7) and rep in range(7) and q in (0,.5,.9,1) and method in ('set','early_exit','full_scan')
    ident=(seed,n,k,q,method,rep);assert ident not in seen;seen.add(ident)
    assert int(r['returned_positive'])==int(r['expected_positive'])==round(200000*(1-q))
    val=float(r['ns_per_query']);assert math.isfinite(val) and val>0
    key=(seed,n,k,q,method);groups[key].append(val)
    calls.setdefault(key,int(r['backend_calls']));assert calls[key]==int(r['backend_calls'])
med={key:statistics.median(values) for key,values in groups.items()}
def ci(vals): return {'mean':statistics.mean(vals),'ci95_half':3.1824463053*statistics.stdev(vals)/2}
summary=[]
for n in (20000,200000):
 for k in (1,7):
  for q in (0,.5,.9,1):
   record=dict(n=n,k=k,negative_fraction=q)
   for seed in range(1,5):assert calls[seed,n,k,q,'early_exit']==calls[seed,n,k,q,'full_scan']
   for name,num,den in [('early_speedup','set','early_exit'),('full_speedup','set','full_scan'),('full_over_early','early_exit','full_scan')]:
    record[name]=ci([med[s,n,k,q,num]/med[s,n,k,q,den] for s in range(1,5)])
   summary.append(record)
(a.out/'pipeline_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (a.out/'pipeline_summary.csv').open('w') as f:
 writer=csv.writer(f);writer.writerow(['n','k','absent_fraction','early_speedup','early_ci95','full_speedup','full_ci95','full_over_early','ratio_ci95'])
 for r in summary:writer.writerow([r['n'],r['k'],r['negative_fraction']]+[r[name][v] for name in ('early_speedup','full_speedup','full_over_early') for v in ('mean','ci95_half')])
fig,axes=plt.subplots(1,2,figsize=(10,3.4))
for ax,n in zip(axes,(20000,200000)):
 for k,color in [(1,'#165D96'),(7,'#D45D00')]:
  rs=[r for r in summary if r['n']==n and r['k']==k]
  for name,style,label in [('early_speedup','o--','early exit'),('full_speedup','s-','full scan')]:
   ax.errorbar([r['negative_fraction']*100 for r in rs],[r[name]['mean'] for r in rs],yerr=[r[name]['ci95_half'] for r in rs],fmt=style,color=color,label=f'k={k}, {label}',capsize=2,ms=4)
 ax.axhline(1,color='gray',lw=1);ax.set(title=f'n = {n:,}',xlabel='Absent queries (%)',ylabel='Exact set time / pipeline time');ax.legend(fontsize=7)
fig.tight_layout();fig.savefig(a.out/'pipeline_exit.png',dpi=170);plt.close(fig)
print(json.dumps(summary,indent=2))
