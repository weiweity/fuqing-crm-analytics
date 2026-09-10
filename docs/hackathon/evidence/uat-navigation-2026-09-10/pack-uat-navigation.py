from pathlib import Path
import hashlib,json,shutil,sqlite3,subprocess,time
repo=Path(__file__).resolve().parents[1];root=repo/'.context/uat-navigation-xlnfdit6'
out=repo/'docs/hackathon/evidence/uat-navigation-2026-09-10';out.mkdir(parents=True,exist_ok=True)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(db,sql):
 with sqlite3.connect((root/'state'/db).as_uri()+'?mode=ro',uri=True) as c:return c.execute(sql).fetchall()
results=[json.loads(row[0]) for row in rows('diagnosis/diagnosis_results.sqlite3','select result_json from results')]
assert len(results)==2
byid={r['result_id']:r for r in results}
assert sorted((r['facts']['current']['gsv'],r['facts']['comparison']['gsv']) for r in results)==[(400,300),(410,305)]
boards=[]
for bid,version,title,blocks in rows('assets/competition_assets.sqlite3','select board_id,version,title,blocks_json from boards order by board_id,version'):
 blocks=json.loads(blocks)
 assert len(blocks)==1 and blocks[0]['evidence_digest']==byid[blocks[0]['result_id']]['evidence_digest']
 boards.append({'board_id':bid,'version':version,'title':title,'blocks':blocks})
assert len({b['board_id'] for b in boards})==2
assert [b['blocks'][0]['layout'] for b in boards if b['board_id'].endswith('a863d838')]==[{'h':4,'w':6,'x':0,'y':0},{'h':4,'w':5,'x':0,'y':0},{'h':4,'w':5,'x':1,'y':0}]
drafts=[json.loads(row[0]) for row in rows('audience/competition-audience.sqlite','select payload_json from drafts order by version')]
assert len(drafts)==2 and [d['version'] for d in drafts]==[1,2] and drafts[0]['draft_id']==drafts[1]['draft_id']
assert all(d['auto_send'] is False for d in drafts)
candidates=[json.loads(row[0]) for row in rows('audience/competition-audience.sqlite','select payload_json from candidates')]
assert len(candidates)==1 and candidates[0]['unique_count']==6
providers=list(map(json.loads,(root/'provider-events.jsonl').read_text().splitlines()))
assert len(providers)==5 and not any(p.get('event')=='PROVIDER_ERROR' for p in providers)
tools=[json.loads(t['content']) for p in providers for t in p['toolResults']]
assert len(tools)==2 and all(t['result']['evidence_digest']==byid[t['result']['result_id']]['evidence_digest'] for t in tools)
sourcefiles=subprocess.check_output(['git','diff','--name-only'],cwd=repo,text=True).splitlines()
sources={f:digest(repo/f) for f in sourcefiles if f.startswith('dsh-plugins/')}
for f in ['provider-events.jsonl','visual-checks.json','edit-actions.json','edit-actions-before.json','keyboard-focus-before.log','keyboard-select-before.log','keyboard-select-timing-before.log','pointer-attempt.py','visual-before.py','empty-final.json','uat_all.json','uat_retail.json','batch-created.json','board-all-evidence.json','keyboard-resize-preview.json','keyboard-resize-saved.json','keyboard-move-preview.json','keyboard-move-saved.json','edited-board-reloaded.json','draft-v1.json','draft-v2.json','draft-v2-reopened.json','detached-reading.json']:
 shutil.copy2(root/f,out/f)
for f in ['uat-navigation-provider.mjs','uat-navigation-workspace.mjs','uat-navigation-browser.py','uat-navigation-edit.py','uat-navigation-visual.py','pack-uat-navigation.py']:
 shutil.copy2(repo/'.context'/f,out/f)
screens=out/'screenshots';screens.mkdir(exist_ok=True)
for f in ['uat-entry-before.png','uat-board-choice-before.png','empty-before-controls.png','empty-final.png','board-all-evidence.png','picker-1440.png','picker-1024.png','picker-390.png','board-1440.png','board-1024.png','board-390.png']:
 if (root/f).exists():shutil.copy2(root/f,screens/f)
for name in ['uat-entry-before-test','uat-navigation-pipeline','uat-navigation-final-pipeline','uat-navigation-evidence-dom','uat-navigation-edit','uat-navigation-visual']:
 shutil.copy2(repo/'.context'/(name+'.log'),out/(name+'.log'))
for port in [4328,18084,63359]:
 assert not subprocess.run(['lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-t'],text=True,capture_output=True).stdout.strip()
report={'base_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),'source_sha256':sources,'browser_client_sha256':digest(root/'plugin-final/lib/client.js'),'upstream':'d347e703908d0406b7a7ef80e3a0e594d86b2215','fixture_root':str(root),'provider':'local deterministic fixture; no paid model calls; not T13','provider_requests':len(providers),'results':results,'boards':boards,'drafts':drafts,'candidates':candidates,'post_process_exit_reads':True,'owned_ports_stopped':[4328,18084,63359],'user_candidate_unchanged':'4325 PID73577 / 18083 PID23661','pipeline':'PASS final full B0 including clean rebuild; Python480 passed; see exact log','focused_tests':'45 passed before final pipeline','pointer_drag':'NOT_RUN: browser CDP allowlist rejected Input.dispatchMouseEvent; no bypass. Keyboard resize/move independently verified.','visual':'1440/1024/390 selector keyboard and overflow checks PASS; screenshots inspected; technical titles and crowded first screen still PARTIAL','uat':'engineering partial only; no user signoff, no full multi-step diagnosis, no diagnosis-derived cohort','created_at_ms':time.time_ns()//1000000}
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(out/'review.json').write_text(json.dumps({'mode':'manual /review checkpoint; no OCR or subagents','base':report['base_head'],'source_sha256':sources,'reviewed':['authorized list before restoring preference; every selection reloads board through current transport','pending edits, loading, restore and in-flight target guards','no selection-listener disposal during switch; explicit reset of board-local UI','B0 explicit navigation retained; competition mount remains open-gated','saved condition/evidence derives from persisted result; no ratio or date rewriting','batch receipt identity retained; list refresh includes both created boards','final full B0 PASS and real browser two-board selection/save/reopen'], 'actionable_findings':[],'limits':'Manual scoped review, not an independent full repository/security audit.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'evidence':str(out),'boards':len({b['board_id'] for b in boards}),'results':len(results),'draft_versions':len(drafts),'source_files':len(sources)},ensure_ascii=False))
