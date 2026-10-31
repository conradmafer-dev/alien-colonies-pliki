# Alien Colonies 0.11.3 — Rój jako plaga

**Pełny serwer + WWW, bez nowego klienta Android.** Wdrożenie tej wersji na istniejącej
bazie jednorazowo resetuje wyłącznie NPC Rój. Nie resetuje kont ani postępów graczy.

Najpierw przeczytaj **AKTUALIZACJA_0.11.3_START_TUTAJ.txt**. Wgraj zawartość tego
katalogu bezpośrednio do głównego katalogu repozytorium serwera, zachowując cały `web/`,
nowy `swarm_reset.py`, `Dockerfile` i dotychczasowy Volume. Nie usuwaj bazy SQLite.

## Najważniejsze zmiany

Rój zaczyna od jednego małego gniazda w każdej dostępnej galaktyce: budynki na poziomie 1,
bez zapasów, statków, obrony i rzadkich kryształów. Wysyła opłacone kolonizatory z dwoma
małymi eskortowcami, zamiast czekać na wielką armię. Po opłaceniu ekspansji nadal rozwija
infrastrukturę i produkuje flotę za pozostałe zasoby. Nie ma sztywnego limitu liczby
statków w gnieździe. Gospodarka i siła pojedynczego gniazda rosną wolniej.

Nowi gracze trafiają do pierwszej galaktyki z wolną, niezarezerwowaną planetą.
Dotychczasowe kolonie nie są przenoszone. Stare ataki graczy na resetowane gniazda są
zawracane bez walki i bez usuwania statków lub ładunku.

## Uruchomienie i testy lokalne

```sh
python start_web.py --local-data ./local_data --port 8080
python -m unittest discover -s tests -v
node --test tests/*.mjs
```

Lokalny serwer używa odrębnej bazy `local_data/private_test.sqlite3`. Nie wskazuj mu
bazy produkcyjnej w ramach testowania.

Symulacja bez graczy i walk (czas świata przyspieszany skokami, nie mnożnik ekonomii):

```sh
python tools/simulate_swarm_plague.py --days 14 --step-seconds 1800 --output simulation.json
```

Po edycji WWW lub słowników uruchom `python tools/build_web_release.py` i dodaj do
commitu także `web/play/release.json`. Manifest sprawdza wersję i kompletność strony.
Ustawienia WWW, wybór języka, mapa galaktyki i dedykowane grafiki z 0.11.1 pozostają.

Wyniki tej aktualizacji: `VERIFICATION_0.11.3.json` i `docs/verification_0113/`.
Materiały z wcześniejszym numerem wersji są archiwalne, nie opisują nowego resetu.
