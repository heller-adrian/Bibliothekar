"""Explicit source-bound QA chain; no result is relabelled onto another commit."""
from pathlib import Path
import json,os,subprocess
import xml.etree.ElementTree as ET
import core as c
import oci


def passing_xml(path,count=None,expected_nodes=None):
    cases=list(ET.parse(path).iter('testcase'))
    assert cases and all(all(t.find(k) is None for k in ('failure','error','skipped')) for t in cases),'Nonpassing JUnit: '+str(path)
    actual={(t.get('classname'),t.get('name')) for t in cases}
    assert len(actual)==len(cases),'Duplicate JUnit nodes'
    if count is not None:assert len(cases)==count,'Unexpected JUnit count'
    if expected_nodes is not None:
        expected=set()
        for node in expected_nodes:
            parts=node.split('::');module=parts[0][:-3].replace('/','.')
            expected.add((module+('.'+'.'.join(parts[1:-1]) if len(parts)>2 else ''),parts[-1]))
        assert actual==expected and len(cases)==len(expected_nodes),'JUnit node identity differs from partition manifest'
    return len(cases)


def checked_delta(base,build,approved):
    changed=c.git('diff','--name-only',base,build,'--','app').splitlines()
    assert set(changed)==set(approved),'Unreviewed app delta'
    for path,entry in approved.items():
        old=subprocess.run(['git','rev-parse',base+':'+path],capture_output=True,text=True)
        assert (old.stdout.strip() if old.returncode==0 else None)==entry['before']
        assert c.git('rev-parse',build+':'+path)==entry['after'],'Reviewed file bytes changed'
    assert not c.git('diff','--name-only',base,build,'--','Dockerfile','requirements.txt','requirements-rc.constraints.txt','app/migrations'),'Build inputs/schema changed'


def audit_source(approval):
    build=approval['source'];backend=approval['backend_source']
    assert approval['coverage_mode']=='reviewed_source_delta_with_final_image_gates'
    checked_delta(backend,build,approval['reviewed_backend_delta'])
    checked_delta(approval['artifacts']['container']['source'],build,approval['reviewed_container_delta'])
    assert c.git('diff','--name-only',backend,build,'--','tests').splitlines()==approval['backend_test_delta']
    assert approval['backend_test_delta']==['tests/backend/test_rc14_legacy_prejournal_verifier.py']
    # All exported UI/renderers are byte-identical to the independently accepted
    # full 191-case browser job. Live image/browser cases are repeated separately.
    front=approval['artifacts']['frontend']['source']
    ui=['qa/rc13/export_ui.py','qa/rc14/export_ui.py','qa/rc13/browser.cjs','qa/rc14/browser.cjs',
        'app/events_ui.py','app/workspace_ui.py','app/transfer_ui.py','app/ui_i18n.py','app/ui_shell.py','app/storage_warning_ui.py']
    assert not c.git('diff','--name-only',front,build,'--',*ui),'Frontend proof does not cover current templates'
    for prior in (backend,front,approval['artifacts']['container']['source']):c.git('merge-base','--is-ancestor',prior,build)


def verify_backend(folder,approval):
    summary=json.loads((folder/'summary.json').read_text());source=approval['backend_source']
    assert summary['status']=='PASS' and summary['source']==source and summary['complete'] is True
    assert summary['collected']==summary['selected_once']==approval['backend_nodes']==2579 and len(summary['parts'])==8
    seen=set();collected=None
    for index,part in enumerate(summary['parts']):
        assert part['partition']==index and part['returncode']==0
        manifest=json.loads((folder/str(index)/'rc13-partition.json').read_text())
        if collected is None:collected=manifest['all_nodes']
        assert collected==manifest['all_nodes'] and not seen.intersection(manifest['selected_nodes'])
        count=passing_xml(folder/str(index)/'f14-qa/targets/results/result.xml',expected_nodes=manifest['selected_nodes'])
        assert part['selected']==count and part['results']=={'tests':count,'failures':0,'errors':0,'skipped':0}
        seen.update(manifest['selected_nodes'])
    assert len(seen)==2579 and seen==set(collected)
    for name,count in [('backend_unretested.json',147),('backend_recovery_contracts.json',15)]:
        nodes=json.loads(c.git('show',approval['source']+':qa/pre5/'+name))
        assert len(nodes)==count and set(nodes)<=seen,'Historical gate node missing from full backend'
    return len(seen)


def fetch(work,approval,qualify_runtime_folder):
    work=Path(work);assets=work/'release-assets';assets.mkdir(exist_ok=False)
    runs={};folders={}
    for role,item in approval['artifacts'].items():
        run_id=item['run']
        if run_id not in runs:
            run=c.github(f'repos/{c.REPO}/actions/runs/{run_id}')
            jobs=c.github(f'repos/{c.REPO}/actions/runs/{run_id}/jobs?per_page=100')['jobs']
            assert run['status']=='completed' and run['run_attempt']==1 and run['path']=='.github/workflows/qa-pre5-operation-recovery.yml'
            runs[run_id]=(run,jobs)
        run,jobs=runs[run_id]
        assert run['head_sha']==item['source'] and run['conclusion']==item['run_conclusion']
        job,=[j for j in jobs if j['name']==item['job']]
        assert job['status']=='completed' and job['conclusion']=='success'
        assert {'self-hosted','Linux','X64','bibliothekar-safe'}<=set(job['labels'])
        steps={s['name']:s['conclusion'] for s in job['steps']}
        assert all(steps.get(name)=='success' for name in item['required_steps']),'Required gate was not executed'
        meta=c.github(f"repos/{c.REPO}/actions/artifacts/{item['id']}")
        assert not meta['expired'] and meta['digest']==item['digest'] and meta['name']==item['name']
        assert meta['workflow_run']['id']==run_id and meta['workflow_run']['head_sha']==item['source']
        raw,_=c.http(meta['archive_download_url'],{'Authorization':'Bearer '+os.environ['GH_TOKEN']})
        assert oci.digest(raw)==item['digest'],'Artifact ZIP changed'
        (assets/('pre5-'+role+'-accepted.zip')).write_bytes(raw)
        folder=work/('accepted-'+role);c.safe_extract(raw,folder);folders[role]=folder
    count=verify_backend(folders['backend'],approval)
    for role,files in approval['pytest'].items():
        for name,total in files.items():passing_xml(folders[role]/(name+'.xml'),total)
    for name,total in approval['frontend'].items():
        data=json.loads((folders['frontend']/name/'results.json').read_text())
        assert data['status']=='PASS' and len(data['cases'])==total and all(v['status']=='PASS' for v in data['cases'])
    qualify_runtime_folder(folders['container'],approval['artifacts']['container']['source'])
    iphone=json.loads((folders['iphone']/'pre-evidence.json').read_text())
    assert iphone['commit']==approval['source'] and iphone['status']=='PASS' and iphone['corrected_files']==14
    assert iphone['same_reservation_preserved_until_retry'] and iphone['origin_preserved'] and iphone['readonly_bytes_preserved']
    c.dump(assets/'verified-accepted-QA.json',{'status':'PASS','release_source':approval['source'],
        'coverage_mode':approval['coverage_mode'],'backend_nodes':count,'backend_source':approval['backend_source'],
        'stages':approval['artifacts'],'pytest':approval['pytest'],'frontend':approval['frontend'],
        'native_truenas':'NOT_RUN','release_image_checks':'REQUIRED_BEFORE_ANY_RELEASE_WRITE'})
    for run_id,(run,jobs) in runs.items():
        c.dump(assets/('accepted-run-'+str(run_id)+'.json'),{'run':run,'jobs':jobs})
