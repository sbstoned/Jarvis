from pathlib import Path
import ast

root = Path(__file__).resolve().parent
ps = (root / 'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')
mp = (root / 'multi_provider.py').read_text(encoding='utf-8')
lq = (root / 'local_qwen_project.py').read_text(encoding='utf-8')

ast.parse(mp)
ast.parse(lq)

for needle in (
    'AvailableRamGB',
    '$LowRamLargeModel',
    '$Target8GBLargeModel',
    '$DefaultContext = 4096',
    '$DefaultBatch = 512',
    '$DefaultUBatch = 128',
    '$AutoManualNgl = 30',
    "@('-ngl', \"$ChosenNgl\")",
    "@('--fit', 'off')",
    "$LoadMode = 'none'",
    "@('--prio', '2', '--prio-batch', '2')",
    "'-ctk', 'q8_0'",
    "'-ctv', 'q8_0'",
    "'-fa', 'on'",
    "'--jinja'",
    "'--reasoning', 'off'",
    "'--repeat-penalty', '1.15'",
    "'-np', '1'",
    "version = 'v2.74.1'",
    '$AutoLoadFallbackUsed',
    'retrying automatically with mmap',
):
    assert needle in ps, needle

assert 'QWEN_PROJECT_AGENT_MEMORY_CHARS = int(os.getenv("JARVIS_QWEN_PROJECT_AGENT_MEMORY_CHARS", "1600"))' in lq
assert 'QWEN_PROJECT_AGENT_RESULT_CHARS = int(os.getenv("JARVIS_QWEN_PROJECT_AGENT_RESULT_CHARS", "3200"))' in lq
assert 'QWEN_PROJECT_AGENT_PROMPT_MAX = int(os.getenv("JARVIS_QWEN_PROJECT_AGENT_PROMPT_MAX", "9000"))' in lq
assert "JARVIS_QWEN_BOOTSTRAP_MAX_TOKENS', '3072'" in lq
assert 'max_tokens=1536' in lq
assert '"repair": {"temperature": 0.2, "max_tokens": 1536, "repetition_penalty": 1.15}' in mp
assert '"generate": {"temperature": 0.0, "max_tokens": 3072, "repetition_penalty": 1.15}' in mp
assert '"cache_prompt": True' in mp
assert '"chat_template_kwargs": {"enable_thinking": False}' in mp

print('PASS: v2.73 quality-first low-RAM guarantees remain present in v2.74.1.')
