"""Bounded teacher-advice edits of the current source, not a replacement paper."""
from pathlib import Path
import json,hashlib,re,difflib
import pandas as pd
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
p=HERE/'baseline-reviewed-source.tex';s=p.read_text();assert hashlib.sha256(p.read_bytes()).hexdigest()=='5604909da964a80acfd906ee697142a5d6f2ddedae6431373a051d8e6bfa14d3'
changes=[]
def replace(old,new):
    global s
    assert s.count(old)==1,old;s=s.replace(old,new,1);changes.append(new)
replace('''contrasts, fitting-seed main effects explain over 98\\% of conditional bootstrap
variance;''','''contrasts in the uncapped design, fitting-seed main effects explain over 98\\%
of conditional bootstrap variance;''')
replace('''oracle, $72/13$ for the best global mixture of the specified eight rules, and
$8$ for risk ordering. These are artificial linear quote units, not empirical''',r'''oracle, $72/13$ for the best global mixture of eight fixture rules, and
$8$ for risk ordering. The eight rules are the six priority permutations of
three items, risk ordering by residual leverage $(\Delta_i-2\eta)_+$, and
no query; this fixture library differs from the twelve-rule empirical CDM
library in Section~3.2. These are artificial linear quote units, not empirical''')
replace('''At a 5\\% honest-error allowance, the frozen allocation study has 8, 4, 2, 0
and 0 passing points across the respective inflation cutoffs.''',r'''At a 5\% honest-error allowance, the frozen allocation study has 8/18, 4/18,
2/18, 0/18 and 0/18 passing contrasts across the respective inflation cutoffs.''')
replace('''joint-policy family, the zero-cutoff gate retains three small MUCars gains;
no joint point passes any inflation cutoff of 5\\% or more.''',r'''joint-policy family, the zero-cutoff gate retains 3/18 contrasts, all small
MUCars gains; 0/18 pass any inflation cutoff of 5\% or more.''')
replace('''Cost per hidden field & Inflation difference & Attack-MAE difference & Failure difference (pp)''','''Cost per hidden field & Inflation improvement & Attack-MAE improvement & Failure improvement (pp)''')
replace('''1,000 records and three fitting seeds. All differences are no-feedback minus
feedback, so positive values favor feedback.''','''1,000 records and three fitting seeds. Improvements are no-feedback minus
feedback; positive values mean reductions in inflation, attacked error or failure.''')
replace('''verification; it does not isolate improved feedback quality as its cause.
Appendix~\\ref{app:mechanism_diagnostics} gives the utility-based bounds.''',r'''verification; it does not isolate improved feedback quality as its cause.
Constructively, deterrence moves this subset toward ordinary valuation:
at both 0.02 cost specifications, feedback no longer worsens mean inflation
and lowers mean honest error, attacked error and query failure. This is a
conditional descriptive benefit, not a fully nonstrategic limit: residual
concealment remains positive. Appendix~\ref{app:mechanism_diagnostics} gives
the utility-based bounds.''')
replace('''Their capped shares are 90.97\\% and 87.42\\%; interval-width ratios alone do
not identify these components.''',r'''Their capped shares are 90.97\% and 87.42\%; these compare different cohort
and weighting designs, not a pure replication-size change. Interval-width
ratios alone do not identify the components.''')
replace('''All 48 capped/full real-source feedback decompositions are retained.
Thirty-seed projections''',r'''All 48 capped/full real-source feedback decompositions are retained.
Capped components use ten equal 100-record batches; uncapped MUCars components
use 107 batches normalized by record counts, including a 72-record tail.
Thus the outcome matrix and averaging weights both change. For top-$B$ and
minimax, batch variances fall by factors 5.73 and 8.04 (not 10.7), while
seed-main variances change by $-13.20\%$ and $-9.43\%$. This is not variance
reduction from sample size alone. Holding all 107 batches fixed and changing
only equal-batch to record-count weights changes the seed term by merely
$-0.16\%$ and $+0.11\%$, respectively; the larger change cannot be attributed
to tail weighting alone.

Thirty-seed projections''')
replace('''Only one covered JUCars and 28 covered MUCars records have a naturally missing
category, explaining the concentration of effects. The guarantee covers only''',r'''On the declared covered domain, the envelope is exactly costless for complete
categorical records: 800/801 JUCars and 971/999 MUCars records have singleton
completion sets. All quotation and error changes are confined to the one and
28 naturally incomplete records, respectively. For the MUCars subset, the
largest individual quotation reduction is 25.5\% of that record's original
predicted quote, while mean honest-MAE increases range from 374.24 to 851.51
currency units (Table~\ref{tab:final_record_pilot}). Quotation discounts and
absolute-error costs have different denominators and must not be conflated.
The practical trade-off is zero change on complete covered categorical
records but potentially substantial discounts on naturally incomplete ones.
The guarantee covers only''')
target=ROOT/'paper/innovation-addendum-v1.tex';target.write_text(s)
(HERE/'manuscript-changes.patch').write_text(''.join(difflib.unified_diff(p.read_text().splitlines(True),s.splitlines(True),fromfile='v3-reviewed',tofile='teacher-v4-revised')))
(HERE/'response-excerpts.tex').write_text('% Exact internal correspondence excerpts, not a submitted reply.\n'+'\n\n'.join('\\RevisedExcerpt{'+x+'}' for x in changes)+'\n')
(HERE/'revision-receipt.json').write_text(json.dumps(dict(status='source_backfilled_pending_compile_and_layout',source_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),replacements=len(changes),abstract_words=len(re.findall(r'\S+',re.search(r'\\begin\{abstract\}(.*?)\\end\{abstract\}',s,re.S)[1]))),indent=2)+'\n')
print('Applied',len(changes),'bounded replacements')
