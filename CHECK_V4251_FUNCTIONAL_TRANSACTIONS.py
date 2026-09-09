"""Offline regression tests. Model replies are fixtures, not a live Qwen run."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import local_qwen_project as j
import jarvis_v4251_repair as v


def write(root,rel,text):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)


def response(edits):
    return True,json.dumps({'edits':[{'file':rel,'replacements':[{'search':a,'replace':b}]} for rel,a,b in edits]})


def group(rel='service.py'):
    return {'file':rel,'kinds':['functional_provider'],'phase':0,'problems':['Read and persist actual data.']}


def delta(root,clone,*args):
    result=subprocess.run([sys.executable,'workflow.py'],cwd=clone,capture_output=True,text=True)
    if result.returncode: return {'improved':False,'after':[{'problem':result.stderr}]}
    return {'improved':True,'before_total':1,'after_total':0,'before':[],'after':[]}


class FunctionalTransactions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def fake(self,model,validator=None):
        return {'_qwen_call':model,'_extract_json':j._extract_json,
                '_copy_project_for_candidate_validation':j._copy_project_for_candidate_validation,
                '_v4216_language_syntax_error':lambda root,m,rel,text: self.syntax(rel,text),
                '_v35_validate_component':validator or (lambda *a:(True,'fixture component')),
                '_append_project_event':lambda *a,**k:None}
    def syntax(self,rel,text):
        if rel.endswith('.py'):
            try:compile(text,rel,'exec')
            except SyntaxError as exc:return str(exc)
        return ''
    def test_manifest_supports_unlisted_language_extensions(self):
        write(self.root,'main.uncommon','import provider; run service')
        write(self.root,'provider.uncommon','provide service')
        manifest={'files':[{'path':'main.uncommon'},{'path':'provider.uncommon'}]}
        self.assertIn('provider.uncommon',v.related_sources(self.root,'main.uncommon',manifest))
    def test_round_does_not_starve_third_target(self):
        rows=[]
        for rel in ['a.py','b.py','c.py']:
            write(self.root,rel,'VALUE=0')
            rows.append({'file':rel,'kind':'functional_provider','problem':'persist data'})
        called=[]
        def repair(*args,**kwargs):
            called.append(args[4]['file'])
            return args[4]['file']=='c.py',['fixture failure']
        with patch.object(v,'repair_transaction',side_effect=repair):
            changed=j._v429_repair_audit_round('finish',{},self.root,{'issues':rows},None,1)
        self.assertTrue(changed);self.assertEqual(called,['a.py','b.py','c.py'])
    def test_exhausted_checkpoint_reopens_after_provider_change(self):
        write(self.root,'service.py','from provider import save')
        write(self.root,'provider.py','def save(): return 0')
        rows=[{'file':'service.py','kind':'functional_provider','problem':'persist data'}]
        with patch.object(v,'repair_transaction',return_value=(False,['fixture failure'])) as repair:
            for n in range(3):j._v429_repair_audit_round('finish',{},self.root,{'issues':rows},None,n+1)
            self.assertEqual(repair.call_count,2)
            write(self.root,'provider.py','def save(): return 1')
            j._v429_repair_audit_round('finish',{},self.root,{'issues':rows},None,4)
            self.assertEqual(repair.call_count,3)
    def test_active_engine_and_guards(self):
        self.assertEqual(j._v36_release_identity()['version'],'V42.63.0')
        self.assertTrue(j._v4250_engine_disk_guard()[0]);self.assertTrue(j._v4249_engine_disk_guard()[0])
    def test_related_source_excludes_metadata_and_backups(self):
        write(self.root,'service.py','from provider import save\n');write(self.root,'provider.py','def save(): return 1\n')
        write(self.root,'.jarvis_resume.json','{"provider":"huge metadata"}');write(self.root,'.jarvis_backups/provider.py','stale')
        self.assertEqual(set(v.related_sources(self.root,'service.py')),{'service.py','provider.py'})
    def test_dependency_change_reopens_identity_but_backups_do_not(self):
        write(self.root,'service.py','from provider import save\n');write(self.root,'provider.py','def save(): return 1\n')
        a=v.dependency_token(self.root,'service.py');write(self.root,'.jarvis_backups/provider.py','anything')
        self.assertEqual(a,v.dependency_token(self.root,'service.py'))
        write(self.root,'provider.py','def save(): return 2\n');self.assertNotEqual(a,v.dependency_token(self.root,'service.py'))
    def test_multifile_sqlite_workflow_success_failure_and_restart(self):
        write(self.root,'service.py','from provider import save\ndef create(name): return save(name)\n')
        write(self.root,'provider.py','def save(name): return "fake"\n')
        write(self.root,'workflow.py', '''import sqlite3, subprocess, sys
from service import create
assert create('hammer') == 1
try: create('')
except ValueError: pass
else: raise AssertionError('empty name accepted')
assert sqlite3.connect('app.db').execute('select count(*) from items').fetchone()[0] == 1
subprocess.run([sys.executable,'-c',"import sqlite3; assert sqlite3.connect('app.db').execute('select name from items').fetchone()[0] == 'hammer'"],check=True)
''')
        new='''import sqlite3
def save(name):
    with sqlite3.connect('app.db') as db:
        db.execute('create table if not exists items(id integer primary key, name text not null)')
        return db.execute('insert into items(name) values (?)',(name,)).lastrowid
'''
        model=lambda *a,**k:response([('provider.py','def save(name): return "fake"\n',new),
            ('service.py','def create(name): return save(name)','def create(name):\n    if not name: raise ValueError("empty")\n    return save(name)')])
        with patch.object(v.gates,'_functional_delta',side_effect=delta):
            ok,errors=v.repair_transaction(self.fake(model),'finish',{},self.root,group())
        self.assertTrue(ok,errors)
        result=subprocess.run([sys.executable,'workflow.py'],cwd=self.root,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_compile_error_feedback_changes_next_candidate(self):
        write(self.root,'service.py','VALUE=0\n');prompts=[]
        def model(prompt,*a,**k):
            prompts.append(prompt)
            return response([('service.py','VALUE=0','VALUE=' if len(prompts)==1 else 'VALUE=1')])
        with patch.object(v.gates,'_functional_delta',return_value={'improved':True,'before':[],'after':[]}):
            ok,errors=v.repair_transaction(self.fake(model),'finish',{},self.root,group())
        self.assertTrue(ok,errors);self.assertIn('invalid syntax',prompts[1]);self.assertEqual((self.root/'service.py').read_text(),'VALUE=1\n')
    def test_failed_component_keeps_original_bytes(self):
        write(self.root,'service.py','VALUE=0\n');model=lambda *a,**k:response([('service.py','VALUE=0','VALUE=1')])
        with patch.object(v.gates,'_component_candidate_proof',return_value={'ok':False,'kind':'test','output':'workflow failed'}):
            ok,errors=v.repair_transaction(self.fake(model),'finish',{},self.root,group())
        self.assertFalse(ok);self.assertEqual((self.root/'service.py').read_text(),'VALUE=0\n')
    def test_out_of_scope_edits_rejected(self):
        write(self.root,'service.py','VALUE=0\n');model=lambda *a,**k:response([('../escape.py','a','b')])
        ok,errors=v.repair_transaction(self.fake(model),'finish',{},self.root,group())
        self.assertFalse(ok);self.assertTrue(any('out-of-scope' in x for x in errors))
    def test_new_functional_regression_rejected(self):
        write(self.root,'service.py','VALUE=0\n');model=lambda *a,**k:response([('service.py','VALUE=0','VALUE=1')])
        with patch.object(v.gates,'_functional_delta',return_value={'improved':True,'before':[],'after':[{'file':'provider.py','kind':'persistence_schema','problem':'broken'}]}):
            ok,errors=v.repair_transaction(self.fake(model),'finish',{},self.root,group())
        self.assertFalse(ok);self.assertEqual((self.root/'service.py').read_text(),'VALUE=0\n')
    def test_commit_rolls_back_all_files_on_write_failure(self):
        clone=self.root/'candidate';clone.mkdir()
        for rel in ['a.py','b.py']:write(self.root,rel,'old\r\n');write(clone,rel,'new\n')
        originals={rel:(self.root/rel).read_bytes() for rel in ['a.py','b.py']};replace=os.replace;calls=[]
        def fail_second(a,b):
            calls.append(str(b))
            if len(calls)==2:raise OSError('injected disk error')
            return replace(a,b)
        with patch.object(v.os,'replace',side_effect=fail_second):
            with self.assertRaises(OSError):v._commit({},self.root,clone,originals,{'a.py':'new','b.py':'new'}, {})
        for rel,raw in originals.items():self.assertEqual((self.root/rel).read_bytes(),raw)
    def test_concurrent_source_change_not_overwritten(self):
        clone=self.root/'candidate';clone.mkdir();write(self.root,'a.py','user edit');write(clone,'a.py','candidate')
        with self.assertRaises(ValueError):v._commit({},self.root,clone,{'a.py':b'old'},{'a.py':'candidate'}, {})
        self.assertEqual((self.root/'a.py').read_text(),'user edit')
    def test_test_debt_survives_repaired_bridge(self):
        import jarvis_v4247_repair as audit
        files=[('src/service.ts',None,'invoke("create", {name:"hammer"});'),('tests/app.test.ts',None,'expect(typeof App).toBe("function");')]
        self.assertTrue(any(x['kind']=='functional_test_coverage' for x in audit._meaningful_test_issues(self.root,files,[])))
    def test_comment_only_patch_rejected(self):
        write(self.root,'service.ts','// mock backend\nexport const x=1;\n');model=lambda *a,**k:response([('service.ts','// mock backend\n','')])
        ok,errors=v.repair_transaction(self.fake(model),'finish',{},self.root,group('service.ts'))
        self.assertFalse(ok);self.assertTrue(any('comment/format-only' in x for x in errors))
    @unittest.skipUnless(shutil.which('gcc'),'GCC unavailable')
    def test_c_compiler_and_executable_use_same_transaction_policy(self):
        write(self.root,'main.c','#include <stdio.h>\nint main(void) { printf("%d", 0); return 0; }\n')
        def validator(clone,*args):
            result=subprocess.run(['gcc','main.c','-o','app'],cwd=clone,capture_output=True,text=True)
            if result.returncode:return False,result.stderr
            run=subprocess.run([str(clone/'app')],cwd=clone,capture_output=True,text=True)
            return run.returncode==0 and run.stdout=='42',run.stdout
        model=lambda *a,**k:response([('main.c','printf("%d", 0)','printf("%d", 42)')])
        manifest={'components':[{'id':'c','root':'.','toolchain_adapter':'c_cpp'}]}
        with patch.object(v.gates,'_functional_delta',return_value={'improved':True,'before':[],'after':[]}):
            ok,errors=v.repair_transaction(self.fake(model,validator),'finish',manifest,self.root,group('main.c'))
        self.assertTrue(ok,errors)
    @unittest.skipUnless(shutil.which('node'),'Node unavailable')
    def test_javascript_workflow_uses_same_policy(self):
        write(self.root,'app.js','const result = 0;\nif (result !== 42) throw Error("wrong result");\n')
        def validator(clone,*args):
            p=subprocess.run(['node','app.js'],cwd=clone,capture_output=True,text=True);return p.returncode==0,p.stderr
        model=lambda *a,**k:response([('app.js','const result = 0','const result = 42')])
        manifest={'components':[{'id':'js','root':'.','toolchain_adapter':'node'}]}
        with patch.object(v.gates,'_functional_delta',return_value={'improved':True,'before':[],'after':[]}):
            ok,errors=v.repair_transaction(self.fake(model,validator),'finish',manifest,self.root,group('app.js'))
        self.assertTrue(ok,errors)

if __name__=='__main__':unittest.main(verbosity=2)
