"""Utilities for working with ARPABET pronunciations and stresses."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

ARPABET_VOWELS = {
    "AA",
    "AE",
    "AH",
    "AO",
    "AW",
    "AY",
    "EH",
    "ER",
    "EY",
    "IH",
    "IY",
    "OW",
    "OY",
    "UH",
    "UW",
}


@dataclass(frozen=True)
class Pronunciation:
    """Structured representation of a pronunciation."""

    phonemes: Sequence[str]

    @property
    def text(self) -> str:
        """Return the pronunciation as a space separated string."""

        return " ".join(self.phonemes)

    @property
    def syllable_count(self) -> int:
        """Number of syllables in the pronunciation."""

        return sum(1 for p in self.phonemes if is_vowel(p))

    @property
    def stress_pattern(self) -> str:
        """Return stress digits for vowels in order."""

        stresses: List[str] = []
        for phoneme in self.phonemes:
            if is_vowel(phoneme):
                stress = phoneme[-1]
                stresses.append(stress if stress.isdigit() else "0")
        return "".join(stresses)

    def rhyme_key(self, syllables: int) -> Optional[str]:
        """Return the canonical rhyme key for the last ``syllables`` syllables."""

        indices = _vowel_indices(self.phonemes)
        if not indices or len(indices) < syllables:
            return None
        start = indices[-syllables]
        return " ".join(self.phonemes[start:])

    def perfect_rhyme_key(self) -> Optional[str]:
        """Return substring covering the final stressed syllable and any trailing syllables."""

        last_stressed: Optional[int] = None
        for index, phoneme in enumerate(self.phonemes):
            if not is_vowel(phoneme):
                continue
            stress = phoneme[-1] if phoneme[-1].isdigit() else "0"
            if stress in {"1", "2"}:
                last_stressed = index
        if last_stressed is None:
            return None
        return " ".join(self.phonemes[last_stressed:])

    def terminal_vowels(self, syllables: int = 1) -> Optional[str]:
        """Return the vowel portion of the final syllables."""

        indices = _vowel_indices(self.phonemes)
        if not indices or len(indices) < syllables:
            return None
        start = indices[-syllables]
        vowels: List[str] = []
        for phoneme in self.phonemes[start:]:
            if is_vowel(phoneme):
                vowels.append(phoneme)
        return " ".join(vowels) if vowels else None

    def terminal_consonants(self) -> str:
        """Return trailing consonant phonemes after the last vowel."""

        indices = _vowel_indices(self.phonemes)
        if not indices:
            return ""
        last_vowel_index = indices[-1]
        return " ".join(self.phonemes[last_vowel_index + 1 :])

    def strip_stress(self) -> "Pronunciation":
        """Return pronunciation with stress digits removed."""

        stripped = [strip_stress(p) for p in self.phonemes]
        return Pronunciation(tuple(stripped))


def tokens(pronunciation: str) -> List[str]:
    """Split a CMU pronunciation string into tokens."""

    return [part for part in pronunciation.strip().split() if part]


def is_vowel(phoneme: str) -> bool:
    """Return ``True`` if the phoneme represents a vowel."""

    base = strip_stress(phoneme)
    return base in ARPABET_VOWELS


def strip_stress(phoneme: str) -> str:
    """Remove stress digits from a phoneme."""

    return phoneme.rstrip("0123456789")


def _vowel_indices(phonemes: Sequence[str]) -> List[int]:
    return [index for index, phoneme in enumerate(phonemes) if is_vowel(phoneme)]


def to_pronunciation(pronunciation: Iterable[str] | str) -> Pronunciation:
    """Create a :class:`Pronunciation` instance from input."""

    if isinstance(pronunciation, str):
        phonemes = tokens(pronunciation)
    else:
        phonemes = list(pronunciation)
    return Pronunciation(tuple(phonemes))


def levenshtein_distance(left: Sequence[str], right: Sequence[str]) -> int:
    """Compute Levenshtein distance between two phoneme sequences."""

    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    prev_row = list(range(len(right) + 1))
    for i, token in enumerate(left, start=1):
        current_row = [i]
        for j, other in enumerate(right, start=1):
            cost = 0 if token == other else 1
            current_row.append(
                min(
                    current_row[-1] + 1,  # insertion
                    prev_row[j] + 1,  # deletion
                    prev_row[j - 1] + cost,  # substitution
                )
            )
        prev_row = current_row
    return prev_row[-1]


def similarity(left: Sequence[str], right: Sequence[str]) -> float:
    """Return a similarity score between 0 and 1 based on edit distance."""

    if not left and not right:
        return 1.0
    distance = levenshtein_distance(left, right)
    normalizer = max(len(left), len(right))
    if normalizer == 0:
        return 1.0
    return max(0.0, 1.0 - distance / normalizer)

