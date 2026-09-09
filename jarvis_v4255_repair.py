"""One model-call policy, intact source evidence, and observable exact edits.

The existing router/provider, cancellation, compiler, transaction, checkpoint
and final acceptance seams remain authoritative. Historical instruction-only
wrappers no longer rewrite formats or cap a caller's output to 2,800 tokens.
"""
from __future__ import annotations
from contextvars import ContextVar
import json
import re
import sys
import jarvis_v4240_repair as control

VERSION = '42.55.0'
ENGINE = 'EXACT_MODEL_PROTOCOL_CONVERGENCE_FACTORY'
STRATEGY = 'functional-acceptance-v12-intact-model-protocol-native-test-ownership'
_ATOMIC_BUDGET = ContextVar('jarvis_atomic_prompt_budget', default=None)

POLICY = '''JARVIS CURRENT EXECUTION POLICY:
Follow this call's requested output format and schema exactly. Work from supplied current source, requirements, and validation evidence. Preserve public APIs and unrelated working features. Honor the requested language, framework, platform, and registered toolchain. Use existing providers and real persistence. Never weaken tests or silence diagnostics to claim progress. Edits are provisional until real validation succeeds; final completion requires the entire project's build, tests, runtime and original requirements.\n'''


def _stop():
    if control._STOP_EVENT.is_set():
        raise control.ProjectStopRequested('Stop requested at the model-call boundary.')


def install(g):
    previous_budget = g['_qwen_budget_prompt']
    previous_identity = g['_v36_release_identity']

    def budget(prompt, max_tokens=None, progress_callback=None, stage='Generating', profile=None):
        limit = _ATOMIC_BUDGET.get()
        if limit is None:
            return previous_budget(prompt,max_tokens,progress_callback,stage,profile)
        if len(str(prompt)) > limit:
            raise ValueError('Structured prompt exceeds the selected model context; source was not truncated.')
        return str(prompt)

    def qwen_call(prompt, progress_callback=None, stage='Generating', profile='chat', **kwargs):
        _stop()
        builder = kwargs.pop('prompt_builder', None)
        target, reason = g['_v426_route_for_call'](stage,profile,prompt)
        switched, detail = g['_v426_switch_for_call'](target,reason,progress_callback)
        _stop()
        if not switched:
            return False, 'Model routing failed: ' + str(detail)

        def emit():
            _stop()
            options = dict(kwargs)
            schema = options.get('response_schema')
            strict = bool(schema or options.get('strict_output') or builder or profile in {'generate','repair'})
            context = max(2048, int(g['_qwen_effective_context_tokens']()))
            requested = int(options.get('max_tokens') or {'repair':4096,'generate':8192}.get(profile,2048))
            # Leave room for complete current source even on a small manual
            # profile; large contexts retain the caller's real requested cap.
            output = max(64, min(requested, max(256,context//3)))
            options['max_tokens'] = output
            safety = max(512, min(2048,int(g.get('QWEN3_CONTEXT_SAFETY_TOKENS',1024))))
            chars = max(1, int((context-output-safety)*min(3.0,float(g.get('QWEN3_CHARS_PER_TOKEN',3.0)))))
            # Reserve space for the base provider's fallback schema and switch.
            overhead = len(POLICY)+len(json.dumps(schema,ensure_ascii=False) if schema else '')+1600
            body = builder(max(1,chars-overhead)) if builder else str(prompt or '')
            body = POLICY + '\n' + body
            token = _ATOMIC_BUDGET.set(chars if strict else None)
            try:
                # Capability proof must belong to the active model/endpoint,
                # not to a different AUTO model previously in the inference slot.
                active = str(g['_v426_active_profile']())
                if g.get('_v4255_schema_model') != active:
                    g['_QWEN_SCHEMA_CAPABILITY'] = None
                    g['_v4255_schema_model'] = active
                result = g['_v36_base_qwen_call'](body,progress_callback,stage,profile=profile,**options)
                _stop()
                return result
            finally:
                _ATOMIC_BUDGET.reset(token)

        try:
            result = emit()
            # Preserve the existing one-peer watchdog rescue in AUTO. Manual
            # model locks never cross over. Refit evidence after a switch.
            if (g.get('V427_WATCHDOG_RESCUE') and g['_v426_mode']() == 'auto'
                    and g['_v427_is_watchdog_failure'](result)):
                alternate = g['_v427_other_auto_model'](g['_v426_active_profile']())
                switched, detail = g['_v426_switch_for_call'](alternate,'watchdog rescue for same call',progress_callback)
                if switched:
                    result = emit()
            return result
        except control.ProjectStopRequested:
            raise
        except ValueError as exc:
            return False, 'Model request could not preserve complete evidence: ' + str(exc)

    for name, module in list(sys.modules.items()):
        if re.fullmatch(r'jarvis_v42(?:4[0-9]|5[0-4])_repair',name):
            module.VERSION, module.ENGINE = VERSION, ENGINE
            if hasattr(module,'STRATEGY'): module.STRATEGY = STRATEGY
            if hasattr(module,'STRATEGY_GENERATION'): module.STRATEGY_GENERATION = STRATEGY

    def identity():
        result = dict(previous_identity())
        result.update(version='V'+VERSION,engine=ENGINE,repair_strategy_generation=STRATEGY,
                      planner_mode='exact-model-protocol-convergence-v42.55',
                      single_model_call_policy=True, intact_structured_source_context=True,
                      transport_completion_required=True, original_source_atomic_patches=True,
                      semantic_sql_debt_identity=True, native_runner_test_ownership=True)
        return result

    g.update(_qwen_call=qwen_call,_qwen_budget_prompt=budget,_v36_release_identity=identity,
             JARVIS_REPAIR_STRATEGY_GENERATION=STRATEGY,V4255_VERSION=VERSION,V4255_ENGINE=ENGINE)
