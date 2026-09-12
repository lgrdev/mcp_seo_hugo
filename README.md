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
|sync_and_get_site_audit|Analyse le graphe du site, indexe le contenu dans ChromaDB et génère le rapport HTML dans `./audit-seo/` (pages orphelines, liens non résolus, fichiers illisibles).|
|find_link_opportunities|Cherche dans la base vectorielle les paragraphes les plus pertinents pour mailler vers une page cible.|
|update_markdown_paragraph|Remplace proprement un paragraphe dans le fichier .md d'origine avec l'ancre insérée par l'IA.|
|generate_proposals_report|Génère `propositions_seo.md` : une proposition de lien par page orpheline ou sous-maillée, à valider à la main.|
|apply_approved_proposals|Applique uniquement les propositions cochées `[x] OUI`. Sauvegarde dans `./.backups_seo/`, option `dry_run`.|
|archive_proposals_report|Archive le rapport dans `./.archives_seo/` avec horodatage et réinitialise un fichier vierge.|
|repair_content_encoding|Répare les fichiers Markdown dont l'UTF-8 est cassé. `dry_run=True` par défaut, sauvegarde avant écriture.|
|get_index_status|Lecture seule : index à jour ou décalé, modèle utilisé, fichiers illisibles, propositions en cours. Ne charge pas le modèle.|

> Premier lancement : le modèle d'embeddings multilingue (`paraphrase-multilingual-MiniLM-L12-v2`, adapté au contenu français) est téléchargé automatiquement (~500 Mo avec torch).

## Commandes

|Commande|Description|
|:--------|:--------|
|`/lgrdev-mcp-seo:init-seo`|Initialise l'index SEO et audite le maillage interne (première utilisation).|
|`/lgrdev-mcp-seo:sync-seo`|Resynchronise l'index après modification d'articles dans `./content` et relance l'audit.|
|`/lgrdev-mcp-seo:review-seo`|Boucle de validation : génère les propositions de liens, applique celles cochées `[x] OUI`, archive le rapport.|
|`/lgrdev-mcp-seo:status-seo`|État de l'index et du contenu, sans rien modifier. Indique la prochaine action utile.|
|`/lgrdev-mcp-seo:repair-seo`|Répare l'encodage des fichiers Markdown cassés (simulation d'abord, puis réparation avec sauvegarde).|
|`/lgrdev-mcp-seo:boost-page <chemin>`|Maille une page précise : cherche les meilleurs paragraphes d'accueil et insère le lien après validation.|

`init-seo` et `sync-seo` appellent le même outil : le premier passage encode tout le contenu, les suivants sont incrémentaux.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Les tests couvrent la logique pure (ancres, parsing du rapport de propositions, résolution des liens internes, filtres de contenu, garde-fous d'écriture). `fastmcp` et `chromadb` sont remplacés par des stubs dans `tests/conftest.py`, donc l'installation de test reste légère (pas de torch).