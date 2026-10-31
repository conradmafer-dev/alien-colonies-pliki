"""Stable report categories, also assigned to legacy reports before translation."""
KINDS = frozenset(("scout", "battle", "warning", "transport", "return", "colonization",
                   "research", "construction", "defense", "shipyard", "skill", "protection",
                   "empire", "recycling", "expedition", "ranking"))
PROJECT_KINDS = {"build": "construction", "research": "research", "ship": "shipyard", "defense": "defense"}
TITLES = {
    "Premia rankingowa": "ranking",
    "Raport ekspedycji": "expedition", "Opóźniona ekspedycja": "expedition",
    "Raport zwiadu": "scout", "Raport zwiadu układu": "scout",
    "Raport bitwy": "battle", "Raport wspólnej bitwy": "battle",
    "Twoja kolonia została zaatakowana": "battle",
    "Nadciąga wroga flota": "warning", "Nadciąga atak sojuszu": "warning",
    "Nadciąga próba przejęcia kolonii": "warning", "Najazd Roju po surowce": "warning",
    "Utracono kolonię": "warning", "Nadciąga wsparcie sojuszu": "defense",
    "Dostarczono transport": "transport", "Transport zawrócił": "transport",
    "Flota wróciła": "return", "Atak odwołany": "return",
    "Nowa kolonia": "colonization", "Przejęto kolonię": "colonization",
    "Kolonizacja przerwana": "colonization", "Ukończono projekt": "construction",
    "Ukończono megastrukturę": "construction", "Archiwum Synaps": "research",
    "Nowa umiejętność": "skill", "Ochrona początkującego": "protection",
    "Ochrona zakończona": "protection", "Recykling": "recycling",
    "Narodziny cywilizacji": "empire", "Witaj w Alien Colonies": "empire",
    "Nowy początek": "empire",
}

def kind(report):
    if report.get("kind") in KINDS:
        return report["kind"]
    if report.get("battle_replay") or report.get("battle_replay_available"):
        return "battle"
    if any(report.get(key) for key in ("planet_snapshot", "system_snapshot", "intel_snapshot",
                                     "planet_scout", "system_scout", "scout")):
        return "scout"
    return TITLES.get(str(report.get("title", "")), "empire")

