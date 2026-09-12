"""Graphe du maillage interne, en dictionnaires.

NetworkX n'était utilisé que pour des degrés et des prédécesseurs : deux dicts
`source -> cible -> ancre` suffisent et suppriment une dépendance.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "tel:", "#")


@dataclass
class Site:
    """Pages du périmètre SEO et liens internes résolus entre elles."""

    pages: dict = field(default_factory=dict)
    out: dict = field(default_factory=dict)          # source -> {cible: ancre}
    inbound: dict = field(default_factory=dict)      # cible -> {source: ancre}
    skipped: list = field(default_factory=list)
    unresolved: list = field(default_factory=list)

    def in_degree(self, path: str) -> int:
        return len(self.inbound.get(path, {}))

    def out_degree(self, path: str) -> int:
        return len(self.out.get(path, {}))

    def predecessors(self, path: str) -> list[str]:
        return sorted(self.inbound.get(path, {}))

    def title(self, path: str) -> str:
        return self.pages[path]["title"]

    def slug(self, path: str) -> str:
        return self.pages[path]["slug"]

    @property
    def node_count(self) -> int:
        return len(self.pages)

    @property
    def edge_count(self) -> int:
        return sum(len(targets) for targets in self.out.values())

    def orphans(self) -> list[str]:
        """Pages sans aucun lien entrant, `_index.md` exclus."""
        return [path for path in self.pages
                if self.in_degree(path) == 0 and not _is_index(path)]

    def underlinked(self) -> list[str]:
        """Pages avec exactement un lien entrant, `_index.md` exclus."""
        return [path for path in self.pages
                if self.in_degree(path) == 1 and not _is_index(path)]

    def link_targets(self) -> list[str]:
        """Cibles à mailler en priorité : les moins liées d'abord."""
        candidates = [path for path in self.pages
                      if self.in_degree(path) <= config.UNDERLINKED_MAX_IN_DEGREE
                      and not _is_index(path)]
        return sorted(candidates, key=lambda path: (self.in_degree(path), path))


def _is_index(path: str) -> bool:
    # Les `_index.md` reçoivent leurs liens entrants des templates Hugo, pas du corps
    # des articles : les compter comme orphelines gonflerait artificiellement la liste.
    return Path(path).stem == "_index"


def resolve_target(target: str, pages: dict) -> str | None:
    """Résout une cible de lien interne vers un chemin de page, par précédence stricte.

    Pas de correspondance par sous-chaîne : elle faisait résoudre `/audit/` vers trois
    pages différentes selon l'ordre du dictionnaire.
    """
    if not target:
        return None

    for path, data in pages.items():
        if data["slug"] == target:
            return path
    for path, data in pages.items():
        if target in data["aliases"]:
            return path
    if target in pages:
        return target
    if f"{target}.md" in pages:
        return f"{target}.md"
    for path in pages:
        if path.endswith(f"/{target}.md"):
            return path

    last_segment = target.rsplit("/", 1)[-1]
    if last_segment != target:
        for path, data in pages.items():
            if data["slug"] == last_segment or path.endswith(f"/{last_segment}.md"):
                return path

    return None


def build_site(pages: dict, skipped: list[dict]) -> Site:
    """Construit le graphe à partir d'un parse déjà fait."""
    site = Site(pages=pages, skipped=skipped)
    site.out = {path: {} for path in pages}
    site.inbound = {path: {} for path in pages}

    for source_path, data in pages.items():
        for anchor, target in _LINK_RE.findall(data["content"]):
            if target.startswith(_EXTERNAL_PREFIXES):
                continue
            target_clean = target.split("#")[0].split("?")[0].strip("/")
            resolved = resolve_target(target_clean, pages)
            if resolved is None:
                site.unresolved.append({"source": source_path, "target": target})
                continue
            if resolved == source_path:
                continue
            site.out[source_path][resolved] = anchor
            site.inbound[resolved][source_path] = anchor

    return site
