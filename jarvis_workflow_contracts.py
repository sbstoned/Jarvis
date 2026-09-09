"""Language-independent workflow debt with optional test-runner conventions.

Static inspection only rejects missing/existence-only proofs. A plausible test
is never execution evidence: the registered component test runner must pass.
"""
from __future__ import annotations
import re
import json
from pathlib import Path, PurePosixPath
from functools import lru_cache

PROBLEM = (
    'FUNCTIONAL TEST CONTRACT: this component still needs an executable feature workflow test. '
    'Exercise a real public UI/service boundary, assert success and failure behavior, and verify '
    'persisted or observable state effects where applicable. Missing tests and existence-only '
    'tests are the same unfinished requirement. Preserve production behavior and existing '
    'assertions; run the declared test command. Static inspection alone is not final acceptance.'
)


def is_test(rel):
    path = PurePosixPath(str(rel).replace('\\', '/').lower())
    name = path.name
    return (bool(set(path.parts) & {'test', 'tests', '__tests__', 'spec', 'specs'})
            or bool(re.search(r'(?:^test_|_test\.|\.test\.|\.spec\.|tests?\.[^.]+$)', name)))


def has_inline_tests(text):
    return bool(re.search(r'#\s*\[\s*(?:test|cfg\s*\(\s*test\s*\))\s*\]|\[\s*(?:Fact|Test|TestMethod)\s*\]|@Test\b', text))


def _code(text):
    # Keep string assertion values, but ignore comments as proof of a workflow.
    return re.sub(r'(?m)^\s*#(?!\[).*$', '', re.sub(r'/\*[\s\S]*?\*/|//[^\n]*', '', text))


def plausible_workflow(text):
    code = _code(text)
    # Remove common existence-only assertions before looking for behavior.
    code = re.sub(r'expect\s*\(\s*typeof\b[^;\n]*', '', code)
    code = re.sub(r'(?m)^.*(?:assert\s+callable\(|assertTrue\(callable\().*$', '', code)
    asserts = re.findall(r'\b(?:assert\w*|expect|should\w*)\s*(?:!|\.|\(|\s+\w)', code, re.I)
    # Actual actions outside equality/existence checks, including UI operations,
    # imported service calls and native test clients. Framework-specific test
    # names are not required, so custom languages can use their own runner.
    calls = re.findall(r'\b([A-Za-z_]\w*)\s*(?:!|::<[^;\n()]*>)?\s*\(', code)
    scaffolding = {'test','it','describe','suite','expect','assert','assertTrue','assertEqual',
                   'toBe','toEqual','toBeDefined','toBeInstanceOf','typeof','callable','isinstance',
                   'Test','Fact','setUp','tearDown','beforeEach','afterEach','beforeAll','afterAll',
                   'require','import','println','print','console','log','skip','only','todo'}
    actions = [name for name in calls if name not in scaffolding and not name.startswith(('assert', 'toBe', 'toEqual'))]
    return len(asserts) >= 2 and bool(actions)


@lru_cache(maxsize=1)
def _adapters():
    try:
        return json.loads((Path(__file__).parent/'project_builder_skills/toolchains.json').read_text())['adapters']
    except (OSError, ValueError, KeyError):
        return {}


def _test_suffix(files, component):
    """Runner/adapter authority precedes incidental build-script languages."""
    adapter = str(component.get('toolchain_adapter') or '').lower()
    command = str(component.get('test_command') or '').lower()
    native = [({'rust','tauri'}, r'\bcargo\b', '.rs'),
              ({'python'}, r'\b(?:pytest|unittest)\b', '.py'),
              ({'go'}, r'\bgo\s+test\b', '.go'),
              ({'dotnet','csharp'}, r'\bdotnet\s+test\b', '.cs'),
              ({'java','maven'}, r'\b(?:mvn|mvnw)\b', '.java')]
    for adapters, pattern, suffix in native:
        if re.search(pattern, command):
            return suffix
    # Node's built-in runner should not silently receive JSX/TypeScript that
    # requires a transpiler. Respect explicitly configured loaders/imports.
    if re.search(r'\bnode\b.*--test\b', command) and not re.search(r'--(?:import|loader)\b', command):
        return '.js'
    for adapters, pattern, suffix in native:
        if adapter in adapters:
            return suffix
    source = [rel for rel in files if not re.search(r'(?:^|/)[^/]*(?:config|\.d)\.[^/]+$', rel, re.I)]
    suffixes = [PurePosixPath(rel).suffix.lower() for rel in source]
    if adapter in {'node','react','vite','typescript','javascript'} or re.search(r'\b(?:vitest|jest|mocha)\b',command):
        return '.ts' if any(s in {'.ts','.tsx','.mts','.cts'} for s in suffixes) else '.js'
    # An explicit custom source language can use its own extension/runner.
    declared = str(component.get('test_extension') or '').strip()
    if re.fullmatch(r'\.[A-Za-z0-9]+', declared):
        return declared
    from collections import Counter
    suffixes = [s for s in suffixes if s not in {'','.json','.toml','.yaml','.yml','.xml','.sql','.html','.css','.md','.txt'}]
    language = str(component.get('language') or _adapters().get(adapter,{}).get('language') or '').lower()
    conventions = {'rust':'.rs','python':'.py','java':'.java','kotlin':'.kt','swift':'.swift','dart':'.dart',
                   'go':'.go','ruby':'.rb','php':'.php','c++':'.cpp','c':'.c','c#':'.cs','f#':'.fs',
                   'elixir':'.exs','lua':'.lua','julia':'.jl','haskell':'.hs','zig':'.zig'}
    native = [ext for name,ext in conventions.items() if name in re.split(r'[/+\s]+',language)]
    # '+' is part of the C++ language name.
    if 'c++' in language: native = ['.cpp'] + [s for s in native if s != '.cpp']
    if native:
        candidates = Counter(s for s in suffixes if s in native)
        return candidates.most_common(1)[0][0] if candidates else native[0]
    suffixes = [s for s in suffixes if s not in {'.h','.hpp','.hh','.hxx'}] or suffixes
    return Counter(suffixes).most_common(1)[0][0] if suffixes else '.txt'


