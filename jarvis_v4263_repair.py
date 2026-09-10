"""Release identity for verified native startup and strict dropdown routing."""
from pathlib import Path
import re
import sys

VERSION = '42.63.0'
ENGINE = 'VERIFIED_NATIVE_STARTUP_HYBRID_WORKFLOW_FACTORY'


def install(g):
    previous_identity = g['_v36_release_identity']
    base_progress = g.get('_v38_prev_progress', g['_progress'])
    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:[345][0-9]|6[012])_repair', name):
            module.VERSION, module.ENGINE = VERSION, ENGINE

    def progress(callback, text=None, **fields):
        if text is not None:
            text = re.sub(r'V42\.\d+(?:\.\d+)?(?!\d)', 'V' + VERSION, str(text))
        fields['engine_version'] = 'V' + VERSION
        return base_progress(callback, text, **fields)

    def identity():
        out = dict(previous_identity() or {})
        out.update(
            version='V' + VERSION, engine=ENGINE,
            native_process_readiness_controller=True,
            shared_dashboard_and_powershell_startup=True,
            bounded_same_model_memory_fallback=True,
            startup_native_log_diagnostics=True,
            startup_stop_cancels_native_process=True,
            auto_reuses_healthy_pool_member=True,
            auto_remembers_exhausted_loads_per_project=True,
            manual_model_selection_strict_lock=True,
            fast_routing_controls_preserved=True,
            default_9b_runtime_context=40960,
        )
        return out

    g.update(_v36_release_identity=identity, _progress=progress,
             V4263_VERSION=VERSION, V4263_ENGINE=ENGINE)
    try:
        Path(g.get('JARVIS_DIR') or Path(__file__).resolve().parent,
             'JARVIS_ACTIVE_ENGINE.txt').write_text('V' + VERSION + '\n', encoding='utf-8')
    except OSError:
        pass

    # V42.66 bounds connected transaction size and malformed-output recovery.
    from jarvis_v4266_repair import install as _v4266_install
    _v4266_install(g)

    # V42.67 narrows BEFORE evidence collection and replaces normal owner repairs
    # with compact target-only SEARCH/REPLACE transport. It also carries forward
    # the V42.65 workflow-test/cache endgame fixes without installing V42.63's
    # one-owner scheduler as the validation policy.
    from jarvis_v4267_repair import install as _v4267_install
    _v4267_install(g)

    # V42.68 keeps the V42.67 owner-local scheduler but lets the model work on one
    # issue through bounded host-controlled search/view/reference/edit/diagnose
    # turns. Current diagnostics and rejected repair history persist across trials.
    from jarvis_v4268_repair import install as _v4268_install
    _v4268_install(g)
