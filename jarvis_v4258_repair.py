"""V42.58: connected functional clusters with durable rejected-trial evidence.

V42.57 closed the evidence set and removed the active-stream wall clock, but late
functional repairs were still scheduled and scored by one arbitrary primary file.
V42.58 makes a small evidence-connected issue cluster the repair/progress unit,
while preserving compiler/component proofs, exact current-source edits, rollback,
new-debt rejection, idle/dead-stream handling and the final publication gate.
"""
from __future__ import annotations
import re
import sys
import jarvis_v4251_repair as transactions

VERSION='42.58.0'
ENGINE='CONNECTED_CLUSTER_FUNCTIONAL_TRANSACTIONS_FACTORY'
STRATEGY='functional-acceptance-v15-connected-cluster-transactions'


def install(g):
    previous_identity=g['_v36_release_identity']

    transactions.VERSION=VERSION
    transactions.ENGINE=ENGINE
    transactions.STRATEGY=STRATEGY
    transactions.MAX_FILES=18
    transactions.MAX_CHARS=120000
    transactions.MAX_ATTEMPTS=4
    transactions.MAX_CLUSTER_OWNERS=6
    try: transactions.SCHEMA['properties']['edits']['maxItems']=transactions.MAX_FILES
    except Exception: pass

    # Keep every installed repair layer's reporting identity coherent. This does
    # not bypass its guard: all repair/build/acceptance functions remain installed.
    for name,module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-7])_repair',name):
            module.VERSION=VERSION
            module.ENGINE=ENGINE
            if hasattr(module,'STRATEGY'): module.STRATEGY=STRATEGY
            if hasattr(module,'STRATEGY_GENERATION'): module.STRATEGY_GENERATION=STRATEGY

    # V42.57 intentionally removed only the absolute useful-stream wall clock.
    # Reassert that policy after older modules have loaded.
    def no_hard_timeout(_profile=None): return 0
    g['_qwen_profile_hard_timeout']=no_hard_timeout
    for key in ('QWEN_CALL_HARD_TIMEOUT_GENERATE','QWEN_CALL_HARD_TIMEOUT_REPAIR',
                'QWEN_CALL_HARD_TIMEOUT_PLAN','QWEN_CALL_HARD_TIMEOUT_AUDIT',
                'V427_27B_PLAN_TIMEOUT','V427_27B_REPAIR_TIMEOUT',
                'V427_27B_AUDIT_TIMEOUT','V427_27B_GENERATE_TIMEOUT'):
        if key in g: g[key]=0
    try:
        import multi_provider
        multi_provider.QWEN_STREAM_HARD_TIMEOUT=0
    except Exception: pass

    def identity():
        out=dict(previous_identity() or {})
        out.update(
            version='V'+VERSION, engine=ENGINE, repair_strategy_generation=STRATEGY,
            planner_mode='evidence-connected-functional-cluster-convergence-v42.58',
            functional_patch_only_primary_strategy=False,
            coordinated_functional_candidates=True,
            connected_functional_clusters=True,
            max_issue_owners_per_cluster=transactions.MAX_CLUSTER_OWNERS,
            cluster_progress_is_acceptance_unit=True,
            any_owned_issue_may_drive_strict_cluster_progress=True,
            per_owner_validator_scope=True,
            cluster_owned_regressions_rejected=True,
            independent_cluster_starvation_protection=True,
            rejected_trial_evidence_preserved=True,
            rejected_trial_source_never_promoted=True,
            rejected_trial_evidence_file='JARVIS_V4258_REJECTED_TRIAL_EVIDENCE.json',
            evidence_proven_scope_expansion=True,
            forced_complete_source_on_scope_retry=True,
            max_related_source_files=transactions.MAX_FILES,
            max_related_source_chars=transactions.MAX_CHARS,
            functional_model_attempts_per_transaction=transactions.MAX_ATTEMPTS,
            active_stream_absolute_timeout_seconds=0,
            active_stream_wall_clock_unbounded=True,
            dead_stream_idle_timeout_preserved=True,
            cooperative_user_stop_preserved=True,
            compiler_and_functional_gates_preserved=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(_v36_release_identity=identity,JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
             V4258_VERSION=VERSION,V4258_ENGINE=ENGINE)
