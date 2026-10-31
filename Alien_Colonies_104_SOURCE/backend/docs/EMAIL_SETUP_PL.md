# Alien Colonies — uruchomienie logowania linkiem e-mail

Obsługa została dodana do serwera, przeglądarki i Androida 0.11.19 (kod 64). Google pozostaje osobną metodą logowania. Nowa opcja jest ukryta, dopóki serwer nie ma konfiguracji wysyłki.

## Konfiguracja nadawcy

1. Otwórz https://resend.com/domains i dodaj domenę, z której chcesz wysyłać linki. Możesz użyć `aliencolonies.com` lub osobnej subdomeny. Wprowadź dokładnie rekordy DNS podane przez Resend i zaczekaj na status Verified.
2. Wyłącz śledzenie otwarć i kliknięć dla domeny używanej do logowania.
3. Na https://resend.com/api-keys utwórz klucz z uprawnieniem **Sending access**, ograniczony do zweryfikowanej domeny.
4. W Railway otwórz usługę `pogranicze-serwer` i jej zakładkę **Variables**. Dodaj:

| Zmienna | Wartość |
|---|---|
| `EMAIL_PROVIDER_API_KEY` | Klucz Resend. Wprowadź go bezpośrednio w Railway; nie zapisuj w źródłach ani aplikacji. |
| `EMAIL_FROM` | Np. `Alien Colonies <login@aliencolonies.com>`, jeśli zweryfikowano tę domenę. |
| `SITE_ORIGIN` | `https://aliencolonies.com` |

Zastosowanie zmiennych/restart serwera włączy obsługę e-mail. Odpowiedź `configured: true` z `/api/auth/email/config` oznacza rozpoznaną konfigurację; nie stanowi potwierdzenia faktycznego doręczenia poczty.

## Sprawdzenie po uruchomieniu

- Na własny adres zamów link w grze. Nie wysyłaj próbnych wiadomości na cudze adresy.
- Otwórz wiadomość, potwierdź logowanie i wróć do gry. Nowe konto poprosi o nazwę imperium, istniejące wczyta swoje imperium.
- W przeglądarce użyj tej samej przeglądarki; po potwierdzeniu wróć do pierwotnej karty gry.
- Na Androidzie użyj tego samego telefonu i przycisku powrotu do gry. Wymagana jest wersja 0.11.19/kod 64 lub nowsza.
- Sprawdź ponowne zalogowanie i usunięcie własnego testowego konta. Link działa raz i wygasa po 15 minutach. Restart serwera unieważnia niedokończone logowanie; wtedy zamów nowy link.

Nie ma hasła ani kodu do przepisywania. Konta Google i e-mail nie są automatycznie łączone. Używaj tej samej metody, którą założono dane imperium.

## Publikacja i dane

Gotową paczkę Androida należy przesłać do Google Play. Samo dodanie konfiguracji na serwerze nie aktualizuje zainstalowanych aplikacji. Nie podnoś minimalnej obsługiwanej wersji 63, dopóki nowa wersja nie będzie dostępna dla graczy.

Polityka prywatności i instrukcja usuwania konta zawierają opis nowej metody. Przy publikacji zaktualizuj deklaracje w Google Play tak, aby odpowiadały przetwarzaniu adresu e-mail i wysyłce wiadomości przez Resend. Serwer gry utrwala tylko identyfikator kryptograficzny adresu; dostawca wysyłki otrzymuje adres odbiorcy i treść wiadomości.

Testy wdrożeniowe używają atrap wysyłki i lokalnych baz. Dostarczenie prawdziwego e-maila i powrót do aplikacji na fizycznym telefonie wymagają sprawdzenia po skonfigurowaniu usługi.
