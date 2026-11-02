"""
Voice to Shell: Web Interface
Interactive edge dashboard replicating the paper's end-to-end voice assistant.
Features:
- Microphone & Audio file upload + keyboard input
- STT (Whisper Tiny) with English & Spanish translation
- FIX Stage (Domain normalization & spell checking)
- TTC Stage (SLM command generation)
- Safety Confirmation Gate with Risk Level classification
- Live Terminal Execution (Docker & Luminaire Mesh Simulator)
"""

import os
import gradio as gr
from voice_to_shell.pipeline import VoiceToShellPipeline
from voice_to_shell.safety import RiskLevel

# Initialize pipeline
pipeline = VoiceToShellPipeline(stt_model="openai/whisper-tiny")


def process_input(audio_file, text_input, context, language):
    """Run voice-to-shell pipeline on provided audio or text input."""
    is_audio = audio_file is not None
    data_input = audio_file if is_audio else (text_input or "").strip()

    if not data_input:
        return (
            "No input provided.",
            "",
            "",
            "SAFE",
            "Please provide a voice recording or type an instruction.",
            "",
            ""
        )

    res = pipeline.process(
        input_data=data_input,
        is_audio=is_audio,
        context=context.lower(),
        language="es" if "Spanish" in language else "en",
        auto_execute=False
    )

    stt_text = res["raw_transcript"]
    fix_text = res["fixed_prompt"]
    command = res["generated_command"]
    safety = res["safety"]
    risk = safety["risk_level"]
    explanation = f"{safety['explanation']}"
    if safety.get("warning"):
        explanation += f"\n\n[WARNING] {safety['warning']}"

    perf = res["performance"]
    telemetry = (
        f"Latency: {perf['latency_seconds']*1000:.1f} ms | "
        f"RAM: {perf['ram_used_mb']:.1f} MB (Delta: {perf['ram_delta_mb']:+.1f} MB) | "
        f"CPU: {perf['cpu_percent']}%"
    )

    terminal_ready = f"Command ready: `{command}`\nRisk level: {risk}\nClick 'Confirm & Execute' below to run."

    return (
        stt_text,
        fix_text,
        command,
        risk,
        explanation,
        telemetry,
        terminal_ready
    )


def execute_command(command, context):
    """Execute confirmed command in the shell environment."""
    if not command or not command.strip():
        return "No command to execute."

    exec_res = pipeline.confirm_and_execute(command.strip(), context=context.lower())
    output = f"$ {exec_res.command}\n"
    if exec_res.stdout:
        output += exec_res.stdout
    if exec_res.stderr:
        output += f"\n[STDERR]\n{exec_res.stderr}"

    status = "SUCCESS" if exec_res.returncode == 0 else "FAILED"
    sim_label = "(Simulated Edge Environment)" if exec_res.simulated else "(Host Execution)"
    return f"[{status}] {sim_label}\n{output}"


# Build Gradio UI
with gr.Blocks(title="Voice to Shell: IoT Maintenance Assistant", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🎙️ Voice to Shell: A SLM-Based Assistant for IoT Maintenance on the Edge
    ### *Implementation of IEEE Internet of Things Journal (JIOT 2026)*
    **Privacy-preserving, edge-deployable multilingual voice assistant converting speech to verified terminal commands.**
    """)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 1. Input & Context Configuration")
            context_selector = gr.Radio(
                choices=["Luminaires", "Docker"],
                value="Luminaires",
                label="Target IoT Domain Context"
            )
            lang_selector = gr.Radio(
                choices=["English (en)", "Spanish (es)"],
                value="English (en)",
                label="Spoken / Text Language"
            )

            with gr.Tabs():
                with gr.TabItem("🎤 Voice Input"):
                    audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak or Upload Audio")
                with gr.TabItem("⌨️ Text Input"):
                    text_input = gr.Textbox(
                        lines=2,
                        placeholder="e.g. 'Retrieve diagnostics and settings for luminaire 299' or 'End the container named grafana immediately with a kill signal'",
                        label="Natural Language Instruction"
                    )

            process_btn = gr.Button("🚀 Process Pipeline (Audio → Text → Command)", variant="primary")

            gr.Markdown("#### Preset Demonstrations (from IEEE Paper):")
            preset_lum_1 = gr.Button("💡 'info 299' (Retrieve diagnostics for luminaire 299)")
            preset_lum_2 = gr.Button("⚡ 'set_brightness 67 80' (Increase display brightness 67 to 80%)")
            preset_lum_3 = gr.Button("🛡️ 'augmented_on 605' (Enable augmented security for luminaire 605)")
            preset_dock_1 = gr.Button("🐳 'docker kill -s SIGKILL grafana' (Kill container grafana)")
            preset_dock_2 = gr.Button("📦 'docker inspect -s ubuntu' (Show disk space of container ubuntu)")

        with gr.Column(scale=1):
            gr.Markdown("### 2. Pipeline Stages & Verification")
            stt_out = gr.Textbox(label="Stage 1: Speech-to-Text (STT) Raw Transcript", interactive=False)
            fix_out = gr.Textbox(label="Stage 2: Spell Checker (FIX) Normalized Text", interactive=False)
            cmd_out = gr.Textbox(label="Stage 3: Text-to-Command (TTC) Predicted Shell Command", interactive=False)

            with gr.Row():
                risk_badge = gr.Textbox(label="Safety Level", scale=1, interactive=False)
                perf_out = gr.Textbox(label="Edge Telemetry", scale=2, interactive=False)

            safety_explanation = gr.Textbox(label="Safety & Impact Analysis", lines=2, interactive=False)

            gr.Markdown("### 3. Human-in-the-Loop Confirmation & Execution")
            terminal_view = gr.Textbox(label="Shell Terminal Output", lines=8, interactive=False)
            confirm_btn = gr.Button("✅ Confirm & Execute on Edge Device", variant="stop")

    # Connect events
    process_btn.click(
        fn=process_input,
        inputs=[audio_input, text_input, context_selector, lang_selector],
        outputs=[stt_out, fix_out, cmd_out, risk_badge, safety_explanation, perf_out, terminal_view]
    )

    confirm_btn.click(
        fn=execute_command,
        inputs=[cmd_out, context_selector],
        outputs=[terminal_view]
    )

    # Preset handlers
    def set_p1():
        return None, "Retrieve diagnostics and settings for luminaire two hundred and ninety nine.", "Luminaires"
    preset_lum_1.click(set_p1, outputs=[audio_input, text_input, context_selector])

    def set_p2():
        return None, "Increase the display brightnes of luminaire sixty seven to eighty percent.", "Luminaires"
    preset_lum_2.click(set_p2, outputs=[audio_input, text_input, context_selector])

    def set_p3():
        return None, "Enable augmented security for luminaire six hundred and five.", "Luminaires"
    preset_lum_3.click(set_p3, outputs=[audio_input, text_input, context_selector])

    def set_p4():
        return None, "End the container named graf ana immediately with a kill signal.", "Docker"
    preset_dock_1.click(set_p4, outputs=[audio_input, text_input, context_selector])

    def set_p5():
        return None, "Show how much disk space the u buntu container is using.", "Docker"
    preset_dock_2.click(set_p5, outputs=[audio_input, text_input, context_selector])


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
