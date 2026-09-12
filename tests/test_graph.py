from seolib.content import load_pages
from seolib.graph import build_site, resolve_target

PAGES = {
    "audit_pme.md": {"slug": "audit_tpe_pme", "aliases": [], "title": "", "content": ""},
    "services/audit_tpe_pme.md": {"slug": "audit-services", "aliases": ["ancien-audit"],
                                  "title": "", "content": ""},
    "blog/2025-12/postgresql-tde.md": {"slug": "postgresql-17-tde-mtls", "aliases": [],
                                       "title": "", "content": ""},
}


def test_resolve_prefers_exact_slug():
    assert resolve_target("audit_tpe_pme", PAGES) == "audit_pme.md"


def test_resolve_by_alias():
    assert resolve_target("ancien-audit", PAGES) == "services/audit_tpe_pme.md"


def test_resolve_by_exact_path_and_filename():
    assert resolve_target("audit_pme.md", PAGES) == "audit_pme.md"
    assert resolve_target("audit_pme", PAGES) == "audit_pme.md"


def test_resolve_by_last_segment():
    assert resolve_target("blog/postgresql-17-tde-mtls", PAGES) == "blog/2025-12/postgresql-tde.md"


def test_resolve_refuses_substring_match():
    # Régression : « audit » matchait trois pages par sous-chaîne, la première
    # arrivée dans le dict gagnait, ce qui gonflait la liste des orphelines.
    assert resolve_target("audit", PAGES) is None
    assert resolve_target("postgresql", PAGES) is None


def test_resolve_unknown_target():
    assert resolve_target("page-inexistante", PAGES) is None
    assert resolve_target("", PAGES) is None


def test_site_collects_unresolved_links(write_page):
    write_page("source.md", 'title: "Source"',
               "Voir [la cible](/cible/) et [le vide](/nulle-part/).")
    write_page("cible.md", 'title: "Cible"\nslug: "cible"')

    site = build_site(*load_pages())

    assert site.out["source.md"] == {"cible.md": "la cible"}
    assert site.predecessors("cible.md") == ["source.md"]
    assert site.in_degree("cible.md") == 1
    assert site.out_degree("source.md") == 1
    assert [item["target"] for item in site.unresolved] == ["/nulle-part/"]


def test_site_ignores_external_links(write_page):
    write_page("source.md", 'title: "Source"',
               "Voir [ext](https://example.com/) et [mail](mailto:a@b.c) et [ancre](#section).")

    site = build_site(*load_pages())

    assert site.edge_count == 0
    assert site.unresolved == []


def test_site_ignores_self_links(write_page):
    # Un lien d'une page vers elle-même ne crée aucun maillage : le compter
    # ferait sortir la page de la liste des orphelines à tort.
    write_page("seule.md", 'title: "Seule"\nslug: "seule"', "Voir [moi-même](/seule/).")

    site = build_site(*load_pages())

    assert site.edge_count == 0
    assert site.orphans() == ["seule.md"]


def test_orphans_and_underlinked_exclude_index_pages(write_page):
    write_page("_index.md", 'title: "Accueil"')
    write_page("blog/_index.md", 'title: "Blog"')
    write_page("a.md", 'title: "A"\nslug: "a"')
    write_page("b.md", 'title: "B"\nslug: "b"', "Un lien vers [A](/a/).")

    site = build_site(*load_pages())

    assert site.orphans() == ["b.md"]
    assert site.underlinked() == ["a.md"]


def test_link_targets_are_sorted_by_in_degree(write_page):
    write_page("orpheline.md", 'title: "Orpheline"\nslug: "orpheline"')
    write_page("une-fois.md", 'title: "Une fois"\nslug: "une-fois"')
    write_page("source.md", 'title: "Source"\nslug: "source"', "Lien vers [une fois](/une-fois/).")

    site = build_site(*load_pages())

    assert site.link_targets()[0] == "orpheline.md"
    assert "une-fois.md" in site.link_targets()
    assert "source.md" in site.link_targets()
