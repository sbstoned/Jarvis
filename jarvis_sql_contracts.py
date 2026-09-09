"""Prepare constant SQLite statements against isolated declared application schemas.

This optional adapter executes DDL only in an empty in-memory database. It never
opens the application's database or executes its data mutations. Native builds,
tests and runtime validation remain required; dynamic SQL and other dialects
must be validated by their own toolchains.
"""
from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3


@dataclass(frozen=True)
class Statement:
    file: str
    sql: str
    line: int
    owner: str = ''


def statement_owner(text, suffix, line):
    if suffix in {'.py', '.pyw'}:
        try:
            spans = [n for n in ast.walk(ast.parse(text))
                     if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.lineno <= line <= (n.end_lineno or n.lineno)]
            return '.'.join(n.name for n in sorted(spans, key=lambda n:n.lineno)) or '<module>'
        except SyntaxError:
            return '<module>'
    # Optional lexical anchors for constant SQL in native/JS sources. No line
    # numbers in the identity: adding imports must not reintroduce old debt.
    prefix = '\n'.join(text.splitlines()[:line])
    prefix = _STRINGS.sub(lambda m:'\n' * m[0].count('\n'), prefix)
    names = re.findall(r'\b(?:fn|function|func|fun)\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*(?:<[^>]*>)?\s*\(', prefix)
    return names[-1] if names else '<module>'


_STRINGS = re.compile(
    r'(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)'
    r'|\br(?P<hash>\#{0,16})"(?P<raw>[\s\S]*?)"(?P=hash)'
    r'|(?P<quote>[\'"`])(?P<body>(?:\\[\s\S]|(?!(?P=quote))[^\\])*)(?P=quote)'
)
# Keep quoted SQL identifiers and strings opaque while counting bind parameters.
_SQL_TOKENS = re.compile(
    r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]"
    r'|--[^\n]*|/\*[\s\S]*?\*/|(?P<bind>\?\d*|[:@$][A-Za-z_][A-Za-z_0-9]*)'
)
_TABLE = r'(?:"[^"]+"|`[^`]+`|\[[^\]]+\]|[A-Za-z_][A-Za-z_0-9]*)'
_CREATE = re.compile(r'^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(' + _TABLE + r')\s*\(', re.I)
_ALTER = re.compile(r'^ALTER\s+TABLE\s+(' + _TABLE + r')\s+ADD\s+(?:COLUMN\s+)?', re.I)
_START = re.compile(r'^(?:SELECT|WITH|INSERT|UPDATE|DELETE|CREATE\s+TABLE|ALTER\s+TABLE)\b', re.I)


def literals(text, suffix):
    if suffix in {'.py', '.pyw'}:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return []  # The language compiler owns syntax diagnostics.
        found = []

        class Visitor(ast.NodeVisitor):
            def visit_JoinedStr(self, node):
                pass  # An interpolated expression is not a complete SQL statement.

            def visit_Expr(self, node):
                if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                    self.generic_visit(node)

            def visit_Constant(self, node):
                if isinstance(node.value, str):
                    found.append((node.value, node.lineno))

        Visitor().visit(tree)
        return found
    found = []
    for match in _STRINGS.finditer(text):
        if match.group('comment') is not None:
            continue
        raw = match.group('raw')
        body = raw if raw is not None else match.group('body')
        if re.search(r'\$\{|\{[A-Za-z_][A-Za-z_0-9.]*\}', body):
            continue
        if raw is None:
            body = re.sub(r'\\([nrt\\\'"`])', lambda m: {'n': '\n', 'r': '\r', 't': '\t'}.get(m[1], m[1]), body)
        found.append((body, text.count('\n', 0, match.start()) + 1))
    return found


def split_sql(text):
    start = 0
    for i, char in enumerate(text):
        if char == ';' and sqlite3.complete_statement(text[start:i + 1]):
            yield text[start:i + 1]
            start = i + 1
    if text[start:].strip():
        yield text[start:]


def clean_sql(text):
    return re.sub(r'^(?:\s+|--[^\n]*(?:\n|$)|/\*[\s\S]*?\*/)*', '', text).strip()


