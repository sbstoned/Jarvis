"""V42.69.2: safe resume-trial promotion and project-root rollover.

A real V42.69.1 GearTrack run proved the compiler-loop repair path by accepting two
functional repairs (8 -> 6), then exposed a Windows resume-sweep promotion bug.
The legacy promoter did `rmtree(work, ignore_errors=True)` followed by
`shutil.move(trial, work)`. If a rebuildable directory such as Cargo `target` was
still open, `rmtree` could leave the destination directory behind. `shutil.move`
then moved the whole trial *inside* that surviving directory, producing
`working/trial_01/...`; the next sweep faithfully cloned that malformed tree into
`trial_02/trial_01/...`.

V42.69.2 fixes the failure at the ownership boundary:
* accepted trials are source-synchronized into the authoritative workspace instead
  of moving a directory onto a possibly-surviving Windows destination;
* rebuildable/volatile directories are preserved in place while authored state is
  replaced exactly, so locked Cargo/npm caches cannot change project-root topology;
* resume cloning detects and unwraps a legacy `working/trial_NN` container before
  creating another trial and refuses destination-inside-source recursion;
* `.jarvis_memory` remains physically portable but is never treated as authored or
  planned application source by functional/whole-project acceptance;
* every promotion verifies the resulting root shape before the next sweep begins.

All V42.69.1 compiler-loop, durable-memory and strict acceptance gates remain active.
"""
from __future__ import annotations

import copy
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import jarvis_v4247_repair as functional_core
import jarvis_v4248_repair as functional_live
import jarvis_v4251_repair as transactions
import jarvis_v4261_repair as resume_copy
import jarvis_v4268_repair as sessions

VERSION = "42.69.2"
ENGINE = "SAFE_TRIAL_PROMOTION_COMPILER_LOOP_FACTORY"
STRATEGY = "functional-acceptance-v27-safe-trial-promotion"
MEMORY_DIR = ".jarvis_memory"

# These names are runtime/rebuildable infrastructure at any depth. They are kept in
# the authoritative workspace during a validated promotion instead of forcing a
# Windows delete of a live compiler/package cache.
_PRESERVE_DIRS = {
    str(x).casefold() for x in getattr(resume_copy, "BASE_SKIP_DIRS", set())
}
_PRESERVE_DIRS.update({MEMORY_DIR.casefold()})
_INTERNAL_AUDIT_DIRS = {
    str(x).casefold() for x in getattr(functional_live, "_INTERNAL_DIRS", set())
}
_INTERNAL_AUDIT_DIRS.add(MEMORY_DIR.casefold())

_ROOT_MARKERS = (
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "pubspec.yaml", "Package.swift", "composer.json", "Gemfile", "mix.exs",
)
_SOURCE_SUFFIXES = set(getattr(transactions, "SUFFIXES", set())) | {
    ".java", ".kt", ".kts", ".swift", ".php", ".rb", ".cs", ".fs", ".fsx"
}
_TRIAL_RE = re.compile(r"trial_\d+$", re.I)


def _internal_rel(rel: object) -> bool:
    parts = [p.casefold() for p in str(rel or "").replace("\\", "/").strip("/").split("/") if p]
    return any(p in _INTERNAL_AUDIT_DIRS for p in parts)


def _authored_file_count(root: Path, limit: int = 40) -> int:
    """Bounded root-shape signal; never walks rebuildable/runtime trees."""
    count = 0
    if not root.is_dir():
        return 0
    try:
        for directory, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.casefold() not in _PRESERVE_DIRS and not _TRIAL_RE.fullmatch(d)]
            for name in files:
                path = Path(directory) / name
                rel = path.relative_to(root).as_posix()
                if _internal_rel(rel) or name.upper().startswith("JARVIS_"):
                    continue
                if path.suffix.lower() in _SOURCE_SUFFIXES:
                    count += 1
                    if count >= limit:
                        return count
    except Exception:
        return count
    return count


def _project_root_score(root: Path) -> tuple[int, int, int]:
    root = Path(root)
    if not root.is_dir():
        return (0, 0, 0)
    markers = 0
    for name in _ROOT_MARKERS:
        if (root / name).is_file():
            markers += 1
    try:
        markers += min(2, len(list(root.glob("*.sln"))))
    except Exception:
        pass
    source_count = _authored_file_count(root)
    # A project with no conventional manifest can still be a valid script/source tree.
    looks = 1 if markers or source_count else 0
    return (looks, markers, source_count)


def _looks_like_project_root(root: Path) -> bool:
    return _project_root_score(Path(root))[0] > 0


def _container_candidates(root: Path) -> list[Path]:
    out = []
    try:
        children = list(Path(root).iterdir())
    except Exception:
        return out
    for child in children:
        if not child.is_dir():
            continue
        if child.name.casefold() == "working" or _TRIAL_RE.fullmatch(child.name):
            out.append(child)
    return out


