"""Aggregate existing construction receipts and feature availability; no test labels.
Historical exclusion flags overlap. Do not sum them or imply vehicle identity.
"""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments'))
from run_all import load_source
from savval import ACTIONS,StateSpace
OUT=Path(__file__).parent/'data-construction'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=True)
    cfg=json.loads((ROOT/'outputs/rpl-ten-seed-v2/manifest.json').read_text())['config']
    flow=[];availability=[];legal=[];bindings=[]
    for source in ['synthetic','jucars','mucars']:
        e,g,ev,_=load_source(source,cfg);train=pd.concat([e,g],ignore_index=True)
        frames={'used_training':train,'used_evaluation':ev}
        if source!='synthetic':
            directory=ROOT.parent/'experiments/data/processed'/f'{source}_bvival_v1'
            ap=directory/f'{source}_bvival_audit.json';audit=json.loads(ap.read_text())
            duplicates=audit.get('duplicate_nonprice_fingerprints_removed',audit.get('conservative_non_target_duplicate_rows_removed'))
            retained=audit.get('retained_used_labeled_listing_count',audit.get('retained_used_listing_count'))
            counts=audit['split_counts'];assert sum(counts.values())==retained
            hashes=audit.get('output_hashes',audit.get('outputs'))
            for rel,h in hashes.items():
                fp=directory/rel;assert sha(fp)==h
                bindings.append(dict(path=str(fp.relative_to(ROOT.parent)),sha256=h,
                    label_access='bytes hashed only; sealed labels never parsed' if 'sealed_labels' in rel else 'feature aggregates / original split binding'))
            manifest=directory/(f'{source}_bvival_manifest_features_only.csv' if source=='mucars' else f'{source}_bvival_manifest.csv')
            frames['all_retained']=pd.read_csv(manifest,usecols=['listing_id',*ACTIONS])
            assert len(frames['all_retained'])==retained
            for split in ['train','validation']:
                frames['full_'+split]=pd.read_csv(directory/'splits'/f'{split}.csv',usecols=['listing_id',*ACTIONS])
                assert len(frames['full_'+split])==counts[split]
            flow.append(dict(source=source,raw=audit['raw_row_count'],joint_filter_removed=audit['raw_row_count']-retained-duplicates,
                 passed_joint_filter=retained+duplicates,duplicates_removed=duplicates,retained=retained,
                 **counts,used_training=len(train),used_evaluation=len(ev)))
            bindings.append(dict(path=str(ap.relative_to(ROOT.parent)),sha256=sha(ap),label_access='historical aggregate receipt'))
        else:
            flow.append(dict(source=source,raw=cfg['synthetic_train']+cfg['synthetic_evaluation'],
                 joint_filter_removed=0,passed_joint_filter=cfg['synthetic_train']+cfg['synthetic_evaluation'],
                 duplicates_removed=0,retained=cfg['synthetic_train']+cfg['synthetic_evaluation'],
                 train=cfg['synthetic_train'],validation=cfg['synthetic_evaluation'],calibration=0,test=0,
                 used_training=len(train),used_evaluation=len(ev)))
        for name,frame in frames.items():
            missing=frame.loc[:,list(ACTIONS)].isna();m=(~missing).sum(1)
            for field in ACTIONS:
                availability.append(dict(source=source,cohort=name,field=field,n=len(frame),
                    missing=int(missing[field].sum()),missing_rate=float(missing[field].mean())))
            reports=1+m+m*(m-1)//2
            _,valid=StateSpace.build(2).materialize(frame.loc[:,list(ACTIONS)])
            assert np.array_equal(reports.to_numpy(),valid.sum(1))
            for number,count in reports.value_counts().sort_index().items():
                legal.append(dict(source=source,cohort=name,legal_reports=int(number),count=int(count),fraction=float(count/len(frame))))
    pd.DataFrame(flow).to_csv(OUT/'sample-flow.csv',index=False)
    pd.DataFrame(availability).to_csv(OUT/'field-missingness.csv',index=False)
    pd.DataFrame(legal).to_csv(OUT/'legal-report-distribution.csv',index=False)
    sources=['experiments/run_all.py','experiments/savval.py']
    external=['build_jucars_bvival_manifest.py','build_mucars_bvival_manifest.py']
    code={p:sha(ROOT/p) for p in sources}
    code.update({'../experiments/'+p:sha(ROOT.parent/'experiments'/p) for p in external})
    (OUT/'verification.json').write_text(json.dumps(dict(status='aggregate_receipts_and_split_hashes_verified',
       bindings=bindings,code_sha256=code,sealed_test_labels_parsed=False,
       note='joint exclusions obtained from bound historical final+duplicate counts; exclusion flags overlap; no new filtering or modeling'),indent=2)+'\n')
    print(pd.DataFrame(flow).to_string(index=False))

if __name__=='__main__':main()
