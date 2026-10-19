"""Package exact checked manuscripts and bounded aggregate support, no raw data."""
from pathlib import Path
import hashlib,json,re,zipfile

ROOT=Path(__file__).resolve().parents[2]
N=Path(__file__).parent
INTEGRATED_COMMIT='d212cb4567c483f8affddf1b485c9b79dbfb1b31'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    qa=json.loads((N/'qa.json').read_text())
    assert qa['status']=='source_numeric_and_visual_checks_passed'
    files=set()
    for doc in qa['documents']:
        tex=ROOT/('paper/innovation-addendum-v1.tex' if doc['name']=='main' else 'paper/review-supplement-v1/main.tex')
        pdf=tex.with_suffix('.pdf')
        assert sha(tex)==doc['source_sha256'] and sha(pdf)==doc['pdf_sha256']
        files.update([tex,pdf])
        for asset in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',tex.read_text()):
            candidates=[tex.parent/asset,tex.parent/'images'/asset]
            p=next(p for p in candidates if p.exists());files.add(p)
    for folder in ['data-construction','mechanisms','gap']:
        files.update(p for p in (N/folder).iterdir() if p.suffix in ['.csv','.json','.md','.zip'])
    for name in ['qa.json','figure-qa.json','diagnostics-qa.json','PLAN.zh.md','REVIEW_RESPONSE.zh.md','DIAGNOSTICS.zh.md','FIGURE_CONTRACT.zh.md','LITERATURE_SCOPE.zh.md','plot_gap.py','qa_paper.py','analyze_gap.py','audit_gap_selection.py','analyze_mechanisms.py','describe_data.py','build_supplement.py','gap-supplement.tex','integrate_full_gap.py','package_gap_receipts.py','build_delivery.py','legacy-extended-appendix.tex','before-prose-revision.tex','before-full-gap-integration.tex','baseline-bindings.json','integration-sync.json']:
        files.add(N/name)
    files.update((ROOT/'paper/figures/review-v1').glob('*.csv'))
    files.update((ROOT/'paper/figures/review-v1').glob('*.svg'))
    files.update((ROOT/'paper/figures/review-v1').glob('*.json'))
    ext=ROOT/'notes/external-reproduction-synthetic-v1/numerical-difference-table-v1'
    files.update(p for p in ext.iterdir() if p.suffix in ['.csv','.json','.md','.tex'])
    files.update([ROOT/'LICENSE',ROOT/'LICENSE_SCOPE.md'])
    readme=N/'DELIVERY.zh.md'
    readme.write_text('''# 审稿后修订交付（2026-10-19）

当前主稿27页，补充13页，正文11pt、1英寸边距，21条参考文献。主稿10表/7图，补充12表/5图（包含原扫描四图）。新更强gap对照已完整进入正文表4、补充S4/表S10–S11/图S1，摘要、引言和讨论同步报告其反例。

## 阅读入口

- 主稿：paper/innovation-addendum-v1.pdf；同目录tex可编辑。
- 补充：paper/review-supplement-v1/main.pdf；同目录main.tex可编辑，图片在images内。
- 修改及科学边界：notes/review-improvement-v1/REVIEW_RESPONSE.zh.md。
- 完整新结果：notes/review-improvement-v1/gap/RESULTS.zh.md，以及该目录全部CSV。
- 凭据：gap/scalar-receipts-v2.zip，663项标量文件，内含360拟合/90评价/30选择凭据及清单；没有模型、数组或逐条记录。
- 检查：qa.json、figure-qa.json与diagnostics-qa.json。编译和数值绑定通过；全部40页视觉检查通过，无Overfull或未定义引用。保留4处主稿参考文献、2处补充Underfull，不影响可读性。

## 核心结果及限制

原RPL×五族90格、外机现有6格差表与DOI归档均保留。新增强gap90格全部完成；每族4个候选，仅用训练OOF选参。相比选定RPL，选定gap在三来源均值操纵增益低34.55/63.37/30.23%，30/30配对方向一致；两组真实来源平均诚实和攻击MAE也更低，合成来源误差更高。因此不支持RPL普遍优于更强gap，也不把固定β=.5的叠加效果推广为强gap叠加结论。候选有限、没有联合λ×β全局搜索，最大权重不是已知最优或推荐默认值。

固定回顾性样本不证明实际市场或真实卖家有效性；训练种子不是新训练总体。恢复图诊断不能作因果中介识别。外机严格数值复现仍失败，未放宽容差或要求新手工重跑。新增90格不是原1206格四阶段审计覆盖的扩张。该交付是修订稿与可核查证据，不是投稿完成、期刊格式合规或作者科学批准。

## 文件和版本

论文、完整汇总及QA的集成提交为 d212cb4567c483f8affddf1b485c9b79dbfb1b31；交付包由后续提交保存。ZIP内MANIFEST.json逐项列出精确文件哈希；包外delivery-manifest.json绑定整个ZIP，避免自指哈希。

DOI 10.5281/zenodo.23447567 仍是源89ad56e的不可变软件版本1.0.0，**不含此次后续机制诊断、强gap证据或论文修订**。此次新增证据由仓库提交和本包清单标识，未替换旧DOI文件。

解压后保留目录结构，可从paper目录编译innovation-addendum-v1.tex，从paper/review-supplement-v1目录编译main.tex（均已用Tectonic同源导出，并经桌面内置编译通过）。所有文稿外部图片依赖均在本包。重新执行科学分析需要仓库的完整依赖与本地模型/原始产物；本包不是完整训练环境或数据分发包。

项目代码/文稿遵循项目许可范围，第三方数据/软件保留各自许可；请参阅LICENSE和LICENSE_SCOPE.md。作者顺序为汤宇晨、游凤芹（第二兼通讯）、顾峻祥（第三）、庞鑫（第四）；已知写作/指导贡献已写入，基金及利益冲突按用户要求不推断。
''')
    files.add(readme)
    rows=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(files)]
    metadata=dict(integrated_commit=INTEGRATED_COMMIT,scope='Checked manuscript sources, PDFs, figure assets, aggregate evidence and scalar receipt archive; no raw records, per-listing outcomes or weights',files=rows)
    archive=ROOT/'paper/review-improvement-delivery-v1.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for row in rows:
            info=zipfile.ZipInfo(row['path'],date_time=(2026,10,19,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,(ROOT/row['path']).read_bytes())
        z.writestr('MANIFEST.json',json.dumps(metadata,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None and len(z.namelist())==len(rows)+1
        for row in rows:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
        # Check that both exact manuscript source trees have all graphics in the ZIP.
        for tex in ['paper/innovation-addendum-v1.tex','paper/review-supplement-v1/main.tex']:
            for asset in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}',z.read(tex).decode()):
                parent=Path(tex).parent
                assert str(parent/asset) in z.namelist() or str(parent/'images'/asset) in z.namelist()
    receipt=dict(status='verified',archive=str(archive.relative_to(ROOT)),bytes=archive.stat().st_size,sha256=sha(archive),files=len(rows)+1,main_pages=27,supplement_pages=13,source_and_asset_closure='all included graphics resolve within archive; exact checked source/PDF hashes verified',integrated_commit=INTEGRATED_COMMIT,manifest=metadata)
    (N/'delivery-manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print({k:v for k,v in receipt.items() if k!='manifest'})

if __name__=='__main__':main()
