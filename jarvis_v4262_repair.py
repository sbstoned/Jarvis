"""Release identity for shared candidate isolation and test protocol recovery.

The fixes live at the actual copy/transaction boundaries, so inherited callers
and captured function references receive the same policy without replacement
validators or language-specific shortcuts.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

from jarvis_workspace_copy import VOLATILE_DIRS

VERSION = '42.62.0'
ENGINE = 'UNIFIED_CANDIDATE_ISOLATION_WORKFLOW_RECOVERY_FACTORY'
STRATEGY = 'functional-acceptance-v19-candidate-preflight-source-envelope-recovery'


def install(g):
    previous_identity = g['_v36_release_identity']
    base_progress = g.get('_v38_prev_progress', g['_progress'])
    # Scanning and ZIP imports must respect the same owned artifact boundaries.
    for name in ('_ANALYSIS_IGNORE_DIRS', '_V4211_RESUME_SKIP_DIRS', '_V4212_CLONE_SKIP_DIRS'):
        if isinstance(g.get(name), set):
            g[name].update(VOLATILE_DIRS)

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:[345][0-9]|6[01])_repair', name):
            module.VERSION, module.ENGINE = VERSION, ENGINE
            for key in ('STRATEGY', 'STRATEGY_GENERATION'):
                if hasattr(module, key):
                    setattr(module, key, STRATEGY)
            for key in ('_DISCOVERY_SKIP', '_DIFF_SKIP', 'SKIP'):
                if isinstance(getattr(module, key, None), set):
                    getattr(module, key).update(VOLATILE_DIRS)

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r'V42\.\d+(?:\.\d+)?(?!\d)', 'V' + VERSION, str(text))
        fields['engine_version'] = 'V' + VERSION
        return base_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION, engine=ENGINE, repair_strategy_generation=STRATEGY,
            planner_mode='shared-candidate-isolation-test-protocol-recovery-v42.62',
            all_source_copies_exclude_owned_volatile_caches=True,
            disposable_candidate_cache_isolation=True,
            candidate_clone_preflight_before_model=True,
            candidate_filesystem_retry_without_model=True,
            infrastructure_copy_failure_preserves_model_budget=True,
            new_test_raw_envelope_after_invalid_json=True,
            truncation_recovery_at_output_cap=True,
            authored_source_copy_failures_remain_strict=True,
            compiler_and_functional_gates_preserved=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(_v36_release_identity=identity, _progress=progress,
             JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
             V4262_VERSION=VERSION, V4262_ENGINE=ENGINE)
    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent,
             'JARVIS_ACTIVE_ENGINE.txt').write_text('V' + VERSION + '\n', encoding='utf-8')
    except OSError:
        pass
