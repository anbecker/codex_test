from __future__ import annotations

import _bootstrap  # noqa: F401
import pytest

from poetry_assistant.database import PoetryDatabase


@pytest.fixture()
def sample_db(tmp_path):
    db_path = tmp_path / "poetry.db"
    db = PoetryDatabase(db_path)
    db.initialize()

    data = {
        "cat": {
            "pronunciations": ["K AE1 T"],
            "definitions": [("noun", "a small domesticated feline", ["feline"])],
        },
        "bat": {
            "pronunciations": ["B AE1 T"],
            "definitions": [("noun", "a nocturnal flying mammal", ["chiropteran"])],
        },
        "bad": {
            "pronunciations": ["B AE1 D"],
            "definitions": [("adjective", "of poor quality", ["inferior"])],
        },
        "battle": {
            "pronunciations": ["B AE1 T AH0 L"],
            "definitions": [("noun", "a fight between opposing forces", ["combat"])],
        },
        "about": {
            "pronunciations": ["AH0 B AW1 T"],
            "definitions": [("preposition", "on the subject of", ["regarding"])],
        },
        "spider": {
            "pronunciations": ["S P AY1 D ER0"],
            "definitions": [("noun", "an eight-legged arachnid", ["arachnid"])],
        },
        "amazing": {
            "pronunciations": ["AH0 M EY1 Z IH0 NG"],
            "definitions": [("adjective", "causing great surprise", ["astonishing"])],
        },
    }

    for word, details in data.items():
        word_id = db.add_word(word)
        for pronunciation in details["pronunciations"]:
            db.add_pronunciation(word_id, pronunciation.split())
        for part, definition, synonyms in details.get("definitions", []):
            db.add_definition(word_id, part, definition, synonyms=synonyms)

    try:
        yield db
    finally:
        db.close()

