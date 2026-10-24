from app.ingestion.chunker import chunk_document, find_headings, split_text, _join_pages

# Imitates how Indian bare acts look after PDF text extraction.
def make_pages(n_sections=30):
    toc = " ".join(f"{i}. Heading number {i}." for i in range(1, n_sections + 1))  # table of contents: no .—
    body = []
    for i in range(1, n_sections + 1):
        body.append(
            f"{i}. Title of section {i}.—(1) Whoever does thing {i} shall be punished. "
            f"(2) For the purposes of this section, 1. (a) is not a heading and 2. foo bar is not either. "
            f"Illustration. A does it."
        )
    body.insert(21, "21A. Special added section.—This one carries a letter suffix.")
    page1 = "ARRANGEMENT OF SECTIONS " + toc
    page2 = " ".join(body[:15])
    page3 = " ".join(body[15:])
    return [page1, page2, page3]


def test_finds_all_sections_in_order_and_skips_toc():
    pages = make_pages(30)
    chunks, mode = chunk_document(pages, "BNS")
    assert mode == "sections"
    numbers = [c.section_number for c in chunks]
    assert numbers[0] == "1" and numbers[-1] == "30"
    assert "21A" in numbers
    assert numbers.index("21A") == numbers.index("21") + 1
    assert len(set(numbers)) == 31
    first = chunks[0]
    assert first.title == "Title of section 1"
    assert first.page == 2


def test_page_tracking():
    chunks, _ = chunk_document(make_pages(30), "BNS")
    by = {c.section_number: c.page for c in chunks}
    assert by["1"] == 2 and by["30"] == 3


def test_fake_subnumbers_not_treated_as_headings():
    full, _ = _join_pages(make_pages(12))
    heads = find_headings(full)
    assert [h[2] for h in heads if h[2] != "21A"] == [str(i) for i in range(1, 13)]
    assert all("is not" not in h[3] for h in heads)


def test_fallback_when_no_headings():
    pages = ["Just some plain text without any section headings at all. " * 100]
    chunks, mode = chunk_document(pages, "BNS")
    assert mode == "fallback" and chunks
    assert all(c.section_number is None for c in chunks)


def test_long_section_is_split_with_same_metadata():
    long_body = " ".join(f"Sentence number {i} about the offence." for i in range(200))
    pages = [f"1. Short title.—Hello world this is section one body text. 2. Long one.—{long_body} " +
             " ".join(f"{i}. T{i}.—Body text for section {i} goes here." for i in range(3, 14))]
    chunks, mode = chunk_document(pages, "BNS")
    long_parts = [c for c in chunks if c.section_number == "2"]
    assert mode == "sections"
    assert len(long_parts) > 1
    assert [c.part for c in long_parts] == list(range(1, len(long_parts) + 1))
    assert all(len(c.content) <= 1500 for c in chunks)


def test_split_text_terminates_and_overlaps():
    text = "word " * 3000
    pieces = split_text(text)
    assert len(pieces) > 5
    assert all(len(p) <= 1500 for _, p in pieces)
    assert split_text("") == []
    assert split_text("short") == [(0, "short")]
