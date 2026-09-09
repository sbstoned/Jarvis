"""Jarvis-Bench V37: repeatable end-to-end project-generation benchmark.

Examples:
  python JARVIS_BENCH_V37.py --list
  python JARVIS_BENCH_V37.py --limit 1
  python JARVIS_BENCH_V37.py --ids python_cli,stockpilot

Each selected case runs the real local Qwen pipeline and records elapsed time, result status,
returned ZIP, and final message in generated_projects/JARVIS_BENCH_V37_RESULTS.json.
"""
import argparse, json, time, traceback
from pathlib import Path
import local_qwen_project as jarvis

CASES = [
    ('taskforge','Build a complete production-quality local application named TaskForge for Windows. Frontend: React + TypeScript + Vite. Backend: Python 3 + FastAPI. Database: SQLite. Frontend and backend must be separate components in one repository. Include complete project/task CRUD, search/filter/sort, dashboard statistics, persistence, validation, meaningful frontend/backend tests, clean dependency setup, production frontend build, backend startup/API behavior, matching TypeScript/Pydantic contracts, Windows setup/build/run scripts, and package only after all executable acceptance gates pass.'),
    ('python_cli','Build a complete Python 3 command-line calculator with add, subtract, multiply, divide, input validation, automated unittest coverage, README, and Windows run/build scripts. Validate from a clean environment and package only after all tests pass.'),
    ('stockpilot','Build a complete production-quality Windows desktop inventory manager named StockPilot using Python 3, Tkinter/ttk, and SQLite. Include layered UI/service/models/database/validation/CSV/reporting architecture, add/edit/delete/search/sort/filter, stock adjustments with history, low/out-of-stock reporting, persistence, meaningful automated tests, clean-environment dependency validation, runtime smoke testing, and no duplicate competing providers. Package only after executable acceptance gates pass.'),
    ('fastapi','Build a complete FastAPI + SQLite REST API for tasks with CRUD, validation, migrations/init, pytest tests, health endpoint, README and Windows launch/build scripts. Use a clean environment and validate real API behavior before packaging.'),
    ('react','Build a complete React + Vite TypeScript personal budget dashboard with local persistence, add/edit/delete transactions, category filters, summaries, validation, Vitest tests, production build, and README. Validate npm install/build/test before packaging.'),
    ('node_api','Build a complete Node.js TypeScript REST API for notes using Express and SQLite, with CRUD, validation, health endpoint, automated tests, clean npm install/build/test/start validation and README.'),
    ('rust_cli','Build a complete Rust CLI meal planner using Cargo, local JSON persistence, CRUD meals, weekly plan generation, input validation, unit tests, README, and real cargo build/test validation.'),
    ('cpp_cmake','Build a complete C++17 CMake console inventory application with models, service, file persistence, validation, tests using CTest, README and real configure/build/test/run validation.'),
    ('dotnet','Build a complete .NET C# console expense tracker with JSON persistence, service/model separation, validation, xUnit tests, README and real dotnet restore/build/test/run validation.'),
    ('flutter','Build a complete Flutter mobile habit tracker with local persistence, add/edit/delete habits, streak tracking, validation, widget/unit tests and README. Run pub get/analyze/test and report host-limited platform build checks honestly.'),
    ('tauri','Build a complete Tauri desktop notes application with a Vite TypeScript frontend and Rust backend, local persistence, CRUD notes, search, validation, frontend tests and Rust tests. Validate BOTH Node and Cargo components before packaging.'),
    ('sveltekit','Build a complete SvelteKit TypeScript recipe organizer with local persistence, add/edit/delete/search recipes, validation, automated tests, production build and README.'),
    ('go_api','Build a complete Go REST API for bookmarks with JSON persistence, CRUD, validation, health endpoint, go tests, README and real go test/build/start validation.'),
]

def progress(message=None, **kwargs):
    if message: print(message, flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--list',action='store_true');ap.add_argument('--limit',type=int,default=0);ap.add_argument('--ids',default='')
    args=ap.parse_args()
    if args.list:
        for cid,_ in CASES: print(cid)
        return
    selected=CASES
    if args.ids:
        wanted={x.strip() for x in args.ids.split(',') if x.strip()};selected=[x for x in CASES if x[0] in wanted]
    if args.limit>0:selected=selected[:args.limit]
    out_path=jarvis.GENERATED_DIR/'JARVIS_BENCH_V37_RESULTS.json'
    results=[]
    for idx,(cid,prompt) in enumerate(selected,1):
        print(f'\n=== [{idx}/{len(selected)}] {cid} ===',flush=True);started=time.monotonic()
        try:
            ok,msg,zpath=jarvis.generate_project_zip(prompt,progress_callback=progress)
            result={'id':cid,'ok':bool(ok),'seconds':round(time.monotonic()-started,2),'minutes':round((time.monotonic()-started)/60,2),'message':str(msg),'zip':str(zpath or '')}
        except Exception as exc:
            result={'id':cid,'ok':False,'seconds':round(time.monotonic()-started,2),'message':f'{type(exc).__name__}: {exc}','traceback':traceback.format_exc()[-6000:]}
        results.append(result);out_path.write_text(json.dumps({'version':'V37.0.0','results':results},indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2),flush=True)
    passed=sum(1 for x in results if x.get('ok'))
    print(f'\nJarvis-Bench V37: {passed}/{len(results)} generation runs reached Jarvis COMPLETE.')
    print(f'Results: {out_path}')
if __name__=='__main__':main()
