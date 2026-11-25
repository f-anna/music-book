"""Sentence-level scoring of the segments with one encoder model (LABELING_GUIDE.md §4, step 2).

Every segment's paragraphs are split into sentences (eval/common/sentences.py) and the model
scores every sentence. Raw outputs and the derived V / A / T go to data/scores/<model>.csv, one
row per sentence; aggregation (p10 / p90 / high, z-scores, tags) is a later step, so it can change
without scoring again. Resumable: segments already in the CSV are skipped, and the file is
flushed after every segment. Run information (revision, device, versions, timing, peak memory)
goes to data/scores/<model>.json.

On a laptop: one model per process (the large models do not fit in memory together), and stop
llama-server first. On a GPU (Kaggle) the notebook calls run() directly, model after model.

Usage (the ~/.venvs/music-book-eval python, from this directory):
  python score.py --model pert --select gold
  models: pert emolit fiction_seq litbert_base litbert_large
  select: gold | evaltest (all validation + test segments) | train | all
"""
import argparse
import csv
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "common")]
# LABELING_DATA overrides the data folder (on Kaggle: /kaggle/working/data, which is kept)
DATA = os.environ.get("LABELING_DATA", os.path.join(HERE, "data"))
SEGMENTS = os.path.join(DATA, "segments.jsonl")
SCORES = os.path.join(DATA, "scores")


def select(records, which):
    if which == "gold":
        return [r for r in records if r["gold"]]
    if which == "evaltest":
        return [r for r in records if r["split"] in ("validation", "test")]
    if which == "train":
        return [r for r in records if r["split"] == "train"]
    if which == "all":
        return records
    raise ValueError(which)


def scored_ids(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="") as f:
        return {r["segment"] for r in csv.DictReader(f)}


def run(model_name, which="gold", device="auto", limit=None, log=print):
    import psutil
    import torch
    import transformers

    import encoders
    from sentences import split_sentences

    with open(SEGMENTS) as f:
        records = [json.loads(line) for line in f if line.strip()]
    os.makedirs(SCORES, exist_ok=True)
    out = os.path.join(SCORES, f"{model_name}.csv")
    done = scored_ids(out)
    todo = [r for r in select(records, which) if r["id"] not in done][:limit]
    if not todo:
        log(f"[{model_name}] nothing to do ({which}: all scored)")
        return
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.set_num_threads(encoders.THREADS)

    t0 = time.perf_counter()
    model = encoders.load(model_name, device)
    load_s = time.perf_counter() - t0
    log(f"[{model_name}] loaded in {load_s:.0f}s on {device}; {len(todo)} segments to go ({which})")

    proc = psutil.Process()
    peak = proc.memory_info().rss
    new = not os.path.exists(out)
    total_s, total_sents, n_trunc = 0.0, 0, 0
    with open(out, "a", newline="") as f:
        writer = None
        for n, r in enumerate(todo, 1):
            sents = [s for p in r["paragraphs"] for s in split_sentences(p)]
            t1 = time.perf_counter()
            scored = model(sents)
            dt = time.perf_counter() - t1
            rows, pos = [], 0
            for j, (text, (raw, trunc)) in enumerate(zip(sents, scored)):
                words = len(text.split())
                rows.append({"segment": r["id"], "idx": j, "word_start": pos, "words": words,
                             "truncated": int(trunc),
                             **{k: round(v, 5) for k, v in encoders.derived(model_name, raw).items()},
                             **{f"raw:{k}": round(v, 5) for k, v in raw.items()},
                             "seconds": round(dt, 2) if j == 0 else ""})
                pos += words
                n_trunc += int(trunc)
            if writer is None:
                writer = csv.DictWriter(f, fieldnames=list(rows[0]))
                if new:
                    writer.writeheader()
            writer.writerows(rows)
            f.flush()
            total_s += dt
            total_sents += len(sents)
            peak = max(peak, proc.memory_info().rss)
            log(f"[{model_name}] [{n}/{len(todo)}] {r['id']} {len(sents)} sentences {dt:.1f}s")

    info_path = os.path.join(SCORES, f"{model_name}.json")
    runs = []
    if os.path.exists(info_path):
        with open(info_path) as f:
            runs = json.load(f)
    repo, revision = encoders.MODELS[model_name]
    runs.append({"model": repo, "revision": revision, "select": which, "segments": len(todo),
                 "sentences": total_sents, "truncated": n_trunc, "device": device,
                 "threads": encoders.THREADS, "load_s": round(load_s, 1),
                 "score_s": round(total_s, 1), "s_per_segment": round(total_s / len(todo), 2),
                 "peak_rss_mb": round(peak / 2**20), "torch": torch.__version__,
                 "transformers": transformers.__version__, "cpu": platform.machine(),
                 "load_note": getattr(model, "load_note", None),
                 "finished": time.strftime("%Y-%m-%d %H:%M:%S")})
    with open(info_path, "w") as f:
        json.dump(runs, f, indent=2, default=str)
    log(f"[{model_name}] done: {len(todo)} segments, {total_s / len(todo):.1f} s/segment")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--select", default="gold", choices=["gold", "evaltest", "train", "all"])
    ap.add_argument("--device", default="auto")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    run(args.model, args.select, args.device, args.limit, log=lambda s: print(s, flush=True))


if __name__ == "__main__":
    main()
