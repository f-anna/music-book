"""Sentence-level encoder models used as labellers: loading, scoring, derived V / A / T.

PERT-EmoPair and EmoLit are copied from eval/literary-tone/sentence_probe.py (the SENT
experiment); vad-bert, GoEmotions, sentiment-fiction and stories-emotion were dropped there
(stories-emotion also has no licence). Added for labelling: sentiment-fiction-seq and
literary-bert (base, large). Changes to the copied code: a `device` argument, and pinned
revisions (MODELS) so the scores can be reproduced.

Every model is called on a list of sentences and returns [(raw {name: value}, truncated)].
`derived()` turns the raw outputs into the common V / A / T columns.

Needs torch + transformers (the ~/.venvs/music-book-eval environment).
"""
import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from torch import nn
from torch.nn import functional as F
from transformers import (AutoModelForSequenceClassification, AutoTokenizer, BertConfig, BertModel,
                          RobertaConfig, RobertaModel)

THREADS = 4
BATCH = 16

# name -> (Hugging Face repo, pinned revision). The revisions are the ones current on 2026-11-25
# (PERT's is the one SENT used); change them only deliberately, scores depend on them.
MODELS = {
    "pert": ("edsi-umd/PERT-EmoPair", "f8ff78b70b737b73b0f2e16378abf6c64e1431ba"),
    "emolit": ("lrei/roberta-large-emolit", "5609a7f6108ccb82ec93eb26d026682bb70b67a6"),
    "fiction_seq": ("fpianz/sentiment-fiction-seq", "8521eb515cb9bf4bf222360a5ff76b4f2b19080e"),
    "litbert_base": ("susurofu/literary-bert-en-base", "74b7552f6053494f8b7de0940c0b6d595f117c53"),
    "litbert_large": ("susurofu/literary-bert-en-large", "4346a939b317e2369b79f76c1df9487887cf9f4b"),
}


def tension_proxy(p):
    """The model-selection formula, on EmoLit's emotion probabilities."""
    return min(1.0, p["fear"] + p["nervousness"] + 0.6 * p["anger"]
               + 0.3 * (p["annoyance"] + p["disgust"]))


