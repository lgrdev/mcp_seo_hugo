"""Compare le mini-lecteur de front matter à PyYAML sur le corpus réel.

PyYAML sert d'oracle de test uniquement : il n'est pas une dépendance d'exécution.
Le test est ignoré si PyYAML est absent ou si le projet n'a pas de `content/`
(le plugin est installable sur n'importe quel projet Hugo, pas seulement celui-ci).
"""

import re
from pathlib import Path

import pytest

from seolib.content import read_front_matter

yaml = pytest.importorskip("yaml")

CORPUS = Path(__file__).resolve().parent.parent / "content"
SEO_KEYS = ("title", "slug", "draft", "option_seo", "robots", "aliases")
_BLOCK_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)

pytestmark = pytest.mark.skipif(not CORPUS.is_dir(), reason="pas de content/ dans ce projet")


def _corpus_files():
    return sorted(CORPUS.rglob("*.md"))


def test_mini_reader_agrees_with_pyyaml_on_the_seo_keys():
    compared, mismatches = 0, []

    for md_file in _corpus_files():
        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # fichier cassé : exclu du périmètre SEO de toute façon

        block = _BLOCK_RE.match(text)
        if not block:
            continue
        try:
            reference = yaml.safe_load(block.group(1)) or {}
        except yaml.YAMLError:
            continue  # PyYAML refuse : le mini-lecteur est plus tolérant, rien à comparer
        if not isinstance(reference, dict):
            continue

        meta, _ = read_front_matter(text)
        compared += 1
        for key in SEO_KEYS:
            expected = reference.get(key)
            found = meta.get(key)
            if key == "aliases":
                expected = [expected] if isinstance(expected, str) else (expected or [])
                found = [found] if isinstance(found, str) else (found or [])
            if expected in (None, "") and found in (None, "", []):
                continue
            if expected != found:
                mismatches.append(f"{md_file.name} [{key}] PyYAML={expected!r} mini={found!r}")

    assert compared > 0, "aucun fichier comparable dans content/"
    assert not mismatches, "\n".join(mismatches)


def test_mini_reader_never_raises_on_the_corpus():
    for md_file in _corpus_files():
        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        meta, body = read_front_matter(text)
        assert isinstance(meta, dict)
        assert isinstance(body, str)
