"""Option A, proper test: calibrated PERT-EmoPair + EmoLit vs. Qwen3-4B labels on several books.

Steps (each resumable; rerunning skips what is done):

  fetch     download the Gutenberg EPUBs of BOOKS into --books (outside the repo)
  segments  segment every book like the plugin (epub.rs rules), sample PER_BOOK segments per book,
            evenly spaced through the book -> data/segments.jsonl
  label     Qwen3-4B (prompt v4 of ../qwen3-llamacpp) on every segment -> data/qwen.jsonl
            needs llama-server (start it with -c 3072: a segment can be ~1100 words)
  score     PERT-EmoPair and EmoLit, sentence by sentence -> data/sent_<model>.csv
            stop llama-server first: the two do not fit in memory together
  handsheet a blind sheet for hand labels (no model output in it): data/hand_labels.csv + .md
  evaluate  leave-one-book-out calibration, against Qwen and (if filled in) the hand labels

Calibration methods (fixed in advance from ../literary-tone, calibrate_loo.py):
  V = pert.V "-low", A = pert.A "p90", T = emolit.T "high"   (one aggregate -> linear map)
  plus: T from pert.A "high" (the shortcut), per-fold best single aggregate, ridge on all 15.

Usage (from this directory, with the ~/.venvs/music-book-eval python):
  python calibration_test.py fetch
  python calibration_test.py segments
  python calibration_test.py label            # hours; run under nohup
  python calibration_test.py score            # ~1-2 h
  python calibration_test.py handsheet
  python calibration_test.py evaluate
"""
import argparse
import csv
import json
import os
import posixpath
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, "..", "common"), os.path.join(HERE, "..", "qwen3-llamacpp")]

DATA = os.path.join(HERE, "data")
DEFAULT_BOOKS = os.path.normpath(os.path.join(HERE, "..", "..", "..", "book_source"))

# short id -> (Gutenberg ebook number or None for a local file, file name, why it is in the set)
BOOKS = {
    "moby": (None, "moby_dick.epub", "the development book; essayistic, action, monologues"),
    "dracula": (345, "pg345-dracula.epub", "dread, horror, calm-but-ominous diaries, chase"),
    "pride": (1342, "pg1342-pride-and-prejudice.epub", "humour, warmth, social tension without action"),
    "treasure": (120, "pg120-treasure-island.epub", "adventure, fights, violence, high arousal"),
    "frankenstein": (84, "pg84-frankenstein.epub", "grief, despair, guilt, sublime landscapes"),
    "threemen": (308, "pg308-three-men-in-a-boat.epub", "comic, idyllic river scenes"),
}
PER_BOOK = 50
HAND_PER_BOOK = 17  # ~100 segments for the blind hand labels

# segmentation of the plugin (crates/tauri-plugin-soundtrack/src/epub.rs)
MAX_WORDS, MIN_WORDS, HEADING_MIN = 800, 300, 100
BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "br"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}

# EmoLit emotion -> Qwen tag (summed probabilities), hand-made, for the tag evaluation
TAG_MAP = {
    "calm": ["calmness", "relief"],
    "cheerful": ["joy", "amusement", "optimism"],
    "humorous": ["amusement"],
    "tender": ["caring", "love"],
    "melancholic": ["sadness", "nostalgia", "disappointment"],
    "grief": ["grief", "despair"],
    "solemn": ["faith"],
    "mysterious": ["curiosity", "doubt", "surprise"],
    "ominous": ["fear", "nervousness"],
    "fear": ["fear"],
    "suspense": ["nervousness", "fear", "excitement"],
    "anger": ["anger", "annoyance"],
    "violence": ["anger", "pain", "disgust"],
    "chaos": ["fear", "surprise"],
    "triumph": ["pride", "joy", "excitement"],
    "contemplative": ["curiosity", "calmness"],
}
METHODS = {  # dim -> (model column, aggregate), fixed in advance
    "V": ("pert.V", "-low"),
    "A": ("pert.A", "p90"),
    "T": ("emolit.T", "high"),
}


def path(name):
    return os.path.join(DATA, name)


