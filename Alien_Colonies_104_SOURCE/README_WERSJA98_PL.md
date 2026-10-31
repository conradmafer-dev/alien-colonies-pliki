# Alien Colonies 98 / 0.12.31

Poprawka przewijania na Androidzie. Odtworzono błąd: przesunięcie o 15 jednostek
widoku potrafiło dodać ponad 400 jednostek ruchu po puszczeniu palca przy 60 FPS.
Godot 4.5.1 szacował prędkość z czasu klatki, zamiast z czasu kolejnych zdarzeń.

Przeciąganie nadal obsługuje natywny ScrollContainer. Nowy kontroler wylicza tylko
pęd po puszczeniu palca, z próbek ruchu i rzeczywistego czasu. Hamuje płynnie,
zachowuje podobny zasięg przy różnych FPS i nie rozpędza widoku po mikroruchu.
Zatrzymanie palca przed puszczeniem oraz nowe dotknięcie zatrzymują pęd.
Pozostaje blokada jednej osi w zagnieżdżonych kartach i anulowanie kliknięć
przycisków podczas przewijania.

Odpowiedzi HTTP stanu gry i poleceń są odczytywane oraz dekodowane poza głównym
wątkiem. Przebudowa widoku czeka na zakończenie gestu i wyhamowanie. Ranking,
wiadomości i sojusz także odkładają aktualizacje podczas gestu. Kosztowne
przeliczanie wszystkich kart nie konkuruje z przewijaniem; zegar i liczniki
misji nadal działają. Spóźnione odpowiedzi nie zastępują nowego widoku ani konta.

Raporty oraz polecenia odtworzenia testów są w `docs/version98/`.
Testy wykorzystują prawdziwy indeks Androida i skompilowane skrypty Godot 4.5.1.
Przeszły testy pędu, komunikacji lokalnej, rankingu, floty, okna oceny i startu.
Nie wykonano testu na fizycznym telefonie ani instalacji przez Google Play.
Pomiarów na komputerze nie należy traktować jako gwarancji FPS na Androidzie.

Paczka AAB zachowuje dotychczasową konfigurację Androida i natywne biblioteki.
Indeks `assets.sparsepck` jest przeliczony dla wszystkich zmienionych zasobów.
Wersja zawiera wcześniejsze poprawki 97, w tym nazwy ras pod punktami oraz
pulsujące „Checking for updates” bez początkowego paska 0%.

Do podpisania użyj dotychczasowego klucza. Klucza ani jego hasła nie ma w kopii.
Mała paczka aktualizacji służy autorowi do odtworzenia pełnego AAB z wersji 97.
Google Play ustala rozmiar aktualizacji pobieranej przez graczy.

Kopia serwera zawiera również wdrożone wcześniej zmiany do commitu
`84fa55af89e6612d9df3a88b34fa6040bed0810f`. Wersja 98 nie wymaga wdrożenia
serwera. Operacja usunięcia nieużywanych kont była jednorazowa; nie jest
uruchamiana przy starcie tego projektu.
