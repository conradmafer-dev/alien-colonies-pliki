# Weryfikacja wydania 0.10.1

Bieżąca zmiana dotyczy krótkich efektów na kafelkach budynków. Wyniki kontroli
wartości, renderowania, geometrii kafelków i tłumaczeń są w
`../VERIFICATION_0101.json` oraz `../docs/verification_0101/`.
Próby porównywano z niezmienioną wersją 0.10.0. Starsze testy liczące
12 budynków i używające nieodkrytych celów zachowują historyczne błędy;
nie zmieniano ich oczekiwań ani mechaniki gry w tej aktualizacji.

```sh
python tools/check_localization.py
python tools/sync_client_version.py --check
```

Poniższe wyniki dotyczą wcześniejszych wydań; nie oznaczają ponownego
wykonania wszystkich testów w tej aktualizacji.

# Historyczne kontrole wydania 0.10.0

```sh
python -m unittest tests.test_alliances_0100 tests.test_alliance_operations_0100 tests.test_alliance_http_0100 tests.test_alliance_integration_0100 tests.test_planet_traits_095 tests.test_planetary_090 tests.test_observation_090 tests.test_facility_speed_076 tests.test_parallel_projects_092 tests.test_battle_replay_094 -v
python tools/check_localization.py
python tools/sync_client_version.py --check
python -m tests.run_alliance_ui_0100 /path/to/godot
python -m tests.run_alliance_replay_ui_0100 /path/to/godot
python -m tests.run_battle_ui_094 /path/to/godot
python -m tests.run_traits_ui_095 /path/to/godot
```

Suite serwera: 141 testów. Obejmuje członkostwo, uprawnienia, prywatność,
równoczesne dołączanie, wspólne bitwy, wsparcie, rozejmy, transporty,
ponawianie poleceń, cofanie transakcji przy błędach zapisu i zgodność
wcześniejszych mechanik. Używa tymczasowych baz oraz serwerów localhost.

Runnery Godota korzystają z testowych kont i rzeczywistych odpowiedzi serwera.
Dodanie `--screenshots /path/to/png` w środowisku X11 zapisuje zrzuty.
Pełne bieżące wyniki: `../VERIFICATION_0100.json` i `../docs/verification_0100/`.
Testy interfejsu nie zastępują próby na fizycznym telefonie. Gotowych APK/AAB
nie wyeksportowano w środowisku przygotowania paczki.

# Historyczne kontrole 0.9.1

```sh
python -m unittest tests.test_account_management tests.test_play_gate_074 tests.test_release_storage tests.test_server.HTTPScenarios -v
python tools/check_localization.py
python tools/sync_client_version.py --check
godot --headless --path . --editor --import
python -m tests.run_auth_ui_091 /path/to/godot
```

Wyniki: **48 testów Pythona i 185 kontroli UI bez błędów**.
Runner UI uruchamia tymczasowy serwer HTTP na localhost i prawdziwy formularz
Godota. Sprawdza wybór trybu bez żądania, prawidłowe zatwierdzenie, Enter,
brak duplikatów, niewłaściwe hasło, zajętą nazwę, walidację, logowanie
i utworzenie konta. Błędy sieci i niepełne odpowiedzi są symulowane w istniejącym
handlerze. Zrzuty uzyskasz dodając `--screenshots /path/to/png` i uruchamiając
na ekranie X11. Wszystkie dane są testowe, zapis prawdziwej sesji jest wyłączony.

Zaktualizowano trzy historyczne oczekiwania testów: numer wydania jest
porównywany z bieżącymi stałymi, wywołanie wbudowanego `is_inside_tree` Godota
jest rozpoznawane, a usuwanie konta zachowuje fizyczne warunki planety zgodnie
z mechaniką 0.9.0. Pozostałe kontrole pozostają aktywne.

Logi i rendery: `../docs/verification_091/`. Starsze wyniki poniżej opisują
tamte wydania, a nie dodatkowe wykonania w tej poprawce.

---

# Historia kontroli 0.9.0

