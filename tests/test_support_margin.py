import numpy as np
import pytest

from experiments.support_margin import LinearModel, MarginSolveError, solve_smi


def test_published_salary_example_predicts_full_model_not_lower_margin():
    # Coefficients and applicant A from the paper's worked example.
    full = LinearModel(np.array([2.1923, 1.7694]), -1.926)
    reduced = LinearModel(np.array([3.6667, 0.]), -1.3333, frozenset([1]))
    result = solve_smi([16., np.nan], [full, reduced], 5.)
    lower = 3.6667 * 16 - 1.3333 - 5
    assert result.lower_margin_objective == pytest.approx(lower)
    assert result.prediction == pytest.approx(lower)
    assert result.imputed_record[1] == pytest.approx((lower - 2.1923 * 16 + 1.926) / 1.7694)


def test_free_variables_are_not_silently_nonnegative_or_prediction_equal_to_y_star():
    full = LinearModel(np.array([1., -2.]), 0.)
    reduced = LinearModel(np.array([1., 0.]), 0., frozenset([1]))
    result = solve_smi([3., np.nan], [full, reduced], 1.)
    assert result.lower_margin_objective == pytest.approx(2.)
    assert result.imputed_record[1] == pytest.approx(.5)
    assert result.prediction == pytest.approx(2.)
    positive = LinearModel(np.array([1., 2.]), 0.)
    free = solve_smi([3., np.nan], [positive, reduced], 1.)
    nonnegative = solve_smi([3., np.nan], [positive, reduced], 1., missing_bounds=[(0, None)])
    assert free.imputed_record[1] == pytest.approx(-.5)
    assert nonnegative.imputed_record[1] == 0
    assert nonnegative.prediction == pytest.approx(3.)
    assert nonnegative.prediction != nonnegative.lower_margin_objective


def test_stage_two_unboundedness_is_reported_and_hidden_inputs_never_used():
    # Unequal positive slopes permit an unbounded sum-x objective with free
    # variables while the full-model weighted sum remains in its margin.
    full = LinearModel(np.array([1., 1., 2.]), 0.)
    reduced = LinearModel(np.array([1., 0., 0.]), 0., frozenset([1, 2]))
    with pytest.raises(MarginSolveError, match=r"Equation \(8\): status 3"):
        solve_smi([3., np.nan, np.nan], [full, reduced], 1.)


def test_inconsistent_coefficients_are_rejected_and_complete_report_is_unchanged():
    full = LinearModel(np.array([1., 2.]), 0.)
    wrong = LinearModel(np.array([-1., 0.]), 0., frozenset([1]))
    with pytest.raises(ValueError, match="sign consistent"):
        solve_smi([3., np.nan], [full, wrong], 1.)
    result = solve_smi([3., 4.], [full], 1.)
    assert result.prediction == 11.
    np.testing.assert_array_equal(result.imputed_record, [3., 4.])
