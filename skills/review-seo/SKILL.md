---
description: Génère les propositions de maillage interne à valider à la main, puis applique celles cochées OUI et archive le rapport.
disable-model-invocation: true
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__generate_proposals_report, mcp__plugin_lgrdev-mcp-seo_hugo-seo__apply_approved_proposals, mcp__plugin_lgrdev-mcp-seo_hugo-seo__archive_proposals_report]
---

Boucle de relecture du maillage interne. L'utilisateur valide chaque proposition à la main dans un fichier Markdown : ne coche jamais les cases à sa place.

Détermine d'abord où en est l'utilisateur, puis agis :

**1. Aucun `propositions_seo.md` en cours, ou l'utilisateur demande de nouvelles propositions**

Appelle `generate_proposals_report`. Indique ensuite :
- le chemin du fichier généré
- le nombre de propositions
- qu'il doit cocher `[x] OUI` sur celles qu'il retient, puis revenir

**2. L'utilisateur a coché ses cases et veut appliquer**

Appelle `apply_approved_proposals` avec `dry_run=True` d'abord, montre ce qui serait modifié, puis appelle-le sans `dry_run` pour appliquer. Rapporte :
- le nombre de modifications appliquées
- le dossier de sauvegarde des fichiers sources
- les échecs éventuels, notamment un paragraphe présent plusieurs fois dans son fichier : dans ce cas l'outil refuse de modifier et la retouche est à faire à la main

**3. Le lot est traité et l'utilisateur veut repartir propre**

Appelle `archive_proposals_report` et donne le chemin de l'archive.

Après une application, rappelle que `sync_and_get_site_audit` (ou `/lgrdev-mcp-seo:sync-seo`) réindexe les paragraphes modifiés et produit un audit à jour.
