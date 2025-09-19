"""Dataclasses representing database records."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Definition:
    word_id: int
    part_of_speech: str
    definition: str
    example: Optional[str] = None
    source: str = "wordnet"
    synonyms: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    word_id: int
    word: str
    pronunciation: str
    syllable_count: int
    stress_pattern: str
    similarity: Optional[float]
    terminal_vowels: Optional[str]
    terminal_consonants: str
    rhyme_key: Optional[str]
    definitions: List[Definition] = field(default_factory=list)

