from pathlib import Path
import json, shutil, tempfile

import jarvis_v4236_repair as native
import jarvis_v4237_repair as tx
import jarvis_v4241_repair as controller
import jarvis_v4242_repair as active

ROOT = Path(__file__).resolve().parent
passed = 0


def check(name, condition, detail=None):
    global passed
    if not condition:
        raise AssertionError(f"{name}: {detail}")
    passed += 1
    print(f"PASS: {name}")


check("active V42.46 version", active.VERSION == "42.50.0", active.VERSION)
check("strategy generation declared", active.STRATEGY_GENERATION == "functional-acceptance-v8-regression-safe-component-proof", active.STRATEGY_GENERATION)
check("active marker V42.46", (ROOT / "JARVIS_ACTIVE_ENGINE.txt").read_text().strip() == "V42.50.0")

failure = r'''V36 COMPONENT FAILED [rust | rust | src-tauri]:
error[E0277]: the trait bound `Asset: sqlx::Decode<'_, Sqlite>` is not satisfied
   --> src\assets.rs:44:18
help: the trait `sqlx::Decode<'_, Sqlite>` is not implemented for `Asset`
   --> src\models\asset.rs:2:1
error[E0277]: the trait bound `Asset: sqlx::Type<Sqlite>` is not satisfied
   --> src\assets.rs:44:18
    = note: required for `(Asset, Option<std::string::String>)` to implement `for<'r> FromRow<'r, SqliteRow>`
error: could not compile `fixture` (lib) due to 2 previous errors
'''

with tempfile.TemporaryDirectory(prefix="jarvis_v4243_sqlx_") as td:
    root = Path(td)
    (root / "src/models").mkdir(parents=True)
    (root / "src/models/asset.rs").write_text('''#[derive(Debug, sqlx::FromRow)]
pub struct Asset {
    pub id: String,
    pub name: String,
    pub location: String,
}
''')
    source = '''use crate::models::Asset;
use sqlx::SqlitePool;

pub async fn get_asset_with_holder(pool: &SqlitePool, id: &str) -> Result<Option<(Asset, Option<String>)>, sqlx::Error> {
    let sql = r#"\n        SELECT a.*, p.name as holder_name\n        FROM assets a LEFT JOIN persons p ON a.holder_id = p.id\n        WHERE a.id = ?\n    "#;
    let result = sqlx::query_as(sql).bind(id).fetch_optional(pool).await?;
    Ok(result)
}
'''
    candidate, reasons = active._sqlx_joined_struct_candidate(root, source, failure, "src/assets.rs")
    check("generic SQLx joined-row strategy changes query site", candidate != source, candidate)
    check("query_as replaced by raw row query", "sqlx::query(sql)" in candidate and "sqlx::query_as(sql)" not in candidate, candidate)
    check("struct reconstructed from named columns", 'Asset {' in candidate and 'row.try_get("id")?' in candidate and 'row.try_get("name")?' in candidate, candidate)
    check("joined alias decoded separately", 'row.try_get("holder_name")?' in candidate, candidate)
    typed = source.replace("sqlx::query_as(sql)", "sqlx::query_as::<_, (Asset, Option<String>)>(sql)")
    typed_candidate, _ = active._sqlx_joined_struct_candidate(root, typed, failure, "src/assets.rs")
    check("typed query_as turbofish is removed safely", "sqlx::query(sql)" in typed_candidate and "query_as::<" not in typed_candidate, typed_candidate)
    check("strategy is not GearTrack/Tool hardcoded", "Tool" not in candidate and "GearTrack" not in " ".join(reasons), reasons)

rows = [
    {"file": "src/models/asset.rs", "role": "definition"},
    {"file": "src/assets.rs", "role": "primary"},
    {"file": "src/models/asset.rs", "role": "definition"},
]
ranked = native._rank_native_targets(rows, failure)
check("SQLx composite error prioritizes compiler primary site", ranked[0] == "src/assets.rs", ranked)

with tempfile.TemporaryDirectory(prefix="jarvis_v4243_reopen_") as td:
    root = Path(td)
    (root / "src-tauri/src").mkdir(parents=True)
    (root / "src-tauri/src/lib.rs").write_text("pub fn x() {}\n")
    old = {
        "version": "V42.42.2",
        "engine": "REVISION_SCOPED_CONVERGENCE_MEMORY_FACTORY",
        "revisions": {
            "fixture": {
                "id": "fixture", "repository_token": "same", "component": "rust",
                "component_root": "src-tauri", "adapter": "rust", "model_cycles": 2,
                "exhausted": True, "terminal": True, "attempts": [],
            }
        }
    }
    # Use the actual key expected by the active release.
    component = {"id": "rust", "root": "src-tauri", "toolchain_adapter": "rust"}
    key = active.revision_key(component, "same")
    old["revisions"][key] = old["revisions"].pop("fixture")
    old["revisions"][key]["id"] = key
    (root / active.LEDGER_FILE).write_text(json.dumps(old))
    g = {"_utc_stamp": lambda: "TEST", "_v429_progress_token": lambda _work: "same"}
    ledger, record, _ = active._revision_record(g, root, component, failure)
    check("old exhausted release reopens once for new strategy", not record["exhausted"] and record["model_cycles"] == 0, record)
    record["exhausted"] = True
    record["terminal"] = True
    active._save(root / active.LEDGER_FILE, ledger)
    _ledger, retained, _ = active._revision_record(g, root, component, failure)
    check("same strategy generation remains circuit-broken", retained["exhausted"] and retained["terminal"], retained)

with tempfile.TemporaryDirectory(prefix="jarvis_v4243_controller_") as td:
    root = Path(td)
    component = {"id": "rust", "root": ".", "toolchain_adapter": "rust"}
    g = {
        "_utc_stamp": lambda: "TEST",
        "_v429_progress_token": lambda _work: "same",
        "JARVIS_REPAIR_STRATEGY_GENERATION": active.STRATEGY_GENERATION,
    }
    token = "same"
    key = controller._failure_key(component, failure, token)
    old_ledger = {"version": "V42.41.0", "issues": {key: {
        "id": key, "repository_token": token, "component": "rust", "adapter": "rust",
        "diagnostic_count": 2, "attempts": [{"strategy": "compiler_directed_transaction", "result": "no_candidate"}],
        "model_cycles": 2, "exhausted": True,
    }}}
    (root / controller.LEDGER_FILE).write_text(json.dumps(old_ledger))
    _ledger, issue, _ = controller._ledger_issue(g, root, component, failure)
    check("nested V42.41 budget reopens under new strategy generation", issue["model_cycles"] == 0 and not issue["exhausted"] and not issue["attempts"], issue)

print(f"V42.46 SQLx/strategy-generation regression: {passed}/{passed} PASS")
