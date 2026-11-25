# Labelling guide: passage mood dataset from task-specific models

**Goal:** a training set for a small encoder (MiniLM / ModernBERT) that predicts the plugin's
`MoodAnalysis` (valence, arousal, tension 1–5 + 1–3 tags) for a ~300–800-word novel passage.

**Approach:**
- **Labellers:** existing task-specific encoder models (sentiment / emotion / VAD), alone or
  combined.
- **Checkers:** ChatGPT and Claude only **check** the labellers' quality. Their outputs never go
  into the training data.
- **Ground truth:** hand labels on a gold set.

```
Gutenberg EPUBs ──▶ segments (epub.rs rules)
                       │
                       ├─▶ encoder labellers (C1–C4) ──▶ candidate labels ──┐
                       │                                                    ├─▶ comparison ──▶ best combination
                       ├─▶ hand labels (gold set) ─────────────────────────┤        │
                       └─▶ GPT / Claude ratings (checking only) ────────────┘        ▼
                                                                         full labelling run ──▶ training set
```

Earlier measurements this builds on (16 Moby Dick passages, provisional labels; on the
`literary-tone-eval` branch until it is merged):
[`../literary-tone/RESULTS-E1.md`](../literary-tone/RESULTS-E1.md) (literary tone classifier),
[`../literary-tone/RESULTS-SENT.md`](../literary-tone/RESULTS-SENT.md) (six sentence-level models).

---

## 1. Licences and terms (checked 2026-11-25)

Not legal advice. Re-check before the full run.

### Labeller models: the licence must allow using their outputs

| Model | Licence | Usable as labeller? |
|---|---|---|
| `edsi-umd/PERT-EmoPair` | CC-BY-4.0 | Yes (cite it) |
| `lrei/roberta-large-emolit` | MIT | Yes |
| `susurofu/literary-bert-en-base` / `-large` | Apache-2.0 | Yes |
| `fpianz/sentiment-fiction-seq` | MIT | Yes |
| `chrlukas/stories-emotion-c4` | **none** ("demo only") | **No.** Without a licence there is no permission to build a dataset from it. Thesis comparison only |
| `Mitchins/literary-tone-classifier-v0.1` | MIT per card, none in HF metadata | Unclear, and weak anyway (§4) |

### ChatGPT / Claude: evaluation only

- **Claude**, Usage Policy (effective 2026-11-12): no using outputs *"to train an AI model …
  without prior authorization from Anthropic"*. Evaluating is not training, so it's allowed.
- **OpenAI**, Usage Policies (effective 2026-11-20): restricts outputs used as training material
  only for models that substitute OpenAI's; evaluation and benchmarking are explicitly allowed.
- **Rules that keep this clean:**
  - Use the **APIs**, not the chat apps. The API terms don't let either provider train on your
    inputs; the consumer apps do unless you opt out.
  - GPT/Claude per-segment ratings are **never** used as training labels, to **fit** the
    combination model (C4), or to **filter or correct** training labels. They only produce
    agreement numbers.
  - State in the thesis which models were used for checking, and how.

---

## 2. Books

- **English and public domain in the EU *and* the US:** author and translator died before 1956.
  For example, Agatha Christie's early novels are public domain in the US but **not** in the EU.
- **Varied moods.**
- Download EPUBs from Project Gutenberg (manually or from a mirror, not by scraping the main
  site), and strip the Gutenberg header and footer.
- **Split by book. Moby Dick is test-only:** the v4 prompt and the earlier encoder aggregations
  were tuned on it.

Verify every ID at `https://www.gutenberg.org/ebooks/<id>` before downloading.

### Train (24): labelled by the winning combination, no hand labels

