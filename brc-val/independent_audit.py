"""Independent rational integration of saved finite BRC mechanism scope."""
import argparse
from fractions import Fraction as F
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path


def audit(results_path):
    target = results_path.parent / "independent-audit.json"
    if target.exists():
        raise FileExistsError("Keep completed audit immutable")
    source = Path(__file__).with_name("finite_demo.py")
    spec = importlib.util.spec_from_file_location("brc_under_test", source)
    mechanism = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mechanism)
    result = json.loads(results_path.read_text())
    assert result["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    # These fixtures and formulas are reconstructed, not read from demo globals.
    table = {(0, 0): 60, (0, 1): 100, (1, 0): 120, (1, 1): 150}
    reports = list(itertools.product((None, 0, 1), repeat=2))
    budget, cap = 2, 200
    cases, quote_checks = 0, 0
    max_error = F(0)
    max_kkt_error = 0.0
    max_improvement = 0.0
    example = None
    for profile in itertools.product(reports, repeat=3):
        compatible, independent_bounds = [], []
        for report in profile:
            types = [typ for typ in table if all(
                reported is None or reported == actual
                for reported, actual in zip(report, typ))]
            compatible.append(types)
            lo, hi = min(table[t] for t in types), max(table[t] for t in types)
            anchor = F(lo + hi, 2)
            floor = max((anchor-lo)/anchor, (hi-anchor)/(cap-anchor)) if hi != lo else F(0)
            independent_bounds.append((lo, hi, anchor, floor))
        tested_bounds = [mechanism.envelope(r) for r in profile]
        for actual, expected in zip(tested_bounds, independent_bounds):
            assert max(abs(x-float(y)) for x, y in zip(actual, expected)) < 1e-12
        prob = mechanism.probabilities(tested_bounds, budget)
        ps = [F(p) for p in prob]
        assert sum(ps) <= budget + F(1, 10**12)
        cumulative = [F(0)]
        for p in ps:
            cumulative.append(cumulative[-1]+p)
        cuts = sorted({F(0), F(1)} | {c - c.numerator//c.denominator for c in cumulative})
        law = []
        for left, right in zip(cuts[:-1], cuts[1:]):
            midpoint = (left+right)/2
            chosen = []
            # Enumerate actual translated interval membership, not sampler code.
            for i in range(3):
                if any(cumulative[i] <= midpoint+k < cumulative[i+1]
                       for k in range(-1, budget+2)):
                    chosen.append(i)
            assert len(chosen) <= budget
            law.append((right-left, chosen))
        for i, p in enumerate(ps):
            assert sum(w for w, chosen in law if i in chosen) == p
        v = [float((hi-lo)**2)/4 for lo, hi, _, _ in independent_bounds]
        free = [i for i in range(3) if v[i] and
                float(independent_bounds[i][3])+1e-8 < prob[i] < 1-1e-8]
        if free:
            multiplier = v[free[0]]/prob[free[0]]**2
            for i in range(3):
                if not v[i]:
                    continue
                slope = v[i]/prob[i]**2
                if prob[i] >= 1-1e-8:
                    err = max(0.0, multiplier-slope)
                elif prob[i] <= float(independent_bounds[i][3])+1e-8:
                    err = max(0.0, slope-multiplier)
                else:
                    err = abs(slope-multiplier)
                max_kkt_error = max(max_kkt_error, err)
                assert err < 1e-7
            assert abs(sum(prob)-budget) < 1e-10
        active = sum(x > 0 for x in v)
        uniform_p = min(1.0, budget/active) if active else 0
        if uniform_p and all(float(b[3]) <= uniform_p+1e-12 for b in independent_bounds):
            uniform_var = sum(x*(1/uniform_p-1) for x in v)
            optimized_var = sum(x*(1/p-1) for x, p in zip(v, prob) if x)
            assert optimized_var <= uniform_var+1e-8
            reduction = (uniform_var-optimized_var)/uniform_var if uniform_var else 0
            if reduction > max_improvement:
                max_improvement = reduction
                example = {"profile": profile, "probabilities": prob,
                           "optimized_variance_bound_sum": optimized_var,
                           "feasible_uniform_variance_bound_sum": uniform_var,
                           "reduction_fraction": reduction}
        for types in itertools.product(*compatible):
            cases += 1
            mean = [F(0)]*3
            log_utility = [0.0]*3
            for weight, chosen in law:
                for i in range(3):
                    anchor = independent_bounds[i][2]
                    price = table[types[i]]
                    q = anchor+(price-anchor)/ps[i] if i in chosen else anchor
                    quote_checks += 1
                    assert -F(1,10**10) <= q <= cap+F(1,10**10)
                    mean[i] += weight*q
                    log_utility[i] += float(weight)*math.log1p(float(q))
            for i in range(3):
                error = abs(mean[i]-table[types[i]])
                max_error = max(max_error, error)
                assert error == 0
                assert log_utility[i] <= math.log1p(table[types[i]])+1e-10
    assert cases == result["truth_type_and_report_cases"] == 4096
    # Tiny near-integer floating breakpoints can increase partition counts here.
    receipt = {
        "status": "complete_independent_finite_audit",
        "method": "independent fixtures/envelopes, exact Fraction marginal and mean integration, KKT checks",
        "public_profiles": 729, "type_and_report_cases": cases,
        "rational_partition_quote_checks": quote_checks,
        "max_exact_expected_price_error": str(max_error),
        "max_water_filling_kkt_residual": max_kkt_error,
        "illustrative_best_finite_profile": example,
        "selection_note": "Maximum over all 729 toy profiles; selected illustration, not a mean effect or real-data result",
        "scope": "Fixed finite type domain only, successful full-bundle audits, zero disclosure cost",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "audit_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "results_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest(),
    }
    target.write_text(json.dumps(receipt, indent=2)+"\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    audit(parser.parse_args().results)
