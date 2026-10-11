import pandas as pd
import pytest

from equal_tuning import GRID,METHODS,choose_weights,tuning_split


def test_tuning_split_is_label_independent_and_excludes_outer_heldout():
    frame=pd.DataFrame({'listing_id':[f'x-{i}' for i in range(100)],'target_log':range(100)})
    outer_train=frame.iloc[:80].copy()
    train,validation=tuning_split(outer_train)
    changed=outer_train.copy()
    changed.target_log=-1000
    again=tuning_split(changed)
    assert train.listing_id.tolist()==again[0].listing_id.tolist()
    assert validation.listing_id.tolist()==again[1].listing_id.tolist()
    assert not set(train.listing_id)&set(validation.listing_id)
    assert not (set(train.listing_id)|set(validation.listing_id))&set(frame.iloc[80:].listing_id)


def test_equal_trial_counts_and_declared_tie_order():
    trials=[{'method':m,'gap_weight':beta,'objective':1.} for m in METHODS for beta in GRID]
    assert choose_weights(trials)=={m:.25 for m in METHODS}
    with pytest.raises(ValueError):choose_weights(trials[:-1])
    changed=[dict(row,objective=0 if row['gap_weight']==1 else 1) for row in trials]
    assert choose_weights(changed)=={m:1. for m in METHODS}
