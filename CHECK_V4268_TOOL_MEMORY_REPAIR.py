from pathlib import Path
import json
import shutil
import tempfile

import jarvis_v4251_repair as tx
import jarvis_v4268_repair as v

passed = 0

def ck(name, condition, detail=""):
    global passed
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    passed += 1
    print("PASS", name)

ck("release constant is V42.68", v.VERSION == "42.68.0")
ck("engine is tool-using memory repair", v.ENGINE == "TOOL_USING_MEMORY_REPAIR_FACTORY")
ck("tool schema exposes bounded edit/search/diagnose interface",
   set(v._TOOL_SCHEMA["properties"]["action"]["enum"]) ==
   {"edit","search","view","references","symbol","diagnose"})

before = "const mockTools = [];\nfunction exportTools(){ return mockTools.length; }\n"
after = "function exportTools(){ return mockTools.length; }\n"
errs = v._local_closure_errors("src/a.ts", before, after)
ck("removed local binding with remaining references is caught",
   any("mockTools" in item and "references" in item for item in errs), errs)

unused = "const { getTools, createTool } = api;\ngetTools();\n"
errs = v._local_closure_errors("src/a.ts", "", unused)
ck("unused destructured binding is caught",
   any("createTool" in item and "never used" in item for item in errs), errs)

big = "x" * 5000
ck("whole-file rewrite is rejected for nontrivial existing file",
   bool(v._whole_file_rewrite_error(big, [{"search":"x"*4500,"replace":"y"}])))
ck("small coherent hunk remains allowed",
   not v._whole_file_rewrite_error(big, [{"search":"x"*300,"replace":"y"}]))

action = v._parse_action('{"action":"search","query":"getTools"}')
ck("tool action parser accepts valid search", action["query"] == "getTools")
try:
    v._parse_action('{"action":"search","query":"x","shell":"rm"}')
    bad = False
except ValueError:
    bad = True
ck("tool action parser rejects unsupported fields", bad)

temp = Path(tempfile.mkdtemp(prefix="jarvis_v4268_check_"))
try:
    job = temp / "job"
    trial1 = job / "trial_01"
    trial2 = job / "trial_02"
    for trial in (trial1, trial2):
        (trial / "src").mkdir(parents=True)
        (trial / "src" / "a.ts").write_text(
            "const mockTools=[];\nfunction f(){ return mockTools.length; }\n",
            encoding="utf-8",
        )
        (trial / "src" / "provider.ts").write_text(
            "export function getTools(){ return []; }\n",
            encoding="utf-8",
        )
    (trial1 / "node_modules").mkdir()
    (trial1 / "node_modules" / "leak.ts").write_text(
        "export const DO_NOT_INDEX='secretneedle';\n", encoding="utf-8"
    )

    group = {"file":"src/a.ts","rows":[{"file":"src/a.ts","kind":"functional_mock","problem":"use real provider"}]}
    v._remember(trial1, "src/a.ts", group, before, "diagnostics", "TS6198 createTool unused", 1, 1)
    ck("trial memory database is shared across sweeps",
       v._memory_path(trial1) == v._memory_path(trial2),
       (v._memory_path(trial1), v._memory_path(trial2)))
    summary = v._memory_summary(trial2, "src/a.ts", group, before)
    ck("current diagnostics persist into next trial", "TS6198" in summary, summary)
    ck("portable checkpoint repair memory is written",
       v._portable_memory_path(trial1).exists(), v._portable_memory_path(trial1))

    search = v._repo_search(trial1, "getTools")
    ck("repository search finds authored provider source", "provider.ts" in search, search)
    search = v._repo_search(trial1, "secretneedle")
    ck("repository search excludes node_modules", "DO_NOT_INDEX" not in search, search)

    refs = v._references(trial1, "mockTools")
    ck("reference tool returns current authored references", "src/a.ts" in refs, refs)
    symbol = v._symbol_definition(trial1, "getTools")
    ck("symbol tool finds function definition", "provider.ts" in symbol, symbol)

    diff = v._compact_diff("const a=1;", "const a=2;", "src/a.ts")
    ck("compact diff reports targeted change", "-const a=1;" in diff and "+const a=2;" in diff, diff)

    old_delta = tx._cluster_functional_delta
    old_owner_files = tx._cluster_owner_files
    try:
        tx._cluster_owner_files = lambda g: ["src/a.ts"]
        tx._cluster_functional_delta = lambda *a, **k: {
            "improved": False,
            "after": [{"file":"src/a.ts","kind":"functional_mock","problem":"still mock"}],
        }
        functional = v._functional_preflight(trial1, trial1, "finish", {}, group)
        ck("functional debt is fed back before ending model session",
           functional and "does not yet reduce" in functional[0], functional)
    finally:
        tx._cluster_functional_delta = old_delta
        tx._cluster_owner_files = old_owner_files

    old_model = tx._model_candidate
    old_repair = tx.repair_transaction
    old_prepare = tx.prepare_candidate_workspace
    try:
        g = {
            "_v36_release_identity": lambda: {"version":"V42.67.0"},
            "_progress": lambda *a, **k: None,
            "JARVIS_DIR": temp,
        }
        v.install(g)
        ident = g["_v36_release_identity"]()
        ck("installed identity reports V42.68", ident.get("version") == "V42.68.0", ident)
        ck("identity confirms durable repair memory",
           ident.get("durable_project_repair_memory") is True, ident)
        ck("identity confirms same-transaction refinement",
           ident.get("same_transaction_draft_refinement") is True, ident)
        ck("identity confirms arbitrary model shell remains disabled",
           ident.get("arbitrary_model_shell_access") is False, ident)
    finally:
        tx._model_candidate = old_model
        tx.repair_transaction = old_repair
        tx.prepare_candidate_workspace = old_prepare
finally:
    shutil.rmtree(temp, ignore_errors=True)

print(f"V42.68 tool-using memory repair checks passed: {passed}/22")
