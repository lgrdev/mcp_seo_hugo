import pytest

from seolib import config
from seolib.proposals import (apply_approved, archive_report, parse_proposals,
                              render_proposals_report, replace_paragraph, set_block_status)

REPORT = """# Propositions

## Proposition 1
- **Fichier source :** `blog/page-a.md`
- **Validation :** [x] OUI / [ ] NON

### Paragraphe original :
```text
Texte initial de la page A.
```

### Paragraphe proposé :
```text
Texte initial de la page A avec [un lien](/cible/).
```
---

## Proposition 2
- **Fichier source :** `blog/page-b.md`
- **Validation :** [ ] OUI / [ ] NON

### Paragraphe original :
```text
Texte de la page B.
```

### Paragraphe proposé :
```text
Texte de la page B enrichi.
```
---
"""


def test_parse_extracts_fields():
    proposals = parse_proposals(REPORT)
    assert [p["id"] for p in proposals] == ["1", "2"]
    assert proposals[0]["source_path"] == "blog/page-a.md"
    assert proposals[0]["approved"] is True
    assert proposals[0]["old"] == "Texte initial de la page A."
    assert proposals[0]["new"] == "Texte initial de la page A avec [un lien](/cible/)."
    assert proposals[0]["status"] is None
    assert proposals[1]["approved"] is False


def test_block_offsets_delimit_each_proposal():
    proposals = parse_proposals(REPORT)
    first = REPORT[proposals[0]["block_start"]:proposals[0]["block_end"]]
    assert "Proposition 1" in first
    assert "Proposition 2" not in first


@pytest.mark.parametrize("validation, approved", [
    ("- **Validation :** [x] OUI / [ ] NON", True),
    ("- **Validation :** [X] OUI / [ ] NON", True),
    ("- **Validation :**  [ x ]  oui  /  [ ] non", True),
    ("- **Validation :** [ ] OUI / [x] NON", False),
    ("- **Validation :** [ ] OUI / [ ] NON", False),
])
def test_approval_detection_tolerates_case_and_spacing(validation, approved):
    report = REPORT.replace("- **Validation :** [x] OUI / [ ] NON", validation, 1)
    assert parse_proposals(report)[0]["approved"] is approved


def test_existing_status_is_read_back():
    report = REPORT.replace(
        "- **Validation :** [x] OUI / [ ] NON",
        "- **Validation :** [x] OUI / [ ] NON\n- **Statut :** APPLIQUÉ le 2026-01-01 10:00:00",
        1,
    )
    assert parse_proposals(report)[0]["status"].startswith("APPLIQUÉ")


def test_set_block_status_inserts_then_replaces():
    block = "## Proposition 1\n- **Fichier source :** `a.md`\n- **Validation :** [x] OUI / [ ] NON\n"
    once = set_block_status(block, "APPLIQUÉ le 2026-01-01 10:00:00")
    assert once.count("**Statut :**") == 1
    assert once.index("Statut") > once.index("Validation")

    twice = set_block_status(once, "ÉCHEC : introuvable")
    assert twice.count("**Statut :**") == 1
    assert "ÉCHEC : introuvable" in twice
    assert "APPLIQUÉ" not in twice


def test_render_then_parse_roundtrip():
    proposals = [{"source_path": "blog/x.md", "old": "Avant.", "new": "Après [lien](/y/)."}]
    parsed = parse_proposals(render_proposals_report(proposals))
    assert len(parsed) == 1
    assert parsed[0]["source_path"] == "blog/x.md"
    assert parsed[0]["old"] == "Avant."
    assert parsed[0]["new"] == "Après [lien](/y/)."
    assert parsed[0]["approved"] is False


def test_replace_paragraph_refuses_ambiguous_match(write_page):
    page = write_page("double.md", 'title: "Double"',
                      "Paragraphe repete.\n\nAutre chose.\n\nParagraphe repete.")

    result = replace_paragraph("double.md", "Paragraphe repete.", "Modifie")

    assert "2 fois" in result
    assert "Modifie" not in page.read_text(encoding="utf-8")