| ID | Title | Author | Main moods |
|---|---|---|---|
| 1342 | Pride and Prejudice | Austen | humorous, tender |
| 158 | Emma | Austen | humorous, cheerful |
| 1260 | Jane Eyre | C. Brontë | melancholic, ominous, tender |
| 768 | Wuthering Heights | E. Brontë | anger, grief, ominous |
| 345 | Dracula | Stoker | fear, suspense, ominous |
| 43 | Dr Jekyll and Mr Hyde | Stevenson | mysterious, fear |
| 120 | Treasure Island | Stevenson | suspense, violence, triumph |
| 98 | A Tale of Two Cities | Dickens | chaos, violence, solemn |
| 1400 | Great Expectations | Dickens | melancholic, humorous, mysterious |
| 174 | The Picture of Dorian Gray | Wilde | contemplative, ominous |
| 76 | Adventures of Huckleberry Finn | Twain | humorous, suspense |
| 35 | The Time Machine | Wells | mysterious, fear, contemplative |
| 36 | The War of the Worlds | Wells | chaos, fear, violence |
| 219 | Heart of Darkness | Conrad | ominous, contemplative |
| 1184 | The Count of Monte Cristo | Dumas (anon. transl.) | suspense, anger, triumph |
| 308 | Three Men in a Boat | Jerome | humorous, calm |
| 514 | Little Women | Alcott | tender, cheerful, grief |
| 215 | The Call of the Wild | London | violence, triumph |
| 110 | Tess of the d'Urbervilles | Hardy | grief, melancholic |
| 73 | The Red Badge of Courage | Crane | fear, chaos, violence |
| 209 | The Turn of the Screw | James | mysterious, ominous |
| 289 | The Wind in the Willows | Grahame | calm, cheerful |
| 2166 | King Solomon's Mines | Haggard | suspense, violence, triumph |
| 45 | Anne of Green Gables | Montgomery | cheerful, tender, humorous |

### Validation (3): gold set part A, used to fit C4 and the 1–5 mappings

| ID | Title | Author |
|---|---|---|
| 84 | Frankenstein | Shelley |
| 550 | Silas Marner | Eliot |
| 60 | The Scarlet Pimpernel | Orczy |

### Test (4): gold set part B, final numbers only

| ID | Title | Author |
|---|---|---|
| 2701 | Moby Dick | Melville |
| 2852 | The Hound of the Baskervilles | Conan Doyle |
| 175 | The Phantom of the Opera | Leroux (transl. de Mattos) |
| 1661 | The Adventures of Sherlock Holmes | Conan Doyle |

Each author is in only one split, so the test also measures generalisation to unseen authors.

---

## 3. Segments

- Segment exactly like the plugin (`crates/tauri-plugin-soundtrack/src/epub.rs`):
  - body text split into paragraphs;
  - greedy, 300–800 words, cut only at paragraph boundaries and at headings;
  - no segment crosses a spine item.
- **Remove** chapter titles, Gutenberg boilerplate, tables of contents, notes and captions. A
  title can give the mood away.
- **Sentences** for the sentence-level models: `split_sentences` from
  [`../common/sentences.py`](../common/sentences.py), applied per paragraph. Take paragraphs from
  block elements, not from line breaks: the Gutenberg XHTML breaks lines inside `<p>`.
- **How many:**
  - train books: 120 segments each (all, if fewer), spread evenly (~2,800 in total);
  - validation and test books: every eligible segment; ~100 (validation) and ~150 (test) of
    them are the gold set.
- **ID per segment:** `<book key>-<seg_index>` (e.g. `dracula-0042`), where `seg_index` is the
  plugin's segment index in that book, so a label can be matched to the plugin's segment `#N`.
- **Implemented in** [`segment.py`](segment.py) and [`books.py`](books.py), run from
  [`labeling.ipynb`](labeling.ipynb). Checked: on Moby Dick it gives the plugin's 347 segments
  and 215,845 words.

---

## 4. Labeller candidates

### Per dimension

| Dimension | Candidates (best first) | Earlier result (SENT, 700 words) |
|---|---|---|
| **Valence** | pert; literary-bert-base; literary-bert-large; sentiment-fiction-seq | pert ρ +0.73 (−low). literary-bert: untested here, card ρ 0.67 on Hemingway. sentiment-fiction-seq: untested, card ρ 0.60–0.73 |
| **Arousal** | pert | ρ +0.83 (p90). **Weak spot:** the only usable model |
| **Tension** | emolit (tension proxy) | ρ +0.67 (high). Also the only usable model |
| **Tags** | emolit (emotions → tags) | AP 0.59–0.65 on the E2 atmosphere labels |

### Left out, with reasons

