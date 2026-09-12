---
description: Renforce le maillage interne vers une page précise : cherche les meilleurs paragraphes d'accueil et insère le lien après validation.
disable-model-invocation: true
arguments: [page]
allowed-tools: [mcp__plugin_lgrdev-mcp-seo_hugo-seo__find_link_opportunities, mcp__plugin_lgrdev-mcp-seo_hugo-seo__update_markdown_paragraph]
---

Page cible demandée : `$page`

Traitement page par page, à la différence de `/lgrdev-mcp-seo:review-seo` qui travaille par lot.

**1. Chercher les opportunités**

Appelle `find_link_opportunities` avec `target_path` = `$page`. Le chemin attendu est relatif à `content/`, par exemple `blog/2026-07/mon-article.md`.

Si `$page` est vide, demande la page cible avant d'aller plus loin.

Gère les deux erreurs que l'outil retourne :
- `Page cible introuvable` → le chemin ne correspond à aucune page analysée. Propose les chemins plausibles et redemande.
- `Index vide` ou message de modèle différent → l'index n'est pas exploitable : renvoie vers `/lgrdev-mcp-seo:sync-seo`.

**2. Présenter et choisir**

Pour chaque candidat, montre la page source, son titre, et le paragraphe d'accueil proposé. Laisse l'utilisateur choisir ceux qu'il retient : ne décide pas à sa place.

**3. Rédiger l'ancre**

Pour chaque paragraphe retenu, propose le paragraphe réécrit avec le lien inséré. Ancre l'expression déjà présente dans le texte quand c'est possible, plutôt que d'ajouter une phrase. Montre le avant/après et demande validation.

**4. Appliquer**

Appelle `update_markdown_paragraph` avec le paragraphe d'origine **exactement** tel que retourné par `find_link_opportunities` (espaces compris) comme `old_paragraph`, sinon le remplacement échoue.

L'outil sauvegarde le fichier avant écriture et refuse de modifier un paragraphe présent plusieurs fois dans son fichier. Si ce refus arrive, indique-le : la retouche est à faire à la main.