Wyniki: `../VERIFICATION_090.json`. Logi i zrzuty: `../docs/verification_090/`.

```sh
python -m unittest tests.test_planetary_090 tests.test_observation_090 tests.test_technology_080 tests.test_megastructures_080 tests.test_facility_speed_076 tests.test_server tests.test_communications_078 tests.test_release_storage tests.test_racial_research tests.test_brief_descriptions_077 -v
python tools/check_localization.py
python tools/sync_client_version.py --check
python -m tests.make_planetary_fixture_090 /tmp/planetary-090.json
godot --headless --path . --editor --import
godot --headless --path . --audio-driver Dummy tests/test_planetary_ui_090.tscn -- /tmp/planetary-090.json
```

Aby uzyskać zrzuty, usuń `--headless` i dodaj drugi argument użytkownika:
ścieżkę katalogu PNG. Test ma wyłączony transport do prawdziwego serwera.

Przeszło 128 z 129 scenariuszy serwera; jeden historyczny kontrakt SHA256
wersji 0.7.7 jest pominięty. W zestawie jest 21 nowych testów: generowanie
świata, orbity, sloty, rezerwacje, wydobycie, migracja i ochrona celów lotów,
usunięcie konta, zasięgi, rozdzielenie galaktyk, aktualizacje właścicieli
i budynków, historyczny zwiad, restart oraz prawdziwe odpowiedzi HTTP.

Starsze testy lotów dostają zapisany zwiad celu, ponieważ 0.9.0 wymaga
poznania planety przed kolonizacją lub atakiem. Regresje bonusów wydobycia
uwzględniają teraz mnożnik typu planety. Różne konta porównują tę samą topologię
układów, ale mają osobną wiedzę. Testy atomowości i zapisów nadal korzystają
z rzeczywistych działań serwera. Żadne scenariusze nie dotykają produkcji.

Interfejs zaliczył 55 kontroli w rendererze oraz osobno te same kontrole
w trybie headless. Sprawdzono trzy proporcje ekranu i pięć języków. Nie wykonano
eksportu Android ani fizycznego testu telefonu. Poniżej jest historia starszych
wydań; jej wyniki i ograniczenia odnoszą się wyłącznie do wskazanych wersji.

---

# Historia kontroli 0.8.0

Wyniki wykonanych scenariuszy: `../VERIFICATION_080.json`.
Logi i rendery: `../docs/verification_080/`. Poniżej zachowano historię starszych wydań;
zawarte w niej ograniczenia opisują tamte dostawy.

```sh
python -m unittest tests.test_technology_080 tests.test_megastructures_080 tests.test_facility_speed_076 tests.test_galaxies tests.test_server tests.test_racial_research tests.test_races tests.test_content_expansion tests.test_brief_descriptions_077 tests.test_communications_078 tests.test_release_storage tests.test_gdscript_override_contracts -v
python tools/check_localization.py
python tools/sync_client_version.py --check
python -m tests.make_technology_fixture_080 /tmp/technology-080.json
godot --headless --path . --editor --import
godot --headless --path . --audio-driver Dummy tests/test_technology_ui_080.tscn -- /tmp/technology-080.json
```

Aby uzyskać zrzuty, usuń `--headless` i dodaj drugi argument użytkownika:
ścieżkę do katalogu PNG. Test odłącza transport sieciowy klienta i używa stanów
wygenerowanych przez prawdziwy serwer. Nie łączy się z produkcją.
Testuje 720×1280, 720×1600 i 1080×2520, pięć języków, wymagania badań,
obsługę megastruktur, tryb lotu przez tunel i wygaśnięcie wyceny.

W zestawie 163 testów Pythona pominięto jeden historyczny test pełnego SHA256
serwera z wydania 0.7.7: dotyczył wyłącznie braku zmian mechaniki w tamtej
poprawce interfejsu. W 0.8.0 mechanika zmienia się celowo. Testy wersji i listy
badań dostosowano do bieżących stałych i nowego katalogu. Wszystkie pozostałe
162 scenariusze przeszły. Rzeczywisty renderer Godota wykonał 247 kontroli.

---

