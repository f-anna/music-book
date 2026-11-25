"""E1: Mitchins/literary-tone-classifier-v0.1 on Moby Dick passages.

- passages: every passage of PASSAGES at every length of LENGTHS (words from the same start);
- windows: consecutive WINDOW-word windows through two chapters (does the tone follow the text?);
- padding: the model card pads to 2048 tokens; checks that dropping it changes nothing.

Writes results/e1_passages.csv, results/e1_windows.csv and results/e1_run.json.

Usage: python tone_probe.py <moby_dick.epub>   (with the ~/.venvs/music-book-eval interpreter)
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

MODEL = "Mitchins/literary-tone-classifier-v0.1"
MAX_TOKENS = 2048  # the training max_length (results.json of the model)
THREADS = 4
LENGTHS = [150, 300, 700, 1500]
WINDOW = 300
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

# id -> (starting phrase, note on the content)
PASSAGES = {
    "loomings": ("CHAPTER 1. Loomings.", "Ch. 1 opening: wry, ironic narration"),
    "spouter_painting": ("CHAPTER 3. The Spouter-Inn.", "Ch. 3 opening: the dark, chaotic painting, weapons"),
    "spouter_landlord": ("Upon entering the place I found a number of young seamen",
                         "Ch. 3: the landlord's jokes about sharing a bed with a harpooneer"),
    "sermon": ("CHAPTER 9. The Sermon.", "Ch. 9: Father Mapple's sermon on Jonah"),
    "bosom_friend": ("CHAPTER 10. A Bosom Friend.", "Ch. 10: friendship with Queequeg"),
    "cetology": ("CHAPTER 32. Cetology.", "Ch. 32: mock-scholarly whale classification"),
    "sunset": ("CHAPTER 37. Sunset.", "Ch. 37: Ahab's monologue, monomania"),
    "whiteness": ("CHAPTER 42. The Whiteness of the Whale.", "Ch. 42: the horror of whiteness, essayistic"),
    "stubb_kills": ("Pull up!—close to!", "Ch. 61: Stubb lances the whale, blood"),
    "stubb_supper": ("“Cook,” said Stubb", "Ch. 64: Stubb torments the cook, comic"),
    "castaway": ("CHAPTER 93. The Castaway.", "Ch. 93: Pip abandoned in the sea"),
    "squeeze": ("CHAPTER 94. A Squeeze of the Hand.", "Ch. 94: blissful squeezing of sperm"),
    "coffin": ("CHAPTER 110. Queequeg in His Coffin.", "Ch. 110: Queequeg's illness, the coffin"),
    "candles": ("CHAPTER 119. The Candles.", "Ch. 119: typhoon, corposants"),
    "symphony": ("CHAPTER 132. The Symphony.", "Ch. 132: Ahab and Starbuck, tender, melancholic"),
    "catastrophe": ("Almost simultaneously, with a mighty volition",
                    "Ch. 135: the whale wrecks the boats and the Pequod"),
}
# starting phrase -> number of windows
WINDOW_RUNS = {
    "CHAPTER 3. The Spouter-Inn.": 16,   # painting (dark) -> landlord, bed jokes (humorous)
    "CHAPTER 132. The Symphony.": 8,     # whole chapter: tender -> melancholic -> Fedallah
}


def rss_mb():
    return psutil.Process().memory_info().rss / 2**20


class Classifier:
    def __init__(self):
        t0 = time.perf_counter()
        self.tok = AutoTokenizer.from_pretrained(MODEL)
        self.model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
        self.load_s = time.perf_counter() - t0
        self.labels = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]
        self.peak_rss = rss_mb()

    def __call__(self, text, pad=False):
        n = len(self.tok(text)["input_ids"])
        enc = self.tok(text, max_length=MAX_TOKENS, truncation=True,
                       padding="max_length" if pad else False, return_tensors="pt")
        t0 = time.perf_counter()
        with torch.no_grad():
            probs = torch.softmax(self.model(**enc).logits, dim=1)[0].tolist()
        ms = (time.perf_counter() - t0) * 1000
        self.peak_rss = max(self.peak_rss, rss_mb())
        return dict(zip(self.labels, probs)), n, ms


def row(scores, **extra):
    top = max(scores, key=scores.get)
    return {**extra, "top": top, "top_p": round(scores[top], 3),
            **{k: round(v, 4) for k, v in scores.items()}}


def write_csv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    torch.set_num_threads(THREADS)
    os.makedirs(OUT, exist_ok=True)
    paras = book.paragraphs(sys.argv[1])
    clf = Classifier()
    print(f"loaded in {clf.load_s:.1f}s, rss {rss_mb():.0f} MB, labels {clf.labels}", flush=True)

    rows = []
    for pid, (start, note) in PASSAGES.items():
        for n in LENGTHS:
            text = book.words_from(paras, start, n)
            scores, tokens, ms = clf(text)
            rows.append(row(scores, passage=pid, words=len(text.split()), tokens=tokens,
                            truncated=tokens > MAX_TOKENS, ms=round(ms)))
            print(f"{pid:17} {n:5}w {tokens:5}tok {ms:6.0f}ms  {rows[-1]['top']:12} "
                  + " ".join(f"{k[:4]}={v:.2f}" for k, v in scores.items()), flush=True)
    write_csv("e1_passages.csv", rows)

    wrows = []
    for start, count in WINDOW_RUNS.items():
        for j, text in enumerate(book.windows(paras, start, WINDOW, count)):
            scores, tokens, ms = clf(text)
            wrows.append(row(scores, run=start, window=j, start_word=j * WINDOW, tokens=tokens,
                             ms=round(ms), begins=" ".join(text.split()[:10])))
            print(f"win {j:2} @{j * WINDOW:5}w  {wrows[-1]['top']:12} "
                  + " ".join(f"{k[:4]}={v:.2f}" for k, v in scores.items()), flush=True)
    write_csv("e1_windows.csv", wrows)

    # padding check: the model card pads every input to 2048 tokens
    pad = []
    for pid in ("spouter_painting", "squeeze", "catastrophe"):
        text = book.words_from(paras, PASSAGES[pid][0], 300)
        a, _, ms_a = clf(text)
        b, _, ms_b = clf(text, pad=True)
        pad.append({"passage": pid, "max_abs_diff": max(abs(a[k] - b[k]) for k in a),
                    "ms_unpadded": round(ms_a), "ms_padded": round(ms_b)})
        print("pad", pad[-1], flush=True)

    meta = {
        "model": MODEL,
        "revision": model_info(MODEL).sha,
        "max_tokens": MAX_TOKENS,
        "threads": THREADS,
        "load_s": round(clf.load_s, 1),
        "peak_rss_mb": round(clf.peak_rss),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cpu": platform.processor() or platform.machine(),
        "padding_check": pad,
    }
    with open(os.path.join(OUT, "e1_run.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
