"""EPUB -> segments, with the plugin's rules (crates/tauri-plugin-soundtrack/src/epub.rs).

A Python copy of the Rust code, checked against it on Moby Dick (`MOBY_PLUGIN`): the plugin gives
347 segments and 215,845 words. Paragraph extraction follows `extract_paragraphs` /
`collect_blocks` (block elements close a paragraph, headings are marked, script/style skipped);
segmentation follows `segment_paragraphs` (greedy on paragraph boundaries, a heading starts a new
segment once the current one has 100 words, a short tail merges back unless it starts with a
heading). Every spine item gets an index (`linear="no"` too), like Foliate and rbook; non-HTML
items are empty sections.

On top of the plugin's cuts, for the models only (LABELING_GUIDE.md §3):
- heading paragraphs are removed from the model input (kept in `headings`): a chapter title can
  give the mood away;
- illustration captions and footnote markers are stripped;
- Gutenberg licence, tables of contents and indexes are left out (`eligible`).

Standard library only.
"""
import json
import os
import posixpath
import re
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

MIN_WORDS, MAX_WORDS, MIN_WORDS_BEFORE_HEADING = 300, 800, 100
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
BLOCKS = {"p", "div", "li", "blockquote", "pre", "dt", "dd", "td", "th", "tr", "table",
          "figcaption", "section", "article", "header", "footer", "aside", "br", "hr"}
VOID = {"br", "hr", "img", "meta", "link", "input", "wbr", "col", "area", "base", "embed",
        "source", "track", "param"}
MOBY_PLUGIN = (347, 215845)  # segments, words: the plugin's numbers (CLAUDE.md, milestone 2)

PER_BOOK_TRAIN = 120             # evenly spaced segments per train book
GOLD = {"validation": 100, "test": 150}  # gold segments per split, shared evenly by its books

ILLUSTRATION = re.compile(r"\[\s*Illustration[^\]]*\]", re.I)
FOOTNOTE = re.compile(r"\[\s*(?:\d{1,3}|[a-z]|[*†‡])\s*\]")


# --- EPUB -> paragraphs -----------------------------------------------------------------------