# Bieżące kontrole 0.7.4

```
python -m unittest discover -s tests -p "test_*.py"
python tools/check_localization.py
python tools/sync_client_version.py --check
```

`test_play_gate_074.py` uruchamia lokalny HTTP i wykonuje też statyczne
kontrole połączenia interfejsu. Testy statyczne nie zastępują Godota.
Zaktualizowano historyczne oczekiwania numeru wersji (33 / 0.7.4).
Testy historycznej niezmienności narzędzi podpisu pomijają WYŁĄCZNIE
nowy blok VERSION_SYNC_074; resztę plików nadal porównują oryginalnym SHA256.
Przepisano testy wymogu zewnętrznego APK na testy stałego linku Google Play;
pozostawiono regresje walidacji nagłówków, uwierzytelniania i braku mutacji.

Test interfejsu do uruchomienia w rzeczywistym Godocie, z izolowanym katalogiem
ustawień użytkownika:
```
python tests/make_localization_fixture.py /tmp/alien-074-fixture.json
XDG_DATA_HOME=/tmp/alien-074-user godot --headless --path . --editor --quit
XDG_DATA_HOME=/tmp/alien-074-user godot --headless --path . --script tests/test_compact_play_ui_074.gd -- /tmp/alien-074-fixture.json
```
Ten test używa lokalnych danych i przechwytuje transport, nie łączy się
z produkcyjnym serwerem ani nie używa prawdziwych sesji. W środowisku
przygotowania paczki nie był wykonany: brak binarnego Godota.

## Historia

# Aktualne testy 0.7.2

`python -m unittest discover -s tests -p "test_*.py"`
`python tools/check_localization.py`
`python tests/smoke_072_http.py`

Testy używają lokalnych, usuwanych baz; nie kontaktują się z produkcją.
`test_ui_balance_072.py`: reset, kopia, zachowanie kont, brak ponownego resetu,
zwroty, idempotencja, kolejki i statyczne kontrakty interfejsu.
Testy oczekiwanego numeru wersji zaktualizowano z 30 / 0.7.1 do 31 / 0.7.2;
regresja obrazów 0.7.1 nadal sprawdza ich oryginalne sumy i wymiary.
Test niezmienności całego serwera 0.7.0 ograniczono do narzędzi podpisu,
ponieważ w 0.7.2 serwer i tłumaczenia celowo się zmieniły.

Nie wykonano testów GDScript w Godocie, renderingu ani eksportu AAB.
Poniżej historia starszych scenariuszy i instrukcji.

---

# Art integration 0.7.1

Static mapping tests: test_defense_art_071.py.
Godot runtime test (not run here): godot --headless --path . --script tests/test_defense_art_071.gd
No sessions or production requests are used by the new test.

# Testy aktualnej paczki 0.7.0

Z katalogu projektu:

```text
python -m unittest discover -s tests -p "test_*.py"
python tools/check_localization.py
python tests/smoke_070_http.py
```

`test_recon_defense_070.py` używa rzeczywistego World z losowym startem we
wszystkich galaktykach. Starsze testy lokalnych lotów korzystają z
`LocalTestWorld`, który nadpisuje wyłącznie wybór planety startowej,
aby nie mieszać losowego kosztu międzygalaktycznego do izolowanych testów.
Produkcja, walka, zasoby, AI, kolejki oraz zapisy pozostają rzeczywiste.

Testy GDScript wymagają uruchomienia w Godocie. Nie wykonano ich w środowisku
przygotowującym tę paczkę. Testy offline używają OfflineClient bez wczytywania
sesji i bez wysyłania żądań do produkcyjnego serwera. Test podglądu twierdzy
został dostosowany do ostatniego zwiadu zamiast bieżących liczników.

Dalsza część jest dokumentacją historycznych scenariuszy i generatorów.

---

# Testy Alien Colonies 0.3.5

Aktualna poprawka: `../docs/VALIDATION_0_3_5.md`. Pełna weryfikacja poprzedniej paczki: `../docs/VALIDATION_0_3_2.md`.

