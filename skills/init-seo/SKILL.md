---
description: Première utilisation sur un site Hugo : vérifie que tout fonctionne, audite le maillage interne et présente la boucle de travail SEO.
disable-model-invocation: true
allowed-tools: ["Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py *)"]
---

Première utilisation du plugin sur ce site. Rien à installer : `seoctl.py` n'utilise que la
bibliothèque standard de Python.

**1. Auditer**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" audit
```

À lancer depuis la racine du projet Hugo, celle qui contient `content/`. Deux erreurs possibles :

- `content/ introuvable` → l'utilisateur n'est pas à la racine du projet Hugo. Demande le bon dossier.
- `python3: command not found` → Python 3 n'est pas installé. Indique-le clairement : c'est le
  seul prérequis du plugin, il n'y a aucune dépendance à installer ensuite.

**2. Présenter**

- le chemin du rapport HTML (`./audit-seo/audit_seo_YYYYMMDD_HHMMSS.html`) ;
- le nombre de pages, de liens internes, de pages orphelines et de pages sous-maillées ;
- les fichiers illisibles s'il y en a, en renvoyant vers `/lgrdev-mcp-seo:repair-seo` ;
- les liens internes non résolus s'il y en a : ce sont des liens cassés ou des cibles hors
  périmètre SEO, leur détail est dans le rapport HTML.

**3. Expliquer la suite**

Termine par la boucle de travail, en une ligne chacune :

- `/lgrdev-mcp-seo:review-seo` — propose des liens vers les pages peu maillées, à valider une par une ;
- `/lgrdev-mcp-seo:boost-page <chemin>` — traite une page précise ;
- `/lgrdev-mcp-seo:sync-seo` — relance l'audit après modification d'articles ;
- `/lgrdev-mcp-seo:status-seo` — état du site sans rien modifier.

Les pages en `draft`, en `robots: noindex` ou marquées `option_seo: false` sont hors périmètre :
dis-le si l'audit en a exclu.
