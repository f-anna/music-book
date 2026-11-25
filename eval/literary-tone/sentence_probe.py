"""Sentence-level scoring of task-specific emotion models on the Moby Dick passages of E1/E2.

The earlier runs flattened the mood: model-selection averaged ~300-word chunk scores, E1 scored a
whole passage in one call. Here every sentence is scored on its own (stories-emotion with +-4
sentences of context, as it was trained), and the per-passage aggregation (mean, percentiles,
share of extreme sentences) is left to analyze_sentences.py.

Units (column `kind`):
- passage: each passage of tone_probe.PASSAGES, cut on a sentence boundary once it has >= 700
  words (the analysis also uses its >= 300-word prefix). Chapter headings are left out;
- window: the chapters of tone_probe.WINDOW_RUNS as one sentence stream; the analysis assigns
  sentences to 300-word windows by their first word;
- chunk (vad-bert and GoEmotions only): the old model-selection method, the 700-word passage in
  ~300-word chunks cut on sentence boundaries, so both methods are compared on the same text.

Every model runs in its own subprocess (clean peak-RSS measurement, memory freed in between).
Writes results/sent_<model>.csv (one row per sentence or chunk) and results/sent_<model>.json.

Usage: python sentence_probe.py <moby_dick.epub> [model ...]   (~/.venvs/music-book-eval python)
       models: vadbert goemotions pert fiction emolit stories (default: all)
"""
import csv
import json
import os
import platform
import re
import subprocess
import sys
import time

import psutil
import torch
import transformers
from huggingface_hub import hf_hub_download, model_info
from torch import nn
from transformers import (AutoModelForSequenceClassification, AutoModelForTokenClassification,
                          AutoTokenizer, RobertaConfig, RobertaModel)

import book
from tone_probe import PASSAGES, WINDOW, WINDOW_RUNS

THREADS = 4
PASSAGE_WORDS = 700   # the median segment size of the plugin
CHUNK_WORDS = 300     # the chunk size of the old model-selection run
BATCH = 16
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

MODELS = {
    "vadbert": "RobroKools/vad-bert",
    "goemotions": "SamLowe/roberta-base-go_emotions",
    "pert": "edsi-umd/PERT-EmoPair",
    "fiction": "fpianz/sentiment-fiction",
    "emolit": "lrei/roberta-large-emolit",
    "stories": "chrlukas/stories-emotion-c4",
}
CHUNKED = {"vadbert", "goemotions"}

# GoEmotions label -> (valence -1..1, arousal 0..1), a hand-made Russell-style placement.
# It re-creates the (deleted) table of the model-selection run, so the numbers are not identical.
GOEMOTIONS_VA = {
    "admiration": (0.6, 0.4), "amusement": (0.7, 0.6), "anger": (-0.7, 0.8),
    "annoyance": (-0.5, 0.6), "approval": (0.5, 0.3), "caring": (0.6, 0.3),
    "confusion": (-0.2, 0.5), "curiosity": (0.3, 0.6), "desire": (0.5, 0.6),
    "disappointment": (-0.6, 0.3), "disapproval": (-0.5, 0.4), "disgust": (-0.7, 0.6),
    "embarrassment": (-0.5, 0.6), "excitement": (0.7, 0.9), "fear": (-0.7, 0.8),
    "gratitude": (0.7, 0.3), "grief": (-0.8, 0.4), "joy": (0.8, 0.7), "love": (0.8, 0.5),
    "nervousness": (-0.5, 0.7), "optimism": (0.6, 0.5), "pride": (0.6, 0.6),
    "realization": (0.1, 0.4), "relief": (0.5, 0.2), "remorse": (-0.6, 0.3),
    "sadness": (-0.7, 0.2), "surprise": (0.2, 0.8), "neutral": (0.0, 0.3),
}


def tension_proxy(p):
    """The model-selection formula; GoEmotions and EmoLit both have these labels."""
    return min(1.0, p["fear"] + p["nervousness"] + 0.6 * p["anger"]
               + 0.3 * (p["annoyance"] + p["disgust"]))


# --- text -------------------------------------------------------------------------------------

