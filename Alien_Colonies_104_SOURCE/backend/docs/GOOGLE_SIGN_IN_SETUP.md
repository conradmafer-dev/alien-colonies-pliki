# Logowanie Google — Alien Colonies

Kod jest przygotowany dla strony i Androida. Aktywacja wymaga klienta OAuth w Google Cloud oraz dwóch zmiennych serwera. Klient gry nie zawiera sekretu OAuth.

## Google Cloud

1. Otwórz projekt `alien-colonies` w Google Cloud Console.
2. W **Google Auth Platform → Branding** ustaw nazwę `Alien Colonies`, kontakt pomocy, stronę `https://aliencolonies.com/` i politykę prywatności `https://aliencolonies.com/privacy`. Dodaj domenę `aliencolonies.com` do autoryzowanych domen, jeśli formularz tego wymaga.
3. W **Audience** wybierz użytkowników zewnętrznych. Dla ogólnodostępnej gry ustaw stan **In production**. Gdy projekt pozostaje w trybie **Testing**, Google ogranicza logowanie do wskazanych użytkowników testowych. Jeżeli konsola wymaga weryfikacji marki, wykonaj wskazany proces.
4. W **Clients → Create client** wybierz **Web application**. Ten klient obsługuje także Androida, który otwiera systemową przeglądarkę.
5. Dodaj dokładny **Authorized redirect URI**, bez końcowego ukośnika:

   ```text
   https://aliencolonies.com/api/auth/google/callback
   ```

6. Zapisz identyfikator klienta oraz jego sekret w bezpiecznym miejscu. Nie umieszczaj sekretu w repozytorium, źródłach Androida ani paczce AAB.

Serwer prosi o zakresy `openid profile`. Trwale zapisuje wyłącznie stały identyfikator Google `sub`, powiązany z kontem gry. Dane profilu są pomijane; zakres `email` nie jest żądany.

## Railway

W zmiennych usługi Alien Colonies ustaw:

| Zmienna | Wartość |
| --- | --- |
| `ALIEN_GOOGLE_CLIENT_ID` | Identyfikator klienta Web, zakończony `.apps.googleusercontent.com` |
| `ALIEN_GOOGLE_CLIENT_SECRET` | Sekret tego samego klienta OAuth |
| `ALIEN_GOOGLE_ORIGIN` | `https://aliencolonies.com` |

Zapisz zmienne i poczekaj na ponowne wdrożenie usługi. To inne dane niż JSON konta usługi używany w `ALIEN_PLAY_SERVICE_ACCOUNT_JSON` do płatności Google Play.

Po prawidłowym skonfigurowaniu logowania Google nowe imperia domyślnie wymagają potwierdzenia Google. Istniejące konta nadal mogą logować się dotychczasową nazwą i hasłem. Opcjonalna zmienna `ALIEN_REQUIRE_GOOGLE_REGISTRATION=true` jawnie utrzymuje wymóg; `false` świadomie zezwala również na rejestrację hasłem. Bez konfiguracji Google domyślnie pozostaje dostępna wcześniejsza rejestracja i logowanie.

## Sprawdzenie

1. Na `https://aliencolonies.com/play/` rozpocznij logowanie Google. Przeglądarka musi pozostać tą samą, w której uruchomiono grę.
2. Dla nowego konta wybierz nazwę imperium. Kolejne logowania tym samym kontem Google otwierają to samo imperium.
3. Dla starego konta zaloguj się hasłem, otwórz Ustawienia i połącz Google, potwierdzając obecne hasło. Sprawdź zachowanie planet i postępu oraz dalsze działanie logowania hasłem.
4. Na Androidzie od **wersji 0.11.12 / kodu 57** logowanie otwiera Google bez ręcznego wpisywania kodu. Wybierz konto Google; przeglądarka spróbuje automatycznie wrócić do aplikacji. Jeżeli pozostanie na stronie potwierdzenia, naciśnij **Wróć do gry**. Dokończ wybór nazwy imperium w grze, jeśli konto jest nowe.
5. Upewnij się, że Ustawienia umożliwiają potwierdzenie konta Google i usuwanie konta. Dla konta bez hasła wrażliwe operacje wymagają logowania Google z ostatnich pięciu minut.

Rozpoczynaj logowanie we własnej aplikacji. Otwarte próby logowania wygasają po 10 minutach; po restarcie serwera albo zamknięciu procesu aplikacji należy rozpocząć próbę ponownie. Powiązanie konta Google i postęp imperium są zapisane w bazie.

## Powrót z przeglądarki na Androidzie

Nowy Android wysyła przy rozpoczęciu logowania `client: "android"` i `handoff: "app_link_v1"`. Serwer nie tworzy wtedy sześciocyfrowego kodu. Po sprawdzeniu tożsamości Google przeglądarka wraca pod stały adres:

```text
com.conradmafer.aliencolonies://google-auth?flow_id=…&handoff_ticket=…
```

Ten adres obsługuje aplikacja Android. **Nie dodawaj go do Google Cloud jako URI przekierowania** — jedyny callback Google nadal brzmi `https://aliencolonies.com/api/auth/google/callback`. Nie trzeba tworzyć nowego klienta OAuth ani zmieniać zmiennych Railway.

Powrót przenosi krótko żyjący, losowy dowód przeglądarki. Nie zawiera sesji gry, hasła, identyfikatora Google ani sekretu odpytywania. Serwer przechowuje tylko skrót dowodu. Aplikacja akceptuje powrót wyłącznie do własnej, nadal otwartej próby i przesyła go razem z osobnym sekretem zachowanym w pamięci. Samo odpytywanie serwera albo przechwycenie adresu powrotu nie wystarcza do zalogowania. Po potwierdzeniu obu dowodów wynik można odebrać tylko raz.

**Starszy Android z kodem 56** nadal korzysta z wcześniejszego formularza sześciocyfrowego kodu. Serwer zachowuje ten protokół, aby aktualizacja nie blokowała zainstalowanych kopii; błąd przekierowania formularza do Google został poprawiony w polityce CSP. Całkowity brak ręcznego kodu wymaga instalacji Androida z kodem 57. Wersja przeglądarkowa działa jak wcześniej, z potwierdzeniem inicjującej przeglądarki przez bezpieczne ciasteczko.

## Dokumentacja Google

- [Klient OAuth aplikacji serwerowej](https://developers.google.com/identity/protocols/oauth2/web-server)
- [OpenID Connect i wymagane zakresy](https://developers.google.com/identity/openid-connect/reference)
- [Weryfikacja ID tokenu i identyfikator sub](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token)
- [Audience i publikacja projektu OAuth](https://support.google.com/cloud/answer/15549945)
- [Weryfikacja marki](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification)

Sprawdzono dokumentację 11 października 2026 r. Testy kodu izolują Google lokalnym dostawcą lub lokalnymi kluczami RSA; rzeczywiste logowanie wymaga konfiguracji powyżej i osobnego sprawdzenia na własnym koncie.
