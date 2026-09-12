# Hugo SEO Linking Agent (Serveur MCP)

Un agent IA sous forme de serveur **MCP (Model Context Protocol)** permettant à Claude (Desktop ou Code) d'analyser, d'optimiser et d'automatiser le maillage interne d'un site statique **Hugo**.

## 🚀 Fonctionnalités

- **Analyse de graphe (NetworkX) :** cartographie tous les liens internes existants et repère automatiquement les pages orphelines ou sous-maillées.
- **Recherche sémantique (ChromaDB) :** vectorise le contenu paragraphe par paragraphe pour trouver les meilleures opportunités de liens contextuels.
- **Mise à jour automatique :** permet à l'agent de modifier directement les fichiers Markdown `.md` sources sans altérer le front matter.

## 🛠️ Prérequis & installation

- Python 3.10 ou supérieur
- Un projet Hugo avec un dossier `content/`

Installe les dépendances Python requises :

```bash
sudo apt update
sudo apt install -y build-essential python3-dev python3-pip python3-venv
pip install fastmcp python-frontmatter networkx chromadb sentence-transformers
```

## outils MCP exposés
|Outil MCP|Description|
|:--------|:--------|
|sync_and_get_site_audit|Analyse le graphe du site, indexe le contenu dans ChromaDB et retourne le rapport SEO (pages orphelines, métriques).|
|find_link_opportunities|Cherche dans la base vectorielle les paragraphes les plus pertinents pour mailler vers une page cible.|
|update_markdown_paragraph|Remplace proprement un paragraphe dans le fichier .md d'origine avec l'ancre insérée par l'IA.|