# SQL-looking text is not necessarily SQL. Error messages such as "Update
# failed" must never be prepared. These are optional SQLite adapter seams;
# unknown/dynamic query builders are left to the project's native validation.
_CALLS = {'execute', 'executemany', 'executescript', 'exec', 'prepare',
          'prepareStatement', 'query', 'query_as', 'query_scalar', 'query_row',
          'query_map', 'rawQuery', 'execSQL', 'executeQuery', 'executeUpdate',
          'Query', 'QueryRow', 'QueryContext', 'QueryRowContext', 'Exec',
          'ExecContext', 'raw', 'read_sql', 'read_sql_query'}
_CALL = re.compile(r'\b(?:' + '|'.join(sorted(_CALLS)) + r')\s*(?:!|::<[^;\n()]*>)?\s*\(')


def executable_literals(text, suffix):
    """Constant statements at database calls, including local variable aliases.

    DDL declarations are schema evidence even when a migration loader executes
    them indirectly. DML/SELECT requires a caller. Never import or run source.
    """
    declarations = [(value, line) for value, line in literals(text, suffix)
                    if re.match(r'^(?:CREATE|ALTER)\s+TABLE\b', clean_sql(value), re.I)]
    if suffix in {'.py', '.pyw'}:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return declarations
        assigned = {}
        for node in ast.walk(tree):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            for target in targets:
                if isinstance(target, ast.Name):
                    assigned.setdefault(target.id, []).append(node.value)

        def resolve(node, seen=()):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return [(node.value, node.lineno)]
            if isinstance(node, ast.Name) and node.id not in seen:
                # Ambiguous bindings are left to native tests rather than
                # assuming a query from a different function is executed here.
                values = assigned.get(node.id, [])
                if len(values) == 1:
                    return resolve(values[0], (*seen, node.id))
            return []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ''
            if name in _CALLS:
                for arg in node.args[:1]:
                    declarations.extend(resolve(arg))
                for arg in node.keywords:
                    if arg.arg in {'sql', 'query', 'statement'}:
                        declarations.extend(resolve(arg.value))
        return list(dict.fromkeys(declarations))

    values, pieces, cursor = {}, [], 0
    for index, match in enumerate(_STRINGS.finditer(text)):
        pieces.append(text[cursor:match.start()])
        cursor = match.end()
        if match.group('comment') is not None:
            pieces.append('\n' * match[0].count('\n') + ' ')
            continue
        token = f'JARVIS_SQL_LITERAL_{index}'
        found = literals(match[0], suffix)
        if found:
            values[token] = (found[0][0], text.count('\n', 0, match.start()) + 1)
        pieces.append(token + '\n' * match[0].count('\n'))
    pieces.append(text[cursor:])
    code = ''.join(pieces)
    assignments = {}
    # Includes Rust's typed let/const, C-family declarations and Go's :=.
    for match in re.finditer(r'\b([A-Za-z_]\w*)\s*(?::\s*[^=;\n]+)?\s*:?=\s*(&?\s*[A-Za-z_]\w*)\s*(?=[;,\n}]|$)', code):
        assignments.setdefault(match[1], []).append((match.start(), match[2].replace('&', '').strip()))

    def resolve(token, at, seen=()):
        if token in values:
            return [values[token]]
        if token in seen:
            return []
        bindings = assignments.get(token, [])
        preceding = [binding for binding in bindings if binding[0] < at]
        if preceding:
            pos, value = preceding[-1]
            return resolve(value, pos, (*seen, token))
        if len(bindings) == 1:  # Module constants may be declared after a caller.
            pos, value = bindings[0]
            return resolve(value, pos, (*seen, token))
        return []

    for match in _CALL.finditer(code):
        # Only whole arguments: don't prepare a fragment of concatenated SQL.
        args = re.match(r'\s*&?\s*([A-Za-z_]\w*)\s*(?=[,)])', code[match.end():])
        if args:
            declarations.extend(resolve(args[1], match.start()))
        # sqlx::query_as!(Row, "...") uses the second macro argument as SQL.
        if re.search(r'query_as\s*!', match[0]):
            args = re.match(r'\s*[\w:]+\s*,\s*([A-Za-z_]\w*)\s*(?=[,)])', code[match.end():])
            if args:
                declarations.extend(resolve(args[1], match.start()))
    return list(dict.fromkeys(declarations))


