"""Disk-backed project uploads, independent of the AI worker and source language."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import zipfile

CHUNK_BYTES = 1024 * 1024
_ID = re.compile(r'^[a-f0-9]{32}$')
SOURCE_EXTENSIONS = set('zip txt md json yaml yml toml ini cfg py pyw js jsx ts tsx mts cts html css csv xml sql ps1 bat cmd dart java cpp cc c cxx h hpp cs go rs kt kts swift rb php lua r jl scala groovy gradle cmake ex exs erl hs sh f90 m mm clj cljs zig nim fs fsx ml mli lisp rkt sol vue svelte proto v sv vhdl pas d'.split())


class UploadError(Exception):
    def __init__(self, message, status=400, code='invalid_upload', **details):
        super().__init__(message)
        self.status, self.code, self.details = status, code, details

    def payload(self):
        return {'status': 'error', 'error': str(self), 'code': self.code, **self.details}


def safe_filename(name):
    name = str(name or '').replace('\\', '/').rsplit('/', 1)[-1].strip()
    name = ''.join(ch for ch in name if ch.isalnum() or ch in ' ._()-[]')
    stem, suffix = os.path.splitext(name)
    if suffix.lower().lstrip('.') not in SOURCE_EXTENSIONS:
        raise UploadError('Attach a project ZIP or a source file.', 415, 'unsupported_file')
    return (stem[:120].strip(' .') or 'project') + suffix.lower()


def validate_zip(path):
    """Check the ZIP index without extracting or executing application content.

    The existing safe importer subsequently reads source members and verifies
    their CRCs. Build/cache entries remain the importer's responsibility.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            entries = [info for info in archive.infolist() if not info.is_dir()]
            if not entries:
                raise UploadError('This ZIP contains no files. ZIP the project source folder and attach it again.', 422, 'empty_zip')
            for info in entries:
                name = info.filename.replace('\\', '/')
                if name.startswith('/') or re.match(r'^[A-Za-z]:', name) or '..' in name.split('/'):
                    raise UploadError('The ZIP contains an unsafe path: ' + name[:200], 422, 'unsafe_zip')
                if info.flag_bits & 1:
                    raise UploadError('Password-protected ZIPs cannot be imported. Attach an unencrypted project ZIP.', 422, 'encrypted_zip')
            return len(entries)
    except (zipfile.BadZipFile, EOFError) as exc:
        raise UploadError('This file is incomplete or is not a readable ZIP. Let Windows finish creating it, then select the saved ZIP again.', 422, 'invalid_zip') from exc


def needs_project_zip(command):
    text = re.sub(r'^\s*(?:use|ask)\s+\S+\s+to\s+', '', str(command or ''), flags=re.I)
    return bool(re.match(
        r'^\s*(?:please\s+)?(?:fix|repair|finish|complete|resume|continue)\b'
        r'.{0,70}\b(?:this|that|my|the|existing|attached|saved|last|uploaded)\s+'
        r'(?:(?:existing|attached|saved|last|uploaded)\s+)?(?:project|app|application|zip|checkpoint)\b',
        text, re.I))


