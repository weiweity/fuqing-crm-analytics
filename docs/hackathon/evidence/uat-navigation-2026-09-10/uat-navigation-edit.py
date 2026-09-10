import json,time
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('browser',Path(__file__).with_name('uat-navigation-browser.py'))
b=module_from_spec(spec);spec.loader.exec_module(b)
events=[]
def action(*args):
 start=time.monotonic();value=b.run(*args)
 events.append({'command':list(args),'seconds':round(time.monotonic()-start,3),'output':value})
 (b.root/'edit-actions.json').write_text(json.dumps(events,ensure_ascii=False,indent=2))
 return value
def settled():
 end=time.monotonic()+10
 while time.monotonic()<end:
  state=b.js('({save:document.querySelector("[data-testid=sm-board-save]")?.disabled,hint:document.querySelector("[data-testid=sm-preview-hint]")?.innerText})')
  if state.get('save') is False:return
  time.sleep(.1)
 raise RuntimeError('preview missing')
def edit(selector,key,name):
 action('scroll',selector)
 action('click','[data-testid="sm-scope-block"]')
 action('press',key)
 settled();b.record(name+'-preview')
 assert b.js('({disabled:document.querySelector(".sm-board-picker input[role=combobox]").disabled})')['disabled']
 action('click','[data-testid="sm-board-save"]')
 end=time.monotonic()+10
 while time.monotonic()<end:
  if not b.js('({pending:!!document.querySelector("[data-testid=sm-preview-hint]")})')['pending']:break
  time.sleep(.1)
 else:raise RuntimeError('save pending')
 b.record(name+'-saved')
edit('.sm-drag-handle','Alt+ArrowRight','keyboard-move')
action('reload')
action('click','[data-testid="analytics-b0-open"]')
action('wait','[data-testid="sm-board-grid"] .sm-block')
b.record('edited-board-reloaded')
print(json.dumps(b.js('({editor:document.querySelector("[data-testid=sm-board-editor]").innerText,style:document.querySelector(".sm-block").getAttribute("style")})'),ensure_ascii=False))
