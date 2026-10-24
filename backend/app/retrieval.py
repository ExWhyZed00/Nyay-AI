"""Hybrid search: exact section lookup + semantic (meaning) + keyword, merged with RRF."""
import json
import logging
import re

from app.clients import embed_query
from app.db import fetch_all

logger = logging.getLogger(__name__)

COLUMNS = "id, act, section_number, title, content, page"

# ---------- 1) Exact lookup ("Section 103 BNS", "Article 21") ----------------------

_SECTION_LIST_RE = re.compile(
    r"\b(?:sections?|sec\.?)\s*((?:\d{1,3}[A-Za-z]?\s*(?:,|and|&|or)?\s*)+)", re.I
)
_ARTICLE_LIST_RE = re.compile(
    r"\barticles?\s*((?:\d{1,3}[A-Za-z]{0,2}\s*(?:,|and|&|or)?\s*)+)", re.I
)
_NUMBER_RE = re.compile(r"\d{1,3}[A-Za-z]{0,2}")
_OLD_LAW_RE = re.compile(
    r"\b(ipc|crpc|cr\.?\s?p\.?\s?c\.?|indian penal code|code of criminal procedure)\b", re.I
)


def _numbers(group: str) -> list[str]:
    return [n.upper() for n in _NUMBER_RE.findall(group)][:5]


def parse_references(query: str) -> list[tuple[list[str], list[str]]]:
    """Find explicit references like 'Section 103 BNS' or 'Article 21'.

    Returns a list of (acts, numbers). Skips everything when the old IPC/CrPC is
    mentioned, because their section numbers differ from BNS/BNSS.
    """
    if _OLD_LAW_RE.search(query):
        return []

    refs: list[tuple[list[str], list[str]]] = []

    sec_nums: list[str] = []
    for m in _SECTION_LIST_RE.finditer(query):
        sec_nums += _numbers(m.group(1))
    if sec_nums:
        lowered = query.lower()
        acts: list[str] = []
        if re.search(r"\bbnss\b|nagarik suraksha", lowered):
            acts.append("BNSS")
        if re.search(r"\bbns\b|bharatiya nyaya", lowered):
            acts.append("BNS")
        if not acts:
            acts = ["BNS", "BNSS"]
        refs.append((acts, sec_nums[:5]))

    art_nums: list[str] = []
    for m in _ARTICLE_LIST_RE.finditer(query):
        art_nums += _numbers(m.group(1))
    if art_nums:
        refs.append((["Constitution"], art_nums[:5]))

    return refs


def exact_lookup(query: str) -> list[dict]:
    rows: list[dict] = []
    for acts, numbers in parse_references(query):
        rows += fetch_all(
            f"""SELECT {COLUMNS} FROM chunks
                WHERE act = ANY(%s) AND upper(section_number) = ANY(%s)
                ORDER BY act, id LIMIT 12""",
            (acts, numbers),
        )
    return rows


# ---------- 2) Semantic search ---------------------------------------------------

def _vector_literal(vec: list[float]) -> str:
    return json.dumps(vec)  # "[0.1, 0.2, ...]" is valid pgvector input


def semantic_search(query_vec: list[float], limit: int = 20) -> list[dict]:
    lit = _vector_literal(query_vec)
    return fetch_all(
        f"""SELECT {COLUMNS} FROM chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s""",
        (lit, limit),
    )


# ---------- 3) Keyword search -----------------------------------------------------

def build_or_tsquery(query: str) -> str | None:
    """'punishment for murder' -> 'punishment | murder' (safe: letters/digits only)."""
    seen: list[str] = []
    for tok in re.findall(r"[A-Za-z0-9]+", query.lower()):
        if len(tok) >= 3 and tok not in seen:
            seen.append(tok)
    seen = seen[:12]
    return " | ".join(seen) if seen else None


def keyword_search(query: str, limit: int = 20) -> list[dict]:
    tsq = build_or_tsquery(query)
    if not tsq:
        return []
    return fetch_all(
        f"""SELECT {COLUMNS} FROM chunks
            WHERE tsv @@ to_tsquery('english', %s)
            ORDER BY ts_rank_cd(tsv, to_tsquery('english', %s)) DESC
            LIMIT %s""",
        (tsq, tsq, limit),
    )


# ---------- Merge: Reciprocal Rank Fusion ----------------------------------------

def rrf_merge(
    ranked_lists: list[list[dict]],
    weights: list[float] | None = None,
    k: int = 60,
    top_n: int = 8,
) -> list[dict]:
    """Chunks ranked high in several lists win. score = sum(weight / (k + rank))."""
    weights = weights or [1.0] * len(ranked_lists)
    scores: dict[int, float] = {}
    by_id: dict[int, dict] = {}
    for rows, weight in zip(ranked_lists, weights):
        for rank, row in enumerate(rows, start=1):
            scores[row["id"]] = scores.get(row["id"], 0.0) + weight / (k + rank)
            by_id.setdefault(row["id"], row)
    ordered = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:top_n]
    return [{**by_id[cid], "score": round(scores[cid], 5)} for cid in ordered]


def search_hybrid(query: str, k: int = 8) -> list[dict]:
    exact = exact_lookup(query)
    try:
        semantic = semantic_search(embed_query(query))
    except Exception:
        logger.exception("Semantic search failed; continuing with keyword search only")
        semantic = []
    keyword = keyword_search(query)
    return rrf_merge([exact, semantic, keyword], weights=[2.0, 1.0, 1.0], top_n=k)


def format_ref(act: str, section_number: str | None) -> str:
    """'BNS Section 103' / 'Constitution Article 21' / 'BNS'."""
    if not section_number:
        return act
    kind = "Article" if act == "Constitution" else "Section"
    return f"{act} {kind} {section_number}"
