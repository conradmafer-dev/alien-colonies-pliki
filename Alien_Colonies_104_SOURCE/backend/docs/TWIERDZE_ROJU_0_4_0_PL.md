# Twierdze Roju — balans 0.4.0

## Zasady

| Parametr | Wartość |
|---|---|
| Początkowe gniazda | 3 twierdze, bez słabych przyczółków |
| Limit gniazd | 5 w całej galaktyce |
| Wyprawa kolonizacyjna | Najwyżej jedna na 7 rzeczywistych dni, od wylotu |
| Pierwsza kolonizacja | Nie wcześniej niż po 7 dniach |
| Odnowa Kryształu Roju | 1 / 18 rzeczywistych godzin / odbudowane gniazdo |
| Początkowy / maksymalny zapas | 3 / 6 |
| Podstawowy łup | Do 3, zależnie od premii, zapasu i ocalałej ładowni |
| Odnowa po rozbiciu | Wstrzymana do odbudowy minimalnej obrony |
| Powtórny nalot po zwycięstwie | Pozostały rzadki łup zamknięty do odbudowy obrony |
| Ataki na graczy | Tylko gdy nie ma żadnej wolnej planety, po ochronie gracza |

Rzeczywiste terminy kolonizacji i kryształów nie przyspieszają po zmianie PGR_SPEED. Kopalnie, kolejki i loty nadal korzystają z tempa świata. AI podejmuje decyzje również przy wylogowanych graczach, gdy proces serwera działa. Podczas przerwy serwera rozliczane są istniejące loty, kolejki i produkcja, lecz nie odtwarzają się tysiące nowych decyzji AI.

Ule płacą za wszystkie późniejsze budowy i statki. Początkowa flota to 360 Żuwaczy i 60 Królowych, gospodarka i wylęgarnia poziomu 8, węzeł feromonowy poziomu 6. Węzeł zwiększa siłę uzbrojenia o 15% na poziom. Ule mają 15% redukcji obrażeń i 10% regeneracji ran ocalałych kadłubów między rundami. Wyższy poziom wylęgarni i wiek podnoszą docelową liczebność floty; AI musi najpierw ją opłacić i wybudować.

Nowa kolonizacja przenosi istniejącą eskortę 180 Żuwaczy i 30 Królowych, nie odbierając macierzystemu ulowi wymaganej obrony. Nowe gniazdo nie otrzymuje darmowych kryształów ani statków i stopniowo rozbudowuje infrastrukturę.

## Koszty koła

Cena = zaokrąglenie w górę: `(dawna cena węzła / 6) × 1,12^liczba dokonanych zakupów`.

Licznik jest wspólny dla całego koła; własny darmowy korzeń nie jest zakupem. Wykupione i połączone umiejętności z poprzedniego zapisu liczą się do cen kolejnych. Ceny poszczególnych węzłów nadal różnią się wagą; każda pozostawiona umiejętność drożeje wraz z zakupami, choć wybór tańszego typu może kosztować mniej niż poprzedni droższy typ.

| Liczba wcześniejszych zakupów | Najniższa cena małego węzła, gdy pozostaje dostępny |
|---|---|
| 0 | 1 |
| 10 | 4 |
| 20 | 10 |
| 40 | 94 |
| 58 | 716 |

Pełne 59 zakupów kosztuje co najmniej 8639 i najwyżej 28448 kryształów niezależnie od kolejności (konserwatywne granice). Przykładowe poprawne przejścia przez połączone ścieżki kosztowały około 15–18 tys. To długoterminowa specjalizacja, a nie cel szybkiego ukończenia. Ule produkują wspólny zapas dla wszystkich graczy; serwer nie mnoży nagrody przez liczbę uczestników wypraw.

## Weryfikacja

- Symulacja 21 dni przy tempie ×1 i decyzjach AI co 120 sekund: czwarte gniazdo około dnia 7,13; piąte około dnia 14,24; nadal pięć po 21 dniach.
- Początkowe twierdze po 21 dniach: około 1188 Żuwaczy, 198 Królowych i technologia bojowa poziomu 17. Wydatki przechodzą przez normalną kolejkę i gospodarkę.
- Sprawdzono ochronę przed odnawianiem kryształów przy wyłączonej obronie oraz naloty dobierające pozostały łup z pustego gniazda.
- Sprawdzono rozliczanie kryształów po powrocie tylko raz, zgodność cen pokazanych z pobraniem na serwerze oraz jednokrotną migrację dawnej sieci przyczółków.
- Sprawdzono osobne ataki dwóch graczy: straty obrony po pierwszym nalocie pozwalają drugiemu zwyciężyć. To nie jest formalny system sojuszy ani wspólna bitwa; zwycięzca zabiera łup.

Liczby są wynikiem testów i symulacji. Rzeczywista trudność wobec dużych imperiów i wielu aktywnych graczy wymaga dalszych rozgrywek. Bardzo silna flota nadal może pokonać słabszą twierdzę; ograniczenie dostępności kryształów działa niezależnie od siły gracza.

W końcowej weryfikacji przeszły wszystkie 232 testy Python, import w Godot 4.5.1 oraz testy klienta: 21 nowych kontroli Roju, 63 interfejsu, 553 koła umiejętności i 41 kontrolek ilości. Nie wykonano eksportu ani testu instalacji na urządzeniu Android w tym środowisku.
