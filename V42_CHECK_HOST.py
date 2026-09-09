from pathlib import Path
import json
import jarvis_v42_runtime as R
root=Path(__file__).resolve().parent
data=R.write_capability_report(root,probe_versions=True)
print(f"Jarvis V42 host capability report: {data.get('available_count')}/{data.get('known_count')} capabilities available")
for name,row in sorted((data.get('tools') or {}).items()):
    if row.get('available'):
        version=(' - '+row.get('version')) if row.get('version') else ''
        print(f"  [OK] {name}: {row.get('path') or 'detected'}{version}")
print('\nReport written to:',root/R.CAPABILITY_FILE)
