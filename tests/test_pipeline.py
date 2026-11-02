"""
Unit Tests and Self-Checks for Voice to Shell Assistant
Verifies all components of the IEEE JIOT 2026 paper implementation.
"""

import unittest
from voice_to_shell.metrics import (
    exact_match,
    levenshtein_char,
    levenshtein_word,
    word_error_rate,
    semantic_textual_similarity
)
from voice_to_shell.fix import TranscriptFixer, convert_spoken_numbers, remove_hallucinations
from voice_to_shell.ttc import TextToCommand
from voice_to_shell.safety import CommandSafetyAnalyzer, RiskLevel
from voice_to_shell.shell_executor import ShellExecutor
from voice_to_shell.pipeline import VoiceToShellPipeline


class TestVoiceToShell(unittest.TestCase):

    def setUp(self):
        self.fixer = TranscriptFixer()
        self.ttc = TextToCommand()
        self.executor = ShellExecutor(force_mock=True)
        self.pipeline = VoiceToShellPipeline(force_mock_shell=True)

    def test_metrics(self):
        # Exact match
        self.assertEqual(exact_match("docker ps", "docker ps"), 100.0)
        self.assertEqual(exact_match("docker ps", "docker ps -a"), 0.0)

        # Levenshtein character
        self.assertAlmostEqual(levenshtein_char("docker", "docker"), 100.0)
        self.assertTrue(levenshtein_char("docker", "doker") > 80.0)

        # WER
        self.assertAlmostEqual(word_error_rate("info 299", "info 299"), 0.0)
        self.assertTrue(word_error_rate("info 299", "information 299") > 0.0)

        # STS
        self.assertEqual(semantic_textual_similarity("docker kill", "docker kill"), 100.0)

    def test_fix_component(self):
        # Spoken numbers
        self.assertIn("299", convert_spoken_numbers("luminaire two hundred and ninety nine"))
        self.assertIn("67", convert_spoken_numbers("luminaire sixty seven to eighty percent"))

        # Domain typos
        res = self.fixer.fix("check graf ana container")
        self.assertIn("grafana", res)

        res2 = self.fixer.fix("retrieve info for luminer two hundred and ninety nine")
        self.assertIn("luminaire 299", res2)

        # Hallucinations
        hallucinated = "docker docker docker docker docker docker docker docker ps"
        cleaned = remove_hallucinations(hallucinated, max_repeat=3)
        self.assertEqual(cleaned, "docker docker docker ps")

    def test_ttc_docker(self):
        cmd1 = self.ttc.generate("End the container named grafana immediately with a kill signal.", context="docker")
        self.assertEqual(cmd1, "docker kill -s SIGKILL grafana")

        cmd2 = self.ttc.generate("Show how much disk space the ubuntu container is using", context="docker")
        self.assertEqual(cmd2, "docker inspect -s ubuntu")

        cmd3 = self.ttc.generate("List all active running containers", context="docker")
        self.assertEqual(cmd3, "docker ps")

    def test_ttc_luminaires(self):
        cmd1 = self.ttc.generate("Retrieve diagnostics and settings for luminaire 299", context="luminaires")
        self.assertEqual(cmd1, "info 299")

        cmd2 = self.ttc.generate("Increase the display brightness of luminaire 67 to 80 percent", context="luminaires")
        self.assertEqual(cmd2, "set_brightness 67 80")

        cmd3 = self.ttc.generate("Enable augmented security for luminaire 605", context="luminaires")
        self.assertEqual(cmd3, "augmented_on 605")

        cmd4 = self.ttc.generate("Show me a connectivity map of the lighting system", context="luminaires")
        self.assertEqual(cmd4, "get_mesh")

    def test_safety_gate(self):
        safe_eval = CommandSafetyAnalyzer.evaluate("info 299")
        self.assertEqual(safe_eval["risk_level"], RiskLevel.SAFE)
        self.assertFalse(safe_eval["requires_confirmation"])

        med_eval = CommandSafetyAnalyzer.evaluate("set_brightness 67 80")
        self.assertEqual(med_eval["risk_level"], RiskLevel.MEDIUM)
        self.assertTrue(med_eval["requires_confirmation"])

        crit_eval = CommandSafetyAnalyzer.evaluate("docker kill -s SIGKILL grafana")
        self.assertEqual(crit_eval["risk_level"], RiskLevel.CRITICAL)
        self.assertTrue(crit_eval["requires_confirmation"])

    def test_shell_executor(self):
        # Luminaire mesh simulation
        res_info = self.executor.execute("info 299", context="luminaires")
        self.assertEqual(res_info.returncode, 0)
        self.assertIn("LUMINAIRE ID: 299", res_info.stdout)

        res_bright = self.executor.execute("set_brightness 67 80", context="luminaires")
        self.assertEqual(res_bright.returncode, 0)
        self.assertIn("Brightness set to 80%", res_bright.stdout)

        res_mesh = self.executor.execute("get_mesh", context="luminaires")
        self.assertEqual(res_mesh.returncode, 0)
        self.assertIn("MESH CONNECTIVITY GRAPH", res_mesh.stdout)

        # Docker simulation
        res_docker = self.executor.execute("docker ps", context="docker")
        self.assertEqual(res_docker.returncode, 0)
        self.assertIn("CONTAINER ID", res_docker.stdout)

    def test_full_pipeline(self):
        output = self.pipeline.process(
            input_data="Retrieve diagnostics and settings for luminer two hundred and ninety nine.",
            is_audio=False,
            context="luminaires",
            auto_execute=True
        )

        self.assertEqual(output["generated_command"], "info 299")
        self.assertIsNotNone(output["execution"])
        self.assertTrue(output["execution"]["success"])
        self.assertIn("LUMINAIRE ID: 299", output["execution"]["stdout"])


if __name__ == "__main__":
    unittest.main()