| Model | Why |
|---|---|
| stories-emotion-c4 | No licence (§1); 85 s / segment. Thesis comparison only |
| literary-tone-classifier-v0.1 | E1: everything "humorous" at ≥ 700 words; weak signal only on 150–300-word windows |
| sentiment-fiction (the non-`seq` one) | No better than pert, and agrees with it at ρ 0.78–0.90, so it adds no new information |
| vad-bert, GoEmotions | Narrow scale, weaker than pert; GoEmotions arousal doesn't work (ρ +0.09) |

### Model-specific notes

- **pert:** custom `RoBERTaForVAD` head. Truncate the *sentence*, never the `<mask>` prompt (as
  in [`../common/encoders.py`](../common/encoders.py)). Valence ~1–5; arousal roughly −1..1 (not documented). Use its ranks,
  not its absolute values.
- **emolit:** multi-label sigmoid. Tension proxy per sentence (`tension_proxy` in `encoders.py`):
  `min(1, fear + nervousness + 0.6·anger + 0.3·(annoyance + disgust))`.
- **literary-bert:**
  - needs `trust_remote_code` (`BertForOrdinalRegression`);
  - score = `1 + Σ sigmoid(logit_k)` on 1–10; no softmax/argmax, no default pipeline, ignore
    the generic `id2label`;
  - max 256 tokens per sentence;
  - it was trained on Gemma-labelled Gutenberg sentences, which may include our test books.
- **sentiment-fiction-seq:** 3-class softmax, valence = `p(pos) − p(neg)`, max 512 tokens. Its
  outputs are overconfident (single sentences often get ±0.9 or more); the card names no
  calibration, and says the plain sentiment-fiction "may be preferable" for single sentences.
  Rank-based aggregates and Spearman are barely affected.
