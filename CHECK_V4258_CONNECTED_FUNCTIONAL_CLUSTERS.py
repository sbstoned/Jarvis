from pathlib import Path
import json, shutil, tempfile, unittest
from unittest.mock import patch
import jarvis_v4251_repair as tx
import jarvis_v4249_repair as planner
import local_qwen_project as j


class V4258ConnectedClusters(unittest.TestCase):
    def setUp(self):
        self.tmp=Path(tempfile.mkdtemp(prefix='v4258_'))
    def tearDown(self):
        shutil.rmtree(self.tmp,ignore_errors=True)

    def _write(self, rel, text):
        p=self.tmp/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')

    def test_active_release_preserves_unbounded_useful_stream_policy(self):
        ident=j._v36_release_identity()
        self.assertEqual(ident['version'],'V42.63.0')
        self.assertTrue(ident.get('connected_functional_clusters'))
        self.assertTrue(ident.get('cluster_progress_is_acceptance_unit'))
        self.assertTrue(ident.get('rejected_trial_evidence_preserved'))
        self.assertEqual(j._qwen_profile_hard_timeout('repair'),0)

    def test_backend_provider_runtime_transitively_cluster(self):
        self._write('src/checkout.rs','fn checkout(){ query("SELECT * FROM tools"); }')
        self._write('src/tools.rs','fn create_tool(){ query("INSERT INTO tools(id) VALUES(?)"); }')
        self._write('src/main.rs','fn main(){ Builder::default(); }')
        groups=planner._group_rows([
            {'file':'src/checkout.rs','kind':'persistence_sql_prepare','problem':'tools query is wrong'},
            {'file':'src/tools.rs','kind':'persistence_returning','problem':'create_tool INSERT needs a row'},
            {'file':'src/main.rs','kind':'functional_bridge','problem':'missing tools_create and tools_update handlers'},
        ])
        clusters=tx.connected_functional_clusters(self.tmp,groups)
        self.assertEqual(len(clusters),1)
        self.assertEqual(set(clusters[0]['files']),{'src/checkout.rs','src/tools.rs','src/main.rs'})

    def test_same_layer_mocks_with_shared_real_seam_cluster(self):
        for name in ('useCategories.ts','usePersons.ts','useCheckouts.ts','useCSV.ts'):
            self._write('src/hooks/'+name,'// replace mock with real Tauri backend command\nexport const x=1;')
        groups=planner._group_rows([
            {'file':'src/hooks/'+name,'kind':'functional_mock','problem':'production mock must use backend'}
            for name in ('useCategories.ts','usePersons.ts','useCheckouts.ts','useCSV.ts')])
        clusters=tx.connected_functional_clusters(self.tmp,groups)
        self.assertEqual(len(clusters),1)
        self.assertEqual(len(clusters[0]['files']),4)

    def test_same_language_independent_targets_are_not_clustered(self):
        self._write('src/a.py','def alpha():\n    return 1\n')
        self._write('src/b.py','def beta():\n    return 2\n')
        self._write('src/c.py','def gamma():\n    return 3\n')
        groups=planner._group_rows([
            {'file':'src/a.py','kind':'functional_provider','problem':'alpha behavior'},
            {'file':'src/b.py','kind':'functional_provider','problem':'beta behavior'},
            {'file':'src/c.py','kind':'functional_provider','problem':'gamma behavior'},
        ])
        clusters=tx.connected_functional_clusters(self.tmp,groups)
        self.assertEqual([c['file'] for c in clusters],['src/a.py','src/b.py','src/c.py'])
        self.assertTrue(all(not c.get('cluster') for c in clusters))

    def test_peer_owner_improvement_can_accept_cluster_when_primary_is_unchanged(self):
        group={'file':'a.rs','owner_groups':[
            {'file':'a.rs','kinds':['persistence_schema']},
            {'file':'b.rs','kinds':['persistence_returning']},
        ]}
        before=[
            {'file':'a.rs','kind':'persistence_schema','problem':'a'},
            {'file':'b.rs','kind':'persistence_returning','problem':'b'},
        ]
        after=[{'file':'a.rs','kind':'persistence_schema','problem':'a'}]
        def audit(root,*_): return after if Path(root).name=='clone' else before
        clone=self.tmp/'clone'; clone.mkdir()
        with patch.object(planner,'functional_acceptance_issues',side_effect=audit):
            delta=tx._cluster_functional_delta(self.tmp,clone,'finish',{},group)
        self.assertTrue(delta['improved'])
        self.assertEqual(delta['owner_before'],{'a.rs':1,'b.rs':1})
        self.assertEqual(delta['owner_after'],{'a.rs':1,'b.rs':0})

    def test_validator_scope_is_applied_to_each_issue_owner(self):
        a='pub fn one(){ let sql = r#"UPDATE a SET x=1"#; }\npub fn unrelated(){ let sql = r#"SELECT * FROM z"#; }\n'
        b='pub fn two(){ let sql = r#"UPDATE b SET y=1"#; }\n'
        self._write('a.rs',a); self._write('b.rs',b)
        group={'file':'a.rs','owner_groups':[
            {'file':'a.rs','rows':[{'kind':'persistence_sql_prepare','evidence':{'owner':'one','sql':'UPDATE a SET x=1'}}]},
            {'file':'b.rs','rows':[{'kind':'persistence_sql_prepare','evidence':{'owner':'two','sql':'UPDATE b SET y=1'}}]},
        ],'rows':[]}
        evidence={'a.rs':a,'b.rs':b}
        raw={'edits':[
            {'file':'a.rs','replacements':[
                {'search':'pub fn one(){ let sql = r#"UPDATE a SET x=1"#; }','replace':'pub fn one(){ let sql = r#"UPDATE a SET x=2"#; }'},
                {'search':'pub fn unrelated(){ let sql = r#"SELECT * FROM z"#; }','replace':'pub fn unrelated(){ let sql = r#"SELECT * FROM q"#; }'},
            ]},
            {'file':'b.rs','replacements':[
                {'search':'pub fn two(){ let sql = r#"UPDATE b SET y=1"#; }','replace':'pub fn two(){ let sql = r#"UPDATE b SET y=2"#; }'},
            ]},
        ]}
        g={'_qwen_call':lambda *a,**k:(True,json.dumps(raw)), '_v4254_repair_evidence':lambda *a:{}, '_qwen_file_output_limit':lambda:9000}
        changes=tx._model_candidate(g,'finish',{},self.tmp,group,evidence,[],1,None)
        self.assertIn('UPDATE a SET x=2',changes['a.rs'])
        self.assertIn('SELECT * FROM z',changes['a.rs'])
        self.assertIn('UPDATE b SET y=2',changes['b.rs'])

    def test_rejected_trial_preserves_metadata_not_source(self):
        trial=self.tmp/'trial'; work=self.tmp/'work'; trial.mkdir(); work.mkdir()
        (trial/'JARVIS_V4251_FUNCTIONAL_TRANSACTIONS.json').write_text(json.dumps({'groups':{'x':{'errors':['bad candidate']}}}))
        folder=trial/'.jarvis_failures'/'model_outputs'; folder.mkdir(parents=True)
        (folder/'v4255_test.json').write_text(json.dumps({'target':'a.rs','attempt':2,'status':'received','error':'compile failed','response_chars':10,'response_sha256':'abc','transport':{},'supplied_source_sha256':{'a.rs':'def'}}))
        (trial/'rejected_source.rs').write_text('broken')
        j._v4258_preserve_rejected_trial_evidence(work,trial,1,['still broken'],{'score':[2,3,4]},{'score':[1,2,3]},[])
        out=json.loads((work/'JARVIS_V4258_REJECTED_TRIAL_EVIDENCE.json').read_text())
        self.assertEqual(out['version'],'V42.58.0')
        self.assertEqual(out['trials'][-1]['model_responses'][0]['target'],'a.rs')
        self.assertFalse((work/'rejected_source.rs').exists())


if __name__=='__main__': unittest.main(verbosity=2)
