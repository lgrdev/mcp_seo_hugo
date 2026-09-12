import hashlib
import html
import re
import shutil
from datetime import datetime
from pathlib import Path
from fastmcp import FastMCP
import frontmatter
import networkx as nx
import chromadb

# Initialisation du serveur MCP
mcp = FastMCP("Hugo SEO Linking Agent")

CONTENT_DIR = Path("./content")
AUDIT_DIR = Path("./audit-seo")
PROPOSALS_FILE = Path("./propositions_seo.md")
ARCHIVE_DIR = Path("./.archives_seo")
BACKUP_DIR = Path("./.backups_seo")
UNDERLINKED_MAX_IN_DEGREE = 1
STOPWORDS = {
    "le", "la", "les", "de", "des", "du", "et", "pour", "avec", "sans",
    "vos", "votre", "une", "un", "en", "sur", "dans", "au", "aux", "par",
}

# Initialisation de ChromaDB (persistant sur disque pour aller plus vite)
chroma_client = chromadb.PersistentClient(path="./.chroma_seo")

# Le modèle par défaut de Chroma (all-MiniLM-L6-v2) est entraîné sur l'anglais :
# sur un corpus français, la similarité sémantique est nettement moins fiable.
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def _embedding_function():
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)


# --- FONCTIONS INTERNES ---
def load_pages() -> tuple[dict, list[dict]]:
    """Parse content/**/*.md une seule fois. Retourne (pages retenues, fichiers ignorés + raison)."""
    pages, skipped = {}, []

    for md_file in sorted(CONTENT_DIR.rglob("*.md")):
        rel_path = str(md_file.relative_to(CONTENT_DIR))
        try:
            post = frontmatter.load(md_file)
        except UnicodeDecodeError as exc:
            skipped.append({"path": rel_path, "reason": f"encodage invalide ({exc.reason})"})
            continue
        except Exception as exc:
            skipped.append({"path": rel_path, "reason": f"front matter illisible ({exc})"})
            continue

        if post.get("draft", False):
            skipped.append({"path": rel_path, "reason": "draft"})
            continue
        if not post.get("option_seo", True):
            skipped.append({"path": rel_path, "reason": "option_seo: false"})
            continue
        # Une page en noindex n'a pas à être maillée : inutile d'exiger option_seo en plus.
        if "noindex" in str(post.get("robots", "")).lower():
            skipped.append({"path": rel_path, "reason": "robots: noindex"})
            continue

        aliases = post.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        pages[rel_path] = {
            "title": post.get("title", md_file.stem),
            "slug": post.get("slug") or md_file.stem,
            "aliases": [str(a).strip("/") for a in aliases],
            "content": post.content,
        }

    return pages, skipped


def _resolve_target(target: str, pages: dict) -> str | None:
    """Résout une cible de lien interne vers un chemin de page, par précédence stricte."""
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


def build_graph() -> nx.DiGraph:
    """Graphe des liens internes. Diagnostics dans G.graph : skipped, unresolved."""
    pages, skipped = load_pages()
    return graph_from_pages(pages, skipped)


def graph_from_pages(pages: dict, skipped: list[dict]) -> nx.DiGraph:
    G = nx.DiGraph()
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    unresolved = []

    for rel_path, data in pages.items():
        G.add_node(rel_path, title=data["title"], slug=data["slug"])

    for source_path, data in pages.items():
        for text, target in link_pattern.findall(data["content"]):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_clean = target.split("#")[0].split("?")[0].strip("/")
            resolved = _resolve_target(target_clean, pages)
            if resolved:
                G.add_edge(source_path, resolved, anchor=text)
            else:
                unresolved.append({"source": source_path, "target": target})

    G.graph["skipped"] = skipped
    G.graph["unresolved"] = unresolved
    return G