ABBREV = re.compile(r"\b(?:Mr|Mrs|Dr|St|Capt|Messrs|Mt|vs|viz|etc|No|i\.e|e\.g)$")
BOUNDARY = re.compile(r"([.!?][”\"’)\]]*)\s+(?=[“\"‘(\[]?[A-Z0-9])")


def split_sentences(par):
    """Rule-based split: end mark (+ closing quotes), whitespace, then a capital / opening quote.

    A lowercase continuation ('“Avast!” cried he') is not a boundary, and neither are the
    abbreviations of ABBREV.
    """
    out, start = [], 0
    for m in BOUNDARY.finditer(par):
        if ABBREV.search(par[start:m.start(1)]):
            continue
        out.append(par[start:m.end(1)].strip())
        start = m.end()
    tail = par[start:].strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


def sentence_stream(paras, start):
    i, k = book.start_index(paras, start)
    if paras[i].startswith("CHAPTER"):
        i, k = i + 1, 0
    for j, p in enumerate(paras[i:]):
        text = p[k:] if j == 0 else p
        if text.startswith("CHAPTER"):   # a later chapter title would leak a label
            continue
        yield from split_sentences(text)


def cut(paras, start, n):
    """-> [(first word offset, sentence)] until the passage has >= n words."""
    out, w = [], 0
    for s in sentence_stream(paras, start):
        if w >= n:
            break
        out.append((w, s))
        w += len(s.split())
    return out


def chunks(sents, size):
    """Consecutive sentences grouped into chunks of >= size words (the remainder is its own)."""
    out, cur, w0 = [], [], 0
    for w, s in sents:
        if not cur:
            w0 = w
        cur.append(s)
        if sum(len(x.split()) for x in cur) >= size:
            out.append((w0, " ".join(cur)))
            cur = []
    if cur:
        out.append((w0, " ".join(cur)))
    return out


# --- models -----------------------------------------------------------------------------------

def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class SeqClassifier:
    """vad-bert (regression), GoEmotions / EmoLit (sigmoid), sentiment-fiction (softmax)."""

    def __init__(self, repo, mode):
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.model = AutoModelForSequenceClassification.from_pretrained(repo).eval()
        self.mode = mode
        cfg = self.model.config
        self.labels = [cfg.id2label[i] for i in range(cfg.num_labels)]
        self.max_len = min(512, cfg.max_position_embeddings - 2)

    def __call__(self, texts):
        """-> [(raw {label: value}, truncated)] in input order; batches sorted by length."""
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        res = [None] * len(texts)
        for idx in batched(order, BATCH):
            batch = [texts[i] for i in idx]
            enc = self.tok(batch, truncation=True, max_length=self.max_len, padding=True,
                           return_tensors="pt")
            full = [len(x) for x in self.tok(batch)["input_ids"]]
            with torch.no_grad():
                logits = self.model(**enc).logits
            if self.mode == "sigmoid":
                vals = torch.sigmoid(logits)
            elif self.mode == "softmax":
                vals = torch.softmax(logits, dim=1)
            else:
                vals = logits
            for i, v, n in zip(idx, vals.tolist(), full):
                res[i] = (dict(zip(self.labels, v)), n > self.max_len)
        return res


