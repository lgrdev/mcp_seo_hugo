---
description: Relance l'audit du maillage interne après modification d'articles dans ./content et compare au rapport précédent.
disable-model-invocation: true
allowed-tools: ["Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py *)"]
---

L'utilisateur a modifié des articles dans `./content` et veut un audit à jour.

**1. Relever l'état précédent**

Avant de relancer l'audit, note le rapport le plus récent déjà présent :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" status
```

**2. Auditer**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" audit
```

Il n'y a aucun index à synchroniser : l'audit est recalculé entièrement à chaque appel, en une
fraction de seconde. Le rapport précédent n'est pas écrasé, chaque audit crée un fichier horodaté.

**3. Présenter les écarts**

- chemin du nouveau rapport HTML ;
- pages, liens internes, orphelines, sous-maillées ;
- **ce qui a changé** depuis l'audit précédent quand l'information est disponible (dans la
  conversation, ou dans l'état relevé à l'étape 1) : une page sortie de la liste des orphelines
  est un progrès, une page entrée dedans est souvent une page nouvellement publiée ;
- fichiers illisibles → `/lgrdev-mcp-seo:repair-seo` ; liens non résolus → détail dans le rapport.

Si l'utilisateur veut agir sur ce qu'il vient de voir, renvoie vers `/lgrdev-mcp-seo:review-seo`
pour un lot, ou `/lgrdev-mcp-seo:boost-page <chemin>` pour une page précise.