def render_audit_html(G: nx.DiGraph, orphans: list[str], underlinked: list[str] | None = None) -> str:
    underlinked = underlinked or []
    rows = "\n".join(
        f"<tr><td>{html.escape(orphan)}</td>"
        f"<td>{html.escape(G.nodes[orphan]['title'])}</td>"
        f"<td>{html.escape(G.nodes[orphan]['slug'])}</td></tr>"
        for orphan in orphans
    )
    underlinked_rows = "\n".join(
        f"<tr><td>{html.escape(node)}</td>"
        f"<td>{html.escape(G.nodes[node]['title'])}</td>"
        f"<td>{html.escape(next(iter(G.predecessors(node)), ''))}</td></tr>"
        for node in underlinked
    )
    degree_rows = "\n".join(
        f"<tr><td>{html.escape(node)}</td>"
        f"<td>{html.escape(G.nodes[node]['title'])}</td>"
        f"<td>{G.in_degree(node)}</td><td>{G.out_degree(node)}</td></tr>"
        for node in sorted(G.nodes, key=lambda n: (G.in_degree(n), G.out_degree(n), n))
    )
    underlinked_section = f"""<h2>Pages sous-maillées, 1 seul lien entrant ({len(underlinked)})</h2>
<table>
<thead><tr><th>Path</th><th>Titre</th><th>Unique page entrante</th></tr></thead>
<tbody>
{underlinked_rows}
</tbody>
</table>
""" if underlinked else ""
    degree_section = f"""<h2>Liens par page ({G.number_of_nodes()})</h2>
<p>Triées par nombre de liens entrants croissant.</p>
<table>
<thead><tr><th>Path</th><th>Titre</th><th>Liens entrants</th><th>Liens sortants</th></tr></thead>
<tbody>
{degree_rows}
</tbody>
</table>
"""
    skipped = G.graph.get("skipped", [])
    unreadable = [s for s in skipped if s["reason"].startswith(("encodage", "front matter"))]
    unresolved = G.graph.get("unresolved", [])

    skipped_rows = "\n".join(
        f"<tr><td>{html.escape(item['path'])}</td><td>{html.escape(item['reason'])}</td></tr>"
        for item in unreadable
    )
    unresolved_rows = "\n".join(
        f"<tr><td>{html.escape(item['source'])}</td><td>{html.escape(item['target'])}</td></tr>"
        for item in unresolved
    )
    skipped_section = f"""<h2>Fichiers illisibles, exclus de l'analyse ({len(unreadable)})</h2>
<p>Ces pages n'apparaissent ni dans le graphe ni dans l'index sémantique.
Utilise l'outil <code>repair_content_encoding</code> pour corriger leur encodage.</p>
<table>
<thead><tr><th>Path</th><th>Raison</th></tr></thead>
<tbody>
{skipped_rows}
</tbody>
</table>
""" if unreadable else ""
    unresolved_section = f"""<h2>Liens internes non résolus ({len(unresolved)})</h2>
<p>Cibles introuvables parmi les pages analysées : lien cassé, page en draft,
page exclue par <code>option_seo: false</code>, ou fichier illisible.</p>
<table>
<thead><tr><th>Page source</th><th>Cible du lien</th></tr></thead>
<tbody>
{unresolved_rows}
</tbody>
</table>
""" if unresolved else ""

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
<li>Total pages : {G.number_of_nodes()}</li>
<li>Total liens internes : {G.number_of_edges()}</li>
<li>Pages orphelines : {len(orphans)}</li>
<li>Pages sous-maillées (1 lien entrant) : {len(underlinked)}</li>
<li>Fichiers illisibles exclus : {len(unreadable)}</li>
<li>Liens internes non résolus : {len(unresolved)}</li>
</ul>
<p class="summary">Les pages <code>_index.md</code> sont exclues des pages orphelines et sous-maillées :
leurs liens entrants viennent des templates Hugo, pas du corps des articles.</p>
<h2>Pages orphelines ({len(orphans)})</h2>
<table>
<thead><tr><th>Path</th><th>Titre</th><th>Slug</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
{underlinked_section}{degree_section}{skipped_section}{unresolved_section}</body>
</html>
"""


def _is_list_block(block: str) -> bool:
    """Bloc majoritairement composé de puces : mauvais support pour une ancre in-prose."""
    lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
    if not lines:
        return False
    bullets = sum(1 for line in lines if re.match(r"^([-*+]|\d+[.)])\s", line))
    return bullets > len(lines) / 2


def _anchor_keywords(target_title: str) -> list[str]:
    """Phrases candidates pour l'ancre, de la plus longue à la plus courte."""
    tokens = (w.strip("-'’") for w in re.findall(r"[\wÀ-ÿ'’-]+", target_title))
    words = [w for w in tokens if any(c.isalnum() for c in w) and w.lower() not in STOPWORDS]
    candidates = []
    for size in range(min(4, len(words)), 0, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start:start + size])
            if len(phrase) >= 5:
                candidates.append(phrase)
    return candidates


