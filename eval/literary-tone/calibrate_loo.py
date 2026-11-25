"""Quick check of "option A": calibrating the frozen PERT + EmoLit outputs to the 1-5 V/A/T scales.

Leave-one-out over the 16 passages (700 words): fit on 15, predict the held-out one. Every choice
that looks at labels (which aggregate, the weights) happens inside the loop. Fixed in advance:
the feature sets, ridge alpha (standardized features), no other tuning.

  M0  mean aggregate of the dimension's model -> linear map
  M1  the aggregate with the best training rho (chosen per fold) -> linear map
  M2  ridge on all 5 aggregates of the dimension's model (alpha 1)
  M3  ridge on all aggregates of pert.V, pert.A and emolit.T (15 features, alpha 5)
  const  predict the training mean (MAE floor to beat)

A linear map of one feature cannot change the ranking, so M0/M1 can only improve the scale (MAE,
range); only M2/M3 can improve rho. The quartile cuts of -low/high use all passages' sentences
(no labels), a small unsupervised leak.

Usage: ~/.venvs/music-book-eval/bin/python calibrate_loo.py
"""
import os

import numpy as np

import analyze_sentences as an

SOURCE = {"V": ("pert", "V"), "A": ("pert", "A"), "T": ("emolit", "T")}
AGGS = an.AGGS


def features():
    data = {m: an.read(os.path.join(an.RES, f"sent_{m}.csv")) for m in ("pert", "emolit")}
    gold = {r["passage"]: {"V": int(r["valence"]), "A": int(r["arousal"]), "T": int(r["tension"])}
            for r in an.read(os.path.join(an.HERE, "annotations_vat.csv"))}
    pids = list(gold)
    feats = {}
    for m, d in SOURCE.values():
        rows = data[m]
        cuts = an.pooled_cuts(rows, d)
        ps = an.passage_sentences(rows, 700)
        for a in AGGS:
            feats[f"{m}.{d}:{a}"] = np.array([an.aggregate(ps[p], d, cuts)[a] for p in pids])
    return pids, gold, feats


def ridge_fit(X, y, alpha):
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return lambda Xn: ((Xn - mu) / sd) @ w + y.mean()


def linear_fit(x, y):
    b, a = np.polyfit(x, y, 1)
    return lambda xn: b * xn + a


def loo(n, fit_predict):
    pred = np.zeros(n)
    for i in range(n):
        tr = np.array([j for j in range(n) if j != i])
        pred[i] = fit_predict(tr, i)
    return pred


def main():
    pids, gold, feats = features()
    n = len(pids)
    names_all = list(feats)
    print(f"{n} passages, leave-one-out. rho = Spearman with the provisional labels, "
          f"MAE on the 1-5 scale, range = max-min of the predictions (gold range in brackets)\n")
    print("| Dim | Model | rho | MAE | range | picked aggregates (folds) |")
    print("|---|---|---|---|---|---|")
    for d, (m, sd) in SOURCE.items():
        y = np.array([gold[p][d] for p in pids], dtype=float)
        own = [f"{m}.{sd}:{a}" for a in AGGS]
        X_own = np.column_stack([feats[k] for k in own])
        X_all = np.column_stack([feats[k] for k in names_all])
        picks = []

        def m0(tr, i):
            x = feats[f"{m}.{sd}:mean"]
            return linear_fit(x[tr], y[tr])(x[i])

        def m1(tr, i):
            best = max(own, key=lambda k: an.spearman(list(feats[k][tr]), list(y[tr])))
            picks.append(best.split(":")[1])
            x = feats[best]
            return linear_fit(x[tr], y[tr])(x[i])

        def m2(tr, i):
            return ridge_fit(X_own[tr], y[tr], 1.0)(X_own[i:i + 1])[0]

        def m3(tr, i):
            return ridge_fit(X_all[tr], y[tr], 5.0)(X_all[i:i + 1])[0]

        def const(tr, i):
            return y[tr].mean()

        raw_best = max(an.spearman(list(feats[k]), list(y)) for k in own)
        for name, fn in (("const", const), ("M0 mean", m0), ("M1 best agg", m1),
                         ("M2 ridge own", m2), ("M3 ridge all", m3)):
            picks.clear()
            p = loo(n, fn)
            rho = an.spearman(list(p), list(y)) if p.std() > 0 else float("nan")
            mae = np.abs(p - y).mean()
            pk = ""
            if picks:
                pk = ", ".join(f"{a}×{picks.count(a)}" for a in sorted(set(picks), key=picks.count, reverse=True))
            print(f"| {d} | {name} | {an.f(rho)} | {mae:.2f} | {p.max() - p.min():.2f} ({y.max() - y.min():.0f}) | {pk} |")
        print(f"| {d} | *raw best aggregate, picked on all 16 (optimistic)* | {an.f(raw_best)} | – | – | |")


if __name__ == "__main__":
    main()
