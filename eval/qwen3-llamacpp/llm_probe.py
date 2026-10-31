"""Quick probe: Moby Dick passages -> llama-server (JSON schema) -> timings + output.

The prompt and schema are the final (4th) version of RESULTS.md.
Needs a running llama-server on 127.0.0.1:8080; standard library only.

Usage: python3 llm_probe.py <moby_dick.epub>
"""
import json
import re
import sys
import time
import urllib.request
import zipfile
from html.parser import HTMLParser

SERVER = "http://127.0.0.1:8080/v1/chat/completions"
# tag -> short definition, shown to the model
TAG_DEFS = {
    "calm": "peaceful, nothing is happening",
    "cheerful": "light, happy, good spirits",
    "humorous": "comic, ironic, playful",
    "tender": "affection, friendship, intimacy",
    "melancholic": "wistful sadness, longing",
    "grief": "loss, mourning, death of someone close",
    "solemn": "grave, dignified, religious or ceremonial",
    "mysterious": "the unknown, enigma, the uncanny; not merely dark",
    "ominous": "foreboding, a sense that something bad will happen",
    "fear": "characters are afraid, terror",
    "suspense": "uncertain outcome, the reader holds their breath",
    "anger": "rage, defiance, hostility",
    "violence": "physical struggle, killing, injury",
    "chaos": "confusion, disorder, things falling apart",
    "triumph": "victory, exultation, pride",
    "contemplative": "reflection, philosophy, inner thought",
}
TAGS = list(TAG_DEFS)
# start of the passage (chapter heading or a phrase) -> why it is in the probe
PASSAGES = {
    "CHAPTER 3. The Spouter-Inn.": "dark painting, then comic",
    "CHAPTER 93. The Castaway.": "Pip: sad, horror",
    "CHAPTER 119. The Candles.": "storm: tense",
    "CHAPTER 94. A Squeeze of the Hand.": "blissful, happy",
    "CHAPTER 10. A Bosom Friend.": "warm, calm",
    "CHAPTER 132. The Symphony.": "tender, melancholic",
    "Almost simultaneously, with a mighty volition": "Ch. 135 catastrophe: frantic",
}
WORDS = 700
SCALE = {"enum": [1, 2, 3, 4, 5]}

SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string", "maxLength": 400},
        "valence": SCALE,
        "arousal": SCALE,
        "tension": SCALE,
        "tags": {"type": "array", "items": {"enum": TAGS}, "minItems": 1, "maxItems": 3},
    },
    "required": ["rationale", "valence", "arousal", "tension", "tags"],
    "additionalProperties": False,
}

SYSTEM = (
    "You rate the mood of a passage from a novel, to drive adaptive background music. "
    "Judge the emotional atmosphere the reader experiences, not the plot. "
    "Rate each scale with an integer from 1 to 5:\n"
    "valence: 1 = grief, despair, horror; 2 = sad, gloomy, unpleasant; 3 = neutral or mixed; "
    "4 = pleasant, warm, affectionate, amusing; 5 = joyful, elated.\n"
    "arousal: 1 = still, sleepy; 2 = quiet, reflective; 3 = moderate activity; "
    "4 = lively, agitated; 5 = frantic, violent action.\n"
    "tension: 1 = relaxed, safe; 2 = slight unease; 3 = noticeable suspense; "
    "4 = strong suspense or threat; 5 = extreme danger, climax.\n"
    "Calibration: most passages of a novel sit in the middle of the scales (2-4). "
    "Use 1 or 5 only when the passage clearly and strongly calls for it, "
    "and rate each scale independently of the others.\n"
    "tags: the 1-3 tags that best describe the dominant feeling, from this list only:\n"
    + "".join(f"- {t}: {d}\n" for t, d in TAG_DEFS.items())
    + "rationale: one sentence of at most 20 words. Answer with JSON only."
)

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


def book_text(path):
    z = zipfile.ZipFile(path)
    names = sorted(n for n in z.namelist() if re.search(r"\.x?html?$", n))
    out = []
    for n in names:
        p = Text()
        p.feed(z.read(n).decode("utf-8", "replace"))
        out.append("".join(p.parts))
    paragraphs = [" ".join(x.split()) for x in "\n".join(out).split("\n")]
    return [x for x in paragraphs if x]


def passage(paragraphs, heading):
    # In the tables of contents the next paragraph is another chapter title.
    start = next(
        i for i, p in enumerate(paragraphs[:-1])
        if p.startswith(heading) and not paragraphs[i + 1].startswith("CHAPTER")
    )
    words, out = 0, []
    for p in paragraphs[start:]:
        out.append(p)
        words += len(p.split())
        if words >= WORDS:
            break
    return " ".join(out)


def ask(text):
    body = {
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}],
        "temperature": 0,
        "seed": 42,
        "max_tokens": 300,
        "response_format": {"type": "json_schema", "json_schema": {"name": "mood", "schema": SCHEMA}},
    }
    req = urllib.request.Request(SERVER, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.perf_counter()
    resp = json.load(urllib.request.urlopen(req, timeout=1800))
    return resp, time.perf_counter() - t0


def main():
    paragraphs = book_text(sys.argv[1])
    for heading, note in PASSAGES.items():
        text = passage(paragraphs, heading)
        resp, wall = ask(text)
        t = resp.get("timings", {})
        content = resp["choices"][0]["message"]["content"]
        print(f"=== {heading} ({note}), {len(text.split())} words")
        print(f"wall {wall:.1f}s | prompt {t.get('prompt_n')} tok in {t.get('prompt_ms', 0)/1000:.1f}s "
              f"({t.get('prompt_per_second', 0):.1f} tok/s) | output {t.get('predicted_n')} tok in "
              f"{t.get('predicted_ms', 0)/1000:.1f}s ({t.get('predicted_per_second', 0):.1f} tok/s)")
        try:
            print(json.dumps(json.loads(content), ensure_ascii=False))
        except json.JSONDecodeError:
            print("INVALID JSON:", content)
        sys.stdout.flush()


if __name__ == "__main__":
    main()
