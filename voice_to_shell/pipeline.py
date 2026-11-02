"""
End-to-End Voice to Shell Pipeline
Replicates Fig. 1 and Section III-A from IEEE JIOT 2026 paper:
Microphone / Text -> STT -> FIX -> TTC -> Safety Gate -> Shell Execution
"""

from typing import Optional, Dict, Any, Union
from voice_to_shell.stt import SpeechToText
from voice_to_shell.fix import TranscriptFixer
from voice_to_shell.ttc import TextToCommand
from voice_to_shell.safety import CommandSafetyAnalyzer, RiskLevel
from voice_to_shell.shell_executor import ShellExecutor, ExecutionResult
from voice_to_shell.metrics import ResourceMonitor


class VoiceToShellPipeline:
    """End-to-end edge-deployable voice assistant for IoT maintenance."""

    def __init__(
        self,
        stt_model: str = "openai/whisper-tiny",
        ttc_model_path: Optional[str] = None,
        use_t5: bool = False,
        force_mock_shell: bool = False
    ):
        self.stt = SpeechToText(model_name=stt_model)
        self.fixer = TranscriptFixer()
        self.ttc = TextToCommand(model_dir=ttc_model_path, use_t5=use_t5)
        self.executor = ShellExecutor(force_mock=force_mock_shell)
        self.safety = CommandSafetyAnalyzer()

    def process(
        self,
        input_data: Union[str, bytes],
        is_audio: bool = False,
        context: str = "docker",
        language: str = "en",
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Execute full Voice-to-Shell pipeline:
        Audio/Text -> STT -> FIX -> TTC -> Safety Evaluation -> (Execution)
        """
        monitor = ResourceMonitor()
        monitor.start()

        # Step 1: STT (Speech to Text)
        stt_info = {}
        if is_audio:
            task = "translate" if language == "es" else "transcribe"
            stt_res = self.stt.transcribe(input_data, language=language, task=task)
            raw_prompt = stt_res.get("text", "")
            stt_info = stt_res
        else:
            raw_prompt = str(input_data).strip()

        # Step 2: FIX (Domain Spell Checker & Normalizer)
        fixed_prompt = self.fixer.fix(raw_prompt, context=context)

        # Step 3: TTC (Text to Command via SLM)
        command = self.ttc.generate(fixed_prompt, context=context)

        # Step 4: Safety / Human-in-the-Loop Gate
        safety_eval = self.safety.evaluate(command)

        # Step 5: Execution (if auto_execute permitted or confirmed)
        exec_result = None
        if auto_execute:
            exec_result = self.executor.execute(command, context=context)

        perf = monitor.stop()

        return {
            "input": raw_prompt if not is_audio else f"<Audio input: {input_data}>",
            "is_audio": is_audio,
            "raw_transcript": raw_prompt,
            "fixed_prompt": fixed_prompt,
            "context": context,
            "generated_command": command,
            "safety": safety_eval,
            "requires_confirmation": safety_eval["requires_confirmation"],
            "execution": exec_result.to_dict() if exec_result else None,
            "performance": perf
        }

    def confirm_and_execute(self, command: str, context: str = "docker") -> ExecutionResult:
        """User confirms execution of the proposed command."""
        return self.executor.execute(command, context=context)
