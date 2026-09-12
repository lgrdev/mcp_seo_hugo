def test_keywords_ignore_stopwords_and_punctuation(seo):
    # Régression : le tiret d'un titre « EloNeva - Audit » devenait un mot, ce qui
    # produisait l'ancre « [- Audit] » et cassait la puce Markdown.
    keywords = seo._anchor_keywords("EloNeva - Audit, cadrage et pilotage")
    assert all(not kw.startswith("-") for kw in keywords)
    assert not any(kw.lower() in {"et", "de", "la"} for kw in keywords)
    assert "EloNeva" in " ".join(keywords)


def test_keywords_longest_phrases_first(seo):
    keywords = seo._anchor_keywords("Migration WinDev vers le web")
    assert len(keywords[0].split()) >= len(keywords[-1].split())


def test_insert_link_wraps_match_preserving_case(seo):
    paragraph = "Une migration WinDev demande du cadrage."
    new, mode = seo._insert_link(paragraph, "Migration WinDev", "/migration-windev/")
    assert mode == "ancre"
    assert "[migration WinDev](/migration-windev/)" in new
    assert new.count("[") == 1


def test_insert_link_skips_text_inside_existing_link(seo):
    paragraph = "Voir [Traefik comme proxy](/traefik/) pour Traefik en production."
    new, mode = seo._insert_link(paragraph, "Traefik", "/autre-traefik/")
    assert mode == "ancre"
    assert "[Traefik comme proxy](/traefik/)" in new
    assert "[Traefik](/autre-traefik/)" in new


def test_insert_link_falls_back_to_appended_sentence(seo):
    paragraph = "Ce paragraphe ne parle pas du tout du sujet visé."
    new, mode = seo._insert_link(paragraph, "PostgreSQL TDE", "/postgresql-tde/")
    assert mode == "phrase"
    assert new.startswith(paragraph)
    assert new.endswith("Pour aller plus loin : [PostgreSQL TDE](/postgresql-tde/).")


def test_is_list_block(seo):
    assert seo._is_list_block("- premier point\n- deuxieme point\n- troisieme point")
    assert seo._is_list_block("1. premier\n2. deuxieme")
    assert not seo._is_list_block("Un paragraphe de prose normale, sans puce.")
    assert not seo._is_list_block("Une phrase d'introduction.\n- une seule puce")
