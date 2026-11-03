#!/usr/bin/env python3
"""Creates an auditable matplotlib dashboard from dora_metrics.json."""
import json,pathlib,math
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parent.parent
m=json.loads((ROOT/'output'/'dora_metrics.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
fig=plt.figure(figsize=(14,9),layout='constrained')
grid=fig.add_gridspec(3,2,height_ratios=[1.0,2.2,1.5])
fig.suptitle('Tour Request System | DORA Dashboard', fontsize=19,weight='bold')
labels=['Deployment Frequency','Lead Time (after merge)','Change Failure Rate','Recovery Time']
vals=[f"{m['deployment_frequency_per_week']}/week",f"{m['lead_time_minutes_avg']} min" if m['lead_time_minutes_avg'] is not None else 'N/A',
      f"{m['change_failure_rate_pct']}%" if m['change_failure_rate_pct'] is not None else 'N/A',
      f"{m['time_to_restore_minutes_avg']} min" if m['time_to_restore_minutes_avg'] is not None else 'N/A']
ax=fig.add_subplot(grid[0,:]);ax.set_xlim(0,4);ax.set_ylim(0,1);ax.axis('off')
for i,(name,val) in enumerate(zip(labels,vals)):
    ax.text(i+.08,.65,name,fontsize=11,weight='bold')
    ax.text(i+.08,.25,val,fontsize=20,weight='bold')
    if i:ax.axvline(i,linewidth=.8,alpha=.3)
ax=fig.add_subplot(grid[1,0]); deps=m.get('deployments',[])
if deps:
    names=[r['deployed_at'][:16].replace('T','\n') for r in deps]
    y=[1 if r['result']=='success' else -1 for r in deps]
    ax.bar(range(len(y)),y)
    ax.set_xticks(range(len(y)),names,rotation=35,ha='right')
    ax.set_ylim(-1.5,1.5);ax.set_ylabel('Success (+1), Failed (-1)')
else: ax.text(.5,.5,'No deployment records',ha='center',va='center',transform=ax.transAxes)
ax.set_title('Deployments (verified records)')
ax=fig.add_subplot(grid[1,1]); l=m.get('lead_time_details',[])
if l:
    ax.bar(range(len(l)),[x['minutes'] for x in l]);ax.set_xticks(range(len(l)),[x['source_sha'][:7] for x in l]);ax.set_ylabel('Minutes')
else:ax.text(.5,.5,'No commit/deploy pairs',ha='center',va='center',transform=ax.transAxes)
ax.set_title('Commit → live (deployed SHA)')
ax=fig.add_subplot(grid[2,:]);ax.axis('off')
notes=[f"Window: {m['window_start']} to {m['window_end']}",
       f"Deployments: {m['successful_deployments']} success / {m['failed_attempts']} failed attempts",
       f"Incident log: {m['incident_count']} incidents; {m['repair_hours']} h recorded repairs",
       'CFR: '+m['cfr_coverage'],
       'CI runs are not counted as deployments. Recovery is N/A without verified incidents.',
       'Interpretation: baseline is too small to assign a reliable DORA performance level.']
for j,s in enumerate(notes):ax.text(.02,.94-j*.15,'• '+s,va='top',fontsize=10,transform=ax.transAxes)
fig.savefig(ROOT/'output'/'dora_dashboard.png',dpi=160,bbox_inches='tight')
print('Dashboard:',ROOT/'output'/'dora_dashboard.png')
