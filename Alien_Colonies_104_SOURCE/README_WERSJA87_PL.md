# Alien Colonies 0.12.20 — kod 87

Wersja 87 upraszcza przygotowanie i wysyłanie flot na Androidzie i w WWW. Zachowuje gospodarkę, zasady walk, koszty paliwa i grafiki wersji 85/86. Nie resetuje świata.

## Przygotowanie wyprawy

Po zmianie statków, planety docelowej lub rodzaju misji podgląd czasu lotu i zużycia paliwa jest automatycznie pobierany z serwera. Nie trzeba osobno naciskać przycisku wyliczania. Wysłanie floty wymaga gotowego, aktualnego podglądu i jednego naciśnięcia „Wyślij”.

Planeta startowa, wybrany cel i podsumowanie wyprawy są łatwiej widoczne, dzięki czemu formularz wymaga mniej przewijania. Wybór celu na mapie prowadzi do przygotowania floty. Nawigacja zachowuje szkic wyprawy i pozwala wrócić do wyboru celu.

Wyliczenia nadal wykonuje serwer. Interfejs nie zmienia kosztów, odległości, limitów kolonizacji, statystyk jednostek ani zasad misji. Wybranie celu i podgląd nie wysyłają floty.

## Ikona Androida

Eksport 87 używa profesjonalnej grafiki aplikacji także w warstwie pierwszoplanowej ikony adaptacyjnej Androida. Klasyczna i adaptacyjna ikona zainstalowanej aplikacji są dzięki temu spójne. Ta poprawka dotyczy aplikacji na urządzeniu; nie zmienia grafiki oferty w Google Play.

## AAB i podpisywanie

1. W folderze `AAB_I_PODPISYWACZ` uruchom `PODPISZ87.bat` na Windows z Java JDK 17 lub nowszą.
2. Użyj dotychczasowego klucza wysyłania do Google Play. Prywatnego klucza nie ma w paczce.
3. Gotowy plik to `Alien_Colonies_ANDROID_0.12.20_CODE_87.aab`, bez dopisku `UNSIGNED`.
4. Najpierw sprawdź w teście wewnętrznym Google Play zmianę statków i celu, automatyczny podgląd, powrót do formularza oraz wysłanie jednej wyprawy jednym naciśnięciem.

Podpisywacz nie publikuje aplikacji ani nie wdraża serwera. Poprawki Androida wymagają klienta 87; zmiany WWW wymagają aktualizacji backendu.

## Serwer i istniejący świat

Pełny kod serwera i WWW znajduje się w `backend`. Zachowaj istniejącą usługę, trwały dysk `/data`, obecną bazę `private_test.sqlite3`, jedną replikę oraz dotychczasowe ustawienia logowania, płatności i tempa `PGR_SPEED`. Nie zmieniaj identyfikatorów resetu i nie uruchamiaj dawnych narzędzi resetujących.

Przed aktualizacją zachowaj spójną kopię bazy i poprzedni kod. Po uruchomieniu `/health` powinno wskazywać `0.12.20` i dotychczasowy `world_epoch`. Wersja 87 nie dodaje migracji gospodarki względem 86. Opis zachowanego balansu znajduje się w `docs/BALANS_85.html`.

Pełny lokalny serwer WWW uruchomisz na osobnym świecie testowym przez `python start_web.py --local-data ./local_data --port 8080` w folderze `backend`.

Instrukcja i zawartość ZIP-a nie są potwierdzeniem wdrożenia na hosting ani publikacji w Google Play. Są to osobne operacje. Paczka nie zawiera produkcyjnej bazy świata.

## Edycja i weryfikacja

Otwórz `project.godot` w Godot 4.5.1 i poczekaj na import. Kod klienta znajduje się w `client/scripts`, grafiki w `client/assets`, a dodatki natywne w `addons`.

Do eksportu Androida użyj szablonów Godot 4.5.1, Java JDK 17, Android SDK 36 i Build Tools 36.0.0. Po instalacji szablonu kompilacji uruchom `python tools/configure_android_build.py`, następnie eksportuj preset Google Play AAB.

Raporty bieżącego wydania są w `docs/version87`; wcześniejsze raporty balansu zachowano w `docs/version85`. Kontrola lokalna i zgodność zawartości AAB nie zastępują próby pełnego przepływu na telefonie.