def _insert_link(paragraph: str, target_title: str, target_slug: str) -> tuple[str, str]:
    """Insère un lien vers target_slug. Retourne (paragraphe, mode) avec mode = 'ancre' ou 'phrase'."""
    already_linked = [m.span() for m in re.finditer(r"\[[^\]]*\]\([^)]*\)", paragraph)]

    for phrase in _anchor_keywords(target_title):
        for match in re.finditer(re.escape(phrase), paragraph, flags=re.IGNORECASE):
            if any(start <= match.start() < end for start, end in already_linked):
                continue
            anchor = f"[{match.group(0)}]({target_slug})"
            return paragraph[:match.start()] + anchor + paragraph[match.end():], "ancre"

    return f"{paragraph} Pour aller plus loin : [{target_title}]({target_slug}).", "phrase"


PROPOSALS_HEADER = """# Propositions de maillage interne

Ce fichier est généré par l'outil MCP `generate_proposals_report`.

Pour valider une proposition, coche la case OUI : `- **Validation :** [x] OUI / [ ] NON`
Puis lance l'outil `apply_approved_proposals` : seules les propositions cochées OUI
seront appliquées dans les fichiers Markdown sources.

Une fois les modifications appliquées, `archive_proposals_report` déplace ce fichier
dans `.archives_seo/` et le réinitialise.
"""


def _render_proposals_report(proposals: list[dict]) -> str:
    parts = [PROPOSALS_HEADER]
    for idx, proposal in enumerate(proposals, start=1):
        parts.append(
            f"""## Proposition {idx}
- **Fichier source :** `{proposal['source_path']}`
- **Validation :** [ ] OUI / [ ] NON

### Paragraphe original :
```text
{proposal['old']}
```

### Paragraphe proposé :
```text
{proposal['new']}
```
---
"""
        )
    return "\n".join(parts)


def _parse_proposals(text: str) -> list[dict]:
    """Parse le rapport Markdown. Tolérant aux espaces, à la casse et aux lignes vides."""
    headings = list(re.finditer(r"^##\s+Proposition\s+(\S+)\s*$", text, flags=re.MULTILINE))
    proposals = []

    for pos, heading in enumerate(headings):
        start = heading.start()
        end = headings[pos + 1].start() if pos + 1 < len(headings) else len(text)
        block = text[start:end]

        source = re.search(r"\*\*Fichier\s+source\s*:?\s*\*\*\s*`?([^`\n]+?)`?\s*$", block,
                           flags=re.MULTILINE | re.IGNORECASE)
        fences = re.findall(r"```(?:text)?\s*\n(.*?)```", block, flags=re.DOTALL)
        status = re.search(r"\*\*Statut\s*:?\s*\*\*\s*(.+?)\s*$", block,
                           flags=re.MULTILINE | re.IGNORECASE)

        proposals.append({
            "id": heading.group(1),
            "block_start": start,
            "block_end": end,
            "source_path": source.group(1).strip() if source else None,
            "approved": bool(re.search(r"\[\s*[xX]\s*\]\s*OUI", block, flags=re.IGNORECASE)),
            "old": fences[0].rstrip("\n") if len(fences) >= 1 else None,
            "new": fences[1].rstrip("\n") if len(fences) >= 2 else None,
            "status": status.group(1).strip() if status else None,
        })

    return proposals


def _set_block_status(block: str, status: str) -> str:
    """Ajoute ou remplace la ligne de statut juste après la ligne de validation."""
    status_line = f"- **Statut :** {status}"
    if re.search(r"^-\s*\*\*Statut\s*:?\s*\*\*.*$", block, flags=re.MULTILINE | re.IGNORECASE):
        return re.sub(r"^-\s*\*\*Statut\s*:?\s*\*\*.*$", status_line, block,
                      count=1, flags=re.MULTILINE | re.IGNORECASE)
    return re.sub(r"^(-\s*\*\*Validation\s*:?\s*\*\*.*)$", rf"\1\n{status_line}", block,
                  count=1, flags=re.MULTILINE | re.IGNORECASE)


