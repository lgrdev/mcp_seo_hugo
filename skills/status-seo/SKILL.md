---
description: Affiche l'état de l'index SEO et du contenu (index à jour ou décalé, fichiers illisibles, propositions en cours) sans rien modifier.
disable-model-invocation: true
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__get_index_status]
---

Appelle `get_index_status`. Lecture seule : aucun fichier n'est modifié, aucun embedding recalculé.

Présente l'état tel qu'il est retourné, puis termine par **la seule action utile ensuite** :
- index absent → `/lgrdev-mcp-seo:init-seo`
- index décalé ou modèle différent → `/lgrdev-mcp-seo:sync-seo`
- fichiers illisibles → `/lgrdev-mcp-seo:repair-seo`
- propositions cochées en attente → `/lgrdev-mcp-seo:review-seo`

S'il n'y a rien à faire, dis-le simplement au lieu de proposer une commande.
