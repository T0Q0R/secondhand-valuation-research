"""Independent selection audit from saved scalar OOF scores; no runner imports."""
from pathlib import Path
import hashlib,json,csv
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/'outputs/review-gap-controls-v2'
OUT=Path(__file__).parent/'gap'
seeds=[13,42,2026,101,211,307,401,503,601,701]
rows=[]
for source in ['synthetic','jucars','mucars']:
    for seed in seeds:
        p=RUN/source/f'seed-{seed}'/'training-selection.json'
        j=json.loads(p.read_text()); items=j['candidates']
        assert len(items)==7 and len({r['method'] for r in items})==7
        common=[r for r in items if r['path_weight']==0 and r['beta']==.5]
        assert len(common)==1
        cap=common[0]['oof_honest_mae']*1.05
        for family,axis,grid in [('rpl','path_weight',[0,.1,.5,1]),('gap','beta',[.5,1,2,4])]:
            eligible=[r for r in items if (r['beta']==.5 if family=='rpl' else r['path_weight']==0)]
            assert len(eligible)==4 and sorted(r[axis] for r in eligible)==grid
            recorded=next(r for r in j['choices'] if r['family']==family)
            qualified=[i for i,r in enumerate(eligible) if r['oof_honest_mae']<=cap]
            available=qualified if qualified else list(range(4))
            ordered=sorted(available,key=lambda i: ((eligible[i]['oof_max_gain'],eligible[i]['oof_honest_mae'],i) if qualified else (eligible[i]['oof_honest_mae'],eligible[i]['oof_max_gain'],i)))
            expected=eligible[ordered[0]]['method']
            assert expected==recorded['selected_method']
            assert recorded['constraint_met']==bool(qualified)
            assert recorded['selection_uses_evaluation'] is False
            assert recorded['honest_mae_limit']==cap
            rows.append(dict(source=source,seed=seed,family=family,selected_method=expected,feasible_count=len(qualified),selection_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
with (OUT/'independent-selection-audit.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
receipt=dict(status='passed',pairs=30,family_choices_checked=60,scope='independent scalar-score choice and constraint audit; no runner imports, no OOF prediction regeneration',source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),constraint_fallbacks=sum(r['feasible_count']==0 for r in rows))
(OUT/'independent-selection-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
