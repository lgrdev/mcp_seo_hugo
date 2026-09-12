from seolib.content import build_chunks, load_pages
from seolib.graph import build_site
from seolib.rank import Bm25Index, candidates_for

DOCKER = ("Le déploiement en conteneurs Docker simplifie la mise en production des "
          "applications métier chez nos clients, même sans équipe dédiée.")
EXCEL = ("Excel reste utile au départ, mais devient un risque dès qu'il sert de base "
         "principale à un processus critique : passer à un outil métier devient nécessaire.")


def _index_and_site():
    pages, skipped = load_pages()
    site = build_site(pages, skipped)
    return Bm25Index(build_chunks(pages)), site


def test_candidates_rank_the_topical_paragraph_first(write_page):
    write_page("cible.md", 'title: "Passer d\'Excel à un outil métier"\nslug: "excel-outil"')
    write_page("docker.md", 'title: "Docker"\nslug: "docker"', DOCKER)
    write_page("excel.md", 'title: "Tableurs"\nslug: "tableurs"', EXCEL)

    index, site = _index_and_site()
    results = candidates_for(index, site, "cible.md", top=5)

    assert results[0]["source_path"] == "excel.md"
    assert results[0]["target_slug"] == "/excel-outil/"
    assert results[0]["score"] > 0


def test_candidates_exclude_the_target_itself(write_page):
    write_page("cible.md", 'title: "Tableurs Excel"\nslug: "tableurs-excel"', EXCEL)
    write_page("autre.md", 'title: "Autre"\nslug: "autre"', EXCEL.replace("Excel", "Le tableur"))

    index, site = _index_and_site()
    results = candidates_for(index, site, "cible.md", top=5)

    assert all(item["source_path"] != "cible.md" for item in results)


def test_candidates_exclude_pages_that_already_link_to_the_target(write_page):
    write_page("cible.md", 'title: "Tableurs Excel"\nslug: "tableurs-excel"')
    write_page("deja.md", 'title: "Déjà"\nslug: "deja"',
               f"{EXCEL}\n\nVoir [les tableurs](/tableurs-excel/).")

    index, site = _index_and_site()
    results = candidates_for(index, site, "cible.md", top=5)

    assert results == []


def test_candidates_for_an_unknown_target(write_page):
    write_page("page.md", 'title: "Page"', EXCEL)

    index, site = _index_and_site()

    assert candidates_for(index, site, "inexistante.md") == []


def test_index_handles_an_empty_corpus(content_dir):
    index, site = _index_and_site()

    assert index.chunks == []
    assert index.avg_length == 0.0
    assert candidates_for(index, site, "n-importe-quoi.md") == []


def test_zero_score_candidates_are_dropped(write_page):
    write_page("cible.md", 'title: "Kubernetes"\nslug: "kubernetes"')
    write_page("sans-rapport.md", 'title: "Sans rapport"\nslug: "sans-rapport"', EXCEL)

    index, site = _index_and_site()

    assert candidates_for(index, site, "cible.md", top=5) == []
