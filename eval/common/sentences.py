"""Rule-based sentence splitting for the sentence-level encoder models.

Copied from eval/literary-tone/sentence_probe.py (the SENT experiment), unchanged, so the
labelling scripts do not depend on an experiment folder.
"""
import re

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
