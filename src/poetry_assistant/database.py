"""SQLite persistence for the poetry assistant."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

from .models import Definition
from .phonetics import Pronunciation, to_pronunciation

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS pronunciations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    pronunciation TEXT NOT NULL,
    syllable_count INTEGER NOT NULL,
    stress_pattern TEXT,
    terminal_vowels TEXT,
    terminal_consonants TEXT,
    terminal_both TEXT,
    rhyme_key_1 TEXT,
    rhyme_key_2 TEXT,
    rhyme_key_3 TEXT,
    rhyme_key_4 TEXT,
    phonemes_no_stress TEXT,
    FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE,
    UNIQUE(word_id, pronunciation)
);

CREATE TABLE IF NOT EXISTS definitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    part_of_speech TEXT,
    definition TEXT,
    example TEXT,
    source TEXT,
    FOREIGN KEY(word_id) REFERENCES words(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS synonyms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    definition_id INTEGER NOT NULL,
    synonym TEXT NOT NULL,
    FOREIGN KEY(definition_id) REFERENCES definitions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pronunciations_word_id ON pronunciations(word_id);
CREATE INDEX IF NOT EXISTS idx_pronunciations_rhyme1 ON pronunciations(rhyme_key_1);
CREATE INDEX IF NOT EXISTS idx_pronunciations_rhyme2 ON pronunciations(rhyme_key_2);
CREATE INDEX IF NOT EXISTS idx_pronunciations_rhyme3 ON pronunciations(rhyme_key_3);
CREATE INDEX IF NOT EXISTS idx_pronunciations_rhyme4 ON pronunciations(rhyme_key_4);
CREATE INDEX IF NOT EXISTS idx_definitions_word_id ON definitions(word_id);
CREATE INDEX IF NOT EXISTS idx_synonyms_definition_id ON synonyms(definition_id);
"""


class PoetryDatabase:
    """High level database manager."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def initialize(self) -> None:
        """Create schema if it does not already exist."""

        with self.conn:
            self.conn.executescript(SCHEMA)

    # ------------------------------------------------------------------
    # insert helpers
    # ------------------------------------------------------------------
    def add_word(self, word: str) -> int:
        """Insert word and return its database id."""

        word = word.lower()
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO words(word) VALUES (?)", (word,))
        row = self.conn.execute("SELECT id FROM words WHERE word = ?", (word,)).fetchone()
        if row is None:
            raise RuntimeError(f"Unable to persist word: {word}")
        return int(row[0])

    def add_pronunciation(self, word_id: int, pronunciation: Sequence[str] | str) -> None:
        pron = to_pronunciation(pronunciation)
        features = _pronunciation_features(pron)
        values = (
            word_id,
            pron.text,
            pron.syllable_count,
            pron.stress_pattern,
            features["terminal_vowels"],
            features["terminal_consonants"],
            features["terminal_both"],
            features.get("rhyme_key_1"),
            features.get("rhyme_key_2"),
            features.get("rhyme_key_3"),
            features.get("rhyme_key_4"),
            features["phonemes_no_stress"],
        )
        with self.conn:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO pronunciations (
                    word_id, pronunciation, syllable_count, stress_pattern,
                    terminal_vowels, terminal_consonants, terminal_both,
                    rhyme_key_1, rhyme_key_2, rhyme_key_3, rhyme_key_4,
                    phonemes_no_stress
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )

    def add_definition(
        self,
        word_id: int,
        part_of_speech: Optional[str],
        definition: str,
        example: Optional[str] = None,
        source: str = "wordnet",
        synonyms: Optional[Iterable[str]] = None,
    ) -> None:
        """Persist a definition and optional synonyms."""

        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO definitions(word_id, part_of_speech, definition, example, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                (word_id, part_of_speech, definition, example, source),
            )
            definition_id = int(cur.lastrowid)
            if synonyms:
                synonym_values = [(definition_id, s.lower()) for s in synonyms if s]
                self.conn.executemany(
                    "INSERT INTO synonyms(definition_id, synonym) VALUES (?, ?)",
                    synonym_values,
                )

    # ------------------------------------------------------------------
    # query helpers
    # ------------------------------------------------------------------
    def pronunciations_for_word(self, word: str) -> List[sqlite3.Row]:
        word = word.lower()
        query = """
            SELECT pronunciations.*
            FROM pronunciations
            JOIN words ON words.id = pronunciations.word_id
            WHERE words.word = ?
        """
        return list(self.conn.execute(query, (word,)))

    def load_definitions(self, word_ids: Sequence[int]) -> Dict[int, List[Definition]]:
        if not word_ids:
            return {}
        placeholders = ",".join("?" for _ in word_ids)
        query = f"""
            SELECT definitions.*, synonyms.synonym
            FROM definitions
            LEFT JOIN synonyms ON synonyms.definition_id = definitions.id
            WHERE definitions.word_id IN ({placeholders})
            ORDER BY definitions.id
        """
        result: Dict[int, List[Definition]] = {}
        rows = self.conn.execute(query, tuple(word_ids))
        current_defs: Dict[int, Definition] = {}
        for row in rows:
            definition_id = int(row["id"])
            word_id = int(row["word_id"])
            definition = current_defs.get(definition_id)
            if definition is None:
                definition = Definition(
                    word_id=word_id,
                    part_of_speech=row["part_of_speech"],
                    definition=row["definition"],
                    example=row["example"],
                    source=row["source"],
                )
                current_defs[definition_id] = definition
                result.setdefault(word_id, []).append(definition)
            synonym = row["synonym"]
            if synonym:
                definition.synonyms.append(synonym)
        return result

    def iter_pronunciations(
        self,
        part_of_speech: Optional[str] = None,
        definition_query: Optional[str] = None,
        synonym_query: Optional[str] = None,
    ) -> Iterator[sqlite3.Row]:
        """Iterate pronunciations optionally filtered by lexical information."""

        conditions: List[str] = []
        params: List[str] = []
        if part_of_speech:
            conditions.append(
                "EXISTS (SELECT 1 FROM definitions WHERE definitions.word_id = words.id AND definitions.part_of_speech = ?)"
            )
            params.append(part_of_speech)
        if definition_query:
            conditions.append(
                "EXISTS (SELECT 1 FROM definitions WHERE definitions.word_id = words.id AND definitions.definition LIKE ?)"
            )
            params.append(f"%{definition_query}%")
        if synonym_query:
            conditions.append(
                "EXISTS (SELECT 1 FROM synonyms JOIN definitions ON synonyms.definition_id = definitions.id WHERE definitions.word_id = words.id AND synonyms.synonym LIKE ?)"
            )
            params.append(f"%{synonym_query}%")

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f"""
            SELECT pronunciations.*, words.word, words.id as word_id
            FROM pronunciations
            JOIN words ON words.id = pronunciations.word_id
            {where_clause}
            ORDER BY words.word
        """
        return self.conn.execute(query, tuple(params))


def _pronunciation_features(pron: Pronunciation) -> Dict[str, Optional[str]]:
    features: Dict[str, Optional[str]] = {}
    features["terminal_vowels"] = pron.terminal_vowels(1)
    features["terminal_consonants"] = pron.terminal_consonants()
    features["terminal_both"] = pron.rhyme_key(1)
    for syllables in range(1, 5):
        features[f"rhyme_key_{syllables}"] = pron.rhyme_key(syllables)
    features["phonemes_no_stress"] = pron.strip_stress().text
    return features

