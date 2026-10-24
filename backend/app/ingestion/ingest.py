"""Load a law PDF into the database.

Usage (run from the backend folder):
    python -m app.ingestion.ingest --act BNS --file data/bns.pdf --dry-run
    python -m app.ingestion.ingest --act BNS --file data/bns.pdf
Acts: BNS, BNSS, Constitution
"""
import argparse
import sys
import time

import psycopg

from app.clients import embed_texts
from app.config import get_settings
from app.ingestion.chunker import Chunk, chunk_document, looks_like_bill, read_pdf_pages
from app.retrieval import format_ref

ACTS = ["BNS", "BNSS", "Constitution"]
EXPECTED = {"BNS": "about 358", "BNSS": "about 531", "Constitution": "about 395-470"}
BATCH = 64


def embedding_text(c: Chunk) -> str:
    head = format_ref(c.act, c.section_number)
    title = f": {c.title}" if c.title else ""
    return f"{head}{title}\n{c.content}"[:6000]


def describe(chunks: list[Chunk], mode: str, act: str) -> None:
    sections = sorted({c.section_number for c in chunks if c.section_number}, key=lambda s: (int("".join(ch for ch in s if ch.isdigit())), s))
    print(f"\nMode: {mode}")
    print(f"Chunks: {len(chunks)}")
    if mode == "sections":
        print(f"Distinct sections/articles found: {len(sections)} (expected {EXPECTED[act]})")
        print(f"First: {sections[0]}   Last: {sections[-1]}")
        if act in ("BNS", "BNSS"):  # these Acts number every section 1..N with no gaps
            nums = {int("".join(ch for ch in s if ch.isdigit())) for s in sections}
            missing = [n for n in range(1, max(nums) + 1) if n not in nums]
            if missing:
                shown = ", ".join(map(str, missing[:25])) + (" ..." if len(missing) > 25 else "")
                print(f"WARNING: {len(missing)} section numbers not found: {shown}")
            else:
                print("No gaps: every section number from 1 to the last was found.")
    else:
        print("WARNING: could not find section headings, so the text was split into plain pieces.")
        print("Search still works, but exact 'Section 103' lookup will not. Check the PDF is a text PDF.")
    # a section with a huge number of parts almost always means unrelated text was glued to it
    parts_per: dict = {}
    for c in chunks:
        if c.section_number:
            parts_per[c.section_number] = parts_per.get(c.section_number, 0) + 1
    for sec, n in parts_per.items():
        if n > 12:
            print(f"WARNING: {format_ref(act, sec)} has {n} parts. Unrelated text (notes, schedule, appendix) may be attached to it.")
    if act == "Constitution" and mode == "sections":
        nums = {int("".join(ch for ch in x if ch.isdigit())) for x in sections}
        missing = [n for n in range(1, max(nums) + 1) if n not in nums]
        print(f"Article numbers not found: {len(missing)} (omitted/repealed articles such as 31 are normal)")
        print("  " + ", ".join(map(str, missing[:60])) + (" ..." if len(missing) > 60 else ""))
        key = ["14", "19", "21", "21A", "32", "51A", "226", "243A", "300A", "370"]
        found = {c.section_number for c in chunks}
        lacking = [k for k in key if k not in found]
        lettered = sorted(x for x in found if x and not x.isdigit())
        print(f"Lettered articles found: {len(lettered)} (for example {', '.join(lettered[:8])})")
        print("Key articles check: " + ("all present" if not lacking else f"MISSING {', '.join(lacking)}"))
    for c in chunks[:2] + chunks[-2:]:
        print(f"\n--- {format_ref(c.act, c.section_number)} | {c.title} | part {c.part} | page {c.page}")
        print(c.content[:300])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--act", required=True, choices=ACTS)
    ap.add_argument("--file", required=True, help="path to the PDF")
    ap.add_argument("--dry-run", action="store_true", help="only show what would be stored")
    ap.add_argument("--min-sections", type=int, default=10)
    ap.add_argument("--allow-fallback", action="store_true",
                    help="store plain text pieces even when no section headings were found (not recommended)")
    ap.add_argument("--allow-bill", action="store_true",
                    help="load a Bill even though its section numbers differ from the final law (not recommended)")
    args = ap.parse_args()

    print(f"Reading {args.file} ...")
    pages = read_pdf_pages(args.file)
    total_chars = sum(len(p) for p in pages)
    print(f"Pages: {len(pages)}, characters: {total_chars}")
    if total_chars < 2000:
        print("ERROR: almost no text found. This looks like a scanned PDF (images). Use a text version.")
        return 1

    if looks_like_bill(pages) and not args.allow_bill:
        print("\nERROR: this file is a BILL (a draft), not the final law.")
        print("Bills use different section numbers from the Act that was passed, so citations would be WRONG.")
        print("Download the final Act text instead (India Code, 'Act No. 45 of 2023' for BNS, 'Act No. 46 of 2023' for BNSS).")
        return 1

    chunks, mode = chunk_document(pages, args.act, args.min_sections, recover=True)
    describe(chunks, mode, args.act)
    if mode == "fallback" and not args.dry_run and not args.allow_fallback:
        print("\nERROR: no section headings were found, so section numbers would be missing from every citation.")
        print("Use the official text PDF of the final Act. Send me the dry-run output if you think this file is right.")
        return 1
    if args.dry_run:
        print("\nDry run: nothing was stored. If the numbers above look right, run again without --dry-run.")
        return 0
    if not chunks:
        print("ERROR: no chunks produced.")
        return 1

    print(f"\nEmbedding {len(chunks)} chunks (this uses a small amount of OpenAI credit) ...")
    vectors: list[list[float]] = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i : i + BATCH]
        vectors += embed_texts([embedding_text(c) for c in batch])
        print(f"  {min(i + BATCH, len(chunks))}/{len(chunks)}", end="\r", flush=True)
        time.sleep(0.2)
    print()

    rows = [
        (c.act, c.section_number, c.title, c.part, c.content, c.page, "[" + ",".join(f"{x:.7f}" for x in v) + "]")
        for c, v in zip(chunks, vectors)
    ]
    print("Saving to the database (replaces any old data for this act) ...")
    with psycopg.connect(get_settings().database_url, prepare_threshold=None) as conn:
        with conn.transaction():
            conn.execute("DELETE FROM chunks WHERE act = %s", (args.act,))
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO chunks (act, section_number, title, part, content, page, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s::vector)""",
                    rows,
                )
    print(f"Done. Stored {len(rows)} chunks for {args.act}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
