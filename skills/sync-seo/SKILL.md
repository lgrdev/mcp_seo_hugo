---
description: Resynchronise l'index SEO après modification d'articles dans ./content et relance l'audit du maillage interne.
disable-model-invocation: true
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__sync_and_get_site_audit]
---

L'utilisateur a modifié des articles dans `./content`. Appelle `sync_and_get_site_audit` pour reconstruire le graphe de liens, mettre l'index à jour et générer un nouveau rapport HTML dans `./audit-seo/`.

L'indexation est incrémentale : seuls les paragraphes nouveaux ou modifiés sont encodés, les autres sont réutilisés. Un sync sans changement prend une fraction de seconde.

Présente ensuite à l'utilisateur :
- Chemin du nouveau fichier HTML généré (`./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html`)
- Résumé rafraîchi : pages orphelines (aucun lien entrant), nombre de liens par page
- Différences notables si évidentes par rapport à un audit précédent mentionné dans la conversation
