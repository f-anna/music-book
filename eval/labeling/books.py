"""The book list of the labelling dataset (LABELING_GUIDE.md §2) and the EPUB download.

Every author and translator died before 1956, so the books are public domain in the EU and the
US. The Gutenberg ids were written from memory: `fetch()` checks each downloaded title against
the expected one, so a wrong id is caught instead of labelling the wrong book.

Test set (changed 2026-11-25, before anything was scored or labelled): Three Men in a Boat (comedy)
and Anne of Green Gables (warm) moved there from train, so the test covers comic and warm moods
too, not only dark and tense ones. The Adventures of Sherlock Holmes was dropped: a second Conan
Doyle in test was redundant, and in train it would put an author in both splits.
"""
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

# key, Gutenberg id (None = local file only), file name, expected title, author, died, split
BOOKS = [
    # train
    ("pride", 1342, "pg1342-pride-and-prejudice.epub", "Pride and Prejudice", "Jane Austen", 1817, "train"),
    ("emma", 158, "pg158-emma.epub", "Emma", "Jane Austen", 1817, "train"),
    ("janeeyre", 1260, "pg1260-jane-eyre.epub", "Jane Eyre", "Charlotte Brontë", 1855, "train"),
    ("wuthering", 768, "pg768-wuthering-heights.epub", "Wuthering Heights", "Emily Brontë", 1848, "train"),
    ("dracula", 345, "pg345-dracula.epub", "Dracula", "Bram Stoker", 1912, "train"),
    ("jekyll", 43, "pg43-jekyll-and-hyde.epub", "Jekyll", "Robert Louis Stevenson", 1894, "train"),
    ("treasure", 120, "pg120-treasure-island.epub", "Treasure Island", "Robert Louis Stevenson", 1894, "train"),
    ("twocities", 98, "pg98-a-tale-of-two-cities.epub", "Tale of Two Cities", "Charles Dickens", 1870, "train"),
    ("expectations", 1400, "pg1400-great-expectations.epub", "Great Expectations", "Charles Dickens", 1870, "train"),
    ("doriangray", 174, "pg174-dorian-gray.epub", "Dorian Gray", "Oscar Wilde", 1900, "train"),
    ("huckfinn", 76, "pg76-huckleberry-finn.epub", "Huckleberry Finn", "Mark Twain", 1910, "train"),
    ("timemachine", 35, "pg35-the-time-machine.epub", "Time Machine", "H. G. Wells", 1946, "train"),
    ("worlds", 36, "pg36-war-of-the-worlds.epub", "War of the Worlds", "H. G. Wells", 1946, "train"),
    ("darkness", 219, "pg219-heart-of-darkness.epub", "Heart of Darkness", "Joseph Conrad", 1924, "train"),
    ("montecristo", 1184, "pg1184-monte-cristo.epub", "Monte Cristo", "Alexandre Dumas (anon. transl.)", 1870, "train"),
    ("littlewomen", 514, "pg514-little-women.epub", "Little Women", "Louisa May Alcott", 1888, "train"),
    ("callwild", 215, "pg215-call-of-the-wild.epub", "Call of the Wild", "Jack London", 1916, "train"),
    ("tess", 110, "pg110-tess.epub", "Tess of the d'Urbervilles", "Thomas Hardy", 1928, "train"),
    ("redbadge", 73, "pg73-red-badge-of-courage.epub", "Red Badge of Courage", "Stephen Crane", 1900, "train"),
    ("screw", 209, "pg209-turn-of-the-screw.epub", "Turn of the Screw", "Henry James", 1916, "train"),
    ("willows", 289, "pg289-wind-in-the-willows.epub", "Wind in the Willows", "Kenneth Grahame", 1932, "train"),
    ("solomon", 2166, "pg2166-king-solomons-mines.epub", "King Solomon's Mines", "H. Rider Haggard", 1925, "train"),
    # validation
    ("frankenstein", 84, "pg84-frankenstein.epub", "Frankenstein", "Mary Shelley", 1851, "validation"),
    ("silasmarner", 550, "pg550-silas-marner.epub", "Silas Marner", "George Eliot", 1880, "validation"),
    ("pimpernel", 60, "pg60-scarlet-pimpernel.epub", "Scarlet Pimpernel", "Baroness Orczy", 1947, "validation"),
    # test
    ("moby", None, "moby_dick.epub", "Moby", "Herman Melville", 1891, "test"),
    ("baskervilles", 2852, "pg2852-hound-of-the-baskervilles.epub", "Hound of the Baskervilles", "Arthur Conan Doyle", 1930, "test"),
    ("phantom", 175, "pg175-phantom-of-the-opera.epub", "Phantom of the Opera", "Gaston Leroux (transl. A. Teixeira de Mattos)", 1927, "test"),
    ("threemen", 308, "pg308-three-men-in-a-boat.epub", "Three Men in a Boat", "Jerome K. Jerome", 1927, "test"),
    ("greengables", 45, "pg45-anne-of-green-gables.epub", "Anne of Green Gables", "L. M. Montgomery", 1942, "test"),
]
FIELDS = ["key", "gutenberg", "file", "title", "author", "died", "split"]


def books():
    return [dict(zip(FIELDS, b)) for b in BOOKS]


def epub_title(path):
    z = zipfile.ZipFile(path)
    root = ET.fromstring(z.read("META-INF/container.xml"))
    opf = root.find(".//{*}rootfile").get("full-path")
    t = ET.fromstring(z.read(opf)).find(".//{http://purl.org/dc/elements/1.1/}title")
    return t.text if t is not None and t.text else "?"


def title_ok(expected, found):
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", s.lower().replace("’", "'")).strip()
    return norm(expected) in norm(found)


def fetch(book_dir, log=print):
    """Download the missing EPUBs (Gutenberg cache, then the official PGLAF mirror) and check
    every title. -> {key: (status, title found)}; status: ok / title-mismatch / missing."""
    os.makedirs(book_dir, exist_ok=True)
    out = {}
    for b in books():
        dest = os.path.join(book_dir, b["file"])
        if not os.path.exists(dest) and b["gutenberg"] is not None:
            num, data = b["gutenberg"], None
            # gutenberg.org rate-limits scripts (503, retry-after hours); the PGLAF mirror is official
            for url in (f"https://www.gutenberg.org/cache/epub/{num}/pg{num}.epub",
                        f"https://gutenberg.pglaf.org/cache/epub/{num}/pg{num}.epub"):
                req = urllib.request.Request(url, headers={"User-Agent": "epub-eval-script/1.0"})
                try:
                    data = urllib.request.urlopen(req, timeout=120).read()
                    break
                except (urllib.error.URLError, TimeoutError) as e:
                    log(f"{b['key']:13} {getattr(e, 'code', e)} from {url}")
            if data is not None:
                with open(dest, "wb") as f:
                    f.write(data)
                log(f"{b['key']:13} fetched {len(data) / 1e6:.1f} MB")
                time.sleep(2)  # be polite to gutenberg.org
        if not os.path.exists(dest):
            out[b["key"]] = ("missing", None)
            continue
        found = epub_title(dest)
        out[b["key"]] = ("ok" if title_ok(b["title"], found) else "title-mismatch", found)
    return out