def test_replace_paragraph_backs_up_before_writing(write_page):
    page = write_page("unique.md", 'title: "Unique"', "Un seul paragraphe ici.")

    result = replace_paragraph("unique.md", "Un seul paragraphe ici.", "Remplace.",
                               run_timestamp="20260101_000000")

    assert result.startswith("Succès")
    assert "Remplace." in page.read_text(encoding="utf-8")
    backup = config.BACKUP_DIR / "20260101_000000" / "unique.md"
    assert "Un seul paragraphe ici." in backup.read_text(encoding="utf-8")


def test_replace_paragraph_dry_run_changes_nothing(write_page):
    page = write_page("unique.md", 'title: "Unique"', "Un seul paragraphe ici.")

    result = replace_paragraph("unique.md", "Un seul paragraphe ici.", "Remplace.", dry_run=True)

    assert result.startswith("Simulation")
    assert "Remplace." not in page.read_text(encoding="utf-8")
    assert not config.BACKUP_DIR.exists()


def test_replace_paragraph_reports_a_missing_file(content_dir):
    assert "introuvable" in replace_paragraph("absente.md", "x", "y")


def _one_proposal_report(source_path, old, new, approved):
    report = render_proposals_report([{"source_path": source_path, "old": old, "new": new}])
    if approved:
        report = report.replace("[ ] OUI", "[x] OUI", 1)
    return report


def test_apply_writes_only_approved_blocks_and_stamps_them(write_page, tmp_path):
    page = write_page("a.md", 'title: "A"', "Le paragraphe d'origine.")
    report_path = tmp_path / "propositions_seo.md"
    report_path.write_text(
        _one_proposal_report("a.md", "Le paragraphe d'origine.", "Le paragraphe enrichi.", True),
        encoding="utf-8")

    result = apply_approved(report_path)

    assert "1 modification(s) appliquée(s)" in result
    assert "Le paragraphe enrichi." in page.read_text(encoding="utf-8")
    assert "APPLIQUÉ le" in report_path.read_text(encoding="utf-8")


def test_apply_is_idempotent(write_page, tmp_path):
    write_page("a.md", 'title: "A"', "Le paragraphe d'origine.")
    report_path = tmp_path / "propositions_seo.md"
    report_path.write_text(
        _one_proposal_report("a.md", "Le paragraphe d'origine.", "Le paragraphe enrichi.", True),
        encoding="utf-8")

    apply_approved(report_path)
    second = apply_approved(report_path)

    assert "0 modification(s) appliquée(s), 1 déjà appliquée(s)" in second


def test_apply_dry_run_touches_neither_content_nor_report(write_page, tmp_path):
    page = write_page("a.md", 'title: "A"', "Le paragraphe d'origine.")
    report_path = tmp_path / "propositions_seo.md"
    original = _one_proposal_report("a.md", "Le paragraphe d'origine.", "Enrichi.", True)
    report_path.write_text(original, encoding="utf-8")

    result = apply_approved(report_path, dry_run=True)

    assert "1 modification(s) seraient appliquée(s)" in result
    assert "Enrichi." not in page.read_text(encoding="utf-8")
    assert report_path.read_text(encoding="utf-8") == original


def test_apply_records_a_failure_without_stopping(write_page, tmp_path):
    write_page("a.md", 'title: "A"', "Un autre texte.")
    report_path = tmp_path / "propositions_seo.md"
    report_path.write_text(
        _one_proposal_report("a.md", "Paragraphe absent du fichier.", "Enrichi.", True),
        encoding="utf-8")

    result = apply_approved(report_path)

    assert "1 échec(s)" in result
    assert "ÉCHEC" in report_path.read_text(encoding="utf-8")


def test_archive_moves_the_report_and_resets_it(tmp_path, content_dir):
    report_path = tmp_path / "propositions_seo.md"
    report_path.write_text(REPORT, encoding="utf-8")

    result = archive_report(report_path)

    assert "archivé" in result
    assert list(config.ARCHIVE_DIR.glob("propositions_*.md"))
    assert "Proposition 1" not in report_path.read_text(encoding="utf-8")


def test_archive_reports_a_missing_report(tmp_path, content_dir):
    assert "introuvable" in archive_report(tmp_path / "absent.md")
