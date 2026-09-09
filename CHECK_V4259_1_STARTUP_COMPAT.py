from pathlib import Path
from unittest.mock import patch
import qwen_model_manager as qmm

ROOT = Path(__file__).resolve().parent
ps = (ROOT / 'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')

# Original optional launcher parameters must remain noninteractive. The native
# argument builder and saved dropdown resolver now live in the shared controller.
assert '[Parameter(Mandatory=$true)]' not in ps
assert '[string]$ModelPath = ""' in ps
assert '[string]$ServerExe = ""' in ps
assert "'qwen_model_manager.py'" in ps
assert '& $python @prefix @controllerArgs' in ps
assert 'exit $LASTEXITCODE' in ps
assert "'--model-path', $ModelPath" in ps
assert "'--context-tokens', [string]$ContextTokens" in ps
assert "'--max-output-tokens', [string]$MaxOutputTokens" in ps
for profile in ('auto', '9b35', '27b38q2', '8b', '27b'):
    with patch.object(qmm, 'selected_profile', return_value=profile), patch.object(qmm, 'ensure_qwen_profile', return_value=(True,'ready')) as start:
        assert qmm._main([]) == 0
        assert start.call_args.args[0] == profile
        assert start.call_args.kwargs['persist_selection'] is False
args = qmm._server_command('27b38q2', {'context':40960,'gpu_layers':'all'})
assert args[args.index('-m') + 1] == qmm.MODEL_PROFILES['27b38q2']['path']
assert args[args.index('-c') + 1] == '40960'
assert args[args.index('-np') + 1] == '1'
assert '--no-context-shift' in args
print('Startup compatibility checks passed with the V42.63 shared controller.')
