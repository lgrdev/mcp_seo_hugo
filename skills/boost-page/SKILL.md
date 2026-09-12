---
description: Renforce le maillage interne vers une page précise : classe les paragraphes d'accueil possibles et insère le lien après validation.
disable-model-invocation: true
arguments: [page]
allowed-tools: ["Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py *)", "Read", "Write"]
---

Page cible demandée : `$page`

Traitement page par page, à la différence de `/lgrdev-mcp-seo:review-seo` qui travaille par lot.

**1. Classer les paragraphes d'accueil**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" candidates --target "$page" --top 10
```

Le chemin attendu est relatif à `content/`, par exemple `blog/2026-07/mon-article.md`.
Si `$page` est vide, demande la page cible avant d'aller plus loin.

Si la sortie contient `Page cible introuvable`, le chemin ne correspond à aucune page du
périmètre SEO. La page est peut-être en `draft`, en `robots: noindex` ou en `option_seo: false` ;
sinon propose les chemins plausibles et redemande.

Une liste de candidats vide signifie qu'aucun paragraphe ne partage de vocabulaire avec la cible,
ou que toutes les pages proches la lient déjà. Dis-le plutôt que de forcer un lien.

**2. Présenter et choisir**

Pour chaque candidat, montre la page source, son titre et le paragraphe d'accueil. Juge le sens,
pas le score : un score plus bas peut être le bon choix. Laisse l'utilisateur trancher.

**3. Proposer l'ancre, puis appliquer**

Écris les choix retenus dans `.seo_work/choix.json` :

```json
{"picks": [{"target_path": "$page", "source_path": "<page hôte>",
            "paragraph_text": "<paragraphe copié à l'octet près>",
            "anchor_phrase": "<expression déjà présente dans le paragraphe, optionnelle>"}]}
```

Puis :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" proposals --from .seo_work/choix.json
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" apply --dry-run
```

Montre le avant/après du paragraphe, demande validation, et seulement ensuite :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" apply
```

`paragraph_text` doit être copié **exactement** depuis la sortie de `candidates`, espaces compris,
sinon la proposition est rejetée. Le fichier source est sauvegardé avant écriture, et un
paragraphe présent plusieurs fois dans son fichier est refusé : la retouche est alors manuelle.

Termine avec `archive` si l'utilisateur ne veut pas garder le rapport d'une seule proposition.
