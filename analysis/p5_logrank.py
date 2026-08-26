"""Nonparametric npm-vs-go log-rank (the primary contrast per draft) + publisher-block
permutation variant (cluster-aware, per review D3). Reads the same rows as the survival script."""
import json, os, datetime, numpy as np
from collections import defaultdict
G2=os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","gate2")
ORIGIN={"go":datetime.date(2026,6,24),"npm":datetime.date(2026,6,25)}
TODAY=datetime.date.today()
def rows(eco):
    hyd={json.loads(l)["repo"]:json.loads(l) for l in open(os.path.join(G2,f"hydrated_{eco}.jsonl")) if not json.loads(l).get("missing")}
    samp={m["repo"]:m for m in json.load(open(os.path.join(G2,f"sample_{eco}.json")))["members"]}
    ev={}
    for l in open(os.path.join(G2,f"events_{eco}.jsonl")):
        d=json.loads(l)
        if d.get("first_capable_commit"): ev[d["repo"]]=datetime.date.fromisoformat(d["first_capable_commit"]["date"])
    out=[]
    for r,m in samp.items():
        h=hyd.get(r)
        if not h: continue
        st=max(ORIGIN[eco],datetime.date.fromisoformat(h["created"][:10]))
        e=ev.get(r); end=e or TODAY
        out.append((max((end-st).days,0)+0.5, 1 if e else 0, r.split("/")[0], eco))
    return out
data=rows("go")+rows("npm")
def logrank(data):
    times=sorted(set(t for t,e,_,_ in data if e==1))
    O_npm=E_npm=V=0.0
    for tt in times:
        atrisk=[d for d in data if d[0]>=tt]
        n=len(atrisk); n_npm=sum(1 for d in atrisk if d[3]=="npm")
        deaths=[d for d in data if d[0]==tt and d[1]==1]; dd=len(deaths)
        d_npm=sum(1 for d in deaths if d[3]=="npm")
        if n>1:
            O_npm+=d_npm; E_npm+=dd*n_npm/n
            V+=dd*(n_npm/n)*(1-n_npm/n)*(n-dd)/(n-1)
    chi=(O_npm-E_npm)**2/V if V>0 else 0
    return chi,O_npm,E_npm
chi,O,E=logrank(data)
from math import erfc,sqrt
p=erfc(sqrt(chi/2))
# publisher-block permutation (shuffle ecosystem label by publisher block)
pubs=defaultdict(list)
for d in data: pubs[d[2]].append(d)
rng=np.random.default_rng(71); ge=[]
blocks=list(pubs.values()); labels=[b[0][3] for b in blocks]
for _ in range(2000):
    perm=rng.permutation(labels)
    relab=[]
    for b,lab in zip(blocks,perm):
        for (t,e,pub,_eco) in b: relab.append((t,e,pub,lab))
    ge.append(logrank(relab)[0])
perm_p=(1+sum(1 for c in ge if c>=chi))/(len(ge)+1)
res={"preliminary":True,"generated":TODAY.isoformat(),"test":"npm vs go log-rank",
     "chi2":round(chi,2),"O_npm":round(O,2),"E_npm":round(E,2),"asymptotic_p":f"{p:.2e}",
     "publisher_block_permutation_p":round(perm_p,4),"n_perm":len(ge)}
json.dump(res,open("p5_logrank_results.json","w"),indent=2)
print(res)
