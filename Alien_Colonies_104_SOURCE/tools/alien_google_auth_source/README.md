# AlienGoogleAuth — odtworzone źródła CODE 82

Ten katalog zawiera edytowalny projekt Android/Java wtyczki logowania. Cztery klasy Java odtworzono z kodu DEX paczki `Alien_Colonies_ANDROID_0.12.15_CODE_82.aab`. Jest to rekonstrukcja zachowania, a nie oryginalny tekst źródłowy sprzed kompilacji. Manifest odczytano z tej samej paczki. Nazwy publicznych metod, adnotacje Godota, walidacja wejścia, obsługa błędów, unieważnianie wcześniejszych prób i kolejka przekierowań odpowiadają CODE 82.

## Budowanie

Wymagania: JDK 17, Android SDK `platforms;android-36` i `build-tools;36.0.0`, dostęp do repozytoriów Google/Maven Central/Gradle. Ustaw `JAVA_HOME` i `ANDROID_HOME` na własne instalacje albo wpisz `sdk.dir=/własna/ścieżka/do/Android/Sdk` w lokalnym pliku `local.properties`.

Dołączone AAR debug i release skompilowano i sprawdzono przez `javac` oraz Android D8. Aby odtworzyć tę sprawdzoną ścieżkę (Python 3):

```sh
python3 build_portable.py
```

Skrypt pobiera przypięte zależności z oficjalnych repozytoriów, weryfikuje SHA256, kompiluje cztery klasy dla obu wariantów, sprawdza je D8 i tworzy AAR. Wtyczka nie ma własnych zasobów Androida, dlatego nie wymaga przetwarzania zasobów przez AGP. Pliki pośrednie zależności są w `.portable-cache`; nie należą do źródeł projektu. Skrypt przyjmuje także `--sdk`, `--jdk` i `--dependencies`.

Alternatywnie można użyć standardowego projektu Gradle (ta ścieżka jest dołączona, ale finalnych AAR nie zbudowano nią podczas odzyskiwania):

Z tego katalogu:

```sh
./gradlew :alien-google-auth:installAddons
```

Windows:

```bat
gradlew.bat :alien-google-auth:installAddons
```

Wynik trafia do katalogu projektu Godota:

- `addons/AlienGoogleAuth/bin/debug/AlienGoogleAuth-debug.aar`
- `addons/AlienGoogleAuth/bin/release/AlienGoogleAuth-release.aar`

W Godocie 4.5.1 włącz wtyczkę `AlienGoogleAuth` i eksport Android z Gradle. Do paczki AAB zależności dodaje `addons/AlienGoogleAuth/export_plugin.gd`. Sam plik AAR nie zawiera SDK Google ani silnika Godot.

Przypięte zależności:

| Składnik | Wersja |
| --- | --- |
| Godot API | 4.5.1.stable, `compileOnly` |
| Android Gradle Plugin | 8.13.2 |
| Gradle | 8.14.5 |
| AndroidX Credentials | 1.6.0 |
| Credentials Play Services Auth | 1.6.0 |
| Google ID | 1.2.0 |

## Interfejs Godota

Singleton: `AlienGoogleAuth`. Wtyczka nie emituje sygnałów; klient odpytuje kolejki.

| Metoda | Wynik / znaczenie |
| --- | --- |
| `getGoogleSignInVersion()` | `1` |
| `beginGoogleSignIn(request_id, server_client_id, nonce)` | Rozpoczyna natywne logowanie; wszystkie trzy argumenty to String |
| `takePendingGoogleSignIn()` | Jednorazowy JSON albo pusty String |
| `cancelGoogleSignIn()` | Unieważnia aktywną próbę i jej wynik |
| `clearGoogleSignInState()` | Unieważnia próbę i czyści stan Credential Manager |
| `setExpectedFlow(flow_id)` | Ustawia oczekiwany identyfikator powrotu z przeglądarki |
| `takePendingReturn()` | Jednorazowy, zwalidowany URL powrotu albo pusty String |

JSON natywny zawiera `request_id`, `status` (`success`, `cancelled` lub `error`), opcjonalnie `id_token` lub `error_code`. Kody błędów: `invalid_request`, `activity_unavailable`, `provider_error`, `invalid_credential`, `cancelled`, `no_credential`, `provider_unavailable`, `unsupported`.

Przekierowanie przeglądarki ma schemat `com.conradmafer.aliencolonies://google-auth?flow_id=...&handoff_ticket=...`. Wtyczka akceptuje wyłącznie oczekiwany flow i dozwolone pola. Token z Google przekazywany jest do serwera; dopiero serwer sprawdza podpis, odbiorcę i nonce oraz przyznaje sesję. Nie zapisuj tokenów ani treści odpowiedzi w logach.

## Weryfikacja i ograniczenia

```sh
python3 run_mailbox_tests.py
```

77 asercji sprawdza m.in. opóźnione callbacki po zmianie konta, anulowanie, jednokrotny odczyt tokenu, błędne i niejednoznaczne URI, deduplikację i ograniczenie kolejki do czterech wpisów. `recovery_evidence/` zawiera wynik testów, skróty źródeł, odczytane adnotacje, manifest i instrukcje DEX użyte do porównania. Raport udanej kompilacji obu wariantów i sprawdzenia D8 znajduje się w `BUILD_VERIFICATION.json`.

Pełne logowanie wymaga konfiguracji OAuth, właściwego identyfikatora pakietu i certyfikatu aplikacji oraz działającego serwera. Testy lokalne nie zastępują próby logowania/anulowania/wylogowania na Androidzie ani publikacji testowej Google Play. Klucza podpisującego, sekretów serwera i kont OAuth nie da się odzyskać z tej rekonstrukcji.
