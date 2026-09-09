"""Jarvis V42.47 functional acceptance convergence.

Compilation is necessary but not sufficient.  This layer turns runtime seams,
persistence contracts, production mocks, and meaningful workflow tests into
first-class whole-project acceptance debt.  It is intentionally adapter based:
framework-specific evidence is detected conservatively and converted into the
same generic repair/audit machinery used by every other stack.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

VERSION = "42.47.0"
ENGINE = "FUNCTIONAL_ACCEPTANCE_CONVERGENCE_FACTORY"
STRATEGY_GENERATION = "functional-acceptance-v5-runtime-seams-persistence-workflow-proof"
REPORT_FILE = "JARVIS_V4247_FUNCTIONAL_ACCEPTANCE.json"

_TEXT_SUFFIXES = {'.rs','.ts','.tsx','.js','.jsx','.mts','.cts','.py','.sql','.toml','.json','.html'}
_SKIP_DIRS = {'node_modules','target','dist','build','.git','.jarvis_runtime','.jarvis_build','__pycache__'}


def _norm(rel: object) -> str:
    return str(rel or '').replace('\\','/').strip('/')


def _source_files(root: Path) -> Iterable[Tuple[str, Path, str]]:
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        try:
            rel=p.relative_to(root).as_posix()
        except Exception:
            continue
        if any(part.lower() in _SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if rel.startswith('JARVIS_') or '/JARVIS_' in rel:
            continue
        try:text=p.read_text(encoding='utf-8',errors='replace')
        except Exception:continue
        yield rel,p,text


def _strip_js_comments(text: str) -> str:
    text=re.sub(r'/\*.*?\*/','',str(text or ''),flags=re.S)
    text=re.sub(r'(?m)//.*$','',text)
    return text


def _pick_tauri_entry(root: Path) -> str:
    for rel in ('src-tauri/src/lib.rs','src-tauri/src/main.rs'):
        if (root/rel).is_file(): return rel
    for p in (root/'src-tauri').rglob('*.rs') if (root/'src-tauri').is_dir() else []:
        try:return p.relative_to(root).as_posix()
        except Exception:pass
    return ''


def _tauri_bridge_issues(root: Path, files: List[Tuple[str,Path,str]]) -> List[dict]:
    if not (root/'src-tauri').is_dir(): return []
    ts=[];rust=[]
    for rel,_,text in files:
        if rel.startswith('src-tauri/') and rel.endswith('.rs'):rust.append((rel,text))
        elif Path(rel).suffix.lower() in {'.ts','.tsx','.js','.jsx','.mts','.cts'}:ts.append((rel,text))
    invoked=set()
    invoke_files={}
    # Direct invoke("name") plus common thin wrappers such as createTauriCommand("name").
    call_re=re.compile(r'\b(?:invoke(?:\s*<[^;\n>]+>)?|createTauriCommand)\s*\(\s*[\'\"]([A-Za-z0-9_:\-.]+)[\'\"]')
    for rel,text in ts:
        code=_strip_js_comments(text)
        for m in call_re.finditer(code):
            name=m.group(1);invoked.add(name);invoke_files.setdefault(name,rel)
    if not invoked:return []
    all_rust='\n'.join(text for _,text in rust)
    commands=set(re.findall(r'#\s*\[\s*tauri::command(?:\([^\]]*\))?\s*\]\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_][A-Za-z0-9_]*)',all_rust,re.S))
    registered=set()
    for body in re.findall(r'generate_handler!\s*\[([^\]]*)\]',all_rust,re.S):
        for token in re.findall(r'(?:[A-Za-z_][A-Za-z0-9_]*::)*([A-Za-z_][A-Za-z0-9_]*)',body):registered.add(token)
    has_handler=bool(re.search(r'\.invoke_handler\s*\(',all_rust))
    entry=_pick_tauri_entry(root)
    issues=[]
    missing=sorted(invoked - registered)
    if not has_handler or missing:
        shown=', '.join(missing[:24])
        problem=(
            'FUNCTIONAL BRIDGE CONTRACT: the frontend invokes real Tauri commands but the Rust application does not '
            'register a matching invoke_handler contract. '
            f'Frontend command names include: {", ".join(sorted(invoked)[:24])}. '
            + (f'Missing registered commands: {shown}. ' if shown else '')
            + 'Implement #[tauri::command] wrappers with matching command names/argument contracts, register them with '
              'tauri::generate_handler![...], and wire any required application state. Compilation alone is not acceptance: '
              'the frontend-to-backend call path must be executable.'
        )
        issues.append({'file':entry or next(iter(invoke_files.values()),''),'kind':'functional_bridge','problem':problem,'evidence':'frontend invoke names vs Rust handler registration'})
    # If SQLx-backed Tauri services exist, a pool/init function must actually be installed into the running builder.
    uses_sqlx=bool(re.search(r'\bSqlitePool\b|\bPool\s*<\s*Sqlite\s*>',all_rust))
    if uses_sqlx:
        builder_text='\n'.join(text for rel,text in rust if rel in {'src-tauri/src/lib.rs','src-tauri/src/main.rs'} or 'app.rs' in rel)
        state_wired=bool(re.search(r'\.manage\s*\(',builder_text))
        setup_wired=bool(re.search(r'\.setup\s*\(',builder_text))
        init_defined=bool(re.search(r'\b(?:init_app|init_db)\s*\(',all_rust))
        if init_defined and not (state_wired and setup_wired):
            issues.append({'file':entry,'kind':'functional_runtime_state','problem':
                'FUNCTIONAL RUNTIME STATE CONTRACT: this Tauri project contains SQLx persistence initialization, but the running tauri::Builder does not visibly call setup and manage the initialized database state. Wire application startup so the database is opened/migrated before commands run and expose the pool/state to command handlers. A smoke-alive process without initialized feature state is not complete.'})
    return issues


def _production_mock_issues(root: Path, files: List[Tuple[str,Path,str]]) -> List[dict]:
    backend_present=(root/'src-tauri').is_dir() or any((root/x).exists() for x in ('server','backend','api'))
    if not backend_present:return []
    out=[]
    integration_re=re.compile(r'\b(?:invoke|fetch|createTauriCommand|useTauriCommands)\s*\(|\baxios\.|\bipcRenderer\.|\bsupabase\.|\bfirebase\.',re.I)
    mock_re=re.compile(r'\b(?:simulate(?:d|s|ing)?|mock(?:ed|ing|data|backend)?|for demonstration|in (?:a )?(?:real|full) implementation|placeholder backend|fake backend)\b',re.I)
    for rel,_,text in files:
        low='/'+rel.lower().strip('/')+'/'
        if not any(seg in low for seg in ('/src/hooks/','/src/services/','/src/api/','/src/repositories/','/src/data/','/app/services/','/lib/services/')):continue
        if '/tests/' in low or '.test.' in low or '.spec.' in low:continue
        if not mock_re.search(text):continue
        code=_strip_js_comments(text)
        if integration_re.search(code):continue
        # A production integration module that explicitly admits simulation and has no real I/O seam is acceptance debt.
        out.append({'file':rel,'kind':'functional_mock','problem':
            'FUNCTIONAL IMPLEMENTATION CONTRACT: this production hook/service explicitly contains simulated/mock/demo behavior but no real backend/network/persistence call in executable code. Replace demonstration/local-only behavior with the project\'s real integration seam while preserving the public hook/service API. Do not satisfy this gate by deleting comments or renaming mock variables; the feature must persist/read real application data.'})
    return out


def _ddl_schema(files: List[Tuple[str,Path,str]]) -> Dict[str,set]:
    schema={}
    for _,_,text in files:
        for m in re.finditer(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"`\]]?\s*\((.*?)\)\s*(?:;|[\"#])',text,re.I|re.S):
            table=m.group(1).lower();body=m.group(2);cols=set()
            # DDL in this builder is formatted one declaration per comma/line. Ignore table constraints.
            for piece in re.split(r',(?=(?:[^()]*\([^()]*\))*[^()]*$)',body):
                part=piece.strip()
                cm=re.match(r'[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)[\"`\]]?\s+',part)
                if not cm:continue
                col=cm.group(1).lower()
                if col in {'primary','foreign','unique','constraint','check'}:continue
                cols.add(col)
            if cols:schema.setdefault(table,set()).update(cols)
    return schema


def _rust_struct_fields(files: List[Tuple[str,Path,str]]) -> Dict[str,set]:
    out={}
    for _,_,text in files:
        for m in re.finditer(r'(?s)(?:#\s*\[[^\]]*\]\s*)*pub\s+struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*?)\}',text):
            fields=set(re.findall(r'\bpub\s+([A-Za-z_][A-Za-z0-9_]*)\s*:',m.group(2)))
            if fields:out[m.group(1)]=fields
    return out


def _sql_contract_issues(files: List[Tuple[str,Path,str]]) -> List[dict]:
    schema=_ddl_schema(files);structs=_rust_struct_fields(files);out=[];seen=set()
    def add(rel,kind,problem):
        key=(rel,kind,problem)
        if key not in seen:seen.add(key);out.append({'file':rel,'kind':kind,'problem':problem})
    for rel,_,text in files:
        if not rel.endswith('.rs'):continue
        # Unknown DML columns are guaranteed runtime failures even when Rust compiles.
        for m in re.finditer(r'UPDATE\s+([A-Za-z_][A-Za-z0-9_]*)\s+SET\s+(.*?)(?:\s+WHERE\s+|[;\"#])',text,re.I|re.S):
            table=m.group(1).lower()
            if table not in schema:continue
            cols=set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*=',m.group(2)))
            bad=sorted(c.lower() for c in cols if c.lower() not in schema[table])
            if bad:add(rel,'persistence_schema',f'PERSISTENCE SCHEMA CONTRACT: UPDATE targets table {table} column(s) {bad}, but CREATE TABLE defines only {sorted(schema[table])}. Reconcile the schema and DML based on the intended feature; do not leave a query that can compile but fails at runtime.')
        for m in re.finditer(r'INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)',text,re.I|re.S):
            table=m.group(1).lower()
            if table not in schema:continue
            cols=[re.sub(r'[^A-Za-z0-9_]','',x).lower() for x in m.group(2).split(',')]
            bad=sorted(c for c in cols if c and c not in schema[table])
            if bad:add(rel,'persistence_schema',f'PERSISTENCE SCHEMA CONTRACT: INSERT targets table {table} column(s) {bad} absent from the declared table schema {sorted(schema[table])}.')
        from jarvis_sql_contracts import sqlx_returning_issues
        out.extend(sqlx_returning_issues(rel,text))
        # String "null" is not SQL NULL. Keep this high-confidence and persistence-specific.
        if re.search(r'\.bind\s*\(\s*[\"\']null[\"\']\s*\)',text,re.I):
            add(rel,'persistence_null_semantics','PERSISTENCE NULL CONTRACT: executable SQL binds the literal string "null" as data. Use a typed Option/SQL NULL when clearing nullable fields; the text value "null" can violate foreign keys and produces incorrect persisted state.')
        # Rust sqlx FromRow projection completeness for explicit SELECT lists.
        pat=re.compile(r'query_as\s*::\s*<\s*_\s*,\s*([A-Za-z_][A-Za-z0-9_:]*)\s*>\s*\(\s*(?:r#+)?[\"\']\s*SELECT\s+(.*?)\s+FROM\s+',re.I|re.S)
        for m in pat.finditer(text):
            struct=m.group(1).split('::')[-1];fields=structs.get(struct)
            if not fields:continue
            projection=m.group(2).strip()
            if projection=='*' or '.*' in projection:continue
            selected=set()
            for part in projection.split(','):
                token=part.strip().split()[-1] if re.search(r'\s+as\s+',part,re.I) else part.strip().split('.')[-1].split()[0]
                token=re.sub(r'[^A-Za-z0-9_]','',token)
                if token:selected.add(token)
            missing=sorted(fields-selected)
            if missing:add(rel,'persistence_row_shape',f'PERSISTENCE ROW SHAPE CONTRACT: query_as decodes {struct}, but the explicit SELECT projection omits struct field(s) {missing}. Select every required FromRow field or decode into a purpose-specific row type.')
    return out


def _meaningful_test_issues(root: Path, files: List[Tuple[str,Path,str]], bridge_issues: List[dict], manifest=None, request='') -> List[dict]:
    from jarvis_workflow_contracts import workflow_issues
    return workflow_issues(((rel,text) for rel,_,text in files), manifest, bridge_issues, request)


def functional_acceptance_issues(work, user_request='', manifest=None) -> List[dict]:
    root=Path(work).resolve();files=list(_source_files(root));issues=[]
    bridge=_tauri_bridge_issues(root,files);issues.extend(bridge)
    issues.extend(_production_mock_issues(root,files))
    issues.extend(_sql_contract_issues(files))
    issues.extend(_meaningful_test_issues(root,files,bridge,manifest,user_request))
    # Stable de-duplication and bounded issue volume so repair remains convergent.
    seen=set();out=[]
    for row in issues:
        rel=_norm(row.get('file'));problem=re.sub(r'\s+',' ',str(row.get('problem') or '')).strip();kind=str(row.get('kind') or 'functional_contract')
        if not rel or not problem:continue
        key=(rel,kind,problem)
        if key in seen:continue
        seen.add(key);out.append({**row,'file':rel,'kind':kind,'problem':problem})
    return out[:48]


def _write_report(g: dict, work: Path, issues: List[dict], user_request: str) -> None:
    payload={
        'version':'V'+VERSION,'engine':ENGINE,'updated_at':g['_utc_stamp'](),
        'clean':not bool(issues),'issue_count':len(issues),'issues':issues,
        'acceptance_policy':{
            'compile_success_is_not_completion':True,
            'runtime_seams_must_be_bound':True,
            'persistence_contracts_must_be_coherent':True,
            'production_mock_implementations_are_rejected':True,
            'meaningful_workflow_test_required_when_cross_boundary_runtime_exists':True,
        },
        'request_excerpt':str(user_request or '')[:2000],
    }
    try:(work/REPORT_FILE).write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    except Exception:pass


def install(g: dict) -> None:
    previous_audit=g['_v429_whole_project_audit']
    previous_priority=g['_v429_issue_priority']
    previous_repair_round=g['_v429_repair_audit_round']
    previous_qwen=g['_qwen_call']
    previous_identity=g['_v36_release_identity']
    previous_skills=g['_v36_stack_skill_names']
    previous_progress=g['_progress']
    previous_append=g['_append_project_event']
    previous_generate=g['generate_project_zip']
    previous_edit=g['analyze_and_edit_project_zip']

    g['JARVIS_REPAIR_STRATEGY_GENERATION']=STRATEGY_GENERATION
    try:
        import jarvis_v4240_repair as v4240
        v4240.VERSION=VERSION;v4240.ENGINE=ENGINE
    except Exception:pass

    def append_event(work,event_type,message,**fields):
        values=dict(fields);values['engine_version']='V'+VERSION
        rendered=re.sub(r'\bV42\.46(?:\.0)?\b','V42.47',str(message or ''))
        return previous_append(work,event_type,rendered,**values)

    def progress(callback,text=None,**fields):
        rendered=re.sub(r'\bV42\.46(?:\.0)?\b','V42.47',str(text or ''))
        values=dict(fields);values['engine_version']='V'+VERSION
        return previous_progress(callback,rendered,**values)

    def issue_priority(manifest,row):
        base=previous_priority(manifest,row)
        kind=str((row or {}).get('kind') or '')
        rel=_norm((row or {}).get('file'))
        if kind.startswith('functional_') or kind.startswith('persistence_'):
            # Production runtime contracts rank after syntax/missing files but before tests.
            if '/tests/' in '/'+rel.lower() or '.test.' in rel.lower() or '.spec.' in rel.lower():return (48,base[1],base[2],rel)
            return (2,base[1],base[2],rel)
        return base

    def audit(work,user_request,manifest,run_components=True,progress_callback=None):
        payload=previous_audit(work,user_request,manifest,run_components,progress_callback)
        issues=functional_acceptance_issues(work,user_request,manifest)
        _write_report(g,Path(work).resolve(),issues,user_request)
        if issues:
            existing={(str(x.get('file') or ''),str(x.get('kind') or ''),str(x.get('problem') or '')) for x in (payload.get('issues') or []) if isinstance(x,dict)}
            added=0
            for row in issues:
                key=(row['file'],row['kind'],row['problem'])
                if key not in existing:payload.setdefault('issues',[]).append(row);existing.add(key);added+=1
            payload['clean']=False;payload['issue_count']=len(payload.get('issues') or [])
            try:g['_v429_write_audit'](work,payload)
            except Exception:pass
            if added:
                append_event(work,'v4247_functional_acceptance_blocked',
                    f'V42.47 blocked publication on {len(issues)} concrete functional/runtime contract issue(s) even though compilation may be green.',
                    functional_issue_count=len(issues),issues=[{'file':x['file'],'kind':x['kind']} for x in issues[:24]])
        else:
            append_event(work,'v4247_functional_acceptance_green',
                'V42.47 functional acceptance found no concrete unbound runtime seam, production mock, or persistence contract defect in its supported adapters.',functional_issue_count=0)
        return payload


    def repair_round(user_request,manifest,work,audit_payload,progress_callback=None,round_no=1):
        rows=[x for x in (audit_payload or {}).get('issues') or [] if isinstance(x,dict)]
        functional=[x for x in rows if str(x.get('kind') or '').startswith(('functional_','persistence_'))]
        if functional:
            def rank(row):
                kind=str(row.get('kind') or '');rel=_norm(row.get('file'));is_test=('/tests/' in '/'+rel.lower() or '.test.' in rel.lower() or '.spec.' in rel.lower())
                tier=5 if is_test else (0 if kind in {'functional_bridge','functional_runtime_state'} else (1 if kind.startswith('persistence_') else 2))
                return (tier,rel,kind)
            for row in sorted(functional,key=rank):
                rel=_norm(row.get('file'));problem=str(row.get('problem') or '')
                target=Path(work)/rel
                if not rel or not target.is_file():continue
                progress(progress_callback,f'V42.47 functional acceptance repair: {rel}',stage='V42.47 functional acceptance repair',percent=91,current_file=rel)
                try:
                    changed=bool(g['_repair_file_for_issues'](user_request,manifest,work,rel,[problem],progress_callback,validation_failure=problem))
                except Exception:
                    changed=False
                if changed:
                    append_event(work,'v4247_functional_repair_accepted',
                        f'V42.47 accepted one functional-contract repair in {rel}; a fresh build/test/runtime/functional audit is required before another functional edit.',
                        file=rel,kind=row.get('kind'),round=round_no)
                    return True
            # If direct functional dispatch cannot make progress, retain every inherited
            # strategy (cluster repair, specialist, checkpoint/circuit breaker) as fallback.
        return bool(previous_repair_round(user_request,manifest,work,audit_payload,progress_callback,round_no))

    def qwen_call(prompt,progress_callback=None,stage='Generating',profile='chat',**kwargs):
        authority='''\n\nV42.47 FUNCTIONAL COMPLETION AUTHORITY:\n- A green compiler is only an intermediate milestone. The finished project must execute the user-facing workflows it claims to provide.\n- Repair concrete runtime seams end-to-end: caller -> registered backend/API handler -> initialized state/persistence -> returned result -> UI/state update.\n- Production hooks/services may not keep mock/demo/simulated data when a real backend or persistence layer exists. Replace the simulation; do not merely rename it or delete comments.\n- SQL/database code must match the declared schema and row shape at runtime. Mutations decoded with fetch_one require a real returned row (RETURNING or execute+SELECT); SQL NULL must not be represented by the string "null".\n- Do not make tests weaker to get green. Integration tests must execute meaningful behavior and assert observable results/state.\n- Preserve the requested architecture and public contracts. Make the smallest coherent implementation change, then let Jarvis rebuild/test/re-audit.\n'''
        stage2=re.sub(r'\bV42\.46(?:\.0)?\b','V42.47',str(stage or 'Generating'))
        return previous_qwen(str(prompt or '')+authority,progress_callback,stage2,profile=profile,**kwargs)

    def identity():
        data=dict(previous_identity() or {})
        data.update({
            'version':'V'+VERSION,'engine':ENGINE,
            'planner_mode':'functional-acceptance-runtime-seam-persistence-workflow-proof-v42.47',
            'repair_strategy_generation':STRATEGY_GENERATION,
            'compile_success_is_not_project_completion':True,
            'functional_acceptance_gate':True,
            'cross_boundary_runtime_contract_audit':True,
            'tauri_invoke_handler_contract_adapter':True,
            'runtime_state_initialization_contract':True,
            'production_mock_rejection':True,
            'sql_schema_dml_contract_audit':True,
            'sqlx_mutation_returning_contract_audit':True,
            'sql_null_semantics_audit':True,
            'sqlx_fromrow_projection_contract_audit':True,
            'meaningful_cross_boundary_workflow_test_gate':True,
            'compiler_repair_convergence_preserved':True,
            'language_framework_toolchain_agnostic':True,
        })
        return data

    def skills(manifest):
        names=list(previous_skills(manifest) or [])
        for name in ('functional-acceptance','integration-testing','data-import-export'):
            if name not in names:names.append(name)
        return names[:32]

    def guard():
        marker=Path(g['__file__']).resolve().with_name('JARVIS_ACTIVE_ENGINE.txt')
        try:disk=marker.read_text(encoding='utf-8',errors='replace').strip()
        except Exception:disk=''
        expected='V'+VERSION
        return (not disk or disk==expected, '' if (not disk or disk==expected) else f'Jarvis engine files identify {disk}, but this running process is {expected}. Fully close and restart Jarvis.')

    def generate(user_request,max_files=None,max_audit_passes=None,progress_callback=None):
        ok,msg=guard()
        if not ok:return False,msg,None
        return previous_generate(user_request,max_files=max_files,max_audit_passes=max_audit_passes,progress_callback=progress_callback)

    def edit(user_request,source_zip,max_audit_passes=None,progress_callback=None):
        ok,msg=guard()
        if not ok:return False,msg,None
        return previous_edit(user_request,source_zip,max_audit_passes=max_audit_passes,progress_callback=progress_callback)

    g.update({
        'V4247_VERSION':VERSION,'V4247_ENGINE':ENGINE,
        'V4246_VERSION':VERSION,'V4246_ENGINE':ENGINE,
        'V4247_REPAIR_STRATEGY_GENERATION':STRATEGY_GENERATION,
        '_v4247_functional_acceptance_issues':functional_acceptance_issues,
        '_v429_whole_project_audit':audit,'_v429_issue_priority':issue_priority,'_v429_repair_audit_round':repair_round,
        '_qwen_call':qwen_call,'_v36_release_identity':identity,'_v36_stack_skill_names':skills,
        '_progress':progress,'_append_project_event':append_event,
        '_v4247_engine_disk_guard':guard,
        'generate_project_zip':generate,'analyze_and_edit_project_zip':edit,
    })
