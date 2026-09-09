from pathlib import Path
import json
import qwen_model_manager as q
import local_qwen_project as l

ROOT=Path(__file__).resolve().parent
results=[]
def check(name, cond, detail=''):
    results.append((name,bool(cond),str(detail)))
    print(('PASS' if cond else 'FAIL')+': '+name+((' :: '+str(detail)) if detail else ''))

# Exact model identity and AUTO pool.
check('AUTO worker is current Qwen3.5 9B', l.V426_AUTO_WORKER=='9b35')
check('AUTO specialist is NEW aggressive Qwen3.8 27B', l.V426_AUTO_SPECIALIST=='27b38q2')
check('new specialist points to requested exact GGUF', str(q.MODEL_PROFILES['27b38q2']['path']).endswith('Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf'), q.MODEL_PROFILES['27b38q2']['path'])
check('legacy 27B is a distinct manual profile', l.V426_AUTO_SPECIALIST!='27b' and 'OBLITERATED' in q.MODEL_PROFILES['27b']['label'])

# AUTO stage routing.
l.configure_project_qwen_routing('auto')
target,reason=l._v426_route_for_call('V42.6 compiling frozen requirements','plan','small')
check('AUTO requirements uses new 27B specialist',target=='27b38q2',(target,reason))
target,reason=l._v426_route_for_call('V42.6 architecture collision repair 1/2','repair','small')
check('AUTO architecture collision uses new 27B specialist',target=='27b38q2',(target,reason))
target,reason=l._v426_route_for_call('Generating src/widget.tsx','generate','small')
check('AUTO routine file generation uses 9B',target=='9b35',(target,reason))
target1,_=l._v426_route_for_call('patch repair 1/2: src/widget.tsx','repair','small')
target2,reason2=l._v426_route_for_call('patch repair 2/2: src/widget.tsx','repair','small')
check('AUTO first ordinary leaf repair stays 9B',target1=='9b35',target1)
check('fast routing keeps ordinary repeated leaf repair on 9B',target2=='9b35',(target2,reason2))
target,reason=l._v426_route_for_call('V42.6 diagnosing ambiguous runtime failure','chat','small')
check('fast routing keeps chat calls on 9B',target=='9b35',(target,reason))
target,reason=l._v426_route_for_call('V42.6 subsystem reconciliation','repair','small')
check('AUTO subsystem reconciliation uses new 27B',target=='27b38q2',(target,reason))
target,reason=l._v426_route_for_call('V42.6 global convergence','audit','small')
check('AUTO global convergence uses new 27B',target=='27b38q2',(target,reason))

# Manual dropdown choices must be strict locks regardless of stage difficulty.
for mode in ('9b35','27b38q2','27b','8b'):
    l.configure_project_qwen_routing(mode)
    a=l._v426_route_for_call('V42.6 architecture collision subsystem global convergence','plan','x')[0]
    b=l._v426_route_for_call('Generating ordinary file','generate','x')[0]
    check(f'manual {mode} remains strict for hard and easy calls',a==mode and b==mode,(a,b))

# HTML must default to AUTO and put the exact new specialist below 9B.
html=(ROOT/'ui'/'index.html').read_text(encoding='utf-8')
check('AUTO HYBRID is selected in dropdown','<option value="auto" selected>AUTO HYBRID' in html)
check('9B is not HTML-selected by default','<option value="qwen35" selected>' not in html)
pos9=html.find('value="qwen35"'); posnew=html.find('value="qwen38q2"'); posold=html.find('value="qwen"')
check('new 27B appears directly after 9B and before old 27B',0 <= pos9 < posnew < posold,(pos9,posnew,posold))
check('old 27B explicitly marked manual legacy','OBLITERATED Q4_K_M (MANUAL STRICT / LEGACY)' in html)

js=(ROOT/'ui'/'app.js').read_text(encoding='utf-8')
check('selection storage key migrated so old 9B choice does not override new AUTO default','jarvis.localQwenSelection.v426' in js)
check('AUTO toast describes hybrid pair','AUTO HYBRID selected' in js and '27B Q2_K_P' in js)

jarvis=(ROOT/'jarvis.py').read_text(encoding='utf-8')
check('project worker prepares hybrid routing','prepare_project_qwen_routing(' in jarvis)
check('project worker clears routing state','clear_project_qwen_routing()' in jarvis)
check('AUTO project provider is labeled hybrid','qwen-auto-hybrid' in jarvis)
check('AUTO standby preserves hybrid selection during fallback','ensure_qwen_profile("auto", persist_selection=False)' in jarvis)

manager=(ROOT/'qwen_model_manager.py').read_text(encoding='utf-8')
check('temporary hybrid switches can avoid changing dropdown selection','persist_selection: bool = True' in manager and 'if persist_selection:' in manager)
check('AUTO resolver excludes legacy 27B and 8B fallback','override in {"9b35", "27b38q2"}' in manager and 'return "27b38q2"' in manager)
check('missing selection defaults to AUTO','return "auto"' in manager[manager.find('def selected_profile'):manager.find('def save_selected_profile')])

l.clear_project_qwen_routing()
passed=sum(1 for _,ok,_ in results if ok)
print(f'\nV42.6 hybrid router: {passed}/{len(results)} PASS')
if passed != len(results): raise SystemExit(1)
