"""Tests de bout en bout du CLI : mêmes chemins que ceux appelés par les skills."""

import json

import pytest

import seoctl
from seolib import config

PARAGRAPH = ("Excel reste utile au départ, mais devient un risque dès qu'il sert de base "
             "principale à un processus critique de l'entreprise.")


def _run(capsys, *argv) -> str:
    assert seoctl.main(list(argv)) == 0
    return capsys.readouterr().out


def test_audit_writes_the_html_report(write_page, capsys):
    write_page("a.md", 'title: "A"\nslug: "a"', PARAGRAPH)
    write_page("b.md", 'title: "B"\nslug: "b"', "Un lien vers [A](/a/).")

    out = _run(capsys, "audit")

    assert "Total pages : 2" in out
    assert "Total liens internes : 1" in out
    reports = list(config.AUDIT_DIR.glob("audit_seo_*.html"))
    assert len(reports) == 1
    html = reports[0].read_text(encoding="utf-8")
    assert "Audit SEO" in html
    assert "b.md" in html


def test_status_reports_content_and_next_step(write_page, capsys):
    write_page("a.md", 'title: "A"\nslug: "a"', PARAGRAPH)

    out = _run(capsys, "status")

    assert "1 page(s) dans le périmètre SEO" in out
    assert "1 paragraphe(s) exploitable(s)" in out
    assert "aucun rapport" in out
    assert "Propositions en cours : aucune" in out


def test_status_flags_unreadable_files(write_page, content_dir, capsys):
    write_page("a.md", 'title: "A"', PARAGRAPH)
    (content_dir / "casse.md").write_bytes(
        "---\ntitle: Casse\n---\n\nUn co".encode("utf-8") + b"\xc3\x22" + b"t.\n")

    out = _run(capsys, "status")

    assert "1 fichier(s) illisible(s)" in out
    assert "repair-seo" in out


def test_candidates_auto_emits_json_for_the_least_linked_targets(write_page, capsys):
    write_page("cible.md", 'title: "Passer d\'Excel à un outil métier"\nslug: "excel-outil"')
    write_page("hote.md", 'title: "Tableurs"\nslug: "tableurs"', PARAGRAPH)

    payload = json.loads(_run(capsys, "candidates", "--auto", "--max", "5", "--top", "3"))

    targets = {entry["target_path"] for entry in payload}
    assert "cible.md" in targets
    chosen = next(entry for entry in payload if entry["target_path"] == "cible.md")
    assert chosen["candidates"][0]["source_path"] == "hote.md"


def test_candidates_out_writes_a_file_instead_of_stdout(write_page, tmp_path, capsys):
    write_page("cible.md", 'title: "Tableurs Excel"\nslug: "tableurs-excel"')
    write_page("hote.md", 'title: "Hôte"\nslug: "hote"', PARAGRAPH)
    destination = tmp_path / "candidats.json"

    out = _run(capsys, "candidates", "--target", "cible.md", "--out", str(destination))

    assert str(destination) in out
    assert json.loads(destination.read_text(encoding="utf-8"))[0]["target_path"] == "cible.md"


def test_proposals_from_picks_then_apply(write_page, tmp_path, capsys):
    write_page("cible.md", 'title: "Tableurs Excel"\nslug: "tableurs-excel"')
    page = write_page("hote.md", 'title: "Hôte"\nslug: "hote"', PARAGRAPH)
    picks = tmp_path / "picks.json"
    picks.write_text(json.dumps({"picks": [
        {"target_path": "cible.md", "source_path": "hote.md", "paragraph_text": PARAGRAPH},
    ]}), encoding="utf-8")

    out = _run(capsys, "proposals", "--from", str(picks))
    assert "1 proposition(s) écrite(s)" in out

    report = config.PROPOSALS_FILE.read_text(encoding="utf-8")
    assert "/tableurs-excel/" in report
    config.PROPOSALS_FILE.write_text(report.replace("[ ] OUI", "[x] OUI", 1), encoding="utf-8")

    out = _run(capsys, "apply", "--dry-run")
    assert "1 modification(s) seraient appliquée(s)" in out
    assert "/tableurs-excel/" not in page.read_text(encoding="utf-8")

    out = _run(capsys, "apply")
    assert "1 modification(s) appliquée(s)" in out
    assert "/tableurs-excel/" in page.read_text(encoding="utf-8")

    out = _run(capsys, "archive")
    assert "archivé" in out
    assert list(config.ARCHIVE_DIR.glob("propositions_*.md"))


def test_proposals_refuses_a_paragraph_absent_from_the_file(write_page, tmp_path, capsys):
    # Garde-fou contre un juge qui reformule le paragraphe au lieu de le citer.
    write_page("cible.md", 'title: "Cible"\nslug: "cible"')
    write_page("hote.md", 'title: "Hôte"\nslug: "hote"', PARAGRAPH)
    picks = tmp_path / "picks.json"
    picks.write_text(json.dumps({"picks": [
        {"target_path": "cible.md", "source_path": "hote.md",
         "paragraph_text": "Un paragraphe reformulé qui n'existe pas dans le fichier."},
    ]}), encoding="utf-8")

    out = _run(capsys, "proposals", "--from", str(picks))

    assert "Aucune proposition retenue" in out
    assert "paragraphe introuvable" in out
    assert not config.PROPOSALS_FILE.exists()


def test_proposals_refuses_an_unknown_target(write_page, tmp_path, capsys):
    write_page("hote.md", 'title: "Hôte"\nslug: "hote"', PARAGRAPH)
    picks = tmp_path / "picks.json"
    picks.write_text(json.dumps([
        {"target_path": "absente.md", "source_path": "hote.md", "paragraph_text": PARAGRAPH},
    ]), encoding="utf-8")

    out = _run(capsys, "proposals", "--from", str(picks))

    assert "cible inconnue" in out


def test_repair_dry_run_then_apply(content_dir, capsys):
    broken = content_dir / "casse.md"
    broken.write_bytes("Un co".encode("utf-8") + b"\xc3\x22" + b"t.\n")

    assert "Mode simulation" in _run(capsys, "repair")
    assert broken.read_bytes().endswith(b"\xc3\x22" + b"t.\n")

    assert "1 fichier(s) réparé(s)" in _run(capsys, "repair", "--apply")
    assert broken.read_text(encoding="utf-8") == "Un coût.\n"


def test_missing_content_dir_is_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "CONTENT_DIR", tmp_path / "absent")

    assert seoctl.main(["status"]) == 2
    assert "introuvable" in capsys.readouterr().err


def test_candidates_requires_a_mode(capsys):
    with pytest.raises(SystemExit):
        seoctl.main(["candidates"])
