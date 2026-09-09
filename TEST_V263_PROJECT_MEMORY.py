import json
import tempfile
from pathlib import Path
import local_qwen_project as lqp


def main():
    with tempfile.TemporaryDirectory() as td:
        work=Path(td)
        (work/'app.py').write_text('def old():\n    return 1\n', encoding='utf-8')
        completed=['app.py']
        criteria=['Feature X works']
        lqp._initialize_project_memory(work, 'demo.zip', 'finish feature x', criteria, completed)
        state=lqp._load_project_state(work)
        assert state['revision']==0
        assert state['unresolved_requirements']==criteria

        responses=[
            (True, json.dumps({'summary':'implemented feature x','files':[{'path':'app.py','content':'def feature_x():\n    return "ok"\n'}]})),
            (True, json.dumps({'complete':True,'remaining':[],'next_files':[],'evidence':['feature_x exists']})),
        ]
        old=lqp._qwen_call
        def fake(*a, **k):
            return responses.pop(0)
        lqp._qwen_call=fake
        try:
            result=lqp._repair_one_requirement('finish feature x', {'files':completed}, criteria, work, completed, {'path':'app.py','instructions':'Feature X works'}, max_attempts=2)
        finally:
            lqp._qwen_call=old
        assert result['complete'] is True
        state=lqp._load_project_state(work)
        assert state['revision']==1
        assert 'app.py' in state['modified_files']
        assert state['accepted_changes'][-1]['summary']=='implemented feature x'
        summary=lqp._project_memory_summary(work)
        assert 'implemented feature x' in summary
        assert 'feature_x exists' in summary
        assert lqp.PROJECT_STATE_FILE not in lqp._existing_project_text_files(work)
        assert lqp.PROJECT_JOURNAL_FILE not in lqp._existing_project_text_files(work)
        print('v2.63 project memory regression: PASS')

if __name__=='__main__':
    main()
