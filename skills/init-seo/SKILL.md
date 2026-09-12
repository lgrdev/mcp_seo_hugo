---
description: Initialise l'index SEO et audite le maillage interne du site Hugo (pages orphelines, comptage de liens).
disable-model-invocation: true
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__sync_and_get_site_audit]
---

Appelle l'outil `sync_and_get_site_audit` pour construire le graphe de liens interne, indexer tout le contenu du site dans ChromaDB, et générer le rapport HTML dans `./audit-seo/`.

Présente ensuite à l'utilisateur :
- Chemin du fichier HTML généré (`./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html`)
- Résumé : pages orphelines (aucun lien entrant), nombre de liens par page
- Tout avertissement d'indexation retourné par l'outil
