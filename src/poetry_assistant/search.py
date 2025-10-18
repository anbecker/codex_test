"""Search utilities for rhyme and phonetic exploration."""
from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from .database import PoetryDatabase
from .models import SearchResult
from .phonetics import Pronunciation, similarity, tokens
from .syllables import (
    PatternElement,
    find_syllable_matches,
    parse_syllable_pattern,
    syllabify,
)


MAX_PRECOMPUTED_RHYME_KEY = 4


@dataclass
class SearchOptions:
    pattern: Optional[str] = None
    pattern_type: str = "rhyme"
    syllables: int = 1
    regex: bool = False
    contains: bool = False
    max_distance: Optional[int] = None
    min_similarity: Optional[float] = None
    stress_pattern: Optional[str] = None
    ignore_stress: bool = False
    part_of_speech: Optional[str] = None
    definition_query: Optional[str] = None
    synonym_query: Optional[str] = None
    limit: Optional[int] = 50


class SearchEngine:
    """Search interface backed by :class:`PoetryDatabase`."""

    def __init__(self, db: PoetryDatabase):
        self.db = db

    def search(self, options: SearchOptions) -> List[SearchResult]:
        rows = self.db.iter_pronunciations(
            part_of_speech=options.part_of_speech,
            definition_query=options.definition_query,
            synonym_query=options.synonym_query,
        )
        results: List[SearchResult] = []
        syllable_pattern: Optional[List[PatternElement]] = None
        if options.pattern_type == "syllable":
            syllable_pattern = parse_syllable_pattern(options.pattern or "")
        for row in rows:
            score = None
            match_span: Optional[Tuple[int, int]] = None
            if options.pattern_type == "syllable":
                syllables = syllabify(row["pronunciation"].split())
                assert syllable_pattern is not None
                matches = find_syllable_matches(
                    syllables,
                    syllable_pattern,
                    contains=options.contains,
                    ignore_stress=options.ignore_stress,
                )
                if not matches:
                    continue
                match_span = matches[0]
                score = 1.0 if syllable_pattern else None
            else:
                sequence = self._sequence_from_row(row, options)
                if sequence is None:
                    continue
                pattern_match = True
                if options.pattern:
                    pattern_match = self._matches_pattern(sequence, options)
                    near_enabled = options.max_distance is not None or options.min_similarity is not None
                    if not pattern_match and not near_enabled:
                        continue
            if options.stress_pattern:
                if not match_wildcard(row["stress_pattern"] or "", options.stress_pattern):
                    continue
            if options.pattern_type != "syllable":
                if options.pattern and options.max_distance is not None:
                    distance = _edit_distance(sequence, options.pattern)
                    if distance > options.max_distance:
                        continue
                    seq_tokens = sequence.split()
                    pattern_tokens = tokens(options.pattern)
                    normalizer = max(len(seq_tokens), len(pattern_tokens) or 1)
                    score = 1.0 - distance / normalizer if normalizer else 1.0
                elif options.pattern and options.min_similarity is not None:
                    score = similarity(sequence.split(), tokens(options.pattern))
                    if score < options.min_similarity:
                        continue
                elif options.pattern:
                    if not pattern_match:
                        continue
                    score = 1.0
            result = SearchResult(
                word_id=row["word_id"],
                word=row["word"],
                pronunciation=row["pronunciation"],
                syllable_count=row["syllable_count"],
                stress_pattern=row["stress_pattern"],
                similarity=score,
                terminal_vowels=row["terminal_vowels"],
                terminal_consonants=row["terminal_consonants"],
                rhyme_key=row["rhyme_key_1"],
                matched_syllables=match_span,
            )
            results.append(result)
            if options.limit is not None and len(results) >= options.limit and not options.pattern:
                break
        results.sort(key=self._result_sort_key)
        limit = options.limit
        limited = results if limit is None else results[:limit]
        self._attach_definitions(limited)
        return limited

    def perfect_rhyme_matches(
        self,
        key: str,
        *,
        part_of_speech: Optional[str] = None,
        limit: Optional[int] = 50,
        exclude_word_ids: Optional[Iterable[int]] = None,
    ) -> List[SearchResult]:
        """Return pronunciations whose perfect rhyme key matches ``key``."""

        excluded: Set[int] = set(exclude_word_ids or [])
        rows = self.db.iter_pronunciations(part_of_speech=part_of_speech)
        results: List[SearchResult] = []
        for row in rows:
            word_id = int(row["word_id"])
            if word_id in excluded:
                continue
            pronunciation = Pronunciation(tuple(row["pronunciation"].split()))
            if pronunciation.perfect_rhyme_key() != key:
                continue
            result = SearchResult(
                word_id=word_id,
                word=row["word"],
                pronunciation=row["pronunciation"],
                syllable_count=row["syllable_count"],
                stress_pattern=row["stress_pattern"],
                similarity=1.0,
                terminal_vowels=row["terminal_vowels"],
                terminal_consonants=row["terminal_consonants"],
                rhyme_key=row["rhyme_key_1"],
            )
            results.append(result)
        results.sort(key=self._result_sort_key)
        limited = results if limit is None else results[:limit]
        self._attach_definitions(limited)
        return limited

    @staticmethod
    def _result_sort_key(result: SearchResult) -> tuple:
        score = result.similarity if result.similarity is not None else float("-inf")
        return (-result.syllable_count, -score, result.word)

    # ------------------------------------------------------------------
    def _sequence_from_row(self, row, options: SearchOptions) -> Optional[str]:
        syllables = max(1, options.syllables)
        if options.pattern_type == "vowel":
            return row["terminal_vowels"]
        if options.pattern_type == "consonant":
            return row["terminal_consonants"]
        if options.pattern_type == "both":
            return row["terminal_both"]
        if options.pattern_type == "rhyme":
            if syllables <= MAX_PRECOMPUTED_RHYME_KEY:
                column = f"rhyme_key_{syllables}"
                return row[column]
            pronunciation = Pronunciation(tuple(row["pronunciation"].split()))
            return pronunciation.rhyme_key(syllables)
        if options.pattern_type == "phonemes":
            return row["pronunciation"]
        return None

    def _matches_pattern(self, sequence: str | None, options: SearchOptions) -> bool:
        if sequence is None:
            return False
        if options.regex:
            target = " ".join(sequence.split())
            matcher = re.search if options.contains else re.fullmatch
            return matcher(options.pattern, target) is not None
        text = " ".join(sequence.split())
        pattern = options.pattern
        if options.contains and not any(ch in pattern for ch in "*?[]"):
            pattern = f"*{pattern}*"
        return fnmatch.fnmatchcase(text, pattern)

    def _attach_definitions(self, results: Sequence[SearchResult]) -> None:
        unique_ids = []
        index_map = {}
        for result in results:
            if result.word_id not in index_map:
                index_map[result.word_id] = []
                unique_ids.append(result.word_id)
            index_map[result.word_id].append(result)
        definitions = self.db.load_definitions(unique_ids)
        for word_id, defs in definitions.items():
            for result in index_map.get(word_id, []):
                result.definitions = defs


def _edit_distance(sequence: str, pattern: str) -> int:
    seq_tokens = sequence.split()
    pattern_tokens = tokens(pattern)
    return _levenshtein(seq_tokens, pattern_tokens)


def _levenshtein(left: Sequence[str], right: Sequence[str]) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for i, token in enumerate(left, start=1):
        row = [i]
        for j, other in enumerate(right, start=1):
            cost = 0 if token == other else 1
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + cost))
        previous = row
    return previous[-1]


def match_wildcard(text: str, pattern: str) -> bool:
    """Match ``pattern`` treating ``*`` as multi-character wildcard."""

    if not pattern:
        return True
    return fnmatch.fnmatchcase(text, pattern)

