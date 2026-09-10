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

    # V42.64 and V42.65 are layered successors to this bootstrap. The main
    # project engine historically imported only V42.63, leaving the newer
    # functional/test endgame repairs present on disk but inactive. Activate
    # successors in order so each layer wraps the exact previous generation.
    emit = g.get('_emit')
    for module_name, label in (
        ('jarvis_v4264_repair', 'V42.64'),
        ('jarvis_v4265_repair', 'V42.65'),
    ):
        try:
            module = __import__(module_name)
            module.install(g)
        except ModuleNotFoundError as exc:
            if exc.name != module_name:
                raise
            if callable(emit):
                emit(f"[Jarvis/{label}] successor repair module unavailable: {exc}")
            break
        except Exception as exc:
            if callable(emit):
                emit(f"[Jarvis/{label}] successor repair activation failed: {exc}")
            raise
