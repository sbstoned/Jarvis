"""V42.69.3 release identity for dependency-closed functional repair sessions.

The fixes live in the existing session, transaction, proof, and workspace
implementations. This final bootstrap layer only advertises the active release.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

VERSION = '42.69.3'
ENGINE = 'DEPENDENCY_CLOSED_FUNCTIONAL_REPAIR_FACTORY'
STRATEGY = 'functional-acceptance-v28-dependency-closed-repair'


def install(g):
    previous_identity = g['_v36_release_identity']
    previous_progress = g['_progress']
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-9]|6[0-9](?:_\d+)?)_repair', name):
            module.VERSION, module.ENGINE = VERSION, ENGINE
            for field in ('STRATEGY', 'STRATEGY_GENERATION'):
                if hasattr(module, field):
                    setattr(module, field, STRATEGY)

    def identity():
        value = dict(previous_identity() or {})
        value.update(
            version='V' + VERSION, engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='dependency-closed-functional-repair-v42.69.3',
            functional_preflight_matches_promotion_gate=True,
            validator_owned_dependency_edits_in_same_candidate=True,
            max_related_candidate_files=3,
            all_changed_components_proved_inside_session=True,
            component_proof_cache_covers_related_source=True,
            cleanup_preserves_transaction_result=True,
            concurrent_source_change_blocks_promotion=True,
        )
        return value

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r'V42\.\d+(?:\.\d+)?(?!\d)', 'V' + VERSION, str(text))
        fields['engine_version'] = 'V' + VERSION
        return previous_progress(callback, text, **fields)

    g.update(_v36_release_identity=identity, _progress=progress,
             JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
             V4269_3_VERSION=VERSION, V4269_3_ENGINE=ENGINE)
    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent,
             'JARVIS_ACTIVE_ENGINE.txt').write_text('V' + VERSION + '\n', encoding='utf-8')
    except OSError:
        pass
