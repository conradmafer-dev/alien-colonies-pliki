# Serwer i kopie — Alien Colonies 0.3.0

> Dokument historyczny. Od 0.3.1 obowiązuje normalne tempo ×1, poprawione bonusy Symbiontów i testowy eksport APK. Bieżące instrukcje: README_PL.md i ZMIANY_0_3_1_PL.md.

## Aktualizacja

Zachowaj istniejącą usługę Railway, domenę, Volume `/data` i jedną replikę. Podmień 11 plików z paczki serwera razem, ponieważ `app.py` importuje nowe moduły kont, pierwszych kroków i kopii. Zapis pozostaje w `/data/private_test.sqlite3`.

Przed wdrożeniem zachowaj kopię aktualnej bazy poza serwerem. Nie kopiuj samego pliku aktywnej bazy WAL. Użyj spójnego backupu wykonanego przez SQLite lub zatrzymaj proces przed kopiowaniem kompletnego zapisu. Kopia może zawierać dane kont; przechowuj ją prywatnie.

## Reakcja na awarię zapisu

Operacja gry jest zatwierdzana razem ze zmianami w SQLite. Jeśli zapis się nie uda, serwer przywraca wcześniejszy stan pamięci i czas rozliczenia. Nieudany zakup nie powinien zostawić kosztu bez zlecenia ani zająć identyfikatora ponowienia.

Po awarii trwałego zapisu `/health` zwraca HTTP 503. Kolejna udana operacja zapisu przywraca prawidłowy status. Przyczynę trzeba usunąć: sprawdzić zamontowanie i wolne miejsce Volume oraz uprawnienia procesu. Nie rozwiązuj problemu przez kasowanie świata. Nie podnoś minimum wersji APK z powodu awarii dysku.

## Rotowane kopie

`backups.py` tworzy spójny plik przez SQLite backup API po pierwszym udanym zapisie na starcie i potem co godzinę działania. W folderze obok bazy `backups/` utrzymuje najwyżej 24 kopie `galaxy-*.sqlite3`. Kopia przechodzi `quick_check`, jest synchronizowana i dopiero potem otrzymuje końcową nazwę. Nieukończony plik `.part` nie jest kopią do odtworzenia.

Przy błędzie kopii następna próba jest odroczona co najmniej o minutę. Nieudana kopia nie kasuje aktywnego świata. Utrzymywane są 24 kopie, a nie obietnica usunięcia danych zawsze po dokładnie 24 godzinach — po zatrzymaniu serwera pliki pozostają.

Kopie są na tym samym Volume. Nie chronią przed utratą całego dysku lub konta hostingu. Po udanym uruchomieniu bety regularnie zachowuj spójną kopię poza Railway. Automat w tej paczce nie wysyła baz do innego dostawcy.

## Próba odtworzenia

1. Wybierz zakończony plik `galaxy-*.sqlite3` i zachowaj jego oryginał.
2. Skopiuj go do nowego, prywatnego katalogu na komputerze jako `private_test.sqlite3`.
3. Uruchom odtworzoną kopię lokalnie: `python run.py --local-data SCIEZKA_DO_NOWEGO_KATALOGU --port 8080`.
4. Sprawdź `/health`, logowanie konta testowego, poziomy budynków, flotę i kolejki. Kopia może zawierać wcześniejsze terminy — serwer rozliczy upływ czasu.
5. Jeśli kiedykolwiek potrzebne będzie odtworzenie produkcji, najpierw zatrzymaj jedyny proces, zachowaj aktualną bazę z plikami WAL/SHM w osobnym miejscu i dopiero podmień komplet na sprawdzoną kopię. Nie zostawiaj starych plików WAL/SHM obok innej bazy i nie uruchamiaj dwóch procesów na tym samym zapisie.

Odtworzenie starszej kopii cofa również hasła, sesje, usunięcia kont i pozostały postęp do chwili kopii. Przed ponownym udostępnieniem takiego świata trzeba uwzględnić zmiany kont dokonane później.

## Zakres pierwszego sektora

Domyślny limit na hostingu to 15 kont; `PGR_MAX_PLAYERS` może go jawnie zmienić. Lokalne narzędzia zachowują brak dodatkowego limitu. Tempo ×10 pozostaje ustawieniem bety. Nie ma automatycznego tworzenia kolejnych sektorów, powiadomień push ani panelu operatora dostępnego przez Internet.
