"""E2 evaluation against the provisional labels (annotations_e2.csv), without thresholds.

- per-label average precision over the 16 passages (ranking only; chance level = prevalence);
- top-1 hit (the best label is an expected one) and top-3 recall per passage;
- the spread of each label's score across passages (does the model separate them at all?);
- the E1 tone classifier on the two shared labels (melancholic, warm ~ "warm and cozy").

Standard library only. Usage: python3 analyze_e2.py
"""
import csv
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
E1_SHARED = {"melancholic": "melancholic", "warm and cozy": "warm"}  # E2 label -> E1 label


def read(name):
    with open(os.path.join(HERE, name), newline="") as f:
        return list(csv.DictReader(f))


def average_precision(scores, positives):
    ranked = sorted(scores, key=scores.get, reverse=True)
    hits, total = 0, 0.0
    for i, pid in enumerate(ranked, 1):
        if pid in positives:
            hits += 1
            total += hits / i
    return total / len(positives)


def evaluate(rows, gold, labels):
    """-> per-label (ap, prevalence, spread), top-1 hits, mean top-3 recall"""
    per_label = {}
    for label in labels:
        positives = {p for p, ls in gold.items() if label in ls}
        if not positives:
            continue
        scores = {r["passage"]: float(r[label]) for r in rows}
        per_label[label] = (average_precision(scores, positives), len(positives) / len(gold),
                            statistics.pstdev(scores.values()))
    top1 = sum(r["top3"].split("|")[0] in gold[r["passage"]] for r in rows)
    recall3 = statistics.mean(
        len(set(r["top3"].split("|")) & gold[r["passage"]]) / min(3, len(gold[r["passage"]]))
        for r in rows)
    return per_label, top1, recall3


def main():
    gold = {r["passage"]: set(r["labels"].split("|")) for r in read("annotations_e2.csv")}
    rows = read("results/e2_passages.csv")
    labels = [k for k in rows[0] if k not in
              ("passage", "template", "words", "tokens", "ms", "top3") and not k.startswith("single:")]

    runs = sorted({(r["template"], int(r["words"])) for r in rows})
    print("| Run | macro AP | chance (mean prevalence) | top-1 hit | top-3 recall |")
    print("|---|---|---|---|---|")
    detail = {}
    for template, n in runs:
        sub = [r for r in rows if r["template"] == template and int(r["words"]) == n]
        per_label, top1, recall3 = evaluate(sub, gold, labels)
        detail[(template, n)] = per_label
        ap = statistics.mean(v[0] for v in per_label.values())
        chance = statistics.mean(v[1] for v in per_label.values())
        print(f"| {template}, {n} words | {ap:.2f} | {chance:.2f} | {top1}/{len(sub)} | {recall3:.2f} |")

    print("\n| Label | positives | " + " | ".join(f"AP {t} {n}w" for t, n in runs)
          + " | spread (std) v1 300w |")
    print("|---|---|" + "---|" * len(runs) + "---|")
    for label in labels:
        if label not in detail[runs[0]]:
            print(f"| {label} | 0 |" + " – |" * len(runs) + " – |")
            continue
        n_pos = round(detail[runs[0]][label][1] * len(gold))
        aps = " | ".join(f"{detail[r][label][0]:.2f}" for r in runs)
        print(f"| {label} | {n_pos} | {aps} | {detail[('v1', 300)][label][2]:.3f} |")

    e1 = read("results/e1_passages.csv")
    print("\n| Shared label | " + " | ".join(f"{n}w E1 / E2" for n in (150, 300, 700)) + " |")
    print("|---|---|---|---|")
    for e2_label, e1_label in E1_SHARED.items():
        positives = {p for p, ls in gold.items() if e2_label in ls}
        cells = []
        for n in (150, 300, 700):
            a = average_precision({r["passage"]: float(r[e1_label]) for r in e1
                                   if int(r["words"]) == n}, positives)
            b = detail[("v1", n)][e2_label][0]
            cells.append(f"{a:.2f} / {b:.2f}")
        print(f"| {e2_label} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
