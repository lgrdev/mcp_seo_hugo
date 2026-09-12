PAGES = {
    "audit_pme.md": {"slug": "audit_tpe_pme", "aliases": [], "title": "", "content": ""},
    "services/audit_tpe_pme.md": {"slug": "audit-services", "aliases": ["ancien-audit"],
                                  "title": "", "content": ""},
    "blog/2025-12/postgresql-tde.md": {"slug": "postgresql-17-tde-mtls", "aliases": [],
                                       "title": "", "content": ""},
}


def test_resolve_prefers_exact_slug(seo):
    assert seo._resolve_target("audit_tpe_pme", PAGES) == "audit_pme.md"


def test_resolve_by_alias(seo):
    assert seo._resolve_target("ancien-audit", PAGES) == "services/audit_tpe_pme.md"


def test_resolve_by_exact_path_and_filename(seo):
    assert seo._resolve_target("audit_pme.md", PAGES) == "audit_pme.md"
    assert seo._resolve_target("audit_pme", PAGES) == "audit_pme.md"


def test_resolve_by_last_segment(seo):
    assert seo._resolve_target("blog/postgresql-17-tde-mtls", PAGES) == "blog/2025-12/postgresql-tde.md"


def test_resolve_refuses_substring_match(seo):
    # Régression : « audit » matchait trois pages par sous-chaîne, la première
    # arrivée dans le dict gagnait, ce qui gonflait la liste des orphelines.
    assert seo._resolve_target("audit", PAGES) is None
    assert seo._resolve_target("postgresql", PAGES) is None


def test_resolve_unknown_target(seo):
    assert seo._resolve_target("page-inexistante", PAGES) is None
    assert seo._resolve_target("", PAGES) is None


def _write(content_dir, name, front_matter, body="Corps de page suffisamment long pour l'index."):
    path = content_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front_matter}\n---\n\n{body}\n", encoding="utf-8")
    return path


def test_load_pages_records_every_exclusion(seo, content_dir):
    _write(content_dir, "ok.md", 'title: "Page OK"')
    _write(content_dir, "brouillon.md", 'title: "Draft"\ndraft: true')
    _write(content_dir, "hors-seo.md", 'title: "Hors SEO"\noption_seo: false')
    _write(content_dir, "noindex.md", 'title: "Noindex"\nrobots: "noindex, nofollow"')
    (content_dir / "casse.md").write_bytes(
        "---\ntitle: Casse\n---\n\nUn co\xc3\x22t mal encode.\n".encode("latin-1")
    )

    pages, skipped = seo.load_pages()

    assert set(pages) == {"ok.md"}
    reasons = {item["path"]: item["reason"] for item in skipped}
    assert reasons["brouillon.md"] == "draft"
    assert reasons["hors-seo.md"] == "option_seo: false"
    assert reasons["noindex.md"] == "robots: noindex"
    assert reasons["casse.md"].startswith("encodage invalide")


def test_graph_collects_unresolved_links(seo, content_dir):
    _write(content_dir, "source.md", 'title: "Source"',
           "Voir [la cible](/cible/) et [le vide](/nulle-part/).")
    _write(content_dir, "cible.md", 'title: "Cible"\nslug: "cible"')

    G = seo.graph_from_pages(*seo.load_pages())

    assert G.has_edge("source.md", "cible.md")
    assert [item["target"] for item in G.graph["unresolved"]] == ["/nulle-part/"]


def test_graph_ignores_external_links(seo, content_dir):
    _write(content_dir, "source.md", 'title: "Source"',
           "Voir [ext](https://example.com/) et [mail](mailto:a@b.c) et [ancre](#section).")

    G = seo.graph_from_pages(*seo.load_pages())

    assert G.number_of_edges() == 0
    assert G.graph["unresolved"] == []


def test_replace_paragraph_refuses_ambiguous_match(seo, content_dir):
    page = _write(content_dir, "double.md", 'title: "Double"',
                  "Paragraphe repete.\n\nAutre chose.\n\nParagraphe repete.")

    result = seo._replace_paragraph("double.md", "Paragraphe repete.", "Modifie")

    assert "2 fois" in result
    assert "Modifie" not in page.read_text(encoding="utf-8")


def test_replace_paragraph_backs_up_before_writing(seo, content_dir):
    page = _write(content_dir, "unique.md", 'title: "Unique"', "Un seul paragraphe ici.")

    result = seo._replace_paragraph("unique.md", "Un seul paragraphe ici.", "Remplace.",
                                    run_timestamp="20260101_000000")

    assert result.startswith("Succès")
    assert "Remplace." in page.read_text(encoding="utf-8")
    backup = seo.BACKUP_DIR / "20260101_000000" / "unique.md"
    assert "Un seul paragraphe ici." in backup.read_text(encoding="utf-8")


def test_replace_paragraph_dry_run_changes_nothing(seo, content_dir):
    page = _write(content_dir, "unique.md", 'title: "Unique"', "Un seul paragraphe ici.")

    result = seo._replace_paragraph("unique.md", "Un seul paragraphe ici.", "Remplace.",
                                    dry_run=True)

    assert result.startswith("Simulation")
    assert "Remplace." not in page.read_text(encoding="utf-8")
    assert not seo.BACKUP_DIR.exists()


def test_repair_encoding_dry_run_detects_without_writing(seo, content_dir):
    broken = content_dir / "casse.md"
    original = "---\ntitle: Casse\n---\n\nUn co\xc3\x22t et bien s\xc3\x22r.\n".encode("latin-1")
    broken.write_bytes(original)

    result = seo.repair_content_encoding()

    assert "casse.md : 2 occurrence(s)" in result
    assert broken.read_bytes() == original


def test_repair_encoding_fixes_only_broken_bytes(seo, content_dir):
    broken = content_dir / "casse.md"
    # « avancées » est déjà du bon UTF-8 : un ré-encodage global le transformerait
    # en mojibake. Seule la séquence cassée doit changer.
    broken.write_bytes("Fonctions avancées, un co".encode("utf-8") + b"\xc3\x22" + b"t.\n")

    result = seo.repair_content_encoding(dry_run=False)

    assert "1 fichier(s) réparé(s)" in result
    assert broken.read_text(encoding="utf-8") == "Fonctions avancées, un coût.\n"
