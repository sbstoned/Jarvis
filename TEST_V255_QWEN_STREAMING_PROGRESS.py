import json
from unittest.mock import patch
import multi_provider

class FakeResponse:
    status_code = 200
    text = ''
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def iter_lines(self, decode_unicode=True):
        yield 'data: ' + json.dumps({'choices':[{'delta':{'content':'hello '}}]})
        yield 'data: ' + json.dumps({'choices':[{'delta':{'content':'world'}}]})
        yield 'data: [DONE]'

seen=[]
with patch.object(multi_provider.requests, 'post', return_value=FakeResponse()) as post:
    ok, text = multi_provider.ask_qwen('test', progress_callback=lambda x: seen.append(x), hard_timeout=60)
    assert ok and text == 'hello world'
    kwargs = post.call_args.kwargs
    assert kwargs['stream'] is True
    assert kwargs['timeout'][1] == multi_provider.QWEN_STREAM_IDLE_TIMEOUT
assert seen and seen[0]['streaming'] is True
print('PASS: v2.55 Qwen streaming + progress regression checks passed.')
