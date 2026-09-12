"""Fixtures des tests : aucun stub nécessaire, seolib n'utilise que la bibliothèque standard."""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seolib import config  # noqa: E402


@pytest.fixture
def content_dir(tmp_path, monkeypatch):
    """Isole tous les chemins de config dans un répertoire temporaire.

    Les modules lisent `config.X` au moment de l'appel, donc remplacer l'attribut
    suffit : aucun argument à passer dans les tests.
    """
    content = tmp_path / "content"
    content.mkdir()
    monkeypatch.setattr(config, "CONTENT_DIR", content)
    monkeypatch.setattr(config, "AUDIT_DIR", tmp_path / "audit-seo")
    monkeypatch.setattr(config, "PROPOSALS_FILE", tmp_path / "propositions_seo.md")
    monkeypatch.setattr(config, "ARCHIVE_DIR", tmp_path / ".archives_seo")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / ".backups_seo")
    return content


@pytest.fixture
def write_page(content_dir):
    """Écrit une page Hugo dans le content/ temporaire et retourne son chemin."""

    def _write(name, front_matter, body="Corps de page suffisamment long pour être exploitable."):
        path = content_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\n{front_matter}\n---\n\n{body}\n", encoding="utf-8")
        return path

    return _write
