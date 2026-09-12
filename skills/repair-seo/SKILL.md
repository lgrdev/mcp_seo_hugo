---
description: Détecte et répare les fichiers Markdown de ./content dont l'encodage UTF-8 est cassé, puis réindexe.
disable-model-invocation: true
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__repair_content_encoding, mcp__plugin_lgrdev-mcp-seo_hugo-seo__sync_and_get_site_audit]
---

Cette commande écrit dans les fichiers sources de l'utilisateur. Procède toujours en deux temps.

**1. Simulation, systématiquement**

Appelle `repair_content_encoding` sans argument (`dry_run=True` par défaut). Présente :
- la liste des fichiers concernés et le nombre de séquences cassées
- les fichiers signalés comme « à traiter manuellement » : l'outil ne devine jamais un caractère qu'il ne reconnaît pas, ceux-là restent à corriger à la main

Si aucun fichier n'est cassé, dis-le et arrête-toi ici.

**2. Réparation, après accord explicite**

Demande confirmation, puis appelle `repair_content_encoding` avec `dry_run=False`. Rapporte :
- le nombre de fichiers réparés
- le dossier de sauvegarde des versions d'origine (`.backups_seo/<horodatage>/`)

Propose ensuite `sync_and_get_site_audit` : les pages réparées deviennent analysables, donc les chiffres de l'audit changent.

N'appelle jamais la réparation sans avoir montré la simulation d'abord.
