"""Moby Dick EPUB -> paragraphs, and passage cutting by a starting phrase.

The extraction is the same as in ../qwen3-llamacpp/llm_probe.py (blocks -> paragraphs,
normalized whitespace), so the passages match the earlier LLM probe.
"""
import re
import zipfile
from html.parser import HTMLParser


class Text(HTMLParser):
    BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "br"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def paragraphs(path):
    z = zipfile.ZipFile(path)
    names = sorted(n for n in z.namelist() if re.search(r"\.x?html?$", n))
    out = []
    for n in names:
        p = Text()
        p.feed(z.read(n).decode("utf-8", "replace"))
        out.append("".join(p.parts))
    paras = [" ".join(x.split()) for x in "\n".join(out).split("\n")]
    return [x for x in paras if x]


BLOCK_MARK = "\x00"


class Blocks(Text):
    """Like Text, but marks block boundaries instead of newlines (the Gutenberg XHTML has hard
    line breaks inside <p>, which `paragraphs` turns into separate 'paragraphs')."""

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag in self.BLOCKS:
            self.parts[-1] = BLOCK_MARK

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag in self.BLOCKS:
            self.parts[-1] = BLOCK_MARK


def block_paragraphs(path):
    """Real paragraphs (one per block element), whitespace-normalized; for sentence splitting."""
    z = zipfile.ZipFile(path)
    names = sorted(n for n in z.namelist() if re.search(r"\.x?html?$", n))
    out = []
    for n in names:
        p = Blocks()
        p.feed(z.read(n).decode("utf-8", "replace"))
        out.append("".join(p.parts))
    paras = [" ".join(x.split()) for x in BLOCK_MARK.join(out).split(BLOCK_MARK)]
    return [x for x in paras if x]


def start_index(paras, start):
    """First paragraph beginning with `start` (or containing it, for mid-paragraph phrases).

    In the tables of contents the next paragraph is another chapter title, so those are skipped.
    """
    for i, p in enumerate(paras[:-1]):
        if p.startswith(start) and not paras[i + 1].startswith("CHAPTER"):
            return i, 0
    for i, p in enumerate(paras):
        k = p.find(start)
        if k > 0:
            return i, k
    raise KeyError(start)


def words_from(paras, start, n):
    """The first `n` words from `start`, cut on a word (not paragraph) boundary.

    A chapter heading is left out: the title (e.g. "Queequeg in His Coffin") would leak a label.
    """
    i, k = start_index(paras, start)
    if paras[i].startswith("CHAPTER"):
        i, k = i + 1, 0
    words = paras[i][k:].split()
    for p in paras[i + 1:]:
        if len(words) >= n:
            break
        words += p.split()
    return " ".join(words[:n])


def windows(paras, start, size, count):
    """`count` consecutive, non-overlapping windows of `size` words from `start`."""
    text = words_from(paras, start, size * count).split()
    return [" ".join(text[j * size:(j + 1) * size]) for j in range(count)]
