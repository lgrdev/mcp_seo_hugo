"""Réparation ciblée des fichiers Markdown dont l'UTF-8 est cassé.

Corruption observée sur ce corpus : l'octet de continuation de « û » (C3 BB) a été
remplacé par un guillemet droit (C3 22). La réparation est volontairement octet par
octet : ré-encoder le fichier entier en cp1252 transformerait au contraire tous ses
accents déjà valides en mojibake. Ce qui n'est pas couvert par un motif connu est
signalé, jamais deviné.
"""

import shutil
from datetime import datetime
from pathlib import Path

from . import config

BROKEN_SEQUENCES = {b"\xc3\x22": b"\xc3\xbb"}


def scan(content_dir: Path | None = None) -> tuple[list[tuple[Path, bytes, int]], list[tuple[Path, str]]]:
    """Retourne (fichiers réparables + contenu corrigé + occurrences, fichiers à traiter à la main)."""
    content_dir = content_dir or config.CONTENT_DIR
    repairable, unknown = [], []

    for md_file in sorted(content_dir.rglob("*.md")):
        raw = md_file.read_bytes()
        try:
            raw.decode("utf-8")
            continue
        except UnicodeDecodeError:
            pass

        fixed = raw
        hits = 0
        for broken, replacement in BROKEN_SEQUENCES.items():
            hits += fixed.count(broken)
            fixed = fixed.replace(broken, replacement)

        try:
            fixed.decode("utf-8")
        except UnicodeDecodeError as exc:
            unknown.append((md_file, f"motif inconnu à l'octet {exc.start} ({exc.reason})"))
            continue

        repairable.append((md_file, fixed, hits))

    return repairable, unknown


def repair(apply: bool = False, content_dir: Path | None = None,
           backup_dir: Path | None = None) -> str:
    content_dir = content_dir or config.CONTENT_DIR
    backup_dir = backup_dir or config.BACKUP_DIR
    repairable, unknown = scan(content_dir)

    if not repairable and not unknown:
        return "Tous les fichiers de content/ sont déjà en UTF-8 valide."

    lines = []
    if repairable:
        total = sum(hits for _, _, hits in repairable)
        lines.append(f"{len(repairable)} fichier(s) réparable(s), {total} séquence(s) cassée(s) :")
        for md_file, _, hits in repairable:
            lines.append(f"- {md_file.relative_to(content_dir)} : {hits} occurrence(s)")
    if unknown:
        lines.append(f"\n{len(unknown)} fichier(s) à traiter manuellement :")
        for md_file, reason in unknown:
            lines.append(f"- {md_file.relative_to(content_dir)} : {reason}")

    if not apply:
        lines.append(
            f"\nMode simulation : aucun fichier modifié. Relance avec --apply pour "
            f"réparer {len(repairable)} fichier(s) (sauvegarde dans {backup_dir})."
        )
        return "\n".join(lines)

    repaired, failures = 0, []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for md_file, fixed, _ in repairable:
        rel = md_file.relative_to(content_dir)
        backup_path = backup_dir / timestamp / rel
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(md_file, backup_path)
            md_file.write_bytes(fixed)
            repaired += 1
        except OSError as exc:
            failures.append(f"{rel} : {exc}")

    lines.append(f"\n{repaired} fichier(s) réparé(s). Sauvegardes : {backup_dir / timestamp}")
    if failures:
        lines.append("Échecs :\n" + "\n".join(f"- {failure}" for failure in failures))
    lines.append("Relance l'audit pour prendre ces pages en compte.")
    return "\n".join(lines)
