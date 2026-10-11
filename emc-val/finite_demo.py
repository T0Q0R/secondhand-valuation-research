"""Finite EMC mechanism check; no real-data or conformal coverage claim."""
import itertools
import json
from pathlib import Path


def weaker(report):
    known = [j for j, v in enumerate(report) if v is not None]
    for bits in itertools.product((False, True), repeat=len(known)):
        keep = {j for j, bit in zip(known, bits) if bit}
        yield tuple(v if j in keep else None for j, v in enumerate(report))


def base_interval(report):
    # A deliberately imperfect, fixed toy estimator; units are artificial.
    center = 100 + sum(v for v in report if v is not None)
    radius = 5 + 12 * sum(v is None for v in report)
    return center - radius, center + radius


def certificate(report, q=10):
    intervals = [base_interval(s) for s in weaker(report)]
    return max(l - q for l, _ in intervals), min(u + q for _, u in intervals)


def quote(report):
    l, _ = certificate(report)
    # Do not reset empty-interval quotes: that would break monotonicity.
    return max(0, l)


def allocate(reports):
    # Complete public rule, B=1, one field/item. No access to private values.
    options = [(certificate(r)[1] - certificate(r)[0], -i, -j, i, j)
               for i, r in enumerate(reports)
               for j, v in enumerate(r) if v is None]
    return [(max(options)[3], max(options)[4])] if options else []


def replay(truth, reports):
    result = [list(r) for r in reports]
    queries = allocate(reports)
    assert len(queries) <= 1
    for i, j in queries:
        result[i][j] = truth[i][j]  # None stays None; failure still uses B.
    return [tuple(r) for r in result]


def main():
    truth = ((-20, 20), (15, -15), (None, 10))
    choices = [list(weaker(r)) for r in truth]
    nesting_checks = deviation_checks = failure_checks = 0
    max_gain = 0
    raw_violations = 0
    for reports in itertools.product(*choices):
        for r in reports:
            l, u = certificate(r)
            for s in weaker(r):
                ls, us = certificate(s)
                assert ls <= l and us >= u
                nesting_checks += 1
                raw_violations += base_interval(s)[0] > base_interval(r)[0]
        after = replay(truth, reports)
        for i, variants in enumerate(choices):
            honest = list(reports)
            honest[i] = truth[i]
            honest_after = replay(truth, honest)
            for hidden in variants:
                candidate = list(reports)
                candidate[i] = hidden
                hidden_after = replay(truth, candidate)
                gain = quote(hidden_after[i]) - quote(honest_after[i])
                assert gain <= 0
                max_gain = max(max_gain, gain)
                deviation_checks += 1
        for i, j in allocate(reports):
            if truth[i][j] is None:
                assert after[i][j] is None
                failure_checks += 1
    assert raw_violations > 0 and failure_checks > 0
    out = {
        "status": "completed_finite_mechanism_check",
        "scope": "Artificial intervals and fixed q=10; no statistical coverage or market performance claim",
        "batch_report_profiles": len(list(itertools.product(*choices))),
        "nesting_checks": nesting_checks,
        "unilateral_deviation_checks": deviation_checks,
        "raw_lower_endpoint_monotonicity_violations": raw_violations,
        "failed_replays_consuming_capacity": failure_checks,
        "max_positive_lower_quote_deviation": max_gain,
        "hard_budget": 1,
        "honest_certificates": [certificate(r) for r in truth],
    }
    destination = Path(__file__).resolve().parent / "outputs" / "finite-demo-01.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
