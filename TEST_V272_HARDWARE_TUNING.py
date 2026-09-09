from pathlib import Path
import ast

root = Path(__file__).resolve().parent
mp = (root / 'multi_provider.py').read_text(encoding='utf-8')
lq = (root / 'local_qwen_project.py').read_text(encoding='utf-8')
ps = (root / 'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')

ast.parse(mp)
ast.parse(lq)

# v2.73 supersedes v2.72 while retaining its core quality/caching guarantees.
for needle in (
    'Get-HardwareProfile',
    "'-b', \"$BatchSize\"",
    "'-ub', \"$UBatchSize\"",
    "'-t', \"$Threads\"",
    "'-tb', \"$ThreadsBatch\"",
    "'-ctk', 'q8_0'",
    "'-ctv', 'q8_0'",
    "'-fa', 'on'",
    "'--jinja'",
    "'--reasoning', 'off'",
    "'--repeat-penalty', '1.15'",
    "'-np', '1'",
    'qwen_runtime_profile.json',
):
    assert needle in ps, needle

assert '"cache_prompt": True' in mp
assert '"chat_template_kwargs": {"enable_thinking": False}' in mp
assert 'Stable instructions/task' in lq
print('PASS: v2.72 core Qwen guarantees remain present under v2.73 tuning.')