def read_jsonl(name):
    if not os.path.exists(path(name)):
        return []
    with open(path(name)) as f:
        return [json.loads(line) for line in f if line.strip()]


def append_jsonl(name, obj):
    os.makedirs(DATA, exist_ok=True)
    with open(path(name), "a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


# --- fetch ------------------------------------------------------------------------------------

def cmd_fetch(args):
    os.makedirs(args.books, exist_ok=True)
    for bid, (num, fname, _) in BOOKS.items():
        dest = os.path.join(args.books, fname)
        if os.path.exists(dest):
            print(f"{bid:13} present  {dest}")
            continue
        if num is None:
            print(f"{bid:13} MISSING  {dest} (local file, not on Gutenberg)")
            continue
        data = None
        # gutenberg.org rate-limits scripts (503, retry-after 6 h); the PGLAF mirror is official
        for url in (f"https://www.gutenberg.org/cache/epub/{num}/pg{num}.epub",
                    f"https://gutenberg.pglaf.org/cache/epub/{num}/pg{num}.epub"):
            req = urllib.request.Request(url, headers={"User-Agent": "epub-eval-script/1.0"})
            try:
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except urllib.error.HTTPError as e:
                print(f"{bid:13} {e.code} from {url}")
        if data is None:
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print(f"{bid:13} fetched  {len(data) / 1e6:.1f} MB  title: {epub_title(dest)}")
        time.sleep(2)  # be polite to gutenberg.org


# --- EPUB -> sections -> segments (the plugin's rules) -----------------------------------------

def epub_title(file):
    z = zipfile.ZipFile(file)
    opf = opf_path(z)
    root = ET.fromstring(z.read(opf))
    t = root.find(".//{http://purl.org/dc/elements/1.1/}title")
    return t.text if t is not None else "?"


def opf_path(z):
    root = ET.fromstring(z.read("META-INF/container.xml"))
    return root.find(".//{*}rootfile").get("full-path")


def spine_files(z):
    """The spine in order (linear='no' included, like Foliate and rbook)."""
    opf = opf_path(z)
    root = ET.fromstring(z.read(opf))
    manifest = {i.get("id"): i.get("href") for i in root.iter("{http://www.idpf.org/2007/opf}item")}
    base = posixpath.dirname(opf)
    out = []
    for ref in root.iter("{http://www.idpf.org/2007/opf}itemref"):
        href = manifest.get(ref.get("idref"))
        if href:
            out.append(posixpath.normpath(posixpath.join(base, urllib.parse.unquote(href))))
    return out


class Paragraphs(HTMLParser):
    """<body> -> [(text, is_heading)], one per block element; <br> is a boundary too."""

    def __init__(self):
        super().__init__()
        self.out, self.buf, self.skip, self.heading, self.body = [], [], 0, 0, False

    def flush(self):
        text = " ".join("".join(self.buf).split())
        if text:
            self.out.append((text, self.heading > 0))
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.body = True
        if tag in ("script", "style"):
            self.skip += 1
        if tag in BLOCKS:
            self.flush()
        if tag in HEADINGS:
            self.heading += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        if tag in BLOCKS:
            self.flush()
        if tag in HEADINGS:
            self.heading = max(0, self.heading - 1)

    def handle_data(self, data):
        if self.body and not self.skip:
            self.buf.append(data)


def segment_section(paras):
    """Greedy, on paragraph boundaries: a new segment if the next paragraph would push it over
    MAX_WORDS and it has MIN_WORDS, or at a heading once it has HEADING_MIN words; a tail under
    MIN_WORDS merges into the previous segment."""
    segs, cur, n = [], [], 0
    for text, heading in paras:
        w = len(text.split())
        if cur and ((n + w > MAX_WORDS and n >= MIN_WORDS) or (heading and n >= HEADING_MIN)):
            segs.append(cur)
            cur, n = [], 0
        cur.append(text)
        n += w
    if cur:
        if segs and n < MIN_WORDS:
            segs[-1] += cur
        else:
            segs.append(cur)
    return segs


def book_segments(file):
    z = zipfile.ZipFile(file)
    out = []
    for si, name in enumerate(spine_files(z)):
        try:
            raw = z.read(name).decode("utf-8", "replace")
        except KeyError:
            continue
        p = Paragraphs()
        p.feed(raw)
        p.flush()
        for paras in segment_section(p.out):
            out.append({"section": si, "paragraphs": paras})
    return out


def eligible(seg):
    """Leave out the Gutenberg licence / header and lists (tables of contents, indexes)."""
    text = " ".join(seg["paragraphs"])
    if re.search(r"gutenberg", text, re.I):
        return False
    lens = sorted(len(p.split()) for p in seg["paragraphs"])
    return len(text.split()) >= MIN_WORDS // 2 and lens[len(lens) // 2] >= 8


def cmd_segments(args):
    if os.path.exists(path("segments.jsonl")):
        sys.exit("data/segments.jsonl exists; delete it to resample (labels refer to its ids)")
    for bid, (_, fname, _) in BOOKS.items():
        segs = book_segments(os.path.join(args.books, fname))
        ok = [(i, s) for i, s in enumerate(segs) if eligible(s)]
        k = min(PER_BOOK, len(ok))
        picked = [ok[int((j + 0.5) * len(ok) / k)] for j in range(k)]
        sizes = sorted(len(" ".join(s["paragraphs"]).split()) for _, s in ok)
        print(f"{bid:13} {len(segs):4} segments, {len(ok):4} eligible, words median {sizes[len(sizes) // 2]} "
              f"max {sizes[-1]}; sampled {k}")
        for i, s in picked:
            text = " ".join(s["paragraphs"])
            append_jsonl("segments.jsonl", {"id": f"{bid}-{i:04d}", "book": bid, "seg_index": i,
                                            "section": s["section"], "words": len(text.split()),
                                            "text": text})


def segments():
    segs = read_jsonl("segments.jsonl")
    if not segs:
        sys.exit("no data/segments.jsonl; run `segments` first")
    return segs


# --- label (Qwen3-4B) -------------------------------------------------------------------------

def validate(obj):
    import llm_probe
    ok = all(isinstance(obj.get(k), int) and 1 <= obj[k] <= 5 for k in ("valence", "arousal", "tension"))
    tags = obj.get("tags")
    return ok and isinstance(tags, list) and 1 <= len(tags) <= 3 and all(t in llm_probe.TAGS for t in tags)


def cmd_label(args):
    import llm_probe
    llm_probe.SERVER = args.server.rstrip("/") + "/v1/chat/completions"
    try:
        urllib.request.urlopen(args.server.rstrip("/") + "/health", timeout=10)
    except Exception as e:
        sys.exit(f"llama-server not reachable at {args.server}: {e}")
    done = {r["id"] for r in read_jsonl("qwen.jsonl")}
    todo = [s for s in segments() if s["id"] not in done][:args.limit]
    print(f"{len(done)} done, {len(todo)} to go", flush=True)
    for n, s in enumerate(todo, 1):
        result = {"id": s["id"], "valid": False}
        for attempt in range(1, 3):  # validation + one retry, like the plugin plan
            try:
                resp, wall = llm_probe.ask(s["text"])
                obj = json.loads(resp["choices"][0]["message"]["content"])
                result.update(obj, seconds=round(wall, 1), attempts=attempt,
                              prompt_tokens=resp.get("timings", {}).get("prompt_n"))
                if validate(obj):
                    result["valid"] = True
                    break
            except Exception as e:  # context overflow, timeout, invalid JSON
                result["error"] = str(e)[:300]
        append_jsonl("qwen.jsonl", result)
        print(f"[{n}/{len(todo)}] {s['id']} {s['words']}w valid={result['valid']} "
              f"V{result.get('valence')} A{result.get('arousal')} T{result.get('tension')} "
              f"{result.get('tags')} {result.get('seconds')}s", flush=True)


# --- score (PERT + EmoLit, sentence level) ----------------------------------------------------

def cmd_score(args):
    import torch
    import encoders as enc
    from sentences import split_sentences
    try:
        urllib.request.urlopen(args.server.rstrip("/") + "/health", timeout=3)
        sys.exit("llama-server is running; stop it first (pkill llama-server), memory is too tight")
    except Exception:
        pass
    torch.set_num_threads(enc.THREADS)
    segs = segments()
    for name in args.models:
        out = path(f"sent_{name}.csv")
        done = set()
        if os.path.exists(out):
            with open(out, newline="") as f:
                done = {r["unit"] for r in csv.DictReader(f)}
        todo = [s for s in segs if s["id"] not in done][:args.limit]
        if not todo:
            print(f"[{name}] all {len(segs)} segments scored")
            continue
        t0 = time.perf_counter()
        model = enc.load(name)
        print(f"[{name}] loaded in {time.perf_counter() - t0:.0f}s; {len(todo)} segments to go", flush=True)
        new = not os.path.exists(out)
        with open(out, "a", newline="") as f:
            w = None
            for n, s in enumerate(todo, 1):
                sents = [x for p in s["text"].split("\n") for x in split_sentences(p)]
                t1 = time.perf_counter()
                scored = model(sents)
                dt = time.perf_counter() - t1
                rows = []
                pos = 0
                for j, (text, (raw, trunc)) in enumerate(zip(sents, scored)):
                    rows.append({"kind": "passage", "unit": s["id"], "idx": j, "word_start": pos,
                                 "words": len(text.split()), "truncated": int(trunc),
                                 **{k: round(v, 5) for k, v in enc.derived(name, raw).items()},
                                 **{f"raw:{k}": round(v, 5) for k, v in raw.items()},
                                 "seconds": round(dt, 2) if j == 0 else ""})
                    pos += len(text.split())
                if w is None:
                    w = csv.DictWriter(f, fieldnames=list(rows[0]))
                    if new:
                        w.writeheader()
                w.writerows(rows)
                f.flush()
                print(f"[{name}] [{n}/{len(todo)}] {s['id']} {len(sents)} sentences {dt:.1f}s", flush=True)


# --- hand-label sheet -------------------------------------------------------------------------

def cmd_handsheet(args):
    if os.path.exists(path("hand_labels.csv")):
        sys.exit("data/hand_labels.csv exists; not overwriting your labels")
    picked = []
    for bid in BOOKS:
        segs = [s for s in segments() if s["book"] == bid]
        k = min(HAND_PER_BOOK, len(segs))
        picked += [segs[int((j + 0.5) * len(segs) / k)] for j in range(k)]
    with open(path("hand_labels.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "valence", "arousal", "tension", "note"])
        for s in picked:
            w.writerow([s["id"], "", "", "", ""])
    with open(path("hand_labels.md"), "w") as f:
        f.write("# Hand labels (blind)\n\nRate each segment 1-5 on the Qwen prompt's scales, into "
                "hand_labels.csv. Do not look at qwen.jsonl or the model scores before finishing.\n\n"
                "- valence: 1 grief/despair/horror, 2 sad/gloomy, 3 neutral/mixed, 4 pleasant/warm/amusing, 5 joyful\n"
                "- arousal: 1 still, 2 quiet/reflective, 3 moderate, 4 lively/agitated, 5 frantic/violent action\n"
                "- tension: 1 relaxed/safe, 2 slight unease, 3 noticeable suspense, 4 strong threat, 5 extreme danger/climax\n\n")
        for s in picked:
            f.write(f"## {s['id']} ({s['words']} words)\n\n{s['text']}\n\n")
    print(f"{len(picked)} segments -> data/hand_labels.csv, data/hand_labels.md")


# --- evaluate ---------------------------------------------------------------------------------

def cmd_evaluate(args):
    import numpy as np
    import aggregate as ag
    import metrics as mt

    segs = {s["id"]: s for s in segments()}
    qwen = {r["id"]: r for r in read_jsonl("qwen.jsonl") if r.get("valid")}
    hand = {}
    if os.path.exists(path("hand_labels.csv")):
        hand = {r["id"]: {d: int(r[k]) for d, k in zip("VAT", ("valence", "arousal", "tension"))}
                for r in mt.read_csv(path("hand_labels.csv")) if r["valence"] and r["arousal"] and r["tension"]}
    rows = {m: mt.read_csv(path(f"sent_{m}.csv")) for m in ("pert", "emolit")
            if os.path.exists(path(f"sent_{m}.csv"))}
    if set(rows) != {"pert", "emolit"}:
        sys.exit("run `score` first (needs sent_pert.csv and sent_emolit.csv)")

    ids = [i for i in segs if i in qwen and all(any(r["unit"] == i for r in rows[m]) for m in rows)]
    print(f"{len(segs)} segments, {len(qwen)} valid Qwen labels, {len(ids)} usable, "
          f"{len(hand)} hand-labelled\n")

    # features: 5 aggregates of pert.V, pert.A, emolit.T (quartile cuts pooled over all segments)
    feats = {}
    for col, (m, d) in {"pert.V": ("pert", "V"), "pert.A": ("pert", "A"), "emolit.T": ("emolit", "T")}.items():
        cuts = ag.pooled_cuts(rows[m], d)
        by = {}
        for r in rows[m]:
            by.setdefault(r["unit"], []).append(r)
        for a in ag.AGGS:
            feats[f"{col}:{a}"] = np.array([ag.aggregate(by[i], d, cuts)[a] for i in ids])
    names = list(feats)
    X_all = np.column_stack([feats[k] for k in names])
    books = np.array([segs[i]["book"] for i in ids])

    def ridge(Xtr, ytr, alpha):
        mu, sd = Xtr.mean(0), Xtr.std(0)
        sd[sd == 0] = 1
        Z = (Xtr - mu) / sd
        w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (ytr - ytr.mean()))
        return lambda X: ((X - mu) / sd) @ w + ytr.mean()

    def lobo(y, method):
        """Leave one book out: fit on the other books, predict the held-out one."""
        pred = np.zeros(len(y))
        for b in sorted(set(books)):
            tr, te = books != b, books == b
            if method[0] == "single":
                x = feats[method[1]]
                k, c = np.polyfit(x[tr], y[tr], 1)
                pred[te] = k * x[te] + c
            elif method[0] == "best":
                key = max(method[1], key=lambda k: mt.spearman(list(feats[k][tr]), list(y[tr])))
                k, c = np.polyfit(feats[key][tr], y[tr], 1)
                pred[te] = k * feats[key][te] + c
            else:
                pred[te] = ridge(X_all[tr], y[tr], method[1])(X_all[te])
        return pred

    def report(y, pred, label):
        ext = (y == 1) | (y == 5)
        per_book = [mt.spearman(list(pred[books == b]), list(y[books == b])) for b in sorted(set(books))]
        print(f"| {label} | {mt.fmt(mt.spearman(list(pred), list(y)))} | {np.abs(pred - y).mean():.2f} | "
              f"{np.abs(pred - y)[ext].mean() if ext.any() else float('nan'):.2f} ({ext.sum()}) | "
              f"{pred.min():.1f}–{pred.max():.1f} | " + " ".join(f"{r:+.2f}" for r in per_book) + " |")

    targets = [("Qwen", {i: {d: qwen[i][k] for d, k in zip("VAT", ("valence", "arousal", "tension"))} for i in ids})]
    if hand:
        targets.append(("hand", hand))
    for tname, tgt in targets:
        sel = np.array([i in tgt for i in ids])
        print(f"## Target: {tname} ({sel.sum()} segments), leave-one-book-out\n")
        print("| Dim / method | rho | MAE | MAE on 1s and 5s (n) | prediction range | rho per book "
              f"({', '.join(sorted(set(books)))}) |")
        print("|---|---|---|---|---|---|")
        for d in "VAT":
            y = np.array([tgt[i][d] if i in tgt else np.nan for i in ids], dtype=float)
            if tname == "Qwen":
                col, agg = METHODS[d]
                own = [k for k in names if k.startswith({"V": "pert.V", "A": "pert.A", "T": "emolit.T"}[d])]
                methods = [(f"{d} fixed: {col} {agg}", ("single", f"{col}:{agg}")),
                           (f"{d} per-fold best aggregate", ("best", own)),
                           (f"{d} ridge, all 15 (alpha 5)", ("ridge", 5.0))]
                if d == "T":
                    methods.append(("T shortcut: pert.A high", ("single", "pert.A:high")))
                for label, mth in methods:
                    report(y, lobo(y, mth), label)
            else:  # hand labels: calibrate on Qwen of the other books, test on hand labels
                yq = np.array([qwen[i][{"V": "valence", "A": "arousal", "T": "tension"}[d]] for i in ids], float)
                col, agg = METHODS[d]
                pred = lobo(yq, ("single", f"{col}:{agg}"))
                report(y[sel], pred[sel], f"{d} fixed {col} {agg} (fit on Qwen)")
                report(y[sel], yq[sel], f"{d} Qwen itself")
        print()

    # where arousal and tension diverge (the scenes tension is for)
    q = {i: (qwen[i]["arousal"], qwen[i]["tension"]) for i in ids}
    div = np.array([abs(q[i][0] - q[i][1]) >= 2 for i in ids])
    yT = np.array([q[i][1] for i in ids], float)
    print(f"## Tension where Qwen's arousal and tension differ by >= 2 ({div.sum()} segments)\n")
    print("| Method | rho | MAE |\n|---|---|---|")
    for label, mth in (("emolit.T high", ("single", "emolit.T:high")),
                       ("shortcut pert.A high", ("single", "pert.A:high")),
                       ("ridge, all 15", ("ridge", 5.0))):
        p = lobo(yT, mth)
        if div.sum() >= 5:
            print(f"| {label} | {mt.fmt(mt.spearman(list(p[div]), list(yT[div])))} | {np.abs(p - yT)[div].mean():.2f} |")

    # tags: EmoLit through TAG_MAP vs Qwen's tags, average precision
    by = {}
    for r in rows["emolit"]:
        by.setdefault(r["unit"], []).append(r)
    print("\n## Tags: EmoLit (mapped) vs. Qwen's tags, average precision over all segments\n")
    print("| Tag | Qwen uses it | chance | AP mean | AP p90 |\n|---|---|---|---|---|")
    aps = []
    for tag, emos in TAG_MAP.items():
        pos = {i for i in ids if tag in qwen[i]["tags"]}
        if len(pos) < 5:
            continue
        sc_mean, sc_p90 = {}, {}
        for i in ids:
            vals = [sum(float(r[f"raw:{e}"]) for e in emos) for r in by[i]]
            w = [int(r["words"]) for r in by[i]]
            sc_mean[i] = sum(v * x for v, x in zip(vals, w)) / sum(w)
            sc_p90[i] = ag.quantile(vals, 0.9)
        a1, a2 = mt.average_precision(sc_mean, pos), mt.average_precision(sc_p90, pos)
        aps.append((len(pos) / len(ids), a1, a2))
        print(f"| {tag} | {len(pos)} | {len(pos) / len(ids):.2f} | {a1:.2f} | {a2:.2f} |")
    if aps:
        print(f"| **macro** | | {np.mean([a[0] for a in aps]):.2f} | **{np.mean([a[1] for a in aps]):.2f}** | "
              f"**{np.mean([a[2] for a in aps]):.2f}** |")

    secs = [float(r["seconds"]) for m in rows for r in rows[m] if r["seconds"]]
    qs = [qwen[i]["seconds"] for i in ids if qwen[i].get("seconds")]
    print(f"\nSpeed: PERT+EmoLit {sum(secs) / len(ids):.1f} s/segment, Qwen {np.median(qs):.0f} s/segment (median)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["fetch", "segments", "label", "score", "handsheet", "evaluate"])
    ap.add_argument("--books", default=DEFAULT_BOOKS, help="folder of the EPUBs (default: %(default)s)")
    ap.add_argument("--server", default="http://127.0.0.1:8080", help="llama-server base URL")
    ap.add_argument("--models", nargs="+", default=["pert", "emolit"], help="for `score`")
    ap.add_argument("--limit", type=int, default=None, help="label/score at most this many (smoke test)")
    args = ap.parse_args()
    {"fetch": cmd_fetch, "segments": cmd_segments, "label": cmd_label, "score": cmd_score,
     "handsheet": cmd_handsheet, "evaluate": cmd_evaluate}[args.step](args)


if __name__ == "__main__":
    main()
