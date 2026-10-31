# Łączność w wersji 0.7.8

Panel otwiera przycisk dymka w górnym pasku. Czat ogólny jest wspólny dla
zalogowanych graczy; rozmowa prywatna dotyczy dwóch konkretnych kont.
Treści graczy są wyświetlane dosłownie, bez interpretacji HTML/BBCode
oraz bez tłumaczenia nazw graczy i ich wiadomości.

## Historia i odczyt

Wiadomości są zapisane w tabelach SQLite, poza publicznym stanem świata.
Do zwykłego stanu gry trafiają wyłącznie liczniki. Serwer sprawdza uczestnika
każdego żądania. Identyfikator nadawcy pochodzi z uwierzytelnionej sesji.
Przeczytanie jest zapisywane dopiero po wyświetleniu końca rozmowy; przeglądanie
starszych wpisów nie oznacza automatycznie nowych jako przeczytanych.
Historia jest dostępna do 30 dni, a ogólny kanał przechowuje do 1000 wiadomości.
Wpisy poza okresem retencji są usuwane przy kolejnej wysyłce. Usunięcie konta
usuwa jego wysłane wiadomości oraz rozmowy prywatne z aktywnej bazy.
Kopie bazy podlegają dotychczasowej rotacji backupów.

Limit: 500 znaków i maksymalnie 8 znaków nowego wiersza. Odstęp pomiędzy
wiadomościami wynosi co najmniej 3 sekundy; dodatkowo obowiązują limity
20 wiadomości na minutę i 120 na godzinę liczone z zapisanej historii.
Ponowienie tej samej wysyłki z tym samym identyfikatorem nie dodaje kopii.

## Moderacja

Blokada ukrywa wiadomości zablokowanego autora w kanale ogólnym i blokuje
nowe wiadomości prywatne w obu kierunkach. Historia prywatnej rozmowy pozostaje
czytelna; odblokowanie jest dostępne w tej samej rozmowie.
Zgłoszenie wymaga potwierdzenia w aplikacji. Moderator przegląda zgłoszenia
przez narzędzie w terminalu serwera; nie są automatycznie wysyłane e-mailem.

Przykłady poleceń, wykonywanych w folderze wdrożonego serwera:

```bash
python moderate_chat.py --db /data/private_test.sqlite3 reports
python moderate_chat.py --db /data/private_test.sqlite3 remove 123
python moderate_chat.py --db /data/private_test.sqlite3 dismiss 123
python moderate_chat.py --db /data/private_test.sqlite3 mute ID_KONTA --hours 24
python moderate_chat.py --db /data/private_test.sqlite3 unmute ID_KONTA
```

Numery wiadomości i identyfikatory kont operator pobiera z listy zgłoszeń.
Zgłoszenie prywatnej wiadomości pozwala operatorowi zobaczyć jej treść.
Klient nie otrzymuje dostępu do zgłoszeń innych osób ani do narzędzi moderatora.

## API

Każda ścieżka wymaga sesji Bearer i podlega dotychczasowej kontroli wersji.

| Metoda i ścieżka | Działanie |
| --- | --- |
| GET `/api/chat?peer_id=...&before=0&after=0` | Historia, po 50 wiadomości; pusty rozmówca oznacza kanał ogólny |
| GET `/api/chat/inbox` | Do 100 najnowszych rozmów bieżącego konta |
| POST `/api/chat/send` | `peer_id`, `text`, `request_id` |
| POST `/api/chat/read` | `peer_id`, `last_id`; ograniczone do dostępnej historii |
| POST `/api/chat/block` | `peer_id`, `blocked` jako bool |
| POST `/api/chat/report` | `message_id` dostępnej wiadomości innego gracza |

## Sprawdzenie lokalne

```bash
python -m unittest tests.test_communications_078 tests.test_account_management tests.test_release_storage -v
python tests/run_communications_ui.py --godot /sciezka/do/godot
python tools/check_localization.py
```

Test Godota uruchamia własny serwer i dwie fikcyjne osoby w pamięci.
Nie łączy się z wdrożonym serwerem ani rzeczywistymi kontami. Scena testowa
ładuje autoload I18n przed skryptami klienta. Wyniki są w VERIFICATION_078.json.
