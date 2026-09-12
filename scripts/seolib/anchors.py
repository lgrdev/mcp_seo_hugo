"""Choix de l'ancre et insertion du lien dans un paragraphe."""

import re

# `\w` est ASCII en Python comme en RE2 : la classe explicite garde les accents français.
TOKEN_RE = re.compile(r"[\wÀ-ÿ'’-]+")

STOPWORDS = {
    "le", "la", "les", "de", "des", "du", "et", "pour", "avec", "sans",
    "vos", "votre", "une", "un", "en", "sur", "dans", "au", "aux", "par",
}

_LINKED_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")


def tokenize(text: str) -> list[str]:
    """Mots significatifs d'un texte : accents conservés, ponctuation et stopwords écartés."""
    tokens = (word.strip("-'’") for word in TOKEN_RE.findall(text))
    return [word for word in tokens
            if any(char.isalnum() for char in word) and word.lower() not in STOPWORDS]


def anchor_keywords(target_title: str) -> list[str]:
    """Phrases candidates pour l'ancre, de la plus longue à la plus courte."""
    words = tokenize(target_title)
    candidates = []
    for size in range(min(4, len(words)), 0, -1):
        for start in range(len(words) - size + 1):
            phrase = " ".join(words[start:start + size])
            if len(phrase) >= 5:
                candidates.append(phrase)
    return candidates


def insert_link(paragraph: str, target_title: str, target_slug: str,
                anchor_phrase: str | None = None) -> tuple[str, str]:
    """Insère un lien vers target_slug. Retourne (paragraphe, mode) avec mode = 'ancre' ou 'phrase'.

    `anchor_phrase` permet d'imposer l'ancre choisie par le juge sémantique ; elle est
    essayée avant les mots-clés du titre, et ignorée si elle n'apparaît pas en clair
    dans le paragraphe hors d'un lien existant.
    """
    already_linked = [match.span() for match in _LINKED_RE.finditer(paragraph)]

    phrases = anchor_keywords(target_title)
    if anchor_phrase:
        phrases = [anchor_phrase] + phrases

    for phrase in phrases:
        for match in re.finditer(re.escape(phrase), paragraph, flags=re.IGNORECASE):
            if any(start <= match.start() < end for start, end in already_linked):
                continue
            anchor = f"[{match.group(0)}]({target_slug})"
            return paragraph[:match.start()] + anchor + paragraph[match.end():], "ancre"

    return f"{paragraph} Pour aller plus loin : [{target_title}]({target_slug}).", "phrase"
