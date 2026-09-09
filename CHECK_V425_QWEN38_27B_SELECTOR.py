from pathlib import Path
import importlib.util
import re

ROOT = Path(__file__).resolve().parent
checks=[]
def check(name, cond, detail=''):
    ok=bool(cond); checks.append(ok)
    print(('PASS' if ok else 'FAIL')+': '+name+(f' -- {detail}' if detail else ''))

spec=importlib.util.spec_from_file_location('qmm_v425', ROOT/'qwen_model_manager.py')
q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)

check('new profile registered', '27b38q2' in q.MODEL_PROFILES)
check('new profile points at exact GGUF', str(q.MODEL_PROFILES['27b38q2']['path']).endswith('Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q2_K_P.gguf'), q.MODEL_PROFILES['27b38q2']['path'])
check('Hugging Face repo metadata registered', q.MODEL_PROFILES['27b38q2'].get('hf_repo') == 'HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF')
check('dropdown alias maps to new profile', q.normalize_profile('qwen38q2') == '27b38q2')
check('specific 27B aggressive alias maps correctly', q.normalize_profile('hauhau27q2') == '27b38q2')
check('generic aggressive alias still preserves 9B default profile', q.normalize_profile('aggressive') == '9b35')
check('legacy 27B profile preserved', q.normalize_profile('27b') == '27b' and '27b' in q.MODEL_PROFILES)
check('V42.6 supersedes selector default with AUTO', q.selected_profile() == 'auto', q.selected_profile())

html=(ROOT/'ui/index.html').read_text(encoding='utf-8')
ix9=html.find('value="qwen35"')
ixnew=html.find('value="qwen38q2"')
ixold=html.find('value="qwen"')
check('new option exists in dropdown', ixnew >= 0)
check('new option is directly after 9B and before legacy 27B', 0 <= ix9 < ixnew < ixold, (ix9,ixnew,ixold))
check('9B remains available but is no longer selected by default', ix9 >= 0 and re.search(r'<option value="qwen35" selected>', html) is None)
check('new 27B remains a direct manual option while AUTO owns default', re.search(r'<option value="qwen38q2" selected>', html) is None and re.search(r'<option value="auto" selected>', html) is not None)

app=(ROOT/'ui/app.js').read_text(encoding='utf-8')
check('frontend switch list includes qwen38q2', "'qwen38q2'" in app)
check('frontend maps qwen38q2 to 27b38q2', "value==='qwen38q2'?'27b38q2'" in app)
check('send path maps new option to qwen provider', "['qwen8b','qwen35','qwen38q2']" in app)

dash=(ROOT/'ui/dashboard.py').read_text(encoding='utf-8')
check('dashboard command API accepts new profile', "'27b38q2'" in dash)
check('dashboard active label recognizes aggressive Q2', 'Qwen3.8-27B HauhauCS Aggressive Q2_K_P' in dash)

jarvis=(ROOT/'jarvis.py').read_text(encoding='utf-8')
check('Jarvis switch error routing recognizes new profile', '"27b38q2"' in jarvis)

lqp=(ROOT/'local_qwen_project.py').read_text(encoding='utf-8')
check('project builder has Qwen3.8 family', "return 'qwen38'" in lqp or 'return "qwen38"' in lqp)
check('Qwen3.8 thinking sampler is 1.0/0.95 by default', 'QWEN38_THINK_TEMP' in lqp and '"1.0"' in lqp and 'QWEN38_THINK_TOP_P' in lqp)
check('Qwen3.8 fallback now targets native 262K context', 'QWEN38_CONTEXT_FALLBACK' in lqp and '"262144"' in lqp)

mp=(ROOT/'multi_provider.py').read_text(encoding='utf-8')
check('provider layer detects Qwen3.8 family', 'return "qwen38"' in mp)
check('provider layer uses Qwen3.8 official thinking defaults', 'elif family == "qwen38"' in mp and 'default_temperature = 1.0' in mp)

check('optional downloader included', (ROOT/'DOWNLOAD_QWEN38_27B_AGGRESSIVE_Q2_K_P.bat').is_file())
check('V42.5 selector README included', (ROOT/'V42_5_QWEN38_27B_SELECTOR_README.txt').is_file())

passed=sum(checks); total=len(checks)
print(f'RESULT: {passed}/{total} PASS')
raise SystemExit(0 if passed==total else 1)
