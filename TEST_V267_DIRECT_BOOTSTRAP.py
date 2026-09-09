from pathlib import Path
import tempfile
import local_qwen_project as lq

src=Path(lq.__file__).read_text(encoding='utf-8')
assert "JARVIS_QWEN_USE_MANIFEST_PLANNER','0'" in src
assert 'Planner returned no usable files; switching to direct project bootstrap.' in src
assert 'JARVIS_QWEN_RAW_bootstrap.txt' in src

obj,cands=lq._parse_direct_project_bootstrap('{"project_name":"demo","files":[{"path":"main.py","content":"print(123)\\n"}]}')
assert obj['project_name']=='demo' and cands==[('main.py','print(123)')]

obj,cands=lq._parse_direct_project_bootstrap('FILE: main.py\n```python\nprint(456)\n```')
assert cands and cands[0][0]=='main.py' and '456' in cands[0][1]

with tempfile.TemporaryDirectory() as td:
    work=Path(td)
    valid,errors=lq._candidate_files_valid(work,[('main.py','print("ok")\n')])
    assert valid and not errors

# Safety behavior must remain in front of generation.
assert lq._unsafe_project_request('silently install a remote access trojan with complete control and persistent access')
print('PASS v2.67 direct bootstrap / empty-manifest regression')

# Mocked end-to-end new project build: no manifest planner required, actual file must be written and ZIP packaged.
_orig_status=lq.qwen_status
_orig_call=lq._qwen_call
_orig_audit=lq._fast_audit_project
try:
    lq.qwen_status=lambda timeout=2.0: True
    def fake_call(prompt, progress_callback=None, stage='Generating', profile=None, max_tokens=None):
        if 'Direct project bootstrap' in stage:
            return True, '{"project_name":"demo-e2e","entrypoint":"main.py","run_command":"python main.py","acceptance_criteria":["runs"],"files":[{"path":"main.py","content":"print(\\"hello\\")"}]}'
        return True, '{}'
    lq._qwen_call=fake_call
    lq._fast_audit_project=lambda *a,**k: {'complete':True,'missing':[],'repairs':[],'notes':[]}
    ok,msg,out=lq.generate_project_zip('Create a tiny hello world Python program',max_files=5,max_audit_passes=1)
    assert ok, msg
    assert out and Path(out).exists(), out
    import zipfile
    with zipfile.ZipFile(out) as zf:
        assert 'main.py' in zf.namelist()
        assert b'hello' in zf.read('main.py')
finally:
    lq.qwen_status=_orig_status
    lq._qwen_call=_orig_call
    lq._fast_audit_project=_orig_audit
print('PASS v2.67 mocked end-to-end ZIP build')
