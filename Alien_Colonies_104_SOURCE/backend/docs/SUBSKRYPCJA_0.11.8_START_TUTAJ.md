# Alien Colonies 0.11.8 — subskrypcja kolejek
Android: wersja 0.11.8, kod 52. Cena bazowa w Polsce: **4,99 zł miesięcznie**.

Subskrypcja odblokowuje do 10 oczekujących zleceń w każdej kolejce:
- budowa i ulepszanie budynków na każdej kolonii;
- konstrukcja statków i obrony w stoczni każdej kolonii;
- badania we wspólnej kolejce całego imperium.

Zlecenia startują po kolei także po zamknięciu gry. Surowce są pobierane dopiero przy rozpoczęciu, a aktualne wymagania, koszt i czas są wtedy sprawdzane ponownie. Przy braku surowców pierwsze zlecenie czeka. Po wygaśnięciu abonamentu rozpoczęte zadania kończą się normalnie, a oczekujące pozostają widoczne i można je porządkować lub usuwać. Zwykłe ręczne uruchamianie trzech równoległych prac pozostaje bezpłatne.

## Zbuduj nowy AAB
Rozpakuj całą paczkę i uruchom **BUILD_GOOGLE_PLAY_AAB_WINDOWS.bat**, używając swojego dotychczasowego lokalnego klucza. Wtyczka Google Play Billing jest już dołączona i włączona. Szczegóły: docs/SUBSKRYPCJA_GOOGLE_PLAY_ANDROID_PL.md.

## Utwórz produkt w Google Play
Po opublikowaniu AAB w testach wewnętrznych lub zamkniętych przejdź do Zarabiaj w Google Play → Produkty → Subskrypcje → Utwórz subskrypcję.

| Pole | Wartość |
| --- | --- |
| Identyfikator produktu | queue_planner |
| Nazwa | Planer kolejek |
| Identyfikator abonamentu podstawowego | monthly |
| Typ | Automatyczne odnawianie |
| Okres rozliczeniowy | 1 miesiąc |
| Cena w Polsce | 4,99 PLN |
| Pozostałe kraje | Przeliczone ceny proponowane przez Google Play |

Przed aktywacją obejrzyj podsumowanie cen regionalnych. Gra pokazuje cenę zwróconą przez Google Play dla kraju gracza; nie ma własnego stałego kursu walut.

Proponowane korzyści do wpisania:
- Planowanie kolejki budowy
- Kolejka konstrukcji statków
- Kolejka badań
- Automatyczna praca także poza grą

## Podłącz serwer do Google Play
1. W Google Cloud utwórz lub wybierz projekt i włącz **Google Play Android Developer API**.
2. Utwórz konto usługi.
3. W Play Console → Użytkownicy i uprawnienia zaproś adres e-mail konta usługi. Przyznaj dla Alien Colonies dostęp do danych finansowych, zamówień i odpowiedzi na ankiety anulowania oraz zarządzania zamówieniami i subskrypcjami.
4. Dane konta usługi umieść na serwerze Railway jako prywatną zmienną **ALIEN_PLAY_SERVICE_ACCOUNT_JSON**, następnie zastosuj zmianę konfiguracji. Alternatywnie można użyć pliku wskazanego przez GOOGLE_APPLICATION_CREDENTIALS.
5. Dane konta usługi należą wyłącznie do serwera. Nie dodawaj ich do paczki Androida.

Jeśli serwer nie ma dostępu do Google API, gra nie uruchomi płatnego zakupu. Po konfiguracji serwer sprawdza zakup i potwierdza go przez Google, a odnowienia i zmiany stanu sprawdza również dla graczy poza grą. Subskrypcja jest przypisana do konta Alien Colonies i działa także w przeglądarce.

## Test przed uruchomieniem sprzedaży
Zainstaluj nowy Android przez Google Play i użyj konta testera licencyjnego. Sprawdź zakup, przywrócenie po ponownym zalogowaniu, wygaśnięcie, anulowanie oraz widoczność kolejek po zalogowaniu na to samo konto w przeglądarce. Wykonane testy automatyczne używały kontrolowanych odpowiedzi Google; nie są testem rzeczywistego rozliczenia przez sklep.

Instrukcje Google:
- https://developer.android.com/google/play/billing/getting-ready
- https://support.google.com/googleplay/android-developer/answer/140504?hl=pl
- https://developers.google.com/android-publisher/getting_started

Serwer i strona WWW są rozwijane w repozytorium conradmafer-dev/pogranicze-serwer. Paczka służy przede wszystkim do budowy klienta Android; pełne zoptymalizowane grafiki WWW pozostają w repozytorium serwera.