def _test_extensions(files, component):
    suffix = _test_suffix(files,component)
    command = str(component.get('test_command') or '').lower()
    if suffix in {'.js','.jsx','.mjs','.cjs','.ts','.tsx','.mts','.cts'}:
        if re.search(r'\bnode\b.*--test\b',command) and not re.search(r'--(?:import|loader)\b',command):
            return {'.js','.mjs','.cjs'}
        return {'.js','.jsx','.mjs','.cjs','.ts','.tsx','.mts','.cts'}
    if suffix in {'.cpp','.cc','.cxx'}: return {'.cpp','.cc','.cxx'}
    return {suffix}


def _target(files, manifest, component, tests):
    root = str(component.get('root') or '').replace('\\', '/').strip('./')
    prefix = root + '/' if root else ''
    suffix = _test_suffix(files, component)
    extensions = _test_extensions(files,component)
    nested = [str(c.get('root') or '').replace('\\','/').strip('./')+'/'
              for c in (manifest or {}).get('components',[]) if c is not component
              and str(c.get('root') or '').strip('./')
              and (not prefix or str(c.get('root')).startswith(prefix))]
    planned = []
    for item in (manifest or {}).get('files', []):
        rel = item.get('path') if isinstance(item, dict) else item
        if (isinstance(rel, str) and rel.startswith(prefix) and is_test(rel)
                and not any(rel.startswith(n) for n in nested)
                and PurePosixPath(rel).suffix in extensions):
            planned.append(rel)
    if planned:
        return sorted(planned)[0]
    # Use a stable conventional path even after an existence-only file appears.
    runnable = [rel for rel in tests if PurePosixPath(rel).suffix in extensions]
    if runnable:
        return sorted(runnable)[0]
    if suffix in {'.ts','.tsx','.mts','.cts'}:
        return prefix + 'tests/application.integration.test.ts'
    if suffix in {'.js','.jsx','.mjs','.cjs'}:
        return prefix + 'tests/application.integration.test.js'
    if suffix == '.py':
        return prefix + 'tests/test_application.py'
    if suffix == '.go':
        return prefix + 'application_test.go'
    if suffix == '.rs':
        return prefix + 'tests/application.rs'
    return prefix + 'tests/application_test' + suffix


def workflow_issues(files, manifest=None, bridge_issues=(), request=''):
    files = dict(files)
    components = (manifest or {}).get('components') or [{'id':'project','root':'.'}]
    out = []
    for component in components:
        prefix = str(component.get('root') or '').replace('\\', '/').strip('./')
        prefix = prefix + '/' if prefix else ''
        # Nested component tests cannot discharge their parent's workflow debt.
        nested = [str(c.get('root') or '').replace('\\', '/').strip('./') + '/'
                  for c in components if c is not component and str(c.get('root') or '').strip('./')
                  and (not prefix or str(c.get('root')).startswith(prefix))]
        own = {rel:text for rel,text in files.items() if rel.startswith(prefix) and not any(rel.startswith(n) for n in nested)}
        tests = {rel:text for rel,text in own.items() if is_test(rel) or has_inline_tests(text)}
        production = '\n'.join(_code(text) for rel,text in own.items() if not is_test(rel))
        runtime = re.search(r'\b(?:invoke|createTauriCommand|fetch|fetchAll|sendRequest)\s*(?:<[^;\n>]+>)?\s*\(|\b(?:requests|httpClient)\s*\.', production)
        relevant_bridge = any(str(row.get('file') or '').startswith(prefix) for row in bridge_issues)
        required = runtime or relevant_bridge or component.get('test_command') or (manifest or {}).get('test_command') or bool(tests)
        extensions = _test_extensions(own, component)
        if not required or any(plausible_workflow(text) for rel,text in tests.items()
                               if PurePosixPath(rel).suffix in extensions):
            continue
        target = _target(own, manifest, component, tests)
        cid = str(component.get('id') or component.get('root') or 'project')
        out.append({'file':target, 'kind':'functional_test_coverage', 'problem':PROBLEM,
                    'contract_id':'workflow:' + cid, 'component':cid,
                    'evidence':{'state':'weak' if tests else 'missing', 'test_files':sorted(tests),
                                'test_command':component.get('test_command'),
                                'candidate_test_path':target, 'static_check_only':True}})
    return out


def debt_key(row):
    if row.get('kind') == 'functional_test_coverage':
        return (row.get('contract_id') or ('workflow:' + str(row.get('component') or row.get('file'))),
                'functional_test_coverage', PROBLEM)
    if row.get('kind') in {'persistence_sql_prepare','persistence_returning'} and row.get('contract_id'):
        return (str(row.get('file') or '').replace('\\','/'), row['kind'], row['contract_id'])
    return (str(row.get('file') or '').replace('\\','/'), str(row.get('kind') or ''),
            re.sub(r'\s+', ' ', str(row.get('problem') or '')).strip())
