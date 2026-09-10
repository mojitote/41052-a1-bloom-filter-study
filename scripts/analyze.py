"""Validate raw measurements and regenerate all report figures and summary tables.

Uncertainty unit: independent seeded workload/filter, not repeated timed loops.
Timing: median of 7 repetitions per seed, then mean and Student t 95% CI over 4 seeds.
Accuracy: mean and Student t 95% CI over 8 seeded filters. These are descriptive
intervals under the seeded sampling model, not guarantees for adversarial inputs.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def interval(values):
    a = np.array(values, dtype=float)
    mean = float(a.mean())
    # Two-sided 95% Student t quantiles, df = trials - 1 (NIST t table).
    critical = {2: 12.7062047364, 4: 3.1824463053, 8: 2.3646242516}
    if len(a) not in critical: raise ValueError("Expected 2, 4 or 8 seeded trials")
    half = float(critical[len(a)] * a.std(ddof=1) / np.sqrt(len(a)))
    return mean, half

def summarize(frame, group, value):
    records=[]
    for key, chunk in frame.groupby(group):
        if not isinstance(key,tuple): key=(key,)
        mean, half=interval(chunk[value])
        records.append(dict(zip(group,key),mean=mean,ci95_half=half,seed_count=len(chunk)))
    return pd.DataFrame(records)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--out",type=Path,default=Path("figures"))
    p.add_argument("--ablation",type=Path)
    args=p.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    a=pd.read_csv(args.run/"accuracy.csv"); d=pd.read_csv(args.run/"timing.csv"); mem=pd.read_csv(args.run/"memory.csv")
    # Fail closed on incomplete runs, duplicated rows or semantically invalid counts.
    seeds=a.seed.nunique(); full=a.queries.iloc[0]==200000
    assert len(a)==seeds*70 and seeds==(8 if full else 2)
    assert not a.duplicated(["experiment","seed","n","m","k"]).any()
    assert (a.false_negatives==0).all() and (a.false_positives.between(0,a.queries)).all()
    assert (a.set_bits.between(0,a.m)).all()
    assert len(d)==(4 if full else 2)*2*4*4*(7 if full else 3)*3
    assert not d.duplicated(["seed","n","k","negative_fraction","repeat","method"]).any()
    assert (d.ns_per_query>0).all()
    exact=d[d.method!="bloom"]
    assert (exact.returned_positive==exact.expected_exact_positive).all()
    assert (mem.combined_live_bytes==mem.bloom_bytes+mem.set_live_bytes).all()
    a["fpr"]=a.false_positives/a.queries
    a["bits_per_key"]=a.m/a.n
    acc=summarize(a[a.experiment=="hash_sweep"],["bits_per_key","k"],"fpr")
    cap=a[a.experiment=="capacity"].copy(); cap["load"]=cap.n/(cap.m/10)
    capacity=summarize(cap,["load"],"fpr")
    med=d.groupby(["seed","n","k","negative_fraction","method"],as_index=False).ns_per_query.median()
    timing=summarize(med,["n","k","negative_fraction","method"],"ns_per_query")
    paired=med.pivot(index=["seed","n","k","negative_fraction"],columns="method",values="ns_per_query").reset_index()
    paired["speedup"]=paired["set"]/paired["filtered_set"]
    speedup=summarize(paired,["n","k","negative_fraction"],"speedup")
    for name,frame in [("accuracy_summary",acc),("capacity_summary",capacity),("timing_summary",timing),("speedup_summary",speedup)]:
        frame.to_csv(args.out/(name+".csv"),index=False)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,"axes.spines.right":False,"figure.dpi":150})
    colors=["#165D96","#D45D00","#217754","#7A3E8E"]
    fig,axes=plt.subplots(1,2,figsize=(10,3.7))
    for b,color in zip([4,8,10,16],colors):
        x=acc[acc.bits_per_key==b]; k=x.k.to_numpy()
        axes[0].errorbar(k,x["mean"]*100,yerr=x.ci95_half*100,fmt="o",ms=3,color=color,label=f"{b} bits/key")
        axes[0].plot(k,(1-np.exp(-k/b))**k*100,color=color,lw=1,alpha=.7)
    axes[0].set(xlabel="Hash count k",ylabel="False positives (%)",yscale="log",title="Measured points and theory lines")
    axes[0].legend(fontsize=8,ncol=2)
    cap_theory=(1-np.exp(-7*capacity.load/10))**7
    axes[1].errorbar(capacity.load,capacity["mean"]*100,yerr=capacity.ci95_half*100,fmt="o",color=colors[0],label="Measured")
    axes[1].plot(capacity.load,cap_theory*100,color=colors[1],label="Theory")
    axes[1].set(xlabel="Inserted keys / design capacity",ylabel="False positives (%)",title="Fixed m and k = 7")
    axes[1].legend(fontsize=8);fig.tight_layout();fig.savefig(args.out/"accuracy.png",bbox_inches="tight");plt.close(fig)
    sizes=sorted(d.n.unique())
    fig,axes=plt.subplots(1,2,figsize=(10,3.7),sharey=True)
    for ax,n in zip(axes,sizes):
        for k,color in zip([1,3,7,11],colors):
            x=speedup[(speedup.n==n)&(speedup.k==k)]
            ax.errorbar(x.negative_fraction*100,x["mean"],yerr=x.ci95_half,fmt="o-",ms=4,color=color,label=f"k = {k}")
        ax.axhline(1,color="black",ls="--",lw=1)
        ax.set(xlabel="Absent queries (%)",ylabel="Exact set time / filtered set time",title=f"n = {n:,}; 10 bits/key")
        ax.legend(fontsize=8,ncol=2)
    fig.tight_layout();fig.savefig(args.out/"speedup.png",bbox_inches="tight");plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.7))
    n=sizes[-1]
    for miss,color in zip([0.,1.],colors):
        x=timing[(timing.n==n)&(timing.method=="bloom")&(timing.negative_fraction==miss)]
        axes[0].errorbar(x.k,x["mean"],yerr=x.ci95_half,fmt="o-",color=color,label=f"{int(miss*100)}% absent")
    axes[0].set(xlabel="Hash count k",ylabel="Bloom query time (ns)",title=f"Early exit changes query cost; n = {n:,}")
    axes[0].legend(fontsize=8)
    m=mem[(mem.seed==1)&(mem.n==n)&(mem.k==7)].iloc[0]
    bars=axes[1].bar(["Bloom only\n(approximate)","Exact set","Bloom + set\n(exact)"],np.array([m.bloom_bytes,m.set_live_bytes,m.combined_live_bytes])/1024,color=[colors[0],colors[1],colors[2]])
    axes[1].bar_label(bars,fmt="%.0f",padding=3)
    axes[1].set(ylabel="KiB of structure storage",title="Requested storage, excluding allocator overhead")
    axes[1].set_ylim(0,m.combined_live_bytes/1024*1.2)
    fig.tight_layout();fig.savefig(args.out/"cost_memory.png",bbox_inches="tight");plt.close(fig)
    # A derived break-even model, not a simulated or measured database benchmark.
    backend=d[d.method=="filtered_set"].groupby(["seed","n","k","negative_fraction"],as_index=False).agg(backend_fraction=("backend_lookups",lambda x:x.iloc[0]/d.queries.iloc[0]))
    model=paired.merge(backend,on=["seed","n","k","negative_fraction"])
    model["extra_backend_ns_break_even"]=(model.filtered_set-model["set"])/(1-model.backend_fraction)
    model.loc[model.backend_fraction==1,"extra_backend_ns_break_even"]=np.inf
    model.to_csv(args.out/"break_even_model.csv",index=False)
    summary={"accuracy_rows":len(a),"timing_rows":len(d),"negative_accuracy_queries":int(a.queries.sum()),"positive_accuracy_checks":int(a.n.sum()),"false_negatives":int(a.false_negatives.sum()),"accuracy":acc.to_dict("records"),"capacity":capacity.to_dict("records"),"timing":timing.to_dict("records"),"speedup":speedup.to_dict("records"),"memory":mem[mem.seed==1].to_dict("records")}
    if args.ablation:
        ab=pd.read_csv(args.ablation)
        assert len(ab)==4*2*2*7*2
        assert not ab.duplicated(["seed","n","negative_fraction","repeat","method"]).any()
        assert (ab.mean_probes.between(1,7)).all()
        counts=ab.pivot(index=["seed","n","negative_fraction","repeat"],columns="method",values="returned_positive")
        assert (counts.early_exit==counts.full_scan).all()
        abmed=ab.groupby(["seed","n","negative_fraction","method"],as_index=False).agg(ns_per_query=("ns_per_query","median"),mean_probes=("mean_probes","first"))
        abst=summarize(abmed,["n","negative_fraction","method"],"ns_per_query")
        abst=abst.merge(abmed.groupby(["n","negative_fraction","method"],as_index=False).mean_probes.mean(),on=["n","negative_fraction","method"])
        abst.to_csv(args.out/"ablation_summary.csv",index=False)
        summary["ablation"]=abst.to_dict("records")
        fig,axes=plt.subplots(1,2,figsize=(10,3.7))
        for ax,n in zip(axes,sizes):
            for j,method in enumerate(["early_exit","full_scan"]):
                x=abst[(abst.n==n)&(abst.method==method)]
                bars=ax.bar(np.arange(2)+(j-.5)*.35,x["mean"],width=.35,yerr=x.ci95_half,color=colors[j],label=method.replace('_',' '),capsize=3)
                ax.bar_label(bars,labels=[f"{v:.1f}" for v in x["mean"]],padding=4,fontsize=9)
            ax.set(xticks=[0,1],xticklabels=["All present","All absent"],ylabel="Query time (ns)",title=f"Follow-up ablation; n = {n:,}, k = 7",ylim=(0,60))
            ax.legend(fontsize=8)
        fig.tight_layout();fig.savefig(args.out/"early_exit.png",bbox_inches="tight");plt.close(fig)
    (args.out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(f"Validated {len(a)} accuracy and {len(d)} main timing rows; regenerated main figures/tables and optional ablation.")
    print("At 10 bits/key:")
    print(acc[acc.bits_per_key==10].to_string(index=False))
    print("Exact pipeline speedups at k=7:")
    print(speedup[speedup.k==7].to_string(index=False))
    print("Capacity:",capacity.to_string(index=False))

if __name__=="__main__":main()
