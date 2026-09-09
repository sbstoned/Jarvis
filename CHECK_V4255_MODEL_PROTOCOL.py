"""Provider-boundary regressions: real HTTP/SSE, routing and staged native work.

The local HTTP fixture emits controlled model text. It is not a live Qwen model.
Production _qwen_call, ask_qwen, parsing and transaction paths are exercised.
"""
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import local_qwen_project as j
import multi_provider as provider
import jarvis_v4240_repair as control
import jarvis_v4251_repair as tx
import jarvis_v4252_repair as progress
from jarvis_model_protocol import exact_replacements, fit_source_prompt, parse_object
from jarvis_sql_contracts import sqlite_contract_issues, sqlx_returning_issues
from jarvis_workflow_contracts import _target, debt_key, workflow_issues


@contextmanager
def model_server(responder, context=32768, mode='9b35'):
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(payload)
            response = responder(payload,len(requests))
            status = response.get('status',200)
            self.send_response(status)
            self.send_header('Content-Type','text/event-stream' if status==200 else 'application/json')
            self.end_headers()
            if status != 200:
                self.wfile.write(b'{"error":"injected provider failure"}'); return
            body = response.get('text','')
            for offset in range(0,len(body),127):
                data = {'choices':[{'delta':{'content':body[offset:offset+127]},'finish_reason':None}]}
                self.wfile.write(('data: '+json.dumps(data)+'\n\n').encode())
            if response.get('finish','stop') is not None:
                data = {'choices':[{'delta':{},'finish_reason':response.get('finish','stop')}],
                        'usage':{'completion_tokens':len(body)//3,'prompt_tokens':100}}
                self.wfile.write(('data: '+json.dumps(data)+'\n\n').encode())
            if response.get('done',True): self.wfile.write(b'data: [DONE]\n\n')
            self.wfile.flush()
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True); worker.start()
    with ExitStack() as stack:
        stack.enter_context(patch.object(provider,'QWEN_CHAT_URL',f'http://127.0.0.1:{server.server_port}/v1/chat/completions'))
        stack.enter_context(patch.object(provider,'qwen_runtime_model_family',return_value='qwen35'))
        stack.enter_context(patch.object(j,'_v426_active_profile',return_value=mode if mode!='auto' else '9b35'))
        # This protocol fixture represents an already verified model runtime.
        # Native readiness and rejected runtimes are covered by CHECK_V4263.
        stack.enter_context(patch.object(j,'_v426_runtime_matches',side_effect=lambda target: target == (mode if mode!='auto' else '9b35')))
        stack.enter_context(patch.object(j,'qwen_status',return_value=True))
        stack.enter_context(patch.object(j,'_qwen_effective_context_tokens',return_value=context))
        stack.enter_context(patch.object(j,'_qwen_structured_output_supported',return_value=True))
        stack.enter_context(patch.object(control,'_STOP_EVENT',threading.Event()))
        j.configure_project_qwen_routing(mode)
        try:
            yield requests
        finally:
            j.clear_project_qwen_routing()
            server.shutdown(); server.server_close(); worker.join(2)


def reply(rel,search,replace):
    return json.dumps({'edits':[{'file':rel,'replacements':[{'search':search,'replace':replace}]}]})


class ModelProtocol(unittest.TestCase):
    def test_actual_call_keeps_requested_output_and_one_format(self):
        body = reply('source.py','VALUE=0','VALUE=1\n# '+('preserved source ' * 1000))
        with model_server(lambda *_:{'text':body}) as calls:
            ok,raw = j._qwen_call('Return JSON edits using CURRENT_SOURCE_SENTINEL.',profile='repair',
                                 max_tokens=9000,thinking=False,response_schema=tx.SCHEMA,strict_output=True)
        self.assertTrue(ok,str(raw)); self.assertEqual(parse_object(raw)['edits'][0]['file'],'source.py')
        self.assertEqual(len(calls),1); self.assertEqual(calls[0]['max_tokens'],9000)
        self.assertGreater(len(body),11200)
        prompt = calls[0]['messages'][0]['content']
        self.assertIn('CURRENT_SOURCE_SENTINEL',prompt)
        self.assertEqual(prompt.count('JARVIS CURRENT EXECUTION POLICY:'),1)
        self.assertNotIn('Return only valid source/config',prompt)
        self.assertNotIn('LAST-MILE CONSTRAINT AUTHORITY',prompt)
        self.assertEqual(calls[0]['response_format']['json_schema']['schema'],tx.SCHEMA)
        self.assertFalse(calls[0]['chat_template_kwargs']['enable_thinking'])

    def test_new_file_continuation_preserves_partial_work_until_complete(self):
        first='<<<JARVIS_FILE path="math_service.py">>>\ndef first():\n    return 1\n'
        second='<<<JARVIS_CONTINUATION path="math_service.py">>>\ndef second():\n    return 2\n<<<JARVIS_END_CONTINUATION>>>\n'
        def response(_,number):
            return {'text':first,'finish':'length'} if number==1 else {'text':second}
        with model_server(response) as calls:
            ok,source=j._qwen_generate_complete_file('Create first() and second().','math_service.py')
        self.assertTrue(ok,source);self.assertEqual(len(calls),2)
        self.assertIn('TAIL OF THE ALREADY-KEPT FILE',calls[1]['messages'][0]['content'])
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'math_service.py').write_text(source)
            run=subprocess.run([sys.executable,'-c','from math_service import first,second; assert first()==1; assert second()==2'],cwd=folder,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stderr)

    def test_incomplete_continuation_never_becomes_accepted_source(self):
        raw='<<<JARVIS_CONTINUATION path="service.py">>>\ndef second():\n    return 2\n'
        with model_server(lambda *_:{'text':raw,'finish':'length'}) as calls, \
             patch.object(j,'FILE_CONTINUATION_ROUNDS',2):
            ok,draft,error=j._continue_truncated_file('service.py','def first():\n    return 1\n')
        self.assertFalse(ok);self.assertIn('def first',draft);self.assertIn('def second',draft)
        self.assertEqual(len(calls),2)

    def test_stream_length_is_failure_even_if_json_happens_to_parse(self):
        with model_server(lambda *_:{'text':'{"edits":[]}','finish':'length'}):
            ok,raw=j._qwen_call('return JSON',profile='repair',max_tokens=9000,response_schema=tx.SCHEMA,strict_output=True)
        self.assertFalse(ok); self.assertIn('output limit',raw)
        self.assertEqual(raw.metadata['finish_reason'],'length')
        self.assertEqual(raw.partial_text,'{"edits":[]}')
        self.assertIsNone(provider._ACTIVE_QWEN_STREAM)

    def test_unterminated_stream_cannot_be_accepted(self):
        with model_server(lambda *_:{'text':'{"ok":true}','finish':None,'done':False}):
            ok,raw=provider.ask_qwen('test',enable_thinking=False)
        self.assertFalse(ok); self.assertIn('completion marker',raw)

    def test_done_only_compatible_stream(self):
        with model_server(lambda *_:{'text':'ready','finish':None}):
            ok,raw=provider.ask_qwen('test',enable_thinking=False)
        self.assertTrue(ok); self.assertEqual(raw,'ready')

    def test_http_error_releases_active_stream(self):
        with model_server(lambda *_:{'status':503}):
            ok,raw=provider.ask_qwen('test',enable_thinking=False)
        self.assertFalse(ok); self.assertIn('503',raw); self.assertIsNone(provider._ACTIVE_QWEN_STREAM)

    def test_invalid_json_is_not_silently_retried_by_hidden_layers(self):
        with model_server(lambda *_:{'text':'{"edits":['}) as calls:
            ok,raw=j._qwen_call('return JSON',profile='repair',response_schema=tx.SCHEMA,strict_output=True)
        self.assertTrue(ok) # Transport complete; caller owns JSON validation.
        self.assertEqual(len(calls),1)
        with self.assertRaisesRegex(ValueError,'line 1, column'):
            parse_object(raw)

    def test_small_manual_context_keeps_entire_selected_source(self):
        source={'service.py':'VALUE=0\n','other.py':'# x\n'*4000,'tail.py':'# y\n'*4000}
        supplied={}
        def builder(budget):
            text,chosen=fit_source_prompt('Return JSON edits.',source,'service.py',budget)
            supplied.update(chosen); return text
        with model_server(lambda *_:{'text':reply('service.py','VALUE=0','VALUE=1')},context=6144) as calls:
            ok,raw=j._qwen_call('fit current source',profile='repair',max_tokens=9000,
                              prompt_builder=builder,response_schema=tx.SCHEMA,strict_output=True)
        self.assertTrue(ok,str(raw));self.assertEqual(supplied,{'service.py':'VALUE=0\n'})
        self.assertEqual(calls[0]['max_tokens'],2048)
        text=calls[0]['messages'][0]['content']
        self.assertIn(json.dumps(supplied),text);self.assertNotIn('COMPACTION',text)

    def test_oversized_atomic_source_fails_before_network(self):
        with model_server(lambda *_:{'text':'should not be called'},context=4096) as calls:
            ok,raw=j._qwen_call('x'*80000,profile='repair',response_schema=tx.SCHEMA,strict_output=True)
        self.assertFalse(ok);self.assertIn('not truncated',raw);self.assertEqual(calls,[])

    def test_stop_prevents_inference(self):
        with model_server(lambda *_:{'text':'unused'}) as calls:
            control._STOP_EVENT.set()
            with self.assertRaises(control.ProjectStopRequested): j._qwen_call('test')
        self.assertEqual(calls,[])

    def test_stop_after_stream_prevents_returning_candidate(self):
        def responder(*_):
            control._STOP_EVENT.set()
            return {'text':reply('source.py','VALUE=0','VALUE=1')}
        with model_server(responder) as calls:
            with self.assertRaises(control.ProjectStopRequested):
                j._qwen_call('test',response_schema=tx.SCHEMA,strict_output=True)
        self.assertEqual(len(calls),1)

    def test_manual_model_never_cross_rescues(self):
        with model_server(lambda *_:{'text':'unused'},mode='27b'):
            with patch.object(j,'_v36_base_qwen_call',return_value=(False,'context window exceeded')), \
                 patch.object(j,'_v426_switch_for_call',return_value=(True,'active')) as switch:
                ok,_=j._qwen_call('test',profile='repair')
                self.assertFalse(ok);self.assertEqual(switch.call_count,1)
                self.assertEqual(switch.call_args.args[0],'27b')

    def test_auto_watchdog_retains_one_peer_rescue(self):
        with model_server(lambda *_:{'text':'unused'},mode='auto'):
            with patch.object(j,'_v36_base_qwen_call',side_effect=[(False,'context window exceeded'),(True,'fixed')]), \
                 patch.object(j,'_v426_switch_for_call',return_value=(True,'active')) as switch:
                self.assertEqual(j._qwen_call('test',profile='repair'),(True,'fixed'))
                self.assertEqual([call.args[0] for call in switch.call_args_list],['9b35','27b38q2'])

    def test_json_fence_and_escaping(self):
        obj={'edits':[{'file':'source.py','replacements':[{'search':'s="a\\b"\n','replace':'s="\\n"\n'}]}]}
        self.assertEqual(parse_object('```json\n'+json.dumps(obj)+'\n```'),obj)
        for text in ['{"edits":[],"edits":[]}','{"edits":NaN}','{} trailing','{"edits":[']:
            with self.assertRaises(ValueError): parse_object(text)

    def test_duplicate_exact_blocks_apply_once(self):
        block={'search':'import sqlite3\n','replace':'import sqlite3, os\n'}
        self.assertEqual(exact_replacements('import sqlite3\nVALUE=1\n',[block,block]),'import sqlite3, os\nVALUE=1\n')

    def test_sequential_blocks_cannot_accidentally_rewrite_inserted_text(self):
        result=exact_replacements('first=0\nsecond=0\n',[
            {'search':'first=0','replace':'first=1\nsecond=0'},
            {'search':'second=0','replace':'second=2'}])
        self.assertEqual(result,'first=1\nsecond=0\nsecond=2\n')

    def test_overlapping_or_ambiguous_source_rejected(self):
        for source,blocks in [
            ('abc',[{'search':'ab','replace':'x'},{'search':'bc','replace':'y'}]),
            ('abcabc',[{'search':'abc','replace':'x'}]),
            ('abc',[{'search':'abc','replace':'x'},{'search':'x','replace':'y'}])]:
            with self.assertRaises(ValueError): exact_replacements(source,blocks)


