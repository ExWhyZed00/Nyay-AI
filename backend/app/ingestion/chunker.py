"""Turn a law PDF into chunks: one chunk per Section / Article (long ones are split)."""
import re
from bisect import bisect_right
from dataclasses import dataclass

from pypdf import PdfReader

MAX_CHARS = 1500
OVERLAP = 150
MIN_SECTIONS = 10  # fewer headings than this -> probably a parsing problem -> fallback

# Indian statutes write headings like:  "103. Punishment for murder.—(1) Whoever ..."
# The title may not contain another "12. " style number, otherwise a table of contents
# followed by the first real heading would be swallowed as one giant fake heading.
# "[" is allowed before the number: amended Acts print inserted sections as "1[21A. Title.—...]".
HEADING_RE = re.compile(
    r"(?<![\w.(])(\d{1,3})([A-Z]{0,2})\.\s+"
    r"([A-Z\"“‘](?:(?!\s\d{1,3}[A-Z]{0,2}\.\s)[^—–]){1,250}?)"
    r"\.\s?[—–-]"
)

# Everything after the last section that is NOT part of it: statement of objects, schedules, appendices.
END_MARKER_RE = re.compile(
    r"STATEMENT OF OBJECTS AND REASONS"
    r"|\b(?:THE )?(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH) SCHEDULE\b"
    r"|\bTHE SCHEDULE\b"
    r"|\bAPPENDIX\s+[IVX0-9]+\b"
)
_OMITTED_RE = re.compile(r"^\W{0,4}(?:Omitted|Repealed)\b", re.I)

_LEADING_PAGE_NO_RE = re.compile(r"^\d{1,3}(?=\s)")  # "17 Explanation 2..." -> page number 17; "5. Heading" is kept
_CHAPTER_START_RE = re.compile(r"\s(?:CHAPTER|PART)\s+[IVXLC]+[A-Z]?\s+[A-Z]")
_LEADING_JUNK = " —–-"


@dataclass
class Chunk:
    act: str
    section_number: str | None
    title: str | None
    part: int
    content: str
    page: int | None


def read_pdf_pages(path: str) -> list[str]:
    reader = PdfReader(path)
    return [(page.extract_text() or "") for page in reader.pages]


