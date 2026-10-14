"""Standard-library audit contract validator; no training/model dependencies.
Validates this contract format and bound artifacts, not scientific conclusions.
"""
from pathlib import Path
import argparse,csv,hashlib,json,math,sys,copy,tempfile
SCHEMA_VERSION='1.0'
def require(condition,message):
    if not condition:raise ValueError(message)
def validate(contract,root):
    required=['schema_version','study','units','axes','response','outcomes','inference','audit_scope','release','artifacts']
    require(isinstance(contract,dict) and all(k in contract for k in required),'missing contract section')
    require(contract['schema_version']==SCHEMA_VERSION,'unsupported schema version')
    require(contract['study']['status']=='retrospective_posthoc','example is not preregistered')
    require(contract['units']['same_validation_across_seeds'] is True,'seed/evaluation dependence must be declared')
    for axis in ['estimator','acquisition','feedback','allocation']:require(len(contract['axes'][axis])>0,'empty axis '+axis)
    response=contract['response'];budget=response['capacity_fraction']
    require(isinstance(budget,(int,float)) and not isinstance(budget,bool) and math.isfinite(budget) and 0<=budget<=1,'invalid capacity fraction')
    require(response['retain_nonconverged'] is True,'nonconverged profiles must be retained')
    require(response['failed_queries_charged'] is True,'failed-query accounting must match this protocol')
    require(response['maximum_hidden_fields']==2,'example action space mismatch')
    names=[v['name'] for v in contract['outcomes']]
    require(len(names)==len(set(names)) and len(names)>=4,'outcomes missing or duplicate')
    require(all(v.get('unit') and v.get('definition') for v in contract['outcomes']),'outcome units/definitions missing')
    require(contract['inference']['confirmatory'] is False,'posthoc example cannot be marked confirmatory')
    require(bool(contract['audit_scope']['shared_primitives']) and bool(contract['audit_scope']['independent_components']),'audit scope missing')
    require(contract['release']['publicly_released'] is False,'private example cannot be marked public')
    require(bool(contract['release']['external_full_training_reproduction'] is False),'external reproduction not supplied')
    require(len(contract['artifacts'])>0,'no evidence bindings')
    checked=[];seen=set();root=Path(root).resolve()
    for a in contract['artifacts']:
        rel=Path(a['path']);require(not rel.is_absolute() and '..' not in rel.parts,'artifact path escapes root')
        require(str(rel) not in seen,'duplicate artifact');seen.add(str(rel));p=root/rel
        require(p.is_file(),'missing artifact '+str(rel));digest=hashlib.sha256(p.read_bytes()).hexdigest()
        require(digest==a['sha256'],'hash mismatch '+str(rel))
        if a['kind']=='csv':
            with p.open(newline='') as f:
                reader=csv.DictReader(f);require(set(a['required_columns'])<=set(reader.fieldnames or []),'missing CSV columns '+str(rel));count=sum(1 for _ in reader)
            require(count==a['rows'],'CSV count mismatch '+str(rel))
        elif a['kind']=='json':
            j=json.loads(p.read_text());require(j['status']==a['status'],'receipt status mismatch '+str(rel))
        else:require(False,'unsupported artifact kind')
        checked.append({'path':str(rel),'sha256':digest})
    return {'status':'contract_and_bound_artifacts_valid','artifacts':checked,'scope':'structural/data-binding validation only; not validity, novelty, independence, causality, fairness or inferential coverage certification'}
def selftest(contract,root):
    failures=[]
    for label,modify in [
        ('invalid_budget',lambda x:x['response'].update(capacity_fraction=1.1)),
        ('drop_nonconvergence',lambda x:x['response'].update(retain_nonconverged=False)),
        ('false_confirmation',lambda x:x['inference'].update(confirmatory=True)),
        ('wrong_hash',lambda x:x['artifacts'][0].update(sha256='0'*64)),
        ('wrong_row_count',lambda x:x['artifacts'][0].update(rows=-1)),
        ('path_escape',lambda x:x['artifacts'][0].update(path='../outside.csv'))]:
        bad=copy.deepcopy(contract);modify(bad)
        try:validate(bad,root)
        except (ValueError,KeyError,TypeError):failures.append(label)
        else:raise AssertionError('negative control accepted: '+label)
    return failures
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--protocol',type=Path,default=Path(__file__).with_name('secondhand-audit.json'));parser.add_argument('--self-test',action='store_true');parser.add_argument('--receipt',type=Path)
    a=parser.parse_args()
    try:
        contract=json.loads(a.protocol.read_text());result=validate(contract,a.root)
        result['protocol_sha256']=hashlib.sha256(a.protocol.read_bytes()).hexdigest();result['validator_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if a.self_test:result['rejected_negative_controls']=selftest(contract,a.root)
        if a.receipt:a.receipt.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    except (ValueError,KeyError,TypeError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
