# Alien Colonies 99 / 0.12.32

Każda z sześciu galaktyk otrzymuje jeden nowy zewnętrzny pierścień z 50 układami. Łącznie jest 155 układów w galaktyce i 930 we wszechświecie. Migracja zachowuje wcześniejsze identyfikatory, planety, kolonie, floty i kolejki; nie zmienia dawnych odległości ani kosztów tras. Przed migracją wymagana jest trwała, zweryfikowana kopia SQLite.

Sześć nowych teł ma 2048 × 1366 pikseli. Powstały z nowych renderów bazowych i dwóch nakładających się renderów szczegółów dla każdej galaktyki. Pliki PNG są wzorcami; WebP w grze i w wersji WWW zachowują wszystkie ich piksele. Wyrównanie środka i wspólna geometria orbit utrzymują układy na obrazie. Mniejszy dysk czarnej dziury w Void nie przecina najbliższej orbity. Zachowano sterowanie i poprawki przewijania z 98.

Serwer i WWW wdrożono przez PR16 do bieżącego świata. Dowody migracji i kontroli zasobów są w deployment99.json oraz live_web99.json. Nie podniesiono wymaganej wersji aplikacji w polityce aktualizacji przed opublikowaniem AAB99.

Sprawdzenia: 28 testów backendu, 20 testów Node, 13 257 sprawdzeń mapy Androida, 15 sprawdzeń startu. Zgodne wszystkie 638 wpisów indeksu zasobów Androida; bundletool 1.18.3 zaakceptował AAB. Testy Androida uruchomiono na komputerze z rzeczywistymi skompilowanymi zasobami AAB, bez fizycznego telefonu i instalacji z Google Play.

Paczki delta są dla autora. Po ich zastosowaniu trzeba podpisać wynik dotychczasowym kluczem i opublikować w Google Play. Rozmiar paczki autora nie określa transferu aktualizacji dla graczy. Paczka 98 → 99 zawiera wyłącznie dane potrzebne do odtworzenia pełnego AAB99, w tym nowe grafiki.

Do odtworzenia grafiki służą tools/assemble_galaxy_art99.py, galaxy_art_measure99.py, check_galaxy_art99.py i prepare_galaxy_web99.py. Renderowane części znajdują się w osobnym archiwum źródeł grafiki na Dysku Google. Polecenie montażu: python tools/assemble_galaxy_art99.py --tiles ŚCIEŻKA_DO_KATALOGU_tiles. Następnie python tools/check_galaxy_art99.py --calibrate i python tools/prepare_galaxy_web99.py. Wymagane ImageMagick, Pillow, NumPy i SciPy.
