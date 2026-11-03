#!/usr/bin/env python3
"""Tour Request System: auditable DORA collector, GitHub REST API + Render CSV.
No artificial metrics. CI runs are NOT deployments.
"""
import argparse, csv, datetime as dt, json, os, pathlib, statistics, urllib.error, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UTC = dt.timezone.utc

def parse_date(v):
    if not v or not v.strip(): return None
    v=v.strip().replace('Z','+00:00')
    obj=dt.datetime.fromisoformat(v)
    if obj.tzinfo is None: raise ValueError('Timezone required: '+v)
    return obj.astimezone(UTC)

def iso(v): return v.isoformat().replace('+00:00','Z') if v else None

def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def api(url, token):
    headers={'Accept':'application/vnd.github+json','User-Agent':'tour-request-system-lab10','X-GitHub-Api-Version':'2022-11-28'}
    if token: headers['Authorization']='Bearer '+token
    r=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(r,timeout=20) as response: return json.load(response)

def paged(url,token,limit=5):
    out=[]
    for page in range(1,limit+1):
        sep='&' if '?' in url else '?'
        a=api(url+f'{sep}per_page=100&page={page}',token)
        if not isinstance(a,list): raise ValueError('Expected list from API')
        out.extend(a)
        if len(a)<100: break
    return out

def fetch_github(repo,token):
    base='https://api.github.com/repos/'+repo
    deployments=[]; runs=[]; commits={}
    try:
        raw=paged(base+'/deployments',token)
        for dep in raw:
            dep_id=dep['id']
            statuses=paged(base+f'/deployments/{dep_id}/statuses',token,limit=2)
            # Most recent final status; transitional states are not counted.
            status=next((s for s in statuses if s.get('state') in ('success','failure','error')),None)
            if not status: continue
            deployments.append({'id':'github:'+str(dep_id),'source':'github','sha':dep.get('sha',''),
                'deployed_at':status.get('created_at',''), 'result':'success' if status['state']=='success' else 'failure',
                'incident_id':'','note':'GitHub Deployment API'})
    except (urllib.error.HTTPError,urllib.error.URLError) as exc:
        print('WARNING: GitHub deployments unavailable:',exc)
    try:
        data=api(base+'/actions/runs?per_page=100',token)
        runs=[{'id':str(x.get('id')),'created_at':x.get('created_at'),'conclusion':x.get('conclusion'),
               'sha':x.get('head_sha'),'name':x.get('name')} for x in data.get('workflow_runs',[])]
    except (urllib.error.HTTPError,urllib.error.URLError) as exc:
        print('WARNING: GitHub Actions unavailable:',exc)
    return deployments,runs