class PertEmoPair:
    """edsi-umd/PERT-EmoPair: roberta-large + linear head on <s>, prompted input (model card)."""

    PROMPT = ("- Valence: The emotional valence of the context is <mask>. "
              "- Arousal: The level of arousal of the context is <mask>. "
              "- Dominance: The perceived dominance associated with the context is <mask>. "
              "Please predict the missing value for each dimension using the content provided.")
    MAX_LEN = 256  # the card's max_length

    class Net(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.base_model = RobertaModel(cfg)
            self.dropout = nn.Dropout(p=0.1)
            self.regressor = nn.Linear(cfg.hidden_size, 3)

        def forward(self, input_ids, attention_mask):
            out = self.base_model(input_ids=input_ids, attention_mask=attention_mask)
            return self.regressor(out.last_hidden_state[:, 0, :])

    def __init__(self, repo):
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.model = self.Net(RobertaConfig.from_pretrained(repo))
        state = torch.load(hf_hub_download(repo, "pytorch_model.bin"), map_location="cpu",
                           weights_only=True)
        state = state.get("model_state_dict", state)
        missing, unexpected = self.model.load_state_dict(state, strict=False)
        bad = [k for k in missing if "pooler" not in k]
        if bad or unexpected:
            raise RuntimeError(f"weights do not fit: missing {bad[:5]}, unexpected {unexpected[:5]}")
        self.load_note = {"missing_keys": missing, "unexpected_keys": unexpected}
        self.model.eval()
        self.labels = ["valence", "arousal", "dominance"]
        # the card truncates the whole prompted string, which would cut the <mask>s off a long
        # sentence; the context is truncated instead, so the prompt always stays
        empty = len(self.tok(f"Context: '' {self.PROMPT}")["input_ids"])
        self.budget = self.MAX_LEN - empty

    def __call__(self, texts):
        prompted, trunc = [], []
        for t in texts:
            ids = self.tok(t, add_special_tokens=False)["input_ids"]
            trunc.append(len(ids) > self.budget)
            if len(ids) > self.budget:
                t = self.tok.decode(ids[:self.budget])
            prompted.append(f"Context: '{t}' {self.PROMPT}")
        order = sorted(range(len(texts)), key=lambda i: len(prompted[i]))
        res = [None] * len(texts)
        for idx in batched(order, BATCH):
            enc = self.tok([prompted[i] for i in idx], truncation=True, max_length=self.MAX_LEN,
                           padding=True, return_tensors="pt")
            with torch.no_grad():
                vals = self.model(enc["input_ids"], enc["attention_mask"]).tolist()
            for i, v in zip(idx, vals):
                res[i] = (dict(zip(self.labels, v)), trunc[i])
        return res


class StoriesEmotion:
    """chrlukas/stories-emotion-c4: token classification, the prediction of a sentence is at the
    [SEP] after it; input = the sentence with WINDOW sentences on each side, joined by [SEP]
    (src/data.py of lc0197/emotional_trajectories_stories). Sigmoid -> 0..1."""

    WINDOW = 4

    def __init__(self, repo):
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.model = AutoModelForTokenClassification.from_pretrained(repo).eval()
        self.labels = ["valence", "arousal"]  # V_EWE, A_EWE

    def encode(self, sents, i):
        """Like the repo: shrink the window until the centre sentence's [SEP] fits in 512."""
        sep = f" {self.tok.sep_token} "
        rl = rr = 0
        while True:
            left = max(i - self.WINDOW + rl, 0)
            right = min(i + self.WINDOW + 1 - rr, len(sents))
            ids = self.tok(sep.join(s.strip() for s in sents[left:right]), truncation=True,
                           max_length=512)["input_ids"]
            seps = [k for k, t in enumerate(ids) if t == self.tok.sep_token_id]
            centre = i - left
            if len(seps) > centre:
                return ids, seps[centre], (rl + rr) > 0
            if rl < rr:
                rl += 1
            else:
                rr += 1

    def score_unit(self, sents):
        encs = [self.encode(sents, i) for i in range(len(sents))]
        res = [None] * len(sents)
        order = sorted(range(len(sents)), key=lambda i: len(encs[i][0]))
        for idx in batched(order, BATCH // 2):
            batch = self.tok.pad({"input_ids": [encs[i][0] for i in idx]}, return_tensors="pt")
            with torch.no_grad():
                logits = self.model(**batch).logits
            for b, i in enumerate(idx):
                v = torch.sigmoid(logits[b, encs[i][1]]).tolist()
                res[i] = (dict(zip(self.labels, v)), encs[i][2])
        return res


def load(name):
    repo = MODELS[name]
    if name == "pert":
        return PertEmoPair(repo)
    if name == "stories":
        return StoriesEmotion(repo)
    mode = {"vadbert": "regression", "fiction": "softmax"}.get(name, "sigmoid")
    return SeqClassifier(repo, mode)


def derived(name, raw):
    """The common V / A / T columns (where the model has them) from the raw outputs."""
    if name == "vadbert":
        v, a, d = (raw[k] for k in ("LABEL_0", "LABEL_1", "LABEL_2"))
        return {"V": v, "A": a, "D": d}
    if name == "pert":
        return {"V": raw["valence"], "A": raw["arousal"], "D": raw["dominance"]}
    if name == "fiction":
        return {"V": raw["positive"] - raw["negative"]}
    if name == "stories":
        return {"V": raw["valence"], "A": raw["arousal"]}
    if name == "goemotions":
        total = sum(raw.values())
        return {"V": sum(raw[k] * GOEMOTIONS_VA[k][0] for k in raw) / total,
                "A": sum(raw[k] * GOEMOTIONS_VA[k][1] for k in raw) / total,
                "T": tension_proxy(raw)}
    if name == "emolit":
        return {"T": tension_proxy(raw)}
    raise KeyError(name)


# --- run --------------------------------------------------------------------------------------

def rss_mb():
    return psutil.Process().memory_info().rss / 2**20


def units(paras):
    """-> [(kind, unit id, [(word offset, text)])]"""
    out = [("passage", pid, cut(paras, start, PASSAGE_WORDS)) for pid, (start, _) in PASSAGES.items()]
    for start, count in WINDOW_RUNS.items():
        out.append(("window", start, cut(paras, start, WINDOW * count)))
    return out


def run_one(epub, name):
    torch.set_num_threads(THREADS)
    paras = book.block_paragraphs(epub)
    t0 = time.perf_counter()
    model = load(name)
    load_s = time.perf_counter() - t0
    peak = rss_mb()
    print(f"[{name}] loaded in {load_s:.1f}s, rss {peak:.0f} MB", flush=True)

    rows, timing = [], {"passage_s": 0.0, "passage_words": 0, "passage_sentences": 0}
    work = units(paras)
    if name in CHUNKED:
        work += [("chunk", pid, chunks(sents, CHUNK_WORDS)) for kind, pid, sents in work
                 if kind == "passage"]
    for kind, uid, items in work:
        texts = [t for _, t in items]
        t1 = time.perf_counter()
        scored = model.score_unit(texts) if name == "stories" else model(texts)
        dt = time.perf_counter() - t1
        peak = max(peak, rss_mb())
        if kind == "passage":
            timing["passage_s"] += dt
            timing["passage_words"] += sum(len(t.split()) for t in texts)
            timing["passage_sentences"] += len(texts)
        for j, ((w, text), (raw, trunc)) in enumerate(zip(items, scored)):
            rows.append({"kind": kind, "unit": uid, "idx": j, "word_start": w,
                         "words": len(text.split()), "truncated": int(trunc),
                         **{k: round(v, 5) for k, v in derived(name, raw).items()},
                         **{f"raw:{k}": round(v, 5) for k, v in raw.items()},
                         "text": text})
        print(f"[{name}] {kind:7} {uid[:30]:30} {len(texts):4} items {dt:6.1f}s", flush=True)

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"sent_{name}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    meta = {
        "model": MODELS[name],
        "revision": model_info(MODELS[name]).sha,
        "threads": THREADS,
        "load_s": round(load_s, 1),
        "peak_rss_mb": round(peak),
        **{k: round(v, 2) if isinstance(v, float) else v for k, v in timing.items()},
        "s_per_1000_words": round(1000 * timing["passage_s"] / timing["passage_words"], 2),
        "truncated_items": sum(r["truncated"] for r in rows),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cpu": platform.processor() or platform.machine(),
        **getattr(model, "load_note", {}),
    }
    with open(os.path.join(OUT, f"sent_{name}.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"[{name}] done: {json.dumps({k: meta[k] for k in ('load_s', 'peak_rss_mb', 's_per_1000_words', 'truncated_items')})}",
          flush=True)


def main():
    epub = sys.argv[1]
    if len(sys.argv) > 3 and sys.argv[2] == "--one":
        run_one(epub, sys.argv[3])
        return
    names = sys.argv[2:] or list(MODELS)
    failed = []
    for name in names:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), epub, "--one", name])
        if r.returncode:
            failed.append(name)
            print(f"[{name}] FAILED with exit code {r.returncode}", flush=True)
    print("failed:", failed or "none")


if __name__ == "__main__":
    main()