def statements(files):
    for rel, text in files:
        lower = '/' + rel.lower().replace('\\', '/')
        if any(part in lower for part in ('/tests/', '/test/', '.test.', '.spec.')):
            continue
        suffix = Path(rel).suffix.lower()
        source = [(text, 1)] if suffix == '.sql' else executable_literals(text, suffix)
        for value, line in source:
            for part in split_sql(value):
                sql = clean_sql(part)
                if _START.match(sql):
                    yield Statement(rel, sql, line, statement_owner(text, suffix, line))


def sqlx_returning_issues(rel, text):
    """Bind each constant mutation to its own SQLx row-consumption chain.

    Fixed-size source tails cross function/variable boundaries: an execute()
    mutation can otherwise inherit a later query_as(...).fetch_one(). Tokenize
    strings and resolve local aliases before checking the exact call chain.
    """
    values, pieces, cursor = {}, [], 0
    for index, match in enumerate(_STRINGS.finditer(text)):
        pieces.append(text[cursor:match.start()]); cursor = match.end()
        if match.group('comment') is not None:
            pieces.append('\n'*match[0].count('\n')+' '); continue
        token = f'JARVIS_SQLX_LITERAL_{index}'
        found = literals(match[0], '.rs')
        if found: values[token] = found[0][0]
        pieces.append(token+'\n'*match[0].count('\n'))
    pieces.append(text[cursor:]); code = ''.join(pieces)
    functions = list(re.finditer(r'\bfn\s+([A-Za-z_]\w*)\s*(?:<[^>]*>)?\s*\(',code))
    def owner(pos):
        return next((m[1] for m in reversed(functions) if m.start()<pos),'<module>')
    assignments = {}
    for match in re.finditer(r'\b(?:let\s+(?:mut\s+)?|const\s+|static\s+)([A-Za-z_]\w*)\s*(?::[^=;\n]+)?\s*=\s*&?\s*([A-Za-z_]\w*)\s*;',code):
        assignments.setdefault(match[1],[]).append((match.start(),match[2],owner(match.start()),match[0].startswith(('const ','static '))))
    def resolve(name,pos,scope,seen=()):
        if name in values: return values[name]
        if name in seen: return None
        candidates=[a for a in assignments.get(name,[]) if a[0]<pos and (a[2]==scope or a[3])]
        if not candidates: return None
        at,value,assigned_scope,_=candidates[-1]
        return resolve(value,at,assigned_scope,(*seen,name))
    calls = re.compile(r'\b(query_as|query_scalar|query)\s*(?:!|::<[^;\n()]*>)?\s*\(\s*([^;()]*?)\s*\)([^;]*)')
    counts, out = Counter(), []
    for call in calls.finditer(code):
        consumed = re.search(r'\.\s*(fetch_one|fetch_optional|fetch_all|fetch)\s*\(',call[3])
        if not consumed: continue
        args = call[2].split(',')
        argument = args[1] if call[1]=='query_as' and '!' in call[0].split('(',1)[0] and len(args)>1 else args[0]
        argument = argument.strip().lstrip('&').strip()
        if not re.fullmatch(r'[A-Za-z_]\w*',argument): continue
        scope = owner(call.start())
        sql = resolve(argument,call.start(),scope)
        if not sql: continue
        mutation = re.match(r'^\s*(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+('+_TABLE+')',sql,re.I)
        if not mutation: continue
        operation, table = mutation[1].split()[0].upper(), mutation[2].strip('"`[]').lower()
        key = (scope,operation,table)
        counts[key] += 1
        keywords = _SQL_TOKENS.sub(lambda m:'?' if m.group('bind') else ' ',sql)
        if re.search(r'\bRETURNING\b',keywords,re.I): continue
        identity = hashlib.sha256(json.dumps([rel,*key,counts[key]]).encode()).hexdigest()[:24]
        out.append({'file':rel,'kind':'persistence_returning','contract_id':'sqlx-row:'+identity,
                    'problem':f'PERSISTENCE RESULT CONTRACT: {scope} row statement {counts[key]} performs {operation} on {table} '
                              f'without RETURNING, but its own SQLx call uses {consumed[1]} to decode rows. '
                              'Add an appropriate RETURNING projection or execute the mutation and then SELECT the row. '
                              'Preserve the public result shape and feature behavior.',
                    'evidence':{'owner':scope,'sql':sql,'consumer':consumed[1],
                                'line':code.count('\n',0,call.start())+1}})
    return out


