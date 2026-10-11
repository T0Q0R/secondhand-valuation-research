"""Noncommuting normalization is a concrete withholding exploit."""
import numpy as np

from run_emc_scale_development import families


def test_state_scale_must_precede_certificate_intersection():
    lower=np.full((1,16),20.);lower[0,0]=10.
    upper=np.full((1,16),100.)
    sigma=np.full((1,16),.1);sigma[0,0]=4.
    intervals=families(lower,upper,sigma,.2,1.)
    scaled_emc_lower=intervals[3,0,0]
    assert np.allclose(scaled_emc_lower,19.9)
    assert scaled_emc_lower[0]>=scaled_emc_lower[1]
    # Intersecting first, then applying the current state's scale, would
    # instead pay 16 for full disclosure and 19.9 after withholding.
    naive_full=20.-4.;naive_hidden=20.-.1
    assert naive_hidden-naive_full>3.8
