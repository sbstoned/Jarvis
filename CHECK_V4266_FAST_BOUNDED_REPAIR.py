from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jarvis_v4251_repair as tx
import jarvis_v4259_repair as io
import jarvis_v4266_repair as v

passed = 0

def ck(name, condition, detail=''):
    global passed
    if not condition:
        raise AssertionError(f'{name}: {detail}')
    passed += 1
    print('PASS', name)

# Install the focused layer against a minimal engine surface. This proves the
# monkey-patches do not require a running model or project.
g = {
    '_v36_release_identity': lambda: {'version': 'V42.63.0', 'engine': 'base'},
    '_progress': lambda *a, **k: None,
    'RESUME_SWEEPS': 3,
    'JARVIS_DIR': ROOT,
}
v.install(g)
ident = g['_v36_release_identity']()
ck('release identity is V42.66', ident.get('version') == 'V42.66.0', ident)
ck('connected scheduler remains enabled', ident.get('connected_functional_clusters') is True, ident)
ck('model owner focus is bounded', int(ident.get('model_issue_owner_focus', 0)) in (1, 2), ident)
ck('resume sweeps raised for incremental progress', int(g.get('RESUME_SWEEPS', 0)) >= 8, g.get('RESUME_SWEEPS'))
ck('related source evidence is bounded', int(tx.MAX_CHARS) <= 120000, tx.MAX_CHARS)

prod = {'file': 'src/service.ts', 'rows': [{'file': 'src/service.ts', 'kind': 'functional_mock'}]}
test = {'file': 'tests/application.test.ts', 'rows': [{'file': 'tests/application.test.ts', 'kind': 'functional_test_coverage'}]}
ck('production attempts stay bounded', tx._attempt_limit(prod) == 4, tx._attempt_limit(prod))
ck('workflow tests get bounded extra retries', tx._attempt_limit(test) == 6, tx._attempt_limit(test))
ck('workflow guidance forbids invented helpers', 'Do not invent helper' in tx._workflow_test_guidance(test), tx._workflow_test_guidance(test))

prompt = ('ISSUE OWNER FILES: ["src/a.ts"]\n'
          'CURRENT CONTRACT FINDINGS: [{"kind":"functional_mock"}]\n'
          'AUTHORIZED VALIDATOR LOCATORS BY ISSUE OWNER:')
budget, target, owners, findings = io._adaptive_functional_output(
    {'_v426_route_for_call': lambda *a: ('27b38q2', 'manual')},
    prompt,
    'V42.66 functional transaction 1: src/a.ts',
    'repair',
    9000,
)
ck('27B production output is compact', budget <= 6144, (budget, target, owners, findings))

# Reproduce the live failure shape: one complete edit followed by an incomplete
# trailing edit. V42.66 may keep the complete first edit, but never reconstructs
# the incomplete source/string.
malformed = (
    '{"edits":['
    '{"file":"src/a.ts","replacements":[{"search":"const a = 1;","replace":"const a = 2;"}]},'
    '{"file":"src/b.ts","replacements":[{"search":"const b = 1;","replace":"const b = '
)
obj = tx.parse_object(malformed)
ck('malformed trailing output salvages one complete leading edit',
   len(obj.get('edits') or []) == 1 and obj['edits'][0].get('file') == 'src/a.ts', obj)

cluster = {
    'file': 'src/a.ts',
    'files': ['src/a.ts', 'src/b.ts', 'src/c.ts'],
    'cluster': True,
    'owner_groups': [
        {'file': 'src/a.ts', 'rows': [{'file':'src/a.ts','kind':'functional_mock'}], 'kinds':['functional_mock'], 'problems':['a']},
        {'file': 'src/b.ts', 'rows': [{'file':'src/b.ts','kind':'functional_mock'}], 'kinds':['functional_mock'], 'problems':['b']},
        {'file': 'src/c.ts', 'rows': [{'file':'src/c.ts','kind':'functional_mock'}], 'kinds':['functional_mock'], 'problems':['c']},
    ],
}
focus1 = v._single_owner_group(cluster, 1)
focus2 = v._single_owner_group(cluster, 2)
ck('first emission focuses a bounded owner set', len(tx._cluster_owner_files(focus1)) <= v.MODEL_OWNER_FOCUS, focus1)
ck('retry rotates owner focus', tx._cluster_owner_files(focus1) != tx._cluster_owner_files(focus2), (focus1, focus2))

print(f'V42.66 fast bounded repair checks passed: {passed}/12')
