# Alien Colonies 0.12.1 — galaktyki, nieaktywność i zwiad układu

Aktualizacja rozszerza każdą z sześciu galaktyk z 30 do 60 układów.
Istniejące 30 układów tworzy pierścień zewnętrzny; nowe pierścienie mają
20 i 10 układów. Pięć dwukierunkowych przejść łączy każdą parę sąsiednich
pierścieni. Zwykłe loty korzystają z najkrótszych tras po tych połączeniach.
Android i przeglądarka pokazują ten sam przebieg trasy. Koszty są nadal
obliczane i sprawdzane przez serwer. Tunele i podróże między galaktykami
zachowują swoje odrębne zasady.

Migracja jest addytywna i powtarzalna: zachowuje identyfikatory istniejących
układów i planet, konta, zasoby, kolejki oraz opłacone trasy i terminy flot.
Przed migracją istniejącej bazy wymagana jest poprawna kopia zapasowa.
Nie zmieniono historycznych znaczników resetu świata ani minimalnej wersji
Androida wymaganej do logowania.

Po 604800 sekundach bez aktywności produkcja metalu, kryształów i paliwa
spada do zera we wszystkich koloniach gracza. Dokładny fragment czasu do
granicy zostaje rozliczony, również przy jednorazowym odczycie po długiej
nieobecności. Powrót wznawia produkcję bez wyrównania za przestój.
Istniejące zapasy pozostają dostępne do zrabowania, a opłacone projekty i
floty kończą swoje zadania. Rój Khar nie podlega tej regule.

Aktywność odnawia poprawne logowanie, nowe udane polecenie gracza albo
sygnał uruchomienia, powrotu lub rzeczywistego wejścia użytkownika w kliencie.
Zwykły polling, billing, ponowienia polecenia, odczyt przez innego gracza,
atak oraz automatyczne zdarzenia świata nie odnawiają aktywności.
Klient nie podaje własnego czasu aktywności. Starsze wydania zachowują
obsługę aktywności przez logowanie i udane polecenia.

Poprzednie wydanie nie zapisywało wiarygodnej daty ostatniej aktywności.
Dlatego stare konta otrzymują jeden zapisany okres przejściowy siedmiu dni
od pierwszego uruchomienia tej aktualizacji. Restart nie wydłuża go.

Przycisk „Zbadaj cały układ” jest dostępny także po odkryciu układu.
Jedna płatna misja aktualizuje informacje o zamieszkaniu wszystkich planet
i zapisuje datowany raport z właścicielami. Raport pozostaje historycznym
zapisem; kolejne kolonizacje nie zmieniają go wstecz. Zwiad konkretnej
planety nadal służy do poznania jej szczegółowych zasobów i obrony.

Nowa ikona zastępuje poprzednią w wersji web i wydaniu Android 68.
Wszystkie nowe komunikaty są dostępne w pięciu obsługiwanych językach.

## Walidacja

Nowe testy uruchamiają faktyczny moduł produkcyjny `app.py`, a nie starszą
kopię `server/main.py` przechowywaną w repozytorium:

```sh
python -m unittest tests.test_galaxy_rings_0121 tests.test_inactivity tests.test_system_scout_0121
node --test web/play/tests/rings-activity.test.mjs
```

Kontrole obejmują migrację i restart istniejącego świata, zachowanie kont
i opłaconych flot, wszystkie 3600 tras wewnątrz jednej galaktyki, ścisłą
granicę siedmiu dni, brak wyrównania produkcji, kolejki premium, rzeczywiste
żądania HTTP oraz ponowny zwiad po zmianie właściciela planety.
Uruchomienie serwera z manifestem wydania zostało sprawdzone lokalnie.
Testy modeli web wykonano; test wizualny Chromium został zablokowany przez
ograniczenia środowiska i nie jest deklarowany jako zaliczony.
Test instalacji Androida na fizycznym telefonie pozostaje do wykonania.

Przed publikacją wdrożenia należy zachować aktualną kopię bazy z Volume.
Aktualizacja Androida wymaga podpisania dotychczasowym kluczem uploadu;
nowy AAB nie został automatycznie opublikowany w Google Play.

## Lokalny plik zmian do przeglądu

Plik `Alien_Colonies_SERVER_0.12.1_GOTOWA_ZMIANA.patch` jest kompletnym
patchem Git zawierającym również nowe ikony. Jego bazą jest commit
`240875b37b6744a16c8f8b0cb096d3ed7b9fffb7` w repozytorium
`conradmafer-dev/pogranicze-serwer`.

Zastosuj go w osobnym, czystym klonie repozytorium, na nowej lokalnej gałęzi:

```sh
git switch -c review/alien-colonies-0121 240875b37b6744a16c8f8b0cb096d3ed7b9fffb7
git am /pelna/sciezka/Alien_Colonies_SERVER_0.12.1_GOTOWA_ZMIANA.patch
```

Patch obejmuje wyłącznie źródła, testy, dokumentację i zasoby strony.
Nie zawiera bazy graczy, plików Volume ani danych uwierzytelniających.
Powyższe polecenia przygotowują lokalny commit do przeglądu; migracja
następuje dopiero przy uruchomieniu nowego serwera na istniejącej bazie.
Przed wdrożeniem zachowaj jej aktualną kopię zapasową. Gałąź `main`
uruchamia automatyczne wdrożenie Railway, dlatego publikacja na GitHubie
i wdrożenie wymagają osobnego zatwierdzenia.
