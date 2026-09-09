from pathlib import Path
import json, shutil, tempfile, unittest
import jarvis_v4251_repair as tx
import local_qwen_project as j

class EvidenceClosedScopedRepair(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='v4256_'))
    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_active_release(self):
        ident=j._v36_release_identity()
        self.assertEqual(ident['version'],'V42.63.0')
        self.assertTrue(ident.get('integration_seam_evidence_priority'))
        self.assertTrue(ident.get('validator_owned_patch_scope'))

    def test_real_integration_seam_outranks_cross_component_similarity(self):
        files={
          'src/hooks/useFeature.ts':'import { Thing } from "../types/thing";\n// simulate backend\nexport const x=()=>Thing;\n',
          'src/hooks/useRuntimeCommands.ts':'import { invoke } from "@runtime/core";\nexport async function getThings(){return invoke("things_get_all");}\n',
          'src/types/thing.ts':'export interface Thing { id:string }\n',
          'native/src/things.rs':'pub async fn get_things(){ query_as("SELECT * FROM things"); }\n',
        }
        for rel,text in files.items():
            p=self.tmp/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
        picked=tx.related_sources(self.tmp,'src/hooks/useFeature.ts',{})
        names=list(picked)
        self.assertIn('src/hooks/useRuntimeCommands.ts',names)
        self.assertLess(names.index('src/hooks/useRuntimeCommands.ts'), names.index('native/src/things.rs'))

    def test_structured_sql_scope_prunes_unrelated_working_query(self):
        current='''pub async fn create_tool() {\n let sql = r#"INSERT INTO tools (id) VALUES (?)"#;\n}\npub async fn get_joined() {\n let sql = r#"SELECT t.*, p.name FROM tools t LEFT JOIN persons p ON p.id=t.person_id"#;\n}\n'''
        group={'file':'src/tools.rs','rows':[{'kind':'persistence_returning','evidence':{
            'owner':'create_tool','line':2,'sql':'INSERT INTO tools (id) VALUES (?)'}}]}
        edits=[
          {'search':'let sql = r#"INSERT INTO tools (id) VALUES (?)"#;',
           'replace':'let sql = r#"INSERT INTO tools (id) VALUES (?) RETURNING id"#;'},
          {'search':'let sql = r#"SELECT t.*, p.name FROM tools t LEFT JOIN persons p ON p.id=t.person_id"#;',
           'replace':'let sql = r#"SELECT t.*, p.name, 1 AS invented FROM tools t LEFT JOIN persons p ON p.id=t.person_id"#;'},
        ]
        kept=tx._scoped_replacements(group,current,edits)
        self.assertEqual(len(kept),1)
        self.assertIn('INSERT INTO tools',kept[0]['search'])

    def test_stale_zero_match_hunk_does_not_discard_exact_sibling(self):
        current='alpha = 1\nbeta = 2\n'
        edits=[
          {'search':'alpha = 0','replace':'alpha = 3'},
          {'search':'beta = 2','replace':'beta = 4'},
        ]
        kept=tx._applicable_replacements(current,edits)
        self.assertEqual(kept,[edits[1]])
        self.assertEqual(tx.exact_replacements(current,kept),'alpha = 1\nbeta = 4\n')

    def test_whole_behavior_targets_keep_coordinated_edit_freedom(self):
        group={'file':'src/hooks/useFeature.ts','rows':[{'kind':'functional_mock','problem':'replace simulation'}]}
        edits=[{'search':'const x=1','replace':'const x=2'}]
        self.assertEqual(tx._scoped_replacements(group,'const x=1',edits),edits)

if __name__=='__main__': unittest.main(verbosity=2)
