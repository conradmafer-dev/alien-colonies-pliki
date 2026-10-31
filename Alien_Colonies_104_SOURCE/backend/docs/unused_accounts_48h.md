# Jednorazowe porządkowanie kont bez rozwoju

Status przygotowania: ZATWIERDZONE przez właściciela 25.10.2026 do jednorazowego
wykonania i zapisu źródeł na jego Dysku Google. Wynik produkcyjny znajduje się
w osobnym raporcie wykonania; ten dokument opisuje procedurę.
Baza: `conradmafer-dev/pogranicze-serwer`, główny katalog, commit
`983a189ddd426d54bd43cb27401e3217a52eeac8` (serwer 0.12.26).
Zmiana nie wymaga aktualizacji Androida i nie uruchamia automatycznego kasowania.

## Wybór kont

Oba warunki muszą być spełnione jednocześnie:

- ostatnia potwierdzona aktywność co najmniej 48 rzeczywistych godzin temu;
- brak zapisanego rozwoju od początku: zero ukończonych budów, wszystkie budynki
  i badania na poziomie zero, brak statków, obrony, lotów, płatnych umiejętności,
  rzadkich kryształów, megastruktur, dodatkowych kolonii i znaczników rozwoju.

Chronione są również konta z trwającą lub zaplanowaną produkcją, zakupem/subskrypcją,
sojuszem, wysłanymi wiadomościami, historią poleceń rozwoju oraz aktualną obecnością
online. Brak wymaganych danych wyklucza konto z usuwania. Sam wybór rasy, jej
bezpłatny korzeń umiejętności i narastające zwykłe surowce nie są ulepszeniami.
Wynik 0 pkt w rankingu nie jest kryterium usuwania.

## Obsługa administratora

Nowa trasa `GET /api/admin/unused-accounts` jest chroniona istniejącym nagłówkiem
`X-AC-Announcement-Key`. Zwraca liczbę, listę nazw/ID/planet, daty aktywności i
losowy `preview_id`, ważny 15 minut. Podgląd nie zapisuje bazy, nie zmienia
aktywności i nie zawiera haseł ani danych uwierzytelniających graczy.

Usunięcie wymaga oddzielnego `POST` na tę samą trasę z JSON:

```json
{
  "preview_id": "wartość z aktualnego podglądu",
  "count": 0,
  "confirmation": "DELETE UNUSED ACCOUNTS"
}
```

`count` musi być dokładnie równy liczbie z podglądu. Nie można podstawić listy
innych ID. Przed zapisem serwer ponownie sprawdza wszystkie wybrane konta.
Powrót gracza, zmiana jego danych lub rozpoczęcie rozwoju unieważnia całą operację;
nie kasuje się części starej listy. Nowe konta spełniające warunki po podglądzie nie
są do niej dopisywane. Restart serwera unieważnia wszystkie podglądy.

Przed usunięciem powstaje zweryfikowana samodzielna kopia SQLite w istniejącym
katalogu `reset-backups/before-unused-48h-*.sqlite3`, poza rotacją godzinowych kopii.
Brak możliwości zapisania lub zweryfikowania kopii przerywa operację.

Usuwanie korzysta ze wspólnej ścieżki usunięcia konta: kasuje konto, sesje,
powiązania logowania, kod odzyskiwania i zależne rekordy. Planeta staje się wolna;
jej położenie, środowisko i cecha są zachowane. Pozostałe konta, ich postęp, Rój,
świat i floty innych graczy są zachowane. Cała lista i zapis świata zatwierdzają
się w jednej transakcji; błąd powoduje wycofanie również zmian w pamięci.

## Jednorazowe wykonanie zatwierdzonej operacji

`authorized_unused_cleanup.py` jest osobnym zadaniem operatora, wybieranym
tymczasowo jako polecenie startowe jednej wersji usługi. Zwykłe `start_web.py`
nie uruchamia czyszczenia. Zadanie korzysta z tego samego zatwierdzonego podglądu
i ścieżki usunięcia, z istniejącej konfiguracji pliku bazy oraz blokady jednego
procesu zapisującego. Weryfikuje istniejącą bazę i identyfikator świata przed
otwarciem zapisu, nie uruchamia resetu i nie odczytuje klucza administratora.

Granica czasu kwalifikacji jest zamrożona w kodzie dla tej konkretnej zgody;
powrót gracza po jej przygotowaniu chroni konto. Operacja musi rozpocząć się
w ciągu godziny. Zapisany wynik uniemożliwia ponowne kasowanie po restarcie,
także gdy lista była pusta. Po operacji przywracane jest normalne polecenie
`python start_web.py`. Logi podają wyłącznie liczby i nazwę kopii, bez listy
graczy i ich danych logowania.

## Weryfikacja

```sh
python -m unittest discover -s tests -p '*unused*.py' -v
```

Testy używają bieżącego głównego `app.py`, lokalnych kont i tymczasowej bazy.
Sprawdzają próg 48 godzin, historię rozwoju, kolejki, brak zmian przy podglądzie,
uprawnienia HTTP, zmianę konta po podglądzie, kopię bazy, usunięcie i restart,
wycofanie całej listy przy błędzie oraz zwykłe usuwanie własnego konta.
Dodatkowe testy zadania operatora sprawdzają zapis pustego wyniku, brak
ponownego usuwania po restarcie, granicę czasu, identyfikator świata i błąd kopii.
Wszystkie 20 testów przeszło.

Do narzędzi podłączonych w tej sesji Railway udostępnia nazwy zmiennych, ale
ukrywa ich wartości. Wykonanie zatwierdzonego zadania operatora nie wymaga ich
odczytu. Klucza administratora nie należy umieszczać w plikach źródłowych,
pakietach, adresach URL ani wiadomości na czacie.
