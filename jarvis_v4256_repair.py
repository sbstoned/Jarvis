"""V42.56: evidence-closed and validator-scoped functional convergence.

This release keeps every existing sandbox, compiler, functional and publication
check.  It strengthens the model transaction input/patch discipline so late-stage
repairs see the actual integration seam and cannot casually rewrite unrelated
working code inside a validator-owned target.
"""
from __future__ import annotations
import re
import sys
import jarvis_v4251_repair as transactions

VERSION = '42.56.0'
ENGINE = 'EVIDENCE_CLOSED_SCOPED_CONVERGENCE_FACTORY'
STRATEGY = 'functional-acceptance-v13-evidence-closed-scoped-transactions'


def install(g):
    previous_identity = g['_v36_release_identity']
    # repair_transaction resolves these globals from jarvis_v4251_repair at call
    # time, so the strengthened helpers remain authoritative through older wrappers.
    transactions.VERSION = VERSION
    transactions.ENGINE = ENGINE
    transactions.STRATEGY = STRATEGY
    transactions.MAX_FILES = 14
    transactions.MAX_CHARS = 90000
    transactions.MAX_ATTEMPTS = 3
    try:
        transactions.SCHEMA['properties']['edits']['maxItems'] = transactions.MAX_FILES
    except Exception:
        pass

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-5])_repair', name):
            module.VERSION = VERSION
            module.ENGINE = ENGINE
            if hasattr(module, 'STRATEGY'):
                module.STRATEGY = STRATEGY
            if hasattr(module, 'STRATEGY_GENERATION'):
                module.STRATEGY_GENERATION = STRATEGY

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='evidence-closed-validator-scoped-convergence-v42.56',
            integration_seam_evidence_priority=True,
            validator_owned_patch_scope=True,
            unrelated_hunk_pruning=True,
            exact_current_source_locators=True,
            stale_hunk_salvage=True,
            functional_model_attempts_per_transaction=3,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4256_VERSION=VERSION,
        V4256_ENGINE=ENGINE,
    )
