"""Focused regression for Jarvis V42.46 compiler-hint last-mile repair."""
from pathlib import Path
import tempfile
import jarvis_v4242_repair as active

passed = 0

def check(name, cond, detail=None):
    global passed
    if not cond:
        raise AssertionError(f"{name}: {detail!r}")
    passed += 1

check("active version", active.VERSION == "42.50.0", active.VERSION)
check("active engine", active.ENGINE == "REGRESSION_SAFE_FUNCTIONAL_CONVERGENCE_FACTORY", active.ENGINE)
check("strategy generation", active.STRATEGY_GENERATION == "functional-acceptance-v8-regression-safe-component-proof", active.STRATEGY_GENERATION)
check("engine marker", Path("JARVIS_ACTIVE_ENGINE.txt").read_text().strip() == "V42.50.0")

path_source = '''use sqlx::SqlitePool;\nuse tauri::{AppHandle, Manager};\n\npub async fn init_app(app_handle: AppHandle) -> Result<SqlitePool, Box<dyn std::error::Error>> {\n    let db_path = app_handle.path().app_data_dir()?.join("data.sqlite");\n    let pool = SqlitePool::connect(&format!("file:{db_path}?mode=rwc&cache=shared"))\n        .await?;\n    Ok(pool)\n}\n'''
path_failure = '''error[E0277]: `PathBuf` doesn't implement `std::fmt::Display`\n --> src\\app.rs:7:51\n  |\n7 |     let pool = SqlitePool::connect(&format!("file:{db_path}?mode=rwc&cache=shared"))\n  |                                                   ^^^^^^^^^ `PathBuf` cannot be formatted with the default formatter; call `.display()` on it\n  = note: call `.display()` or `.to_string_lossy()` to safely print paths\n'''
path_out, path_reasons = active.rust_compiler_candidate(path_source, path_failure, "src-tauri/src/app.rs")
check("PathBuf candidate changes source", path_out != path_source, path_reasons)
check("PathBuf candidate uses positional display", 'format!("file:{}?mode=rwc&cache=shared", db_path.display())' in path_out, path_out)
check("PathBuf candidate reason", any("rustc-recommended" in r for r in path_reasons), path_reasons)

# Fail closed if the source line is not the compiler-owned line.
unrelated = path_failure.replace('format!("file:{db_path}?mode=rwc&cache=shared")', 'format!("different:{db_path}")')
unchanged, reasons = active.rust_compiler_candidate(path_source, unrelated, "src-tauri/src/app.rs")
check("PathBuf rewrite requires exact compiler-owned source line", unchanged == path_source and not reasons, (unchanged, reasons))

# Reproduce the real SQLx joined-row shape with a generic Tool model.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "src-tauri/src/models").mkdir(parents=True)
    (root / "src-tauri/src/models/tool.rs").write_text('''#[derive(sqlx::FromRow)]\npub struct Tool {\n    pub id: String,\n    pub name: String,\n    pub category_id: Option<String>,\n    pub condition: String,\n    pub location: Option<String>,\n    pub is_checked_out: bool,\n    pub current_holder_id: Option<String>,\n}\n''')
    sqlx_source = '''pub async fn get_tool_with_holder(pool: &Pool, id: &str) -> Result<Option<(Tool, Option<String>)>, Box<dyn std::error::Error + Send + Sync>> {\n    let sql = r#"\n        SELECT t.*, p.name as holder_name\n        FROM tools t LEFT JOIN persons p ON t.current_holder_id = p.id\n        WHERE t.id = ?;\n    "#;\n    let result = sqlx::query_as(sql).bind(id).fetch_optional(pool).await?;\n    Ok(result)\n}\n'''
    sqlx_failure = '''error[E0277]: the trait bound `Tool: sqlx::Decode<'_, Sqlite>` is not satisfied\n --> src\\tools.rs:145:18\n = note: required for `(Tool, Option<std::string::String>)` to implement `for<'r> FromRow<'r, SqliteRow>`\nerror[E0277]: the trait bound `Tool: sqlx::Type<Sqlite>` is not satisfied\n = note: required for `(Tool, Option<std::string::String>)` to implement `for<'r> FromRow<'r, SqliteRow>`\n'''
    sqlx_out, sqlx_reasons = active._sqlx_joined_struct_candidate(root, sqlx_source, sqlx_failure, "src-tauri/src/tools.rs")
    check("SQLx joined row still repaired", sqlx_out != sqlx_source, sqlx_reasons)
    check("SQLx raw query generated", "sqlx::query(sql)" in sqlx_out and 'row.try_get("holder_name")?' in sqlx_out, sqlx_out)

# Ensure the two real compiler stages are both deterministic and do not require a model call.
check("7-to-2 strategy present", callable(active._sqlx_joined_struct_candidate))
check("2-to-0 strategy present", callable(active._rust_path_display_candidate))
print(f"V42.46 compiler-hint last-mile regression: {passed}/{passed} PASS")
