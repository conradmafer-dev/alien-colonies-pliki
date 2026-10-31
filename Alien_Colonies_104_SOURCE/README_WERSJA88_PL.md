# Alien Colonies 0.12.21 — kod 88

Wersja 88 powstała na podstawie przesłanej paczki `Alien_Colonies_87_SOURCE.7z`.

## Wybór celu floty

Mapa galaktyki wykorzystuje wolną wysokość okna zamiast dawnego limitu 380 jednostek. Przy logicznym ekranie 720 × 1280 ma teraz 838 jednostek wysokości; przy 720 × 1600 — 1158. Przyciski wyboru galaktyki, powiększania i wyboru układu pozostają widoczne. Początkowe przybliżenie wynosi 2,4 — identycznie jak po kliknięciu „Galaktyka” w dolnym panelu — i nadal można je regulować. Oba wejścia korzystają z jednej wspólnej wartości, dzięki czemu nie rozchodzą się ich ustawienia.

Rewizja MAPA poprawia wcześniejszy AAB 88, w którym wybór celu startował z przybliżeniem 3,2. Poprzedni zrzut zawierał tylko dwa sztuczne układy po przeciwnych stronach elipsy, więc nie nadawał się do oceny liczby widocznych sąsiadów. Porównanie tej rewizji używa pełnej galaktyki z 60 układami na trzech pierścieniach. Poprawiono też dopasowanie zwykłej mapy po ułożeniu nagłówka i legendy: wcześniej mogła zachować zbyt małą wysokość wyliczoną podczas otwierania ekranu, co dodatkowo zmieniało skalę galaktyki. Rewizja zachowuje versionCode 88 i versionName 0.12.21; należy użyć poprawionego AAB i odpowiadającego mu podpisywacza.

„Wstecz” z listy planet wraca do galaktyki. Kolejne „Wstecz” wraca do formularza floty. Powrót zachowuje pozycję i przybliżenie mapy oraz przygotowaną flotę i ładunek. Wybranie planety nadal zamyka wybór celu i uzupełnia formularz. Przycisk systemowy Androida i Escape zachowują tę samą kolejność. Otwarta lista wyboru jest zamykana przed ekranem pod nią.

## Jednorazowe zaproszenie do subskrypcji

Zaproszenie staje się dostępne po sześciu łącznie ukończonych budowach lub ulepszeniach budynków w całym imperium. Kolejne ulepszenia tego samego budynku liczą się osobno. Rozpoczęte lub anulowane projekty, badania i budowa statków nie zwiększają tego licznika.

Okno zawiera dotychczasową grafikę Premium, opis „Planuj budowę, flotę i badania.” oraz przycisk „Wypróbuj 7 dni za darmo”. Cena po próbie jest pobierana z Google Play. Okno można zamknąć przez „Może później”, X albo Wstecz.

Serwer zapisuje jednorazowe wyświetlenie na koncie. Zaproszenie czeka na bezpieczny ekran planety: nie przerywa nawigacji floty, logowania, innych okien ani prośby o ocenę. Aktywni subskrybenci nie otrzymują zaproszenia. Samo zaproszenie nie przyznaje korzyści płatnego planu.

Zaproszenie pojawia się wyłącznie, jeśli Google Play udostępnia graczowi właściwą siedmiodniową próbę planu tygodniowego. Kliknięcie ponownie pobiera ofertę przed otwarciem płatności. Utrata uprawnienia do próby nie uruchamia płatnego planu zastępczego. Zamknięcie okna albo zmiana sesji anuluje oczekujące otwarcie płatności.

## Wymagana aktualizacja serwera

Mapa i nawigacja działają w nowym kliencie. Automatyczne zaproszenie wymaga także aktualizacji serwera o `subscription_invite.py`, zmiany `app.py`, `Dockerfile` i tłumaczenia. Bez nowego pola `subscription_prompt` klient nie wyświetla tego zaproszenia.

Mała paczka poprawki serwera jest przygotowana dla istniejącego, płaskiego układu repozytorium `conradmafer-dev/pogranicze-serwer`. Bazą jest commit `1273b655bcd4b778165a948389b9ca3ba6b41935`. Pakiet nie oznacza wykonania wdrożenia produkcyjnego ani publikacji w Google Play.

Aktualizacja nie wymaga zmiany trwałego dysku `/data`, bazy świata, zmiennych Railway ani identyfikatorów resetu. `world_epoch` pozostaje dotychczasowy. Backend otrzymuje wersję 0.12.21, a niezmieniony frontend WWW zachowuje `web_build` 0.12.20.

## AAB i podpisywanie

Złóż części AAB rewizji MAPA dołączonym łącznikiem. Plik `Alien_Colonies_ANDROID_0.12.21_CODE_88_MAPA_UNSIGNED.aab` podpisz na Windows podpisywaczem z tej samej poprawionej paczki, używając swojego dotychczasowego klucza wysyłania. Podpisywacz wymaga Java JDK 17 lub nowszej; klucz prywatny nie jest dołączony. Do Google Play należy wysłać wynikowy podpisany plik AAB, bez dopisku `UNSIGNED`.

## Źródła i ponowna kompilacja

Pełne źródła zawierają klienta, grafiki, natywne dodatki, backend, tłumaczenia, testy i raporty. Nie zawierają wygenerowanego cache `.godot`, lokalnego drzewa kompilacji Androida ani produkcyjnych danych i prywatnych kluczy.

Otwórz `project.godot` w Godot 4.5.1 i poczekaj na import. Do Androida użyj szablonów Godot 4.5.1, Java JDK 17, Android SDK 36 i Build Tools 36.0.0. Po instalacji szablonu kompilacji uruchom `python tools/configure_android_build.py`, a następnie eksportuj preset `Google Play AAB`.

Raporty korekty mapy i poprawionego AAB znajdują się w `docs/version88_mapfix`. Historyczne raporty pierwszej paczki 88 pozostają w `docs/version88` i opisują poprzedni plik AAB. Testy obejmują rzeczywiste drzewo interfejsu Godot, logikę serwera, jednorazowy zapis zaproszenia i zakup próbny z atrapą Google Play. Nie obejmują rzeczywistej płatności na telefonie ani podpisania prywatnym kluczem użytkownika. Końcową próbę zakupu należy przeprowadzić w wewnętrznym teście Google Play.
