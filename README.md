# Hugo SEO Linking Agent (plugin Claude Code)

Plugin Claude Code qui analyse et optimise le **maillage interne** d'un site statique **Hugo** :
audit des pages orphelines, propositions de liens contextuels, application après validation.

**Rien à installer en plus du plugin.** Aucune dépendance Python, aucun modèle à télécharger,
aucun serveur à lancer : les commandes appellent un CLI qui n'utilise que la bibliothèque
standard de Python 3.

## 🚀 Fonctionnalités

- **Graphe du maillage :** cartographie les liens internes, repère les pages orphelines et
  sous-maillées, signale les liens cassés et les fichiers illisibles.
- **Classement des paragraphes d'accueil :** BM25 sur le contenu du site pour trouver où un lien
  serait naturel, puis jugement sémantique par un sous-agent dédié.
- **Validation humaine :** chaque modification passe par un rapport Markdown à cocher, avec
  simulation et sauvegarde avant écriture.

## 🛠️ Prérequis & installation

- Python 3.10 ou supérieur (présent par défaut sur Linux et macOS)
- Un projet Hugo avec un dossier `content/`

```bash
/plugin marketplace add lgrdev/mcp_seo_hugo
claude plugin install lgrdev-mcp-seo@lgrdev-mcp-seo
```

C'est tout. Lance ensuite les commandes depuis la racine de ton projet Hugo, celle qui contient
`content/`.

## Commandes

|Commande|Description|
|:--------|:--------|
|`/lgrdev-mcp-seo:init-seo`|Première utilisation : audit du maillage interne et présentation de la boucle de travail.|
|`/lgrdev-mcp-seo:sync-seo`|Relance l'audit après modification d'articles dans `./content` et montre les écarts.|
|`/lgrdev-mcp-seo:review-seo`|Boucle par lot : propositions de liens, validation `[x] OUI`, application, archivage.|
|`/lgrdev-mcp-seo:status-seo`|État du contenu et du maillage, sans rien modifier. Indique la prochaine action utile.|
|`/lgrdev-mcp-seo:repair-seo`|Répare l'encodage des fichiers Markdown cassés (simulation d'abord, puis sauvegarde).|
|`/lgrdev-mcp-seo:boost-page <chemin>`|Maille une page précise : classe les paragraphes d'accueil et insère le lien après validation.|

Le choix du paragraphe d'accueil est confié au sous-agent `link-picker`, qui lit les candidats
classés et écarte une cible plutôt que de forcer un lien hors sujet.

## CLI sous-jacent

Les skills appellent `scripts/seoctl.py`. Il est utilisable directement :

|Commande|Rôle|
|:--------|:--------|
|`audit`|Graphe du maillage + rapport HTML dans `./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html`.|
|`status`|Lecture seule : pages en périmètre, orphelines, fichiers illisibles, propositions en cours.|
|`candidates --target <page>`|Paragraphes candidats (BM25) pour mailler vers une page, en JSON.|
|`candidates --auto --max 10`|Idem pour les pages les moins liées du site.|
|`proposals --from <choix.json>`|Écrit `propositions_seo.md` à partir des paragraphes retenus.|
|`apply [--dry-run]`|Applique les propositions cochées `[x] OUI`. Sauvegarde dans `./.backups_seo/`.|
|`archive`|Archive le rapport dans `./.archives_seo/` et le réinitialise.|
|`repair [--apply]`|Répare les octets UTF-8 cassés sur motifs connus. Simulation par défaut.|

Les pages en `draft`, en `robots: noindex` ou marquées `option_seo: false` dans le front matter
sont hors périmètre SEO. Les pages `_index.md` ne comptent pas comme orphelines : leurs liens
entrants viennent des templates Hugo.

## Performance

Mesures sur un corpus réel de 98 fichiers, 91 pages en périmètre, 2226 paragraphes exploitables :

|Opération|Temps|
|:--------|--:|
|`audit` complet|0,07 s|
|`status`|0,08 s|
|`candidates --auto --max 10`|0,56 s|

La version 1.x, qui reposait sur ChromaDB et un modèle d'embeddings multilingue, demandait ~39 s
par synchronisation complète, environ 1 Go de téléchargement au premier lancement et un
`pip install` manuel. Le graphe donne exactement les mêmes chiffres qu'avant.

Contrepartie assumée : un classement lexical ne rapproche pas deux formulations qui ne partagent
aucun mot. Le sous-agent juge le sens des candidats retenus, mais un bon paragraphe absent du
classement n'est pas rattrapé.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

69 tests, moins d'une seconde. Aucun stub : tout le code testé n'utilise que la bibliothèque
standard. `PyYAML` sert uniquement d'oracle pour vérifier que le mini-lecteur de front matter
donne les mêmes valeurs qu'un vrai parseur YAML sur le corpus réel.
