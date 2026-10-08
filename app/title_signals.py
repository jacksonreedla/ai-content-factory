"""Heuristic "out-of-pocket" title scoring.

``wild_title_score`` rates how provocative / shocking / clickable a title is on
a 0..1 scale, using keyword and pattern signals - no AI, no network, fully
unit-testable. The Story Analyst uses it (when the toggle is on) to boost the
ranking of stories with wild titles like "I hate my disabled sister" or
"Playing the Spanking Game".
"""
from __future__ import annotations

import re

# Strong taboo / shock words - the biggest driver of a "wild" title.
_TABOO = {
    "hate", "kill", "killed", "kills", "killing", "murder", "died", "dead",
    "death", "dying", "suicide", "cheat", "cheated", "cheating", "affair",
    "affairs", "sex", "sexual", "spanking", "naked", "nude", "pregnant",
    "pregnancy", "abortion", "arrested", "jail", "prison", "revenge", "caught",
    "molested", "abuse", "abused", "abusive", "incest", "virginity", "orgy",
    "drugs", "overdose", "stalker", "stalking", "creepy", "pee", "peed",
    "poop", "pooped", "toilet", "underwear", "slept", "hooked", "threesome",
    "trauma", "traumatized", "blackmail", "kidnapped", "assault",
}

# Vulnerable / edgy topics that make a title feel taboo to say out loud.
_VULNERABLE = {
    "disabled", "disability", "autistic", "autism", "cancer", "terminal",
    "homeless", "adopted", "orphan", "disfigured", "amputee", "blind", "deaf",
    "wheelchair", "mute", "special", "handicapped",
}

# Family / relationship words - drama hits harder when it's close to home.
_FAMILY = {
    "sister", "brother", "mom", "mother", "dad", "father", "wife", "husband",
    "girlfriend", "boyfriend", "fiance", "fiancee", "ex", "stepmom", "stepdad",
    "stepsister", "stepbrother", "aunt", "uncle", "cousin", "grandma",
    "grandpa", "grandmother", "grandfather", "son", "daughter", "niece",
    "nephew", "in-law", "mil", "fil", "sil",
}

# Strong emotion / conflict verbs.
_EMOTION = {
    "ruined", "destroyed", "humiliated", "betrayed", "exposed", "confronted",
    "screamed", "dumped", "disowned", "abandoned", "furious", "obsessed",
    "refuse", "refused", "banned", "kicked", "fired", "quit",
}

# Provocative phrasings.
_PATTERNS = [
    re.compile(r"\bthe\s+\w+\s+game\b"),        # "the spanking game"
    re.compile(r"\bmy\s+secret\b"),
    re.compile(r"\bno\s+one\s+knows\b"),
    re.compile(r"\bi\s+never\s+told\b"),
    re.compile(r"\bwhat\s+i\s+did\b"),
    re.compile(r"\bfound\s+out\b"),
    re.compile(r"\bwalked\s+in\s+on\b"),
]

# First-person confession openers.
_OPENER = re.compile(r"^\s*(i|my|aita|wibta|am\s+i|why\s+i|how\s+i|the\s+time)\b",
                     re.IGNORECASE)


def wild_title_score(title: str) -> float:
    """Return a 0..1 "out-of-pocket" score for a title. Pure function."""
    if not title:
        return 0.0
    text = title.lower()
    words = set(re.findall(r"[a-z']+", text))

    score = 0.0
    if words & _TABOO:
        score += 0.45
    if words & _VULNERABLE:
        score += 0.30
    if words & _FAMILY:
        score += 0.15
    if words & _EMOTION:
        score += 0.20
    if any(p.search(text) for p in _PATTERNS):
        score += 0.15
    if _OPENER.match(text):
        score += 0.12
    # A second taboo/emotion word compounds the shock a little.
    strong_hits = len((words & _TABOO) | (words & _EMOTION))
    if strong_hits >= 2:
        score += 0.10

    return min(1.0, round(score, 3))
