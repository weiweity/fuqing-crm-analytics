from pathlib import Path
import json,subprocess,time,sys
repo=Path(__file__).resolve().parents[1]
root=Path(json.loads((repo/'.context/uat-navigation-current.json').read_text())['root'])
b='/Users/hutou/.codex/skills/gstack/browse/dist/browse'
def run(*args):
 p=subprocess.run([b,*args],cwd=repo,text=True,capture_output=True,timeout=35)
 if p.returncode:raise RuntimeError(p.stderr+p.stdout)
 return p.stdout
def js(code):return json.loads(run('js',code))
def record(name):
 value=js('({url:location.href,text:document.body.innerText,buttons:[...document.querySelectorAll("button")].map(b=>({text:b.innerText,label:b.getAttribute("aria-label"),disabled:b.disabled}))})')
 value['recorded_at_ms']=time.time_ns()//1000000
 (root/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'record':name,'url':value['url'],'chars':len(value['text'])}))
 return value
def prompt(marker):
 before=sum(1 for _ in (root/'provider-events.jsonl').open()) if (root/'provider-events.jsonl').exists() else 0
 run('fill','[data-composer-input="true"]',marker+' — 请计算2026年8月GSV，对比2025年8月；本期和对比期都用整月，保留小样。ALL 用全部销售范围；RETAIL 仅用 CH_RETAIL。只使用本地合成数据。')
 run('click','button[aria-label="Send message"]')
 end=time.monotonic()+30
 while time.monotonic()<end:
  count=sum(1 for _ in (root/'provider-events.jsonl').open()) if (root/'provider-events.jsonl').exists() else 0
  state=js('({busy:!!document.querySelector("button[aria-label=\\"Stop generating\\"]"),text:document.body.innerText})')
  if count>before and not state['busy'] and ('UAT local fixture response' in state['text'] or 'History item 160:' in state['text']):
   record(marker.lower());return
  time.sleep(.15)
 record(marker.lower()+'-timeout');raise RuntimeError('native turn did not settle')
if __name__=='__main__':
 if sys.argv[1]=='record':record(sys.argv[2])
 elif sys.argv[1]=='prompt':prompt(sys.argv[2])
