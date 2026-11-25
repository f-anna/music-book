"""Evaluation of sentence_probe.py: sentence scores -> passage aggregates -> provisional labels.

Aggregates of a passage (over its sentences): word-weighted mean, p10, p90, and the word share of
"extreme" sentences: -low (minus the share below the model's pooled 25th percentile, so a higher
value means more positive / aroused / tense, like the others) and high (share above the 75th).

- spread: how much of the model's scale the passage means use (range and std / nominal scale),
  the measure of the model-selection run (there: 4-5 %);
- Spearman rho against annotations_vat.csv (16 passages, provisional 1-5 V/A/T), per aggregate;
  with 16 passages |rho| >= 0.50 is needed for p < 0.05;
- Spearman rho against the Qwen3-4B v4 output on the 7 shared passages (mean aggregate);
- chunk (the old method) vs sentence aggregation for vad-bert and GoEmotions;
- agreement between the models (Spearman of the passage means);
- GoEmotions / EmoLit: average precision of the atmosphere labels of annotations_e2.csv, through
  a hand-made emotion -> atmosphere mapping (ATMOSPHERE);
- windows: z-scored window means through the two chapters of tone_probe.WINDOW_RUNS.

Standard library only. Usage: python3 analyze_sentences.py   (writes results/sent_analysis.md too)
"""
import csv
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results")
MODELS = ["vadbert", "pert", "fiction", "stories", "goemotions", "emolit"]
DIMS = ["V", "A", "T"]
WINDOW = 300
SHORT = 300  # the shorter passage: the prefix of the 700-word passage with >= 300 words

# nominal scale width per (model, dim), for the spread
NOMINAL = {
    ("vadbert", "V"): 4, ("vadbert", "A"): 4,      # EmoBank 1..5
    ("pert", "V"): 4, ("pert", "A"): 2,            # V ~1..5; A centred on 0 (observed -0.78..0.82), -1..1 assumed
    ("fiction", "V"): 2,                           # p(pos) - p(neg), -1..1
    ("stories", "V"): 1, ("stories", "A"): 1,      # sigmoid 0..1
    ("goemotions", "V"): 2, ("goemotions", "A"): 1, ("goemotions", "T"): 1,
    ("emolit", "T"): 1,
}
# Qwen3-4B, prompt v4 (../qwen3-llamacpp/RESULTS.md, round 4), 700 words from the same start
QWEN = {
    "spouter_painting": (2, 4, 4), "castaway": (2, 4, 4), "candles": (3, 4, 4),
    "squeeze": (5, 3, 1), "bosom_friend": (4, 2, 2), "symphony": (3, 2, 3),
    "catastrophe": (2, 5, 5),
}
# atmosphere label (annotations_e2.csv) -> emotion labels summed, per model; hand-made
ATMOSPHERE = {
    "goemotions": {
        "ominous": ["fear", "nervousness"],
        "suspenseful": ["fear", "nervousness", "excitement"],
        "mysterious": ["confusion", "curiosity"],
        "melancholic": ["sadness", "grief", "disappointment", "remorse"],
        "warm and cozy": ["caring", "love", "gratitude"],
        "peaceful": ["relief"],
        "oppressive": ["fear", "disgust", "sadness"],
        "whimsical": ["amusement"],
        "wondrous": ["admiration", "surprise", "excitement"],
    },
    "emolit": {
        "ominous": ["fear", "nervousness"],
        "suspenseful": ["fear", "nervousness", "excitement"],
        "mysterious": ["doubt", "curiosity"],
        "melancholic": ["sadness", "grief", "despair", "disappointment", "nostalgia"],
        "warm and cozy": ["caring", "love", "gratitude"],
        "peaceful": ["calmness", "relief"],
        "oppressive": ["despair", "pain", "fear"],
        "whimsical": ["amusement"],
        "wondrous": ["admiration", "surprise", "excitement"],
    },
}
AGGS = ["mean", "p10", "p90", "-low", "high"]

out_lines = []


def emit(s=""):
    print(s)
    out_lines.append(s)


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# --- statistics -------------------------------------------------------------------------------

def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    if statistics.pstdev(ra) == 0 or statistics.pstdev(rb) == 0:
        return float("nan")
    return statistics.correlation(ra, rb)


def quantile(xs, q):
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def average_precision(scores, positives):
    ranked = sorted(scores, key=scores.get, reverse=True)
    hits, total = 0, 0.0
    for i, pid in enumerate(ranked, 1):
        if pid in positives:
            hits += 1
            total += hits / i
    return total / len(positives)


def f(x, d=2):
    return "–" if x is None or x != x else f"{x:+.{d}f}" if d == 2 else f"{x:.{d}f}"


# --- aggregation ------------------------------------------------------------------------------