def batched(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class SeqClassifier:
    """A standard sequence classifier: sigmoid (multi-label, e.g. EmoLit), softmax or raw logits."""

    def __init__(self, repo, mode, revision=None, device="cpu"):
        self.tok = AutoTokenizer.from_pretrained(repo, revision=revision)
        self.model = AutoModelForSequenceClassification.from_pretrained(repo, revision=revision).eval()
        self.device = device
        self.model.to(device)
        self.mode = mode
        cfg = self.model.config
        self.labels = [cfg.id2label[i] for i in range(cfg.num_labels)]
        self.max_len = min(512, cfg.max_position_embeddings - 2)

    def __call__(self, texts):
        """-> [(raw {label: value}, truncated)] in input order; batches sorted by length."""
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        res = [None] * len(texts)
        for idx in batched(order, BATCH):
            batch = [texts[i] for i in idx]
            enc = self.tok(batch, truncation=True, max_length=self.max_len, padding=True,
                           return_tensors="pt")
            full = [len(x) for x in self.tok(batch)["input_ids"]]
            with torch.no_grad():
                logits = self.model(**enc.to(self.device)).logits
            if self.mode == "sigmoid":
                vals = torch.sigmoid(logits)
            elif self.mode == "softmax":
                vals = torch.softmax(logits, dim=1)
            else:
                vals = logits
            for i, v, n in zip(idx, vals.tolist(), full):
                res[i] = (dict(zip(self.labels, v)), n > self.max_len)
        return res


class PertEmoPair:
    """edsi-umd/PERT-EmoPair: roberta-large + linear head on <s>, prompted input (model card)."""

    PROMPT = ("- Valence: The emotional valence of the context is <mask>. "
              "- Arousal: The level of arousal of the context is <mask>. "
              "- Dominance: The perceived dominance associated with the context is <mask>. "
              "Please predict the missing value for each dimension using the content provided.")
    MAX_LEN = 256  # the card's max_length

    class Net(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.base_model = RobertaModel(cfg)
            self.dropout = nn.Dropout(p=0.1)
            self.regressor = nn.Linear(cfg.hidden_size, 3)

        def forward(self, input_ids, attention_mask):
            out = self.base_model(input_ids=input_ids, attention_mask=attention_mask)
            return self.regressor(out.last_hidden_state[:, 0, :])

    def __init__(self, repo, revision=None, device="cpu"):
        self.tok = AutoTokenizer.from_pretrained(repo, revision=revision)
        self.model = self.Net(RobertaConfig.from_pretrained(repo, revision=revision))
        state = torch.load(hf_hub_download(repo, "pytorch_model.bin", revision=revision),
                           map_location="cpu", weights_only=True)
        state = state.get("model_state_dict", state)
        missing, unexpected = self.model.load_state_dict(state, strict=False)
        bad = [k for k in missing if "pooler" not in k]
        if bad or unexpected:
            raise RuntimeError(f"weights do not fit: missing {bad[:5]}, unexpected {unexpected[:5]}")
        self.load_note = {"missing_keys": missing, "unexpected_keys": unexpected}
        self.device = device
        self.model.to(device).eval()
        self.labels = ["valence", "arousal", "dominance"]
        # the card truncates the whole prompted string, which would cut the <mask>s off a long
        # sentence; the context is truncated instead, so the prompt always stays
        empty = len(self.tok(f"Context: '' {self.PROMPT}")["input_ids"])
        self.budget = self.MAX_LEN - empty

    def __call__(self, texts):
        prompted, trunc = [], []
        for t in texts:
            ids = self.tok(t, add_special_tokens=False)["input_ids"]
            trunc.append(len(ids) > self.budget)
            if len(ids) > self.budget:
                t = self.tok.decode(ids[:self.budget])
            prompted.append(f"Context: '{t}' {self.PROMPT}")
        order = sorted(range(len(texts)), key=lambda i: len(prompted[i]))
        res = [None] * len(texts)
        for idx in batched(order, BATCH):
            enc = self.tok([prompted[i] for i in idx], truncation=True, max_length=self.MAX_LEN,
                           padding=True, return_tensors="pt")
            with torch.no_grad():
                vals = self.model(enc["input_ids"].to(self.device),
                                  enc["attention_mask"].to(self.device)).tolist()
            for i, v in zip(idx, vals):
                res[i] = (dict(zip(self.labels, v)), trunc[i])
        return res


class LiteraryBert:
    """susurofu/literary-bert-en-{base,large}: BERT + cumulative-logit ordinal head, 10 levels.

    Re-implemented from the repo's modeling_ordinal_bert.py (revision pinned in MODELS) instead of
    loading it with trust_remote_code, so no code from the model repo runs. The head: a linear
    score on the pooler output, minus 9 ordered thresholds (the first one, then cumulative
    softplus steps) -> 9 cumulative logits. Score = 1 + sum(sigmoid(logits)), on 1..10 (the
    card: no softmax / argmax). Sentences are truncated at 256 tokens, as in training.
    """

    MAX_LEN = 256

    class Net(nn.Module):
        def __init__(self, cfg):
            super().__init__()
            self.bert = BertModel(cfg)
            self.dropout = nn.Dropout(0.1)
            self.sentiment_score = nn.Linear(cfg.hidden_size, 1)
            self.first_threshold = nn.Parameter(torch.tensor(-2.0))
            self.threshold_deltas = nn.Parameter(torch.zeros(cfg.num_labels - 2))

        def thresholds(self):
            rest = self.first_threshold + torch.cumsum(F.softplus(self.threshold_deltas), dim=0)
            return torch.cat([self.first_threshold.reshape(1), rest])

        def forward(self, input_ids, attention_mask, token_type_ids):
            out = self.bert(input_ids=input_ids, attention_mask=attention_mask,
                            token_type_ids=token_type_ids, return_dict=True)
            latent = self.sentiment_score(out.pooler_output)
            return latent.squeeze(1), latent - self.thresholds().unsqueeze(0)

    def __init__(self, repo, revision=None, device="cpu"):
        self.tok = AutoTokenizer.from_pretrained(repo, revision=revision)
        cfg = BertConfig.from_pretrained(repo, revision=revision)
        self.model = self.Net(cfg)
        state = load_file(hf_hub_download(repo, "model.safetensors", revision=revision))
        missing, unexpected = self.model.load_state_dict(state, strict=False)
        # position_ids is a buffer some checkpoints carry; nothing else may be missing or extra
        bad = [k for k in missing + unexpected if "position_ids" not in k]
        if bad:
            raise RuntimeError(f"weights do not fit: {bad[:5]}")
        self.load_note = {"missing_keys": missing, "unexpected_keys": unexpected}
        self.device = device
        self.model.to(device).eval()

    def __call__(self, texts):
        order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
        res = [None] * len(texts)
        for idx in batched(order, BATCH):
            batch = [texts[i] for i in idx]
            enc = self.tok(batch, truncation=True, max_length=self.MAX_LEN, padding=True,
                           return_tensors="pt").to(self.device)
            full = [len(x) for x in self.tok(batch)["input_ids"]]
            with torch.no_grad():
                latent, logits = self.model(enc["input_ids"], enc["attention_mask"],
                                            enc["token_type_ids"])
            scores = 1 + torch.sigmoid(logits).sum(dim=1)
            for b, i in enumerate(idx):
                raw = {"score": scores[b].item(), "latent": latent[b].item()}
                raw.update({f"logit{k + 1}": v for k, v in enumerate(logits[b].tolist())})
                res[i] = (raw, full[b] > self.MAX_LEN)
        return res


def load(name, device="cpu"):
    repo, revision = MODELS[name]
    if name == "pert":
        return PertEmoPair(repo, revision, device)
    if name.startswith("litbert"):
        return LiteraryBert(repo, revision, device)
    mode = {"emolit": "sigmoid", "fiction_seq": "softmax"}[name]
    return SeqClassifier(repo, mode, revision, device)


def derived(name, raw):
    """The common V / A / T columns (where the model has them) from the raw outputs.

    pert: V ~1..5, A roughly -1..1 (undocumented); emolit: T = tension proxy 0..1;
    fiction_seq: V = p(pos) - p(neg), -1..1; litbert: V = ordinal score 1..10.
    """
    if name == "pert":
        return {"V": raw["valence"], "A": raw["arousal"], "D": raw["dominance"]}
    if name == "emolit":
        return {"T": tension_proxy(raw)}
    if name == "fiction_seq":
        return {"V": raw["positive"] - raw["negative"]}
    if name.startswith("litbert"):
        return {"V": raw["score"]}
    raise KeyError(name)
