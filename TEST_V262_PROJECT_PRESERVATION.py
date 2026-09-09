from pathlib import Path
import tempfile
from local_qwen_project import _audit_is_internally_consistent

def test_audit_consistency():
    assert _audit_is_internally_consistent({"complete": True, "missing": []})
    assert not _audit_is_internally_consistent({"complete": False, "missing": [], "repairs": [], "notes": []})
    assert _audit_is_internally_consistent({"complete": False, "missing": ["x"]})

if __name__ == "__main__":
    test_audit_consistency(); print("v2.62 repair engine regression checks passed")
