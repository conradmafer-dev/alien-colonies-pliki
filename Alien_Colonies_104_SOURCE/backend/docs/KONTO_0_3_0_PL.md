# Konto i odzyskiwanie — Alien Colonies 0.3.0

Konto jest powiązane z nazwą imperium i hasłem. Ta wersja nie wymaga adresu
e-mail i nie wysyła wiadomości z linkiem resetującym hasło. Gracz sam tworzy
w ustawieniach kod odzyskiwania i zapisuje go poza grą, np. w menedżerze haseł.

## Kod odzyskiwania

- Utworzenie lub zastąpienie kodu wymaga aktywnej sesji i obecnego hasła.
- Kod zawiera 192 bity losowości. Serwer przechowuje tylko jego skrót SHA-256
  w osobnej tabeli kont; kod nie trafia do stanu galaktyki ani raportów.
- Pełny kod jest zwracany tylko bezpośrednio po utworzeniu. Serwer nie ma funkcji
  ponownego wyświetlenia starego kodu. Nowy kod natychmiast zastępuje poprzedni.
- Reset wymaga nazwy imperium, kodu oraz nowego hasła mającego 8–128 znaków.
  Po poprawnym resecie kod zostaje zużyty, wszystkie dotychczasowe sesje wygasają,
  a gracz dostaje nową sesję. Następnie powinien utworzyć nowy kod odzyskiwania.
- Literówka lub nieprawidłowe nowe hasło nie zużywa poprawnego kodu i nie zmienia
  hasła ani aktywnych sesji. Kod innego imperium nie działa.
- Jeśli gracz straci zarówno hasło, jak i kod, ta wersja nie zapewnia
  automatycznego odzyskania konta. Nie należy obiecywać odzyskiwania przez e-mail.

## Zmiana hasła i sesje

Zmiana hasła wymaga obecnego hasła. Unieważnia wszystkie stare sesje oraz kod
odzyskiwania i zwraca nową sesję dla urządzenia wykonującego zmianę. Operacja
„Wyloguj inne urządzenia” zachowuje tylko sesję używaną do jej wykonania;
nie zmienia hasła ani kodu. Obie operacje dotyczą wyłącznie tego konta.

Nieprawidłowe obecne hasło zwraca błąd 403, dzięki czemu literówka nie wylogowuje
gracza. Kod 401 w prywatnych operacjach konta oznacza brak lub wygaśnięcie sesji.

## Usuwanie konta

Usunięcie wymaga aktywnej sesji, obecnego hasła i dokładnej frazy `USUŃ KONTO`.
Jest wykonywane w jednej transakcji wraz z zapisem świata:

1. Znikają dane uwierzytelniania, wszystkie sesje i kod odzyskiwania tego konta.
2. Znika gracz, jego badania, umiejętności, raporty, Kryształy Roju oraz floty
   znajdujące się w podróży, razem z ich ładunkiem.
3. Wszystkie jego kolonie stają się pustymi planetami. Nie zachowują budynków,
   statków, zasobów ani zamówień. Ich stałe nazwy i położenie w galaktyce zostają.
4. Pozostałe konta, kolonie i floty są zachowywane. Cudza misja do zwolnionej
   planety pozostaje pojedynczą misją z dotychczasowym terminem i ładunkiem.
   Atak przy dotarciu zostaje odwołany, zwiad widzi wolną planetę, a kolonizacja
   może się udać według zwykłych zasad. Usunięcie konta nie tworzy łupów.

Historyczne raporty zapisane u innych graczy mogą nadal zawierać dawny pseudonim
imperium. Nie zawierają haseł, kodów odzyskiwania ani tokenów logowania.
Usunięcie działa w aktywnej bazie. Starsze kopie zapasowe mogą nadal zawierać
poprzedni stan do czasu ich usunięcia zgodnie z ustawioną przez operatora
rotacją. Przy ręcznym odtwarzaniu starej kopii operator musi ponownie uwzględnić
usunięcia kont wykonane po dacie tej kopii; gra nie prowadzi zewnętrznego rejestru
tych usunięć. Nie należy obiecywać natychmiastowego wymazania wszystkich kopii.

## API dla klienta

Wszystkie żądania są JSON przez HTTPS. Nagłówki i limity obsługuje serwer HTTP.
Operacje `/api/account/*` wymagają `Authorization: Bearer …` oraz hasła.

| Ścieżka POST | Pola | Sukces |
|---|---|---|
| `/api/account/recovery-code` | `password` | `ok`, jednorazowy `recovery_code`, `message` |
| `/api/recover` | `name`, `recovery_code`, `new_password` | `ok`, nowy `token`, `state`, `message` |
| `/api/account/password` | `password`, `new_password` | `ok`, nowy `token`, `state`, `message` |
| `/api/account/logout-others` | `password` | `ok`, `message` |
| `/api/account/delete` | `password`, `confirmation` | `ok`, `deleted: true`, `message` |

Publiczny stan konta zawiera wyłącznie `recovery_code_enabled`, bez samego kodu
i bez jego skrótu. Hasło, kod odzyskiwania i token nie mogą być dopisywane do logu
aplikacji, raportu błędu ani adresu URL. Konto w aktywnej grze nadal używa tego
samego identyfikatora niezależnie od zmiany hasła lub odzyskania dostępu.
