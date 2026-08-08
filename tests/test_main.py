from pathlib import Path
import sys


def test_ensure_project_root_on_path_adds_repo_root(monkeypatch):
    from src.main import _ensure_project_root_on_path

    repo_root = str(Path(__file__).resolve().parents[1])
    monkeypatch.setattr(sys, "path", [p for p in sys.path if p != repo_root])

    _ensure_project_root_on_path()

    assert repo_root in sys.path
