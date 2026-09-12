from seolib.content import build_chunks, load_pages, read_front_matter, unreadable

LONG_PARAGRAPH = ("Un paragraphe de prose assez long pour depasser le seuil de quatre-vingts "
                  "caracteres impose par le decoupage en blocs.")


def test_front_matter_reads_scalars_bools_and_lists():
    meta, body = read_front_matter(
        '---\n'
        'title: "Un titre : avec deux-points"\n'
        'slug: mon-slug\n'
        'draft: true\n'
        'option_seo: false\n'
        'aliases:\n'
        '  - /ancien/\n'
        '  - /tres-ancien/\n'
        '---\n\nLe corps.\n'
    )
    assert meta["title"] == "Un titre : avec deux-points"
    assert meta["slug"] == "mon-slug"
    assert meta["draft"] is True
    assert meta["option_seo"] is False
    assert meta["aliases"] == ["/ancien/", "/tres-ancien/"]
    assert body.strip() == "Le corps."


def test_front_matter_ignores_nested_blocks():
    # Le corpus contient des maps imbriquées (faq, liens_utiles) et des tableaux JSON
    # multi-lignes : le lecteur les saute au lieu de tenter d'interpréter du YAML.
    meta, _ = read_front_matter(
        '---\n'
        'title: "Page"\n'
        'faq:\n'
        '  - question: "Pourquoi ?"\n'
        '    answer: "Parce que."\n'
        'categories:\n'
        '  [\n'
        '    "Docker",\n'
        '  ]\n'
        'slug: apres-le-bloc\n'
        '---\n\nCorps.\n'
    )
    assert meta["title"] == "Page"
    assert meta["slug"] == "apres-le-bloc"


def test_front_matter_absent_returns_whole_text():
    meta, body = read_front_matter("Pas de front matter ici.\n")
    assert meta == {}
    assert body == "Pas de front matter ici.\n"


def test_load_pages_records_every_exclusion(write_page, content_dir):
    write_page("ok.md", 'title: "Page OK"')
    write_page("brouillon.md", 'title: "Draft"\ndraft: true')
    write_page("hors-seo.md", 'title: "Hors SEO"\noption_seo: false')
    write_page("noindex.md", 'title: "Noindex"\nrobots: "noindex, nofollow"')
    (content_dir / "casse.md").write_bytes(
        "---\ntitle: Casse\n---\n\nUn co".encode("utf-8") + b"\xc3\x22" + b"t mal encode.\n"
    )

    pages, skipped = load_pages()

    assert set(pages) == {"ok.md"}
    reasons = {item["path"]: item["reason"] for item in skipped}
    assert reasons["brouillon.md"] == "draft"
    assert reasons["hors-seo.md"] == "option_seo: false"
    assert reasons["noindex.md"] == "robots: noindex"
    assert reasons["casse.md"].startswith("encodage invalide")
    assert [item["path"] for item in unreadable(skipped)] == ["casse.md"]


def test_load_pages_falls_back_to_the_file_stem(write_page):
    write_page("sans-titre.md", 'description: "Aucun titre ni slug"')

    pages, _ = load_pages()

    assert pages["sans-titre.md"]["title"] == "sans-titre"
    assert pages["sans-titre.md"]["slug"] == "sans-titre"


def test_build_chunks_skips_short_and_list_blocks(write_page):
    write_page("page.md", 'title: "Page"',
               f"{LONG_PARAGRAPH}\n\nTrop court.\n\n- puce une\n- puce deux\n- puce trois")

    chunks = build_chunks(load_pages()[0])

    assert [chunk.text for chunk in chunks] == [LONG_PARAGRAPH]
    assert chunks[0].source_path == "page.md"
    assert chunks[0].title == "Page"


def test_build_chunks_strips_code_images_and_headings(write_page):
    body = (f"{LONG_PARAGRAPH}\n\n```python\nprint('un bloc de code assez long pour compter')\n```"
            f"\n\n![une image avec une legende suffisamment longue](/img/x.png)\n\n"
            f"## Un titre de section qui depasserait le seuil de quatre-vingts caracteres ici")
    write_page("page.md", 'title: "Page"', body)

    chunks = build_chunks(load_pages()[0])

    assert [chunk.text for chunk in chunks] == [LONG_PARAGRAPH]
