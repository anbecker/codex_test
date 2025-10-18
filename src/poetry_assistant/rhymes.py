"""High level rhyme suggestions built on top of the search engine."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .database import PoetryDatabase
from .phonetics import Pronunciation
from .search import SearchEngine, SearchOptions

WORD_RE = re.compile(r"[A-Za-z']+")


class RhymeAssistant:
    """Combine pronunciation lookups and search queries."""

    def __init__(self, db: PoetryDatabase):
        self.db = db
        self.search = SearchEngine(db)

    def pronunciations_for_word(self, word: str) -> List[Pronunciation]:
        rows = self.db.pronunciations_for_word(word)
        return [Pronunciation(tuple(row["pronunciation"].split())) for row in rows]

    def suggest_rhymes(
        self,
        line: str,
        max_syllables: int = 3,
        max_results: int = 20,
        max_distance: Optional[int] = None,
        min_similarity: Optional[float] = None,
        part_of_speech: Optional[str] = None,
    ) -> Dict[int, List[str]]:
        """Suggest rhyming words for the final syllables of ``line``."""

        candidates = self._line_pronunciations(line)
        results: Dict[int, List[str]] = defaultdict(list)
        seen = set()
        for word_text, pron in candidates:
            syllable_count = pron.syllable_count
            for syllables in range(1, min(max_syllables, syllable_count) + 1):
                rhyme_key = pron.rhyme_key(syllables)
                if not rhyme_key:
                    continue
                options = SearchOptions(
                    pattern=rhyme_key,
                    pattern_type="rhyme",
                    syllables=syllables,
                    max_distance=max_distance,
                    min_similarity=min_similarity,
                    part_of_speech=part_of_speech,
                    limit=max_results,
                )
                matches = self.search.search(options)
                for match in matches:
                    if match.word.lower() == word_text.lower():
                        continue
                    key = (match.word.lower(), syllables)
                    if key in seen:
                        continue
                    seen.add(key)
                    formatted = _format_match(match)
                    if len(results[syllables]) < max_results:
                        results[syllables].append(formatted)
        return dict(sorted(results.items(), reverse=True))

    def _line_pronunciations(self, line: str) -> List[Tuple[str, Pronunciation]]:
        words = WORD_RE.findall(line.lower())
        pronunciations: List[Tuple[str, Pronunciation]] = []
        for word in reversed(words):
            rows = self.db.pronunciations_for_word(word)
            for row in rows:
                pronunciation = Pronunciation(tuple(row["pronunciation"].split()))
                pronunciations.append((word, pronunciation))
            if pronunciations:
                break
        return pronunciations


def _format_match(result) -> str:
    pieces = [result.word]
    if result.similarity is not None:
        pieces.append(f"(score={result.similarity:.2f})")
    stresses = result.stress_pattern or ""
    pieces.append(f"[{stresses}] {result.pronunciation}")
    if result.definitions:
        definition = result.definitions[0]
        gloss = definition.definition
        pieces.append(f"- {gloss}")
    return " ".join(pieces)

