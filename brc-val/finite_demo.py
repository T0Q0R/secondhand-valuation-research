"""Finite-domain BRC mechanism checks; synthetic prices, full bundle audits."""
import argparse
from fractions import Fraction
import hashlib
import itertools
import json
import math
from pathlib import Path


TYPES = list(itertools.product((0, 1), repeat=2))
VALUES = dict(zip(TYPES, (60.0, 100.0, 120.0, 150.0)))
CAP = 200.0
PUBLIC_REPORTS = list(itertools.product((None, 0, 1), repeat=2))


def envelope(report):
    prices = [price for typ, price in VALUES.items()
              if all(r is None or r == t for r, t in zip(report, typ))]
    if not prices:
        raise ValueError("No certified compatible type")
    lo, hi = min(prices), max(prices)
    anchor = (lo + hi) / 2
    floor = (max((anchor - lo) / anchor,
                 (hi - anchor) / (CAP - anchor)) if lo != hi else 0.0)
    return lo, hi, anchor, floor


def probabilities(bounds, budget):
    floors = [min(1.0, math.nextafter(b[3], math.inf)) if b[3] else 0.0
              for b in bounds]
    variances = [((b[1] - b[0]) / 2) ** 2 for b in bounds]
    if sum(Fraction(f) for f in floors) > budget:
        raise ValueError("Insufficient certified audit budget")
    active = sum(v > 0 for v in variances)
    if active <= budget:
        return [float(v > 0) for v in variances]

    def at(multiplier):
        return [min(1.0, max(f, math.sqrt(v / multiplier))) if v else 0.0
                for f, v in zip(floors, variances)]

    lower, upper = 0.0, 1.0
    while sum(at(upper)) > budget:
        upper *= 2
    for _ in range(100):
        mid = (lower + upper) / 2
        if sum(at(mid)) > budget:
            lower = mid
        else:
            upper = mid
    chosen_prob = at(upper)
    # A rounded float sum <= B does not certify the represented exact sum <= B.
    while sum(Fraction(p) for p in chosen_prob) > budget:
        i = max(range(len(chosen_prob)), key=lambda j: chosen_prob[j]-floors[j])
        lowered = math.nextafter(chosen_prob[i], 0.0)
        if lowered < floors[i]:
            raise ValueError("Cannot represent feasible probabilities at precision")
        chosen_prob[i] = lowered
    return chosen_prob


def draw(prob, uniform):
    """Systematic sample: one U+k per interval of length at most one."""
    selected = []
    left = Fraction(0)
    uniform = Fraction(uniform)
    for i, p in enumerate(prob):
        right = left + Fraction(p)
        k = math.ceil(left - uniform)
        if left <= uniform + k < right:
            selected.append(i)
        left = right
    return selected


def exact_law(prob):
    """Integrate the sampler independently at all cumulative breakpoints."""
    breaks = {Fraction(0), Fraction(1)}
    cumulative = Fraction(0)
    for p in prob:
        cumulative += Fraction(p)
        fraction = cumulative - math.floor(cumulative)
        if 0 < fraction < 1:
            breaks.add(fraction)
    edges = sorted(breaks)
    return [(right - left, draw(prob, (left + right) / 2))
            for left, right in zip(edges[:-1], edges[1:])]


def reports_for(typ):
    return list(itertools.product(*[(None, t) for t in typ]))


