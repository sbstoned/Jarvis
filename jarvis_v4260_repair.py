"""V42.60: hardware-fit runtime context for native-long-context local models.

V42.59 correctly separated target-slot context detection from MTP/draft metadata,
but then used Qwen3.8-27B's 262,144-token *native capability* as the default live
KV-cache allocation. On constrained local hardware that can prevent llama.cpp from
becoming healthy at all. V42.60 keeps 262,144 as capability metadata while using a
proven 40,960-token runtime by default, and makes connected repair output fit the
verified live slot.

This is model/runtime resource management, not project- or language-specific logic.
"""
from __future__ import annotations
import os,re,sys
from pathlib import Path
import jarvis_v4251_repair as transactions
import jarvis_v4259_repair as adaptive

VERSION='42.60.0'
ENGINE='HARDWARE_FIT_NATIVE_CONTEXT_MODEL_IO_FACTORY'
STRATEGY='functional-acceptance-v17-hardware-fit-native-context-connected-convergence'


def install(g):
    previous_identity=g['_v36_release_identity']
    previous_progress=g['_progress']

    # A 40,960-token live slot can safely reserve about half for structured output.
    # Users who explicitly raise the live context can also override this cap.
    if 'JARVIS_V4260_27B_REPAIR_OUTPUT_TOKENS' in os.environ:
        try: adaptive.CAP_27B=max(8192,int(os.environ['JARVIS_V4260_27B_REPAIR_OUTPUT_TOKENS']))
        except Exception: adaptive.CAP_27B=20480
    else:
        adaptive.CAP_27B=20480

    # V42.59 raised working ceilings to the native maximum. They are ceilings only,
    # but keep defaults aligned with a healthy hardware-fit runtime. The live /props
    # value remains the final authority in _qwen_budget_prompt.
    safe_defaults={
        'QWEN38_WORKING_CONTEXT_GENERATE':32768,
        'QWEN38_WORKING_CONTEXT_REPAIR':40960,
        'QWEN38_WORKING_CONTEXT_PLAN':40960,
        'QWEN38_WORKING_CONTEXT_AUDIT':32768,
        'QWEN38_WORKING_CONTEXT_MAX':65536,
    }
    for key,value in safe_defaults.items():
        env_name='JARVIS_'+key
        if env_name not in os.environ and key in g:
            try:g[key]=int(value)
            except Exception:pass

    transactions.VERSION=VERSION
    transactions.ENGINE=ENGINE
    transactions.STRATEGY=STRATEGY
    # Keep the stale-process boot marker aligned with the active release. V42.30
    # checks this file before work begins, so a packaged V42.60 tree must not
    # retain V42.59 merely because the marker was written earlier in import order.
    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent, 'JARVIS_ACTIVE_ENGINE.txt').write_text('V'+VERSION+'\n', encoding='utf-8')
    except Exception:
        pass
    for name,module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-9])_repair',name):
            try:module.VERSION=VERSION;module.ENGINE=ENGINE
            except Exception:pass
            if hasattr(module,'STRATEGY'):module.STRATEGY=STRATEGY
            if hasattr(module,'STRATEGY_GENERATION'):module.STRATEGY_GENERATION=STRATEGY

    def progress(callback,text=None,**fields):
        if text is not None:
            text=str(text).replace('V42.59','V42.60')
        fields=dict(fields);fields['engine_version']='V'+VERSION
        return previous_progress(callback,text,**fields)

    def identity():
        out=dict(previous_identity() or {})
        out.update(
            version='V'+VERSION,
            engine=ENGINE,
            repair_strategy_generation=STRATEGY,
            planner_mode='hardware-fit-native-context-connected-convergence-v42.60',
            qwen38_native_context_max=262144,
            qwen38_runtime_context_default=40960,
            qwen38_runtime_context_min=16384,
            qwen38_native_context_is_capability_not_forced_allocation=True,
            qwen38_runtime_context_env='JARVIS_QWEN_38_RUNTIME_CONTEXT',
            qwen27b_functional_output_cap=adaptive.CAP_27B,
            live_context_is_authoritative=True,
            connected_functional_clusters=True,
            cluster_progress_is_acceptance_unit=True,
            active_stream_wall_clock_unbounded=True,
            dead_stream_idle_timeout_preserved=True,
            compiler_and_functional_gates_preserved=True,
            language_framework_toolchain_agnostic=True,
        )
        return out

    g.update(
        _progress=progress,
        _v36_release_identity=identity,
        JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,
        V4260_VERSION=VERSION,
        V4260_ENGINE=ENGINE,
    )
