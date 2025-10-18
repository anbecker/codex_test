from pathlib import Path

import _bootstrap  # noqa: F401

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


def test_default_database_path_prefers_env_override(monkeypatch, tmp_path):
    env_path = tmp_path / "custom.db"
    monkeypatch.setenv("POETRY_ASSISTANT_DB", str(env_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    resolved = cli._default_database_path()
    assert resolved == env_path


def test_default_database_path_prefers_existing_files(monkeypatch, tmp_path):
    monkeypatch.delenv("POETRY_ASSISTANT_DB", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    home_dir = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    monkeypatch.chdir(tmp_path)

    local_db = tmp_path / "poetry_assistant.db"
    local_db.write_text("")

    resolved = cli._default_database_path()
    assert resolved == local_db


def test_default_database_path_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("POETRY_ASSISTANT_DB", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    home_dir = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

    resolved = cli._default_database_path()
    expected = tmp_path / "xdg" / "poetry_assistant" / "poetry_assistant.db"
    assert resolved == expected


def test_word_command_prints_syllables(sample_db, capsys):
    cli.main(["--database", str(sample_db.path), "word", "spider"])
    captured = capsys.readouterr().out
    assert "syllabified:" in captured
    assert "S P-AY[1]/- | D-ER[0]/-" in captured