Kontrola bezpośredniego dotyku pól ilości (rzeczywisty renderer, emulacja ekranu dotykowego):

```bash
python3 tests/make_unique_building_fixture.py /tmp/unique-buildings.json
godot --audio-driver Dummy --emulate-touchscreen --path . --script tests/test_quantity_touch.gd -- /tmp/unique-buildings.json /tmp/quantity-screenshots
godot --headless --path . --script tests/test_mobile_quantity.gd
```

W drugim argumencie testu dotykowego można wskazać katalog na zrzut. Test obejmuje przeciągnięcie bezpośrednio po cyfrach, dotknięcie i puszczenie, aktywne pole, ilości i zatwierdzanie. Nie korzysta z produkcyjnego serwera.

Nowe kontrole 0.3.2 obejmują Gaj tylko w obronie właściwej planety, palety ras, przełącznik Misje/Budowa oraz eliptyczną mapę. Reprodukcja interfejsu (Godot 4.5.1):

```bash
python3 tests/make_unique_building_fixture.py /tmp/unique-buildings.json
godot --headless --path . --script tests/test_ui_032.gd -- /tmp/unique-buildings.json
godot --headless --path . --script tests/test_race_theme.gd
godot --headless --path . --script tests/test_galaxy_map.gd
godot --headless --path . --script tests/test_mobile_ui.gd -- tests/fixtures/legacy_ui_0111.json
godot --headless --path . --script tests/test_ui_fixes_018.gd -- tests/fixtures/legacy_ui_0111.json
```

Starsze testy ogólnego układu wymagają dołączonego `legacy_ui_0111.json`. Nowo wygenerowany stan z nieprzypisaną rasą prawidłowo otwiera wybór rasy zamiast głównego ekranu, którego te testy oczekują. Aby wykonać rzeczywiste rendery nowego interfejsu, usuń `--headless` i po ścieżce danych w `test_ui_032.gd` podaj katalog na zrzuty.

Nowe kontrole: `test_release_storage.py`, `test_incoming_attacks.py`, `test_account_management.py`, `test_onboarding.py`, `test_public_beta.py` oraz testy eksportu release. Obejmują faktyczne błędy SQLite, restart, przywrócenie kopii, prywatność nadchodzących ataków, cykl konta przez HTTP, trzy pełne początki gry i 15 równoległych graczy ponawiających zlecenia.

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Testy nie łączą się z publicznym serwerem i nie zastępują instalacji APK na telefonie. Poniżej historia poprzednich zestawów.

# Testy Alien Colonies 0.2.2

Aktualne wyniki i ograniczenia: `../docs/VALIDATION_0_2_2.md`.

- `test_racial_research.py`: 15 scenariuszy wymagań i izolacji ras, szybkości nowych lotów, globalnego wzrostu floty, ułamków produkcji, strat, restartów oraz jednorazowych zwrotów rzeczywistych kosztów.
- `make_racial_research_fixture.py` + `test_racial_research_ui.gd`: karty trzech ras, wymagania, efekty, ilustracje, maksymalny poziom, postęp, podgląd zwrotów, hodowla i zgodność ze starszym serwerem.

```bash
python3 -m unittest discover -s tests -v
python3 tests/make_racial_research_fixture.py /tmp/racial-research.json
godot --headless --path . --script tests/test_racial_research_ui.gd -- /tmp/racial-research.json
```

Dla zrzutów ekranu użyj prawdziwego renderera zamiast `--headless` i podaj drugi argument użytkownika: katalog na PNG. Zrzuty sprawdzonych kart są w `docs/screenshots_0_2_2/`.

Poniżej zachowano historię poprzednich zestawów.

# Testy Alien Colonies 0.2.1

Aktualne wyniki: `../docs/VALIDATION_0_2_1.md`.

- `test_race_buildings.py`: 17 scenariuszy rzeczywistych efektów, izolacji ras/kolonii, snapshotów, limitów i wypłat.
- `make_unique_building_fixture.py` + `test_unique_building_ui.gd`: trzy katalogi, grafiki, ceny, wymagania, postęp, rabat partii i zgodność starszego protokołu.

