"""Shared source-copy policy for every disposable Jarvis workspace.

Rebuildable Jarvis artifacts must be excluded before traversal, even when an
older caller has its own ignore list. Authored file failures remain fatal.
"""
from __future__ import annotations

from contextvars import ContextVar
import os
from pathlib import Path
import shutil
import time


VOLATILE_DIRS = frozenset({
    '.jarvis_shared_build_cache', '.jarvis_runtime', '.jarvis_artifacts',
    '.jarvis_build', '.jarvis_candidates', '.jarvis_backups', '.jarvis_failures',
})
_WORKSPACE_FAILURE = ContextVar('jarvis_candidate_workspace_failure', default=None)


def clear_workspace_failure():
    _WORKSPACE_FAILURE.set(None)


def workspace_failure(root):
    record = _WORKSPACE_FAILURE.get()
    return record[1] if record and record[0] == str(Path(root).resolve()) else ''


class CandidateWorkspaceError(OSError):
    """Validation infrastructure failed before a model candidate was requested."""


def copy_source_tree(src, dst, *, ignore=None, **kwargs):
    """Compose the caller's exclusions with owned caches at every depth.

    Never suppress missing/locked source or use ignore_dangling_symlinks as a
    workaround. Case folding covers Windows paths and old imported archives.
    No cache is traversed or deleted in the accepted workspace.
    """
    def source_ignore(directory, names):
        skipped = set(ignore(directory, names) or ()) if ignore else set()
        skipped.update(name for name in names if name.casefold() in VOLATILE_DIRS)
        return skipped

    existed = os.path.lexists(dst)
    try:
        return shutil.copytree(src, dst, ignore=source_ignore, **kwargs)
    except (OSError, shutil.Error):
        if not existed:
            shutil.rmtree(dst, ignore_errors=True)
        raise


def prepare_candidate_workspace(g, root, callback=None):
    """Retry a transient clone failure once, without spending a model attempt."""
    from jarvis_v4240_repair import _STOP_EVENT, ProjectStopRequested

    clear_workspace_failure()
    for attempt in range(2):
        if _STOP_EVENT.is_set():
            raise ProjectStopRequested('Stop requested before candidate workspace preparation.')
        try:
            return g['_copy_project_for_candidate_validation'](root)
        except (OSError, shutil.Error) as exc:
            if attempt:
                error = CandidateWorkspaceError(
                    'CANDIDATE_WORKSPACE_UNAVAILABLE: could not clone authored source after two attempts. '
                    'No model call or accepted-source edit was made. Resolve the filesystem failure '
                    'and resume the checkpoint. Cause: ' + str(exc)[-4000:]
                )
                _WORKSPACE_FAILURE.set((str(Path(root).resolve()), str(error)))
                raise error from exc
            progress = g.get('_progress')
            if callable(progress):
                progress(callback, 'Candidate workspace copy failed; retrying preparation before model generation.',
                         stage='Candidate workspace preparation', percent=92)
            time.sleep(0.15)
