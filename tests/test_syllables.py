import _bootstrap  # noqa: F401

from poetry_assistant.syllables import (
    find_syllable_matches,
    matches_syllable_pattern,
    parse_syllable_pattern,
    syllabify,
)


def test_syllabify_breaks_into_syllables():
    syllables = syllabify("S P AY1 D ER0")
    assert len(syllables) == 2
    first, second = syllables
    assert first.onset == ("S", "P")
    assert first.nucleus == "AY1"
    assert first.coda == ()
    assert second.onset == ("D",)
    assert second.nucleus == "ER0"
    assert second.coda == ()


def test_pattern_matching_exact_sequence():
    syllables = syllabify("S P AY1 D ER0")
    pattern = parse_syllable_pattern("[S P]-AY[1] D-ER[0]")
    matches = find_syllable_matches(syllables, pattern)
    assert matches == [(0, 2)]


def test_pattern_matching_with_contains():
    syllables = syllabify("AH0 B AW1 T")
    pattern = parse_syllable_pattern("*-AW[1]/*")
    matches = find_syllable_matches(syllables, pattern, contains=True)
    assert matches == [(1, 2)]


def test_ignore_stress_allows_mismatch():
    syllables = syllabify("S P AY1 D ER0")
    pattern = parse_syllable_pattern("D-ER*[1]")
    assert not matches_syllable_pattern(syllables, pattern, contains=True)
    assert matches_syllable_pattern(syllables, pattern, contains=True, ignore_stress=True)


def test_question_mark_requires_single_onset_phoneme():
    single_consonant = syllabify("G AW1 N")
    double_consonant = syllabify("B R AW1 N")
    pattern = parse_syllable_pattern("?-AW[1]/N")
    assert matches_syllable_pattern(single_consonant, pattern)
    assert not matches_syllable_pattern(double_consonant, pattern)


def test_second_consonant_can_be_constrained():
    pattern = parse_syllable_pattern("(* R)-AW[1]/N")
    brown = syllabify("B R AW1 N")
    drown = syllabify("D R AW1 N")
    gown = syllabify("G AW1 N")
    clown = syllabify("K L AW1 N")
    assert matches_syllable_pattern(brown, pattern)
    assert matches_syllable_pattern(drown, pattern)
    assert not matches_syllable_pattern(gown, pattern)
    assert not matches_syllable_pattern(clown, pattern)


def test_multi_letter_phonemes_match_with_wildcards():
    thrown = syllabify("TH R OW1 N")
    charm = syllabify("CH AA1 R M")
    pattern_second_r = parse_syllable_pattern("(* R)-OW[1]/N")
    single_onset_pattern = parse_syllable_pattern("?-AA[1]/(R M)")
    assert matches_syllable_pattern(thrown, pattern_second_r)
    assert matches_syllable_pattern(charm, single_onset_pattern)


def test_vowel_alternatives_match_multiple_words():
    pattern = parse_syllable_pattern("*-EH[1]/* *-[AH|ER][0]/* *-AE[1]/P")
    clever_rap = syllabify("K L EH1 V ER0 R AE1 P")
    mend_the_gap = syllabify("M EH1 N D DH AH0 G AE1 P")
    assert matches_syllable_pattern(clever_rap, pattern)
    assert matches_syllable_pattern(mend_the_gap, pattern)
