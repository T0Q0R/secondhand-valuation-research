"""Summarize verified matched cells and existing external-machine summaries.

No fitting, inference, response search, tolerance changes or manuscript edits.
"""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=ROOT/'outputs/rpl-five-factorial-v3'
EXT=ROOT/'notes/external-reproduction-synthetic-v1'
METRICS=['mean_positive_log_inflation','clean_mae','attack_mae',
         'failed_query_fraction','max_remaining_response_regret','nonconverged_batch_fraction']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def factorial():
    done=read(RUN/'completion.json')
    assert done['cells']==90 and sha(RUN/'summary.csv')==done['summary_sha256']
    df=pd.read_csv(RUN/'summary.csv')
    assert len(df)==90 and not df.duplicated(['dataset','seed','rpl_weight','family']).any()
    assert sorted(df.seed.unique())==[13,42,2026]
    receipts=[];nrows=0;dev=0
    for cp in sorted(RUN.glob('*/seed-*/rpl-*/*/completion.json')):
        r=read(cp);assert sha(cp.parent/'outcomes.csv.gz')==r['outcomes_sha256']
        assert sha(ROOT/r['inputs']['price_model'])==r['inputs']['price_sha256']
        for name,h in r['inputs']['source_bindings'].items():assert sha(ROOT/name)==h
        assert sha(cp.parent/'scores.npz')==r['inputs']['score_sha256']
        s=r['summary'];match=df[(df.dataset==s['dataset'])&(df.seed==s['seed'])&(df.family==s['family'])&(df.rpl_weight==s['rpl_weight'])]
        assert len(match)==1
        for m in METRICS:np.testing.assert_allclose(match.iloc[0][m],s[m],atol=1e-12,rtol=1e-12)
        receipts.append(dict(path=str(cp.relative_to(ROOT)),sha256=sha(cp),reused=bool(r.get('reused_from_v2'))))
        nrows+=s['n'];dev+=r['legal_unilateral_deviations']
    assert len(receipts)==90
    for _,g in df.groupby(['dataset','seed','rpl_weight']):
        assert g.clean_mae.max()-g.clean_mae.min()<1e-8
    df.to_csv(HERE/'factorial-90-cells.csv',index=False)
    paired=[];aggregate=[]
    for (source,family,seed),g in df.groupby(['dataset','family','seed']):
        a=g[g.rpl_weight==0].iloc[0];b=g[g.rpl_weight==1].iloc[0]
        row=dict(dataset=source,family=family,seed=int(seed))
        for m in METRICS:
            row[m+'_lambda0']=a[m];row[m+'_lambda1']=b[m]
            row[m+'_delta']=b[m]-a[m]
            row[m+'_relative_change_pct']=100*(b[m]/a[m]-1) if a[m]!=0 else np.nan
        paired.append(row)
    pair=pd.DataFrame(paired);assert len(pair)==45
    pair.to_csv(HERE/'factorial-45-paired-effects.csv',index=False)
    for (source,family),g in pair.groupby(['dataset','family']):
        row=dict(dataset=source,family=family,n_fitting_seeds=3)
        for m in METRICS:
            for w in [0,1]:
                col=f'{m}_lambda{w}';row[col+'_mean']=g[col].mean();row[col+'_min']=g[col].min();row[col+'_max']=g[col].max()
            delta=g[m+'_delta'];row[m+'_paired_delta_mean']=delta.mean();row[m+'_paired_delta_min']=delta.min();row[m+'_paired_delta_max']=delta.max()
            a=g[m+'_lambda0'].mean();b=g[m+'_lambda1'].mean()
            row[m+'_ratio_of_means_change_pct']=100*(b/a-1) if a else np.nan
        row['inflation_decreasing_seeds']=int((g.mean_positive_log_inflation_delta<0).sum())
        aggregate.append(row)
    ag=pd.DataFrame(aggregate);ag.to_csv(HERE/'factorial-15-comparisons.csv',index=False)
    interactions=[]
    for source in ag.dataset.unique():
        reference=pair[(pair.dataset==source)&(pair.family=='aco')].set_index('seed')
        for family in ['sefa','gdfs','dime','efa']:
            g=pair[(pair.dataset==source)&(pair.family==family)].set_index('seed')
            for metric in METRICS:
                for seed in g.index:
                    interactions.append(dict(dataset=source,family=family,reference_family='aco',seed=int(seed),metric=metric,
                         difference_of_paired_deltas=g.loc[seed,metric+'_delta']-reference.loc[seed,metric+'_delta']))
    pd.DataFrame(interactions).to_csv(HERE/'factorial-interactions-vs-aco.csv',index=False)
    lines=['# RPL × 五族：90 单元结果','',
           '固定10%容量、gap=0.5；三来源×三共同拟合种子×λ0/1×五族。数字为种子均值；百分比为均值之比。原始45组配对、全种子范围及差中差CSV一并提供；n=3开发证据，无确认性显著性或置信区间主张。','',
           '| 来源 | 采集族 | inflation λ0 | inflation λ1 | 变化% | 下降种子 | attacked MAE变化% | 失败查询Δ(pp) |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for _,r in ag.iterrows():
        lines.append(f"| {r.dataset} | {r.family} | {r.mean_positive_log_inflation_lambda0_mean:.7f} | {r.mean_positive_log_inflation_lambda1_mean:.7f} | {r.mean_positive_log_inflation_ratio_of_means_change_pct:+.2f} | {r.inflation_decreasing_seeds}/3 | {r.attack_mae_ratio_of_means_change_pct:+.2f} | {100*r.failed_query_fraction_paired_delta_mean:+.2f} |")
    nonconv=int((df.nonconverged_batch_fraction>1e-10).sum());batches=int(round((df.nonconverged_batch_fraction*10).sum()))
    lines+=['',f'全部90格保留：{nonconv}格含未收敛批，共{batches}/900批；最大剩余单边后悔为{df.max_remaining_response_regret.max():.9f} log。新拟合0次。', '',
            '四个神经采集族评分固定；ACO的指导集损失按估价器重建。主效应解释为固定族内的RPL变化，跨族变化还包含各策略适配与共享批次分配作用。全部90格通过独立整数分配和逐记录全部合法单边偏离复算，ACO另有全评分坐标重建；这不等于旧1206格的四阶段拟合/统计闭包。', '',
            '原v1因并行文稿编辑触发保护而退出，v2误将合成训练样本数用于JUCars而在该来源评价前停止；两者源码、manifest、失败与有效检查点完整保留。v3使用原来源训练ID核验并只复用科学输入完全相同的有效结果。']
    (HERE/'RESULTS.zh.md').write_text('\n'.join(lines)+'\n')
    tex=[r'\begin{table}[htbp]',r'\centering\small',r'\caption{Matched RPL by acquisition-family crossing at 10\% capacity. Three fitting-seed means; changes are ratios of means. All cells, including nonconvergence, are retained.}',r'\label{tab:rpl-five-crossing}',r'\begin{tabular}{llrrrr}',r'\toprule Source & Family & Inflation $\lambda=0$ & Inflation $\lambda=1$ & Change (\%) & MAE change (\%)\\\midrule']
    for _,r in ag.iterrows():tex.append(f'{r.dataset} & {r.family.upper()} & {r.mean_positive_log_inflation_lambda0_mean:.6f} & {r.mean_positive_log_inflation_lambda1_mean:.6f} & {r.mean_positive_log_inflation_ratio_of_means_change_pct:+.2f} & {r.attack_mae_ratio_of_means_change_pct:+.2f}'+r'\\')
    tex += [r'\bottomrule\end{tabular}',r'\end{table}']
    (HERE/'factorial-table.tex').write_text('\n'.join(tex)+'\n')
    write(HERE/'verification.json',dict(status='all_90_receipts_and_summaries_bound',cells=90,paired_comparisons=45,source_family_comparisons=15,
          outcome_rows=nrows,legal_unilateral_deviations=dev,nonconverged_cells=nonconv,nonconverged_batches=batches,
          maximum_regret=float(df.max_remaining_response_regret.max()),receipts=receipts,
          source_manifest_sha256=sha(RUN/'manifest.json'),source_completion_sha256=sha(RUN/'completion.json'),
          script_sha256=sha(Path(__file__)),four_stage_fit_statistical_audit=False))
    print(ag[['dataset','family','mean_positive_log_inflation_ratio_of_means_change_pct','inflation_decreasing_seeds']].to_string(index=False))


def external():
    out=EXT/'numerical-difference-table-v1';out.mkdir(exist_ok=True)
    comp=pd.read_csv(EXT/'returned/reference-comparison.csv')
    summary=pd.read_csv(EXT/'returned/summary.csv');receipt=read(EXT/'returned/external-training-receipt.json')
    intake=read(EXT/'intake-check.json');contract=read(ROOT/'reproduction/macos-core-v2/contract.json')
    for name,h in intake['files'].items():assert sha(EXT/'returned'/name)==h
    assert len(comp)==len(summary)==6 and sha(EXT/'returned/summary.csv')==receipt['summary_sha256']
    long=[];wide=[]
    for _,r in comp.iterrows():
        w=dict(method=r.method,seed=int(r.seed),budget=r.budget)
        for m in METRICS:
            a=float(r[m+'_reference']);b=float(r[m+'_new']);delta=b-a;limit=contract['metric_atol']+contract['metric_rtol']*abs(a)
            long.append(dict(method=r.method,seed=int(r.seed),budget=r.budget,metric=m,local=a,external=b,
                        external_minus_local=delta,absolute_difference=abs(delta),relative_difference_pct=100*delta/a if a else np.nan,
                        original_tolerance=limit,strict_pass=bool(abs(delta)<=limit)))
            w[m+'_local']=a;w[m+'_external']=b;w[m+'_delta']=delta
        wide.append(w)
    long=pd.DataFrame(long);wide=pd.DataFrame(wide);long.to_csv(out/'differences-36.csv',index=False);wide.to_csv(out/'comparison-6-cells.csv',index=False)
    for r in receipt['comparisons']:
        g=long[long.metric==r['metric']]
        assert bool(g.strict_pass.all())==r['passed']
        np.testing.assert_allclose(g.absolute_difference.max(),r['maximum_absolute_difference'],atol=1e-12,rtol=1e-10)
    lines=['# 外机既有六单元数值差对比表','',
           '仅整理原有synthetic/seed13、λ0/1、容量0/10/30%的六格。每格1000记录、10批。斜线前为本机参考，后为外机。严格验收继续未通过；容差仍为原合同的atol + rtol×|reference|。未重训或重跑外机。','',
           '| λ | 容量 | inflation (log) | honest MAE | attacked MAE | 失败查询(%) | 最大regret(log) | 未收敛批/10 |',
           '|---:|---:|---:|---:|---:|---:|---:|---:|']
    for _,r in wide.iterrows():
        weight=0 if r.method.startswith('path-0-') else 1
        values=[]
        for m in METRICS:
            a=r[m+'_local'];b=r[m+'_external']
            if m=='nonconverged_batch_fraction':v=f'{round(a*10)}/{round(b*10)}'
            elif m=='failed_query_fraction':v=f'{a*100:.2f} / {b*100:.2f}'
            elif 'mae' in m:v=f'{a:.3f} / {b:.3f}'
            else:v=f'{a:.7f} / {b:.7f}'
            values.append(v)
        lines.append(f'| {weight} | {r.budget*100:.0f}% | '+' | '.join(values)+' |')
    lines+=['','## 原阈值下的差异','', '| 指标 | 最大绝对差 | 超阈值格数/6 |','|---|---:|---:|']
    for m,g in long.groupby('metric',sort=False):lines.append(f'| {m} | {g.absolute_difference.max():.10g} | {int((~g.strict_pass).sum())}/6 |')
    lines+=['','10%容量下λ1相对λ0的inflation降幅本机53.97%、外机57.54%；同方向仅属单种子的描述。最坏regret明显不同，30%容量λ1未收敛由1/10增至2/10；不能用方向一致替代严格数值验收，也不宣称已因果定位底层环境原因。','',
            '来源：原returned/summary.csv、reference-comparison.csv、external-training-receipt.json与intake-check.json；36项原始差值、相对差、原容差和逐项pass/fail见differences-36.csv。']
    (out/'TABLE.zh.md').write_text('\n'.join(lines)+'\n')
    tex=[r'\begin{table}[htbp]',r'\centering\small',r'\caption{Existing external-machine numerical comparison, synthetic seed 13. Each entry is local reference / external value. Strict numerical reproduction failed under the original tolerances.}',r'\label{tab:external-numerical}',r'\begin{tabular}{rrlll}',r'\toprule $\lambda$ & Capacity & Inflation (log) & Honest MAE & Attacked MAE\\\midrule']
    for _,r in wide.iterrows():
        weight=0 if r.method.startswith('path-0-') else 1
        tex.append(f'{weight} & {r.budget*100:.0f}\\% & {r.mean_positive_log_inflation_local:.7f}/{r.mean_positive_log_inflation_external:.7f} & {r.clean_mae_local:.3f}/{r.clean_mae_external:.3f} & {r.attack_mae_local:.3f}/{r.attack_mae_external:.3f}'+r'\\')
    tex += [r'\midrule $\lambda$ & Capacity & Failed query (\%) & Maximum regret (log) & Nonconverged batches /10\\\midrule']
    for _,r in wide.iterrows():
        weight=0 if r.method.startswith('path-0-') else 1
        tex.append(f'{weight} & {r.budget*100:.0f}\\% & {r.failed_query_fraction_local*100:.2f}/{r.failed_query_fraction_external*100:.2f} & {r.max_remaining_response_regret_local:.7f}/{r.max_remaining_response_regret_external:.7f} & {round(r.nonconverged_batch_fraction_local*10)}/{round(r.nonconverged_batch_fraction_external*10)}'+r'\\')
    tex += [r'\bottomrule\end{tabular}',r'\end{table}']
    (out/'table.tex').write_text('\n'.join(tex)+'\n')
    write(out/'verification.json',dict(status='existing_six_cell_differences_verified',cells=6,metric_comparisons=36,
            source_hashes={str((EXT/'returned'/p).relative_to(ROOT)):sha(EXT/'returned'/p) for p in intake['files']},
            original_metric_atol=contract['metric_atol'],original_metric_rtol=contract['metric_rtol'],
            strict_reproduction_pass=False,new_fits=0,new_external_runs=0,script_sha256=sha(Path(__file__))))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--external-only',action='store_true');a=p.parse_args()
    if not a.external_only:factorial()
    external()
