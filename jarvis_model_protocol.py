"""Exact, bounded model-edit protocol independent of project language."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import time
import uuid


def parse_object(raw):
    """Accept one JSON object, optionally fenced; never repair truncated code."""
    text = str(raw).strip().lstrip('\ufeff')
    fenced = re.fullmatch(r'```(?:json)?\s*\n([\s\S]*?)\n```', text, re.I)
    if fenced:
        text = fenced[1].strip()
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    try:
        obj = json.loads(text, object_pairs_hook=pairs,
                         parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Invalid JSON constant: '+value)))
    except json.JSONDecodeError as exc:
        fragment = text[max(0, exc.pos - 100):exc.pos + 140]
        raise ValueError(f'Invalid transaction JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}. '
                         f'Near {fragment!r}. Return one smaller complete JSON object with escaped source strings.') from exc
    if not isinstance(obj, dict):
        raise ValueError('Transaction must be one JSON object.')
    return obj


def parse_source_file(raw, path):
    """Read one complete, exactly named source envelope; never guess JSON edits.

    Used only for a supplied new test after JSON serialization failed. Transport
    completion is checked by the caller before this parser runs.
    """
    header = '<<<JARVIS_FILE path=' + json.dumps(path, ensure_ascii=False) + '>>>'
    text = str(raw).strip().lstrip('\ufeff')
    match = re.fullmatch(re.escape(header) + r'\r?\n([\s\S]+?)\r?\n<<<JARVIS_END_FILE>>>', text)
    if not match or not match[1].strip():
        raise ValueError('Expected exactly one complete source envelope for ' + path +
                         '; wrong paths, missing end markers and surrounding prose are rejected.')
    source = match[1]
    if re.search(r'(?m)^<<<JARVIS_(?:FILE|END_FILE|CONTINUATION)\b', source):
        raise ValueError('Multiple or nested source envelopes are not allowed.')
    return source + '\n'


def exact_replacements(current, replacements):
    """Resolve disjoint edits against the same original, then apply backwards.

    Identical duplicate blocks are harmless. Conflicting/overlapping blocks and
    ambiguous matches fail before any change. A generated REPLACE never becomes
    the accidental SEARCH target of a later block.
    """
    if not isinstance(replacements, list) or not 1 <= len(replacements) <= 30:
        raise ValueError('Provide 1-30 exact replacements per changed file.')
    source = current.replace('\r\n', '\n')
    spans, seen = [], set()
    for block in replacements:
        if not isinstance(block, dict) or set(block) != {'search','replace'}:
            raise ValueError('Each replacement needs exactly search and replace strings.')
        search, replace = block['search'], block['replace']
        if not isinstance(search,str) or not search or not isinstance(replace,str):
            raise ValueError('SEARCH must be nonempty and REPLACE must be text.')
        search, replace = search.replace('\r\n','\n'), replace.replace('\r\n','\n')
        if (search, replace) in seen:
            continue
        seen.add((search,replace))
        matches = [m.start() for m in re.finditer('(?=' + re.escape(search) + ')', source)]
        if len(matches) != 1:
            raise ValueError(f'SEARCH must match exactly once in the supplied ORIGINAL source; found {len(matches)} matches. '
                             f'Exact search: {search[:500]!r}. Copy current source including imports; do not search text created by another block.')
        start, end = matches[0], matches[0]+len(search)
        if any(start < b and a < end for a,b,_ in spans):
            raise ValueError('Overlapping replacement blocks. Combine them into one exact original-source SEARCH/REPLACE block.')
        spans.append((start,end,replace))
    for start,end,replace in sorted(spans, reverse=True):
        source = source[:start] + replace + source[end:]
    return source


def fit_source_prompt(header, evidence, target, budget):
    """Drop complete secondary files, never slice source/JSON in the middle."""
    selected = dict(evidence)
    def render():
        omitted = sorted(set(evidence) - set(selected))
        return (header + '\nOMITTED FILES (not editable in this response):\n' + json.dumps(omitted)
                + '\nCOMPLETE ALLOWED SOURCE FILES:\n' + json.dumps(selected, ensure_ascii=False))
    prompt = render()
    while len(prompt) > budget and len(selected) > 1:
        name = next(rel for rel in reversed(selected) if rel != target)
        selected.pop(name)
        prompt = render()
    if len(prompt) > budget:
        raise ValueError(f'Complete target and requirements need {len(prompt)} characters; selected model input budget is {budget}. '
                         'No source was truncated. Use a larger model context or a smaller source unit.')
    return prompt, selected


def save_response(root, target, attempt, raw, evidence, error='', status='received'):
    """Bounded local diagnostics and source hashes; no prompts or reasoning logs."""
    folder = Path(root)/'.jarvis_failures'/'model_outputs'
    folder.mkdir(parents=True, exist_ok=True)
    body = getattr(raw, 'partial_text', '') or str(raw)
    limit = 48000
    record = {
        'protocol':'exact-json-v12', 'target':target, 'attempt':attempt, 'status':status,
        'error':str(error)[-6000:], 'transport':getattr(raw,'metadata',{}),
        'response_chars':len(body), 'response_sha256':hashlib.sha256(body.encode()).hexdigest(),
        'response':body if len(body)<=limit else body[:limit//2]+'\n[diagnostic excerpt truncated]\n'+body[-limit//2:],
        'supplied_source_sha256':{rel:hashlib.sha256(text.encode()).hexdigest() for rel,text in evidence.items()},
    }
    path = folder/f'v4255_{time.time_ns()}_{uuid.uuid4().hex[:8]}.json'
    path.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    # Bound only this release's response journal. Leave other user diagnostics.
    for old in sorted(folder.glob('v4255_*.json'))[:-80]:
        old.unlink(missing_ok=True)
    return path