def build_chunks(pages: dict) -> tuple[list[str], list[dict], list[str]]:
    """Découpe les pages en paragraphes indexables. Aucun encodage : pur texte."""
    documents, metadatas, ids = [], [], []

    for rel_path, data in pages.items():
        cleaned = re.sub(r"```.*?```", "", data["content"], flags=re.DOTALL)
        cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", cleaned)
        cleaned = re.sub(r"#+\s+.*", "", cleaned)
        chunks = [p.strip() for p in cleaned.split("\n\n")
                  if len(p.strip()) >= 80 and not _is_list_block(p)]

        for chunk in chunks:
            # Identifiant dérivé du contenu : un paragraphe inchangé garde son id même si
            # un paragraphe est inséré avant lui, ce qui rend la réindexation incrémentale.
            chunk_id = f"{rel_path}#{hashlib.sha1(chunk.encode('utf-8')).hexdigest()[:12]}"
            if chunk_id in ids:
                continue
            documents.append(chunk)
            metadatas.append({"source_path": rel_path, "title": data["title"]})
            ids.append(chunk_id)

    return documents, metadatas, ids


def _sync_collection(embedding_function, documents: list[str], metadatas: list[dict],
                     ids: list[str]) -> dict:
    """Met l'index à jour en n'encodant que les paragraphes nouveaux ou modifiés."""
    try:
        col = chroma_client.get_collection("hugo_seo", embedding_function=embedding_function)
        # Un index construit avec un autre modèle n'est pas comparable : on le reconstruit.
        if (col.metadata or {}).get("embedding_model") != EMBEDDING_MODEL:
            chroma_client.delete_collection("hugo_seo")
            raise ValueError("modèle d'embeddings différent")
    except Exception:
        col = chroma_client.create_collection(
            "hugo_seo",
            embedding_function=embedding_function,
            metadata={"embedding_model": EMBEDDING_MODEL},
        )

    existing = set(col.get(include=[])["ids"])
    wanted = set(ids)

    obsolete = existing - wanted
    if obsolete:
        col.delete(ids=list(obsolete))

    new_positions = [pos for pos, chunk_id in enumerate(ids) if chunk_id not in existing]
    if new_positions:
        col.add(
            documents=[documents[pos] for pos in new_positions],
            metadatas=[metadatas[pos] for pos in new_positions],
            ids=[ids[pos] for pos in new_positions],
        )

    return {
        "added": len(new_positions),
        "removed": len(obsolete),
        "reused": len(wanted) - len(new_positions),
    }


def write_audit_report(G: nx.DiGraph, orphans: list[str], underlinked: list[str] | None = None) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"audit_seo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    file_path = AUDIT_DIR / filename
    file_path.write_text(render_audit_html(G, orphans, underlinked), encoding="utf-8")
    return file_path


# --- OUTILS MCP EXPOSÉS À CLAUDE ---

