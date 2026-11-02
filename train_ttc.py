"""
Fine-tuning Script for T5 Small Text-to-Command (TTC) Component
Replicates Section III-D & Table III of IEEE JIOT 2026 paper:
- Architecture: T5 Small (60.5M parameters)
- Tokenization with padding to 128 tokens
- Contexts: Docker & Emergency Luminaires
- Optuna-optimized hyperparameters from Table III
"""

import os
import json
import argparse
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    get_linear_schedule_with_warmup
)
from torch.optim import AdamW


class CommandDataset(Dataset):
    """Loads prompt -> command pairs from JSON split."""

    def __init__(self, json_path: str, tokenizer, context: str, max_length: int = 128):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.context = context
        with open(json_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        prompt = f"translate to {self.context} command: {item['prompt']}"
        command = item["command"]

        inputs = self.tokenizer(
            prompt,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        targets = self.tokenizer(
            command,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )

        labels = targets["input_ids"].squeeze(0)
        # Replace padding token id's of the label with -100 so they are ignored by loss
        labels[labels == self.tokenizer.pad_token_id] = -100

        return {
            "input_ids": inputs["input_ids"].squeeze(0),
            "attention_mask": inputs["attention_mask"].squeeze(0),
            "labels": labels,
            "raw_prompt": item["prompt"],
            "raw_command": command
        }


def train_model(
    context: str = "docker",
    epochs: int = 5,
    batch_size: int = 8,
    grad_accum_steps: int = 2,
    lr: float = 3.163e-4,
    warmup_steps: int = 100,
    output_dir: str = "models/ttc_t5",
    limit_samples: int = None
):
    print(f"\n=======================================================")
    print(f"Fine-tuning T5 Small for {context.upper()} Command Generation")
    print(f"Hyperparameters: epochs={epochs}, batch={batch_size}, grad_accum={grad_accum_steps}, lr={lr}")
    print(f"=======================================================\n")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cpu":
        torch.set_num_threads(min(8, os.cpu_count() or 4))
    print(f"Using device: {device} (threads: {torch.get_num_threads()})")

    base_dir = f"data/{context}/en"
    train_path = os.path.join(base_dir, "train.json")
    val_path = os.path.join(base_dir, "val.json")

    tokenizer = AutoTokenizer.from_pretrained("t5-small")
    model = AutoModelForSeq2SeqLM.from_pretrained("t5-small").to(device)

    train_ds = CommandDataset(train_path, tokenizer, context=context)
    val_ds = CommandDataset(val_path, tokenizer, context=context)

    if limit_samples:
        train_ds.data = train_ds.data[:limit_samples]
        val_ds.data = val_ds.data[:max(10, limit_samples // 4)]
        print(f"Sample limit applied: {len(train_ds)} train, {len(val_ds)} val")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    total_steps = (len(train_loader) // grad_accum_steps) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=max(total_steps, 1)
    )

    model.train()
    for epoch in range(1, epochs + 1):
        running_loss = 0.0
        optimizer.zero_grad()

        for step, batch in enumerate(train_loader):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels
            )
            loss = outputs.loss / grad_accum_steps
            loss.backward()
            running_loss += loss.item() * grad_accum_steps

            if (step + 1) % grad_accum_steps == 0 or (step + 1) == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()

        avg_train_loss = running_loss / max(len(train_loader), 1)

        # Validation pass
        model.eval()
        val_loss = 0.0
        exact_matches = 0
        total_eval_samples = 0

        with torch.no_grad():
            for v_idx, batch in enumerate(val_loader):
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["labels"].to(device)

                outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
                val_loss += outputs.loss.item()

                # Generate on first few batches to evaluate EQ quickly without bottlenecking
                if v_idx < 4:
                    generated_ids = model.generate(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        max_new_tokens=32
                    )
                    preds = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
                    for pred, target in zip(preds, batch["raw_command"]):
                        if pred.strip() == target.strip():
                            exact_matches += 1
                        total_eval_samples += 1

        avg_val_loss = val_loss / max(len(val_loader), 1)
        val_accuracy = (exact_matches / max(total_eval_samples, 1)) * 100.0

        print(f"Epoch {epoch}/{epochs} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} | Val Sample EQ: {val_accuracy:.2f}% ({exact_matches}/{total_eval_samples})")
        model.train()

    # Save fine-tuned checkpoint
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    print(f"\nModel and tokenizer successfully saved to: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune T5 Small for Voice to Shell TTC")
    parser.add_argument("--context", choices=["docker", "luminaires"], default="docker", help="Domain context")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size")
    parser.add_argument("--grad_accum", type=int, default=2, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=3.163e-4, help="Learning rate")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of train samples for quick testing")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory")

    args = parser.parse_args()
    out = args.output_dir or f"models/ttc_{args.context}_t5"

    train_model(
        context=args.context,
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum_steps=args.grad_accum,
        lr=args.lr,
        output_dir=out,
        limit_samples=args.limit
    )
