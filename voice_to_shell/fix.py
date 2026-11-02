"""
FIX Component: Domain Spell-Checker and Transcript Normalizer
Replicates Section III-C3 & Section IV-B of IEEE JIOT 2026 paper:
- Corrects STT transcription errors & non-native accent artifacts
- Eliminates STT hallucinations (e.g. repeated token sequences)
- Normalizes spelled-out spoken numbers (e.g., 'two hundred and ninety nine' -> '299')
- Fixes domain-specific IoT terminology (Docker & Emergency Luminaires)
- Supports fine-tuned T5-small inference when available
"""

import re
from typing import Optional


# Spoken number word mapping dictionary
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000
}

# Domain vocabulary corrections for IoT maintenance (Docker & Luminaires)
DOMAIN_REPLACEMENTS = [
    # Docker domain
    (r"\b(dricker|darker|docer|doker)\b", "docker"),
    (r"\b(contaner|containr|contayner)\b", "container"),
    (r"\b(volum|volumn)\b", "volume"),
    (r"\b(graf\s*ana|graphana)\b", "grafana"),
    (r"\b(engine\s*x|n\s*ginx|n-jinx)\b", "nginx"),
    (r"\b(protheus|promethius)\b", "prometheus"),
    (r"\b(ubun\s*tu|u\s*buntu)\b", "ubuntu"),

    # Emergency Luminaires domain
    (r"\b(luminer|luminary|illuminare|luminare|luminaire's|luminair)\b", "luminaire"),
    (r"\b(luminers|luminaries|illuminaires)\b", "luminaires"),
    (r"\b(cinq|sync)\s+node\b", "sink node"),
    (r"\b(cinq|sync)\b", "sink"),
    (r"\b(d\s*b\s*r|d-b-r)\b", "dbr"),
    (r"\b(b\s*l\s*e)\b", "ble"),
    (r"\b(z\s*w\s*p|zeta\s*wp)\b", "zwp"),
    (r"\b(pictogramm|picto\s*gram)\b", "pictogram"),
    (r"\b(autonomi|autonimy)\b", "autonomy"),
    (r"\b(provitioning|provisionning)\b", "provisioning"),
    (r"\b(diagnoctics|diagnostis)\b", "diagnostics"),
    (r"\b(brightnes|brighness)\b", "brightness"),
]


def words_to_number(phrase: str) -> Optional[int]:
    """Convert spoken number word sequence into an integer."""
    tokens = phrase.lower().replace("-", " ").split()
    total = 0
    current = 0
    valid = False

    for token in tokens:
        if token == "and":
            continue
        if token in NUMBER_WORDS:
            valid = True
            val = NUMBER_WORDS[token]
            if val == 100:
                current = (current if current else 1) * 100
            elif val == 1000:
                total += (current if current else 1) * 1000
                current = 0
            else:
                current += val
        else:
            return None

    if not valid:
        return None
    return total + current


def convert_spoken_numbers(text: str) -> str:
    """Find multi-word spoken number phrases and replace with digits."""
    # Pattern matching sequences of number words and 'and'
    num_tokens = set(NUMBER_WORDS.keys()) | {"and"}
    words = text.split()
    result = []
    i = 0

    while i < len(words):
        word_clean = words[i].strip(".,;:!?").lower()
        if word_clean in NUMBER_WORDS and word_clean != "and":
            # Start collecting number phrase
            j = i
            chunk = []
            while j < len(words):
                w = words[j].strip(".,;:!?").lower()
                if w in num_tokens:
                    chunk.append(w)
                    j += 1
                else:
                    break

            # Trailing 'and' shouldn't be part of number
            while chunk and chunk[-1] == "and":
                chunk.pop()
                j -= 1

            num_val = words_to_number(" ".join(chunk))
            if num_val is not None:
                # Retain punctuation from the last word if any
                punct = "".join([c for c in words[j - 1] if c in ".,;:!?"])
                result.append(f"{num_val}{punct}")
                i = j
                continue

        result.append(words[i])
        i += 1

    return " ".join(result)


def remove_hallucinations(text: str, max_repeat: int = 5) -> str:
    """
    Remove repeated tokens caused by STT hallucinations (Section III-C3).
    Paper notes hallucinations where words are repeated > 7 times.
    """
    words = text.split()
    if not words:
        return text

    cleaned = []
    prev_word = None
    repeat_count = 0

    for w in words:
        w_lower = w.lower()
        if w_lower == prev_word:
            repeat_count += 1
            if repeat_count <= max_repeat:
                cleaned.append(w)
        else:
            prev_word = w_lower
            repeat_count = 1
            cleaned.append(w)

    return " ".join(cleaned)


class TranscriptFixer:
    """
    Domain-specific transcript corrector (FIX Component).
    Combines rule-based normalizer with optional T5-small checkpoint.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.tokenizer = None
        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str):
        """Load fine-tuned T5-small FIX model if available."""
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
            self.model.eval()
        except Exception:
            self.model = None
            self.tokenizer = None

    def fix(self, transcript: str, context: Optional[str] = None) -> str:
        """
        Process raw STT transcript through FIX pipeline.
        Returns cleaned, domain-corrected prompt.
        """
        if not transcript or not transcript.strip():
            return ""

        # Step 1: Remove STT loop hallucinations
        text = remove_hallucinations(transcript.strip())

        # Step 2: Normalize casing & basic spacing
        text = " ".join(text.split())

        # Step 3: Domain spelling replacements
        for pattern, replacement in DOMAIN_REPLACEMENTS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Step 4: Spoken numbers to digits
        text = convert_spoken_numbers(text)

        # Step 5: If fine-tuned T5-small model loaded, apply seq2seq correction
        if self.model and self.tokenizer:
            try:
                prefix = f"fix {context}: " if context else "fix: "
                inputs = self.tokenizer(prefix + text, return_tensors="pt", max_length=128, truncation=True)
                outputs = self.model.generate(**inputs, max_length=128, num_beams=2, early_stopping=True)
                ml_fixed = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
                if ml_fixed:
                    return ml_fixed
            except Exception:
                pass

        return text
