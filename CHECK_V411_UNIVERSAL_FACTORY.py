import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as q

results=[]
def ck(name,cond):
    results.append((name,bool(cond)))

registry=json.loads((ROOT/'project_builder_skills'/'toolchains.json').read_text(encoding='utf-8'))
adapters=registry['adapters']
expected_adapters=list(adapters)
for name in expected_adapters:
    ck('adapter:'+name, name in q._v34_toolchain_catalog())

skills=sorted((ROOT/'project_builder_skills').glob('*.md'))
for p in skills:
    ck('skill:'+p.stem, p.is_file() and bool(p.read_text(encoding='utf-8').strip()))

routes=[
 ('C# + Unity','Build me a C# Unity game','unity'),
 ('C++ + Unreal','Build me a C++ Unreal survival game','unreal'),
 ('C++ + Qt','Build a C++ Qt desktop app','qt_cmake'),
 ('Rust + Tauri','Create a Rust Tauri desktop app','tauri'),
 ('Kotlin + Android','Build a Kotlin Android app in Android Studio','android_gradle'),
 ('Swift + iOS','Build a native iOS app in Swift','ios_xcode'),
 ('TypeScript + Electron','Create a TypeScript Electron desktop app','electron'),
 ('C++ + xmake','Build a C++ project using xmake','xmake'),
 ('Flutter','Make a Flutter mobile app','flutter'),
 ('Go','Create a backend written in Go','go'),
 ('Zig','Build a CLI in Zig','zig'),
 ('Crystal registry adapter','Build this using Crystal', 'crystal'),
]
for label,prompt,want in routes:
    if want=='custom':
        got=q._v34_infer_toolchain('',{'language':'Crystal','toolchain_adapter':'crystal','build_command':'crystal build src/main.cr'})
    else: got=q._v34_infer_toolchain(prompt,{})
    ck('route:'+label,got==want)

ck('core:catalog-count',len(q._v34_toolchain_catalog())>=59)
ck('core:skill-count',len(skills)>=58)
ck('core:casual-build-routes',q.wants_project_zip('Build me a C++ Unreal game'))
ck('core:question-stays-chat',not q.wants_project_zip('How do I build a C++ project?'))
ck('core:file-limits',q.DEFAULT_MAX_FILES==int(os.getenv('JARVIS_QWEN_PROJECT_MAX_FILES','160')) and q.HARD_MAX_FILES>=1000)
m=q._v34_apply_toolchain_defaults('Build an Android Unity game in C#',{})
ck('core:kind-platform-separation',m.get('toolchain_adapter')=='unity' and m.get('platform')=='android' and 'game' in m.get('project_kinds',[]) and 'mobile' in m.get('project_kinds',[]))

assert len(results)>=135, f'checker definition error: {len(results)} checks'
failed=[name for name,ok in results if not ok]
for name,ok in results:
    print(('PASS ' if ok else 'FAIL ')+name)
print(f'\n{len(results)-len(failed)} / {len(results)} PASS')
if failed:
    print('FAILED:',*failed,sep='\n- ')
    raise SystemExit(1)
