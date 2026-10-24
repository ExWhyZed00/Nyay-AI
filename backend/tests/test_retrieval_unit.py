from app.retrieval import build_or_tsquery, format_ref, parse_references, rrf_merge


def test_parse_section_with_act():
    assert parse_references("What is Section 103 BNS?") == [(["BNS"], ["103"])]


def test_parse_bnss_not_confused_with_bns():
    assert parse_references("section 35 of BNSS") == [(["BNSS"], ["35"])]


def test_parse_without_act_checks_both():
    assert parse_references("explain section 303") == [(["BNS", "BNSS"], ["303"])]


def test_parse_lists_and_articles():
    refs = parse_references("sections 103 and 105 BNS, also Article 21A")
    assert refs == [(["BNS"], ["103", "105"]), (["Constitution"], ["21A"])]


def test_old_laws_skip_exact_lookup():
    assert parse_references("IPC section 302") == []
    assert parse_references("what is section 41 of CrPC") == []


def test_no_reference():
    assert parse_references("someone stole my phone") == []


def test_tsquery():
    assert build_or_tsquery("What's the punishment for murder?!") == "what | the | punishment | for | murder"
    assert build_or_tsquery("??") is None
    assert "'" not in (build_or_tsquery("a'; drop table x; --") or "")


def test_rrf_prefers_chunks_found_by_several_lists():
    a, b, c = {"id": 1}, {"id": 2}, {"id": 3}
    merged = rrf_merge([[a, b], [c, b]], top_n=3)
    assert merged[0]["id"] == 2


def test_rrf_exact_weight_wins():
    a, b = {"id": 1}, {"id": 2}
    merged = rrf_merge([[a], [b]], weights=[2.0, 1.0], top_n=2)
    assert [m["id"] for m in merged] == [1, 2]


def test_format_ref():
    assert format_ref("BNS", "103") == "BNS Section 103"
    assert format_ref("Constitution", "21") == "Constitution Article 21"
    assert format_ref("BNS", None) == "BNS"
