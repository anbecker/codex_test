from pathlib import Path

from poetry_assistant import cli


def test_ingest_accepts_database_option_in_any_position(monkeypatch, tmp_path):
    calls: list[Path] = []

    def fake_build_database(
        *,
        database_path,
        cmu_source=None,
        download_if_missing=True,
        include_wordnet=True,
    ):
        calls.append(Path(database_path))

    monkeypatch.setattr(cli, "build_database", fake_build_database)

    db_path = tmp_path / "cli.db"

    cli.main(["ingest", "--database", str(db_path)])
    assert calls and calls[-1] == db_path

    calls.clear()

    cli.main(["--database", str(db_path), "ingest"])
    assert calls and calls[-1] == db_path
