# Start publiczny — reset i zasady nowych kont, 12 października 2026

Właściciel gry zlecił jednorazowe usunięcie wszystkich dotychczasowych kont graczy i reset Roju. Aktualizacja działa po stronie wspólnego serwera Androida i WWW; nie wymaga nowego AAB ani zmian konfiguracji OAuth.

## Jednorazowy reset

Przy pierwszym uruchomieniu istniejącej bazy bez znacznika `public-launch-20261012` serwer zapisuje kompletną, trwałą kopię SQLite w `reset-backups/` obok bazy świata. Sprawdza schemat, zawartość wszystkich tabel, integralność i klucze obce. Błąd kopii zatrzymuje reset.

Następnie jedna transakcja usuwa konta, sesje, powiązania Google, kody odzyskiwania, czat, postępy, floty, sojusze i lokalne uprawnienia do kolejek. Powstaje nowy świat. Błąd zapisu wycofuje usunięcie. Znacznik resetu jest częścią zapisu świata, więc restarty i kolejne wdrożenia nie usuwają nowych kont. Nowe bazy otrzymują ten sam znacznik od początku. Nie zmieniać tego identyfikatora przy zwykłych aktualizacjach.

Reset nie wywołuje anulowania ani zwrotu płatności Google Play. Ewentualne wcześniejsze subskrypcje pozostają po stronie Google Play, a nowe konto nie odzyskuje automatycznie zakupu przypisanego do starego ID gracza. Kopia bezpieczeństwa zawiera wcześniejszy stan; nie trafia do repozytorium ani publicznych plików.

## Konta i Rój

- Nowe konta zaczynają bez statków. Początkowe surowce, budynki i ochrona pozostają jak wcześniej.
- Rejestracja wybiera pierwszą galaktykę z dostępną planetą, zaczynając od Aurory. Dopiero pełna wcześniejsza galaktyka przenosi rejestrację do następnej.
- Aurora zaczyna z jednym małym ulem i 3 rzadkimi Kryształami Roju. Zwykłe surowce, statki i obrona ula zaczynają od zera.
- W pozostałych galaktykach Rój pojawia się po powstaniu pierwszej kolonii gracza: przez rejestrację albo zakończoną kolonizację. Mapa, zwiad i flota w drodze go nie uruchamiają.
- Pojawienie się ula nie zajmuje planet graczy ani planet zarezerwowanych przez lecących kolonizatorów. Przy braku bezpiecznej planety czeka na wolne miejsce. Aktywacja i wykonany zasiew są trwałe; restart nie daje nowego ula ani kolejnych darmowych kryształów.
- Płatne przyczółki Roju nadal zaczynają z 0 Kryształów Roju. Zachowano tempo: najwyżej jeden start kolonizatora na galaktykę na 24 godziny, 48 godzin pomiędzy startami z tego samego gniazda i co najmniej 24 godziny dojrzewania nowego gniazda.

## Wiadomości

Przy utworzeniu konta serwer zapisuje niezmienną granicę identyfikatorów wiadomości. Czat ogólny i sojuszowy nie ujawniają wpisów wysłanych przed powstaniem tego konta. Dotyczy to również paginacji, liczników oraz zgłaszania starych wiadomości przez zgadywanie ID. Wpis wysłany po utworzeniu konta pozostaje widoczny nawet przy takim samym znaczniku czasu. Granica nie przesuwa się przy czytaniu i przetrwa restart.

## Kontrola wdrożenia

Po poprawnym uruchomieniu `/health` zwraca `world_epoch: "public-launch-20261012"`. Endpoint nie ujawnia kont, tokenów ani ścieżek kopii. Szczegóły i liczby usuniętych rekordów są zapisane w prywatnym podsumowaniu resetu oraz logu serwera. Nie ma publicznego endpointu do powtórzenia resetu.
