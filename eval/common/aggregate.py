"""Sentence scores -> one value per segment.

Copied from eval/literary-tone/analyze_sentences.py (the SENT experiment), unchanged.
Standard library only.

Aggregates over a segment's sentences: word-weighted mean, p10, p90, and the word share of
"extreme" sentences: -low (minus the share at or below the pooled 25th percentile, so a higher
value means more positive / aroused / tense, like the others) and high (share at or above the
pooled 75th percentile).
"""

AGGS = ["mean", "p10", "p90", "-low", "high"]


def quantile(xs, q):
    xs = sorted(xs)
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def aggregate(sents, col, cuts):
    """sents: sentence rows of one segment (dicts with `col` and `words`); cuts: pooled_cuts()."""
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
    """25th / 75th percentile of `col` over all sentence rows of kind 'passage' (no labels used)."""
    vals = [float(r[col]) for r in rows if r["kind"] == "passage"]
    return quantile(vals, 0.25), quantile(vals, 0.75)
