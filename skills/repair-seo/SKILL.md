---
description: Détecte et répare les fichiers Markdown de ./content dont l'encodage UTF-8 est cassé, puis relance l'audit.
disable-model-invocation: true
allowed-tools: ["Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py *)"]
---

Cette commande écrit dans les fichiers sources de l'utilisateur. Procède toujours en deux temps.

**1. Simulation, systématiquement**

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" repair
```

Sans `--apply`, rien n'est écrit. Présente :

- la liste des fichiers concernés et le nombre de séquences cassées ;
- les fichiers signalés « à traiter manuellement » : l'outil ne devine jamais un caractère
  qu'il ne reconnaît pas, ceux-là restent à corriger à la main.

Si tous les fichiers sont déjà en UTF-8 valide, dis-le et arrête-toi ici.

**2. Réparation, après accord explicite**

Demande confirmation, puis :

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/seoctl.py" repair --apply
```

La correction est faite octet par octet sur des motifs connus. C'est volontaire : ré-encoder un
fichier entier transformerait ses accents déjà valides en mojibake. Rapporte le nombre de
fichiers réparés et le dossier de sauvegarde (`.backups_seo/<horodatage>/`).

Propose ensuite `/lgrdev-mcp-seo:sync-seo` : les pages réparées entrent dans le périmètre
d'analyse, donc les chiffres de l'audit changent.

N'appelle jamais `--apply` sans avoir montré la simulation d'abord.
