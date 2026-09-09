from pathlib import Path
import tempfile, sys, json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import local_qwen_project as lqp

# Placeholder detection regression: the exact failure mode from v2.60 must be rejected.
assert lqp._placeholder_or_stub('# Placeholder to ensure the module is fully defined.\n# The actual chat endpoints are provided below.\n')
assert not lqp._placeholder_or_stub('def add(a,b):\n    return a+b\n' * 20)

with tempfile.TemporaryDirectory() as td:
    work=Path(td)
    (work/'app/routes').mkdir(parents=True)
    (work/'app/__init__.py').write_text('from .routes.chat import register_chat\n\ndef create_app(app):\n    register_chat(app)\n',encoding='utf-8')
    (work/'app/models.py').write_text('class Message:\n    def __init__(self,text): self.text=text\n',encoding='utf-8')
    (work/'app/routes/chat.py').write_text('# Placeholder to ensure the module is fully defined.\n',encoding='utf-8')
    completed=['app/__init__.py','app/models.py','app/routes/chat.py']
    manifest={'files':completed,'project_name':'demo'}
    criteria=['Users can send and receive chat messages and retrieve chat history.']
    calls=[]
    def fake_qwen(prompt, progress_callback=None, stage='Generating'):
        calls.append((stage,prompt))
        if stage.startswith('Targeted repair 1/'):
            # First attempt repeats the old bad behavior and must not be written/count as success.
            return True, json.dumps({'summary':'done','files':[{'path':'app/routes/chat.py','content':'# Placeholder to ensure module.\\n# actual implementation provided below.\\n'}]})
        if stage.startswith('Targeted repair 2/'):
            return True, json.dumps({'summary':'implemented chat','files':[
                {'path':'app/routes/chat.py','content':'MESSAGES = []\n\ndef send_message(text):\n    msg = {"text": text}\n    MESSAGES.append(msg)\n    return msg\n\ndef get_history():\n    return list(MESSAGES)\n\ndef register_chat(app):\n    app.chat_send = send_message\n    app.chat_history = get_history\n'},
                {'path':'app/models.py','content':'class Message:\n    def __init__(self, text):\n        self.text = text\n'}
            ]})
        if stage == 'Verifying targeted repair':
            return True, json.dumps({'complete':True,'remaining':[],'next_files':[],'evidence':['send_message stores messages and get_history returns them']})
        raise AssertionError(stage)
    old=lqp._qwen_call
    lqp._qwen_call=fake_qwen
    try:
        result=lqp._repair_one_requirement('fix chat',manifest,criteria,work,completed,{'path':'app/routes/chat.py','instructions':'Implement chat send/receive and history'},max_attempts=4)
    finally:
        lqp._qwen_call=old
    assert result['complete'] is True, result
    text=(work/'app/routes/chat.py').read_text(encoding='utf-8')
    assert 'send_message' in text and 'get_history' in text
    assert result['attempts']==2
    # Related context should include registration/model files, not isolate chat.py.
    repair_prompts=[p for stage,p in calls if stage.startswith('Targeted repair')]
    assert any('app/__init__.py' in p and 'app/models.py' in p for p in repair_prompts)

print('v2.61 targeted repair engine regression tests passed')
