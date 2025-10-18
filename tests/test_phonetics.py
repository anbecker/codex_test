import pytest

import _bootstrap  # noqa: F401

from poetry_assistant.phonetics import Pronunciation, levenshtein_distance, similarity


def test_pronunciation_features():
    pron = Pronunciation(("K", "AE1", "T"))
    assert pron.syllable_count == 1
    assert pron.stress_pattern == "1"
    assert pron.rhyme_key(1) == "AE1 T"
    assert pron.terminal_vowels() == "AE1"
    assert pron.terminal_consonants() == "T"


def test_perfect_rhyme_key_uses_last_primary_stress():
    pron = Pronunciation(("P", "AH1", "S", "T", "EY2", "SH", "AH0", "N"))
    assert pron.perfect_rhyme_key() == "AH1 S T EY2 SH AH0 N"


def test_perfect_rhyme_key_requires_primary_stress():
    pron = Pronunciation(("B", "AH0", "T", "ER0", "F", "L", "AY2"))
    assert pron.perfect_rhyme_key() is None


def test_similarity_metrics():
    left = ["AE1", "T"]
    right = ["AE1", "D"]
    assert levenshtein_distance(left, right) == 1
    assert similarity(left, right) == pytest.approx(0.5)

