from seolib.anchors import anchor_keywords, insert_link
from seolib.content import is_list_block


def test_keywords_ignore_stopwords_and_punctuation():
    # Régression : le tiret d'un titre « EloNeva - Audit » devenait un mot, ce qui
    # produisait l'ancre « [- Audit] » et cassait la puce Markdown.
    keywords = anchor_keywords("EloNeva - Audit, cadrage et pilotage")
    assert all(not kw.startswith("-") for kw in keywords)
    assert not any(kw.lower() in {"et", "de", "la"} for kw in keywords)
    assert "EloNeva" in " ".join(keywords)


def test_keywords_longest_phrases_first():
    keywords = anchor_keywords("Migration WinDev vers le web")
    assert len(keywords[0].split()) >= len(keywords[-1].split())


def test_insert_link_wraps_match_preserving_case():
    paragraph = "Une migration WinDev demande du cadrage."
    new, mode = insert_link(paragraph, "Migration WinDev", "/migration-windev/")
    assert mode == "ancre"
    assert "[migration WinDev](/migration-windev/)" in new
    assert new.count("[") == 1


def test_insert_link_skips_text_inside_existing_link():
    paragraph = "Voir [Traefik comme proxy](/traefik/) pour Traefik en production."
    new, mode = insert_link(paragraph, "Traefik", "/autre-traefik/")
    assert mode == "ancre"
    assert "[Traefik comme proxy](/traefik/)" in new
    assert "[Traefik](/autre-traefik/)" in new


def test_insert_link_falls_back_to_appended_sentence():
    paragraph = "Ce paragraphe ne parle pas du tout du sujet visé."
    new, mode = insert_link(paragraph, "PostgreSQL TDE", "/postgresql-tde/")
    assert mode == "phrase"
    assert new.startswith(paragraph)
    assert new.endswith("Pour aller plus loin : [PostgreSQL TDE](/postgresql-tde/).")


def test_insert_link_honours_anchor_phrase_chosen_by_the_judge():
    paragraph = "Le cadrage d'un projet métier évite bien des dérapages."
    new, mode = insert_link(paragraph, "Piloter un projet", "/piloter/",
                            anchor_phrase="cadrage d'un projet métier")
    assert mode == "ancre"
    assert "[cadrage d'un projet métier](/piloter/)" in new


def test_insert_link_ignores_an_anchor_phrase_absent_from_the_paragraph():
    # Le juge peut proposer une ancre reformulée : on retombe sur les mots du titre,
    # jamais sur une insertion approximative.
    paragraph = "Une migration WinDev demande du cadrage."
    new, mode = insert_link(paragraph, "Migration WinDev", "/migration-windev/",
                            anchor_phrase="phrase inventée")
    assert mode == "ancre"
    assert "[migration WinDev](/migration-windev/)" in new
    assert "phrase inventée" not in new


def test_is_list_block():
    assert is_list_block("- premier point\n- deuxieme point\n- troisieme point")
    assert is_list_block("1. premier\n2. deuxieme")
    assert not is_list_block("Un paragraphe de prose normale, sans puce.")
    assert not is_list_block("Une phrase d'introduction.\n- une seule puce")
