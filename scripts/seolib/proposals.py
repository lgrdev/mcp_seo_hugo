"""Boucle de validation humaine : rapport de propositions, application, archivage.

Seul chemin d'écriture dans `content/`. Les garde-fous d'origine sont conservés :
refus d'un paragraphe présent plusieurs fois, sauvegarde avant première écriture,
réécriture des blocs à l'envers pour garder les offsets valides, idempotence.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path

from . import config

PROPOSALS_HEADER = """# Propositions de maillage interne

Ce fichier est généré par la commande `/lgrdev-mcp-seo:review-seo`.

Pour valider une proposition, coche la case OUI : `- **Validation :** [x] OUI / [ ] NON`
Puis relance `/lgrdev-mcp-seo:review-seo` : seules les propositions cochées OUI
seront appliquées dans les fichiers Markdown sources.

Une fois les modifications appliquées, le rapport est déplacé dans `.archives_seo/`
et réinitialisé.
"""


def render_proposals_report(proposals: list[dict]) -> str:
    parts = [PROPOSALS_HEADER]
    for index, proposal in enumerate(proposals, start=1):
        parts.append(
            f"""## Proposition {index}
- **Fichier source :** `{proposal['source_path']}`
- **Validation :** [ ] OUI / [ ] NON

### Paragraphe original :
```text
{proposal['old']}
```

### Paragraphe proposé :
```text
{proposal['new']}
```
---
"""
        )
    return "\n".join(parts)


def parse_proposals(text: str) -> list[dict]:
    """Parse le rapport Markdown. Tolérant aux espaces, à la casse et aux lignes vides."""
    headings = list(re.finditer(r"^##\s+Proposition\s+(\S+)\s*$", text, flags=re.MULTILINE))
    proposals = []

    for position, heading in enumerate(headings):
        start = heading.start()
        end = headings[position + 1].start() if position + 1 < len(headings) else len(text)
        block = text[start:end]

        source = re.search(r"\*\*Fichier\s+source\s*:?\s*\*\*\s*`?([^`\n]+?)`?\s*$", block,
                           flags=re.MULTILINE | re.IGNORECASE)
        fences = re.findall(r"```(?:text)?\s*\n(.*?)```", block, flags=re.DOTALL)
        status = re.search(r"\*\*Statut\s*:?\s*\*\*\s*(.+?)\s*$", block,
                           flags=re.MULTILINE | re.IGNORECASE)

        proposals.append({
            "id": heading.group(1),
            "block_start": start,
            "block_end": end,
            "source_path": source.group(1).strip() if source else None,
            "approved": bool(re.search(r"\[\s*[xX]\s*\]\s*OUI", block, flags=re.IGNORECASE)),
            "old": fences[0].rstrip("\n") if len(fences) >= 1 else None,
            "new": fences[1].rstrip("\n") if len(fences) >= 2 else None,
            "status": status.group(1).strip() if status else None,
        })

    return proposals


def set_block_status(block: str, status: str) -> str:
    """Ajoute ou remplace la ligne de statut juste après la ligne de validation."""
    status_line = f"- **Statut :** {status}"
    if re.search(r"^-\s*\*\*Statut\s*:?\s*\*\*.*$", block, flags=re.MULTILINE | re.IGNORECASE):
        return re.sub(r"^-\s*\*\*Statut\s*:?\s*\*\*.*$", status_line, block,
                      count=1, flags=re.MULTILINE | re.IGNORECASE)
    return re.sub(r"^(-\s*\*\*Validation\s*:?\s*\*\*.*)$", rf"\1\n{status_line}", block,
                  count=1, flags=re.MULTILINE | re.IGNORECASE)


def backup_content_file(full_path: Path, rel_path: str, run_timestamp: str,
                        backup_dir: Path | None = None) -> Path | None:
    """Copie le fichier source avant première modification. None s'il est déjà sauvegardé."""
    backup_dir = backup_dir or config.BACKUP_DIR
    backup_path = backup_dir / run_timestamp / rel_path
    if backup_path.exists():
        return None
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(full_path, backup_path)
    return backup_path


