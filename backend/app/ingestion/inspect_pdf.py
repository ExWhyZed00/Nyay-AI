"""Debug helper: show the text around a section number as the loader sees it.

    python -m app.ingestion.inspect_pdf --file data/constitution.pdf --find 368

Cross-references such as "under article 368." are hidden unless you add --all.
"""
import argparse
import re

from app.ingestion.chunker import _join_pages, read_pdf_pages

XREF = re.compile(r"(?:articles?|sections?|clauses?|paragraphs?|and|or|to|under|by|see|of|in)\s*$", re.I)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--find", required=True, help="section/article number, for example 217 or 21A")
    ap.add_argument("--all", action="store_true", help="also show cross-references")
    args = ap.parse_args()
    full, _ = _join_pages(read_pdf_pages(args.file))
    hits = list(re.finditer(rf"(?<!\d){re.escape(args.find)}\s?\.", full))
    likely = [m for m in hits if not XREF.search(full[max(0, m.start() - 14) : m.start()])]
    shown = hits if args.all else likely
    print(f"'{args.find}.' appears {len(hits)} times; {len(likely)} look like a heading, the rest are cross-references.")
    if not shown:
        print("No heading-like match. Re-run with --all to see every place.")
    for m in shown[:8]:
        print("\n..." + full[max(0, m.start() - 160) : m.end() + 300] + "...")


if __name__ == "__main__":
    main()
