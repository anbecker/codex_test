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