@mcp.tool()
def sync_and_get_site_audit() -> str:
    """Analyse le site Hugo, indexe les paragraphes dans ChromaDB et retourne la liste des pages orphelines et métriques SEO."""
    pages, skipped = load_pages()
    G = graph_from_pages(pages, skipped)

    # Réindexation ChromaDB, à partir du même parse que le graphe
    documents, metadatas, ids = build_chunks(pages)

    try:
        embedding_function = _embedding_function()
    except ImportError as exc:
        return (f"Erreur : sentence-transformers est requis pour l'index sémantique ({exc}). "
                f"Installe les dépendances : pip install -r requirements.txt")

    index_stats = _sync_collection(embedding_function, documents, metadatas, ids)

    # Les _index.md reçoivent leurs liens entrants par les templates Hugo, pas par le corps
    # des articles : les compter comme orphelines gonflerait artificiellement la liste.
    orphans = [node for node, in_deg in G.in_degree()
               if in_deg == 0 and Path(node).stem != "_index"]
    underlinked = [node for node, in_deg in G.in_degree()
                   if in_deg == 1 and Path(node).stem != "_index"]
    unreadable = [s for s in skipped if s["reason"].startswith(("encodage", "front matter"))]
    unresolved = G.graph["unresolved"]

    report_path = write_audit_report(G, orphans, underlinked)

    report = f"Total pages : {G.number_of_nodes()}\n"
    report += f"Total liens internes : {G.number_of_edges()}\n"
    report += (f"Paragraphes indexés : {len(ids)} "
               f"({index_stats['added']} encodés, {index_stats['reused']} réutilisés, "
               f"{index_stats['removed']} supprimés)\n")
    report += f"Pages orphelines ({len(orphans)}) :\n"
    for orphan in orphans:
        report += f"- Path: {orphan} | Titre: {G.nodes[orphan]['title']} | Slug: {G.nodes[orphan]['slug']}\n"

    if underlinked:
        report += f"\nPages sous-maillées, 1 seul lien entrant ({len(underlinked)}) :\n"
        for node in underlinked:
            report += f"- Path: {node} | Titre: {G.nodes[node]['title']}\n"

    if unreadable:
        report += f"\nFichiers illisibles, exclus de l'analyse ({len(unreadable)}) :\n"
        for item in unreadable:
            report += f"- {item['path']} : {item['reason']}\n"
        report += "Lance repair_content_encoding pour corriger l'encodage.\n"

    if unresolved:
        report += f"\nLiens internes non résolus ({len(unresolved)}) : cibles inexistantes ou hors périmètre SEO.\n"

    report += f"\nRapport HTML : {report_path}\n"

    return report


@mcp.tool()
def find_link_opportunities(target_path: str, top_k: int = 3) -> list[dict]:
    """Trouve des paragraphes dans d'autres articles pertinents pour créer un lien vers target_path."""
    return _find_link_opportunities(build_graph(), target_path, top_k)


def _find_link_opportunities(G: nx.DiGraph, target_path: str, top_k: int = 3) -> list[dict]:
    if target_path not in G.nodes:
        return [{"error": f"Page cible introuvable : {target_path}"}]

    target_data = G.nodes[target_path]
    existing_parents = set(G.predecessors(target_path))

    try:
        col = chroma_client.get_collection("hugo_seo", embedding_function=_embedding_function())
    except ImportError as exc:
        return [{"error": f"sentence-transformers est requis pour la recherche sémantique ({exc})."}]
    except Exception:
        return [{"error": "Index vide. Lance d'abord sync_and_get_site_audit."}]

    # Un index construit avec un autre modèle donnerait des résultats silencieusement faux.
    indexed_model = (col.metadata or {}).get("embedding_model")
    if indexed_model != EMBEDDING_MODEL:
        return [{"error": f"Index construit avec un autre modèle ({indexed_model or 'inconnu'}). "
                          f"Relance sync_and_get_site_audit pour le reconstruire."}]
    results = col.query(query_texts=[target_data["title"]], n_results=top_k * 4)

    opps = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        source_path = meta["source_path"]
        if source_path == target_path or source_path in existing_parents:
            continue

        opps.append({
            "source_path": source_path,
            "source_title": meta["title"],
            "paragraph_text": doc,
            "target_title": target_data["title"],
            "target_slug": f"/{target_data['slug']}/"
        })
        if len(opps) >= top_k:
            break

    return opps


@mcp.tool()
def update_markdown_paragraph(file_path: str, old_paragraph: str, new_paragraph: str) -> str:
    """Remplace un paragraphe exact dans un fichier Markdown par sa version enrichie du lien interne."""
    return _replace_paragraph(file_path, old_paragraph, new_paragraph)


def _backup_content_file(full_path: Path, rel_path: str, run_timestamp: str) -> Path | None:
    """Copie le fichier source dans .backups_seo avant première modification. None si déjà sauvegardé."""
    backup_path = BACKUP_DIR / run_timestamp / rel_path
    if backup_path.exists():
        return None
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(full_path, backup_path)
    return backup_path


