"""Rend scripts/hugo_seo_mcp.py importable sans fastmcp ni chromadb.

Les tests couvrent la logique pure (ancres, parsing du rapport, résolution de
liens, filtres de contenu). Installer torch pour les exercer serait absurde, donc
les deux dépendances lourdes sont remplacées par des stubs minimaux.
"""

import sys
import types
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _install_stubs() -> None:
    fastmcp = types.ModuleType("fastmcp")

    class FastMCP:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def run(self, *args, **kwargs):
            pass

    fastmcp.FastMCP = FastMCP
    sys.modules.setdefault("fastmcp", fastmcp)

    chromadb = types.ModuleType("chromadb")

    class _Client:
        def get_or_create_collection(self, *args, **kwargs):
            return None

        def get_collection(self, *args, **kwargs):
            raise RuntimeError("collection absente (stub)")

        def create_collection(self, *args, **kwargs):
            return None

        def delete_collection(self, *args, **kwargs):
            pass

    chromadb.PersistentClient = lambda *args, **kwargs: _Client()
    sys.modules.setdefault("chromadb", chromadb)


_install_stubs()
sys.path.insert(0, str(SCRIPTS_DIR))

import hugo_seo_mcp  # noqa: E402


@pytest.fixture
def seo():
    return hugo_seo_mcp


@pytest.fixture
def content_dir(tmp_path, monkeypatch):
    """CONTENT_DIR et BACKUP_DIR isolés dans un répertoire temporaire."""
    content = tmp_path / "content"
    content.mkdir()
    monkeypatch.setattr(hugo_seo_mcp, "CONTENT_DIR", content)
    monkeypatch.setattr(hugo_seo_mcp, "BACKUP_DIR", tmp_path / ".backups_seo")
    return content
