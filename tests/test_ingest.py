from poetry_assistant.database import PoetryDatabase
from poetry_assistant.ingest import build_database, ingest_cmudict, parse_cmudict


def test_build_database_creates_nested_directory(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "poetry.db"
    cmu_dict = tmp_path / "cmudict.sample"
    cmu_dict.write_text("CAT  K AE1 T\n")

    result = build_database(
        database_path=db_path,
        cmu_source=cmu_dict,
        download_if_missing=False,
        include_wordnet=False,
    )

    assert db_path.parent.exists()
    assert db_path.exists()
    assert result == db_path


def test_cmudict_ingest_tolerates_latin1_bytes(tmp_path):
    cmu_dict = tmp_path / "cmudict.sample"
    cmu_dict.write_bytes(
        b"CAT  K AE1 T\n;;; CAF\xC9 COMMENT\nDOG  D AO1 G\n"
    )

    entries = list(parse_cmudict(cmu_dict))
    assert entries == [
        ("cat", ["K", "AE1", "T"]),
        ("dog", ["D", "AO1", "G"]),
    ]

    db_path = tmp_path / "poetry.db"
    db = PoetryDatabase(db_path)
    db.initialize()
    try:
        ingest_cmudict(db, cmu_dict)
        pronunciations = db.pronunciations_for_word("cat")
        assert pronunciations
    finally:
        db.close()