def replace_paragraph(file_path: str, old_paragraph: str, new_paragraph: str,
                      dry_run: bool = False, run_timestamp: str | None = None,
                      content_dir: Path | None = None,
                      backup_dir: Path | None = None) -> str:
    content_dir = content_dir or config.CONTENT_DIR
    full_path = content_dir / file_path
    if not full_path.exists():
        return f"Erreur : Fichier {file_path} introuvable."

    try:
        content = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"Erreur : Lecture impossible de {file_path} ({exc})."

    occurrences = content.count(old_paragraph)
    if occurrences == 0:
        return f"Erreur : Le paragraphe d'origine est introuvable dans {file_path}."
    # Un remplacement aveugle sur la 1re occurrence toucherait peut-être le mauvais endroit.
    if occurrences > 1:
        return (f"Erreur : Le paragraphe apparaît {occurrences} fois dans {file_path}, "
                f"remplacement ambigu. Modifie-le manuellement ou rends le paragraphe unique.")

    if dry_run:
        return f"Simulation : {file_path} serait modifié (1 occurrence trouvée)."

    updated = content.replace(old_paragraph, new_paragraph, 1)
    try:
        backup_content_file(full_path, file_path,
                            run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S"),
                            backup_dir=backup_dir)
        full_path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        return f"Erreur : Écriture impossible dans {file_path} ({exc})."

    return f"Succès : Fichier {file_path} mis à jour avec le nouveau lien."


def apply_approved(report_path: Path, dry_run: bool = False,
                   content_dir: Path | None = None,
                   backup_dir: Path | None = None) -> str:
    """Applique les propositions cochées OUI et horodate chaque bloc traité."""
    backup_dir = backup_dir or config.BACKUP_DIR
    try:
        text = report_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"Erreur : Lecture impossible de {report_path} ({exc})."

    proposals = parse_proposals(text)
    if not proposals:
        return f"Aucune proposition trouvée dans {report_path}."

    applied, already, refused, failures = 0, 0, 0, []
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    updated_text = text

    # Parcours en ordre inverse : les offsets des blocs restent valides pendant la réécriture.
    for proposal in reversed(proposals):
        if not proposal["approved"]:
            refused += 1
            continue
        if proposal["status"] and proposal["status"].startswith("APPLIQUÉ"):
            already += 1
            continue

        if not proposal["source_path"] or proposal["old"] is None or proposal["new"] is None:
            status = "ÉCHEC : bloc incomplet (fichier source ou paragraphes manquants)"
            failures.append(f"Proposition {proposal['id']} : bloc incomplet")
        else:
            result = replace_paragraph(proposal["source_path"], proposal["old"], proposal["new"],
                                       dry_run=dry_run, run_timestamp=run_timestamp,
                                       content_dir=content_dir, backup_dir=backup_dir)
            if result.startswith(("Succès", "Simulation")):
                status = f"APPLIQUÉ le {stamp}"
                applied += 1
            else:
                status = f"ÉCHEC : {result}"
                failures.append(f"Proposition {proposal['id']} : {result}")

        if dry_run:
            continue

        block = updated_text[proposal["block_start"]:proposal["block_end"]]
        updated_text = (
            updated_text[:proposal["block_start"]]
            + set_block_status(block, status)
            + updated_text[proposal["block_end"]:]
        )

    if dry_run:
        summary = (
            f"Simulation : {applied} modification(s) seraient appliquée(s), "
            f"{already} déjà appliquée(s), {refused} non validée(s), {len(failures)} bloquée(s).\n"
            f"Aucun fichier modifié. Relance sans --dry-run pour appliquer."
        )
        if failures:
            summary += "\n" + "\n".join(f"- {failure}" for failure in failures)
        return summary

    try:
        report_path.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        return (f"Erreur : {applied} modification(s) appliquée(s) mais mise à jour de "
                f"{report_path} impossible ({exc}).")

    summary = (
        f"{applied} modification(s) appliquée(s), {already} déjà appliquée(s), "
        f"{refused} non validée(s), {len(failures)} échec(s)."
    )
    if applied:
        summary += f"\nSauvegardes des fichiers modifiés : {backup_dir / run_timestamp}"
    if failures:
        summary += "\n" + "\n".join(f"- {failure}" for failure in failures)
    return summary


def archive_report(report_path: Path, archive_dir: Path | None = None) -> str:
    """Archive le rapport avec horodatage et réinitialise un fichier vierge."""
    archive_dir = archive_dir or config.ARCHIVE_DIR
    if not report_path.exists():
        return f"Erreur : Fichier {report_path} introuvable."

    archive_path = archive_dir / f"propositions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(report_path), str(archive_path))
        report_path.write_text(PROPOSALS_HEADER, encoding="utf-8")
    except OSError as exc:
        return f"Erreur : Archivage impossible ({exc})."

    return f"Rapport archivé dans {archive_path}. {report_path} réinitialisé (en-tête seul)."
