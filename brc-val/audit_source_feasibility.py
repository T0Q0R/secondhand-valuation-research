"""Independent additive-envelope/field-budget replay; no new model fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from run_all import load_source
from savval import ACTIONS, FEATURES, price_features


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Fresh independent audit required')
    complete = json.loads((args.run/'completion.json').read_text())
    assert complete['status']=='completed_source_feasibility_screen'
    assert complete['manifest_sha256']==sha(args.run/'manifest.json')
    manifest = json.loads((args.run/'manifest.json').read_text())
    assert manifest['source_sha256']==sha(Path(__file__).with_name('source_feasibility.py'))
    assert manifest['protocol_sha256']==sha(ROOT/'plan/brc-source-feasibility-v1.md')
    assert manifest['parent_manifest_sha256']==sha(args.parent/'run_manifest.json')
    config = manifest['config']
    rows_checked, cells_checked, extrema_checked = 0, 0, 0
    source_results = []
    with threadpool_limits(limits=1):
        for name in ('synthetic','jucars','mucars'):
            folder = args.run/name
            receipt = json.loads((folder/'completion.json').read_text())
            for filename, digest in receipt['files'].items():
                assert sha(folder/filename)==digest
            first, head, evaluation, provenance = load_source(name, config)
            train = pd.concat([first,head],ignore_index=True)
            recorded_provenance=json.loads((folder/'provenance.json').read_text())
            # Relocation may change absolute input paths; their exact bytes
            # and every other source/split feature remain checksum-bound.
            path_keys={'source_train','source_validation'}
            assert {k:v for k,v in provenance.items() if k not in path_keys}=={
                k:v for k,v in recorded_provenance.items() if k not in path_keys}
            assert pd.read_csv(folder/'training_ids.csv').listing_id.tolist()==train.listing_id.tolist()
            frame = price_features(evaluation,FEATURES[name])
            schema = json.loads((folder/'schema.json').read_text())
            assert [e['name'] for e in schema]==FEATURES[name]
            model = joblib.load(folder/'model.joblib')
            coeff = model.coef_
            raw = np.full(len(frame),model.intercept_,float)
            base = np.full(len(frame),model.intercept_,float)
            lower_extra, upper_extra = 0., 0.
            saved_extrema = {e['name']:e for e in json.loads((folder/'optional_extrema.json').read_text())}
            for entry in schema:
                column = frame[entry['name']]
                w = coeff[entry['columns']]
                if entry['kind']=='numeric':
                    original = pd.to_numeric(column,errors='coerce').to_numpy(float)
                    unavailable = ~np.isfinite(original)
                    span = entry['upper']-entry['lower']
                    observed = np.where(unavailable,entry['median'],original)
                    z = np.maximum(0.,np.minimum(1.,(observed-entry['lower'])/span)) if span else np.zeros(len(frame))
                    contribution = w[0]*z+w[1]*unavailable
                    imputed = min(1.,max(0.,(entry['median']-entry['lower'])/span)) if span else 0.
                    candidate = [0.,float(w[0]) if span else 0.,float(w[0]*imputed+w[1])]
                else:
                    by_value = dict(zip(entry['categories'],map(float,w)))
                    contribution = column.fillna('<MISSING>').astype(str).map(by_value).fillna(0.).to_numpy(float)
                    candidate = [0.,*map(float,w)]
                raw += contribution
                if entry['name'] in ACTIONS:
                    lo, hi = min(candidate),max(candidate)
                    lower_extra += lo;upper_extra += hi;extrema_checked += 1
                    saved = saved_extrema[entry['name']]
                    assert abs(lo-saved['lower_contribution'])<1e-7
                    assert abs(hi-saved['upper_contribution'])<1e-7
                    assert abs(np.dot(w,saved['lower_encoding'])-lo)<1e-7
                    assert abs(np.dot(w,saved['upper_encoding'])-hi)<1e-7
                else:
                    base += contribution
            cap = float(np.expm1(train.target_log.to_numpy(float)).max())
            lo, hi = np.clip(base+lower_extra,0,cap),np.clip(base+upper_extra,0,cap)
            quote = np.clip(raw,0,cap)
            middle = (lo+hi)/2
            needed = np.zeros(len(frame));variable = hi>lo
            needed[variable] = np.maximum(1-lo[variable]/middle[variable],
                                          (hi[variable]-middle[variable])/(cap-middle[variable]))
            necessary = (hi-lo)/cap
            recorded = pd.read_csv(folder/'envelopes.csv')
            assert recorded.listing_id.tolist()==evaluation.listing_id.tolist()
            for key, actual in [('model_price',quote),('all_missing_lower',lo),('all_missing_upper',hi),
                                ('midpoint_reserve_floor',needed),('necessary_two_branch_floor',necessary)]:
                np.testing.assert_allclose(recorded[key],actual,rtol=1e-9,atol=1e-7*cap if 'floor' not in key else 1e-9)
            batches = pd.read_csv(folder/'batch_feasibility.csv')
            assert len(batches)==60
            expected_midpoint, expected_necessary = 0,0
            for row in batches.itertuples():
                selected = (np.arange(len(frame))//100)==row.batch
                n = int(selected.sum());budget = int(np.floor(row.field_allowance*n))//4
                floor = float(needed[selected].sum());minimum = float(necessary[selected].sum())
                assert row.listings==n and row.bundle_units==budget
                assert abs(row.midpoint_reserve_floor_sum-floor)<1e-8
                assert abs(row.necessary_two_branch_floor_sum-minimum)<1e-8
                assert row.midpoint_feasible==(floor<=budget)
                assert row.necessary_condition_satisfied==(minimum<=budget)
                if row.field_allowance==.1:
                    expected_midpoint += int(floor<=budget)
                    expected_necessary += int(minimum<=budget)
                cells_checked += 1
            gate = json.loads((folder/'gate.json').read_text())
            assert gate['primary_midpoint_feasible_batches']==expected_midpoint
            assert gate['primary_necessary_feasible_batches']==expected_necessary
            assert gate['primary_all10_midpoint_batches_feasible']==(expected_midpoint==10)
            assert abs(gate['honest_model_MAE']-np.abs(quote-np.expm1(evaluation.target_log)).mean())<1e-7*cap
            assert any(g==gate for g in complete['gates'])
            source_results.append(gate);rows_checked += len(frame)
    assert rows_checked==3000 and cells_checked==180 and extrema_checked==12
    args.output.mkdir(parents=True)
    (args.output/'auditor_snapshot.py').write_bytes(Path(__file__).read_bytes())
    result = {'status':'completed_independent_feasibility_audit','model_fits':0,
        'record_envelopes':rows_checked,'batch_capacity_cells':cells_checked,
        'independent_optional_group_extrema':extrema_checked,'gates':source_results,
        'run_completion_sha256':sha(args.run/'completion.json'),
        'run_manifest_sha256':sha(args.run/'manifest.json'),'auditor_sha256':sha(__file__),
        'imported_core_hashes':{n:sha(ROOT/'experiments'/n) for n in ('run_all.py','savval.py')},
        'scope':'Independent model-contribution/extrema/witness/budget/gate replay; floating tolerance only; no new fitting or physical verification proof'}
    (args.output/'completion.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