def get_commit(repo, sha, token, cache):
    if not sha: return None
    if sha in cache: return cache[sha]
    try:
        raw=api(f'https://api.github.com/repos/{repo}/commits/{urllib.parse.quote(sha)}',token)
        v=raw['commit']['committer']['date']
        cache[sha]=v; return v
    except (urllib.error.HTTPError,urllib.error.URLError,KeyError) as exc:
        print('WARNING: commit unavailable',sha,exc); cache[sha]=None;return None

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo',default='bonesxm/tour-request-system')
    p.add_argument('--offline',action='store_true',help='Do not query GitHub; use verified CSV records only')
    p.add_argument('--window-start',default='2026-10-28T00:00:00+05:00')
    p.add_argument('--window-end',help='ISO datetime with timezone; default now')
    args=p.parse_args()
    start=parse_date(args.window_start); end=parse_date(args.window_end) if args.window_end else dt.datetime.now(UTC)
    if end<=start: raise SystemExit('Window end must be after start')
    token=os.environ.get('GH_TOKEN','')
    github_deps,runs=([],[]) if args.offline else fetch_github(args.repo,token)
    manual=read_csv(ROOT/'data'/'deployments.csv')
    all_deps=[]
    for row in manual:
        if not row.get('deployed_at') or not row.get('result'): continue
        all_deps.append({'id':'render:'+row['id'],'source':'render','sha':row.get('sha',''),
            'deployed_at':row['deployed_at'],'result':row['result'].lower().strip(),
            'incident_id':row.get('incident_id',''),'note':row.get('note',''),
            'source_commit_at':row.get('source_commit_at','')})
    all_deps.extend(github_deps)
    # No heuristic dedup across providers: Render deploy and GitHub deployment can be distinct events.
    # When GitHub mirrors Render, manually remove the duplicate Render record or record just one authoritative stream.
    selected=sorted([x for x in all_deps if start<=parse_date(x['deployed_at'])<end],key=lambda x:x['deployed_at'])
    commits={}
    for row in selected:
        if not row.get('source_commit_at') and not args.offline:
            row['source_commit_at']=get_commit(args.repo,row.get('sha'),token,commits) or ''
    successes=[x for x in selected if x['result']=='success']
    failures=[x for x in selected if x['result'] in ('failure','error')]
    lead=[]; lead_rows=[]
    for x in successes:
        orig=parse_date(x.get('source_commit_at',''))
        if orig:
            seconds=(parse_date(x['deployed_at'])-orig).total_seconds()
            if seconds>=0:
                lead.append(seconds/60)
                lead_rows.append({'deployment_id':x['id'],'source_sha':x['sha'],'minutes':round(seconds/60,2)})
    incidents=read_csv(ROOT/'data'/'incidents.csv')
    restoration=[]; repair_hours=0.;incident_rows=[]
    for inc in incidents:
        start_inc=parse_date(inc.get('started_at',''))
        if not start_inc or not (start<=start_inc<end): continue
        restored=parse_date(inc.get('restored_at',''))
        minute=(restored-start_inc).total_seconds()/60 if restored else None
        if minute is not None and minute<0: raise ValueError('Restored before incident started')
        if minute is not None: restoration.append(minute)
        h=float(inc.get('repair_hours') or 0)
        repair_hours+=h
        incident_rows.append({'incident_id':inc.get('incident_id'),'deployment_id':inc.get('deployment_id'),
            'recovery_minutes':round(minute,2) if minute is not None else None,'repair_hours':h})
    # DORA CFR: only deployments known to cause customer-impacting incidents, not raw CI failures.
    failed_change_ids={x['deployment_id'].strip() for x in incident_rows if x['deployment_id']}
    if failed_change_ids:
        bad_deploys=sum(1 for x in successes if x['id'] in failed_change_ids)
        cfr=round(100*bad_deploys/len(successes),2) if successes else None
        cfr_coverage='incident-linked'
    else:
        cfr=None
        cfr_coverage='not measured: no confirmed deploy-to-incident classification'
    days=(end-start).total_seconds()/86400
    metrics={'repo':args.repo,'window_start':iso(start),'window_end':iso(end),
        'successful_deployments':len(successes),'failed_attempts':len(failures),
        'deployment_frequency_per_week':round(len(successes)/days*7,3),
        'lead_time_minutes_avg':round(statistics.mean(lead),2) if lead else None,
        'lead_time_samples':len(lead), 'change_failure_rate_pct':cfr,'cfr_coverage':cfr_coverage,
        'time_to_restore_minutes_avg':round(statistics.mean(restoration),2) if restoration else None,
        'recovery_samples':len(restoration),'repair_hours':round(repair_hours,2),
        'incident_count':len(incident_rows),'ci_runs_not_deployments':len(runs),
        'lead_time_details':lead_rows,'incidents':incident_rows,'deployments':selected,
        'notes':['GitHub Actions runs are NOT deployments.',
                 'Only successful production/staging deploys count for frequency.',
                 'CFR requires incident linkage; no evidence is not equivalent to 0%.',
                 'Repair hours are logged manually; 0 hours without incidents means no recorded repair.',
                 'Lead time based on selected deployed SHA (merge commit where applicable), not necessarily first feature commit.',
                 'For full DORA change lead time link PR first commit to deploy separately.']}
    out=ROOT/'output';out.mkdir(exist_ok=True)
    (out/'dora_metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'deployments_analyzed.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['id','source','sha','deployed_at','result','incident_id','note','source_commit_at'],extrasaction='ignore')
        w.writeheader();w.writerows(selected)
    print('Report:',out/'dora_metrics.json')
    for k in ['successful_deployments','deployment_frequency_per_week','lead_time_minutes_avg','change_failure_rate_pct','time_to_restore_minutes_avg','repair_hours','ci_runs_not_deployments']:
        print(f'{k}: {metrics[k] if metrics[k] is not None else "N/A (not measured)"}')

if __name__=='__main__': main()
