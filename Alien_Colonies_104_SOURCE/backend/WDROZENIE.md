# Wdrożenie 0.11.3

Bieżąca instrukcja: **AKTUALIZACJA_0.11.3_START_TUTAJ.txt**.

To pełny serwer i WWW. Wgraj całą zawartość paczki do głównego katalogu
repozytorium serwera, bez dodatkowego folderu nadrzędnego. Zachowaj `web/`,
`swarm_reset.py`, `Dockerfile` i dotychczasowy Volume z `private_test.sqlite3`.
Punkt startowy to `python start_web.py`; używaj jednej repliki.

**Pierwszy start wykonuje jednorazowy reset wyłącznie Roju.** Wcześniej tworzy
zweryfikowaną kopię. Konta i postęp graczy pozostają. Nie usuwaj bazy i nie
wywołuj historycznego resetu balansu graczy.

Nie potrzeba nowego AAB. Sprawdź wersję 0.11.3 w `/health` i ustawieniach WWW.
Jeżeli istnieje ustawiona zmienna `PGR_MAX_PLAYERS=15`, usuń ten stary limit
przez `PGR_MAX_PLAYERS=0`, aby rejestracje mogły wypełniać pierwszą galaktykę.
Zachowaj obecne domeny i inne ustawienia hostingu, w tym tempo produkcji.

Dawna instrukcja pierwszego dodania strony znajduje się w
`docs/history/WDROZENIE_PIERWOTNE_WWW.md` i nie opisuje aktualizacji 0.11.3.
