from pathlib import Path

from gpt2json import __version__
from scripts import clean_workspace as cleaner


def test_clean_workspace_dry_run_does_not_delete(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cleaner, "ROOT", tmp_path)
    generated = tmp_path / "build"
    generated.mkdir()

    messages = cleaner.clean_workspace(dry_run=True)

    assert generated.exists()
    assert any(message == "would remove build" for message in messages)


def test_clean_workspace_apply_removes_generated_dirs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cleaner, "ROOT", tmp_path)
    generated = tmp_path / "packaging" / "windows" / "build"
    generated.mkdir(parents=True)
    (generated / "old.exe").write_text("old", encoding="utf-8")

    messages = cleaner.clean_workspace(dry_run=False)

    assert not generated.exists()
    assert any(message == "removed packaging/windows/build" for message in messages)


def test_clean_workspace_release_old_keeps_current_assets(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(cleaner, "ROOT", tmp_path)
    release = tmp_path / "release"
    release.mkdir()
    current = release / f"GPT2JSON-Setup-v{__version__}.exe"
    old = release / "GPT2JSON-Setup-v0.0.1.exe"
    current.write_text("current", encoding="utf-8")
    old.write_text("old", encoding="utf-8")

    messages = cleaner.clean_workspace(dry_run=False, release_old=True)

    assert current.exists()
    assert not old.exists()
    assert any(message == "removed release/GPT2JSON-Setup-v0.0.1.exe" for message in messages)
