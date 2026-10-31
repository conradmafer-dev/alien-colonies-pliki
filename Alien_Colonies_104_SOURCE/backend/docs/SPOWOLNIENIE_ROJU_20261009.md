# Wolniejsza kolonizacja Roju — 9 października 2026

Rój wysyła najwyżej jedną wyprawę kolonizacyjną na galaktykę co 24 godziny. To samo gniazdo może wysłać kolejną wyprawę po 48 godzinach; nowe gniazdo musi mieć co najmniej 24 godziny. Wszystkie odstępy dotyczą rzeczywistego czasu, niezależnie od szybkości produkcji. Koszty, budowa statków i podróż dodatkowo ograniczają tempo.

Pierwsze uruchomienie nowej polityki jednorazowo wydłuża stare zapisane terminy: istniejące gniazda czekają co najmniej 48 godzin od zastosowania zmiany, a bramka galaktyki co najmniej 24 godziny. Dłuższe istniejące terminy pozostają. Znacznik `swarm_expansion_tempo=slow-20261009` jest zapisywany w bazie; ponowne uruchomienie nie przesuwa terminów ponownie.

Zmiana nie uruchamia resetu. Zachowuje kolonie, zasoby, statki, opłacone kolejki i wyprawy już w locie oraz cały postęp graczy. Trwająca kolonizacja może nadal zakończyć się normalnie. Stały znacznik resetu `khar-plague-0113-v1` pozostaje bez zmiany. Nie jest potrzebny nowy AAB.

Weryfikacja: 51 testów polityki, migracji i zachowania świata oraz 14 testów niszczenia przyczółków przeszło. Z 12 starszych testów najazdów 11 przeszło; test przygotowywania transportowców ma ten sam wcześniejszy błąd także na niezmienionym `main` (oczekuje najazdu mimo dostępnych celów kolonizacji).

Izolowana symulacja 7 dni, krok 1800 sekund, szybkość produkcji 1, bez graczy i dodatkowych surowców: stare tempo osiągnęło 240 kolonii (40 w każdej galaktyce); nowe 36 (6 w każdej galaktyce). To porównanie scenariusza, nie prognoza świata z graczami.
