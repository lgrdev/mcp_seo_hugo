---
description: Affiche l'état du contenu et du maillage interne (pages en périmètre, orphelines, fichiers illisibles, propositions en cours) sans rien modifier.
disable-model-invocation: true
allowed-tools: ["Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py *)"]
---

## État actuel

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" status`

Lecture seule : aucun fichier n'est modifié. L'état ci-dessus a été calculé avant que tu ne
lises ces instructions ; ne relance la commande que si l'utilisateur demande un rafraîchissement.

Présente cet état, puis termine par **la seule action utile ensuite** :

- aucun rapport d'audit → `/lgrdev-mcp-seo:init-seo` ;
- fichiers illisibles → `/lgrdev-mcp-seo:repair-seo` ;
- propositions cochées en attente → `/lgrdev-mcp-seo:review-seo` ;
- pages orphelines ou sous-maillées, rien d'autre en cours → `/lgrdev-mcp-seo:review-seo`, ou
  `/lgrdev-mcp-seo:boost-page <chemin>` pour une page précise.

Si la sortie commence par `Erreur : content/ introuvable`, l'utilisateur n'est pas à la racine
de son projet Hugo : demande-lui le bon dossier au lieu d'interpréter le reste.

S'il n'y a rien à faire, dis-le simplement au lieu de proposer une commande.
