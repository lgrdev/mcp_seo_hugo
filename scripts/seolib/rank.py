"""Classement lexical BM25 des paragraphes candidats à l'accueil d'un lien.

Remplace la recherche vectorielle ChromaDB. Le signal de départ est le même que celui
utilisé jusqu'ici : le titre de la page cible — l'ancien index n'était interrogé qu'avec
`query_texts=[titre]`. Le choix final revient au juge sémantique, pas à ce score.
"""

import math
import re
from collections import Counter

from .anchors import STOPWORDS, TOKEN_RE
from .content import Chunk

K1 = 1.5
B = 0.75

# L'apostrophe fait partie de TOKEN_RE, utile pour une ancre (« d'Excel » reste d'un bloc)
# mais nuisible pour le classement : « d'Excel » ne matcherait jamais « Excel ». Les
# élisions sont donc coupées ici, et les fragments d'une ou deux lettres écartés.
_ELISION_RE = re.compile(r"['’]")


def terms(text: str) -> list[str]:
    """Termes normalisés pour le classement : minuscules, élisions coupées, stopwords écartés."""
    words = []
    for token in TOKEN_RE.findall(text):
        for part in _ELISION_RE.split(token):
            part = part.strip("-").lower()
            if len(part) > 2 and part not in STOPWORDS and any(c.isalnum() for c in part):
                words.append(part)
    return words


class Bm25Index:
    """Index BM25 en mémoire. Reconstruit à chaque appel : 47 ms pour 2817 paragraphes."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.term_freqs = [Counter(terms(chunk.text)) for chunk in chunks]
        self.lengths = [sum(freqs.values()) for freqs in self.term_freqs]
        self.avg_length = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0

        doc_freqs: Counter = Counter()
        for freqs in self.term_freqs:
            doc_freqs.update(freqs.keys())
        total = len(chunks)
        self.idf = {
            term: math.log(1 + (total - count + 0.5) / (count + 0.5))
            for term, count in doc_freqs.items()
        }

    def score(self, query: str, position: int) -> float:
        freqs = self.term_freqs[position]
        length = self.lengths[position]
        total = 0.0
        for term in terms(query):
            frequency = freqs.get(term, 0)
            if not frequency:
                continue
            denominator = frequency + K1 * (1 - B + B * length / (self.avg_length or 1))
            total += self.idf.get(term, 0.0) * frequency * (K1 + 1) / denominator
        return total

    def best_hosts(self, query: str, exclude_paths: set[str], top: int) -> list[tuple[float, Chunk]]:
        """Meilleurs paragraphes d'accueil, hors pages exclues et hors score nul."""
        scored = []
        for position, chunk in enumerate(self.chunks):
            if chunk.source_path in exclude_paths:
                continue
            value = self.score(query, position)
            if value <= 0:
                continue
            scored.append((value, position, chunk))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [(value, chunk) for value, _, chunk in scored[:top]]


def candidates_for(index: Bm25Index, site, target_path: str, top: int = 20) -> list[dict]:
    """Paragraphes candidats pour mailler vers `target_path`.

    Exclut la cible elle-même et les pages qui la lient déjà : leur proposer un lien
    de plus n'apporte rien au maillage.
    """
    if target_path not in site.pages:
        return []

    target = site.pages[target_path]
    exclude = {target_path} | set(site.inbound.get(target_path, {}))
    query = f"{target['title']} {target.get('description', '')}".strip()

    return [
        {
            "score": round(score, 2),
            "source_path": chunk.source_path,
            "source_title": chunk.title,
            "paragraph_text": chunk.text,
            "target_path": target_path,
            "target_title": target["title"],
            "target_slug": f"/{target['slug']}/",
        }
        for score, chunk in index.best_hosts(query, exclude, top)
    ]
