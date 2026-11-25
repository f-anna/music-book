"""Sentence-level encoder models used as labellers: loading, scoring, derived V / A / T.

Copied from eval/literary-tone/sentence_probe.py (the SENT experiment), limited to the models
kept for labelling (PERT-EmoPair, EmoLit). vad-bert, GoEmotions, sentiment-fiction and
stories-emotion were dropped there (stories-emotion also has no licence). New models
(literary-bert, sentiment-fiction-seq) go here when they are added.

Needs torch + transformers (the ~/.venvs/music-book-eval environment).
"""
import torch
from huggingface_hub import hf_hub_download
from torch import nn
from transformers import AutoModelForSequenceClassification, AutoTokenizer, RobertaConfig, RobertaModel

THREADS = 4
BATCH = 16

MODELS = {
    "pert": "edsi-umd/PERT-EmoPair",
    "emolit": "lrei/roberta-large-emolit",
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

    def __init__(self, repo, mode):
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.model = AutoModelForSequenceClassification.from_pretrained(repo).eval()
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
                logits = self.model(**enc).logits
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

    def __init__(self, repo):
        self.tok = AutoTokenizer.from_pretrained(repo)
        self.model = self.Net(RobertaConfig.from_pretrained(repo))
        state = torch.load(hf_hub_download(repo, "pytorch_model.bin"), map_location="cpu",
                           weights_only=True)
        state = state.get("model_state_dict", state)
        missing, unexpected = self.model.load_state_dict(state, strict=False)
        bad = [k for k in missing if "pooler" not in k]
        if bad or unexpected:
            raise RuntimeError(f"weights do not fit: missing {bad[:5]}, unexpected {unexpected[:5]}")
        self.load_note = {"missing_keys": missing, "unexpected_keys": unexpected}
        self.model.eval()
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
                vals = self.model(enc["input_ids"], enc["attention_mask"]).tolist()
            for i, v in zip(idx, vals):
                res[i] = (dict(zip(self.labels, v)), trunc[i])
        return res


def load(name):
    repo = MODELS[name]
    if name == "pert":
        return PertEmoPair(repo)
    return SeqClassifier(repo, "sigmoid")


def derived(name, raw):
    """The common V / A / T columns (where the model has them) from the raw outputs."""
    if name == "pert":
        return {"V": raw["valence"], "A": raw["arousal"], "D": raw["dominance"]}
    if name == "emolit":
        return {"T": tension_proxy(raw)}
    raise KeyError(name)
