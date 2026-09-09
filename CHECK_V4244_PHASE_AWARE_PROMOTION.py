from pathlib import Path
import json
import shutil
import tempfile

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
check("warm-cache strategy generation", active.STRATEGY_GENERATION == "functional-acceptance-v8-regression-safe-component-proof", active.STRATEGY_GENERATION)
check("active V42.46 marker", (ROOT / "JARVIS_ACTIVE_ENGINE.txt").read_text().strip() == "V42.50.0")

failure = r'''V36 COMPONENT FAILED [rust | rust | .]:
error[E0277]: the trait bound `Asset: sqlx::Decode<'_, Sqlite>` is not satisfied
   --> src\assets.rs:14:18
help: the trait `sqlx::Decode<'_, Sqlite>` is not implemented for `Asset`
   --> src\models\asset.rs:2:1
error[E0277]: the trait bound `Asset: sqlx::Type<Sqlite>` is not satisfied
   --> src\assets.rs:14:18
    = note: required for `(Asset, Option<std::string::String>)` to implement `for<'r> FromRow<'r, SqliteRow>`
error: could not compile `fixture` (lib) due to 2 previous errors
'''

source = '''use crate::models::Asset;
use sqlx::SqlitePool;

pub async fn get_asset_with_holder(pool: &SqlitePool, id: &str) -> Result<Option<(Asset, Option<String>)>, sqlx::Error> {
    let sql = r#"\n        SELECT a.*, p.name as holder_name\n        FROM assets a LEFT JOIN persons p ON a.holder_id = p.id\n        WHERE a.id = ?\n    "#;
    let result = sqlx::query_as(sql).bind(id).fetch_optional(pool).await?;
    Ok(result)
}
'''


def fixture(root: Path):
    (root / "src/models").mkdir(parents=True)
    (root / "src/models/asset.rs").write_text('''#[derive(Debug, sqlx::FromRow)]
pub struct Asset {
    pub id: String,
    pub name: String,
    pub location: String,
}
''', encoding="utf-8")
    (root / "src/assets.rs").write_text(source, encoding="utf-8")
    (root / "Cargo.toml").write_text('[package]\nname="fixture"\nversion="0.1.0"\nedition="2021"\n\n[dependencies]\nsqlx={version="0.8",features=["sqlite","derive"]}\n', encoding="utf-8")


def copy_candidate(root):
    handle = tempfile.TemporaryDirectory(prefix="jarvis_v4244_candidate_")
    clone = Path(handle.name) / "candidate"
    shutil.copytree(root, clone)
    return handle, clone


def fake_g(validator, proof):
    events = []
    return {
        "_v4236_native_diagnostics": lambda *_args, **_kwargs: [{"file": "src/assets.rs", "role": "primary"}],
        "_v4236_rank_native_targets": lambda *_args, **_kwargs: ["src/assets.rs", "src/models/asset.rs"],
        "_copy_project_for_candidate_validation": copy_candidate,
        "_v35_validate_component": validator,
        "_v4244_compile_phase_probe_override": proof,
        "_progress": lambda *args, **kwargs: None,
        "_v36_checkpoint_file": lambda *args, **kwargs: None,
        "_v413_mark_accepted": lambda *args, **kwargs: None,
        "_append_project_event": lambda *args, **kwargs: events.append((args, kwargs)),
        "events": events,
    }


component = {"id": "rust", "root": ".", "toolchain_adapter": "rust"}
manifest = {"components": [component]}

# Reproduce the observed V42.43 shape: full validator is false, but no compiler
# diagnostics are parseable because validation advanced to a later test/runtime gate.
with tempfile.TemporaryDirectory(prefix="jarvis_v4244_phase_green_") as td:
    root = Path(td)
    fixture(root)
    g = fake_g(
        lambda *_args, **_kwargs: (False, "test result: FAILED. 0 passed; 1 failed; 0 ignored"),
        lambda *_args, **_kwargs: {"available": True, "ok": True, "output": "cargo build PASS", "kind": "cargo_build"},
    )
    accepted, result = active.deterministic_component_transaction(g, "finish", manifest, root, failure, component)
    repaired = (root / "src/assets.rs").read_text()
    check("compile-phase proof promotes real source delta", accepted is True and result.get("result") == "committed_compile_phase", result)
    check("phase promotion records positive proof", result.get("phase_progress") is True and result.get("proof_kind") == "cargo_build", result)
    check("promoted source removes scalar tuple query_as", "sqlx::query(sql)" in repaired and "sqlx::query_as(sql)" not in repaired, repaired)
    check("downstream failure remains explicit rather than falsely green", result.get("validator_ok") is False, result)
    check("warm-compile event requests revalidation", any(args and args[1] == "v4245_warm_compile_progress_committed" for args, _ in g["events"]), g["events"])

# Parser-zero without a positive compile proof must remain fail-closed.
with tempfile.TemporaryDirectory(prefix="jarvis_v4244_phase_red_") as td:
    root = Path(td)
    fixture(root)
    original = (root / "src/assets.rs").read_text()
    g = fake_g(
        lambda *_args, **_kwargs: (False, "test harness could not start"),
        lambda *_args, **_kwargs: {"available": True, "ok": False, "output": "cargo build still failed", "kind": "cargo_build"},
    )
    accepted, result = active.deterministic_component_transaction(g, "finish", manifest, root, failure, component)
    check("failed full validator plus failed compile proof is rejected", accepted is False and result.get("result") == "compile_gate_failed_unclassified", result)
    check("failed proof cannot mutate accepted source", (root / "src/assets.rs").read_text() == original, result)

# A V42.44 exhausted same-source revision must reopen exactly once because V42.46
# installs a genuinely new warm-cache strategy generation.
with tempfile.TemporaryDirectory(prefix="jarvis_v4244_reopen_") as td:
    root = Path(td)
    (root / "src").mkdir()
    (root / "src/lib.rs").write_text("pub fn x() {}\n")
    component2 = {"id": "rust", "root": ".", "toolchain_adapter": "rust"}
    key = active.revision_key(component2, "same")
    old = {
        "version": "V42.44.0",
        "engine": "PHASE_AWARE_COMPILER_PROMOTION_FACTORY",
        "strategy_generation": "sqlx-joined-struct-row-v2-phase-aware",
        "revisions": {key: {
            "id": key, "repository_token": "same", "component": "rust", "component_root": ".", "adapter": "rust",
            "model_cycles": 2, "exhausted": True, "terminal": True, "attempts": [],
            "strategy_generation": "sqlx-joined-struct-row-v2-phase-aware",
        }},
    }
    (root / active.LEDGER_FILE).write_text(json.dumps(old))
    g = {"_utc_stamp": lambda: "TEST", "_v429_progress_token": lambda _root: "same"}
    ledger, record, _ = active._revision_record(g, root, component2, failure)
    check("V42.44 exhausted revision reopens for V42.46 strategy", not record.get("exhausted") and record.get("model_cycles") == 0, record)
    check("reopened record is stamped new strategy", record.get("strategy_generation") == active.STRATEGY_GENERATION, record)
    record["exhausted"] = True
    record["terminal"] = True
    active._save(root / active.LEDGER_FILE, ledger)
    _ledger, second, _ = active._revision_record(g, root, component2, failure)
    check("same V42.46 strategy remains bounded", second.get("exhausted") is True and second.get("terminal") is True, second)

print(f"V42.46 phase-aware promotion regression: {passed}/{passed} PASS")
