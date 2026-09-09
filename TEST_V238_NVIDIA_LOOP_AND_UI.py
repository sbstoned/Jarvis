from pathlib import Path
import ast
m=Path("multi_provider.py").read_text(encoding="utf-8")
h=Path("ui/index.html").read_text(encoding="utf-8")
ast.parse(m)
assert 'deepseek-ai/deepseek-v4-flash-0731' in m
assert 'nvidia_max_turns' in m
assert '18 if any(marker in task_low for marker in small_markers)' in m
assert 'That exact tool action already completed.' in m
assert 'forcing validation and final-diff phase' in m
assert 'validating completed work and finishing safely' in m
assert 'AUTO (FREE FIRST)' in h
assert '<option value="nvidia">NVIDIA</option>' in h
print("v2.38 NVIDIA loop/UI regression passed.")