```bash
python3 -m unittest discover -s tests -v
python3 tests/make_unique_building_fixture.py /tmp/unique-buildings.json
godot --headless --path . --script tests/test_unique_building_ui.gd -- /tmp/unique-buildings.json
```

Poniżej zachowano historię poprzednich zestawów.

# Testy Alien Colonies 0.2.0

Aktualne wyniki i odtwarzalne polecenia: `../docs/VALIDATION_0_2_0.md`.
103 testy Python, 517 kontroli koła, 303 kontrole interfejsu rozwoju oraz regresje ras, dotyku i planet przeszły. Koło testuje się przez `make_progression_fixture.py` / `test_progression_ui.gd`; starsze kontrole używają dołączonego `fixtures/legacy_ui_0111.json`.

Poniżej historia wcześniejszych zestawów i ich pierwotnych poleceń.

# Testy serwera i połączenia

W 0.1.11: `test_world_art.gd` sprawdza 12 par planet/panoram i przełączanie kolonii; używa tego samego lokalnego fixture co pozostałe testy UI.

```bash
python3 tests/make_ui_fixture.py /tmp/alien-colonies-ui.json
godot --headless --path . --script tests/test_world_art.gd -- /tmp/alien-colonies-ui.json
```

Wykonano: world_art 568 kontroli, presentation_ui 751 i ui_fixes_018 993 — wszystkie przeszły. To kontrole offline bez zrzutów renderowanego ekranu i bez instalowania APK.

Historyczna paczka Alien Colonies 0.1.11: weryfikacja zielonego interfejsu i par grafik planet/kolonii w docs/ALIEN_COLONIES_0_1_11_PL.md. Zakres kontroli mobilnych z poprzedniej wersji jest w docs/INTERFEJS_0_1_8_PL.md. Testy sprawdzają rzeczywistą szerokość tekstu, gesty list, duże przyciski i widoczność postępu, ponieważ same granice kontrolek nie wykrywały pionowego zawijania cyfr. Poniżej także historia starszych wersji.

Regresje mobilne 0.1.8:

```bash
python3 tests/make_ui_fixture.py /tmp/pogranicze-ui.json
godot --headless --path . --script tests/test_ui_fixes_018.gd -- /tmp/pogranicze-ui.json
godot --headless --path . --script tests/test_mobile_choice.gd
godot --headless --path . --script tests/test_mobile_quantity.gd
```

Nowe zestawy 0.1.7:

```bash
python3 tests/make_ui_fixture.py /tmp/pogranicze-ui.json
godot --headless --path . --script tests/test_mobile_ui.gd -- /tmp/pogranicze-ui.json
godot --headless --path . --script tests/test_presentation_ui.gd -- /tmp/pogranicze-ui.json
godot --headless --path . --script tests/test_galaxy_map.gd
godot --headless --path . --script tests/test_touch_scroll.gd
godot --headless --path . --script tests/test_apk_manifest.gd
```

Fixture APK w tests/fixtures to wyłącznie manifest działającej 0.1.6, nie APK. Testy manifestu używają go domyślnie; nie wymagają telefonu ani połączenia z Internetem.

Uruchom w głównym katalogu projektu:

```bash
python3 -m unittest discover -s tests -v
```

Testy wymagają tylko Pythona i jego biblioteki standardowej. Tworzą tymczasowe
bazy SQLite i uruchamiają serwer HTTP na losowym porcie lokalnym. Nie łączą się
z Internetem i nie modyfikują istniejącego świata gry. Scenariusze upływu czasu
korzystają ze sterowanego zegara, więc nie trzeba czekać na koniec budowy i lotów.

Sprawdzane zachowania:

- Dwa konta widzą wspólną galaktykę, zachowując własne planety i gospodarkę.
- Cudza planeta nie może być odczytana jako własna ani użyta do wysłania floty.
- Nieprawidłowe ilości, ujemny ładunek, NaN i przekroczenie dostępnych statków
  nie zmieniają stanu świata.
