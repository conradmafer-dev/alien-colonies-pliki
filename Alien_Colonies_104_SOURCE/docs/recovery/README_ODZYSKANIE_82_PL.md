# Alien Colonies — odzyskany projekt 0.12.15, kod 82

Projekt jest przygotowany do dalszej edycji w **Godot 4.5.1**. Zawiera klienta odpowiadającego paczce `Alien_Colonies_ANDROID_0.12.15_CODE_82.aab` oraz aktualny kod serwera z GitHuba, przypięty do commitu `5ff017c36b503a512e7f483a774755e88e3e9f21` z 19 października 2026.

## Otwieranie gry

1. Rozpakuj całe archiwum do jednego folderu.
2. W Godot 4.5.1 wybierz **Importuj**, wskaż `project.godot` i otwórz projekt.
3. Poczekaj na pierwszy import grafik. Może potrwać kilka minut.
4. Uruchom projekt klawiszem **F5**.

Skrypty gry są w `client/scripts`, grafiki w `client/assets`, scena startowa w `client/scenes/main.tscn`, a tłumaczenia w `localization`. Konfiguracja połączenia klienta pozostała taka jak w AAB; samo odzyskanie projektu nie zmienia działającego świata.

## Co zostało odzyskane

- Wszystkie **61 skryptów GDScript obecnych w AAB 82** — zgodność tokenów i układu sprawdzona względem skompilowanych plików. Część odtworzonego tekstu ma inne formatowanie; komentarze nieobecne w skompilowanej paczce nie mogły zostać odzyskane.
- **234 tekstury**, oryginalne ścieżki, ustawienia importu i scena główna. Zachowano 29 oryginalnych plików SVG po porównaniu wyrenderowanych pikseli z AAB.
- Konfiguracja Godota odczytana z `project.binary`, pięć języków i konfiguracja serwera z AAB.
- Dodatek Google Play Billing z oryginalnymi AAR debug/release i źródłami Kotlin.
- Dodatek AlienGoogleAuth: odtworzone źródła Java, manifest i biblioteki Android. Szczegóły kompilacji i ograniczeń testów są przy jego źródłach.
- Aktualny backend i strona WWW w `backend`. To kod z głównego katalogu repozytorium, a nie starsze kopie z katalogów `server` i `railway`.

Bazą pomocniczą były zachowane źródła 0.11.10 oraz paczka skryptów 81 z poprawką 82. Trzy stare pomocnicze skrypty instalatora APK pozostały w źródłach, ale są wyłączone z eksportu, tak jak w wydaniu Google Play.

## Aktualny serwer lokalnie

Serwer jest oddzielnym programem Python. Uruchom go z katalogu `backend`:

```sh
python -m pip install -r requirements.txt
python start_web.py --local-data ./local_data --port 8080
```

Kod produkcyjny korzysta z Python 3.12. Na Windows możesz również użyć `START_SERVER_LOCAL_WINDOWS.bat` po zainstalowaniu Pythona i zależności. Dane testowego świata trafią do `backend/local_data`. Strona lokalna: `http://127.0.0.1:8080`, kontrola serwera: `http://127.0.0.1:8080/health`.

Do testowania klienta z lokalnym backendem trzeba osobno ustawić jego adres serwera. Wersja źródeł serwera jest oznaczona w kodzie jako 0.12.13; nie została sztucznie zmieniona na numer klienta Android.

## Budowanie Androida

W projekcie są profile eksportu **Android Test** i **Google Play AAB**, ustawione na wersję **0.12.15 / 82**, pakiet `com.conradmafer.aliencolonies`, minimum SDK 24 i target SDK 36.

1. Zainstaluj szablony eksportu dokładnie dla Godot 4.5.1.
2. Skonfiguruj w edytorze Java SDK 17 i Android SDK z platformą 36 oraz wymaganymi narzędziami budowania.
3. Zainstaluj szablon budowania Androida z menu projektu. Eksport korzysta z Gradle i obu dołączonych dodatków. Gotowe AAR są już dołączone; kompilowanie źródeł dodatków jest potrzebne dopiero wtedy, gdy zechcesz je zmienić.
4. Wybierz profil eksportu. Pierwsza kompilacja pobierze zależności Google/AndroidX.
5. Dla wydania do Google Play ustaw **własny istniejący klucz wysyłania** i alias. Nie są zawarte w AAB ani w tej paczce.

Kod 82 zachowano dla identyfikacji odzyskanego wydania. Przed publikacją nowej aktualizacji ustaw większy kod wersji niż ostatnio przyjęty w Play Console. Pełny podpisany AAB i działanie logowania oraz zakupów na urządzeniu wymagają osobnej próby z Twoją konfiguracją Google Play/OAuth.

## Granice odzyskania

To kompletna robocza baza kodu klienta i bieżącego backendu, nie kopia wszystkich danych produkcyjnych. **Bazy graczy i świata sprzed resetu, sekretów hostingu, klucza podpisu i ustawień Play Console/OAuth nie ma w AAB.** Stary świat można przywrócić tylko z zachowanego backupu danych.

W oryginalnym `project.binary` pozostało oznaczenie 0.12.14, mimo że Android manifest i skrypty mają 0.12.15 / 82. W `project.godot` i profilach eksportu uporządkowano oznaczenie do 0.12.15. Pozostałe odzyskane ustawienia klienta zachowano.

Raporty pochodzenia i sprawdzeń znajdują się w `docs/recovery`. Nie zawierają potwierdzenia wykonania zakupów ani logowania Google na prawdziwym urządzeniu. Przywrócenie kodu nie oznacza cofnięcia resetu świata.

## Wykonane sprawdzenia

- Godot 4.5.1: import edytora, uruchomienie głównej sceny przez 120 klatek w trybie headless oraz eksport pakietu PCK z profilu Windows — zakończone bez błędów skryptów.
- 61 skryptów: identyczne tokeny i układ względem GDSC w oryginalnym AAB.
- 234 tekstury: identyczne piksele we wszystkich 330 poziomach mipmap po ponownym imporcie w Godocie.
- Backend: poprawna składnia 154 plików Python; strona, /health, lokalna rejestracja, logowanie i stan gry — HTTP 200 na odizolowanej bazie testowej.
- AlienGoogleAuth: AAR debug/release zbudowane przez javac 17, oba zaakceptowane przez kompilator Android D8; 77 asercji obsługi odpowiedzi, anulowania, nieaktualnych wyników i adresów powrotu.
- Google Play Billing: oryginalne AAR; sprawdzone 19 metod API względem AAB 82 i zgodność źródeł z upstream.

Eksport PCK nie zastępuje próby całego APK/AAB. Pełna kompilacja Androida, podpisywanie i test na urządzeniu pozostają kolejnym etapem przed publikacją.
