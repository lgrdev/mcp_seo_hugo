from seolib.encoding import repair


def test_repair_dry_run_detects_without_writing(content_dir):
    broken = content_dir / "casse.md"
    original = ("---\ntitle: Casse\n---\n\nUn co".encode("utf-8") + b"\xc3\x22"
                + " et bien s".encode("utf-8") + b"\xc3\x22" + b"r.\n")
    broken.write_bytes(original)

    result = repair()

    assert "casse.md : 2 occurrence(s)" in result
    assert broken.read_bytes() == original


def test_repair_fixes_only_broken_bytes(content_dir):
    broken = content_dir / "casse.md"
    # « avancées » est déjà du bon UTF-8 : un ré-encodage global le transformerait
    # en mojibake. Seule la séquence cassée doit changer.
    broken.write_bytes("Fonctions avancées, un co".encode("utf-8") + b"\xc3\x22" + b"t.\n")

    result = repair(apply=True)

    assert "1 fichier(s) réparé(s)" in result
    assert broken.read_text(encoding="utf-8") == "Fonctions avancées, un coût.\n"


def test_repair_reports_unknown_patterns_without_guessing(content_dir):
    broken = content_dir / "inconnu.md"
    original = "Texte avec un octet ".encode("utf-8") + b"\xff" + b" invalide.\n"
    broken.write_bytes(original)

    result = repair(apply=True)

    assert "à traiter manuellement" in result
    assert broken.read_bytes() == original


def test_repair_on_a_clean_corpus(content_dir):
    (content_dir / "ok.md").write_text("Déjà valide.\n", encoding="utf-8")

    assert repair() == "Tous les fichiers de content/ sont déjà en UTF-8 valide."
