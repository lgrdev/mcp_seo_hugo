"""Rapport d'audit HTML du maillage interne."""

import html
from datetime import datetime
from pathlib import Path

from . import config
from .content import unreadable


def _rows(cells_per_row) -> str:
    return "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>"
        for cells in cells_per_row
    )


def _section(title: str, intro: str, headers: list[str], rows: str) -> str:
    if not rows:
        return ""
    head = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    intro_html = f"<p>{intro}</p>\n" if intro else ""
    return f"""<h2>{html.escape(title)}</h2>
{intro_html}<table>
<thead><tr>{head}</tr></thead>
<tbody>
{rows}
</tbody>
</table>
"""


def render_audit_html(site) -> str:
    orphans = site.orphans()
    underlinked = site.underlinked()
    broken = unreadable(site.skipped)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    orphan_section = _section(
        f"Pages orphelines ({len(orphans)})", "",
        ["Path", "Titre", "Slug"],
        _rows((path, site.title(path), site.slug(path)) for path in orphans),
    )
    underlinked_section = _section(
        f"Pages sous-maillées, 1 seul lien entrant ({len(underlinked)})", "",
        ["Path", "Titre", "Unique page entrante"],
        _rows((path, site.title(path), next(iter(site.predecessors(path)), ""))
              for path in underlinked),
    )
    degree_section = _section(
        f"Liens par page ({site.node_count})",
        "Triées par nombre de liens entrants croissant.",
        ["Path", "Titre", "Liens entrants", "Liens sortants"],
        _rows((path, site.title(path), site.in_degree(path), site.out_degree(path))
              for path in sorted(site.pages,
                                 key=lambda p: (site.in_degree(p), site.out_degree(p), p))),
    )
    broken_section = _section(
        f"Fichiers illisibles, exclus de l'analyse ({len(broken)})",
        "Ces pages n'apparaissent pas dans le graphe. "
        "Lance <code>/lgrdev-mcp-seo:repair-seo</code> pour corriger leur encodage.",
        ["Path", "Raison"],
        _rows((item["path"], item["reason"]) for item in broken),
    )
    unresolved_section = _section(
        f"Liens internes non résolus ({len(site.unresolved)})",
        "Cibles introuvables parmi les pages analysées : lien cassé, page en draft, "
        "page exclue par <code>option_seo: false</code>, ou fichier illisible.",
        ["Page source", "Cible du lien"],
        _rows((item["source"], item["target"]) for item in site.unresolved),
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Audit SEO - {generated_at}</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #222; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.5rem; text-align: left; }}
th {{ background: #f0f0f0; }}
.summary {{ margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>Audit SEO - Maillage interne</h1>
<p class="summary">Généré le {generated_at}</p>
<ul class="summary">
<li>Total pages : {site.node_count}</li>
<li>Total liens internes : {site.edge_count}</li>
<li>Pages orphelines : {len(orphans)}</li>
<li>Pages sous-maillées (1 lien entrant) : {len(underlinked)}</li>
<li>Fichiers illisibles exclus : {len(broken)}</li>
<li>Liens internes non résolus : {len(site.unresolved)}</li>
</ul>
<p class="summary">Les pages <code>_index.md</code> sont exclues des pages orphelines et sous-maillées :
leurs liens entrants viennent des templates Hugo, pas du corps des articles.</p>
{orphan_section}{underlinked_section}{degree_section}{broken_section}{unresolved_section}</body>
</html>
"""


def write_audit_report(site, audit_dir: Path | None = None) -> Path:
    audit_dir = audit_dir or config.AUDIT_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    file_path = audit_dir / f"audit_seo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    file_path.write_text(render_audit_html(site), encoding="utf-8")
    return file_path
