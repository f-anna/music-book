"""E2: MoritzLaurer/ModernBERT-large-zeroshot-v2.0 on Moby Dick passages, target only (C0).

Every atmosphere label is scored independently (multi-label NLI, as the zero-shot pipeline does
with multi_label=True): P(entailment) from the softmax over (entailment, not_entailment).
The single-label view (softmax of the entailment logits across labels) is saved too.

- passages: the passages of tone_probe.PASSAGES at every length of LENGTHS, template v1;
- template: the same at TEMPLATE_CHECK_LENGTH words with template v2 (wording sensitivity);
- windows: consecutive WINDOW-word windows through the chapters of tone_probe.WINDOW_RUNS.

Writes results/e2_passages.csv, results/e2_windows.csv and results/e2_run.json.

Usage: python zeroshot_probe.py <moby_dick.epub>   (with the ~/.venvs/music-book-eval interpreter)
"""
import csv
import json
import os
import platform
import sys
import time

import psutil
import torch
import transformers
from huggingface_hub import model_info
from transformers import AutoModelForSequenceClassification, AutoTokenizer

import book
from tone_probe import PASSAGES, WINDOW, WINDOW_RUNS

MODEL = "MoritzLaurer/ModernBERT-large-zeroshot-v2.0"
THREADS = 4
LENGTHS = [150, 300, 700]
TEMPLATE_CHECK_LENGTH = 300
# the atmosphere labels of the test plan
LABELS = ["ominous", "suspenseful", "mysterious", "melancholic", "warm and cozy",
          "peaceful", "hopeful", "oppressive", "whimsical", "wondrous"]
TEMPLATES = {
    "v1": "The atmosphere of this passage is {}.",
    "v2": "This passage creates a {} atmosphere.",
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def rss_mb():
    return psutil.Process().memory_info().rss / 2**20


class ZeroShot:
    def __init__(self):
        t0 = time.perf_counter()
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        # reference_compile: the config asks for torch.compile, which is not needed on CPU
        self.model = AutoModelForSequenceClassification.from_pretrained(
            MODEL, dtype=torch.float32, reference_compile=False).eval()
        self.load_s = time.perf_counter() - t0
        self.entail = self.model.config.label2id["entailment"]
        self.peak_rss = rss_mb()

    def __call__(self, text, template):
        """-> ({label: P(entailment)}, {label: single-label share}, premise tokens, ms)"""
        hyps = [template.format(label) for label in LABELS]
        enc = self.tok([text] * len(hyps), hyps, return_tensors="pt", padding=True)
        n = len(self.tok(text)["input_ids"])
        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(**enc).logits
        ms = (time.perf_counter() - t0) * 1000
        self.peak_rss = max(self.peak_rss, rss_mb())
        multi = torch.softmax(logits, dim=1)[:, self.entail].tolist()
        single = torch.softmax(logits[:, self.entail], dim=0).tolist()
        return dict(zip(LABELS, multi)), dict(zip(LABELS, single)), n, ms


def row(multi, single, **extra):
    ranked = sorted(multi, key=multi.get, reverse=True)
    return {**extra, "top3": "|".join(ranked[:3]),
            **{k: round(v, 4) for k, v in multi.items()},
            **{f"single:{k}": round(v, 4) for k, v in single.items()}}


def show(prefix, multi):
    ranked = sorted(multi, key=multi.get, reverse=True)
    print(prefix + "  " + " ".join(f"{k}={multi[k]:.3f}" for k in ranked[:4]), flush=True)


def write_csv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    torch.set_num_threads(THREADS)
    os.makedirs(OUT, exist_ok=True)
    paras = book.paragraphs(sys.argv[1])
    zs = ZeroShot()
    print(f"loaded in {zs.load_s:.1f}s, rss {rss_mb():.0f} MB", flush=True)

    runs = [("v1", n) for n in LENGTHS] + [("v2", TEMPLATE_CHECK_LENGTH)]
    rows = []
    for template, n in runs:
        for pid, (start, _) in PASSAGES.items():
            text = book.words_from(paras, start, n)
            multi, single, tokens, ms = zs(text, TEMPLATES[template])
            rows.append(row(multi, single, passage=pid, template=template, words=n,
                            tokens=tokens, ms=round(ms)))
            show(f"{template} {pid:17} {n:4}w {tokens:5}tok {ms / 1000:5.1f}s", multi)
        write_csv("e2_passages.csv", rows)  # after every run, so a crash keeps the rest

    wrows = []
    for start, count in WINDOW_RUNS.items():
        for j, text in enumerate(book.windows(paras, start, WINDOW, count)):
            multi, single, tokens, ms = zs(text, TEMPLATES["v1"])
            wrows.append(row(multi, single, run=start, window=j, start_word=j * WINDOW,
                             tokens=tokens, ms=round(ms), begins=" ".join(text.split()[:10])))
            show(f"win {j:2} @{j * WINDOW:5}w", multi)
    write_csv("e2_windows.csv", wrows)

    meta = {
        "model": MODEL,
        "revision": model_info(MODEL).sha,
        "labels": LABELS,
        "templates": TEMPLATES,
        "threads": THREADS,
        "load_s": round(zs.load_s, 1),
        "peak_rss_mb": round(zs.peak_rss),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cpu": platform.processor() or platform.machine(),
    }
    with open(os.path.join(OUT, "e2_run.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
