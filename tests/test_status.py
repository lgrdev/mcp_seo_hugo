def _write(content_dir, name, front_matter, body):
    path = content_dir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front_matter}\n---\n\n{body}\n", encoding="utf-8")


LONG_PARAGRAPH = ("Un paragraphe de prose assez long pour depasser le seuil de quatre-vingts "
                  "caracteres impose par le decoupage en chunks.")


def test_status_reports_absent_index(seo, content_dir, monkeypatch, tmp_path):
    # Le stub chromadb de conftest fait echouer get_collection : cas « index absent ».
    monkeypatch.setattr(seo, "AUDIT_DIR", tmp_path / "audit-seo")
    monkeypatch.setattr(seo, "PROPOSALS_FILE", tmp_path / "propositions_seo.md")
    _write(content_dir, "page.md", 'title: "Page"', LONG_PARAGRAPH)

    status = seo.get_index_status()

    assert "1 page(s) dans le périmètre SEO" in status
    assert "1 paragraphe(s) indexable(s)" in status
    assert "Index sémantique : absent" in status
    assert "aucun rapport" in status
    assert "Propositions en cours : aucune" in status


def test_status_flags_unreadable_files(seo, content_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(seo, "AUDIT_DIR", tmp_path / "audit-seo")
    monkeypatch.setattr(seo, "PROPOSALS_FILE", tmp_path / "propositions_seo.md")
    _write(content_dir, "page.md", 'title: "Page"', LONG_PARAGRAPH)
    (content_dir / "casse.md").write_bytes(
        "---\ntitle: Casse\n---\n\nUn co".encode("utf-8") + b"\xc3\x22" + b"t.\n"
    )

    status = seo.get_index_status()

    assert "1 fichier(s) illisible(s)" in status
    assert "repair-seo" in status


def test_status_counts_pending_proposals(seo, content_dir, monkeypatch, tmp_path):
    monkeypatch.setattr(seo, "AUDIT_DIR", tmp_path / "audit-seo")
    proposals = tmp_path / "propositions_seo.md"
    proposals.write_text(
        seo._render_proposals_report([
            {"source_path": "a.md", "old": "Avant un.", "new": "Après un."},
            {"source_path": "b.md", "old": "Avant deux.", "new": "Après deux."},
        ]).replace("- **Validation :** [ ] OUI / [ ] NON",
                   "- **Validation :** [x] OUI / [ ] NON", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(seo, "PROPOSALS_FILE", proposals)

    status = seo.get_index_status()

    assert "2 au total, 1 cochée(s) OUI, 0 déjà appliquée(s)" in status
    assert "review-seo" in status


def test_build_chunks_skips_short_and_list_blocks(seo, content_dir):
    _write(content_dir, "page.md", 'title: "Page"',
           f"{LONG_PARAGRAPH}\n\nTrop court.\n\n- puce une\n- puce deux\n- puce trois")

    pages, _ = seo.load_pages()
    documents, metadatas, ids = seo.build_chunks(pages)

    assert documents == [LONG_PARAGRAPH]
    assert metadatas == [{"source_path": "page.md", "title": "Page"}]
    assert ids[0].startswith("page.md#")


def test_build_chunks_ids_are_content_addressed(seo, content_dir):
    other = "Un second paragraphe de prose, lui aussi bien au-dessus du seuil de quatre-vingts caracteres."
    _write(content_dir, "page.md", 'title: "Page"', f"{LONG_PARAGRAPH}\n\n{other}")
    before = seo.build_chunks(seo.load_pages()[0])[2]

    # Insérer un paragraphe en tête ne doit pas changer l'id des suivants.
    _write(content_dir, "page.md", 'title: "Page"', f"{other}\n\n{LONG_PARAGRAPH}")
    after = seo.build_chunks(seo.load_pages()[0])[2]

    assert set(before) == set(after)
