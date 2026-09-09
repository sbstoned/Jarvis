from pathlib import Path
import os,sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import qwen_model_manager as qmm
import multi_provider as mp

class V4260HardwareFit(unittest.TestCase):
    def test_27b_native_max_and_runtime_default_are_separate(self):
        self.assertEqual(qmm.MODEL_PROFILES['27b38q2']['native_context'],262144)
        self.assertEqual(qmm.MODEL_PROFILES['27b38q2']['runtime_context_default'],40960)
        with patch.dict(os.environ,{},clear=False):
            for k in ('JARVIS_QWEN_38_RUNTIME_CONTEXT','JARVIS_QWEN_38_CONTEXT','JARVIS_QWEN_38_27B_CONTEXT'):
                os.environ.pop(k,None)
            self.assertEqual(qmm._desired_context('27b38q2'),40960)

    def test_27b_explicit_context_can_raise_to_native_max(self):
        with patch.dict(os.environ,{'JARVIS_QWEN_38_RUNTIME_CONTEXT':'65536'},clear=False):
            self.assertEqual(qmm._desired_context('27b38q2'),65536)
        with patch.dict(os.environ,{'JARVIS_QWEN_38_RUNTIME_CONTEXT':'262144'},clear=False):
            self.assertEqual(qmm._desired_context('27b38q2'),262144)

    def test_launcher_defaults_to_hardware_fit_not_native_max(self):
        ps=(ROOT/'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')
        self.assertIn("'qwen_model_manager.py'",ps)
        self.assertEqual(qmm._desired_context('27b38q2'),40960)
        command=qmm._server_command('27b38q2',{'context':qmm._desired_context('27b38q2'),'gpu_layers':'all'})
        self.assertEqual(command[command.index('-c')+1],'40960')
        self.assertEqual(qmm.MODEL_PROFILES['27b38q2']['native_context'],262144)

    def test_6144_true_target_is_still_rejected(self):
        with patch.object(qmm,'_health',return_value=True), patch.object(qmm,'active_profile',return_value='27b38q2'), patch.object(qmm,'_runtime_context_tokens',return_value=6144), patch.object(qmm,'_windows_server_commandline',return_value='llama-server.exe -np 1 --no-context-shift -c 6144'):
            self.assertFalse(qmm._runtime_matches('27b38q2'))

    def test_healthy_32768_fallback_is_accepted(self):
        with patch.object(qmm,'_health',return_value=True), patch.object(qmm,'active_profile',return_value='27b38q2'), patch.object(qmm,'_runtime_context_tokens',return_value=32768), patch.object(qmm,'_windows_server_commandline',return_value='llama-server.exe -np 1 --no-context-shift -c 32768'):
            self.assertTrue(qmm._runtime_matches('27b38q2'))

    def test_provider_source_caps_qwen38_output_to_live_half_slot(self):
        src=(ROOT/'multi_provider.py').read_text(encoding='utf-8')
        self.assertIn('safe_output = max(4096, min(20480, live_ctx // 2))',src)
        self.assertIn('selected_max_tokens = min(selected_max_tokens, safe_output)',src)

    def test_startup_modelpath_remains_optional(self):
        ps=(ROOT/'START_QWEN_LOCAL.ps1').read_text(encoding='utf-8')
        self.assertIn('[string]$ModelPath = ""',ps)
        self.assertIn('if (-not [string]::IsNullOrWhiteSpace($ModelPath))',ps)

if __name__=='__main__': unittest.main(verbosity=2)
