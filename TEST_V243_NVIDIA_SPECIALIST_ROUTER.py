from pathlib import Path
import ast
m=Path("multi_provider.py").read_text(encoding="utf-8")
a=Path("ui/app.js").read_text(encoding="utf-8")
ast.parse(m)
assert '"general":(' in m and "deepseek-v4-flash-0731" in m
assert '"coding":(' in m
assert '"hard_reasoning":(' in m and "nemotron-3-ultra" in m
assert '"long_coding":(' in m and "laguna-xs-2.1" in m
assert '"vision":(' in m
assert "auto_long_coding" in m and "auto_vision" in m
assert "★ RECOMMENDED" in a
assert "deepseek-ai/deepseek-v4-flash-0731" in a
print("v2.43 NVIDIA specialist router regression passed.")
