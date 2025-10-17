import _bootstrap  # noqa: F401

from poetry_assistant.search import SearchEngine, SearchOptions


def test_exact_rhyme_search(sample_db):
    engine = SearchEngine(sample_db)
    options = SearchOptions(pattern="AE1 T", pattern_type="rhyme", syllables=1, limit=10)
    results = engine.search(options)
    words = {result.word for result in results}
    assert {"cat", "bat"}.issubset(words)
    # ensure definitions are included
    assert results[0].definitions


def test_near_rhyme_distance(sample_db):
    engine = SearchEngine(sample_db)
    options = SearchOptions(pattern="AE1 T", pattern_type="rhyme", syllables=1, max_distance=1, limit=10)
    results = engine.search(options)
    words = {result.word for result in results}
    assert "bad" in words  # AE1 D should be within distance 1 of AE1 T


def test_stress_filter(sample_db):
    engine = SearchEngine(sample_db)
    options = SearchOptions(pattern="*", pattern_type="rhyme", syllables=1, stress_pattern="1")
    results = engine.search(options)
    assert all(result.stress_pattern.startswith("1") for result in results)


def test_rhyme_search_with_large_syllable_request(sample_db):
    engine = SearchEngine(sample_db)
    options = SearchOptions(pattern="AE1 T", pattern_type="rhyme", syllables=5, limit=10)
    results = engine.search(options)
    # No entries should match but the search should gracefully handle the request
    assert results == []


def test_syllable_pattern_exact(sample_db):
    engine = SearchEngine(sample_db)
    options = SearchOptions(pattern="[S P]-AY[1] D-ER[0]", pattern_type="syllable", limit=10)
    results = engine.search(options)
    assert [result.word for result in results] == ["spider"]
    assert results[0].matched_syllables == (0, 2)


def test_syllable_pattern_contains(sample_db):
    engine = SearchEngine(sample_db)
    options = SearchOptions(pattern="*-AW[1]/*", pattern_type="syllable", contains=True, limit=10)
    results = engine.search(options)
    words = [result.word for result in results]
    assert "about" in words
    about_result = next(result for result in results if result.word == "about")
    assert about_result.matched_syllables == (1, 2)


def test_syllable_pattern_ignore_stress(sample_db):
    engine = SearchEngine(sample_db)
    strict = SearchOptions(pattern="D-ER*[1]", pattern_type="syllable", contains=True, limit=10)
    relaxed = SearchOptions(
        pattern="D-ER*[1]",
        pattern_type="syllable",
        contains=True,
        ignore_stress=True,
        limit=10,
    )
    strict_results = engine.search(strict)
    relaxed_results = engine.search(relaxed)
    assert all(result.word != "spider" for result in strict_results)
    assert any(result.word == "spider" for result in relaxed_results)


def test_three_syllable_vowel_options(sample_db):
    # add entries that exercise multi-option vowel matching with explicit stress blocks
    heavenly = sample_db.add_word("heavenly")
    sample_db.add_pronunciation(heavenly, "HH EH1 V AH0 N L IY0".split())
    seventeen = sample_db.add_word("seventeen")
    sample_db.add_pronunciation(seventeen, "S EH1 V AH0 N T IY1 N".split())
    memory = sample_db.add_word("memory")
    sample_db.add_pronunciation(memory, "M EH1 M ER0 IY0".split())

    engine = SearchEngine(sample_db)
    options = SearchOptions(
        pattern="*-EH[12]/* *-(AH|ER)[0]/* *-IY[012]/*",
        pattern_type="syllable",
        limit=10,
    )
    results = engine.search(options)
    words = {result.word for result in results}
    assert {"heavenly", "seventeen", "memory"}.issubset(words)
