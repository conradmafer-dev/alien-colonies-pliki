# Odtworzenie testów interfejsu logowania86

Wymagania: Python3 i Godot **4.5.1 stable** dla używanego systemu. Test nie wymaga Android SDK, konta Google, skrzynki e-mail ani połączenia z serwerem gry. Nie uruchamiać go na telefonie: to test offline w Godot headless.

Z katalogu głównego rozpakowanych źródeł uruchom:

```bash
python3 docs/version86/prepare_auth_ui86.py --godot /pelna/sciezka/Godot_v4.5.1-stable_linux.x86_64 --work-dir /tmp/alien-auth-ui86
```

Windows PowerShell, z odpowiednio poprawioną ścieżką Godot:

```powershell
python docs/version86/prepare_auth_ui86.py --godot "C:\Godot\Godot_v4.5.1-stable_win64_console.exe" --work-dir "$env:TEMP\alien-auth-ui86"
```

Katalog roboczy musi być nowy lub pusty, poza źródłami. Można pominąć `--work-dir`, aby utworzyć nowy katalog tymczasowy. Skrypt wypisze jego ścieżkę. Przy uruchomieniu z innego miejsca można podać `--source /sciezka/Alien_Colonies_86_SOURCE`.

Skrypt najpierw porównuje pięć zamrożonych plików z `client_freeze86.json`. Następnie kopiuje z bieżącej paczki do izolowanego projektu:

- `client/scripts/` i `localization/`;
- wyłącznie pliki `*.gd` z `addons/`, z zachowaniem podkatalogów;
- trzy obrazy: `client/assets/alien_colonies_portrait.png`, `alien_colonies_icon.png`, `google_signin_g.png`;
- sześć małych plików z `auth_ui86_fixture.zip`: projekt testowy, scena, test, host oraz dwa transporty testowe.

Nie kopiuje pełnego projektu, całej biblioteki grafik, konfiguracji serwera, danych kont ani istniejącego cache. Źródła pozostają niezmienione. Godot tworzy cache importu wyłącznie w katalogu roboczym.

Dokładne polecenia Godot wykonywane przez skrypt:

```text
GODOT --headless --editor --import --path KATALOG_ROBOCZY/ui_project
GODOT --headless --path KATALOG_ROBOCZY/ui_project
```

Zmienna `AC_AUTH86_REPORT_PATH` wskazuje `KATALOG_ROBOCZY/auth_ui86_report.json`. Jedyna różnica między spakowanym testem a testem użytym przy wydaniu to przenośna ścieżka wyjściowa raportu; asercje pozostały identyczne. Bez tej zmiennej test zapisuje raport w swoim izolowanym projekcie.

Oczekiwany wynik: **1796 sprawdzeń, 0 błędów**. Raport JSON oraz `auth_ui86_import.log` i `auth_ui86_runtime.log` pojawią się w katalogu roboczym. Raporty przeprowadzonego testu, logi, `client_ui86.diff` i sumy `client_freeze86.json` są też dołączone bezpośrednio w tym katalogu dokumentacji. Ścieżki `work86_checks/` w oryginalnym raporcie odnoszą się do stanowiska, na którym przygotowano wydanie.

Test wykonuje rzeczywisty interfejs Godot, obsługę odpowiedzi logowania i kontrolery Google/e-mail. Odpowiedzi HTTP/native są syntetyczne. Zapis sesji i renderowanie pełnego ekranu gry zastępuje host testowy. Sprawdzane są oba sposoby logowania, istniejące konta i wybór rasy, błędna nazwa, anulowanie, wygaśnięcie, konfiguracja w tle, ogłoszenie, reauth, logout, sesja401, PL/EN i pięć rozmiarów viewportu. Marginesy Androida są symulowane.

Wynik nie oznacza sprawdzenia fizycznego urządzenia, realnego logowania Google/e-mail ani zakupów. Nie przygotowano zrzutów telefonu z renderera headless. Skrypt nie wdraża aplikacji ani serwera.
