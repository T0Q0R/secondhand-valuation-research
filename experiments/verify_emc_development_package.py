"""Check every archive entry and reproduce the full EMC audit from its copy."""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    package=args.package.resolve();output=args.output.resolve();archive=package.with_suffix('.zip')
    if output.exists():raise ValueError('Fresh verification receipt required')
    manifest=json.loads((package/'manifest.json').read_text())
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(manifest['files'])|{'manifest.json'}
        for name,item in manifest['files'].items():
            assert sha(package/name)==item['sha256'] and len(z.read(name))==item['bytes']
            assert hashlib.sha256(z.read(name)).hexdigest()==item['sha256']
        assert hashlib.sha256(z.read('manifest.json')).hexdigest()==sha(package/'manifest.json')
    project=package/'sav-val';proof=package/'copy-proof.json';destination=project/'outputs/copied-independent-audit'
    script=project/'experiments/analyze_emc_development.py'
    scaled=manifest.get('scale_refinement') is not None
    wrapper=f'''
import builtins,io,json,os,runpy,sys
from pathlib import Path
package=Path({str(package)!r});project=package/'sav-val'
scaled={scaled!r}
forbidden=[Path({str(ROOT)!r}),Path({str(ROOT.parent/'experiments')!r})]
expected_probes=[Path({str(ROOT/'experiments/emc_val.py')!r}),Path({str(ROOT.parent/'experiments/data/processed/jucars_bvival_v1/splits/train.csv')!r})]
blocked=[]
original_open=builtins.open;original_io_open=io.open
def check(value):
    if isinstance(value,(str,bytes,os.PathLike)):
        actual=Path(os.fsdecode(value)).resolve()
        if not actual.is_relative_to(package) and any(actual.is_relative_to(root) for root in forbidden):
            blocked.append(str(actual));raise PermissionError('Original project/input IO denied')
def guarded(value,*a,**k):check(value);return original_open(value,*a,**k)
def guarded_io(value,*a,**k):check(value);return original_io_open(value,*a,**k)
builtins.open=guarded;io.open=guarded_io
for path in expected_probes:
    try:builtins.open(path,'rb')
    except PermissionError:pass
    else:raise AssertionError('Original-file guard probe failed')
sys.path.insert(0,str(project/'experiments'))
import emc_val,savval,pytest
modules=[('emc_val',emc_val),('savval',savval)]
if scaled:
    import run_emc_scale_development,analyze_emc_scale_development
    modules.extend([('run_emc_scale_development',run_emc_scale_development),('analyze_emc_scale_development',analyze_emc_scale_development)])
loaded={{name:str(Path(module.__file__).resolve()) for name,module in modules}}
assert all(Path(path).is_relative_to(project/'experiments') for path in loaded.values())
tests=['tests/test_emc_certificates.py']+(['tests/test_emc_state_scale.py'] if scaled else [])
result=pytest.main(tests+['-q','--confcutdir',str(project),'-p','no:cacheprovider'])
assert result==0
sys.argv=[{str(script)!r},'--run',str(project/'outputs/emc-development-v1'),'--output',{str(destination)!r}]
runpy.run_path({str(script)!r},run_name='__main__')
if scaled:
    script=project/'experiments/analyze_emc_scale_development.py'
    sys.argv=[str(script),'--parent',str(project/'outputs/emc-development-v1'),'--run',str(project/'outputs/emc-state-scale-development-v1'),'--output',str(project/'outputs/copied-independent-scale-audit')]
    runpy.run_path(str(script),run_name='__main__')
assert blocked==[str(p.resolve()) for p in expected_probes],blocked
(package/'copy-proof.json').write_text(json.dumps({{'status':'completed','tests':4 if scaled else 3,'test_exit_code':result,
'loaded_modules':loaded,'guard_probes':blocked,'unexpected_original_python_file_reads':[],
'guard_scope':'Python builtins/io open; native model-load arguments are constructed from the copied run folder; not an OS sandbox',
'scope':'saved-model and calibration/allocation arithmetic, not fresh fitting'}},indent=2)+'\\n')
'''
    process=subprocess.run([sys.executable,'-c',wrapper],cwd=project,text=True,capture_output=True)
    log=output.with_suffix('.log');log.write_text(process.stdout+process.stderr)
    if process.returncode:raise RuntimeError(f'Copied audit failed, see {log}')
    detail=json.loads(proof.read_text());audit=json.loads((destination/'completion.json').read_text())
    assert audit['status']=='completed' and audit['cell_count']==810 and audit['record_outcome_checks']==598590
    assert sha(destination/'summary.csv')==sha(project/'outputs/emc-development-v1-audit-02/summary.csv')
    result={'status':'completed','entries_sha256_verified':len(manifest['files'])+1,'archive_sha256':sha(archive),
        'manifest_sha256':sha(package/'manifest.json'),'copied_tests':4 if scaled else 3,'audit_cells':810,
        'record_outcome_checks':598590,'public_equivalence_checks':audit['forced_public_equivalence_checks'],
        'copied_audit_summary_byte_identical':True,'copy_proof':detail,'verifier_sha256':sha(__file__),
        'scope':'full EMC saved-model arithmetic from copied source/data with explicit original Python IO probes; no fresh re-fitting or final-paper completion'}
    if scaled:
        original=project/'outputs/emc-state-scale-development-v1-audit'
        copied=project/'outputs/copied-independent-scale-audit';receipt=json.loads((copied/'completion.json').read_text())
        assert receipt['status']=='completed' and not receipt['smoke'] and receipt['cells']==1080 and receipt['cases']==9
        assert receipt['record_outcome_checks']==798120 and receipt['forced_public_equivalence_checks']==2160
        assert sha(copied/'summary.csv')==sha(original/'summary.csv')
        binding=manifest['scale_refinement']
        for key,folder in [('run_completion_sha256','emc-state-scale-development-v1'),('audit_completion_sha256','emc-state-scale-development-v1-audit'),('statistics_completion_sha256','emc-state-scale-development-v1-contrasts-02')]:
            assert binding[key]==sha(project/'outputs'/folder/'completion.json')
        gate=project/'outputs/emc-state-scale-development-v1-contrasts-02/decision_gate.json'
        assert sha(gate)==binding['decision_gate_sha256'] and json.loads(gate.read_text())['all_prespecified_checks_pass'] is False
        result['scale_refinement']={'audit_cells':1080,'cases':9,'record_outcome_checks':798120,
            'public_equivalence_checks':2160,'copied_audit_summary_byte_identical':True,'practical_gate_pass':False,
            'statistics_scope':'4032 mean contrasts,6 medians and72 coverage rows checksum-verified; not rerun in this copied audit'}
    output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