- Budowa kończy się dokładnie raz, a zajętej kolejki nie da się nadpisać.
- Podgląd lotu nie pobiera kosztu; zwiad wraca bez powielania statków.
- Transport dostarcza dokładną ilość ładunku po uwzględnieniu produkcji kolonii,
  nie rozładowuje go ponownie i wraca z tym samym transportowcem.
- Wyścig dwóch kolonizatorów nie nadpisuje właściciela kolonii.
- Ochrona startowa blokuje atak bez utraty zasobów i statków.
- Ponowne otwarcie bazy zachowuje sesję, kolejkę i lecącą flotę.
- Rój bez zasobów nie buduje kolonizatora, a bez paliwa go nie wysyła.
  Po opłaceniu budowy i lotu zakłada nową kolonię dokładnie raz.
- HTTP odrzuca brak autoryzacji, błędne dane logowania, niepoprawny JSON,
  nieprawidłowy typ dokumentu, przepełnienie liczby i zbyt duże żądanie.
- Równoczesne rozkazy nie mogą wydać tego samego kolonizatora dwa razy.

To testy logiki i kontraktu HTTP. Nie zastępują uruchomienia klienta na telefonie,
testów wydajności ani przeglądu bezpieczeństwa przed publicznym wdrożeniem.

W 0.1.2 dodatkowo sprawdzamy otwartą rejestrację ponad dwa konta, opcjonalny limit administracyjny, zachowanie sesji po restarcie, blokadę równoczesnego otwarcia zapisu, wybór adresu do APK, odrzucenie nieodpowiadającego tunelu i przywrócenie konfiguracji po błędzie eksportu. Testy z symulowanym procesem Godota sprawdzają narzędzie eksportu, nie tworzą instalowalnej aplikacji.

W 0.1.4 dodano tests/test_client_updates_server.py: konfiguracja wersji, publiczny manifest, odrzucenie starych klientów przed zmianą świata, poprawne żądania nowego klienta i niepoprawne linki. tests/test_railway_proxy.py sprawdza zachowanie limitów i nagłówków proxy. Są to testy HTTP na localhost, bez tworzenia kont na publicznym serwerze.

W 0.1.5 rozszerzono testy serwera o rozmiar i sumę SHA-256 pliku aktualizacji. `tests/test_prepare_update.py` sprawdza generator danych do Railway. Przed poprawką eksportera zestaw Python zawierał 58 testów.

Testy GDScript uruchom osobno w Godocie 4.5.1 lub nowszym:

```bash
godot --headless --path . --script tests/test_update_policy.gd
godot --headless --path . --script tests/test_apk_download.gd
```

Obejmują parser ustawień, unieważnianie pobranego pliku po zmianie wydania, anulowanie, opóźnione odpowiedzi i sprawdzanie pliku. Nie testują prawdziwej instalacji ani transmisji sieciowej na telefonie. Stan wykonania opisano w `docs/VALIDATION.md`.

Poprawka eksportera 0.1.5 dodaje `tests/test_export_android.py`: 4 testy obejmujące 21 scenariuszy logów procesu, poprawności wyniku i zachowania plików po błędzie. Uruchomiono je osobno; wszystkie przeszły. Cały zestaw liczy teraz 62 testy, ale po tej poprawce nie powtarzano niezmienionych testów gry i serwera.


## Trzy rasy (0.1.12)

`python3 -m unittest discover -s tests -p "test_races.py" -v` sprawdza trwały wybór, idempotencję, różnice ekonomii, statki, loty i walkę. `tests/make_race_fixture.py` oraz `tests/test_race_ui.gd` sprawdzają prawdziwy katalog i interfejs bez połączenia z serwerem produkcyjnym. Polecenia i ograniczenia: `../docs/VALIDATION_RACES.md`.

0.3.1: `test_race_buildings.py` pokrywa nowe premie Symbiontów i kolejność katalogu, `test_server_tempo.py` normalne tempo świata/hostingu, a `test_export_android.py` tryb testowy bez zmiennych podpisu release. Test UI budynków: `test_unique_building_ui.gd` z generatorem `make_unique_building_fixture.py`.
