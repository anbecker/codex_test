import _bootstrap  # noqa: F401

from poetry_assistant.rhymes import RhymeAssistant


def test_rhyme_assistant(sample_db):
    assistant = RhymeAssistant(sample_db)
    line = "The curious cat"
    results = assistant.suggest_rhymes(line, max_syllables=2, max_results=5)
    keys = list(results.keys())
    assert keys == sorted(keys, reverse=True)
    assert 1 in results
    assert any("bat" in suggestion for suggestion in results[1])


def test_perfect_rhyme(sample_db):
    assistant = RhymeAssistant(sample_db)
    suggestions = assistant.perfect_rhymes("amazing", max_results=5)
    assert "AH0 M EY1 Z IH0 NG" in suggestions
    matches = suggestions["AH0 M EY1 Z IH0 NG"]
    assert any("blazing" in suggestion for suggestion in matches)
    assert all("amazing" not in suggestion for suggestion in matches)

