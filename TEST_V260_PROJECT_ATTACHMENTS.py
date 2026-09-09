from pathlib import Path
import tempfile, zipfile, sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as lqp

with tempfile.TemporaryDirectory() as td:
    td=Path(td); src=td/'demo.zip'; out=td/'out'
    with zipfile.ZipFile(src,'w') as z:
        z.writestr('demo/main.py','print("hello")\n')
        z.writestr('demo/README.md','# Demo\n')
    n,total=lqp._safe_extract_existing_zip(src,out)
    assert n==2 and (out/'demo/main.py').exists()
    files=lqp._existing_project_text_files(out)
    assert 'demo/main.py' in files and 'demo/README.md' in files

with tempfile.TemporaryDirectory() as td:
    td=Path(td); bad=td/'bad.zip'; out=td/'out'
    with zipfile.ZipFile(bad,'w') as z:z.writestr('../escape.txt','nope')
    try:lqp._safe_extract_existing_zip(bad,out)
    except ValueError:pass
    else:raise AssertionError('Traversal ZIP was not rejected')
print('v2.60 attachment/extraction regression tests passed')
