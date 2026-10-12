"""Shard the frozen auditor loop; publish only its hash-bound batch checkpoints.

The formal auditor retains full coverage and creates the authoritative receipt.
Worker completion receipts are partial and never substituted for it.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
worker, count = map(int, sys.argv[1:3])
run = ROOT / 'outputs/matched-factorial-ten-seeds-v1'
formal = ROOT / 'outputs/matched-factorial-ten-seeds-v1-pipeline/outcome-audit'
out = ROOT / 'outputs/parallel-outcome-audit' / f'worker-{worker}'
source = ROOT / 'experiments/audit_matched_factorial_results.py'
raw = source.read_bytes()
source_hash = hashlib.sha256(raw).hexdigest()
inputs = json.loads((formal / 'inputs.json').read_text())
assert inputs['checker_hashes'][str(source)] == source_hash

class Shard(ast.NodeTransformer):
    loops = checkpoints = 0
    def visit_For(self, node):
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and node.target.id == 'cp' and isinstance(node.iter, ast.Name) and node.iter.id == 'files':
            node.iter = ast.Call(func=ast.Name(id='select_files', ctx=ast.Load()), args=[node.iter], keywords=[])
            self.loops += 1
        return node
    def visit_Assign(self, node):
        self.generic_visit(node)
        if any(isinstance(t, ast.Name) and t.id == 'checkpoint' for t in node.targets):
            class Destination(ast.NodeTransformer):
                def visit_Name(self, n):
                    return ast.copy_location(ast.Name(id='shared_out', ctx=n.ctx), n) if n.id == 'out' else n
            node.value = Destination().visit(node.value)
            self.checkpoints += 1
        return node

# Keep the main auditor's first in-flight source/seed exclusively with it.
def select_files(files):
    pairs = sorted({str(p.relative_to(run).parent).split('/evaluation/')[0] for p in files})
    pairs = [p for p in pairs if p != 'jucars/seed-101']
    selected = set(pairs[worker::count])
    return [p for p in files if str(p.relative_to(run).parent).split('/evaluation/')[0] in selected]

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)

transform = Shard()
tree = transform.visit(ast.parse(raw, filename=str(source)))
assert transform.loops == transform.checkpoints == 1
ast.fix_missing_locations(tree)
namespace = {'__name__': 'frozen_auditor_worker', '__file__': str(source),
             'select_files': select_files, 'shared_out': formal}
exec(compile(tree, str(source), 'exec'), namespace)
namespace['write_atomic'] = atomic
out.mkdir(parents=True, exist_ok=True)
(out / 'worker_binding.json').write_text(json.dumps({
    'frozen_checker_sha256': source_hash,
    'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'worker': worker, 'workers': count, 'scope': 'partial batch checks; formal auditor must aggregate all cells'
}, indent=2) + '\n')
namespace['main'](run, out)
