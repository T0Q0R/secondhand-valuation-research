"""Re-derive first-divergence and same-machine checks from private return ZIPs.

No fitting or pickle loading; publishes aggregate numeric diagnostics only.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
from compare_onepass_returns import load_return
from run_onepass_diagnostic import compare


def numeric_payload(path):
    with zipfile.ZipFile(path) as outer:
        with zipfile.ZipFile(io.BytesIO(outer.read('threads-2-repeat-1.zip'))) as inner:
            payload = inner.read('arrays.npz')
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 128 * 1024**2:
            raise ValueError('Unexpected expanded diagnostic arrays')
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        return {name: archive[name] for name in archive.files}


def identity(event):
    return {key: event[key] for key in ['round', 'step', 'event']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--external', type=Path, required=True)
    parser.add_argument('--local', type=Path, required=True)
    parser.add_argument('--previous-external-fingerprints', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    es, external = load_return(args.external)
    ls, local = load_return(args.local)
    with zipfile.ZipFile(args.previous_external_fingerprints) as archive:
        previous = json.loads(archive.read('diagnostic.json'))
    previous_models = {(m['method'], m['stage']): m for m in previous['models']}
    within = {}
    for label, runs in [('external', external), ('local', local)]:
        within[label] = {f'repeat_threads_{t}': compare(runs[f'threads-{t}-repeat-1.zip'], runs[f'threads-{t}-repeat-2.zip']) for t in [1, 2]}
        within[label]['one_vs_two_threads'] = compare(runs['threads-1-repeat-1.zip'], runs['threads-2-repeat-1.zip'])
    cross_machine = {}
    for name in sorted(external):
        e, l = external[name], local[name]
        for key in ['probe_sha256', 'frozen_training_sha256', 'threads', 'repeat']:
            if e[key] != l[key]:
                raise ValueError('Inconsistent diagnostic sources/settings')
        for stage in e['stages']:
            if stage['final_parameter_sha256'] != previous_models[(stage['method'], stage['stage'])]['residual_parameter_sha256']:
                raise ValueError('Replayed external model differs from previously returned saved parameters')
        cross_machine[name] = compare(e, l)
    e, l = external['threads-2-repeat-1.zip'], local['threads-2-repeat-1.zip']
    ea, la = numeric_payload(args.external), numeric_payload(args.local)
    stages = []
    for stage in e['stages']:
        pair = stage['method'], stage['stage']
        er = [r for r in e['records'] if (r['method'], r['stage']) == pair]
        lr = [r for r in l['records'] if (r['method'], r['stage']) == pair]
        if len(er) != len(lr):
            raise ValueError('Trace length mismatch')
        first = {}
        for x, y in zip(er, lr):
            for key in ['round', 'step', 'event']:
                if x[key] != y[key]:
                    raise ValueError('Trace ordering mismatch')
            comparisons = {
                'any_recorded_difference': x != y,
                'parameter_difference': x['parameters'] != y['parameters'],
                'gradient_difference': x.get('gradients') != y.get('gradients'),
                'prediction_difference': x.get('values', {}).get('predicted') != y.get('values', {}).get('predicted'),
                'selected_state_difference': x.get('values', {}).get('final_states') != y.get('values', {}).get('final_states'),
                'input_difference': any(x.get('values', {}).get(k) != y.get('values', {}).get(k) for k in ['idx', 'bx', 'bb', 'by']),
                'torch_rng_difference': x['torch_rng_sha256'] != y['torch_rng_sha256'],
            }
            for key, different in comparisons.items():
                if different and key not in first:
                    first[key] = identity(x)
        gradients = []
        prefix = '__'.join(pair) + '__round-0__step-0__after_backward__gradient__'
        first_external = next(x for x in er if x['round'] == 0 and x['step'] == 0 and x['event'] == 'after_backward')
        first_local = next(x for x in lr if x['round'] == 0 and x['step'] == 0 and x['event'] == 'after_backward')
        for key in first_external['gradients']:
            array_key = prefix + key
            x, y = ea[array_key], la[array_key]
            if x.dtype != y.dtype or x.shape != y.shape:
                raise ValueError('Gradient layout mismatch')
            for array, recorded in [(x, first_external['gradients'][key]), (y, first_local['gradients'][key])]:
                if hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest() != recorded['sha256']:
                    raise ValueError('Gradient array SHA mismatch')
            delta = np.abs(x.astype(np.float64) - y.astype(np.float64))
            gradients.append(dict(parameter=key, dtype=str(x.dtype), total_entries=int(x.size),
                changed_entries=int(np.count_nonzero(x != y)), maximum_absolute_difference=float(delta.max())))
        stages.append(dict(method=pair[0], stage=pair[1], first_observed_differences=first,
                           first_batch_unclipped_gradient_differences=gradients))
    result = dict(
        scope='Private archived one-pass data only; no fitting, no formal tolerance changes',
        recomputed_within_machine_comparisons=within,
        recomputed_cross_machine_comparisons=cross_machine,
        external_replays_match_previous_saved_parameters='32/32 independently compared parameter fingerprints',
        first_batch_gradient_maximum_absolute_difference=max(g['maximum_absolute_difference'] for s in stages for g in s['first_batch_unclipped_gradient_differences']),
        first_batch_gradient_minimum_nonzero_stage_maximum=min(max(g['maximum_absolute_difference'] for g in s['first_batch_unclipped_gradient_differences']) for s in stages),
        models_with_recorded_selected_state_divergence=sum('selected_state_difference' in s['first_observed_differences'] for s in stages),
        stages=stages,
        limitations=['First differing recorded event is not necessarily the first differing primitive operation: intermediate hidden activations were not captured.',
                     'The specific CPU, system math library or numerical kernel responsible is not causally isolated.',
                     'Later selected-state divergence follows earlier gradient divergence; no intervention here proves that branch changes cause the final effect.',
                     'Independent source execution and within-machine repeatability do not certify strict cross-machine metric reproduction.'])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['external_replays_match_previous_saved_parameters',
        'first_batch_gradient_maximum_absolute_difference', 'first_batch_gradient_minimum_nonzero_stage_maximum',
        'models_with_recorded_selected_state_divergence']}, indent=2))


if __name__ == '__main__':
    main()
