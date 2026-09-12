# Hugo SEO Linking Agent (Serveur MCP)

Un agent IA sous forme de serveur **MCP (Model Context Protocol)** permettant à Claude (Desktop ou Code) d'analyser, d'optimiser et d'automatiser le maillage interne d'un site statique **Hugo**.

## 🚀 Fonctionnalités

- **Analyse de graphe (NetworkX) :** cartographie tous les liens internes existants et repère automatiquement les pages orphelines ou sous-maillées.
- **Recherche sémantique (ChromaDB) :** vectorise le contenu paragraphe par paragraphe pour trouver les meilleures opportunités de liens contextuels.
- **Mise à jour automatique :** permet à l'agent de modifier directement les fichiers Markdown `.md` sources sans altérer le front matter.

## 🛠️ Prérequis & installation

- Python 3.10 ou supérieur
- Un projet Hugo avec un dossier `content/`

### Installation via plugin Claude Code

```bash
/plugin marketplace add lgrdev/mcp_seo_hugo
claude plugin install lgrdev-mcp-seo@lgrdev-mcp-seo
pip install -r requirements.txt
```

L'installation du plugin déclare le serveur MCP automatiquement dans Claude Code ; les dépendances Python restent à installer manuellement (le système de plugins ne gère pas les dépendances Python).

### Installation manuelle

```bash
sudo apt update
sudo apt install -y build-essential python3-dev python3-pip python3-venv
pip install -r requirements.txt
```

## outils MCP exposés
|Outil MCP|Description|
|:--------|:--------|
|sync_and_get_site_audit|Analyse le graphe du site, indexe le contenu dans ChromaDB et retourne le rapport SEO (pages orphelines, métriques).|
|find_link_opportunities|Cherche dans la base vectorielle les paragraphes les plus pertinents pour mailler vers une page cible.|
|update_markdown_paragraph|Remplace proprement un paragraphe dans le fichier .md d'origine avec l'ancre insérée par l'IA.|

## Commandes

|Commande|Description|
|:--------|:--------|
|`/lgrdev-mcp-seo:init-seo`|Initialise l'index SEO et audite le maillage interne (première utilisation).|
|`/lgrdev-mcp-seo:sync-seo`|Resynchronise l'index après modification d'articles dans `./content` et relance l'audit.|