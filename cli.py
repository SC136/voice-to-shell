"""
Voice to Shell: Interactive Terminal Assistant
Replicates the functional edge maintenance assistant (Section IV-C & Fig. 1)
Supports:
- Docker and Emergency Luminaire contexts
- Speech/Audio or Text instructions
- STT -> FIX -> TTC -> Safety Gate -> Execution
"""

import sys
import os
import argparse
from voice_to_shell.pipeline import VoiceToShellPipeline
from voice_to_shell.safety import RiskLevel


def banner():
    print("""
========================================================================
   VOICE TO SHELL: SLM-BASED ASSISTANT FOR IOT MAINTENANCE ON EDGE
             IEEE Internet of Things Journal (JIOT 2026)
========================================================================
    """)


def run_interactive():
    banner()

    print("Select IoT Domain Context:")
    print("  [1] Docker Infrastructure (Public Domain)")
    print("  [2] Emergency Luminaires System (Proprietary IoT Mesh)")
    choice = input("\nEnter choice [1 or 2, default: 2]: ").strip()
    context = "docker" if choice == "1" else "luminaires"

    print(f"\n[+] Active Context: {context.upper()}")
    print("[+] Loading Voice-to-Shell Pipeline...")

    pipeline = VoiceToShellPipeline(
        stt_model="openai/whisper-tiny",
        force_mock_shell=False
    )
    print("[+] Pipeline ready. Type 'exit' or 'quit' to terminate.\n")

    while True:
        try:
            raw_input_text = input(f"\n({context}) Enter instruction or path to audio file: ").strip()
            if not raw_input_text:
                continue
            if raw_input_text.lower() in ("exit", "quit", "q"):
                print("Exiting Voice to Shell assistant. Goodbye.")
                break

            # Switch context command
            if raw_input_text.lower() in ("docker", "switch docker"):
                context = "docker"
                print(f"[+] Switched context to {context.upper()}")
                continue
            elif raw_input_text.lower() in ("luminaires", "luminaire", "switch luminaires"):
                context = "luminaires"
                print(f"[+] Switched context to {context.upper()}")
                continue

            is_audio = os.path.isfile(raw_input_text) and raw_input_text.lower().endswith((".wav", ".mp3", ".ogg", ".flac"))

            print("\n---------------- Processing Pipeline ----------------")
            res = pipeline.process(
                input_data=raw_input_text,
                is_audio=is_audio,
                context=context,
                auto_execute=False
            )

            if is_audio:
                print(f"[*] [STT Raw]:     {res['raw_transcript']}")
            print(f"[*] [FIX Clean]:   {res['fixed_prompt']}")
            print(f"[*] [TTC Command]: {res['generated_command']}")

            safety = res["safety"]
            risk = safety["risk_level"]
            print(f"[*] [Safety]:      Level={risk} | {safety['explanation']}")
            if safety.get("warning"):
                print(f"    [!] WARNING:   {safety['warning']}")

            perf = res["performance"]
            print(f"[*] [Telemetry]:   Latency={perf['latency_seconds']*1000:.1f}ms | RAM={perf['ram_used_mb']:.1f}MB | CPU={perf['cpu_percent']}%")
            print("-----------------------------------------------------")

            # Human-in-the-loop confirmation gate (Section III-A)
            if safety["requires_confirmation"]:
                confirm = input(f"\n[?] Execute command `{res['generated_command']}`? [Y/n/edit]: ").strip().lower()
            else:
                confirm = input(f"\n[?] Execute read-only command `{res['generated_command']}`? [Y/n/edit]: ").strip().lower()

            if confirm in ("", "y", "yes"):
                print("\n[+] Executing command...")
                exec_res = pipeline.confirm_and_execute(res["generated_command"], context=context)
                print(exec_res)
            elif confirm.startswith("e"):
                edited_cmd = input("Enter corrected command: ").strip()
                if edited_cmd:
                    exec_res = pipeline.confirm_and_execute(edited_cmd, context=context)
                    print(exec_res)
            else:
                print("[-] Execution aborted by user.")

        except KeyboardInterrupt:
            print("\nInterrupted by user. Exiting.")
            break
        except Exception as e:
            print(f"[!] Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice to Shell CLI")
    parser.add_argument("--context", choices=["docker", "luminaires"], default=None)
    args = parser.parse_args()
    run_interactive()