def check(output):
    if output.exists():
        raise FileExistsError("Keep completed finite demonstrations immutable")
    budget = 2
    global_floor = 3 * envelope((None, None))[3]
    assert global_floor <= budget
    profile_cache = {}
    max_budget = 0
    max_marginal_error = 0.0
    max_variance_gap = 0.0
    for profile in itertools.product(PUBLIC_REPORTS, repeat=3):
        bounds = [envelope(r) for r in profile]
        p = probabilities(bounds, budget)
        law = exact_law(p)
        assert abs(sum(w for w, _ in law) - 1) < 1e-12
        for i in range(3):
            marginal = sum(w for w, chosen in law if i in chosen)
            max_marginal_error = max(max_marginal_error, abs(marginal - p[i]))
            assert abs(marginal - p[i]) < 1e-10
        for _, chosen in law:
            max_budget = max(max_budget, len(chosen))
            assert len(chosen) <= budget
        active = sum(b[0] != b[1] for b in bounds)
        uniform_p = min(1.0, budget / active) if active else 0.0
        if all(b[3] <= uniform_p + 1e-12 for b in bounds):
            optimized = sum(((b[1] - b[0]) / 2) ** 2 * (1 / pi - 1)
                            for b, pi in zip(bounds, p) if pi)
            uniform = sum(((b[1] - b[0]) / 2) ** 2 * (1 / uniform_p - 1)
                          for b in bounds if b[0] != b[1])
            max_variance_gap = max(max_variance_gap, optimized - uniform)
            assert optimized <= uniform + 1e-8
        profile_cache[profile] = (bounds, p, law)

    cases = 0
    quote_checks = 0
    max_mean_error = 0.0
    max_concave_gain = 0.0
    min_quote, max_quote = math.inf, -math.inf
    for true_types in itertools.product(TYPES, repeat=3):
        true_prices = [VALUES[t] for t in true_types]
        for profile in itertools.product(*[reports_for(t) for t in true_types]):
            bounds, p, law = profile_cache[profile]
            means, concave = [0.0] * 3, [0.0] * 3
            for weight, chosen in law:
                for i, (b, pi, true) in enumerate(zip(bounds, p, true_prices)):
                    q = b[2] + (true - b[2]) / pi if i in chosen else b[2]
                    quote_checks += 1
                    assert -1e-8 <= q <= CAP + 1e-8
                    # Guard roundoff only for evaluating log1p, not the quote.
                    assert q > -1
                    means[i] += float(weight) * q
                    concave[i] += float(weight) * math.log1p(q)
                    min_quote, max_quote = min(min_quote, q), max(max_quote, q)
            for mean, util, true in zip(means, concave, true_prices):
                max_mean_error = max(max_mean_error, abs(mean - true))
                max_concave_gain = max(max_concave_gain, util - math.log1p(true))
                assert abs(mean - true) < 1e-8
                assert util <= math.log1p(true) + 1e-10
            cases += 1

    rejected = False
    try:
        probabilities([envelope((None, None))] * 3, 1)
    except ValueError:
        rejected = True
    assert rejected
    # A counterexample to correcting then clipping, with success and withdrawal.
    a, true, p = 100.0, 60.0, 0.2
    audited = a + (true - a) / p
    corrected_mean = (1 - p) * a + p * audited
    clipped_mean = (1 - p) * a + p * max(0.0, audited)
    failed_audit_mean = a + 0.8 * (true - a)
    assert abs(corrected_mean - true) < 1e-12
    assert clipped_mean > true and failed_audit_mean > true
    # Naturally absent true record need not have a singleton compatibility set.
    natural_anchor, natural_value, natural_p = 100.0, 90.0, 0.5
    natural_verified = natural_anchor + (natural_value-natural_anchor)/natural_p
    assert abs((1-natural_p)*natural_anchor + natural_p*natural_verified
               - natural_value) < 1e-12

    output.mkdir(parents=True)
    result = {
        "status": "complete_finite_mechanism_checks",
        "scope": "Synthetic 3-item, 2-field, 4-complete-type market; no model fitting",
        "currency": "artificial price units, not observed market prices",
        "audit_unit": "one full two-field bundle; not one field query",
        "price_cap": CAP, "budget_bundles": budget,
        "all_report_profile_reserve_floor": global_floor,
        "public_report_profiles": len(profile_cache),
        "truth_type_and_report_cases": cases,
        "realized_quote_checks": quote_checks,
        "max_realized_audit_bundles": max_budget,
        "max_marginal_probability_error": max_marginal_error,
        "max_expected_price_error": max_mean_error,
        "max_concave_hiding_gain": max_concave_gain,
        "max_optimized_minus_feasible_uniform_variance_bound": max_variance_gap,
        "observed_quote_range": [min_quote, max_quote],
        "budget_one_rejected": rejected,
        "counterexamples": {
            "direct_unbounded_audited_quote": audited,
            "direct_unbounded_mean": corrected_mean,
            "clipped_mean": clipped_mean,
            "success_0_8_with_uncorrected_failure_mean": failed_audit_mean,
            "withdraw_after_draw_unaudited_quote": a,
            "positive_disclosure_cost": "Equal expected price does not offset disclosure cost",
        },
        "natural_missing_arithmetic_check": {
            "scope": "one-record arithmetic only, not the complete-type market",
            "expected_quote": natural_value,
            "honest_quote_is_random": True,
        },
        "limitations": ["No real-data performance or certified real-data envelopes",
                        "Full bundle succeeds with certainty in primary finite market",
                        "Zero disclosure cost and locked reports before private draw",
                        "Finite type-domain proof; method novelty remains unverified"],
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    check(parser.parse_args().output)