def _resolve_project_root(root: Path) -> Path:
    """Recover one accidentally nested legacy trial without guessing inside a real project."""
    current = Path(root).resolve()
    for _ in range(4):
        if _looks_like_project_root(current):
            return current
        candidates = []
        for child in _container_candidates(current):
            resolved = child
            if not _looks_like_project_root(resolved):
                inner = _container_candidates(resolved)
                if len(inner) == 1 and _looks_like_project_root(inner[0]):
                    resolved = inner[0]
            score = _project_root_score(resolved)
            if score[0]:
                try:
                    mtime = int(resolved.stat().st_mtime_ns)
                except Exception:
                    mtime = 0
                candidates.append((score, mtime, resolved))
        if not candidates:
            return current
        candidates.sort(key=lambda row: (row[0], row[1]), reverse=True)
        current = candidates[0][2].resolve()
    return current


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except Exception:
        return False


def _remove_strict(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    if path.exists() or path.is_symlink():
        raise OSError(f"could not replace authored path during validated promotion: {path}")


def _prune_stale_authored(stage: Path, destination: Path) -> None:
    """Delete stale authored state while leaving rebuildable directories untouched."""
    if not destination.is_dir():
        return
    for dest_child in list(destination.iterdir()):
        if dest_child.name.casefold() in _PRESERVE_DIRS:
            continue
        source_child = stage / dest_child.name
        if not source_child.exists() and not source_child.is_symlink():
            _remove_strict(dest_child)
            continue
        if dest_child.is_dir() and source_child.is_dir() and not dest_child.is_symlink() and not source_child.is_symlink():
            _prune_stale_authored(source_child, dest_child)
            continue
        if dest_child.is_dir() != source_child.is_dir() or dest_child.is_symlink() != source_child.is_symlink():
            _remove_strict(dest_child)


def _copy_authored_into(stage: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for source_child in stage.iterdir():
        if source_child.name.casefold() in _PRESERVE_DIRS:
            continue
        dest_child = destination / source_child.name
        if source_child.is_dir() and not source_child.is_symlink():
            if dest_child.exists() and not dest_child.is_dir():
                _remove_strict(dest_child)
            dest_child.mkdir(parents=True, exist_ok=True)
            _copy_authored_into(source_child, dest_child)
        else:
            if dest_child.exists() and dest_child.is_dir():
                _remove_strict(dest_child)
            dest_child.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_child, dest_child, follow_symlinks=True)


def _sync_promoted_tree(stage: Path, destination: Path) -> None:
    """Replace accepted authored state in place without deleting live caches."""
    stage = Path(stage).resolve()
    destination = Path(destination).resolve()
    if not _looks_like_project_root(stage):
        raise RuntimeError(f"validated promotion source is not a project root: {stage}")
    destination.mkdir(parents=True, exist_ok=True)
    _prune_stale_authored(stage, destination)
    _copy_authored_into(stage, destination)
    if not _looks_like_project_root(destination):
        raise RuntimeError(f"validated promotion did not produce a valid project root: {destination}")
    # A surviving nested trial is a topology regression, not project source.
    nested = [p for p in _container_candidates(destination) if _looks_like_project_root(p)]
    if nested and not any((destination / marker).is_file() for marker in _ROOT_MARKERS) and _authored_file_count(destination) == 0:
        raise RuntimeError("validated promotion produced a nested trial/workspace instead of a flat project root")


def _sanitize_manifest_in_place(manifest: dict | None) -> int:
    if not isinstance(manifest, dict):
        return 0
    rows = manifest.get("files")
    if not isinstance(rows, list):
        return 0
    kept = []
    removed = 0
    for item in rows:
        rel = item.get("path") if isinstance(item, dict) else item
        if _internal_rel(rel):
            removed += 1
            continue
        kept.append(item)
    if removed:
        manifest["files"] = kept
    return removed


def install(g: dict[str, Any]) -> None:
    previous_identity = g["_v36_release_identity"]
    previous_progress = g["_progress"]
    previous_copy = g["_copy_resume_workspace"]
    previous_resume_sweeps = g["_run_resume_sweeps"]
    previous_audit = g["_v429_whole_project_audit"]

    # Functional/source iterators must never consider portable repair memory to be
    # application code. Keep the file physically present for checkpoint portability.
    try:
        functional_live._INTERNAL_DIRS.add(MEMORY_DIR)
        functional_core._SKIP_DIRS.add(MEMORY_DIR)
        transactions.SKIP.add(MEMORY_DIR)
    except Exception:
        pass

    def copy_resume_workspace(src, dst):
        raw_source = Path(src).resolve()
        destination = Path(dst).resolve()
        source = _resolve_project_root(raw_source)

        # Never recursively copy a job/container into one of its own trial folders.
        # If the caller handed us the container, only an unwrapped project child may
        # be used. Otherwise fail before corrupting topology.
        if _is_relative_to(destination, raw_source) and source == raw_source:
            raise RuntimeError(
                "RESUME_ROOT_GUARD: destination is inside the supplied source container and no "
                "unambiguous project root could be recovered; refusing recursive/nested trial copy."
            )

        result = previous_copy(source, destination)
        recovered = _resolve_project_root(destination)
        if recovered != destination:
            # A copy must always land project contents at the trial root. If an old
            # wrapper still produced nesting, flatten once through a sibling stage.
            flatten = destination.with_name(destination.name + ".v4269_2_flatten")
            previous_copy(recovered, flatten)
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=False)
            shutil.move(str(flatten), str(destination))
        if not _looks_like_project_root(destination):
            raise RuntimeError(f"RESUME_ROOT_GUARD: cloned trial is not a project root: {destination}")
        return destination

    def commit_resume_trial(trial, work, checkpoint_dir=None):
        trial = Path(trial).resolve()
        work = Path(work).resolve()
        source = _resolve_project_root(trial)
        current = _resolve_project_root(work) if work.exists() else work

        if checkpoint_dir is not None and work.exists():
            copy_resume_workspace(current, Path(checkpoint_dir))

        # Clone accepted authored state to a sibling staging root first. This proves
        # we have a complete source snapshot before touching the authoritative tree.
        stage = work.parent / f".jarvis_promote_{os.getpid()}_{time.time_ns()}"
        try:
            previous_copy(source, stage)
            _sync_promoted_tree(stage, work)
            try:
                sessions._write_portable_memory(work)
            except Exception:
                pass
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        # Trial cleanup is best-effort only after authoritative source is safely in
        # place. Locked caches may keep remnants on Windows, but they can no longer
        # alter the authoritative project-root topology.
        if trial != work:
            try:
                shutil.rmtree(trial, ignore_errors=True)
            except Exception:
                pass
        return None

    def run_resume_sweeps(user_request, manifest, work, job_root, progress_callback=None,
                          generic_resume=True, prior_issues=None, max_sweeps=None):
        removed = _sanitize_manifest_in_place(manifest)
        if removed:
            try:
                g["_append_project_event"](
                    work,
                    "v4269_2_internal_manifest_paths_removed",
                    f"V{VERSION} removed {removed} Jarvis-owned internal path(s) from the application manifest before resume validation.",
                    removed_count=removed,
                    final_acceptance=False,
                )
            except Exception:
                pass
        return previous_resume_sweeps(
            user_request, manifest, work, job_root, progress_callback,
            generic_resume=generic_resume, prior_issues=prior_issues, max_sweeps=max_sweeps,
        )

    def audit(root, request, manifest, run_components=True, progress_callback=None):
        clean_manifest = copy.deepcopy(manifest or {})
        _sanitize_manifest_in_place(clean_manifest)
        value = previous_audit(
            root, request, clean_manifest,
            run_components=run_components, progress_callback=progress_callback,
        )
        if not isinstance(value, dict):
            return value
        rows = [
            row for row in (value.get("issues") or [])
            if not (isinstance(row, dict) and _internal_rel(row.get("file")))
        ]
        if len(rows) != len(value.get("issues") or []):
            value = dict(value)
            value["issues"] = rows
            value["clean"] = bool(value.get("clean")) and not rows
        return value

    g["_copy_resume_workspace"] = copy_resume_workspace
    g["_commit_resume_trial"] = commit_resume_trial
    g["_run_resume_sweeps"] = run_resume_sweeps
    g["_v429_whole_project_audit"] = audit

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r"jarvis_v42(?:4[0-9]|5[0-9]|6[0-9](?:_\d+)?)_repair", name):
            try:
                module.VERSION = VERSION
                module.ENGINE = ENGINE
            except Exception:
                pass
            if hasattr(module, "STRATEGY"):
                module.STRATEGY = STRATEGY
            if hasattr(module, "STRATEGY_GENERATION"):
                module.STRATEGY_GENERATION = STRATEGY

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r"V42\.\d+(?:\.\d+)?(?!\d)", "V" + VERSION, str(text))
        fields = dict(fields)
        fields["engine_version"] = "V" + VERSION
        return previous_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version="V" + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode="compiler-loop-safe-trial-promotion-v42.69.2",
            safe_in_place_trial_promotion=True,
            windows_locked_cache_promotion_safe=True,
            trial_directory_move_into_existing_destination_disabled=True,
            resume_root_shape_guard=True,
            legacy_nested_trial_auto_unwrap=True,
            destination_inside_source_guard=True,
            portable_repair_memory_excluded_from_authored_audit=True,
            internal_manifest_path_sanitization=True,
            durable_project_repair_memory=True,
            same_transaction_compiler_refinement=True,
            rejected_candidate_source_never_promoted=True,
            compiler_and_functional_gates_preserved=True,
            manual_model_selection_strict_lock=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4269_2_VERSION=VERSION,
        V4269_2_ENGINE=ENGINE,
    )
    try:
        Path(
            g.get("JARVIS_DIR") or Path(__file__).resolve().parent,
            "JARVIS_ACTIVE_ENGINE.txt",
        ).write_text("V" + VERSION + "\n", encoding="utf-8")
    except OSError:
        pass