class Paragraphs(HTMLParser):
    """<body> -> [(text, is_heading)], like collect_blocks() in epub.rs."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.buf, self.stack, self.body, self.skip = [], [], [], False, 0

    def _flush(self, heading):
        text = " ".join("".join(self.buf).split())
        self.buf = []
        if text:
            self.out.append((text, heading))

    def _in_heading(self):
        return self.stack[-1][1] if self.stack else False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.body = True
            return
        if not self.body:
            return
        if tag in ("script", "style"):
            self.skip += 1
            self.stack.append((tag, self._in_heading(), False))
            return
        parent = self._in_heading()
        heading = parent or tag in HEADINGS
        block = heading or tag in BLOCKS
        if block:
            self._flush(parent)
        self.stack.append((tag, heading, block))
        if tag in VOID:
            self.handle_endtag(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "body":
            self.close_all()
            self.body = False
            return
        if not any(t == tag for t, _, _ in self.stack):
            return  # a stray end tag
        while self.stack:
            t, heading, block = self.stack.pop()
            if t in ("script", "style"):
                self.skip -= 1
            elif block:
                self._flush(heading)
            if t == tag:
                break

    def handle_data(self, data):
        if self.body and not self.skip:
            self.buf.append(data)

    def close_all(self):
        while self.stack:
            t, heading, block = self.stack.pop()
            if block and t not in ("script", "style"):
                self._flush(heading)
        self._flush(False)


def spine(z):
    """[(href, is_html)] in spine order; itemrefs missing from the manifest are skipped."""
    root = ET.fromstring(z.read("META-INF/container.xml"))
    opf = root.find(".//{*}rootfile").get("full-path")
    pkg = ET.fromstring(z.read(opf))
    ns = "{http://www.idpf.org/2007/opf}"
    manifest = {i.get("id"): (i.get("href"), i.get("media-type") or "") for i in pkg.iter(f"{ns}item")}
    base = posixpath.dirname(opf)
    out = []
    for ref in pkg.iter(f"{ns}itemref"):
        item = manifest.get(ref.get("idref"))
        if item and item[0]:
            href = posixpath.normpath(posixpath.join(base, urllib.parse.unquote(item[0])))
            out.append((href, "html" in item[1]))
    return out


def section_paragraphs(z, href, is_html):
    if not is_html:
        return []
    try:
        raw = z.read(href).decode("utf-8", "replace")
    except KeyError:
        return []
    p = Paragraphs()
    p.feed(raw)
    p.close()
    p.close_all()
    return p.out


# --- paragraphs -> segments (segment_paragraphs in epub.rs) ------------------------------------

def segment_section(paras):
    """[(text, heading)] -> [(first, end) paragraph ranges]."""
    groups, start, words = [], 0, 0
    for i, (text, heading) in enumerate(paras):
        w = len(text.split())
        cut = i > start and ((heading and words >= MIN_WORDS_BEFORE_HEADING)
                             or (words >= MIN_WORDS and words + w > MAX_WORDS))
        if cut:
            groups.append([start, i, words])
            start, words = i, 0
        words += w
    if start < len(paras):
        if groups and words < MIN_WORDS and not paras[start][1]:
            groups[-1][1] = len(paras)
            groups[-1][2] += words
        else:
            groups.append([start, len(paras), words])
    return groups


def book_segments(path):
    """All segments of a book, in plugin order: [{section, seg_index, plugin_words, paras}]."""
    z = zipfile.ZipFile(path)
    out = []
    for si, (href, is_html) in enumerate(spine(z)):
        paras = section_paragraphs(z, href, is_html)
        for first, end, words in segment_section(paras):
            out.append({"section": si, "seg_index": len(out), "plugin_words": words,
                        "paras": paras[first:end]})
    return out


# --- model input ------------------------------------------------------------------------------

def clean(text):
    text = ILLUSTRATION.sub(" ", text)
    text = FOOTNOTE.sub("", text)
    return " ".join(text.split())


CAPTION = re.compile(r"^\[?\s*Illustrations?\b", re.I)  # a caption as its own paragraph


def model_input(seg):
    """-> (paragraphs without headings and captions, cleaned; headings)"""
    paras = [clean(t) for t, h in seg["paras"] if not h and not CAPTION.match(t)]
    return [p for p in paras if p], [t for t, h in seg["paras"] if h]


def eligible(paragraphs):
    """Leave out the Gutenberg licence / header, short leftovers and lists (contents, indexes)."""
    text = " ".join(paragraphs)
    if not paragraphs or re.search(r"gutenberg", text, re.I):
        return False
    lens = sorted(len(p.split()) for p in paragraphs)
    return len(text.split()) >= MIN_WORDS // 2 and lens[len(lens) // 2] >= 8


def evenly(items, k):
    """k items evenly spaced through the list (deterministic)."""
    k = min(k, len(items))
    return [items[int((j + 0.5) * len(items) / k)] for j in range(k)]


# --- the dataset ------------------------------------------------------------------------------

def build(book_list, book_dir):
    """-> (segment records, per-book stats). Train books: PER_BOOK_TRAIN segments each;
    validation / test books: every eligible segment, GOLD of them marked as gold."""
    records, stats = [], []
    per_split = {s: [b for b in book_list if b["split"] == s] for s in GOLD}
    for b in book_list:
        segs = book_segments(os.path.join(book_dir, b["file"]))
        ok = []
        for s in segs:
            paragraphs, headings = model_input(s)
            if eligible(paragraphs):
                ok.append((s, paragraphs, headings))
        if b["split"] == "train":
            picked, gold = evenly(ok, PER_BOOK_TRAIN), set()
        else:
            picked = ok
            n_books = len(per_split[b["split"]])
            share = GOLD[b["split"]] // n_books + (per_split[b["split"]].index(b) < GOLD[b["split"]] % n_books)
            gold = {s["seg_index"] for s, _, _ in evenly(ok, share)}
        for s, paragraphs, headings in picked:
            records.append({
                "id": f"{b['key']}-{s['seg_index']:04d}", "book": b["key"], "split": b["split"],
                "section": s["section"], "seg_index": s["seg_index"],
                "words": sum(len(p.split()) for p in paragraphs), "gold": s["seg_index"] in gold,
                "headings": headings, "paragraphs": paragraphs,
            })
        sizes = sorted(sum(len(p.split()) for p in pp) for _, pp, _ in ok) or [0]
        stats.append({"book": b["key"], "split": b["split"], "segments": len(segs),
                      "plugin_words": sum(s["plugin_words"] for s in segs), "eligible": len(ok),
                      "selected": len(picked), "gold": len(gold), "median_words": sizes[len(sizes) // 2]})
    return records, stats


def write_jsonl(path, records, overwrite=False):
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path} exists; labels refer to its ids. Pass overwrite=True only "
                              "if nothing has been labelled or scored yet.")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]
