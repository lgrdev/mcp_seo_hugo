import pytest

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


def test_parse_extracts_fields(seo):
    proposals = seo._parse_proposals(REPORT)
    assert [p["id"] for p in proposals] == ["1", "2"]
    assert proposals[0]["source_path"] == "blog/page-a.md"
    assert proposals[0]["approved"] is True
    assert proposals[0]["old"] == "Texte initial de la page A."
    assert proposals[0]["new"] == "Texte initial de la page A avec [un lien](/cible/)."
    assert proposals[0]["status"] is None
    assert proposals[1]["approved"] is False


def test_block_offsets_delimit_each_proposal(seo):
    proposals = seo._parse_proposals(REPORT)
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
def test_approval_detection_tolerates_case_and_spacing(seo, validation, approved):
    report = REPORT.replace("- **Validation :** [x] OUI / [ ] NON", validation, 1)
    assert seo._parse_proposals(report)[0]["approved"] is approved


def test_existing_status_is_read_back(seo):
    report = REPORT.replace(
        "- **Validation :** [x] OUI / [ ] NON",
        "- **Validation :** [x] OUI / [ ] NON\n- **Statut :** APPLIQUÉ le 2026-01-01 10:00:00",
        1,
    )
    assert seo._parse_proposals(report)[0]["status"].startswith("APPLIQUÉ")


def test_set_block_status_inserts_then_replaces(seo):
    block = "## Proposition 1\n- **Fichier source :** `a.md`\n- **Validation :** [x] OUI / [ ] NON\n"
    once = seo._set_block_status(block, "APPLIQUÉ le 2026-01-01 10:00:00")
    assert once.count("**Statut :**") == 1
    assert once.index("Statut") > once.index("Validation")

    twice = seo._set_block_status(once, "ÉCHEC : introuvable")
    assert twice.count("**Statut :**") == 1
    assert "ÉCHEC : introuvable" in twice
    assert "APPLIQUÉ" not in twice


def test_render_then_parse_roundtrip(seo):
    proposals = [{"source_path": "blog/x.md", "old": "Avant.", "new": "Après [lien](/y/)."}]
    parsed = seo._parse_proposals(seo._render_proposals_report(proposals))
    assert len(parsed) == 1
    assert parsed[0]["source_path"] == "blog/x.md"
    assert parsed[0]["old"] == "Avant."
    assert parsed[0]["new"] == "Après [lien](/y/)."
    assert parsed[0]["approved"] is False
