import pytest

from poetry_assistant.phonetics import Pronunciation, levenshtein_distance, similarity


def test_pronunciation_features():
    pron = Pronunciation(("K", "AE1", "T"))
    assert pron.syllable_count == 1
    assert pron.stress_pattern == "1"
    assert pron.rhyme_key(1) == "AE1 T"
    assert pron.terminal_vowels() == "AE1"
    assert pron.terminal_consonants() == "T"


def test_similarity_metrics():
    left = ["AE1", "T"]
    right = ["AE1", "D"]
    assert levenshtein_distance(left, right) == 1
    assert similarity(left, right) == pytest.approx(0.5)

