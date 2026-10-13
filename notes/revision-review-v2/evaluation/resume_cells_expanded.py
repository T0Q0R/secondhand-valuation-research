"""Schedule remaining independent cells separately, reusing the frozen worker.

The frozen worker's per-fit receipt is routed to a unique cell-receipt folder
to avoid collisions. Its model prediction, scoring, prefix validation and
batch evaluation code remain unchanged. Complete cells retain exact summaries.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import argparse, fcntl, json, time
import pandas as pd
import resume_expanded as guard

producer = guard.producer
BASE = producer.OUT

class ReceiptRoute:
    def __init__(self, tag): self.tag = tag
    def __truediv__(self, component):
        if component == 'worker-receipts':
            return BASE / 'cell-worker-receipts' / self.tag
        return BASE / component

def cell_worker(task):
    source, seed, fit, cell = task
    producer.OUT = ReceiptRoute('__'.join(cell))
    try:
        rows = producer.worker((source, seed, fit, [cell]))
        assert len(rows) == 1
        assert rows[0]['initial_objective'] == cell[0]
        assert rows[0]['score'] == cell[1] and rows[0]['feedback'] == cell[2]
        assert rows[0]['allocation'] == cell[3]
        return rows[0]
    finally: producer.OUT = BASE

def cached_row(task):
    source, seed, fit, cell = task
    folder = BASE / source / f'seed-{seed}' / Path(*cell)
    cp = folder / 'completion.json'
    if not cp.exists(): return None
    done = json.loads(cp.read_text())
    assert producer.sha(folder/'summary.json') == done['summary_sha256']
    assert producer.sha(folder/'inputs.json') == done['inputs_sha256']
    for name, digest in done['batch_receipts'].items():
        assert producer.sha(folder/name) == digest
    summary = json.loads((folder/'summary.json').read_text())
    return {'dataset':source, 'seed':seed, 'fit_id':fit,
            'initial_objective':cell[0], 'score':cell[1], 'feedback':cell[2], **summary}

def main(workers):
    lock = (BASE/'execution.lock').open('r+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest = json.loads((producer.RUN/'manifest.json').read_text())
    binding = json.loads((BASE/'manifest.json').read_text())
    assert producer.sha(producer.RUN/'manifest.json') == binding['frozen_manifest_sha256']
    assert producer.sha(Path(producer.__file__)) == binding['script_sha256']
    for name, digest in manifest['source_hashes'].items():
        assert producer.sha(producer.ROOT/'experiments'/name) == digest
    tasks = []
    for source in ('jucars','mucars'):
        for seed in manifest['config']['seeds']:
            mapping = json.loads((producer.RUN/source/f'seed-{seed}/fit/cell_mapping.json').read_text())
            tasks.extend((source, seed, row['fit_id'], row['cell']) for row in mapping)
    assert len(tasks) == 480
    rows = []; pending = []
    for task in tasks:
        row = cached_row(task)
        if row is None: pending.append(task)
        else: rows.append(row)
    started = time.time()
    def checkpoint():
        pd.DataFrame(rows).to_csv(BASE/'partial_summary.csv',index=False)
        producer.write(BASE/'progress.json',{'completed_cells':len(rows),'expected_cells':480,
                      'seconds_this_process':time.time()-started,'scheduling':'independent_remaining_cells'})
        print(f'CELL SCHEDULE {len(rows)}/480',flush=True)
    checkpoint()
    print('PENDING INDEPENDENT CELLS '+str(len(pending)),flush=True)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(cell_worker,task) for task in pending]):
            rows.append(future.result());checkpoint()
    assert len(rows) == 480
    assert len({(r['dataset'],r['seed'],r['initial_objective'],r['score'],r['feedback'],r['allocation']) for r in rows}) == 480
    # Assemble the original per-fit provenance records only after all its
    # separately evaluated cells exist; preserve already-complete records.
    grouped = {}
    for row in rows: grouped.setdefault((row['dataset'],row['seed'],row['fit_id']),[]).append(row)
    assert len(grouped) == 280
    for (source,seed,fit), summaries in grouped.items():
        path = BASE/'worker-receipts'/source/f'seed-{seed}'/(fit+'.json')
        if path.exists():
            previous = json.loads(path.read_text())
            assert len(previous['summaries']) == len(summaries)
            continue
        wanted = json.loads((producer.RUN/source/f'seed-{seed}/fit/completion.json').read_text())['deployment_model_hashes'][fit]
        producer.write(path,{'status':'completed','script_sha256':producer.sha(Path(producer.__file__)),
                            'model_sha256':wanted,'summaries':summaries})
    pd.DataFrame(rows).to_csv(BASE/'summary.csv',index=False)
    producer.write(BASE/'completion.json',{'status':'completed_pending_corroborating_audit','cells':480,
          'summary_sha256':producer.sha(BASE/'summary.csv'),'manifest_sha256':producer.sha(BASE/'manifest.json'),
          'operational_scheduler_sha256':producer.sha(Path(__file__)),'scheduling':'independent_remaining_cells'})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=8);a=p.parse_args();main(a.workers)