def _normalize(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u00ad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return _LEADING_PAGE_NO_RE.sub("", text).lstrip()


def strip_trailing_heading(body: str) -> str:
    """Remove a 'CHAPTER III GENERAL EXCEPTIONS' style heading stuck to the end of a section."""
    last = None
    for last in _CHAPTER_START_RE.finditer(body):
        pass
    if last is not None and len(body) - last.start() <= 250:
        return body[: last.start()].rstrip()
    return body


def cut_at_end_marker(body: str) -> str:
    """For the LAST section only: drop statement of objects, schedules and appendices."""
    m = END_MARKER_RE.search(body)
    return body[: m.start()].rstrip() if m else body


def looks_like_bill(pages: list[str]) -> bool:
    """A Bill (not yet law) has different section numbers from the final Act. Detect it."""
    head = " ".join(pages[:3])[:8000]
    full = " ".join(pages)
    return bool(re.search(r"\bA BILL to\b", head)) or bool(re.search(r"\bClause \d+ of the Bill\b", full))


def _join_pages(pages: list[str]) -> tuple[str, list[int]]:
    """Join all pages into one string; remember where each page starts."""
    parts, starts, pos = [], [], 0
    for p in pages:
        t = _normalize(p)
        starts.append(pos)
        parts.append(t)
        pos += len(t) + 1  # +1 for the joining space
    return " ".join(parts), starts


def split_text(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP) -> list[tuple[int, str]]:
    """Split long text on sentence-ish boundaries. Returns (start_offset, piece) pairs."""
    text = text.strip()
    if len(text) <= max_chars:
        return [(0, text)] if text else []
    pieces: list[tuple[int, str]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            window_start = start + int(max_chars * 0.6)
            cut = max(text.rfind(". ", window_start, end), text.rfind("; ", window_start, end))
            if cut == -1:
                cut = text.rfind(" ", window_start, end)
            if cut != -1:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append((start, piece))
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return pieces


def _page_of(offset: int, starts: list[int]) -> int:
    return max(1, bisect_right(starts, offset))


def find_headings(full: str) -> list[tuple[int, int, str, str]]:
    """Return accepted headings as (start, end, number, title).

    Numbers must increase through the document. This filters out look-alikes such as
    '1. (a) ...' inside a section or numbers in the table of contents.
    """
    accepted: list[tuple[int, int, str, str]] = []
    last: tuple[int, str] | None = None
    for m in HEADING_RE.finditer(full):
        num, suffix, title = int(m.group(1)), m.group(2), m.group(3).strip()
        key = (num, suffix)
        if last is None:
            ok = num <= 3
        else:
            ok = (num == last[0] and suffix > last[1]) or (last[0] < num <= last[0] + 30)
        if ok:
            accepted.append((m.start(), m.end(), f"{num}{suffix}", title))
            last = key
    return accepted


def _int_of(number: str) -> int:
    return int(re.match(r"\d+", number).group())  # type: ignore[union-attr]


_TITLE = r"[A-Z\"“‘][^—–\[\]]{1,250}?"


def _recovery_patterns(n: int) -> list[str]:
    """Odd heading styles found in the real India Code PDFs, tried in this order."""
    return [
        rf"(?<!\d){n}\s?\.\s*({_TITLE})\.\s?(?:\d{{1,2}}\s?)?[—–-]",   # "217. Title.1—text"   (footnote digit)
        rf"(?<!\d){n}\s?\.\s*[—–]\s*({_TITLE})\s*\.\s*[—–-]",           # "255.—Title .—text"
        rf"(?<!\d){n}\s?\.\s*\[({_TITLE})\.?\s*\]\s*\.?\s*[—–-]",     # "370. [Title.]—text"
        rf"(?<!\d){n}\s?\.\s*({_TITLE})\s*[—–]",                           # "217. Title—text"     (no period)
        # "368. 1[Title.]—text" / "368. 1[Title].—text": amended title wrapped in a footnote bracket
        rf"(?<!\d){n}\s?\.\s*(?:\d{{1,2}}\s?)?\[?\s*({_TITLE})\s*\.?\s*\]?\s*\.?\s*[—–]",
    ]


# Words that, right before "368.", mean it is a cross-reference ("under article 368."), not a heading.
_XREF_WORDS = {
    "article", "articles", "section", "sections", "clause", "clauses", "paragraph", "paragraphs",
    "schedule", "part", "chapter", "and", "or", "to", "under", "by", "see", "with", "from", "of", "in",
    "sub-section", "sub-clause",
}


def _first_real_heading(pattern: str, text: str) -> "re.Match[str] | None":
    """First match that is not a cross-reference.

    Headings may follow a Part or sub-heading ("AMENDMENT OF THE CONSTITUTION 368. Power..."),
    so we only reject a match when the word before it is a reference word like "article".
    """
    for m in re.finditer(pattern, text):
        words = text[: m.start()].split()
        prev = re.sub(r"[^a-z\-]", "", words[-1].lower()) if words else ""
        if prev not in _XREF_WORDS:
            return m
    return None


def recover_missing(full: str, headings: list[tuple[int, int, str, str]]) -> list[tuple[int, int, str, str]]:
    """Look for numbers skipped by the main pass, only between their two neighbouring headings.

    Uses more tolerant patterns than the main pass (see _recovery_patterns).
    """
    result: list[tuple[int, int, str, str]] = []
    for idx, h in enumerate(headings):
        result.append(h)
        if idx + 1 >= len(headings):
            continue
        nxt = headings[idx + 1]
        lo, hi = _int_of(h[2]) + 1, _int_of(nxt[2])
        pos = h[1]
        for n in range(lo, hi):
            for pattern in _recovery_patterns(n):
                m = _first_real_heading(pattern, full[pos : nxt[0]])
                if m:
                    result.append((pos + m.start(), pos + m.end(), str(n), m.group(1).strip()))
                    pos = pos + m.end()
                    break
    return result


def chunk_document(
    pages: list[str], act: str, min_sections: int = MIN_SECTIONS, recover: bool = True
) -> tuple[list[Chunk], str]:
    """Returns (chunks, mode) where mode is 'sections' or 'fallback'.

    recover=True also looks for headings the main pass skipped (odd formatting).
    """
    full, starts = _join_pages(pages)
    headings = find_headings(full)
    if recover and headings:
        headings = recover_missing(full, headings)

    if len(headings) < min_sections:
        chunks = [
            Chunk(act, None, None, i, piece, _page_of(offset, starts))
            for i, (offset, piece) in enumerate(split_text(full), start=1)
        ]
        return chunks, "fallback"

    chunks: list[Chunk] = []
    for i, (h_start, h_end, number, title) in enumerate(headings):
        is_last = i + 1 >= len(headings)
        body_end = len(full) if is_last else headings[i + 1][0]
        body = full[h_end:body_end].strip().lstrip(_LEADING_JUNK).strip()
        if is_last:
            body = cut_at_end_marker(body)
        body = strip_trailing_heading(body)
        if len(body) < 15 or _OMITTED_RE.match(body):  # skip repealed / omitted provisions
            continue
        page = _page_of(h_start, starts)
        for part, (_off, piece) in enumerate(split_text(body), start=1):
            chunks.append(Chunk(act, number, title, part, piece, page))
    return chunks, "sections"
