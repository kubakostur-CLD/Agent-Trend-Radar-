"""Proste narzędzia tekstowe dla PL/EN: składanie znaków, tokeny, przybliżony stemming."""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = set(
    """
    a aby ale albo ani az bez bo by byc byl byla bylo czy dla do gdy go i ich ii iii im ja jak jako je jego jej jest
    jeszcze juz ktora ktore ktory ktorzy kiedy lub ma maja mnie moze na nad nie niz no o od on ona one oni po pod
    przed przez przy sa sie so ta tak tam te tego tej ten to tu ty tylko w we wiec wszystko z za ze zl co czym
    nowy nowa nowe roku dzis wczoraj teraz bedzie byly mozna trzeba
    the of and or to in on at for from by with as is are was were be been it its this that these those an
    but not no new after over into about how why what who when will would can could has have had his her their
    they you your our we he she says said than more most just out up off vs via
    """.split()
)

TOKEN_RE = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    """Małe litery, bez polskich znaków i akcentów."""
    text = text.lower().replace("ł", "l")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def stem(token: str) -> str:
    # Odmiana polska („Trumpa”, „wyborach”) i angielska („elections”) w praktyce różni się
    # końcówką, więc porównujemy pierwsze 5 znaków dłuższych słów.
    return token[:5] if len(token) > 5 else token


def keywords(text: str) -> list[str]:
    return [stem(t) for t in TOKEN_RE.findall(fold(text)) if len(t) >= 3 and t not in STOPWORDS and not t.isdigit()]
