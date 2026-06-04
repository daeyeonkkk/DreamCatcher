from pathlib import Path

from app.core.rawprep_contract import build_directory_layout
from app.core.studio_paths import resolve_output_path, resolve_output_root


def test_resolve_output_root_anchors_relative_paths_to_repo_root(monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    resolved = resolve_output_root("outputs")

    assert resolved == (tmp_path / "outputs").resolve()


def test_resolve_output_path_accepts_repo_relative_and_output_relative_paths(monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)
    target = tmp_path / "outputs" / "session_demo" / "02_manual" / "source.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"demo")

    assert resolve_output_path("outputs/session_demo/02_manual/source.png", output_root="outputs") == target.resolve()
    assert resolve_output_path("session_demo/02_manual/source.png", output_root="outputs") == target.resolve()


def test_build_directory_layout_returns_absolute_session_paths(monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.studio_paths.repo_root", lambda: tmp_path)

    layout = build_directory_layout("outputs", "session_demo")

    assert Path(layout.session_root) == (tmp_path / "outputs" / "session_demo").resolve()
    assert Path(layout.input_dir) == (tmp_path / "outputs" / "session_demo" / "00_input").resolve()
