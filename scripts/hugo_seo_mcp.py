import re
from pathlib import Path
from fastmcp import FastMCP
import frontmatter
import networkx as nx
import chromadb

# Initialisation du serveur MCP
mcp = FastMCP("Hugo SEO Linking Agent")

CONTENT_DIR = Path("./content")

# Initialisation de ChromaDB (persistant sur disque pour aller plus vite)
chroma_client = chromadb.PersistentClient(path="./.chroma_seo")
collection = chroma_client.get_or_create_collection(name="hugo_seo")


# --- FONCTIONS INTERNES ---
def build_graph() -> nx.DiGraph:
    G = nx.DiGraph()
    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    nodes = {}

    for md_file in CONTENT_DIR.rglob("*.md"):
        try:
            post = frontmatter.load(md_file)
            if post.get("draft", False):
                continue
            rel_path = str(md_file.relative_to(CONTENT_DIR))
            slug = post.get("slug") or md_file.stem
            nodes[rel_path] = {
                "title": post.get("title", md_file.stem),
                "slug": slug,
                "content": post.content,
            }
            G.add_node(rel_path, title=nodes[rel_path]["title"], slug=slug)
        except Exception:
            pass

    for source_path, data in nodes.items():
        for text, target in link_pattern.findall(data["content"]):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_clean = target.split("#")[0].strip("/")
            for candidate_path, candidate_data in nodes.items():
                if target_clean in candidate_path or candidate_data["slug"] == target_clean:
                    G.add_edge(source_path, candidate_path, anchor=text)
                    break
    return G


# --- OUTILS MCP EXPOSÉS À CLAUDE ---

@mcp.tool()
def sync_and_get_site_audit() -> str:
    """Analyse le site Hugo, indexe les paragraphes dans ChromaDB et retourne la liste des pages orphelines et métriques SEO."""
    G = build_graph()
    
    # Réindexation ChromaDB
    documents, metadatas, ids = [], [], []
    for md_file in CONTENT_DIR.rglob("*.md"):
        post = frontmatter.load(md_file)
        if post.get("draft", False):
            continue
        rel_path = str(md_file.relative_to(CONTENT_DIR))
        title = post.get("title", md_file.stem)
        
        # Nettoyage et découpe
        cleaned = re.sub(r"```.*?```", "", post.content, flags=re.DOTALL)
        cleaned = re.sub(r"!\[.*?\]\(.*?\)", "", cleaned)
        cleaned = re.sub(r"#+\s+.*", "", cleaned)
        chunks = [p.strip() for p in cleaned.split("\n\n") if len(p.strip()) >= 80]
        
        for idx, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({"source_path": rel_path, "title": title})
            ids.append(f"{rel_path}#chunk-{idx}")

    if documents:
        # Reconstitution simple de la collection
        chroma_client.delete_collection("hugo_seo")
        col = chroma_client.create_collection("hugo_seo")
        col.add(documents=documents, metadatas=metadatas, ids=ids)

    orphans = [node for node, in_deg in G.in_degree() if in_deg == 0]
    
    report = f"Total pages : {G.number_of_nodes()}\n"
    report += f"Total liens internes : {G.number_of_edges()}\n"
    report += f"Pages orphelines ({len(orphans)}) :\n"
    for orphan in orphans:
        report += f"- Path: {orphan} | Titre: {G.nodes[orphan]['title']} | Slug: {G.nodes[orphan]['slug']}\n"
        
    return report


@mcp.tool()
def find_link_opportunities(target_path: str, top_k: int = 3) -> list[dict]:
    """Trouve des paragraphes dans d'autres articles pertinents pour créer un lien vers target_path."""
    G = build_graph()
    if target_path not in G.nodes:
        return [{"error": f"Page cible introuvable : {target_path}"}]

    target_data = G.nodes[target_path]
    existing_parents = set(G.predecessors(target_path))

    col = chroma_client.get_collection("hugo_seo")
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
    full_path = CONTENT_DIR / file_path
    if not full_path.exists():
        return f"Erreur : Fichier {file_path} introuvable."

    content = full_path.read_text(encoding="utf-8")
    if old_paragraph not in content:
        return f"Erreur : Le paragraphe d'origine est introuvable dans {file_path}."

    updated = content.replace(old_paragraph, new_paragraph, 1)
    full_path.write_text(updated, encoding="utf-8")
    return f"Succès : Fichier {file_path} mis à jour avec le nouveau lien."


if __name__ == "__main__":
    mcp.run()