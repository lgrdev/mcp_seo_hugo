"""Chemins et seuils partagés par les sous-commandes de seoctl."""

from pathlib import Path

CONTENT_DIR = Path("./content")
AUDIT_DIR = Path("./audit-seo")
PROPOSALS_FILE = Path("./propositions_seo.md")
ARCHIVE_DIR = Path("./.archives_seo")
BACKUP_DIR = Path("./.backups_seo")

# Une page avec un seul lien entrant est traitée comme sous-maillée.
UNDERLINKED_MAX_IN_DEGREE = 1

# En dessous de ce seuil, un bloc est trop court pour accueillir une ancre lisible.
MIN_CHUNK_CHARS = 80
