# Voice to Shell: A SLM-Based Assistant for IoT Maintenance Tasks on the Edge

An end-to-end, edge-deployable, privacy-preserving multilingual voice assistant implementing the research published in **IEEE Internet of Things Journal (JIOT 2026)**:
> **"From Voice to Shell: A SLM-Based Assistant for IoT Maintenance Tasks on the Edge"**  
> *Ángela Gijón Flores, Cristina Bolaños Peño, Henry Llumiguano Solano, Jesús Fernández-Bermejo Ruiz, Félix Jesús Villanueva Molina, and Fernando Rincón Calle*  
> IEEE Xplore: [10.1109/JIOT.2025.3632638](https://ieeexplore.ieee.org/document/11244914) | Zenodo Datasets: [10.5281/zenodo.17288923](https://doi.org/10.5281/zenodo.17288923)

---

## 🎯 Architecture Overview (Fig. 1)

Traditional cloud LLM assistants present serious privacy risks (sending biometric voice data off-premise, violating GDPR), high latency, cloud dependency, and lack awareness of private, proprietary IoT systems.

**Voice to Shell** runs completely on resource-constrained edge devices (CPU-only laptops, Raspberry Pi, industrial edge gateways):

```
                        ┌──────────────────────────────────────────────┐
                        │             Command Context                  │
                        │        [Docker, Luminaires Mesh]             │
                        │                                              │
                        │   ┌──────────────────────────────────────┐   │
                        │   │        Spell Checker (FIX)           │   │
                        │   │  (Domain phonetic & number normalizer│   │
                        │   └──────────────────┬───────────────────┘   │
                        │                      │                       │
                        │   ┌──────────────────▼───────────────────┐   │
                        │   │       Text to Command (TTC)          │   │
                        │   │        (Fine-tuned T5 SLM)           │   │
                        │   └──────────────────┬───────────────────┘   │
                        └──────────────────────┼───────────────────────┘
                                               │
   [Speak] ──> Microphone ──> [ STT ] ─────────┤
                                Whisper        │
                                               ▼
   [Write] ──> Keyboard ────────────────> Generated Command
                                               │
                                               ▼
                                    ┌───────────────────────┐
                                    │ Confirm Action Gate?  │
                                    │   (Safety Analyzer)   │
                                    └──────────┬────────────┘
                                               │
                                     [Yes] ────┴────> [ Shell Execution ]
                                                       • Docker Daemon
                                                       • Luminaire Mesh
```

### Pipeline Components:
1. **STT (Speech-to-Text)**: Local on-device Whisper (`openai/whisper-tiny` or `whisper-base`). Supports English transcription as well as direct Spanish-to-English translation.
2. **FIX (Domain Spell-Checker & Normalizer)**: Corrects phonetic STT misrecognitions (e.g. `"dricker"` -> `"docker"`, `"luminer"` -> `"luminaire"`), normalizes spoken worded numbers (e.g. `"two hundred and ninety nine"` -> `"299"`), and removes loop hallucinations. (Improves command exact match by up to +30% as documented in Table VII).
3. **TTC (Text-to-Command)**: Fine-tuned Small Language Model (T5-Small with 60.5M parameters) mapping natural language instructions into exact shell commands across:
   - **Docker Infrastructure**: Public container commands (133 commands, 3,192 verified samples).
   - **Emergency Luminaires**: Proprietary IoT lighting mesh system (53 commands, 1,272 verified samples).
4. **Safety & Human-in-the-Loop Gate**: Classifies command risk (`SAFE`, `MEDIUM`, `CRITICAL`), displays transparent explanations, and enforces human confirmation before executing destructive operations (`docker rm`, `purge_luminaires`, `reset_mesh`, `docker kill`).
5. **Shell Execution Engine**: Dual-backend executing on live host tools (Docker) or complete simulation of the proprietary Emergency Luminaire Mesh Controller.

---

## 📁 Repository Structure

```
├── data/
│   ├── docker/                     # Text to Docker dataset (en/es splits)
│   │   ├── en/ [train.json, val.json, test.json]
│   │   └── es/ [test.json]
│   └── luminaires/                 # Text to Luminaires dataset (en/es splits)
│       ├── en/ [train.json, val.json, test.json]
│       └── es/ [test.json]
├── voice_to_shell/
│   ├── __init__.py
│   ├── stt.py                      # Whisper ASR transcription & translation
│   ├── fix.py                      # Domain spell checker & spoken number normalizer
│   ├── ttc.py                      # T5 SLM command generator & pattern fallback
│   ├── safety.py                   # Risk level assessment & confirmation gate
│   ├── shell_executor.py           # Docker & 53-command Luminaire mesh simulator
│   ├── pipeline.py                 # Full end-to-end Voice-to-Shell pipeline
│   └── metrics.py                  # Evaluation metrics (EQ, LEV, WER, STS, latency)
├── train_ttc.py                    # Fine-tuning script for T5 Small on IoT datasets
├── evaluate_benchmark.py           # Benchmark script reproducing Table V and Table VII
├── cli.py                          # Interactive terminal assistant
├── app.py                          # Modern Web UI (Gradio)
├── tests/
│   └── test_pipeline.py            # Comprehensive unit tests & self-checks
└── README.md
```

---

## 🚀 Quick Start

### 1. Interactive Terminal Assistant (CLI)

```bash
python cli.py
```
- Select context (`1` for Docker, `2` for Emergency Luminaires).
- Enter speech audio file path (e.g. `.wav`) or type instruction directly.
- Inspect the output at every stage (STT -> FIX -> TTC -> Safety Check).
- Confirm action to execute!

### 2. Web Interface (Gradio Dashboard)

```bash
python app.py
```
- Open `http://127.0.0.1:7860` in your browser.
- Speak directly into the microphone or test using built-in presets from the IEEE paper.
- View live edge telemetry (latency in ms, CPU %, RAM used).

---

## 📊 Benchmark & Evaluation (Replicating Paper Tables)

Run the standardized benchmark:

```bash
python evaluate_benchmark.py
```

### Table V: Command Generation Evaluation
| Context / Domain | Samples | EQ (%) | LEV Char (%) | Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Docker (Public)** | 266 | 76.69% (T5-Small) | 95.72% | ~0.20 s/cmd (CPU) |
| **Emergency Luminaires** | 106 | 89.62% (T5-Small) | 98.22% | ~0.20 s/cmd (CPU) |

### Table VII: Impact of FIX Component on Noisy Transcripts
| Sample Noisy STT Input | Clean Fixed Transcript (FIX Stage) | Target Shell Command |
| :--- | :--- | :--- |
| `"Retrieve diagnostics and settings for luminer two hundred and ninety nine."` | `"Retrieve diagnostics and settings for luminaire 299."` | `info 299` |
| `"Increase the display brightnes of luminaire sixty seven to eighty percent."` | `"Increase the display brightness of luminaire 67 to 80 percent."` | `set_brightness 67 80` |
| `"End the container named graf ana immediately with a kill signal."` | `"End the container named grafana immediately with a kill signal."` | `docker kill -s SIGKILL grafana` |
| `"Switch augmented security off on luminaire nine hundred and sixty eight."` | `"Switch augmented security off on luminaire 968."` | `augmented_off 968` |

---

## 🧠 Training Your Own Model (Fine-tuning T5 Small)

To fine-tune T5 Small on the Emergency Luminaires or Docker dataset using the paper's Optuna hyperparameters (Table III):

```bash
# Fine-tune on Emergency Luminaires
python train_ttc.py --context luminaires --epochs 5 --batch_size 8 --grad_accum 2 --lr 4.143e-4

# Fine-tune on Docker
python train_ttc.py --context docker --epochs 5 --batch_size 8 --grad_accum 2 --lr 3.163e-4
```

Checkpoints will be saved to `models/ttc_luminaires_t5` and `models/ttc_docker_t5`.

---

## 🧪 Running Unit Tests

```bash
python -m unittest tests/test_pipeline.py
```
Verifies exact match, Levenshtein, WER, STS, FIX number normalizer, typo corrections, safety classifier, Docker and Luminaire mesh execution engines.
