"""V42.61: volatile shared-build-cache isolation for resume/trial/checkpoint cloning.

A real resumed project exposed a Windows race after V42.20 introduced the sibling/shared
build cache.  Some resumed archives/workspaces can contain a nested
`.jarvis_shared_build_cache` tree.  Resume trial creation used shutil.copytree while npm
was mutating its content-addressed cache, so disappearing `_cacache` blobs raised
WinError 3 and aborted the project before Qwen could continue.

Shared dependency/build caches are rebuildable runtime infrastructure, never authored
project source.  V42.61 excludes them consistently from ZIP import, trial/checkpoint
clone, accepted-trial pruning, and packaging while preserving strict failure behavior
for real source files.
"""
from __future__ import annotations

import os
import re
import shutil
from jarvis_workspace_copy import copy_source_tree
import sys
import time
from pathlib import Path

VERSION = '42.61.0'
ENGINE = 'VOLATILE_SHARED_CACHE_ISOLATED_RESUME_FACTORY'
STRATEGY = 'functional-acceptance-v18-volatile-cache-isolated-connected-convergence'
SHARED_CACHE_DIR = '.jarvis_shared_build_cache'

# Rebuildable directory names that must never be source-cloned.  Keep this generic
# across languages/toolchains: package/build caches are reconstructed by validators.
BASE_SKIP_DIRS = {
    '.git', '.svn', '.hg', 'node_modules', 'vendor', 'dist', 'build', 'target',
    '.next', '.nuxt', '.idea', '.vscode', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', '.venv', 'venv', 'env', '.dart_tool',
    '.gradle', 'pods', 'Pods', 'deriveddata', 'DerivedData', '.jarvis_runtime',
    '.jarvis_build', '.jarvis_candidates', '.jarvis_backups', '.jarvis_failures',
    '.cache', 'coverage', '.turbo', '.parcel-cache', '.angular', '.svelte-kit',
    'out', 'bin', 'obj', SHARED_CACHE_DIR,
}


def _is_shared_cache_path(path) -> bool:
    try:
        return any(str(part).lower() == SHARED_CACHE_DIR for part in Path(path).parts)
    except Exception:
        return SHARED_CACHE_DIR in str(path).replace('\\', '/').lower().split('/')


def install(g):
    previous_identity = g['_v36_release_identity']
    previous_progress = g['_progress']
    previous_prune = g.get('_v4220_prune_rebuildable_tree')
    previous_package = g.get('_package_workspace_zip')

    # V42.11 ZIP import and V42.12 source-clone isolation consult these mutable sets
    # at execution time.  Extend both so old checkpoints containing the newer shared
    # cache are cleaned on import and can never re-enter an authored workspace.
    for name in ('_V4211_RESUME_SKIP_DIRS', '_V4212_CLONE_SKIP_DIRS'):
        rows = g.get(name)
        if isinstance(rows, set):
            rows.add(SHARED_CACHE_DIR)

    def _clone_ignore(_directory, names):
        return [name for name in names if str(name) in BASE_SKIP_DIRS or str(name).lower() in {x.lower() for x in BASE_SKIP_DIRS}]

    def copy_resume_workspace(src, dst):
        """Clone stable authored/resume state only; never clone volatile shared caches."""
        src = Path(src)
        dst = Path(dst)
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        dst.parent.mkdir(parents=True, exist_ok=True)

        # A source editor/AV can transiently race an authored file too.  Retry a
        # bounded number of times, but never swallow a persistent source failure.
        last = None
        for attempt in range(3):
            try:
                copy_source_tree(src, dst, ignore=_clone_ignore)
                return dst
            except shutil.Error as exc:
                last = exc
                shutil.rmtree(dst, ignore_errors=True)
                if attempt < 2:
                    time.sleep(0.15 * (attempt + 1))
                    continue
                raise
            except (FileNotFoundError, OSError) as exc:
                last = exc
                shutil.rmtree(dst, ignore_errors=True)
                if _is_shared_cache_path(getattr(exc, 'filename', '') or str(exc)):
                    # This should be unreachable because the directory is ignored,
                    # but one bounded retry handles a Windows traversal race safely.
                    if attempt < 2:
                        time.sleep(0.15 * (attempt + 1))
                        continue
                raise
        if last is not None:
            raise last
        return dst

    def prune_rebuildable_tree(root):
        removed = []
        if callable(previous_prune):
            try:
                removed.extend(previous_prune(root) or [])
            except Exception:
                pass
        root = Path(root)
        # Remove nested copies wherever they occur. This is safe because Jarvis owns
        # this exact hidden cache name and its contents are always reconstructable.
        for p in list(root.rglob(SHARED_CACHE_DIR)):
            try:
                if p.is_dir():
                    rel = p.relative_to(root).as_posix()
                    shutil.rmtree(p, ignore_errors=True)
                    removed.append(rel)
            except Exception:
                pass
        return list(dict.fromkeys(removed))

    def package_workspace_zip(work, name_stem, stamp=None):
        # Critical ordering: prune BEFORE calling inherited packaging. V42.20's
        # historical wrapper pruned after creating the ZIP, which was too late for
        # a nested shared cache already present in a resumed workspace.
        prune_rebuildable_tree(work)
        if not callable(previous_package):
            raise RuntimeError('Jarvis packaging function is unavailable.')
        return previous_package(work, name_stem, stamp)

    # Keep the stale-process boot marker aligned with the active release.
    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent, 'JARVIS_ACTIVE_ENGINE.txt').write_text(
            'V' + VERSION + '\n', encoding='utf-8'
        )
    except Exception:
        pass

    # Propagate release identity through the repair modules used by durable ledgers.
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-9]|60)_repair', name):
            try:
                module.VERSION = VERSION
                module.ENGINE = ENGINE
            except Exception:
                pass
            if hasattr(module, 'STRATEGY'):
                module.STRATEGY = STRATEGY
            if hasattr(module, 'STRATEGY_GENERATION'):
                module.STRATEGY_GENERATION = STRATEGY

    def progress(callback, text=None, **fields):
        if text is not None:
            text = str(text).replace('V42.60', 'V42.61')
        fields = dict(fields)
        fields['engine_version'] = 'V' + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='volatile-shared-cache-isolated-connected-convergence-v42.61',
            volatile_shared_build_cache_isolated=True,
            resume_zip_skips_shared_build_cache=True,
            resume_trial_skips_shared_build_cache=True,
            checkpoint_clone_skips_shared_build_cache=True,
            packaging_prunes_shared_build_cache_before_zip=True,
            authored_source_copy_failures_remain_strict=True,
            qwen38_native_context_max=262144,
            qwen38_runtime_context_default=40960,
            connected_functional_clusters=True,
            active_stream_wall_clock_unbounded=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _copy_resume_workspace=copy_resume_workspace,
        _v4220_prune_rebuildable_tree=prune_rebuildable_tree,
        _package_workspace_zip=package_workspace_zip,
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4261_VERSION=VERSION,
        V4261_ENGINE=ENGINE,
    )