def _compile(db, sql):
    count = 0

    def parameter(match):
        nonlocal count
        if match.group('bind') is None:
            return match[0]
        count += 1
        return '?'

    sql = _SQL_TOKENS.sub(parameter, sql)
    if count > 10000:
        raise sqlite3.OperationalError('parameter limit')
    db.execute('EXPLAIN ' + sql, (None,) * count).close()


def sqlite_contract_issues(files):
    files = list(files)
    if not any(re.search(r'\b(?:sqlite\w*|rusqlite)\b', text, re.I) for _, text in files):
        return []
    rows = list(statements(files))
    definitions = {}
    for row in rows:
        match = _CREATE.match(row.sql)
        if match:
            table = match[1].strip('"`[]').lower()
            definitions.setdefault(table, []).append(row)
    if not definitions:
        return []
    databases = []
    issues, occurrences = [], Counter()
    try:
        # Alternative install-time definitions can describe the same table. A
        # query accepted by either declared schema is left to native validation.
        for reverse in (False, True):
            db = sqlite3.connect(':memory:')
            databases.append(db)
            db.execute('PRAGMA foreign_keys=ON')
            db.set_progress_handler(lambda: 1, 100000)
            for variants in definitions.values():
                for row in (list(reversed(variants)) if reverse else variants):
                    try:
                        db.execute(row.sql)
                        break
                    except sqlite3.Error:
                        continue
            for row in rows:
                if _ALTER.match(row.sql):
                    try:
                        db.execute(row.sql)
                    except sqlite3.Error:
                        pass  # Already applied or not a supported additive migration.
        for row in rows:
            if re.match(r'^(?:CREATE|ALTER)\b', row.sql, re.I):
                continue
            errors = []
            for db in databases:
                try:
                    _compile(db, row.sql)
                    break
                except sqlite3.Error as exc:
                    errors.append(str(exc))
            else:
                definite = r'no such column|has no column named|ambiguous column name|syntax error|incomplete input|\d+ values for \d+ columns|\d+ columns but \d+ values'
                if not all(re.search(definite, error, re.I) for error in errors):
                    continue  # Unknown external tables, functions or dialect features.
                error = errors[0]
                problem = (
                    'SQL PREPARE CONTRACT: SQLite rejected a constant production statement '
                    'against the declared schema: ' + error + '. SQL: '
                    + re.sub(r'\s+', ' ', row.sql)[:1400]
                    + '. Fix the query/schema relationship and preserve feature behavior; '
                    'compilation is insufficient.'
                )
                # RETURNING/formatting edits may remove another defect while
                # this exact query's wrong-column debt remains. Compare the
                # error, owner, operation and tables, keeping multiplicity.
                tables = re.findall(r'\b(?:FROM|JOIN|UPDATE|INTO)\s+(' + _TABLE + ')', row.sql, re.I)
                identity = [row.file, row.owner, row.sql.split()[0].upper(),
                            sorted(t.strip('"`[]').lower() for t in tables), error.lower()]
                key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
                occurrences[key] += 1
                issues.append({'file': row.file, 'kind': 'persistence_sql_prepare', 'problem': problem,
                                   'contract_id': 'sqlite:' + key + ':' + str(occurrences[key]),
                                   'evidence': {'line': row.line, 'sql': row.sql, 'database': 'sqlite',
                                                'owner': row.owner, 'error': error,
                                                'method': 'isolated schema + EXPLAIN'}})
        return issues
    finally:
        for db in databases:
            db.close()
