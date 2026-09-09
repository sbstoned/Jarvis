from pathlib import Path
import ast
j=Path("jarvis.py").read_text(encoding="utf-8")
m=Path("multi_provider.py").read_text(encoding="utf-8")
ast.parse(j); ast.parse(m)
assert 'provider_status().get("nvidia")' in j
assert 'provider = "gemini"' in j
assert 'requested_provider in {"openai", "claude", "nvidia"}' in j
assert "credit_balance_exhausted" in j
assert "run_nvidia_coding_agent" in m
assert "NVIDIA_API_KEY" in m
assert "z-ai/glm-5.2" in m
print("v2.37 free-AI routing regression passed.")