def _replace_paragraph(file_path: str, old_paragraph: str, new_paragraph: str,
                       dry_run: bool = False, run_timestamp: str | None = None) -> str:
    full_path = CONTENT_DIR / file_path
    if not full_path.exists():
        return f"Erreur : Fichier {file_path} introuvable."

    try:
        content = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"Erreur : Lecture impossible de {file_path} ({exc})."

    occurrences = content.count(old_paragraph)
    if occurrences == 0:
        return f"Erreur : Le paragraphe d'origine est introuvable dans {file_path}."
    # Un remplacement aveugle sur la 1re occurrence toucherait peut-être le mauvais endroit.
    if occurrences > 1:
        return (f"Erreur : Le paragraphe apparaît {occurrences} fois dans {file_path}, "
                f"remplacement ambigu. Modifie-le manuellement ou rends le paragraphe unique.")

    if dry_run:
        return f"Simulation : {file_path} serait modifié (1 occurrence trouvée)."

    updated = content.replace(old_paragraph, new_paragraph, 1)
    try:
        _backup_content_file(full_path, file_path, run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S"))
        full_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return f"Erreur : Écriture impossible dans {file_path} ({exc})."

    return f"Succès : Fichier {file_path} mis à jour avec le nouveau lien."


# Corruption observée sur ce corpus : l'octet de continuation de « û » (C3 BB)
# a été remplacé par un guillemet droit (C3 22), ce qui casse le décodage UTF-8.
# Réparation ciblée octet par octet : un ré-encodage global du fichier en cp1252
# transformerait au contraire tous les accents déjà valides en mojibake.
BROKEN_SEQUENCES = {b"\xc3\x22": b"\xc3\xbb"}


@mcp.tool()
def get_index_status() -> str:
    """État de l'index sémantique et du contenu, sans rien modifier ni recalculer d'embeddings."""
    pages, skipped = load_pages()
    unreadable = [s for s in skipped if s["reason"].startswith(("encodage", "front matter"))]
    _, _, expected_ids = build_chunks(pages)

    lines = [f"Contenu : {len(pages)} page(s) dans le périmètre SEO, "
             f"{len(skipped)} exclue(s), {len(expected_ids)} paragraphe(s) indexable(s)."]
    if unreadable:
        lines.append(f"⚠ {len(unreadable)} fichier(s) illisible(s), exclus de l'analyse. "
                     f"Lance /lgrdev-mcp-seo:repair-seo.")

    # get_collection sans embedding_function : ne charge pas le modèle (mesuré ~1 ms).
    try:
        col = chroma_client.get_collection("hugo_seo")
    except Exception:
        lines.append("Index sémantique : absent. Lance /lgrdev-mcp-seo:init-seo pour le construire.")
        col = None

    if col is not None:
        indexed_model = (col.metadata or {}).get("embedding_model")
        indexed_ids = set(col.get(include=[])["ids"])
        to_encode = len(set(expected_ids) - indexed_ids)
        obsolete = len(indexed_ids - set(expected_ids))

        lines.append(f"Index sémantique : {col.count()} paragraphe(s), "
                     f"modèle {indexed_model or 'inconnu'}.")
        if indexed_model != EMBEDDING_MODEL:
            lines.append(f"⚠ Modèle attendu : {EMBEDDING_MODEL}. La recherche est refusée tant que "
                         f"l'index n'est pas reconstruit. Lance /lgrdev-mcp-seo:sync-seo.")
        elif to_encode or obsolete:
            lines.append(f"⚠ Index décalé : {to_encode} paragraphe(s) à encoder, "
                         f"{obsolete} obsolète(s). Lance /lgrdev-mcp-seo:sync-seo.")
        else:
            lines.append("Index à jour.")

    reports = sorted(AUDIT_DIR.glob("audit_seo_*.html")) if AUDIT_DIR.exists() else []
    lines.append(f"Dernier audit : {reports[-1]}" if reports
                 else "Dernier audit : aucun rapport dans ./audit-seo/.")

    if PROPOSALS_FILE.exists():
        try:
            proposals = _parse_proposals(PROPOSALS_FILE.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            proposals = []
        approved = sum(1 for p in proposals if p["approved"])
        applied = sum(1 for p in proposals
                      if (p["status"] or "").startswith("APPLIQUÉ"))
        lines.append(f"Propositions en cours ({PROPOSALS_FILE}) : {len(proposals)} au total, "
                     f"{approved} cochée(s) OUI, {applied} déjà appliquée(s). "
                     f"Poursuis avec /lgrdev-mcp-seo:review-seo.")
    else:
        lines.append("Propositions en cours : aucune. Lance /lgrdev-mcp-seo:review-seo pour en générer.")

    return "\n".join(lines)


@mcp.tool()
def repair_content_encoding(dry_run: bool = True) -> str:
    """Répare les fichiers Markdown dont l'UTF-8 est cassé par une séquence d'octets connue."""
    repairable, unknown = [], []

    for md_file in sorted(CONTENT_DIR.rglob("*.md")):
        raw = md_file.read_bytes()
        try:
            raw.decode("utf-8")
            continue
        except UnicodeDecodeError:
            pass

        fixed = raw
        hits = 0
        for broken, replacement in BROKEN_SEQUENCES.items():
            hits += fixed.count(broken)
            fixed = fixed.replace(broken, replacement)

        try:
            fixed.decode("utf-8")
        except UnicodeDecodeError as exc:
            unknown.append((md_file, f"motif inconnu à l'octet {exc.start} ({exc.reason})"))
            continue

        repairable.append((md_file, fixed, hits))

    if not repairable and not unknown:
        return "Tous les fichiers de content/ sont déjà en UTF-8 valide."

    lines = []
    if repairable:
        total = sum(hits for _, _, hits in repairable)
        lines.append(f"{len(repairable)} fichier(s) réparable(s), {total} séquence(s) cassée(s) :")
        for md_file, _, hits in repairable:
            lines.append(f"- {md_file.relative_to(CONTENT_DIR)} : {hits} occurrence(s)")
    if unknown:
        lines.append(f"\n{len(unknown)} fichier(s) à traiter manuellement :")
        for md_file, reason in unknown:
            lines.append(f"- {md_file.relative_to(CONTENT_DIR)} : {reason}")

    if dry_run:
        lines.append(
            f"\nMode simulation : aucun fichier modifié. Relance avec dry_run=False pour "
            f"réparer {len(repairable)} fichier(s) (sauvegarde dans {BACKUP_DIR})."
        )
        return "\n".join(lines)

    repaired, failures = 0, []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for md_file, fixed, _ in repairable:
        rel = md_file.relative_to(CONTENT_DIR)
        backup_path = BACKUP_DIR / timestamp / rel
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_file, backup_path)
            md_file.write_bytes(fixed)
            repaired += 1
        except OSError as exc:
            failures.append(f"{rel} : {exc}")

    lines.append(f"\n{repaired} fichier(s) réparé(s). Sauvegardes : {BACKUP_DIR / timestamp}")
    if failures:
        lines.append("Échecs :\n" + "\n".join(f"- {failure}" for failure in failures))
    lines.append("Relance sync_and_get_site_audit pour réindexer ces pages.")
    return "\n".join(lines)


@mcp.tool()
def generate_proposals_report(output_file: str = "propositions_seo.md", max_items: int = 10) -> str:
    """Génère un fichier Markdown de propositions de liens internes à valider manuellement."""
    G = build_graph()
    try:
        chroma_client.get_collection("hugo_seo")
    except Exception:
        return "Erreur : Index vide. Lance d'abord sync_and_get_site_audit."

    targets = sorted(
        (node for node, in_deg in G.in_degree()
         if in_deg <= UNDERLINKED_MAX_IN_DEGREE and Path(node).stem != "_index"),
        key=lambda node: (G.in_degree(node), node),
    )

    proposals = []
    used_paragraphs = set()
    for target in targets:
        if len(proposals) >= max_items:
            break
        for opp in _find_link_opportunities(G, target, top_k=1):
            if "error" in opp:
                continue
            if (opp["source_path"], opp["paragraph_text"]) in used_paragraphs:
                continue
            used_paragraphs.add((opp["source_path"], opp["paragraph_text"]))
            new_paragraph, mode = _insert_link(
                opp["paragraph_text"], opp["target_title"], opp["target_slug"]
            )
            proposals.append({
                "source_path": opp["source_path"],
                "target_path": target,
                "old": opp["paragraph_text"],
                "new": new_paragraph,
                "mode": mode,
            })

    if not proposals:
        return "Aucune opportunité de lien trouvée pour les pages orphelines ou sous-maillées."

    report_path = Path(output_file)
    try:
        report_path.write_text(_render_proposals_report(proposals), encoding="utf-8")
    except OSError as exc:
        return f"Erreur : Écriture impossible dans {output_file} ({exc})."

    anchors = sum(1 for p in proposals if p["mode"] == "ancre")
    return (
        f"{len(proposals)} proposition(s) écrite(s) dans {report_path} "
        f"({anchors} avec ancre in-prose, {len(proposals) - anchors} avec phrase ajoutée).\n"
        f"Coche [x] OUI sur les propositions retenues, puis lance apply_approved_proposals."
    )


@mcp.tool()
def apply_approved_proposals(input_file: str = "propositions_seo.md", dry_run: bool = False) -> str:
    """Applique dans les fichiers sources les propositions cochées OUI dans le rapport Markdown."""
    report_path = Path(input_file)
    try:
        text = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"Erreur : Lecture impossible de {input_file} ({exc})."

    proposals = _parse_proposals(text)
    if not proposals:
        return f"Aucune proposition trouvée dans {input_file}."

    applied, already, refused, failures = 0, 0, 0, []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    updated_text = text

    # Parcours en ordre inverse : les offsets des blocs restent valides pendant la réécriture.
    for proposal in reversed(proposals):
        if not proposal["approved"]:
            refused += 1
            continue
        if proposal["status"] and proposal["status"].startswith("APPLIQUÉ"):
            already += 1
            continue

        if not proposal["source_path"] or proposal["old"] is None or proposal["new"] is None:
            status = "ÉCHEC : bloc incomplet (fichier source ou paragraphes manquants)"
            failures.append(f"Proposition {proposal['id']} : bloc incomplet")
        else:
            result = _replace_paragraph(proposal["source_path"], proposal["old"], proposal["new"],
                                        dry_run=dry_run, run_timestamp=run_timestamp)
            if result.startswith(("Succès", "Simulation")):
                status = f"APPLIQUÉ le {timestamp}"
                applied += 1
            else:
                status = f"ÉCHEC : {result}"
                failures.append(f"Proposition {proposal['id']} : {result}")

        if dry_run:
            continue

        block = updated_text[proposal["block_start"]:proposal["block_end"]]
        updated_text = (
            updated_text[:proposal["block_start"]]
            + _set_block_status(block, status)
            + updated_text[proposal["block_end"]:]
        )

    if dry_run:
        summary = (
            f"Simulation : {applied} modification(s) seraient appliquée(s), "
            f"{already} déjà appliquée(s), {refused} non validée(s), {len(failures)} bloquée(s).\n"
            f"Aucun fichier modifié. Relance sans dry_run pour appliquer."
        )
        if failures:
            summary += "\n" + "\n".join(f"- {failure}" for failure in failures)
        return summary

    try:
        report_path.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        return f"Erreur : {applied} modification(s) appliquée(s) mais mise à jour de {input_file} impossible ({exc})."

    summary = (
        f"{applied} modification(s) appliquée(s), {already} déjà appliquée(s), "
        f"{refused} non validée(s), {len(failures)} échec(s)."
    )
    if applied:
        summary += f"\nSauvegardes des fichiers modifiés : {BACKUP_DIR / run_timestamp}"
    if failures:
        summary += "\n" + "\n".join(f"- {failure}" for failure in failures)
    return summary


@mcp.tool()
def archive_proposals_report(report_file: str = "propositions_seo.md",
                             archive_dir: str = ".archives_seo") -> str:
    """Archive le rapport de propositions avec horodatage et réinitialise un fichier vierge."""
    report_path = Path(report_file)
    if not report_path.exists():
        return f"Erreur : Fichier {report_file} introuvable."

    archive_path = Path(archive_dir) / f"propositions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(report_path), str(archive_path))
        report_path.write_text(PROPOSALS_HEADER, encoding="utf-8")
    except OSError as exc:
        return f"Erreur : Archivage impossible ({exc})."

    return f"Rapport archivé dans {archive_path}. Fichier {report_file} réinitialisé (en-tête seul)."


if __name__ == "__main__":
    mcp.run()