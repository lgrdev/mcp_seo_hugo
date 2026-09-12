---
description: Boucle de maillage par lot : classe les paragraphes candidats, fait choisir le sous-agent link-picker, écrit les propositions à valider, applique celles cochées OUI et archive.
disable-model-invocation: true
allowed-tools: ["Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py *)", "Task", "Agent", "Read"]
---

Boucle de relecture du maillage interne. L'utilisateur valide chaque proposition à la main dans
un fichier Markdown : **ne coche jamais les cases à sa place**.

Commence par situer l'utilisateur :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" status
```

La dernière ligne indique s'il existe déjà des propositions en cours. Enchaîne sur l'étape qui
correspond.

## 1. Produire un nouveau lot de propositions

**a. Classer les candidats** (BM25, aucun modèle, aucune dépendance) :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" candidates --auto --max 10 --top 5 \
  --out .seo_work/candidats.json
```

`--auto` cible les pages orphelines et sous-maillées, les moins liées d'abord. Le JSON est
écrit dans un fichier plutôt qu'affiché : il n'a pas à traverser la conversation.

**b. Faire choisir le juge sémantique.** Lance le sous-agent `link-picker` (type
`lgrdev-mcp-seo:link-picker`) avec cette consigne :

> Lis `.seo_work/candidats.json`. Pour chaque page cible, choisis au plus un paragraphe d'accueil
> et écris tes choix dans `.seo_work/choix.json` au format décrit dans tes instructions. Copie
> `paragraph_text` à l'octet près. Écarte une cible plutôt que de forcer un lien.

Le classement lexical ne juge pas le sens : c'est le rôle de ce sous-agent, et le passer
produirait des liens hors sujet. S'il n'est pas disponible, fais le choix toi-même en lisant
`.seo_work/candidats.json`, avec les mêmes règles, et écris le même JSON.

**c. Écrire le rapport** :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" proposals --from .seo_work/choix.json
```

L'outil vérifie que chaque paragraphe retenu existe **littéralement** dans son fichier source et
qu'il n'y apparaît qu'une fois, puis insère l'ancre de façon déterministe. Tout choix écarté est
listé avec sa raison : rapporte-les, ce sont souvent des paragraphes reformulés par le juge.

Indique ensuite à l'utilisateur le chemin de `propositions_seo.md`, le nombre de propositions, et
qu'il doit cocher `[x] OUI` sur celles qu'il retient avant de revenir.

## 2. Appliquer les propositions cochées

Simulation d'abord, toujours :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" apply --dry-run
```

Montre ce qui serait modifié, puis applique :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" apply
```

Rapporte le nombre de modifications, le dossier de sauvegarde (`.backups_seo/<horodatage>/`) et
les échecs. Un paragraphe présent plusieurs fois dans son fichier est refusé volontairement :
la retouche est alors à faire à la main.

Chaque bloc traité est horodaté `APPLIQUÉ` dans le rapport, donc relancer la commande ne
réapplique rien.

## 3. Repartir propre

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" archive
```

Donne le chemin de l'archive, puis propose `/lgrdev-mcp-seo:sync-seo` : l'audit reflètera les
liens qui viennent d'être ajoutés.
