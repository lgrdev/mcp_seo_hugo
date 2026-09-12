"""Lecture du contenu Hugo : front matter, périmètre SEO, découpage en paragraphes.

Aucune dépendance hors bibliothèque standard : le plugin doit fonctionner sans
`pip install`. Le front matter est lu par un mini-lecteur volontairement limité,
pas par un vrai parseur YAML (voir `read_front_matter`).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

# Le front matter du corpus est riche (maps imbriquées, tableaux JSON multi-lignes),
# mais le SEO n'a besoin que de clés scalaires ou de listes simples de premier niveau.
# Tout ce qui est indenté et n'est pas un item de liste est donc ignoré, pas interprété.
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")
_LIST_ITEM_RE = re.compile(r"^\s+-\s+(.*)$")
_FRONT_MATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", re.DOTALL)

_BOOLS = {"true": True, "false": False, "yes": True, "no": False, "on": True, "off": False}


@dataclass(frozen=True)
class Chunk:
    """Un paragraphe indexable, rattaché à sa page."""

    source_path: str
    title: str
    text: str


def _scalar(raw: str):
    """Convertit une valeur de front matter en bool, None ou chaîne nettoyée."""
    value = raw.strip()
    if not value.startswith(("\"", "'")) and " #" in value:
        value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    lowered = value.lower()
    if lowered in _BOOLS:
        return _BOOLS[lowered]
    if lowered in ("", "null", "~"):
        return None
    return value


def read_front_matter(text: str) -> tuple[dict, str]:
    """Retourne (clés de premier niveau, corps). Sans front matter : ({}, texte entier).

    Le lecteur reconnaît `clé: valeur` non indenté et les listes `  - item` qui suivent
    une clé sans valeur. Tout le reste est ignoré : une clé absente redonne le même
    comportement de repli qu'une valeur vide, jamais une exception.
    """
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text

    meta: dict = {}
    pending_list_key = None

    for line in match.group(1).splitlines():
        if not line.strip():
            continue

        item = _LIST_ITEM_RE.match(line)
        if item and pending_list_key:
            meta[pending_list_key].append(_scalar(item.group(1)))
            continue
        if line[:1].isspace():
            # Bloc imbriqué hors périmètre (faq, liens_utiles, tableau JSON...).
            continue

        key_match = _KEY_RE.match(line)
        if not key_match:
            pending_list_key = None
            continue

        key, raw = key_match.group(1), key_match.group(2)
        if raw.strip() == "":
            # Une clé sans valeur ouvre soit une liste, soit un bloc imbriqué ignoré.
            meta[key] = []
            pending_list_key = key
        else:
            meta[key] = _scalar(raw)
            pending_list_key = None

    return meta, text[match.end():]


def load_pages(content_dir: Path | None = None) -> tuple[dict, list[dict]]:
    """Parse content/**/*.md une seule fois. Retourne (pages retenues, fichiers ignorés + raison)."""
    content_dir = content_dir or config.CONTENT_DIR
    pages: dict[str, dict] = {}
    skipped: list[dict] = []

    for md_file in sorted(content_dir.rglob("*.md")):
        rel_path = str(md_file.relative_to(content_dir))
        try:
            text = md_file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            skipped.append({"path": rel_path, "reason": f"encodage invalide ({exc.reason})"})
            continue
        except OSError as exc:
            skipped.append({"path": rel_path, "reason": f"lecture impossible ({exc})"})
            continue

        meta, body = read_front_matter(text)

        if meta.get("draft", False):
            skipped.append({"path": rel_path, "reason": "draft"})
            continue
        if not meta.get("option_seo", True):
            skipped.append({"path": rel_path, "reason": "option_seo: false"})
            continue
        # Une page en noindex n'a pas à être maillée : inutile d'exiger option_seo en plus.
        if "noindex" in str(meta.get("robots", "") or "").lower():
            skipped.append({"path": rel_path, "reason": "robots: noindex"})
            continue

        aliases = meta.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        pages[rel_path] = {
            "title": str(meta.get("title") or md_file.stem),
            "slug": str(meta.get("slug") or md_file.stem),
            "aliases": [str(alias).strip("/") for alias in aliases if alias],
            "description": str(meta.get("description") or ""),
            "content": body,
        }

    return pages, skipped


def unreadable(skipped: list[dict]) -> list[dict]:
    """Sous-ensemble des exclusions qui relèvent d'un fichier cassé, pas d'un choix éditorial."""
    return [item for item in skipped
            if item["reason"].startswith(("encodage", "lecture impossible"))]


def is_list_block(block: str) -> bool:
    """Bloc majoritairement composé de puces : mauvais support pour une ancre in-prose."""
    lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
    if not lines:
        return False
    bullets = sum(1 for line in lines if re.match(r"^([-*+]|\d+[.)])\s", line))
    return bullets > len(lines) / 2


def build_chunks(pages: dict) -> list[Chunk]:
    """Découpe les pages en paragraphes candidats à l'accueil d'un lien."""
    chunks: list[Chunk] = []
    seen: set[tuple[str, str]] = set()

    for rel_path, data in pages.items():
        cleaned = re.sub(r"```.*?```", "", data["content"], flags=re.DOTALL)
        cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", cleaned)
        cleaned = re.sub(r"#+\s+.*", "", cleaned)

        for block in cleaned.split("\n\n"):
            text = block.strip()
            if len(text) < config.MIN_CHUNK_CHARS or is_list_block(text):
                continue
            if (rel_path, text) in seen:
                continue
            seen.add((rel_path, text))
            chunks.append(Chunk(source_path=rel_path, title=data["title"], text=text))

    return chunks
