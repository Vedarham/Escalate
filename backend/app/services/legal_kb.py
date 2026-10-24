"""Land-law knowledge base + BM25 retriever for the legal advisory agent.

Why BM25 (lexical) retrieval instead of embeddings:
  * legal questions hinge on exact terms ("7/12", "Section 53A", "encumbrance
    certificate", "GPA") that keyword ranking matches precisely;
  * the corpus is small and curated, so no vector database is needed;
  * zero extra dependencies or paid embedding calls - it runs inside a
    serverless function (Vercel) with millisecond latency and is deterministic,
    which makes retrieval quality unit-testable.
A synonym table bridges colloquial and regional terms (satbara -> 7/12, EC ->
encumbrance certificate, ...) and the LLM planner adds paraphrased queries.

Knowledge files live in app/knowledge/land_law/*.md. Each article:

    ## ID | Title
    jurisdiction: all-india            (comma-separated, lowercase state slugs)
    topics: comma, separated, keywords
    sources: statutes / judgments

    Body text...
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "land_law"

JURISDICTIONS = {
    "all-india": "All India",
    "maharashtra": "Maharashtra",
    "karnataka": "Karnataka",
    "tamil-nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "andhra-pradesh": "Andhra Pradesh",
    "uttar-pradesh": "Uttar Pradesh",
    "delhi": "Delhi",
    "gujarat": "Gujarat",
    "madhya-pradesh": "Madhya Pradesh",
}

# colloquial / regional term -> canonical expansion (applied to queries and documents)
SYNONYMS = {
    "satbara": "7/12 record rights",
    "saatbara": "7/12 record rights",
    "utara": "7/12 extract",
    "rtc": "rtc pahani record rights",
    "pahani": "rtc pahani record rights",
    "khatauni": "khatauni record rights",
    "patta": "patta record rights",
    "chitta": "chitta record rights",
    "ec": "encumbrance certificate",
    "encumbrance": "encumbrance certificate",
    "gpa": "power attorney gpa",
    "poa": "power attorney",
    "spa": "power attorney",
    "na": "non agricultural conversion",
    "dc": "conversion",
    "oc": "occupancy certificate",
    "cc": "commencement completion certificate",
    "nri": "nri non resident fema",
    "oci": "oci fema",
    "rera": "rera real estate regulation",
    "huf": "hindu undivided family coparcener",
    "ancestral": "ancestral inheritance coparcener",
    "inherited": "inheritance heirs",
    "heir": "heirs inheritance",
    "heirs": "heirs inheritance",
    "daughter": "daughters coparcener",
    "sister": "daughters coparcener heirs",
    "builder": "builder promoter rera",
    "flat": "flat apartment",
    "plot": "plot layout land",
    "farm": "agricultural land",
    "farmland": "agricultural land",
    "agri": "agricultural",
    "loan": "mortgage loan bank",
    "mortgaged": "mortgage",
    "squatter": "encroachment occupant adverse possession",
    "living": "occupant possession adverse",
    "staying": "occupant possession adverse",
    "occupying": "occupant possession adverse",
    "occupied": "occupant possession adverse",
    "squatting": "encroachment occupant adverse possession",
    "encroacher": "encroachment occupant",
    "tenant": "tenant occupant",
    "advance": "advance earnest money",
    "token": "token earnest money advance",
    "stamp": "stamp duty",
    "tds": "tds 194 ia tax",
    "testament": "will testament",
    "wills": "will testament",
    "probate": "probate will",
    "minor": "minor guardian court permission",
    "lawsuit": "litigation suit",
    "case": "litigation suit",
    "court": "court litigation",
    "fake": "fraud forgery",
    "forged": "fraud forgery",
    "cheated": "fraud remedy",
    "scam": "fraud",
    "road": "road access easement",
    "access": "access easement right way",
    "boundary": "boundary demarcation",
    "lal": "lal dora",
    "dora": "lal dora abadi",
    "mutation": "mutation revenue records",
    "khata": "khata mutation",
    "khasra": "khasra record rights",
    "mp": "madhya pradesh",
    "namantaran": "mutation",
    "diversion": "diversion conversion land use",
}

STOPWORDS = set("""a an the and or of to in on for with is are was were be been it this that what which who whom
how can could should would do does did i my me we our you your they their he she his her at by from as if
any about into than then there here so not no yes will shall may might must have has had get got buy buying
purchase purchasing property land want need know tell please sir""".split()) - {"no"}

_TOKEN_RE = re.compile(r"\d+/\d+[a-z]?|[a-z0-9]+(?:-[a-z0-9]+)*")
# "will" is a stopword as a verb ("who will win") but a legal term as a noun ("left a will")
_WILL_NOUN_RE = re.compile(r"\b(a|the|his|her|my|their|our|its|no|without|under|registered|unregistered|valid|"
                           r"forged|last|father's|mother's|grandfather's)\s+will\b")


def tokenize(text: str) -> list[str]:
    text = _WILL_NOUN_RE.sub(r"\1 testament", text.lower().replace("\u2019", "'"))
    raw = _TOKEN_RE.findall(text)
    out: list[str] = []
    for tok in raw:
        if tok in SYNONYMS:
            out.extend(_TOKEN_RE.findall(SYNONYMS[tok]))
        if tok not in STOPWORDS:
            out.append(tok)
        if "-" in tok:  # "non-agricultural" also matches "non agricultural"
            out.extend(p for p in tok.split("-") if p not in STOPWORDS)
    # light stemming: plural -> singular
    return [t[:-1] if len(t) > 4 and t.endswith("s") and not t.endswith("ss") else t for t in out]


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    jurisdictions: tuple[str, ...]
    topics: tuple[str, ...]
    sources: str
    body: str
    file: str

    def excerpt(self, n: int = 320) -> str:
        return self.body if len(self.body) <= n else self.body[:n].rsplit(" ", 1)[0] + "…"


@dataclass
class Hit:
    article: Article
    score: float
    matched_terms: list[str] = field(default_factory=list)


def parse_kb(directory: Path = KB_DIR) -> list[Article]:
    articles: list[Article] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
            header, _, rest = block.partition("\n")
            if "|" not in header:
                continue
            art_id, title = (s.strip() for s in header.split("|", 1))
            meta: dict[str, str] = {}
            lines = rest.strip("\n").split("\n")
            i = 0
            while i < len(lines) and re.match(r"^[a-z_]+:\s", lines[i]):
                k, v = lines[i].split(":", 1)
                meta[k.strip()] = v.strip()
                i += 1
            body = "\n".join(lines[i:]).strip()
            articles.append(Article(
                id=art_id, title=title,
                jurisdictions=tuple(j.strip() for j in meta.get("jurisdiction", "all-india").split(",") if j.strip()),
                topics=tuple(t.strip() for t in meta.get("topics", "").split(",") if t.strip()),
                sources=meta.get("sources", ""), body=body, file=path.name,
            ))
    return articles


class BM25Index:
    def __init__(self, articles: list[Article], k1: float = 1.4, b: float = 0.7):
        self.articles = articles
        self.k1, self.b = k1, b
        self.docs: list[Counter] = []
        for a in articles:
            # title and topics are weighted x3 / x2 by repetition
            text = " ".join([a.title] * 3 + [" ".join(a.topics)] * 2 + [a.sources, a.body])
            self.docs.append(Counter(tokenize(text)))
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avgdl = sum(self.lengths) / max(1, len(self.lengths))
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query_tokens: list[str], idx: int) -> tuple[float, list[str]]:
        d, dl = self.docs[idx], self.lengths[idx]
        s, matched = 0.0, []
        for t in set(query_tokens):
            tf = d.get(t)
            if not tf:
                continue
            matched.append(t)
            s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s, matched

    def search(self, queries: list[str], jurisdiction: str | None = None, k: int = 6) -> list[Hit]:
        """Score each article by its best query (max fusion) with a jurisdiction prior."""
        best: dict[int, Hit] = {}
        for q in queries:
            toks = tokenize(q)
            if not toks:
                continue
            for i, art in enumerate(self.articles):
                s, matched = self.score(toks, i)
                if s <= 0:
                    continue
                if jurisdiction and jurisdiction != "all-india":
                    if jurisdiction in art.jurisdictions:
                        s *= 1.35
                    elif "all-india" not in art.jurisdictions:
                        s *= 0.45  # another state's rules: keep but demote
                elif "all-india" not in art.jurisdictions:
                    s *= 0.8
                if i not in best or s > best[i].score:
                    best[i] = Hit(art, s, matched)
        hits = sorted(best.values(), key=lambda h: h.score, reverse=True)
        if not hits:
            return []
        top = hits[0].score
        # drop weak tail matches (< 25% of the best score)
        return [h for h in hits[:k] if h.score >= 0.25 * top]

    def get(self, art_id: str) -> Article | None:
        return next((a for a in self.articles if a.id == art_id), None)


@lru_cache
def get_index() -> BM25Index:
    return BM25Index(parse_kb())
