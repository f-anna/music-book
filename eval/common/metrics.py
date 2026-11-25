"""Rank correlation, average precision and small report helpers.

Copied from eval/literary-tone/analyze_sentences.py (the SENT experiment); `read` is renamed to
`read_csv` and `f` to `fmt`. Standard library only.
"""
import csv
import statistics


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def ranks(xs):
    """Average ranks (ties share the mean rank)."""
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


def average_precision(scores, positives):
    """scores: {id: score}; positives: the ids that carry the label."""
    ranked = sorted(scores, key=scores.get, reverse=True)
    hits, total = 0, 0.0
    for i, pid in enumerate(ranked, 1):
        if pid in positives:
            hits += 1
            total += hits / i
    return total / len(positives)


def fmt(x, d=2):
    """Signed with 2 decimals by default, '–' for None / NaN."""
    return "–" if x is None or x != x else f"{x:+.{d}f}" if d == 2 else f"{x:.{d}f}"
