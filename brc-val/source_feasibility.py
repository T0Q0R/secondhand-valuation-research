"""Train-only additive price envelopes and full-bundle BRC feasibility screen."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
from run_all import load_source
from savval import ACTIONS, FEATURES, price_features


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')


def fit_schema(frame):
    schema, offset = [], 0
    for name in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[name]):
            values = pd.to_numeric(frame[name], errors='coerce').to_numpy(float)
            finite = values[np.isfinite(values)]
            lower = float(finite.min()) if len(finite) else 0.
            upper = float(finite.max()) if len(finite) else 1.
            median = float(np.median(finite)) if len(finite) else .5
            entry = {'name': name, 'kind': 'numeric', 'lower': lower, 'upper': upper,
                     'median': median, 'columns': [offset, offset+1]}
            offset += 2
        else:
            cats = sorted(set(frame[name].fillna('<MISSING>').astype(str)) | {'<MISSING>'})
            entry = {'name': name, 'kind': 'categorical', 'categories': cats,
                     'columns': list(range(offset, offset+len(cats)))}
            offset += len(cats)
        schema.append(entry)
    return schema


def encode(frame, schema):
    columns = []
    for entry in schema:
        if entry['kind'] == 'numeric':
            raw = pd.to_numeric(frame[entry['name']], errors='coerce').to_numpy(float)
            missing = ~np.isfinite(raw)
            filled = np.where(missing, entry['median'], raw)
            span = entry['upper']-entry['lower']
            value = np.clip((filled-entry['lower'])/span, 0, 1) if span else np.zeros(len(frame))
            columns.extend([value[:, None], missing.astype(float)[:, None]])
        else:
            values = frame[entry['name']].fillna('<MISSING>').astype(str).to_numpy()
            columns.append((values[:, None] == np.array(entry['categories'])[None, :]).astype(float))
    return np.concatenate(columns, axis=1)


def optional_extrema(schema, coefficients):
    extremes = []
    for entry in schema:
        if entry['name'] not in ACTIONS:
            continue
        indices = entry['columns']
        local = coefficients[indices]
        if entry['kind'] == 'numeric':
            span = entry['upper']-entry['lower']
            imputed = np.clip((entry['median']-entry['lower'])/span, 0, 1) if span else 0.
            # Constant features map every observed value to zero.
            candidates = np.array([[0., 0.], [1. if span else 0., 0.], [imputed, 1.]])
        else:
            candidates = np.vstack([np.eye(len(indices)), np.zeros((1, len(indices)))])
        contributions = candidates @ local
        low, high = int(np.argmin(contributions)), int(np.argmax(contributions))
        extremes.append({'name': entry['name'], 'columns': indices,
                         'lower_contribution': float(contributions[low]),
                         'upper_contribution': float(contributions[high]),
                         'lower_encoding': candidates[low].tolist(),
                         'upper_encoding': candidates[high].tolist()})
    if set(e['name'] for e in extremes) != set(ACTIONS):
        raise ValueError('All four optional groups required')
    return extremes


def screen(name, config, folder):
    estimator, head, evaluation, provenance = load_source(name, config)
    train = pd.concat([estimator, head], ignore_index=True)
    public_train = price_features(train, FEATURES[name])
    public_evaluation = price_features(evaluation, FEATURES[name])
    schema = fit_schema(public_train)
    fit_x, eval_x = encode(public_train, schema), encode(public_evaluation, schema)
    target = np.expm1(train.target_log.to_numpy(float))
    cap = float(target.max())
    if not np.isfinite(target).all() or cap <= 0:
        raise ValueError('Require positive finite asking-price cap')
    model = Ridge(alpha=10., solver='lsqr', tol=1e-8)
    model.fit(fit_x, target)
    coefficients = model.coef_
    extremes = optional_extrema(schema, coefficients)
    raw = model.predict(eval_x)
    base = raw.copy()
    low_x, high_x = eval_x.copy(), eval_x.copy()
    for entry in extremes:
        indices = entry['columns']
        base -= eval_x[:, indices] @ coefficients[indices]
        low_x[:, indices] = entry['lower_encoding']
        high_x[:, indices] = entry['upper_encoding']
    raw_lower = base + sum(e['lower_contribution'] for e in extremes)
    raw_upper = base + sum(e['upper_contribution'] for e in extremes)
    tolerance = 1e-7*cap
    assert np.max(np.abs(model.predict(low_x)-raw_lower)) <= tolerance
    assert np.max(np.abs(model.predict(high_x)-raw_upper)) <= tolerance
    lower, upper = np.clip(raw_lower, 0, cap), np.clip(raw_upper, 0, cap)
    prices = np.clip(raw, 0, cap)
    assert ((lower-tolerance <= prices) & (prices <= upper+tolerance)).all()
    anchor = (lower+upper)/2
    floor = np.zeros(len(evaluation))
    nonzero = upper > lower
    floor[nonzero] = np.maximum((anchor[nonzero]-lower[nonzero])/anchor[nonzero],
        (upper[nonzero]-anchor[nonzero])/(cap-anchor[nonzero]))
    necessary = (upper-lower)/cap
    outcomes = pd.DataFrame({'listing_id': evaluation.listing_id,
        'batch': np.arange(len(evaluation))//100, 'model_price': prices,
        'all_missing_lower': lower, 'all_missing_upper': upper,
        'midpoint_reserve_floor': floor, 'necessary_two_branch_floor': necessary,
        'natural_missing_fields': public_evaluation[list(ACTIONS)].isna().sum(axis=1)})
    summaries = []
    for batch, rows in outcomes.groupby('batch'):
        n = len(rows)
        for rho in (0., .01, .05, .1, .2, .3):
            fields = int(np.floor(rho*n))
            bundles = fields//4
            reserve = float(rows.midpoint_reserve_floor.sum())
            needed = float(rows.necessary_two_branch_floor.sum())
            summaries.append({'dataset': name, 'batch': int(batch), 'listings': n,
                'field_allowance': rho, 'field_units': fields, 'bundle_units': bundles,
                'midpoint_reserve_floor_sum': reserve, 'necessary_two_branch_floor_sum': needed,
                'midpoint_feasible': reserve <= bundles, 'necessary_condition_satisfied': needed <= bundles})
    folder.mkdir()
    write(folder/'schema.json', schema)
    write(folder/'optional_extrema.json', extremes)
    write(folder/'provenance.json', provenance)
    joblib.dump(model, folder/'model.joblib')
    train[['listing_id']].to_csv(folder/'training_ids.csv', index=False)
    outcomes.to_csv(folder/'envelopes.csv', index=False)
    pd.DataFrame(summaries).to_csv(folder/'batch_feasibility.csv', index=False)
    truth = np.expm1(evaluation.target_log.to_numpy(float))
    gate = {'dataset': name, 'scope': 'One deterministic additive screening model; no final performance claim',
        'train_rows': len(train), 'evaluation_rows': len(evaluation), 'price_cap': cap,
        'honest_model_MAE': float(np.abs(prices-truth).mean()),
        'natural_missing_fraction': float((outcomes.natural_missing_fields>0).mean()),
        'primary_all10_midpoint_batches_feasible': all(r['midpoint_feasible'] for r in summaries if r['field_allowance']==.1),
        'primary_midpoint_feasible_batches': sum(r['midpoint_feasible'] for r in summaries if r['field_allowance']==.1),
        'primary_necessary_feasible_batches': sum(r['necessary_condition_satisfied'] for r in summaries if r['field_allowance']==.1),
        'machine_arithmetic_scope': 'Analytic additive bounds with extrema witnesses; numerical1e-7*M checks, not formal directed-rounding certification'}
    write(folder/'gate.json', gate)
    write(folder/'completion.json', {'status': 'completed_source_feasibility_screen',
        'source': name, 'files': {p.name: sha(p) for p in folder.iterdir() if p.is_file()}})
    return gate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError('Fresh source-feasibility generation required')
    manifest = json.loads((args.parent/'run_manifest.json').read_text())
    config = manifest['config']
    output.mkdir(parents=True)
    write(output/'manifest.json', {'status': 'exploratory_source_screen', 'config': config,
        'parent_manifest_sha256': sha(args.parent/'run_manifest.json'),
        'source_sha256': sha(__file__), 'protocol_sha256': sha(ROOT/'plan/brc-source-feasibility-v1.md'),
        'model': 'currency ridge alpha10 LSQR; train-only bounded encoding', 'bundle_cost_fields': 4})
    gates = []
    with threadpool_limits(limits=1):
        for name in ('synthetic', 'jucars', 'mucars'):
            gates.append(screen(name, config, output/name))
            print('SCREENED BRC '+name, flush=True)
    write(output/'completion.json', {'status': 'completed_source_feasibility_screen',
        'sources': 3, 'model_fits': 3, 'batch_capacity_cells': 180,
        'gates': gates, 'manifest_sha256': sha(output/'manifest.json'),
        'scope': 'Budget feasibility and additive envelope witnesses only; no mechanism-performance or novelty validation'})
    print(json.dumps(gates, indent=2), flush=True)


if __name__ == '__main__':
    main()
