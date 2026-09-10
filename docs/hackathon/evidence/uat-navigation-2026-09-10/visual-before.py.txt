import json,time
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
spec=spec_from_file_location('browser',Path(__file__).with_name('uat-navigation-browser.py'))
b=module_from_spec(spec);spec.loader.exec_module(b)
checks=[]
for width,height in [(1440,1000),(1024,900),(390,844)]:
 b.run('viewport',f'{width}x{height}')
 b.js('({closed:(()=>{for(const d of document.querySelectorAll("dialog details"))d.open=false;document.querySelector("dialog").scrollTop=0;return true})()})')
 b.run('click','.sm-board-picker .ant-select-selector')
 state=b.js('({dialog:!!document.querySelector("dialog[open]"),width:document.querySelector("dialog").clientWidth,scroll:document.querySelector("dialog").scrollWidth,options:[...document.querySelectorAll("[role=option]")].map(x=>({text:x.innerText,inDialog:!!x.closest("dialog"),rect:{x:x.getBoundingClientRect().x,right:x.getBoundingClientRect().right}}))})')
 assert state['dialog'] and state['width']==state['scroll'] and len(state['options'])==2 and all(x['inDialog'] for x in state['options'])
 b.run('screenshot',str(b.root/f'picker-{width}.png'))
 # Native keyboard on the focused AntD input: choose the second authorized board.
 b.run('press','End');b.run('press','Enter')
 b.run('wait','[data-testid="sm-board-grid"] .sm-block')
 state['after']=b.js('({selection:document.querySelector(".sm-board-picker .ant-select-selection-item").innerText,text:document.querySelector("[data-testid=sm-board-grid]").innerText,dialogOpen:document.querySelector("dialog").open})')
 assert '42e5261f' in state['after']['selection'] and '400' in state['after']['text'] and 'CH_RETAIL' in state['after']['text'] and state['after']['dialogOpen']
 b.js('({scroll:(document.querySelector("dialog").scrollTop=0)})')
 b.run('screenshot',str(b.root/f'board-{width}.png'))
 checks.append({'viewport':[width,height],**state})
 (b.root/'visual-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2))
 print(json.dumps({'viewport':width,'keyboardChoice':'retail','overflow':False}))
b.run('viewport','1440x1000')