class NativeContractIdentity(unittest.TestCase):
    def statements(self,query,owner='write'):
        return [('storage.py', 'import sqlite3\nSCHEMA="CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)"\n'
                 +f'def {owner}(db):\n    return db.execute({query!r})\n')]

    def test_returning_does_not_reintroduce_existing_wrong_column(self):
        before=sqlite_contract_issues(self.statements('UPDATE items SET missing = 1'))
        after=sqlite_contract_issues(self.statements('UPDATE items SET missing = 1 RETURNING id, name'))
        self.assertEqual(len(before),1);self.assertEqual(len(after),1)
        self.assertEqual(debt_key(before[0]),debt_key(after[0]))
        self.assertEqual(progress.new_functional_regressions({'functional_issues':before},{'functional_issues':after}),[])

    def test_new_column_table_or_owner_remains_regression(self):
        before=sqlite_contract_issues(self.statements('UPDATE items SET missing = 1'))
        for files in [self.statements('UPDATE items SET other_missing = 1'),
                      self.statements('UPDATE items SET missing = 1',owner='other'),
                      [(rel,text.replace('items','other_items')) for rel,text in self.statements('UPDATE items SET missing = 1')]]:
            after=sqlite_contract_issues(files)
            self.assertTrue(progress.new_functional_regressions({'functional_issues':before},{'functional_issues':after}))

    def test_duplicate_bad_queries_are_counted(self):
        files=self.statements('UPDATE items SET missing = 1')
        before=sqlite_contract_issues(files)
        after=sqlite_contract_issues([(files[0][0],files[0][1]+'    db.execute("UPDATE items SET missing = 1")\n')])
        self.assertEqual(len(after),2)
        self.assertEqual(len(progress.new_functional_regressions({'functional_issues':before},{'functional_issues':after})),1)

    def test_import_line_shifts_keep_identity(self):
        files=self.statements('UPDATE items SET missing = 1')
        a=sqlite_contract_issues(files)
        b=sqlite_contract_issues([(files[0][0],'import os\n\n'+files[0][1])])
        self.assertEqual(debt_key(a[0]),debt_key(b[0]))

    def test_rust_runner_overrides_incidental_javascript(self):
        c={'id':'native','root':'src-tauri','toolchain_adapter':'rust'}
        files={'src-tauri/tailwind.config.js':'module.exports={}', 'src-tauri/src/main.rs':'fn main() {}'}
        manifest={'components':[c],'files':[{'path':'src-tauri/tests/application.integration.test.js'}]}
        self.assertEqual(_target(files,manifest,c,{}),'src-tauri/tests/application.rs')

    def test_wrong_language_test_cannot_clear_native_workflow_debt(self):
        c={'id':'native','root':'native','toolchain_adapter':'rust','test_command':'cargo test'}
        files={'native/src/main.rs':'fn main() {}','native/tests/fake.test.js':'const {run} = require("../app"); assert(run(1)===1); assert(run(2)===2);'}
        rows=workflow_issues(files,{'components':[c]})
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['file'],'native/tests/application.rs')

    def test_declared_runners_select_native_formats(self):
        for adapter,command,ending in [('go','go test ./...','application_test.go'),
                                      ('python','python -m pytest','tests/test_application.py'),
                                      ('custom','cargo test','tests/application.rs'),
                                      ('react','node --test','tests/application.integration.test.js'),
                                      ('react','vitest run','tests/application.integration.test.ts')]:
            c={'root':'.','toolchain_adapter':adapter,'test_command':command}
            self.assertEqual(_target({'app.tsx':'export const app=1'}, {}, c, {}),ending)

    def test_custom_language_preserves_declared_test_extension(self):
        c={'root':'engine','toolchain_adapter':'custom','test_extension':'.unusual','test_command':'native-check tests/application_test.unusual'}
        self.assertEqual(_target({'engine/app.unusual':'program app'}, {}, c, {}),'engine/tests/application_test.unusual')

    def test_js_test_remains_valid_for_typescript_vitest_project(self):
        c={'id':'web','root':'.','toolchain_adapter':'react','test_command':'vitest run'}
        files={'app.tsx':'export const run=()=>1;', 'tests/app.test.js':'import {run} from "../app"; expect(run()).toBe(1); expect(run()).toBe(1);'}
        self.assertEqual(workflow_issues(files,{'components':[c]}),[])
        self.assertEqual(_target(files,{},c,{'tests/app.test.js':files['tests/app.test.js']}),'tests/app.test.js')

    def test_child_planned_test_cannot_become_parent_target(self):
        c={'id':'web','root':'.','toolchain_adapter':'node','test_command':'npm test'}
        m={'components':[c,{'id':'api','root':'api','toolchain_adapter':'node'}],
           'files':[{'path':'api/tests/application.test.js'}]}
        self.assertEqual(_target({'app.js':'run()'},m,c,{}),'tests/application.integration.test.js')

    def test_declared_harness_language_precedes_application_language(self):
        c={'root':'.','toolchain_adapter':'rust','test_command':'python -m pytest'}
        self.assertEqual(_target({'src/main.rs':'fn main() {}'}, {}, c, {}),'tests/test_application.py')

    def test_rust_sql_identity_survives_returning_and_import_edits(self):
        source='''use sqlx::SqlitePool;
pub async fn update(pool: &SqlitePool) {
    let schema = "CREATE TABLE items(id INTEGER PRIMARY KEY, name TEXT)";
    sqlx::query(schema).execute(pool).await;
    let query = "UPDATE items SET missing = ? WHERE id = ?";
    sqlx::query(query).execute(pool).await;
}
'''
        before=sqlite_contract_issues([('storage.rs',source)])
        after=sqlite_contract_issues([('storage.rs','use std::sync::Arc;\n'+source.replace('WHERE id = ?','WHERE id = ? RETURNING id, name'))])
        self.assertEqual(len(before),1);self.assertEqual(len(after),1)
        self.assertEqual(debt_key(before[0]),debt_key(after[0]))
        self.assertEqual(after[0]['evidence']['owner'],'update')

    def test_execute_does_not_inherit_a_different_functions_fetch(self):
        source='''use sqlx::SqlitePool;
pub async fn execute_update(pool: &SqlitePool) {
    let query = "UPDATE items SET name = ? WHERE id = ?";
    sqlx::query(query).bind("saved").bind(1).execute(pool).await;
}
pub async fn returning_update(pool: &SqlitePool) {
    let query = "UPDATE items SET name = ? WHERE id = ? RETURNING id, name";
    sqlx::query_as::<_, Item>(query).bind("saved").bind(1).fetch_one(pool).await;
}
'''
        self.assertEqual(sqlx_returning_issues('storage.rs',source),[])

    def test_missing_returning_debt_tracks_each_owning_function(self):
        def method(name):
            return f'''pub async fn {name}(pool: &SqlitePool) {{
    let query = "INSERT INTO items(name) VALUES (?)";
    sqlx::query_as::<_, Item>(query).bind("saved").fetch_one(pool).await;
}}
'''
        source=method('first')+method('second')
        before=sqlx_returning_issues('storage.rs',source)
        after=sqlx_returning_issues('storage.rs',source.replace('VALUES (?)','VALUES (?) RETURNING id, name',1))
        self.assertEqual(len(before),2);self.assertEqual(len(after),1)
        self.assertEqual(after[0]['evidence']['owner'],'second')
        self.assertEqual(progress.new_functional_regressions({'functional_issues':before},{'functional_issues':after}),[])

    def test_sqlx_row_mutation_direct_literals_and_aliases(self):
        direct='sqlx::query_as::<_, Item>("INSERT INTO items(name) VALUES (?)").bind("saved").fetch_one(pool).await;'
        self.assertEqual(len(sqlx_returning_issues('storage.rs',direct)),1)
        aliases='let sql: &str = "INSERT INTO items(name) VALUES (?)";\nlet query = sql;\nlet again = query;\nsqlx::query_as::<_, Item>(again).fetch_one(pool).await;'
        self.assertEqual(len(sqlx_returning_issues('storage.rs',aliases)),1)
        self.assertEqual(sqlx_returning_issues('storage.rs',direct.replace('.fetch_one(','.execute(')),[])

    def test_returning_in_string_data_is_not_a_projection(self):
        source='sqlx::query_as::<_, Item>("INSERT INTO items(name) VALUES (\'RETURNING\')").fetch_one(pool).await;'
        self.assertEqual(len(sqlx_returning_issues('storage.rs',source)),1)


