from poetry_assistant.ingest import build_database


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
