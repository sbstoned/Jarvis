from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jarvis_v4251_repair as tx
import jarvis_v4259_repair as io
import jarvis_v4267_repair as v

passed = 0

def ck(name, condition, detail=""):
    global passed
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    passed += 1
    print("PASS", name)

cluster = {
    "file": "src/a.ts",
    "key": "cluster",
    "cluster": True,
    "owner_groups": [
        {"file": "src/a.ts", "key": "a", "rows": [{"file":"src/a.ts","kind":"functional_mock"}], "kinds":["functional_mock"], "problems":["a"]},
        {"file": "src/b.ts", "key": "b", "rows": [{"file":"src/b.ts","kind":"functional_mock"}], "kinds":["functional_mock"], "problems":["b"]},
        {"file": "src/c.ts", "key": "c", "rows": [{"file":"src/c.ts","kind":"functional_mock"}], "kinds":["functional_mock"], "problems":["c"]},
        {"file": "src/d.ts", "key": "d", "rows": [{"file":"src/d.ts","kind":"functional_mock"}], "kinds":["functional_mock"], "problems":["d"]},
    ],
}

first = v._focus_group(cluster, [])
second = v._focus_group(cluster, ["prior rejection"])
ck("focus happens at one owner", len(v._owner_groups(first)) == 1, first)
ck("retry rotates outer owner", first["file"] != second["file"], (first, second))

evidence = {
    "src/a.ts": "A" * 12000,
    "src/provider.ts": "P" * 12000,
    "src/runtime.ts": "R" * 12000,
    "src/unrelated.ts": "U" * 12000,
}
selected = v._select_evidence(evidence, "src/a.ts")
ck("target is retained", "src/a.ts" in selected, selected.keys())
ck("related file count is bounded", len(selected) <= 1 + v.RELATED_FILE_LIMIT, selected.keys())
ck("selected evidence obeys char cap",
   sum(len(str(x)) for x in selected.values()) <= v.OWNER_EVIDENCE_CHARS,
   sum(len(str(x)) for x in selected.values()))

prod = {"file":"src/a.ts","rows":[{"file":"src/a.ts","kind":"functional_mock"}],"kinds":["functional_mock"]}
workflow = {"file":"tests/application.test.ts","rows":[{"file":"tests/application.test.ts","kind":"functional_test_coverage"}],"kinds":["functional_test_coverage"]}
ck("production classification ignores unrelated test text", v._repair_class(prod) == "production")
ck("workflow owner is explicit", v._repair_class(workflow) == "workflow_test")
ck("27B first production budget is 3072", v._budget_for("27b38q2","production",1) == 3072)
ck("27B production escalation is bounded", v._budget_for("27b38q2","production",99) == 6144)
ck("workflow budget remains available", v._budget_for("27b38q2","workflow_test",3) == 8192)

raw = (
    '{"replacements":['
    '{"search":"const a = 1;","replace":"const a = 2;"},'
    '{"search":"const b = 1;","replace":"const b = '
)
obj = v._parse_compact_replacements(raw)
ck("malformed compact tail salvages complete leading hunk",
   len(obj["replacements"]) == 1 and obj["replacements"][0]["search"] == "const a = 1;", obj)

good = v._parse_compact_replacements(json.dumps({
    "replacements":[{"search":"old","replace":"new"}]
}))
ck("valid compact transport parses", good["replacements"][0]["replace"] == "new")

orig_repair = tx.repair_transaction
orig_model = tx._model_candidate
orig_adaptive = io._adaptive_functional_output
orig_max_chars = tx.MAX_CHARS
try:
    tx.repair_transaction = lambda *a, **k: (False, ["stub"])
    tx._model_candidate = lambda *a, **k: {"src/a.ts":"stub"}
    io._adaptive_functional_output = lambda g,p,s,pr,requested=None: (8192, "27b38q2", 4, 4)
    g = {
        "_v36_release_identity": lambda: {"version":"V42.66.0"},
        "_progress": lambda *a, **k: None,
        "JARVIS_DIR": ROOT,
    }
    v.install(g)
    ident = g["_v36_release_identity"]()
    ck("release identity is V42.67", ident.get("version") == "V42.67.0", ident)
    ck("owner evidence cap is active", int(ident.get("owner_evidence_char_cap", 0)) <= 42000, ident)
    v._CALL.repair_class = "production"
    v._CALL.attempt = 1
    budget, target, owners, findings = io._adaptive_functional_output(
        {}, "prompt mentions functional_test_coverage elsewhere",
        "V42.67 functional transaction 1: src/a.ts", "repair", 9000
    )
    ck("production 27B budget cannot be promoted by unrelated test text",
       budget == 3072 and owners == 1 and findings == 1,
       (budget,target,owners,findings))
finally:
    tx.repair_transaction = orig_repair
    tx._model_candidate = orig_model
    io._adaptive_functional_output = orig_adaptive
    tx.MAX_CHARS = orig_max_chars

print(f"V42.67 owner-local compact repair checks passed: {passed}/15")