- **literary-bert, observed (2026-11-25):** the trained thresholds of the top levels are huge
  (logits 7–9 around −10²²), so levels 8–10 are unreachable and the score effectively spans
  ~1–8. A property of the model, not of our code (same numbers as the repo's own class).

---

## 5. Combinations to compare

Every model scores **sentences**; a segment's score is an aggregate over its sentences,
weighted by sentence length in words.

**Fixed aggregations.** Write these down **before** looking at the gold labels: they are the
ones SENT found best, now tested on new data.
- Valence = **p10** (pert: also report **−low**).
- Arousal = **p90**.
- Tension = **high**: the word share of sentences in the model's top quartile.
- Quartile cut-offs are computed over **all** labelled segments' sentences, not the gold set.

Also report the plain word-weighted mean for each, as a check.

### C1: pert + emolit (the earlier choice)

- V: pert valence (p10)
- A: pert arousal (p90)
- T: emolit tension proxy (high)
- Tags: emolit → tag mapping (below)

### C2: C1 + valence ensemble

- V = mean of the z-scored segment valences of **pert** and **literary-bert-base**.
- Z-scores are computed over all labelled segments, per model.
- Run literary-bert-large too, and keep whichever of base/large is better on validation.

### C3: C2 + third valence voter

- V = mean of the z-scores of pert, literary-bert, **sentiment-fiction-seq**.
- Keep it only if it beats C2 on validation. If the three agree at ρ > 0.85, the third adds
  nothing.

### C4: learned combination (stacking)

- **Features per segment:** all the aggregates of all models in C3, plus emolit's aggregated
  emotion probabilities (mean and p90 per emotion).
- **Scales:** one ridge regression each for V, A, T.
- **Tags:** one logistic regression per tag. A tag is kept if p ≥ 0.5, max 3 tags, at least
  the most likely one.
- **Fitting:** on the **validation** gold segments only (your hand labels), regularisation
  chosen by cross-validation within them.
- **Never** fit on GPT/Claude ratings (§1). Report on the test books.
- With ~100 fitting segments, keep the models linear and strongly regularised. If C4 doesn't
  beat C1–C3 on test, use the simpler one.

### Tag mapping for C1–C3 (draft)

Tag score = mean over sentences of the summed emolit probabilities. A tag is kept if its score
is in the top 25% of that tag's scores over all segments, max 3 tags. Fill in the `?` rows from
emolit's `config.json` `id2label` before running, and freeze the mapping before looking at the gold.

| Our tag | emolit emotions |
|---|---|
| calm | calmness, relief |
| cheerful | ? (joy / optimism, if present) |
| humorous | amusement |
| tender | caring, love, gratitude |
| melancholic | sadness, disappointment, nostalgia |
| grief | grief, despair |
| solemn | ? (check id2label; may stay without a mapping) |
| mysterious | doubt, curiosity |
| ominous | fear, nervousness |
| fear | fear |
| suspense | fear, nervousness, excitement |
| anger | anger, annoyance |
| violence | pain, anger, disgust |
| chaos | ? (confusion / surprise, if present) |
| triumph | ? (pride / admiration, if present) |
| contemplative | ? (check id2label; may stay without a mapping) |

Tags with no mapping can't be produced by C1–C3. Report them as such; C4 may still learn them
from other emotions.

### Runtime estimate (CPU, this machine)

pert 14.5 s + emolit 9.2 s + literary-bert ~2–3 s + sentiment-fiction-seq ~9 s per 700-word
segment ≈ **35 s / segment**, so ~30 hours for 3,000 segments. Run each model separately in the
background, and cache sentence scores so every combination reuses them.

---

## 6. Gold set and checking

### 6.1 Hand labels (ground truth)

- ~250 segments from the validation and test books (§2), labelled before looking at any
  model output.
- Same scales and tags as the v4 prompt (§6.3).
- Ideally a second person labels at least the test part. Human–human agreement is the
  **ceiling** in the results table.
- Store in `gold.csv`: `segment_id, annotator, valence, arousal, tension, tags, note`.

### 6.2 GPT / Claude ratings (checking only)

Purpose: check the combinations on more segments than you can hand-label, and see whether the
LLMs agree with you.

1. Rate the **gold set** with GPT and Claude (API), prompt §6.3. Measure their agreement with
   your hand labels.
2. If an LLM agrees with you about as well as a second human would (or ρ ≥ ~0.6 without a
   second human), also rate ~500–1,000 extra segments from the **validation and test** books
   with it.
3. Use these ratings only as a second yardstick: does the ranking of C1–C4 against the LLM
   ratings match the ranking against your hand labels?

Settings:
- **One segment per request.** Several in one message influence each other.
- Temperature 0 (or the lowest the API allows) and a fixed seed where supported.
- Structured output with the schema in §6.3.
- Validate every response (§6.3). If invalid, retry up to 2 times, then mark it as failed.

### 6.3 Checker prompt (`prompt_version = "4-teacher"`)

The v4 prompt from [`../qwen3-llamacpp/RESULTS.md`](../qwen3-llamacpp/RESULTS.md) with four added
rules for large models.

**System prompt:**

```
You rate the mood of a passage from a novel, to drive adaptive background music. Judge the emotional atmosphere the reader experiences, not the plot. Rate each scale with an integer from 1 to 5:
valence: 1 = grief, despair, horror; 2 = sad, gloomy, unpleasant; 3 = neutral or mixed; 4 = pleasant, warm, affectionate, amusing; 5 = joyful, elated.
arousal: 1 = still, sleepy; 2 = quiet, reflective; 3 = moderate activity; 4 = lively, agitated; 5 = frantic, violent action.
tension: 1 = relaxed, safe; 2 = slight unease; 3 = noticeable suspense; 4 = strong suspense or threat; 5 = extreme danger, climax.
Calibration: most passages of a novel sit in the middle of the scales (2-4). Use 1 or 5 only when the passage clearly and strongly calls for it, and rate each scale independently of the others.
Additional rules:
- Rate only what is in this passage. Do not use knowledge of the rest of the book, even if you recognise it: the reader does not know what comes next.
- Rate the atmosphere, not the characters' feelings: a character may be calm while the scene is tense, or afraid in a comic scene.
- If the mood changes within the passage, rate what dominates most of it, weighted towards the ending.
- Narrative distance matters: a calm retelling of past danger is less tense than danger happening now.
tags: the 1-3 tags that best describe the dominant feeling, from this list only:
- calm: peaceful, nothing is happening
- cheerful: light, happy, good spirits
- humorous: comic, ironic, playful
- tender: affection, friendship, intimacy
- melancholic: wistful sadness, longing
- grief: loss, mourning, death of someone close
- solemn: grave, dignified, religious or ceremonial
- mysterious: the unknown, enigma, the uncanny; not merely dark
- ominous: foreboding, a sense that something bad will happen
- fear: characters are afraid, terror
- suspense: uncertain outcome, the reader holds their breath
- anger: rage, defiance, hostility
- violence: physical struggle, killing, injury
- chaos: confusion, disorder, things falling apart
- triumph: victory, exultation, pride
- contemplative: reflection, philosophy, inner thought
rationale: one sentence of at most 20 words. Answer with JSON only.
```

**User message:** the segment text only, whitespace-normalised, with no title, book or author.

**JSON schema:**

```json
{
  "type": "object",
  "properties": {
    "rationale": {"type": "string", "maxLength": 400},
    "valence": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    "arousal": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    "tension": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
    "tags": {
      "type": "array",
      "items": {"type": "string", "enum": ["calm", "cheerful", "humorous", "tender", "melancholic", "grief", "solemn", "mysterious", "ominous", "fear", "suspense", "anger", "violence", "chaos", "triumph", "contemplative"]},
      "minItems": 1, "maxItems": 3, "uniqueItems": true
    }
  },
  "required": ["rationale", "valence", "arousal", "tension", "tags"],
  "additionalProperties": false
}
```

**Validation:**
- exactly these 5 fields;
- the three scales are integers 1–5;
- 1–3 distinct tags, all from the list;
- the rationale is at most ~25 words.

Some APIs don't support `minItems`/`maxItems`/`uniqueItems` in strict mode. Drop them there and
check them in validation instead.

---

## 7. Evaluation

### Metrics (per combination; test books unless stated)

- **V, A, T:**
  - Spearman ρ against the hand labels; needs no scale conversion.
  - MAE on the 1–5 scale, after a monotone mapping (quantile matching) fitted on the
    validation gold segments only.
  - Scale use: the share of 1–5 values that occur.
- **Tags:** mean Jaccard overlap, per-tag F1, and tags that are never produced.
- **Second yardstick:** the same metrics against GPT and Claude ratings (§6.2).
- **Cost:** seconds per segment.

### Results table

| Row | V ρ / MAE | A ρ / MAE | T ρ / MAE | Tag Jaccard | s / segment |
|---|---|---|---|---|---|
| Human vs. human (ceiling) | | | | | – |
| GPT vs. human | | | | | |
| Claude vs. human | | | | | |
| Qwen3-4B (in-app) vs. human | | | | | |
| C1 … C4 vs. human | | | | | |
| stories-emotion-c4 (comparison only) | | | – | – | |

### Decision rule

1. Pick the simplest combination that is not clearly worse than the best one on the test books:
   within ~0.05 ρ on every scale.
2. If **arousal or tension** stays well below the LLM checkers (e.g. ρ < 0.4 while the LLMs get
   > 0.6), note it as a limit of the labels. The student can't learn it from these labels.
3. Treat differences of less than ~0.1 ρ as noise: with ~150 test segments the uncertainty is
   about that large. Report bootstrap confidence intervals.

---

## 8. Full labelling run

1. Run the winning combination on all train-book segments (§3).
2. **Training target:** the continuous combined scores (not rounded), converted to 1–5 with the
   validation mapping. For tags, the per-tag scores (soft labels).
3. **Distribution check:**
   - a histogram per scale and per tag;
   - if > 70% of segments sit on one value, or a tag is never or always chosen, look at
     examples before training.
4. **Output** (JSONL, one line per segment; texts separately in `segments.jsonl`):

```json
{"segment_id": "dracula-0042", "split": "train", "book": "dracula", "section": 12,
 "seg_index": 42, "words": 702, "sentences": 31,
 "labeller": "C2", "models": {"pert": "<revision>", "emolit": "<revision>", "literary-bert-en-base": "<revision>"},
 "label": {"valence": 2.4, "arousal": 3.1, "tension": 3.8,
           "tags": {"ominous": 0.71, "suspense": 0.55, "fear": 0.40}},
 "created_at": "2026-11-25T12:00:00Z"}
```

Pin every model to a Hugging Face revision (commit hash), so the dataset can be reproduced.
