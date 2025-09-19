from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

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

