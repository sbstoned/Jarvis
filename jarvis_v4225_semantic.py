"""Jarvis V42.25 semantic-code intelligence helpers.

Design inspiration: DeepSeek Harness's narrow, read-only LSP seam.  This module keeps
semantic navigation optional and bounded: ordinary repair context uses a deterministic
source index; when a compatible language server is already installed, callers may ask
for hover/definition/reference evidence without giving the model arbitrary JSON-RPC.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote, unquote, urlparse

_SOURCE_EXTS = {'.ts','.tsx','.mts','.cts','.js','.jsx','.rs','.py','.go','.java','.kt','.kts','.cs','.cpp','.cc','.cxx','.c','.h','.hpp'}
_TS_EXTS = {'.ts','.tsx','.mts','.cts','.js','.jsx'}
_IGNORE_DIRS = {'.git','node_modules','target','dist','build','.next','.nuxt','.venv','venv','env','__pycache__','.jarvis_runtime','.jarvis_build','.jarvis_candidates','.jarvis_failures','.jarvis_shared_build_cache'}


def _norm_rel(root: Path, p: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return p.as_posix().replace('\\','/')


def _iter_source(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in _IGNORE_DIRS]
        base = Path(d)
        for name in files:
            p = base / name
            if p.suffix.lower() in _SOURCE_EXTS:
                yield p


def _resolve_ts_import(root: Path, importer: Path, ref: str) -> Optional[Path]:
    if not ref.startswith(('./','../')):
        return None
    q = (importer.parent / ref).resolve()
    cands: List[Path] = []
    if q.suffix:
        cands.append(q)
    else:
        for ext in ('.ts','.tsx','.js','.jsx','.mts','.cts'):
            cands.append(Path(str(q)+ext))
        for ext in ('.ts','.tsx','.js','.jsx'):
            cands.append(q / ('index'+ext))
    for c in cands:
        try:
            c.resolve().relative_to(root.resolve())
        except Exception:
            continue
        if c.is_file():
            return c
    return None


def _symbol_at(text: str, line: int, col: int) -> str:
    lines = text.splitlines()
    if not lines:
        return ''
    li = max(0, min(len(lines)-1, int(line or 1)-1))
    s = lines[li]
    ci = max(0, min(len(s), int(col or 1)-1))
    left = ci
    right = ci
    while left > 0 and (s[left-1].isalnum() or s[left-1] in '_$'):
        left -= 1
    while right < len(s) and (s[right].isalnum() or s[right] in '_$'):
        right += 1
    return s[left:right]


def _public_signature_excerpt(text: str, max_chars: int = 2800) -> str:
    lines = text.splitlines()
    selected: List[str] = []
    capture = 0
    patterns = (
        r'^\s*export\s+(?:default\s+)?(?:interface|type|enum|class|function|const|let|var)\b',
        r'^\s*(?:export\s+)?interface\s+\w+(?:Props|Return|Options|State)\b',
        r'^\s*export\s+\{',
        r'^\s*const\s+\w+\s*:\s*React\.',
    )
    for line in lines:
        if any(re.search(p, line) for p in patterns):
            capture = 10
        if capture > 0:
            selected.append(line)
            capture -= 1
        if sum(len(x)+1 for x in selected) >= max_chars:
            break
    if not selected:
        selected = lines[:min(len(lines), 80)]
    out='\n'.join(selected)
    return out[:max_chars]


class SemanticIndex:
    """Cheap deterministic semantic index used before any LSP process is started."""
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.files = list(_iter_source(self.root))

    def imported_contracts(self, rel: str, max_files: int = 8, max_chars: int = 9000) -> str:
        p=(self.root/rel).resolve()
        try: text=p.read_text(encoding='utf-8',errors='replace')
        except Exception: return ''
        refs=[]
        for m in re.finditer(r'(?m)^\s*import\s+(?:type\s+)?(?:[^\n]*?\s+from\s+)?[\'\"]([^\'\"]+)[\'\"]', text):
            target=_resolve_ts_import(self.root,p,m.group(1))
            if target and target not in refs: refs.append(target)
        chunks=[]; used=0
        for target in refs[:max_files]:
            try: src=target.read_text(encoding='utf-8',errors='replace')
            except Exception: continue
            body=_public_signature_excerpt(src)
            block=f'READ-ONLY SEMANTIC CONTRACT {_norm_rel(self.root,target)}:\n{body}\n'
            if used+len(block)>max_chars:
                block=block[:max(0,max_chars-used)]
            if block:
                chunks.append(block);used+=len(block)
            if used>=max_chars: break
        return '\n'.join(chunks)

    def reverse_consumers(self, rel: str, max_files: int = 8, max_chars: int = 6000) -> str:
        target=(self.root/rel).resolve(); chunks=[];used=0
        for p in self.files:
            if p.suffix.lower() not in _TS_EXTS or p==target: continue
            try:text=p.read_text(encoding='utf-8',errors='replace')
            except Exception:continue
            hit=False
            for m in re.finditer(r'(?m)^\s*import\s+(?:type\s+)?(?:[^\n]*?\s+from\s+)?[\'\"]([^\'\"]+)[\'\"]',text):
                q=_resolve_ts_import(self.root,p,m.group(1))
                if q and q.resolve()==target: hit=True;break
            if not hit:continue
            excerpt='\n'.join(text.splitlines()[:120])[:2200]
            block=f'READ-ONLY REVERSE CONSUMER {_norm_rel(self.root,p)}:\n{excerpt}\n'
            if used+len(block)>max_chars:block=block[:max(0,max_chars-used)]
            if block:chunks.append(block);used+=len(block)
            if len(chunks)>=max_files or used>=max_chars:break
        return '\n'.join(chunks)

    def symbol_evidence(self, rel: str, line: int, col: int, max_hits: int = 12, max_chars: int = 7000) -> str:
        p=(self.root/rel).resolve()
        try:text=p.read_text(encoding='utf-8',errors='replace')
        except Exception:return ''
        sym=_symbol_at(text,line,col)
        if not sym or len(sym)<2:return ''
        defin=[];refs=[]
        defpat=re.compile(r'(?m)^\s*(?:export\s+)?(?:default\s+)?(?:interface|type|enum|class|function|const|let|var)\s+'+re.escape(sym)+r'\b')
        refpat=re.compile(r'\b'+re.escape(sym)+r'\b')
        for f in self.files:
            try:s=f.read_text(encoding='utf-8',errors='replace')
            except Exception:continue
            if defpat.search(s):defin.append(f)
            elif refpat.search(s):refs.append(f)
        hits=defin+refs
        chunks=[f'SEMANTIC SYMBOL: {sym} at {rel}:{line}:{col}']
        used=len(chunks[0])
        for f in hits[:max_hits]:
            try:s=f.read_text(encoding='utf-8',errors='replace')
            except Exception:continue
            body=_public_signature_excerpt(s,1800) if f in defin else '\n'.join(s.splitlines()[:90])[:1800]
            block=f"\n{'DEFINITION' if f in defin else 'REFERENCE'} {_norm_rel(self.root,f)}:\n{body}"
            if used+len(block)>max_chars:block=block[:max(0,max_chars-used)]
            if block:chunks.append(block);used+=len(block)
            if used>=max_chars:break
        return ''.join(chunks)


class _LspSession:
    def __init__(self, cmd: Sequence[str], root: Path, timeout: float = 12.0):
        self.cmd=list(cmd);self.root=root.resolve();self.timeout=timeout;self.proc=None;self.q=queue.Queue();self._reader=None;self._id=0

    def _write(self,obj:Dict[str,Any]):
        raw=json.dumps(obj,separators=(',',':'),ensure_ascii=False).encode('utf-8')
        self.proc.stdin.write(f'Content-Length: {len(raw)}\r\n\r\n'.encode('ascii')+raw);self.proc.stdin.flush()

    def _reader_loop(self):
        out=self.proc.stdout
        try:
            while True:
                headers={}
                while True:
                    line=out.readline()
                    if not line:return
                    if line in (b'\r\n',b'\n'):break
                    try:k,v=line.decode('ascii','replace').split(':',1);headers[k.lower().strip()]=v.strip()
                    except Exception:continue
                n=int(headers.get('content-length','0') or 0)
                if n<=0:continue
                body=out.read(n)
                try:self.q.put(json.loads(body.decode('utf-8','replace')))
                except Exception:continue
        except Exception:return

    def start(self):
        flags=0
        if os.name=='nt' and hasattr(subprocess,'CREATE_NO_WINDOW'):flags=subprocess.CREATE_NO_WINDOW
        self.proc=subprocess.Popen(self.cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,cwd=str(self.root),creationflags=flags)
        self._reader=threading.Thread(target=self._reader_loop,daemon=True);self._reader.start()
        uri=self.root.as_uri()
        result=self.request('initialize',{'processId':os.getpid(),'rootUri':uri,'capabilities':{},'workspaceFolders':[{'uri':uri,'name':self.root.name}]},timeout=self.timeout)
        self._write({'jsonrpc':'2.0','method':'initialized','params':{}})
        return result

    def request(self,method:str,params:Dict[str,Any],timeout:Optional[float]=None):
        self._id+=1;rid=self._id;self._write({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
        end=time.monotonic()+(timeout or self.timeout)
        stash=[]
        while time.monotonic()<end:
            try:item=self.q.get(timeout=max(.05,end-time.monotonic()))
            except queue.Empty:break
            if item.get('id')==rid:
                for x in stash:self.q.put(x)
                if 'error' in item:raise RuntimeError(str(item['error']))
                return item.get('result')
            stash.append(item)
        for x in stash:self.q.put(x)
        raise TimeoutError(f'LSP request timed out: {method}')

    def notify(self,method:str,params:Dict[str,Any]):
        self._write({'jsonrpc':'2.0','method':method,'params':params})

    def close(self):
        try:self.request('shutdown',{},timeout=2)
        except Exception:pass
        try:self.notify('exit',{})
        except Exception:pass
        try:self.proc.terminate()
        except Exception:pass
        try:self.proc.wait(timeout=2)
        except Exception:
            try:self.proc.kill()
            except Exception:pass


def _language_id(p:Path)->str:
    return {'.tsx':'typescriptreact','.ts':'typescript','.jsx':'javascriptreact','.js':'javascript','.rs':'rust','.py':'python'}.get(p.suffix.lower(),p.suffix.lower().lstrip('.'))


def _lsp_command(root:Path,p:Path)->Optional[List[str]]:
    ext=p.suffix.lower()
    env=''
    if ext in _TS_EXTS:
        env=os.getenv('JARVIS_LSP_TYPESCRIPT','').strip()
        names=['typescript-language-server.cmd','typescript-language-server'] if os.name=='nt' else ['typescript-language-server','typescript-language-server.cmd']
    elif ext=='.rs':
        env=os.getenv('JARVIS_LSP_RUST','').strip();names=['rust-analyzer.exe','rust-analyzer'] if os.name=='nt' else ['rust-analyzer']
    else:return None
    if env:return [env,'--stdio'] if ext in _TS_EXTS and '--stdio' not in env else [env]
    for name in names:
        q=root/'node_modules'/'.bin'/name
        if q.exists():return [str(q),'--stdio'] if ext in _TS_EXTS else [str(q)]
        w=shutil.which(name)
        if w:return [w,'--stdio'] if ext in _TS_EXTS else [w]
    return None


def lsp_query(root:str|Path, rel:str, line:int, col:int, operations:Sequence[str]=('hover','definition'), timeout:float=12.0)->Dict[str,Any]:
    root=Path(root).resolve();p=(root/rel).resolve()
    try:p.relative_to(root)
    except Exception:return {'available':False,'error':'outside workspace'}
    cmd=_lsp_command(root,p)
    if not cmd:return {'available':False,'error':'language server unavailable'}
    sess=_LspSession(cmd,root,timeout=timeout)
    out={'available':True,'provider':cmd[0],'results':{}}
    try:
        sess.start();text=p.read_text(encoding='utf-8',errors='replace');uri=p.as_uri();lang=_language_id(p)
        sess.notify('textDocument/didOpen',{'textDocument':{'uri':uri,'languageId':lang,'version':1,'text':text}})
        pos={'line':max(0,int(line)-1),'character':max(0,int(col)-1)}
        mapping={'hover':'textDocument/hover','definition':'textDocument/definition','references':'textDocument/references','implementation':'textDocument/implementation'}
        for op in operations:
            method=mapping.get(op)
            if not method:continue
            params={'textDocument':{'uri':uri},'position':pos}
            if op=='references':params['context']={'includeDeclaration':True}
            try:out['results'][op]=sess.request(method,params,timeout=timeout)
            except Exception as exc:out['results'][op]={'error':str(exc)}
        try:sess.notify('textDocument/didClose',{'textDocument':{'uri':uri}})
        except Exception:pass
    except Exception as exc:
        out={'available':False,'provider':cmd[0],'error':str(exc)}
    finally:
        try:sess.close()
        except Exception:pass
    return out


def render_lsp_result(root:str|Path, data:Dict[str,Any], max_chars:int=6000)->str:
    if not data.get('available'):return ''
    root=Path(root).resolve();chunks=[f"OPTIONAL LSP PROVIDER: {data.get('provider','')}\n"]
    for op,val in (data.get('results') or {}).items():
        if not val:continue
        if op=='hover':
            contents=val.get('contents') if isinstance(val,dict) else None
            if isinstance(contents,dict):contents=contents.get('value')
            if isinstance(contents,list):contents='\n'.join(str(x.get('value') if isinstance(x,dict) else x) for x in contents)
            chunks.append(f'LSP {op}:\n{str(contents)[:2200]}\n')
            continue
        arr=val if isinstance(val,list) else [val]
        rendered=[]
        for loc in arr[:20]:
            if not isinstance(loc,dict) or 'uri' not in loc:continue
            try:
                u=urlparse(loc['uri']);p=Path(unquote(u.path));
                if os.name=='nt' and re.match(r'^/[A-Za-z]:',str(p)):p=Path(str(p)[1:])
                name=_norm_rel(root,p)
            except Exception:name=str(loc.get('uri'))
            rng=loc.get('range') or {};st=rng.get('start') or {}
            rendered.append(f"{name}:{int(st.get('line',0))+1}:{int(st.get('character',0))+1}")
        if rendered:chunks.append(f'LSP {op}: '+', '.join(rendered)+'\n')
    return ''.join(chunks)[:max_chars]


def semantic_context(root:str|Path, rel:str, diagnostics:Sequence[Dict[str,Any]]|None=None, use_lsp:bool=False, max_chars:int=15000)->str:
    root=Path(root).resolve();idx=SemanticIndex(root);chunks=[]
    imported=idx.imported_contracts(rel,max_chars=max_chars//2)
    if imported:chunks.append(imported)
    reverse=idx.reverse_consumers(rel,max_chars=max_chars//3)
    if reverse:chunks.append(reverse)
    rows=list(diagnostics or [])
    if rows:
        r=rows[0];evid=idx.symbol_evidence(rel,int(r.get('line') or 1),int(r.get('col') or 1),max_chars=max_chars//3)
        if evid:chunks.append(evid)
        if use_lsp:
            data=lsp_query(root,rel,int(r.get('line') or 1),int(r.get('col') or 1),operations=('hover','definition','references'),timeout=float(os.getenv('JARVIS_V4225_LSP_TIMEOUT','10')))
            rendered=render_lsp_result(root,data,max_chars=max_chars//3)
            if rendered:chunks.append(rendered)
    return '\n\n'.join(chunks)[:max_chars]


def source_fingerprint(root:str|Path)->str:
    root=Path(root).resolve();h=hashlib.sha256()
    for p in sorted(_iter_source(root),key=lambda x:_norm_rel(root,x)):
        rel=_norm_rel(root,p);h.update(rel.encode());h.update(b'\0')
        try:h.update(p.read_bytes())
        except Exception:pass
        h.update(b'\0')
    return h.hexdigest()[:24]