class FullProviderTransaction(unittest.TestCase):
    def test_http_model_reply_repairs_real_service_and_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source='''import sqlite3
def add(name):
    if not name.strip(): raise ValueError("name required")
    with sqlite3.connect("app.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, name TEXT)")
        return db.execute("INSERT INTO items(name) VALUES (?)", (name,)).lastrowid
def get(key):
    with sqlite3.connect("app.db") as db:
        return db.execute("SELECT id, label FROM items WHERE id=?", (key,)).fetchone()
'''
            (root/'service.py').write_text(source)
            (root/'tests').mkdir()
            (root/'tests/test_application.py').write_text('''import sqlite3, subprocess, sys, unittest
from pathlib import Path
from service import add, get
class Workflow(unittest.TestCase):
    def test_workflow(self):
        Path("app.db").unlink(missing_ok=True)
        key=add("saved")
        self.assertEqual(get(key),(key,"saved"))
        with self.assertRaises(ValueError): add(" ")
        with sqlite3.connect("app.db") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM items").fetchone()[0],1)
        subprocess.run([sys.executable,"-c","from service import get; assert get(1) == (1, 'saved')"],check=True)
''')
            manifest={'files':[{'path':'service.py'},{'path':'tests/test_application.py'}],
                      'components':[{'id':'storage','root':'.','toolchain_adapter':'custom',
                                     'build_command':f'"{sys.executable}" -m py_compile service.py',
                                     'test_command':f'"{sys.executable}" -m unittest discover -s tests -v'}]}
            rows=progress.functional_issues(root,'finish',manifest)
            sql=[r for r in rows if r['kind']=='persistence_sql_prepare']
            self.assertEqual(len(sql),1)
            group={'file':'service.py','kinds':['persistence_sql_prepare'],'phase':0,'rows':sql}
            def respond(payload,n):
                prompt=payload['messages'][0]['content']
                self.assertIn('import sqlite3',prompt)
                if n==1: return {'text':'{"edits":[','finish':'length'}
                self.assertIn('output limit',prompt)
                return {'text':reply('service.py','SELECT id, label FROM items','SELECT id, name FROM items')}
            with model_server(respond) as calls:
                ok,errors=tx.repair_transaction(vars(j),'finish',manifest,root,group)
            self.assertTrue(ok,errors);self.assertEqual(len(calls),2)
            self.assertTrue((root/'service.py').read_text().startswith('import sqlite3\n'))
            self.assertEqual(progress.functional_issues(root,'finish',manifest),[])
            run=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=root,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            records=[json.loads(p.read_text()) for p in (root/'.jarvis_failures/model_outputs').glob('v4255_*.json')]
            # V42.59 may recover transport truncation inside the same functional
            # attempt. The final bounded receipt must still preserve the truncation
            # history and current-source hashes; older outer-attempt recovery may
            # legitimately leave two receipts.
            self.assertGreaterEqual(len(records),1)
            self.assertTrue(any(
                r['transport'].get('finish_reason')=='length' or
                any(h.get('finish_reason')=='length' for h in r['transport'].get('v4259_truncation_history',[]))
                for r in records))
            self.assertTrue(all('service.py' in r['supplied_source_sha256'] for r in records))
            with sqlite3.connect(root/'app.db') as db:
                self.assertEqual(db.execute('SELECT name FROM items').fetchall(),[('saved',)])


if __name__=='__main__': unittest.main(verbosity=2)
