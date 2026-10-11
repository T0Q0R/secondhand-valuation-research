import numpy as np


def test_main_batch_size_realizes_every_requested_budget():
    # Scientific-design check: a 1% curve must not secretly be a zero-query
    # curve. A 100-record batch has integral quotas at every prespecified point.
    for fraction in [.01, .05, .1, .2, .3]:
        assert int(np.floor(100 * fraction)) >= 1
        for cohort_size in [1000, 1374, 10672]:
            sizes = [min(100, cohort_size - start) for start in range(0, cohort_size, 100)]
            assert sum(int(np.floor(fraction * size)) for size in sizes) == int(np.floor(fraction * cohort_size))
