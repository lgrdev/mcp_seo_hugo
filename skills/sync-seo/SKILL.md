---
description: Resynchronise l'index SEO après modification d'articles dans ./content et relance l'audit du maillage interne.
disable-model-invocation: true
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__sync_and_get_site_audit]
---

L'utilisateur a modifié des articles dans `./content`. Appelle `sync_and_get_site_audit` pour reconstruire le graphe de liens, ré-indexer le contenu à jour (l'outil recrée la collection ChromaDB en entier à chaque appel), et générer un nouveau rapport HTML dans `./audit-seo/`.

Présente ensuite à l'utilisateur :
- Chemin du nouveau fichier HTML généré (`./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html`)
- Résumé rafraîchi : pages orphelines (aucun lien entrant), nombre de liens par page
- Différences notables si évidentes par rapport à un audit précédent mentionné dans la conversation