def passage_sentences(rows, words):
    """{passage: [(value row, words)]} of the passage cut at `words` (same rule as the probe)."""
    out = {}
    for r in rows:
        if r["kind"] != "passage":
            continue
        if int(r["word_start"]) >= words:
            continue
        out.setdefault(r["unit"], []).append(r)
    return out


def aggregate(sents, col, cuts):
    vals = [float(r[col]) for r in sents]
    w = [int(r["words"]) for r in sents]
    tot = sum(w)
    q25, q75 = cuts
    return {
        "mean": sum(v * x for v, x in zip(vals, w)) / tot,
        "p10": quantile(vals, 0.10),
        "p90": quantile(vals, 0.90),
        "-low": -sum(x for v, x in zip(vals, w) if v <= q25) / tot,
        "high": sum(x for v, x in zip(vals, w) if v >= q75) / tot,
    }


def pooled_cuts(rows, col):
    vals = [float(r[col]) for r in rows if r["kind"] == "passage"]
    return quantile(vals, 0.25), quantile(vals, 0.75)


# --- main -------------------------------------------------------------------------------------

def main():
    data = {m: read(os.path.join(RES, f"sent_{m}.csv")) for m in MODELS
            if os.path.exists(os.path.join(RES, f"sent_{m}.csv"))}
    meta = {m: json.load(open(os.path.join(RES, f"sent_{m}.json"))) for m in data}
    gold = {r["passage"]: {"V": int(r["valence"]), "A": int(r["arousal"]), "T": int(r["tension"])}
            for r in read(os.path.join(HERE, "annotations_vat.csv"))}
    gold_e2 = {r["passage"]: set(r["labels"].split("|")) for r in read(os.path.join(HERE, "annotations_e2.csv"))}
    pids = list(gold)

    emit(f"Models found: {', '.join(data)}")
    emit()
    emit("## Speed and memory (passages, 16 x ~700 words)")
    emit()
    emit("| Model | Load (s) | Peak RSS (MB) | s / 1000 words | s / passage | Truncated items |")
    emit("|---|---|---|---|---|---|")
    for m in data:
        j = meta[m]
        emit(f"| {m} | {j['load_s']} | {j['peak_rss_mb']} | {j['s_per_1000_words']} | "
             f"{j['passage_s'] / 16:.1f} | {j['truncated_items']} |")

    # aggregates per model/dim/length
    agg = {}  # (m, dim, words) -> {pid: {agg: value}}
    dims_of = {}
    for m, rows in data.items():
        dims_of[m] = [d for d in DIMS if d in rows[0]]
        for d in dims_of[m]:
            cuts = pooled_cuts(rows, d)
            for words in (700, SHORT):
                ps = passage_sentences(rows, words)
                agg[(m, d, words)] = {p: aggregate(ps[p], d, cuts) for p in pids}

    emit()
    emit("## Spread of the passage means (700 words)")
    emit()
    emit("| Model.dim | min | max | range / scale | std / scale | sentence-level std / scale |")
    emit("|---|---|---|---|---|---|")
    for m in data:
        for d in dims_of[m]:
            means = [agg[(m, d, 700)][p]["mean"] for p in pids]
            sent = [float(r[d]) for r in data[m] if r["kind"] == "passage"]
            n = NOMINAL[(m, d)]
            emit(f"| {m}.{d} | {min(means):.3f} | {max(means):.3f} | "
                 f"{(max(means) - min(means)) / n:.3f} | {statistics.pstdev(means) / n:.3f} | "
                 f"{statistics.pstdev(sent) / n:.3f} |")

    emit()
    emit("## Spearman rho vs. the provisional V/A/T labels (16 passages; |rho| >= 0.50 ~ p < 0.05)")
    emit()
    emit("| Model.dim | " + " | ".join(f"{a} 700" for a in AGGS) + " | mean 300 | best 300 | vs Qwen (7, mean 700) |")
    emit("|---|" + "---|" * (len(AGGS) + 3))
    for m in data:
        for d in dims_of[m]:
            g = [gold[p][d] for p in pids]
            cells = [spearman([agg[(m, d, 700)][p][a] for p in pids], g) for a in AGGS]
            short = [spearman([agg[(m, d, SHORT)][p][a] for p in pids], g) for a in AGGS]
            qp = list(QWEN)
            qi = DIMS.index(d)
            q = spearman([agg[(m, d, 700)][p]["mean"] for p in qp], [QWEN[p][qi] for p in qp])
            emit(f"| {m}.{d} | " + " | ".join(f(c) for c in cells)
                 + f" | {f(short[0])} | {f(max(short))} ({AGGS[short.index(max(short))]}) | {f(q)} |")

    emit()
    emit("## The old method (300-word chunks, word-weighted mean) vs. sentence-level, 700 words")
    emit()
    emit("| Model.dim | chunk: range / scale | sentence mean: range / scale | chunk: rho | sentence mean: rho | sentence best: rho |")
    emit("|---|---|---|---|---|---|")
    for m in ("vadbert", "goemotions"):
        if m not in data:
            continue
        chunk = {}
        for r in data[m]:
            if r["kind"] == "chunk":
                chunk.setdefault(r["unit"], []).append(r)
        for d in dims_of[m]:
            n = NOMINAL[(m, d)]
            cm = {p: sum(float(r[d]) * int(r["words"]) for r in chunk[p]) / sum(int(r["words"]) for r in chunk[p]) for p in pids}
            sm = {p: agg[(m, d, 700)][p]["mean"] for p in pids}
            g = [gold[p][d] for p in pids]
            best = max(spearman([agg[(m, d, 700)][p][a] for p in pids], g) for a in AGGS)
            emit(f"| {m}.{d} | {(max(cm.values()) - min(cm.values())) / n:.3f} | "
                 f"{(max(sm.values()) - min(sm.values())) / n:.3f} | "
                 f"{f(spearman([cm[p] for p in pids], g))} | {f(spearman([sm[p] for p in pids], g))} | {f(best)} |")

    for d in ("V", "A"):
        ms = [m for m in data if d in dims_of[m]]
        emit()
        emit(f"## Agreement between the models, {d} (Spearman of the passage means, 700 words)")
        emit()
        emit("| | " + " | ".join(ms) + " |")
        emit("|---|" + "---|" * len(ms))
        for a in ms:
            emit(f"| {a} | " + " | ".join(
                f(spearman([agg[(a, d, 700)][p]["mean"] for p in pids],
                           [agg[(b, d, 700)][p]["mean"] for p in pids])) for b in ms) + " |")

    # atmosphere labels through the emotion mapping
    for m in ("goemotions", "emolit"):
        if m not in data:
            continue
        emit()
        emit(f"## {m}: atmosphere labels (annotations_e2.csv) via the emotion mapping, average precision")
        emit()
        labels = [l for l in ATMOSPHERE[m] if any(l in s for s in gold_e2.values())]
        cols = []
        for words in (700, SHORT):
            ps = passage_sentences(data[m], words)
            for how in ("mean", "p90"):
                ap = {}
                for l in labels:
                    pos = {p for p in pids if l in gold_e2[p]}
                    scores = {}
                    for p in pids:
                        vals = [sum(float(r[f"raw:{e}"]) for e in ATMOSPHERE[m][l]) for r in ps[p]]
                        w = [int(r["words"]) for r in ps[p]]
                        scores[p] = (sum(v * x for v, x in zip(vals, w)) / sum(w) if how == "mean"
                                     else quantile(vals, 0.9))
                    ap[l] = average_precision(scores, pos)
                cols.append((f"{how} {words}", ap))
        chance = {l: sum(l in gold_e2[p] for p in pids) / len(pids) for l in labels}
        emit("| Label | chance | " + " | ".join(c for c, _ in cols) + " |")
        emit("|---|---|" + "---|" * len(cols))
        for l in labels:
            emit(f"| {l} | {chance[l]:.2f} | " + " | ".join(f"{ap[l]:.2f}" for _, ap in cols) + " |")
        emit(f"| **macro** | {statistics.mean(chance.values()):.2f} | "
             + " | ".join(f"**{statistics.mean(ap.values()):.2f}**" for _, ap in cols) + " |")

    # windows
    emit()
    emit("## Windows (300 words), z-scored window means per column")
    cols = [(m, d) for m in data for d in dims_of[m]]
    for run in sorted({r["unit"] for r in next(iter(data.values())) if r["kind"] == "window"}):
        series = {}
        begins = {}
        for m, d in cols:
            win = {}
            for r in data[m]:
                if r["kind"] == "window" and r["unit"] == run:
                    k = int(r["word_start"]) // WINDOW
                    win.setdefault(k, []).append(r)
                    begins.setdefault(k, " ".join(r["text"].split()[:6]))
            means = {k: sum(float(r[d]) * int(r["words"]) for r in v) / sum(int(r["words"]) for r in v)
                     for k, v in win.items()}
            mu, sd = statistics.mean(means.values()), statistics.pstdev(means.values()) or 1
            series[(m, d)] = {k: (v - mu) / sd for k, v in means.items()}
        emit()
        emit(f"### {run}")
        emit()
        emit("| win | begins | " + " | ".join(f"{m[:5]}.{d}" for m, d in cols) + " |")
        emit("|---|---|" + "---|" * len(cols))
        for k in sorted(begins):
            emit(f"| {k * WINDOW} | {begins[k]}… | "
                 + " | ".join(f"{series[c].get(k, float('nan')):+.1f}" for c in cols) + " |")

    with open(os.path.join(RES, "sent_analysis.md"), "w") as fh:
        fh.write("\n".join(out_lines) + "\n")


if __name__ == "__main__":
    main()
