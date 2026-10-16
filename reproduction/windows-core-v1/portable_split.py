"""Portable copies of frozen pure split functions; never import Unix file locking.
verify_split_origin checks identical function ASTs before any fitting.
"""
from pathlib import Path
import ast
import numpy as np
from run_all import rank_subset
from savval import stable_rank

def fold_assignments(frame, folds):
    if folds < 2 or len(frame) < folds:
        raise ValueError("Need at least two nonempty outer folds")
    hashes = frame.listing_id.map(lambda x: stable_rank(str(x), "sav-val-outer-v2"))
    order = np.argsort(hashes.to_numpy(), kind="stable")
    assigned = np.empty(len(frame), dtype=int)
    assigned[order] = np.arange(len(frame)) % folds
    return assigned

def inner_split(frame, fraction):
    ordered = rank_subset(frame, len(frame), "sav-val-inner-guidance-v2")
    count = int(np.floor(fraction * len(frame)))
    if count < 2 or count >= len(frame) - 2:
        raise ValueError("Insufficient inner-fitting records")
    return ordered.iloc[count:].copy(), ordered.iloc[:count].copy()

def verify_split_origin(path):
    def selected(source):
        tree = ast.parse(source)
        return {node.name: ast.dump(node, include_attributes=False)
                for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in {"fold_assignments", "inner_split"}}
    expected = selected(Path(path).read_text(encoding="utf-8"))
    actual = selected(Path(__file__).read_text(encoding="utf-8"))
    if set(expected) != {"fold_assignments", "inner_split"} or actual != expected:
        raise RuntimeError("Portable split functions differ from frozen originals")