class ProjectUploads:
    def __init__(self, root, max_bytes=4 * 1024**3):
        self.root = Path(root).resolve()
        self.sessions = self.root / '.upload_sessions'
        self.root.mkdir(parents=True, exist_ok=True)
        self.sessions.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes
        self.lock = threading.RLock()

    def _paths(self, upload_id):
        if not isinstance(upload_id, str) or not _ID.fullmatch(upload_id):
            raise UploadError('Unknown upload. Select the ZIP again.', 404, 'upload_not_found')
        return self.sessions / (upload_id + '.json'), self.sessions / (upload_id + '.part')

    def _load(self, upload_id):
        meta, part = self._paths(upload_id)
        try:
            row = json.loads(meta.read_text(encoding='utf-8'))
        except (FileNotFoundError, ValueError) as exc:
            raise UploadError('Upload session is unavailable. Select the saved ZIP again.', 404, 'upload_not_found') from exc
        return row, meta, part

    def _save(self, meta, row):
        temporary = meta.with_suffix('.tmp')
        row['updated_at'] = time.time()
        with temporary.open('w', encoding='utf-8') as stream:
            json.dump(row, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, meta)

    def _target(self, row):
        return self.root / (row['id'] + '_' + safe_filename(row['name']))

    def _status(self, row, part):
        target = self._target(row)
        complete = row.get('upload_status') == 'complete'
        if not complete and not part.is_file() and target.is_file():
            return self.complete(row['id'])
        path = target if complete else part
        if not path.is_file():
            raise UploadError('The uploaded file is no longer available. Select the ZIP again.', 410, 'upload_missing')
        received = path.stat().st_size
        result = {'status': 'ok', 'id': row['id'], 'name': row['name'], 'size': row['size'],
                  'received': received, 'chunk_size': CHUNK_BYTES,
                  'kind': 'zip' if row['name'].endswith('.zip') else 'file',
                  'upload_status': 'complete' if complete else 'uploading'}
        if complete:
            if received != row['size']:
                raise UploadError('The attached file changed after upload. Select it again.', 409, 'upload_changed')
            result['path'] = str(target)
            result['zip_entries'] = row.get('zip_entries')
        return result

    def create(self, data):
        if not isinstance(data, dict):
            raise UploadError('Invalid upload request.')
        name = safe_filename(data.get('name'))
        size = data.get('size')
        if type(size) is not int or size <= 0:
            raise UploadError('The selected file is empty or has an invalid size.', code='empty_upload')
        if size > self.max_bytes:
            raise UploadError(f'This file exceeds the configured {self.max_bytes // (1024 * 1024)} MB limit. ZIP the source folder without generated build or dependency folders, or raise JARVIS_CHAT_UPLOAD_MAX_BYTES.', 413, 'upload_too_large')
        upload_id = data.get('id') or uuid.uuid4().hex
        meta, part = self._paths(upload_id)
        with self.lock:
            if meta.exists():
                row, _, part = self._load(upload_id)
                if row['name'] != name or row['size'] != size:
                    raise UploadError('The upload ID belongs to a different file.', 409, 'upload_conflict')
                return self._status(row, part)
            if shutil.disk_usage(self.root).free < size + 16 * 1024 * 1024:
                raise UploadError('There is not enough free disk space to attach this file.', 507, 'disk_full')
            row = {'id': upload_id, 'name': name, 'size': size, 'upload_status': 'uploading'}
            part.touch(exist_ok=True)
            self._save(meta, row)
            return self._status(row, part)

    def status(self, upload_id):
        with self.lock:
            row, _, part = self._load(upload_id)
            return self._status(row, part)

    def chunk(self, upload_id, offset, content):
        if type(offset) is not int or offset < 0:
            raise UploadError('Invalid chunk offset.')
        if not content or len(content) > CHUNK_BYTES:
            raise UploadError('Invalid upload chunk size.', 413, 'invalid_chunk')
        with self.lock:
            row, _, part = self._load(upload_id)
            state = self._status(row, part)
            received = state['received']
            if offset + len(content) > row['size']:
                raise UploadError('Chunk exceeds the declared file size.', 409, 'offset_conflict', received=received)
            # Lost HTTP responses are retried safely: acknowledge already-saved
            # identical bytes, never append the same chunk a second time.
            if offset < received:
                path = self._target(row) if state['upload_status'] == 'complete' else part
                with path.open('rb') as stream:
                    stream.seek(offset)
                    identical = stream.read(len(content)) == content
                if offset + len(content) <= received and identical:
                    return state
                raise UploadError('The retried chunk does not match the saved file.', 409, 'chunk_mismatch', received=received)
            if offset != received or state['upload_status'] == 'complete':
                raise UploadError('Upload offset is out of order. Retry to resume from the saved position.', 409, 'offset_conflict', received=received)
            with part.open('r+b') as stream:
                stream.seek(received)
                try:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                except OSError:
                    stream.truncate(received)
                    raise
            return self._status(row, part)

    def complete(self, upload_id):
        with self.lock:
            row, meta, part = self._load(upload_id)
            if row.get('upload_status') == 'complete':
                return self._status(row, part)
            target = self._target(row)
            # Recover a process restart between atomic rename and metadata save.
            candidate = part if part.is_file() else target
            if not candidate.is_file() or candidate.stat().st_size != row['size']:
                raise UploadError('Upload is incomplete. Retry to send the remaining bytes.', 409, 'upload_incomplete')
            if row['name'].endswith('.zip'):
                row['zip_entries'] = validate_zip(candidate)
            if candidate == part:
                os.replace(part, target)
            row['upload_status'] = 'complete'
            self._save(meta, row)
            return self._status(row, part)

    def cancel(self, upload_id):
        with self.lock:
            meta, part = self._paths(upload_id)
            # A completed attachment may already be in use by a repair worker.
            # Removing a chip never deletes its accepted source ZIP.
            if meta.exists():
                row, _, _ = self._load(upload_id)
                if row.get('upload_status') == 'complete':
                    return {'status': 'ok'}
            part.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
            return {'status': 'ok'}

    def resolve_attachments(self, items, require_zip=False):
        if not isinstance(items, list) or len(items) > 8:
            raise UploadError('Attach at most eight files.', 422, 'invalid_attachments')
        result = []
        for item in items:
            if not isinstance(item, dict) or not item.get('path'):
                raise UploadError('An attachment has not finished uploading. Retry it before sending.', 422, 'attachment_incomplete')
            candidate = Path(str(item['path'])).resolve()
            if candidate.parent != self.root or not candidate.is_file():
                raise UploadError('An attached file is missing or unavailable. Reattach it before sending; no project was started.', 422, 'attachment_missing')
            if 'size' in item and item['size'] != candidate.stat().st_size:
                raise UploadError('An attached file changed after upload. Reattach it before sending.', 422, 'attachment_changed')
            kind = 'zip' if candidate.suffix.lower() == '.zip' else 'file'
            if kind == 'zip':
                validate_zip(candidate)
            result.append({'path': str(candidate), 'name': str(item.get('name') or candidate.name),
                           'kind': kind, 'size': candidate.stat().st_size})
        if require_zip and not any(row['kind'] == 'zip' for row in result):
            raise UploadError('Attach the saved project ZIP and wait until it says Ready to repair, then send your request.', 422, 'project_zip_required')
        return result
