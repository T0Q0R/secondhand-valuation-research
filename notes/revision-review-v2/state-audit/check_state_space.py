"""Independent bit-mask oracle; production StateSpace is only the test target."""
from pathlib import Path
import hashlib, json, sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments'))
from savval import StateSpace  # system under test, never oracle logic

FIELDS = ('mileage_km', 'transmission', 'fuel_type', 'feat_body_condition')
OUT = Path(__file__).resolve().parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def bits(row):
    return sum((1 << i) for i, value in enumerate(row) if bool(value))

def reference(frame, masks):
    """No combinations, StateSpace, load_source, query_next, or replay calls."""
    natural = [bits(row) for row in frame[list(FIELDS)].isna().to_numpy()]
    records, legal, public = [], [], []
    for rowno, absent in enumerate(natural):
        for mask in masks:
            record = frame.iloc[rowno].to_dict()
            for field in range(4):
                if mask & (1 << field): record[FIELDS[field]] = np.nan
            records.append(record)
            legal.append((mask & absent) == 0)
            public.append([bool((mask | absent) & (1 << f)) for f in range(4)])
    return pd.DataFrame(records, columns=frame.columns), np.array(legal).reshape(len(frame), -1), np.array(public).reshape(len(frame), -1, 4)

def check(frame, space, maximum, mutation=None):
    observed = [bits(row) for row in space.masks]
    expected = {m for m in range(16) if m.bit_count() <= maximum}
    assert len(observed) == len(set(observed)) and set(observed) == expected
    lookup = {m: s for s, m in enumerate(observed)}
    transitions = np.array([[lookup[m & ~(1 << f)] if m & (1 << f) else lookup[m] for f in range(4)] for m in observed])
    actual_next = space.query_next.copy()
    if mutation == 'wrong_recovery_transition': actual_next[-1, 0] = (actual_next[-1, 0] + 1) % len(observed)
    assert np.array_equal(actual_next, transitions)
    flat, valid = space.materialize(frame)
    missing = space.reported_missing(frame)
    independent, wanted_valid, wanted_missing = reference(frame, observed)
    if mutation == 'natural_missing_treated_as_concealable': valid[-1, -1] = True
    if mutation == 'natural_and_strategic_missing_distinguished': missing[-1, 0, 0] = False
    if mutation == 'wrong_materialized_field': flat.loc[0, FIELDS[0]] = -12345.
    assert np.array_equal(valid, wanted_valid)
    assert np.array_equal(missing, wanted_missing)
    pd.testing.assert_frame_equal(flat.reset_index(drop=True), independent, check_dtype=False)
    legal_transitions = successful = failed_public = 0
    for i in range(len(frame)):
        natural = bits(frame.iloc[i][list(FIELDS)].isna())
        for s, mask in enumerate(observed):
            if mask & natural: continue
            for f, name in enumerate(FIELDS):
                after = mask & ~(1 << f)
                target = lookup[after]
                assert valid[i, target]
                if (natural | mask) & (1 << f):
                    legal_transitions += 1
                    if natural & (1 << f): failed_public += 1
                    else: successful += 1
                left = independent.iloc[i * len(observed) + target][name]
                right = frame.iloc[i][name] if mask & (1 << f) else independent.iloc[i * len(observed) + s][name]
                assert (pd.isna(left) and pd.isna(right)) or left == right
    return {'records': len(frame), 'states': len(observed), 'legal_reports': int(valid.sum()), 'all_field_transitions': int(valid.sum()) * 4,
            'publicly_eligible_transitions': legal_transitions, 'successful_recovery_transitions': successful, 'failed_public_queries': failed_public}

fixtures = []
for natural in range(16):
    row = {'mileage_km': 1001., 'transmission': 'automatic', 'fuel_type': 'petrol', 'feat_body_condition': 'used', 'marker': str(natural)}
    for f in range(4):
        if natural & (1 << f): row[FIELDS[f]] = np.nan
    fixtures.append(row)
frame = pd.DataFrame(fixtures)
results = {str(k): check(frame, StateSpace.build(k), k) for k in range(5)}
rejected = []
for mutation in ['wrong_recovery_transition', 'natural_missing_treated_as_concealable', 'natural_and_strategic_missing_distinguished', 'wrong_materialized_field']:
    try: check(frame, StateSpace.build(2), 2, mutation)
    except AssertionError: rejected.append(mutation)
    else: raise AssertionError('Mutation accepted: ' + mutation)
sources = {}
for name in ('jucars', 'mucars'):
    path = ROOT.parent / 'experiments/data/processed' / (name + '_bvival_v1') / 'splits/validation.csv'
    data = pd.read_csv(path, usecols=list(FIELDS))
    # Exhaustive masks fixture covers every pattern; real records additionally
    # check materialization values without sharing the production data loader.
    sources[name] = {'input_sha256': digest(path), **check(data, StateSpace.build(2), 2)}
receipt = {'status': 'completed', 'fixture_natural_patterns': 16, 'maximum_hidden_values_checked': list(range(5)),
           'fixture_counts': results, 'full_validation_records': sources, 'mutations_rejected': rejected,
           'production_savval_sha256': digest(ROOT / 'experiments/savval.py'), 'checker_sha256': digest(Path(__file__)),
           'oracle_imports_shared_state_or_query_logic': False,
           'scope': 'state masks, validity, materialized records, public missingness and recovery/failure transitions; not independent model/scorer/training reimplementation',
           'remaining_shared_primitives': ['model.predict', 'head.score', 'training libraries', 'cohort construction in the historical factorial audit']}
(OUT / 'completion.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
