# Android 90 (0.12.23): galaktyki i powiadomienia

Galaktyka zawiera pięć pierścieni i 105 układów. WWW i Android ustawiają optyczne jądro każdej z sześciu grafik na środku orbit; grafika jest powiększona 1,5 raza. Położenie pozostaje zgodne przy przesuwaniu i powiększaniu.

Android prosi o pozwolenie na powiadomienia po zalogowaniu do wybranego imperium. Każdy nowy raport może utworzyć jedno powiadomienie: budowa, badania, misja, walka i inne zdarzenia korzystające z raportów gry. Dotknięcie otwiera zakładkę Raporty. Historyczne raporty przy logowaniu nie wywołują powiadomień. Wylogowanie i zmiana konta odłączają poprzednie imperium.

## Włączenie wysyłki przy zamkniętej aplikacji

Kod i pakiet Androida zawierają odbiornik Firebase Cloud Messaging. Wysyłka pozostaje nieaktywna, dopóki poniższe zmienne środowiskowe serwera nie zostaną skonfigurowane. Dostępne powiadomienia lokalne korzystają z odświeżania raportów podczas pracy aplikacji.

1. W projekcie Firebase dodaj aplikację Android o nazwie pakietu `com.conradmafer.aliencolonies`.
2. Pobierz jej publiczny plik `google-services.json` i ustaw jego pełną zawartość jako `ALIEN_FIREBASE_ANDROID_CONFIG_JSON` w istniejącym serwisie Railway.
3. Ustaw `ALIEN_FIREBASE_SERVICE_ACCOUNT_JSON` jako JSON konta usługi z tego samego projektu, uprawnionego do wysyłki FCM HTTP v1. Klucz prywatny pozostaje w zmiennych serwera; nie dodawaj go do aplikacji, źródeł ani archiwów.
4. Włącz Firebase Cloud Messaging API dla projektu i wdroż nowe zmienne. Nowa aplikacja pobiera publiczną konfigurację z `/api/notifications/config`, więc nie wymaga kolejnej kompilacji po uzupełnieniu Firebase.
5. Na fizycznym telefonie uruchom Androida 90, zaloguj się, zezwól na powiadomienia i odczekaj do następnego odświeżenia raportów. Zweryfikuj powiadomienie nowego raportu po przejściu do innej aplikacji i po zamknięciu gry oraz otwieranie Raportów po dotknięciu.

Serwer zapisuje zlecenie powiadomienia w tej samej transakcji co raport. Oddzielny pracownik wysyła tylko zatwierdzone raporty, bez utrzymywania blokady świata podczas połączenia z Firebase. Próby są ponawiane z opóźnieniem; kolejka wygasa po 24 godzinach. Urządzenie jest powiązane z ważną sesją, a nieaktywny token jest usuwany.

## Weryfikacja

Automatyczne testy obejmują pełną natywną nawigację z mapą pięciu pierścieni, sześć jąder przy różnych przybliżeniach i przesunięciach, brak historycznych i powtórnych powiadomień, zmianę konta, otwieranie Raportów oraz transakcje, kolejkę i ponawianie wysyłki serwera. Testy odbiornika Androida na fizycznym telefonie i faktycznej wysyłki FCM wymagają konfiguracji powyżej.
