from pathlib import Path
import ast

root = Path(__file__).resolve().parent
mp = (root / 'multi_provider.py').read_text(encoding='utf-8')
lq = (root / 'local_qwen_project.py').read_text(encoding='utf-8')
ps = (root / 'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')

# Syntax
ast.parse(mp)
ast.parse(lq)

# Server template/model settings
for needle in ("'--jinja'", "'--reasoning', 'off'", "'--repeat-penalty', '1.15'", "'-np', '1'"):
    assert needle in ps, needle

# Client task profiles and payload
for needle in (
    '"generate": {"temperature": 0.0, "max_tokens": 3072, "repetition_penalty": 1.15}',
    '"repair": {"temperature": 0.2, "max_tokens": 1536, "repetition_penalty": 1.15}',
    '"audit": {"temperature": 0.0, "max_tokens": 768, "repetition_penalty": 1.15}',
    '"repeat_penalty": selected["repetition_penalty"]',
    '"max_tokens": selected["max_tokens"]',
):
    assert needle in mp, needle

assert 'def _compact_feedback(' in lq
assert 'low_stage = str(stage or "").lower()' in lq
assert 'profile = "repair"' in lq
assert 'profile = "audit"' in lq
assert 'profile = "plan"' in lq
assert 'profile = "generate"' in lq
assert 'MAX_NO_PROGRESS_CYCLES' in lq
assert '_project_fingerprint' in lq

print('PASS: v2.66 Qwen model-specific tuning is present and syntactically valid.')
