"""V42.58: connected-cluster, evidence-fed coordinated functional transactions.

Policies apply to every source language. Framework adapters still own validation.
Model edits never touch accepted source until all changed components and the
functional delta pass. Publication remains owned by the complete existing audit.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from jarvis_model_protocol import exact_replacements, fit_source_prompt, parse_object, parse_source_file, save_response
from jarvis_workspace_copy import CandidateWorkspaceError, prepare_candidate_workspace, workspace_failure
import jarvis_v4249_repair as planner
import jarvis_v4250_repair as gates
from jarvis_workflow_contracts import is_test, debt_key, has_inline_tests

VERSION = '42.58.0'
ENGINE = 'CONNECTED_CLUSTER_FUNCTIONAL_TRANSACTIONS_FACTORY'
STRATEGY = 'functional-acceptance-v15-connected-cluster-transactions'
LEDGER = 'JARVIS_V4251_FUNCTIONAL_TRANSACTIONS.json'
MAX_ATTEMPTS = 4
MAX_FILES = 18
MAX_CHARS = 120000
MAX_CLUSTER_OWNERS = 6
SKIP = {'node_modules', 'target', 'dist', 'build', '.git', '__pycache__', '.venv', 'venv'}
SUFFIXES = {'.py','.pyw','.rs','.ts','.tsx','.js','.jsx','.mts','.cts','.sql','.toml',
            '.json','.cpp','.cc','.c','.h','.hpp','.cs','.java','.kt','.go','.rb','.php',
            '.swift','.dart','.vue','.svelte','.yaml','.yml','.xml','.gradle','.cmake',
            '.ex','.exs','.erl','.hs','.lua','.r','.jl','.pl','.sh','.ps1','.f90','.m','.mm',
            '.scala','.clj','.cljs','.zig','.nim','.v','.sv','.vhdl','.pas','.d','.fs','.fsx',
            '.ml','.mli','.lisp','.rkt','.groovy','.sol','.html','.css'}
_IS_SENSITIVE = lambda rel: False
STOP = set('const export import from return function async await string bool true false null None self pub fn let use the and for with state error result'.split())


def source_files(root, declared=()):
    declared = set(declared)
    root = Path(root).resolve()
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not d.startswith('.jarvis') and not planner.v4248._is_internal_rel(Path(directory, d).relative_to(root).as_posix()))
        for name in sorted(files):
            path = Path(directory, name)
            rel = path.relative_to(root).as_posix()
            if _IS_SENSITIVE(rel) or path.is_symlink() or (path.suffix.lower() not in SUFFIXES and rel not in declared) or planner.v4248._is_internal_rel(rel) or name.startswith(('JARVIS_', '.jarvis')) or name.endswith(('.lock', '-lock.json')) or '/gen/schemas/' in '/' + rel:
                continue
            if path.stat().st_size > 150000:
                continue
            content = path.read_text(encoding='utf-8', errors='replace')
            if '\x00' not in content: yield rel, content


def words(text):
    return set(re.findall(r'[A-Za-z_][A-Za-z_0-9]{2,}', text)) - STOP


def related_sources(root, rel, manifest=None):
    """Bounded source evidence: imports, consumers, shared symbols, sibling owners.

    Paths and complete source are supplied together; never ask a model to read a
    filename that is not actually in its context. No project-specific names.
    """
    declared = {rel}
    for item in (manifest or {}).get('files',[]):
        if isinstance(item,dict): declared.add(str(item.get('path') or '').replace('\\','/'))
        elif isinstance(item,str): declared.add(item.replace('\\','/'))
    files = dict(source_files(root,declared))
    if rel not in files:
        path = Path(root) / rel
        if not is_test(rel) or path.exists() or not _safe_path(root, rel):
            return {}
        files[rel] = ''  # Explicitly authorized new workflow-test target.
    target = files[rel]
    symbols = words(target)
    stem = Path(rel).stem
    target_suffix = Path(rel).suffix.lower()
    script_family = {'.ts','.tsx','.js','.jsx','.mts','.cts','.mjs','.cjs'}
    python_family = {'.py','.pyw'}
    native_family = {'.rs','.go','.java','.kt','.swift','.dart','.cs','.cpp','.cc','.c','.h','.hpp'}
    target_family = script_family if target_suffix in script_family else (python_family if target_suffix in python_family else (native_family if target_suffix in native_family else {target_suffix}))
    integration_markers = re.compile(r'\b(?:invoke|fetch|axios|httpx|requests|ipc|rpc|client|repository|service|SqlitePool|query_as|execute|fetch_one|fetch_all|manage|setup|init_db|initialize)\b', re.I)
    runtime_markers = re.compile(r'\b(?:invoke_handler|generate_handler|Builder|setup|manage|init_db|initialize|route|handler|controller|provider|service)\b', re.I)
    config_names = {'package.json','Cargo.toml','pyproject.toml','pytest.ini','vitest.config.ts','vite.config.ts','tsconfig.json','go.mod','pom.xml','build.gradle','build.gradle.kts'}
    def rank(item):
        name, text = item
        score = len(symbols & words(text))
        same_family = Path(name).suffix.lower() in target_family
        same_parent = Path(name).parent == Path(rel).parent
        if re.search(r'\b' + re.escape(Path(name).stem) + r'\b', target): score += 65
        if re.search(r'\b' + re.escape(stem) + r'\b', text): score += 12
        if same_parent: score += 24
        # Functional caller/service repairs need the *real* integration seam in
        # context, not merely similarly named domain files in another component.
        # This is stack-agnostic: prefer same-language files that already perform
        # persistence/network/IPC/runtime work.
        if same_family and integration_markers.search(text): score += 150
        if same_parent and integration_markers.search(text): score += 70
        # Runtime/entrypoint owners matter even when the *finding* lives in a
        # domain file. Late-stage functional defects frequently cross the
        # domain -> service/repository -> runtime-registration boundary. Keep
        # those owners close enough to survive prompt-budget fitting instead of
        # dropping main/app/lib/server files and then rejecting the model for
        # correctly recognizing that the repair is coordinated.
        if same_family and runtime_markers.search(text): score += 145
        if same_parent and runtime_markers.search(text): score += 55
        if Path(name).stem.lower() in {'main','app','lib','server','index'} and runtime_markers.search(text): score += 70
        if Path(rel).stem.lower() in {'main','app','lib','server','index'} and runtime_markers.search(text): score += 85
        # Module/import topology is stronger evidence than filename similarity.
        # This stays language-agnostic: a consumer that names the target module
        # or the target that names a sibling module is a legitimate transaction
        # neighbor and should be retained before unrelated same-language files.
        if re.search(r'\b' + re.escape(stem) + r'\b', text): score += 45
        if re.search(r'\b' + re.escape(Path(name).stem) + r'\b', target): score += 45
        if Path(name).name in config_names: score += 25
        # Existing entry points and state/initialization owners are relevant to
        # tiny runtime entry files that have few domain symbols of their own.
        if re.search(r'\b(setup|init_db|initialize|manage|create_pool|createPool)\b', text): score += 24
        if is_test(rel) and not target:
            if Path(name).name in config_names: score += 110
            if re.search(r'\b(?:export|pub fn|def|public)\b', text): score += 30
            if re.search(r'\b(?:invoke|fetch|execute|query|save)\s*\(',text): score += 45
        return (-score, name)
    selected = {rel: target}
    size = len(target)
    for name, text in sorted(((n,t) for n,t in files.items() if n != rel), key=rank):
        if len(selected) >= MAX_FILES: break
        if size + len(text) > MAX_CHARS: continue
        selected[name] = text
        size += len(text)
    return selected


def _requested_scope_expansions(errors, evidence, target):
    """Recover model-requested related files from prior rejection evidence.

    A file is never authorized merely because the model named it. Expansion is
    allowed only when that exact path is already present in Jarvis's bounded
    related-source evidence set. The next attempt then receives the COMPLETE
    current source for that file before it may edit it.
    """
    candidates = []
    patterns = (
        r'(?:Duplicate or out-of-scope edit|EVIDENCE_PROVEN_SCOPE_EXPANSION_REQUIRED)\s*:\s*([^\s,;]+)',
        r'retry with related file forced into source set\s*:\s*([^\s,;]+)',
    )
    for error in errors or []:
        text = str(error or '')
        for pattern in patterns:
            for raw in re.findall(pattern, text, re.I):
                rel = raw.strip().strip('"\'`[](){}.,')
                if rel != target and rel in evidence and rel not in candidates:
                    candidates.append(rel)
    return candidates[:4]


def _prioritized_evidence(evidence, target, priority=()):
    """Stable insertion order for prompt fitting: target, forced neighbors, rest."""
    ordered = {}
    if target in evidence:
        ordered[target] = evidence[target]
    for rel in priority or ():
        if rel in evidence and rel not in ordered:
            ordered[rel] = evidence[rel]
    for rel, text in evidence.items():
        if rel not in ordered:
            ordered[rel] = text
    return ordered


def dependency_token(root, rel, manifest=None):
    evidence = related_sources(root, rel, manifest)
    commands = {key:(manifest or {}).get(key) for key in ('components','build_command','test_command','requirements','acceptance_criteria')}
    return hashlib.sha256(json.dumps([evidence,commands], sort_keys=True, default=str).encode()).hexdigest()[:24]


def _owner_groups(group):
    """Return validator-owned per-file groups for a single target or cluster."""
    owners = group.get('owner_groups') if isinstance(group, dict) else None
    if isinstance(owners, list) and owners:
        return [item for item in owners if isinstance(item, dict) and item.get('file')]
    return [group] if isinstance(group, dict) and group.get('file') else []


def _owner_group_map(group):
    return {str(item.get('file')): item for item in _owner_groups(group)}


def _cluster_owner_files(group):
    return [str(item.get('file')) for item in _owner_groups(group)]


def cluster_dependency_token(root, group, manifest=None):
    owners = _cluster_owner_files(group)
    if len(owners) == 1:
        return dependency_token(root, owners[0], manifest)
    evidence = _cluster_evidence(root, group, manifest)
    commands = {key:(manifest or {}).get(key) for key in ('components','build_command','test_command','requirements','acceptance_criteria')}
    return hashlib.sha256(json.dumps([evidence,commands], sort_keys=True, default=str).encode()).hexdigest()[:24]


def _cluster_evidence(root, group, manifest=None):
    """Merge bounded evidence around every issue owner in a connected cluster.

    All owner files are retained first. Secondary files are ranked by how many
    owner evidence sets independently selected them, so shared provider/runtime
    seams survive the prompt budget without authorizing arbitrary project files.
    """
    root = Path(root)
    owners = _cluster_owner_files(group)
    if not owners:
        return {}
    per_owner = []
    owner_text = {}
    for rel in owners:
        evidence = related_sources(root, rel, manifest)
        if rel not in evidence:
            return {}
        per_owner.append(evidence)
        owner_text[rel] = evidence[rel]
    selected = {}
    size = 0
    for rel in owners:
        text = owner_text[rel]
        if rel not in selected:
            selected[rel] = text
            size += len(text)
    # Do not form a cluster that cannot even carry complete issue-owner source.
    if len(selected) > MAX_FILES or size > MAX_CHARS:
        return related_sources(root, owners[0], manifest)
    votes, order, texts = Counter(), {}, {}
    seq = 0
    for evidence in per_owner:
        for rel, text in evidence.items():
            if rel in selected:
                continue
            votes[rel] += 1
            texts.setdefault(rel, text)
            order.setdefault(rel, seq)
            seq += 1
    for rel in sorted(texts, key=lambda name: (-votes[name], order[name], name)):
        text = texts[rel]
        if len(selected) >= MAX_FILES:
            break
        if size + len(text) > MAX_CHARS:
            continue
        selected[rel] = text
        size += len(text)
    return selected


def _owned_counts(rows, group):
    counts = {}
    for owner in _owner_groups(group):
        rel = str(owner.get('file') or '')
        kinds = set(str(x or '') for x in owner.get('kinds') or [])
        counts[rel] = sum(1 for row in rows or [] if isinstance(row,dict)
                          and str(row.get('file') or '').replace('\\','/') == rel.replace('\\','/')
                          and str(row.get('kind') or '') in kinds)
    return counts


def _cluster_functional_delta(root, clone, user_request, manifest, group):
    owners = _owner_groups(group)
    if len(owners) == 1 and not group.get('cluster'):
        return gates._functional_delta(root, clone, user_request, manifest, owners[0])
    before = list(planner.functional_acceptance_issues(root, user_request, manifest or {}) or [])
    after = list(planner.functional_acceptance_issues(clone, user_request, manifest or {}) or [])
    before_counts = _owned_counts(before, group)
    after_counts = _owned_counts(after, group)
    before_owned, after_owned = sum(before_counts.values()), sum(after_counts.values())
    regressions = {rel:(before_counts.get(rel,0),after_counts.get(rel,0)) for rel in before_counts
                   if after_counts.get(rel,0) > before_counts.get(rel,0)}
    decreases = {rel:(before_counts.get(rel,0),after_counts.get(rel,0)) for rel in before_counts
                 if after_counts.get(rel,0) < before_counts.get(rel,0)}
    return {
        'before_total':len(before), 'after_total':len(after),
        'before_group':before_owned, 'after_group':after_owned,
        'before_owned':before_owned, 'after_owned':after_owned,
        'owner_before':before_counts, 'owner_after':after_counts,
        'owner_decreases':decreases, 'owner_regressions':regressions,
        'improved':bool(before_owned > 0 and after_owned < before_owned and not regressions),
        'before':before, 'after':after,
    }


def _family(rel):
    suffix = Path(str(rel)).suffix.lower()
    if suffix in {'.ts','.tsx','.js','.jsx','.mts','.cts','.mjs','.cjs'}: return 'script'
    if suffix in {'.py','.pyw'}: return 'python'
    if suffix in {'.rs'}: return 'rust'
    if suffix in {'.cpp','.cc','.cxx','.c','.h','.hpp'}: return 'cpp'
    if suffix in {'.java','.kt','.kts'}: return 'jvm'
    if suffix in {'.cs','.fs','.fsx'}: return 'dotnet'
    return suffix or 'other'


def _relation_payload(root, group):
    rel = str(group.get('file') or '')
    try: source = (Path(root)/rel).read_text(encoding='utf-8',errors='replace')
    except Exception: source = ''
    issue = json.dumps(group.get('rows') or group.get('problems') or [], ensure_ascii=False, default=str)
    return source, source + '\n' + issue


def _persistent_entities(text):
    out = set()
    for name in re.findall(r'(?i)\b(?:from|join|update|into|table|references)\s+[`"\[]?([A-Za-z_][A-Za-z0-9_]*)', str(text or '')):
        low = name.lower()
        if low not in {'select','set','values','where'}:
            out.add(low)
    return out


def _integration_terms(text):
    terms = set(re.findall(r'(?i)\b(tauri|invoke|backend|frontend|ipc|rpc|http|api|service|repository|persistence|database|sqlx|sqlite|provider)\b', str(text or '')))
    return {x.lower() for x in terms}


def _groups_connected(root, left, right):
    """Conservative topology edge; same language alone is never sufficient."""
    if _family(left.get('file')) != _family(right.get('file')):
        return False
    lrel, rrel = str(left.get('file') or ''), str(right.get('file') or '')
    lsrc, ltext = _relation_payload(root,left)
    rsrc, rtext = _relation_payload(root,right)
    lstem, rstem = Path(lrel).stem, Path(rrel).stem
    # Direct module/entity ownership evidence from authored source or validator evidence.
    def stem_hit(stem, text):
        return len(stem) >= 4 and bool(re.search(r'(?<![A-Za-z0-9])'+re.escape(stem)+r'(?=[_\W]|$)', text, re.I))
    if stem_hit(rstem,ltext): return True
    if stem_hit(lstem,rtext): return True
    # Persistence/provider files that demonstrably touch the same concrete table/entity.
    if _persistent_entities(ltext) & _persistent_entities(rtext): return True
    # Same-layer production mocks may be repaired together only when they are in
    # the same authored directory and independently identify a real integration seam.
    lk = set(str(x or '') for x in left.get('kinds') or [])
    rk = set(str(x or '') for x in right.get('kinds') or [])
    if Path(lrel).parent == Path(rrel).parent and 'functional_mock' in lk and 'functional_mock' in rk:
        shared = _integration_terms(ltext) & _integration_terms(rtext)
        if shared:
            return True
    return False


def connected_functional_clusters(root, groups):
    """Build small transitive clusters from actual dependency/integration evidence."""
    groups = [g for g in groups or [] if isinstance(g,dict) and g.get('file')]
    n = len(groups)
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra != rb: parent[rb]=ra
    for i in range(n):
        for j in range(i+1,n):
            if groups[i].get('phase',2) >= 5 or groups[j].get('phase',2) >= 5:
                continue
            if _groups_connected(root,groups[i],groups[j]):
                union(i,j)
    comps = {}
    for i,g in enumerate(groups): comps.setdefault(find(i),[]).append(g)
    result = []
    for items in comps.values():
        items = sorted(items,key=lambda g:(g.get('phase',2),str(g.get('file'))))
        # Bound transaction ownership. Oversized components are split into small
        # deterministic chunks; later outer audits may reconnect the remaining tail.
        for start in range(0,len(items),MAX_CLUSTER_OWNERS):
            chunk = items[start:start+MAX_CLUSTER_OWNERS]
            if len(chunk) == 1:
                result.append(chunk[0]); continue
            # Do not cluster files whose complete issue-owner source alone exceeds
            # the evidence budget. This preserves exact complete-source semantics.
            total = 0
            for g in chunk:
                try: total += (Path(root)/g['file']).stat().st_size
                except Exception: pass
            if total > MAX_CHARS:
                result.extend(chunk); continue
            rows = [row for g in chunk for row in (g.get('rows') or [])]
            kinds = sorted({str(x or '') for g in chunk for x in (g.get('kinds') or [])})
            files = [str(g.get('file')) for g in chunk]
            payload = json.dumps({'files':files,'kinds':kinds,'strategy':STRATEGY},sort_keys=True)
            result.append({
                'file':files[0], 'files':files, 'owner_groups':chunk, 'rows':rows,
                'kinds':kinds, 'problems':[p for g in chunk for p in (g.get('problems') or [])],
                'phase':min(int(g.get('phase',2)) for g in chunk),
                'key':hashlib.sha256(payload.encode()).hexdigest()[:24], 'cluster':True,
            })
    return sorted(result,key=lambda g:(g.get('phase',2),str(g.get('file'))))


def _event(g, root, name, message, **fields):
    fn = g.get('_append_project_event')
    if callable(fn):
        fn(root, name, message, **fields)


def _feedback(errors):
    return '\n'.join(errors[-3:])[-6500:]


def _result_errors(errors, limit=3):
    """Return compact diagnostics without losing the original rejection cause."""
    unique = []
    for item in errors or []:
        text = str(item)
        if text not in unique:
            unique.append(text)
    if len(unique) <= limit:
        return unique
    # Keep the first causal failure plus the newest distinct follow-up evidence.
    return [unique[0]] + unique[-(limit-1):]


def _safe_path(root, rel):
    path = Path(str(rel).replace('\\', '/'))
    return (not path.is_absolute() and '..' not in path.parts and ':' not in str(path)
            and Path(root).resolve() in (Path(root) / path).resolve().parents)


def _test_integrity_error(rel, before, after):
    if re.search(r'passWithNoTests|--pass-with-no-tests|--no-test|skipTests\s*[=:]\s*true', after, re.I) and not re.search(r'passWithNoTests|--pass-with-no-tests|--no-test|skipTests\s*[=:]\s*true', before, re.I):
        return 'Candidate disables required test execution.'
    if not is_test(rel) and not has_inline_tests(before):
        return ''
    assertions = r'\b(?:assert\w*|expect|should\w*)\s*(?:!|\.|\(|\s+\w)'
    skipped = r'\b(?:skip|todo|ignore|pending|xit|xdescribe)\b'
    if len(re.findall(assertions, after)) < len(re.findall(assertions, before)) or len(re.findall(skipped, after, re.I)) > len(re.findall(skipped, before, re.I)):
        return 'Candidate removes assertions or skips existing workflow tests.'
    return ''


def _apply(current, replacements):
    return exact_replacements(current, replacements)


def _applicable_replacements(current, replacements):
    """Keep exact current-source hunks and drop only stale zero-match hunks.

    A single stale SEARCH from an earlier model hypothesis must not discard other
    independent exact hunks from the same response. Ambiguous or overlapping
    hunks are still rejected by exact_replacements, and every surviving subset
    still needs functional improvement plus a real component proof.
    """
    source = str(current or '').replace('\r\n','\n')
    kept = []
    for block in replacements or []:
        if not isinstance(block, dict) or set(block) != {'search','replace'}:
            raise ValueError('Each replacement needs exactly search and replace strings.')
        search = block.get('search')
        if not isinstance(search, str) or not search:
            raise ValueError('SEARCH must be nonempty text.')
        normalized = search.replace('\r\n','\n')
        count = source.count(normalized)
        if count == 0:
            continue
        if count > 1:
            raise ValueError(f'SEARCH must match exactly once in the supplied ORIGINAL source; found {count} matches. Exact search: {normalized[:500]!r}.')
        kept.append(block)
    return kept



def _norm_space(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().lower()


def _structured_scope(group, current):
    """Extract validator-owned locators for a narrow target repair.

    Structured SQL/compiler findings already know the owning function, exact SQL
    statement, and/or line.  Preserve those locators so a model cannot repair one
    statement while gratuitously rewriting an unrelated working function.
    """
    owners, sqls, line_snippets = set(), [], []
    for row in group.get('rows') or []:
        evidence = row.get('evidence') if isinstance(row, dict) else None
        if not isinstance(evidence, dict):
            continue
        owner = str(evidence.get('owner') or '').strip()
        if owner: owners.add(owner)
        sql = str(evidence.get('sql') or '').strip()
        if sql: sqls.append(sql)
        try: line = int(evidence.get('line') or 0)
        except Exception: line = 0
        if line > 0:
            lines = current.splitlines()
            lo, hi = max(0, line-4), min(len(lines), line+3)
            snippet = '\n'.join(lines[lo:hi]).strip()
            if snippet: line_snippets.append(snippet)
    return owners, sqls, line_snippets


def _sql_literals(text):
    """Best-effort SQL literals used only to limit edit scope, never validation."""
    found = []
    patterns = [r'r#"([\s\S]*?)"#', r'r"([\s\S]*?)"', r'"([^"\\]*(?:\\.[^"\\]*)*)"', r"'([^'\\]*(?:\\.[^'\\]*)*)'"]
    for pattern in patterns:
        for value in re.findall(pattern, str(text or '')):
            norm = _norm_space(value)
            if re.match(r'^(select|insert|update|delete|create|alter|drop|with|pragma)\b', norm):
                found.append(norm)
    return found


def _header_only(search):
    lines = [x.strip() for x in str(search or '').splitlines() if x.strip()]
    if not lines or len(lines) > 18:
        return False
    prefixes = ('import ', 'from ', 'use ', 'pub use ', '#include ', 'using ', 'package ', 'extern crate ')
    return all(line.startswith(prefixes) or line.startswith(('//','#','/*','*')) for line in lines)


def _scoped_replacements(group, current, replacements):
    """Drop unrelated model hunks when the validator gave exact ownership.

    A remaining subset still has to pass the normal functional-delta and real
    component proof, so pruning cannot manufacture acceptance.  When no precise
    validator locators exist (UI behavior, bridge wiring, custom stacks), the
    historical coordinated-edit freedom is preserved.
    """
    owners, sqls, line_snippets = _structured_scope(group, current)
    if not owners and not sqls and not line_snippets:
        return replacements
    allowed_sql = [_norm_space(x) for x in sqls if _norm_space(x)]
    kept = []
    for block in replacements or []:
        search = str((block or {}).get('search') or '')
        replace = str((block or {}).get('replace') or '')
        if _header_only(search):
            kept.append(block); continue
        norm_search = _norm_space(search)
        locator_hit = any(owner and owner in search for owner in owners)
        locator_hit = locator_hit or any((sql in norm_search or (len(norm_search) >= 16 and norm_search in sql)) for sql in allowed_sql)
        locator_hit = locator_hit or any(_norm_space(snippet)[:120] in norm_search for snippet in line_snippets if len(_norm_space(snippet)) >= 28)
        # If this hunk changes SQL literals, every changed old statement must be
        # owned by one of the current findings.  This rejects the observed failure
        # mode where a valid INSERT fix was bundled with a rewrite of a working
        # joined-row SELECT in another function.
        old_sql, new_sql = _sql_literals(search), _sql_literals(replace)
        changed_old = [value for i,value in enumerate(old_sql) if i >= len(new_sql) or value != new_sql[i]]
        sql_scope_ok = all(any(sql == value or sql in value or value in sql for sql in allowed_sql) for value in changed_old) if changed_old else True
        if locator_hit and sql_scope_ok:
            kept.append(block)
    return kept


def _scope_hints(group, current):
    owners, sqls, line_snippets = _structured_scope(group, current)
    hints = []
    if owners: hints.append('owning symbols: ' + ', '.join(sorted(owners)))
    if sqls: hints.append('validator SQL: ' + ' | '.join(sqls[:6]))
    if line_snippets: hints.append('current exact locator excerpts: ' + ' | '.join(x[:900] for x in line_snippets[:5]))
    return '\n'.join(hints) or '(whole target behavior is in scope)'


SCHEMA = {
 'type':'object', 'properties':{
  'edits':{'type':'array','minItems':1,'maxItems':MAX_FILES,'items':{
   'type':'object','properties':{'file':{'type':'string'},'content':{'type':'string'},'replacements':{
    'type':'array','items':{'type':'object','properties':{'search':{'type':'string'},'replace':{'type':'string'}},'required':['search','replace'],'additionalProperties':False}}},
   'required':['file'],'additionalProperties':False}}},
 'required':['edits'],'additionalProperties':False}


def _model_candidate(g, request, manifest, root, group, evidence, errors, attempt, callback):
    # Escaping an entire source file as JSON can fail on otherwise complete
    # model output. Retry a supplied NEW test with a strict raw-file envelope;
    # existing production edits still require the exact JSON transaction.
    target = group['file']
    raw_test = (is_test(target) and not evidence.get(target, '').strip()
                and any('Invalid transaction JSON' in str(error) for error in errors))
    if raw_test:
        header = '<<<JARVIS_FILE path=' + json.dumps(target, ensure_ascii=False) + '>>>'
        format_rule = (
            'Return one complete executable workflow test at the supplied new target. '
            'Other supplied files are read-only evidence in this response. Return raw source '
            'between these exact envelope lines, without JSON, Markdown or surrounding prose:\n'
            + header + '\n<complete source>\n<<<JARVIS_END_FILE>>>\n'
        )
    else:
        format_rule = (
            'Return JSON edits with exact search/replace blocks. '
            'For an explicitly listed NEW TEST PATH, use {file, content} with a complete executable '
            'workflow test; existing files must use {file, replacements:[{search,replace}]}. '
            'The response is a single JSON object {"edits":[{"file":"path","replacements":'
            '[{"search":"exact original","replace":"replacement"}]}]}. No surrounding prose.\n'
        )
    forced_neighbors = _requested_scope_expansions(errors, evidence, group['file'])
    owner_files = [rel for rel in _cluster_owner_files(group) if rel != group['file']]
    ordered_evidence = _prioritized_evidence(evidence, group['file'], owner_files + forced_neighbors)
    prompt = (
        f'V{VERSION} CONNECTED FUNCTIONAL TRANSACTION. ' + format_rule +
        'Edit only supplied files, preserving public APIs, unrelated features, tests, and validation. '
        'Repair the target using existing providers and actual data persistence. Coordinated edits '
        'to supplied callers/providers/runtime owners are allowed when required. No mock substitutions, '
        'diagnostic suppression, comment-only fixes, test weakening, or unconnected invoke calls. '
        'A bridge must match caller argument/return shapes, register actual handlers and initialize state. '
        'Persistence fixes must preserve feature semantics, typed nulls, complete decoded rows, and '
        'transactional consistency of related writes. Reuse existing schema/model definitions. '
        'Do not add an arbitrary SQL column just to silence a wrong-table update. '
        'Compiler success and static-contract reduction are intermediate proof only. '
        'Related files below are evidence, not mandatory edit targets. A small coordinated multi-file '
        'repair is allowed when the supplied source proves the target crosses a provider/repository/runtime '
        'or registration boundary. Never invent or name an unsupplied file. '
        'Copy every SEARCH from ORIGINAL source, including its imports. Blocks must be disjoint; '
        'never search text produced by another block. A stale zero-match hunk may be omitted while other exact hunks are validated; do not rely on stale source. Prefer 1-3 small blocks per file and a '
        'complete partial repair that reduces the target debt over an oversized rewrite. '
        'Preserve all imports and definitions needed by unchanged code. When validator-owned locators are listed, '
        'do not edit other functions/queries in the target merely because they look improvable; Jarvis will discard unrelated hunks. '
        'For tests, derive expected values, error behavior and postconditions from the original '
        'requirements and supplied public APIs. Test actual workflows using isolated temporary state. '
        'After a mutation or deletion, assert the documented resulting state and related-record behavior; '
        'do not make contradictory assertions or change working production semantics to suit a new test.\n'
        + 'USER REQUEST:\n' + str(request) + '\nISSUE OWNER FILES: ' + json.dumps(_cluster_owner_files(group))
        + '\nCURRENT CONTRACT FINDINGS:\n' + json.dumps(group.get('rows') or group.get('problems'), ensure_ascii=False)
        + '\nAUTHORIZED VALIDATOR LOCATORS BY ISSUE OWNER:\n' + json.dumps({rel:_scope_hints(owner, evidence.get(rel,'')) for rel,owner in _owner_group_map(group).items()}, ensure_ascii=False)
        + '\nEVIDENCE-PROVEN SCOPE EXPANSIONS FOR THIS RETRY:\n' + (json.dumps(forced_neighbors) if forced_neighbors else '(none)')
        + '\nPREVIOUS REJECTION EVIDENCE (fix the cause; do not repeat the rejected patch):\n' + (_feedback(errors) or '(first attempt)')
        + '\nCURRENT VALIDATION AND REQUIREMENTS:\n' + json.dumps(g.get('_v4254_repair_evidence', lambda *a:{})(root,manifest,group), ensure_ascii=False, default=str)
        + '\nNEW TEST PATHS (absent or empty tests on disk):\n' + json.dumps([rel for rel in evidence if not (Path(root)/rel).exists() or (is_test(rel) and not evidence[rel].strip())])
    )
    supplied = dict(ordered_evidence)
    def build_prompt(budget):
        rendered, selected = fit_source_prompt(prompt,ordered_evidence,group['file'],budget)
        supplied.clear(); supplied.update(selected)
        return rendered
    initial = build_prompt(max(1000000,len(prompt)+len(json.dumps(ordered_evidence))*2))
    ok, raw = g['_qwen_call'](initial, callback, f'V{VERSION} functional transaction {attempt}: {" + ".join(_cluster_owner_files(group))}',
        profile='repair', max_tokens=min(9000, g.get('_qwen_file_output_limit', lambda:9000)()),
        thinking=False, response_schema=None if raw_test else SCHEMA,
        schema_name='v4251_transaction', strict_output=True,
        prompt_builder=build_prompt)
    try:
        # The raw output/transport reason survives parse, patch and compiler
        # rejection, making the next run diagnosable from its checkpoint.
        receipt = save_response(root,group['file'],attempt,raw,supplied,status='received' if ok else 'transport_failed')
        _event(g,root,'v4255_model_response','Saved bounded model response evidence.',
               file=group['file'],attempt=attempt,diagnostic=str(receipt.relative_to(root)),
               transport=getattr(raw,'metadata',{}))
    except OSError:
        pass  # Diagnostics cannot bypass or veto the actual acceptance checks.
    if not ok: raise ValueError('Model call failed: ' + str(raw)[-1800:])
    obj = ({'edits':[{'file':target,'content':parse_source_file(raw,target)}]}
           if raw_test else parse_object(raw))
    if set(obj) != {'edits'}:
        raise ValueError('Transaction JSON must contain only the edits array.')
    if not isinstance(obj, dict) or not isinstance(obj.get('edits'), list) or not 1 <= len(obj['edits']) <= MAX_FILES:
        raise ValueError('Invalid transaction JSON.')
    changes, seen_files = {}, set()
    for edit in obj['edits']:
        if not isinstance(edit,dict) or set(edit) - {'file','content','replacements'}:
            raise ValueError('Each edit must be an object with file and replacements (or content for a new test).')
        rel = edit.get('file')
        if not isinstance(rel,str) or rel in seen_files or not _safe_path(root, rel):
            raise ValueError('Duplicate or out-of-scope edit: ' + str(rel))
        if rel not in supplied:
            # Do not accept a guessed edit. If the path is already part of the
            # evidence-closed dependency set, turn the rejection into an
            # adaptive scope-expansion signal. The next attempt will force the
            # COMPLETE current source for this file into the prompt before any
            # edit is considered.
            if rel in evidence:
                raise ValueError('EVIDENCE_PROVEN_SCOPE_EXPANSION_REQUIRED: ' + rel +
                                 '. retry with related file forced into source set: ' + rel)
            raise ValueError('Duplicate or out-of-scope edit: ' + str(rel))
        seen_files.add(rel)
        if not (Path(root)/rel).exists() or (is_test(rel) and not evidence[rel].strip()):
            content = edit.get('content')
            if not is_test(rel) or not isinstance(content, str) or not content.strip() or edit.get('replacements'):
                raise ValueError('A new test needs complete content at its supplied path.')
        else:
            if 'content' in edit:
                raise ValueError('Existing files require exact replacements, not whole-file overwrite.')
            replacements = edit.get('replacements')
            owner_group = _owner_group_map(group).get(rel)
            if owner_group is not None:
                replacements = _scoped_replacements(owner_group, evidence[rel], replacements)
            replacements = _applicable_replacements(evidence[rel], replacements)
            if not replacements:
                if owner_group is not None:
                    raise ValueError('All proposed issue-owner hunks were stale or outside validator-owned repair scope; make a smaller edit at the supplied current-source locators.')
                continue
            content = _apply(evidence[rel], replacements)
        if content != evidence[rel]: changes[rel] = content
    if not changes: raise ValueError('Candidate made no source change.')
    return changes


def _commit(g, root, clone, originals, changes, manifest):
    # Check every original before writing any file. Preserve bytes for rollback,
    # including CRLF. All compiler/audit checks already ran in the clone.
    if any(((root / rel).read_bytes() if (root / rel).exists() else None) != raw for rel, raw in originals.items()):
        raise ValueError('Accepted source changed during candidate validation; re-audit required.')
    written = []
    staged = []
    try:
        for rel in changes:
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + '.jarvis_v4251_tmp')
            staged.append(temp)
            temp.write_bytes((clone / rel).read_bytes())
        for rel, temp in zip(changes, staged):
            os.replace(temp, root / rel)
            written.append(rel)
    except Exception:
        for rel in written:
            if originals[rel] is None: (root / rel).unlink(missing_ok=True)
            else: (root / rel).write_bytes(originals[rel])
        raise
    finally:
        for temp in staged: temp.unlink(missing_ok=True)
    # Newly verified tests become plan-owned files. Otherwise the legacy
    # requirement-ownership gate would keep reporting "tests" after they pass.
    if isinstance(manifest, dict):
        planned = manifest.setdefault('files', [])
        known = {item.get('path') if isinstance(item,dict) else item for item in planned}
        for rel in changes:
            if is_test(rel) and rel not in known:
                planned.append({'path':rel, 'phase':'tests', 'purpose':'Executable integration tests for public feature success, failure and persisted/state behavior.'})
    for rel in changes:
        for name, args in [('_v36_checkpoint_file',(root,rel,(originals[rel] or b'').decode('utf-8',errors='replace'),'before_v4251_transaction')),
                           ('_v413_mark_accepted',(root,rel,'v4251_validated_transaction')),
                           ('_delete_candidate_draft',(root,rel))]:
            try:
                if callable(g.get(name)): g[name](*args)
            except Exception: pass
    for name in ('_v36_build_repo_graph','_v36_build_contract_registry'):
        try:
            if callable(g.get(name)): g[name](root,manifest,write=True)
        except Exception: pass
    if callable(g.get('_v33_write_architecture')):
        try: g['_v33_write_architecture'](root,manifest)
        except Exception as exc:
            _event(g,root,'v4254_plan_report_warning','Verified files were committed, but writing the plan report failed.',error=str(exc))


def repair_transaction(g, request, manifest, root, group, callback=None, prior_errors=None):
    root = Path(root).resolve()
    errors = list(prior_errors or [])
    evidence = _cluster_evidence(root, group, manifest)
    if any(rel not in evidence for rel in _cluster_owner_files(group)): return False, ['One or more issue owners have no complete readable authored source in the bounded cluster.']
    originals = {rel:(root/rel).read_bytes() if (root/rel).exists() else None for rel in evidence}
    fingerprints = set()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        handle = None
        try:
            from jarvis_v4240_repair import _STOP_EVENT, ProjectStopRequested
            if _STOP_EVENT.is_set(): raise ProjectStopRequested('Stop requested before a functional transaction.')
            if any(((root/rel).read_bytes() if (root/rel).exists() else None) != data for rel,data in originals.items()):
                return False, errors + ['Source changed during repair; re-audit current source before another model call.']
            # Fail cheap: an unavailable candidate clone must not burn a long
            # model generation or be recorded as a rejected code repair.
            handle, clone = prepare_candidate_workspace(g, root, callback)
            clone = Path(clone).resolve()
            changes = _model_candidate(g,request,manifest,root,group,evidence,errors,attempt,callback)
            digest = hashlib.sha256(json.dumps(changes,sort_keys=True).encode()).hexdigest()
            if digest in fingerprints: raise ValueError('Repeated rejected candidate; change the repair strategy.')
            fingerprints.add(digest)
            for rel, content in changes.items():
                if Path(rel).suffix in {'.js','.jsx','.ts','.tsx','.rs','.java','.cs','.cpp','.c'}:
                    strip = planner.v4247._strip_js_comments
                    if re.sub(r'\s+','',strip(evidence[rel])) == re.sub(r'\s+','',strip(content)):
                        raise ValueError(rel + ': comment/format-only changes cannot repair a functional contract.')
                error = _test_integrity_error(rel, evidence[rel], content)
                if error: raise ValueError(rel + ': ' + error)
                (clone/rel).parent.mkdir(parents=True,exist_ok=True)
                (clone/rel).write_text(content,encoding='utf-8')
            for rel, content in changes.items():
                content_gate = g.get('_content_validation_error')
                if callable(content_gate):
                    error = content_gate(rel,content)
                    if error: raise ValueError(rel + ': ' + str(error)[-3500:])
                # Preserve the existing Python generated-test integrity policy.
                is_test = g.get('_is_jarvis_generated_acceptance_test')
                metrics = g.get('_generated_test_integrity_metrics')
                if Path(rel).suffix in {'.py','.pyw'} and callable(is_test) and is_test(rel) and callable(metrics):
                    before_test, after_test = metrics(evidence[rel]), metrics(content)
                    if any(after_test[key] < before_test[key] for key in ('tests','asserts')) or after_test['skips'] > before_test['skips']:
                        raise ValueError(rel + ': candidate weakens generated acceptance tests.')
                error = gates._syntax_candidate_error(g,clone,manifest,rel,content)
                if error: raise ValueError(rel + ': ' + error[-3500:])
                # Keep semantic ownership gates, applied after the complete
                # transaction is staged, avoiding partial-file compiler deadlock.
                semantic = g.get('_v4221_semantic_role_error')
                if callable(semantic):
                    error = semantic(clone,manifest,rel,content)
                    if error: raise ValueError(rel + ': ' + str(error)[-3500:])
            delta = _cluster_functional_delta(root,clone,str(request),manifest,group)
            if not delta.get('improved'):
                owner_set = set(_cluster_owner_files(group))
                target_rows = [row for row in delta.get('after', []) if row.get('file') in owner_set]
                raise ValueError('Connected functional cluster did not strictly improve without owned regressions: ' + json.dumps(target_rows or delta, default=str)[:5000])
            # Do not replace one production defect with a different one. Bridge
            # reachability can legitimately expand when real callers are added;
            # it remains explicit debt for the next runtime phase, never hidden.
            before = Counter(debt_key(x) for x in delta.get('before',[]))
            added = []
            for row in delta.get('after',[]):
                key = debt_key(row)
                if before[key]: before[key] -= 1
                elif row.get('kind') not in {'functional_bridge','functional_runtime_state'}: added.append(row)
            if added: raise ValueError('Candidate introduced new functional debt: ' + json.dumps(added)[-4500:])
            proved = set()
            for rel in changes:
                component = gates._resolve_component(g,root,manifest,rel)
                identity = json.dumps(component,sort_keys=True) if component else rel
                if identity in proved: continue
                proof = gates._component_candidate_proof(g,root,clone,manifest,rel,callback)
                if not proof.get('ok'):
                    raise ValueError(rel + ': component proof ' + str(proof.get('kind')) + '\n' + str(proof.get('output'))[-5000:])
                proved.add(identity)
            if _STOP_EVENT.is_set(): raise ProjectStopRequested('Stop requested before committing the validated candidate.')
            _commit(g,root,clone,originals,changes,manifest)
            _event(g,root,'v4251_transaction_committed',f'V{VERSION} promoted a validated connected functional transaction.',
                   files=list(changes),owners=_cluster_owner_files(group),before=delta.get('before_total'),after=delta.get('after_total'),
                   owner_before=delta.get('owner_before'),owner_after=delta.get('owner_after'),final_acceptance=False)
            return True, errors
        except CandidateWorkspaceError as exc:
            errors.append(str(exc))
            _event(g,root,'v4262_candidate_workspace_unavailable',
                   'Candidate workspace could not be prepared; accepted source and model repair budget preserved.',
                   file=group['file'],attempt=attempt,error=errors[-1],final_acceptance=False)
            return False, _result_errors(errors)
        except Exception as exc:
            if isinstance(exc,ProjectStopRequested): raise
            errors.append(str(exc)[-6000:])
            _event(g,root,'v4251_transaction_rejected',f'V{VERSION} rejected a disposable connected candidate; its evidence will inform the next attempt.',
                   file=group['file'],owners=_cluster_owner_files(group),attempt=attempt,error=errors[-1],final_acceptance=False)
        finally:
            if handle is not None: handle.cleanup()
    return False, _result_errors(errors)


def install(g):
    """Install V42.58 cluster scheduling while preserving every prior gate."""
    import sys
    global _IS_SENSITIVE
    _IS_SENSITIVE = g.get('_is_sensitive_project_rel', _IS_SENSITIVE)
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-7])_repair',name):
            module.VERSION = VERSION
            module.ENGINE = ENGINE
            if hasattr(module,'STRATEGY'): module.STRATEGY = STRATEGY
            if hasattr(module,'STRATEGY_GENERATION'): module.STRATEGY_GENERATION = STRATEGY
    previous = g['_v429_repair_audit_round']
    previous_identity = g['_v36_release_identity']

    def repair_round(request,manifest,work,audit,callback=None,round_no=1):
        rows = [x for x in (audit or {}).get('issues',[]) if isinstance(x,dict)]
        # Compiler/build authority still comes before behavior repair. Functional
        # test debt and test-substrate debt are not compiler blockers.
        if any(gates._is_component_blocker(x) for x in rows):
            return previous(request,manifest,work,audit,callback,round_no)
        groups = planner._group_rows(rows)
        if not groups:
            return previous(request,manifest,work,audit,callback,round_no)
        root = Path(work).resolve()
        clusters = connected_functional_clusters(root, groups)
        path = root/LEDGER
        data = planner._load_json(path,{})
        if data.get('strategy') != STRATEGY:
            data = {'strategy':STRATEGY,'version':VERSION,'groups':{}}
        production = [item for item in clusters if item.get('phase',2) < 5]
        candidates = production or clusters
        # Each connected cluster is attempted once per audit round. If it fails,
        # continue to independent clusters so one hard feature cannot starve the rest.
        seen = set()
        for group in candidates[:12]:
            if group.get('key') in seen: continue
            seen.add(group.get('key'))
            token = cluster_dependency_token(root,group,manifest)
            state = data['groups'].setdefault(group['key'],{})
            if state.get('token') != token:
                state.update(token=token,attempts=0,errors=[])
            if state.get('attempts',0) >= 2: continue
            state['attempts'] = state.get('attempts',0)+1
            state['file'] = group['file']
            state['owners'] = _cluster_owner_files(group)
            planner._save_json(path,data)
            label = ' + '.join(_cluster_owner_files(group))
            g['_progress'](callback,f'V{VERSION} connected functional transaction: {label}',stage=f'V{VERSION} connected functional convergence',percent=92)
            changed, errors = repair_transaction(g,request,manifest or {},root,group,callback,state.get('errors'))
            state.update(errors=errors,accepted=bool(changed))
            if not changed and workspace_failure(root):
                state['attempts'] = max(0, state['attempts'] - 1)
                state['infrastructure_blocked'] = True
                planner._save_json(path,data)
                return False  # Same source-wide copy failure also blocks sibling clusters.
            state.pop('infrastructure_blocked', None)
            planner._save_json(path,data)
            if changed:
                return True  # outer build/audit re-establishes authoritative current debt
        return False

    def identity():
        value = dict(previous_identity())
        value.update(
            version='V'+VERSION, engine=ENGINE, repair_strategy_generation=STRATEGY,
            planner_mode='evidence-connected-functional-cluster-convergence-v42.58',
            functional_patch_only_primary_strategy=False,
            coordinated_functional_candidates=True,
            connected_functional_clusters=True,
            cluster_progress_is_acceptance_unit=True,
            any_owned_issue_may_drive_strict_cluster_progress=True,
            per_owner_validator_scope=True,
            independent_cluster_starvation_protection=True,
            rejected_trial_evidence_preserved=True,
            evidence_proven_scope_expansion=True,
            forced_complete_source_on_scope_retry=True,
            active_stream_absolute_timeout_seconds=0,
            active_stream_wall_clock_unbounded=True,
            compiler_and_functional_gates_preserved=True,
            language_framework_toolchain_agnostic=True,
        )
        return value
    g.update(_v429_repair_audit_round=repair_round,_v36_release_identity=identity,
             JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,V4258_VERSION=VERSION,V4258_ENGINE=ENGINE)
