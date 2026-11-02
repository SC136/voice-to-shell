"""
Benchmark Evaluation Suite for Voice-to-Shell
Replicates Table V and Table VII from IEEE JIOT 2026 paper:
- Strict Exact Match (EQ %)
- Levenshtein character & word similarity (LEV %)
- Average latency per sample (seconds)
- Compares Docker (public) and Emergency Luminaires (proprietary)
- Demonstrates the impact of the FIX (spell-checker) component
"""

import os
import json
import time
import argparse
from typing import Dict, Any, List

from voice_to_shell.metrics import (
    exact_match,
    levenshtein_char,
    levenshtein_word,
    semantic_textual_similarity,
    ResourceMonitor
)
from voice_to_shell.ttc import TextToCommand
from voice_to_shell.fix import TranscriptFixer


def evaluate_dataset(
    json_path: str,
    context: str,
    ttc_engine: TextToCommand,
    apply_fix: bool = False,
    fixer: TranscriptFixer = None,
    sample_limit: int = None
) -> Dict[str, float]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if sample_limit:
        data = data[:sample_limit]

    total_eq = 0.0
    total_lev_char = 0.0
    total_lev_word = 0.0
    total_sts = 0.0
    latencies = []

    for item in data:
        prompt = item["prompt"]
        target = item["command"]

        if apply_fix and fixer:
            prompt = fixer.fix(prompt, context=context)

        t0 = time.perf_counter()
        pred = ttc_engine.generate(prompt, context=context)
        t1 = time.perf_counter()
        latencies.append(t1 - t0)

        total_eq += exact_match(pred, target)
        total_lev_char += levenshtein_char(pred, target)
        total_lev_word += levenshtein_word(pred, target)
        total_sts += semantic_textual_similarity(pred, target)

    n = max(len(data), 1)
    return {
        "count": len(data),
        "eq_percent": round(total_eq / n, 2),
        "lev_char_percent": round(total_lev_char / n, 2),
        "lev_word_percent": round(total_lev_word / n, 2),
        "sts_percent": round(total_sts / n, 2),
        "avg_latency_ms": round((sum(latencies) / n) * 1000, 3)
    }


def run_benchmark(sample_limit: int = None):
    print("=" * 80)
    print("           VOICE TO SHELL: SYSTEM BENCHMARK & EVALUATION           ")
    print("               IEEE JIOT 2026 Paper Reproduction                   ")
    print("=" * 80)

    ttc = TextToCommand()
    fixer = TranscriptFixer()

    docker_test = "data/docker/en/test.json"
    lum_test = "data/luminaires/en/test.json"

    # Evaluate Docker
    print("\nEvaluating Docker Test Split (data/docker/en/test.json)...")
    res_docker = evaluate_dataset(docker_test, "docker", ttc, apply_fix=True, fixer=fixer, sample_limit=sample_limit)

    # Evaluate Luminaires
    print("Evaluating Emergency Luminaires Test Split (data/luminaires/en/test.json)...")
    res_lum = evaluate_dataset(lum_test, "luminaires", ttc, apply_fix=True, fixer=fixer, sample_limit=sample_limit)

    # Print Table V format
    print("\n" + "=" * 80)
    print("TABLE V REPRODUCTION: COMMAND GENERATION EVALUATION")
    print("=" * 80)
    print(f"{'Context / Domain':<25} | {'Samples':<8} | {'EQ (%)':<10} | {'LEV Char (%)':<14} | {'Latency':<12}")
    print("-" * 80)
    print(f"{'Docker (Public)':<25} | {res_docker['count']:<8} | {res_docker['eq_percent']:<10.2f} | {res_docker['lev_char_percent']:<14.2f} | {res_docker['avg_latency_ms']} ms/cmd")
    print(f"{'Luminaires (Proprietary)':<25} | {res_lum['count']:<8} | {res_lum['eq_percent']:<10.2f} | {res_lum['lev_char_percent']:<14.2f} | {res_lum['avg_latency_ms']} ms/cmd")
    print("=" * 80)

    # Demonstrate FIX component effect on simulated noisy STT transcripts (Table VII reproduction)
    print("\n" + "=" * 80)
    print("TABLE VII REPRODUCTION: STT NOISE & FIX STAGE RECOVERY")
    print("=" * 80)

    noisy_samples = [
        ("End the container named graf ana immediately with a kill signal.", "docker kill -s SIGKILL grafana", "docker"),
        ("show how much space the u buntu container is using?", "docker inspect -s ubuntu", "docker"),
        ("Retrieve diagnostics and settings for luminer two hundred and ninety nine.", "info 299", "luminaires"),
        ("Increase the display brightnes of luminaire sixty seven to eighty percent.", "set_brightness 67 80", "luminaires"),
        ("Switch augmented security off on luminaire nine hundred and sixty eight.", "augmented_off 968", "luminaires"),
        ("Clear the routing map cache on sync node.", "reset_mesh", "luminaires"),
    ]

    print(f"{'Noisy STT Transcript':<45} -> {'Clean Fixed Transcript'}")
    print("-" * 80)
    for noisy, ground_cmd, ctx in noisy_samples:
        clean = fixer.fix(noisy, context=ctx)
        pred_cmd = ttc.generate(clean, context=ctx)
        match = "MATCH" if pred_cmd == ground_cmd else "DIFF"
        print(f"[{match}] \"{noisy}\"")
        print(f"       Fixed: \"{clean}\"")
        print(f"       Command: `{pred_cmd}` (Target: `{ground_cmd}`)\n")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit number of test samples")
    args = parser.parse_args()
    run_benchmark(sample_limit=args.limit)
