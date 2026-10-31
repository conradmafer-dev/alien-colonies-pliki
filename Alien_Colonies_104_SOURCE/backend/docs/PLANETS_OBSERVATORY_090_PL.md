# Planety i obserwatorium — 0.9.0

## Planety i sloty

Nowy świat ma 180 układów po 1–5 planet (532 planety przy obecnym ziarnie).
Liczba, orbity, typ i wielkość są deterministyczne. Warunki fizyczne są zapisane
przy pierwszym utworzeniu lub migracji i pozostają po zmianie właściciela.

| Wielkość | Sloty |
|---|---:|
| Mała | 48–64 |
| Średnia | 66–84 |
| Duża | 86–104 |
| Olbrzymia | 106–120 |

Każdy ukończony poziom budynku zajmuje **1 slot**, także pierwszy poziom,
budynki rasowe i obserwatorium. Laboratorium na poziomie 4 zajmuje więc 4 sloty.
Rozpoczęte ulepszenie rezerwuje kolejny slot. Ukończenie zmienia rezerwację
w zajęty slot; anulowanie zwalnia rezerwację wraz z dotychczasowym zwrotem kosztu.
Brak miejsca blokuje budowę po stronie serwera. Badania, statki i obrona
nie zajmują slotów. Kosmiczna Sfera Dysona i projekt tunelu również ich nie zajmują.

Nowa planeta startowa jest wybierana spośród wolnych dużych lub olbrzymich,
jeśli są dostępne. Zwykły start ma 6 zajętych slotów, nowa kolonia 4.
Rój także respektuje pojemność planet przy rozbudowie. W tej wersji nie ma
terraformowania ani rozbiórki budynków; warto zostawić miejsce na specjalizację.

## Typy i wydobycie

Mnożniki zmieniają rzeczywistą godzinową produkcję zasobów. Łączą się z premiami
rasy, badań i budynków; niedobór energii nadal ogranicza produkcję. Katalog
kopalni pokazuje wynik uwzględniający warunki wybranej planety.
**100%** oznacza zwykłe wydobycie przed pozostałymi premiami.

| Typ | Metal | Kryształ | Paliwo | Strefa |
|---|---:|---:|---:|---|
| Ognista | 150% | 100% | 50% | Najbliższa |
| Obsydianowa | 115% | 145% | 40% | Najbliższa |
| Metaliczna | 165% | 85% | 50% | Gorąca |
| Pustynna | 130% | 110% | 60% | Gorąca |
| Skalista | 145% | 95% | 60% | Gorąca |
| Oceaniczna | 85% | 90% | 125% | Umiarkowana |
| Organiczna | 75% | 90% | 135% | Umiarkowana |
| Koralowa | 80% | 115% | 105% | Umiarkowana |
| Krystaliczna | 65% | 170% | 65% | Chłodna |
| Zmierzchowa | 90% | 130% | 80% | Chłodna |
| Burzowa | 85% | 110% | 105% | Chłodna lub zewnętrzna |
| Lodowa | 75% | 80% | 145% | Zewnętrzna |

Układ wybiera obsadzone orbity spośród pięciu stref. Średnie odległości wynoszą
0,35 / 0,75 / 1,15 / 2,2 / 4,5 AU, z odchyleniem do 8%; temperatury to
350 / 140 / 20 / −75 / −160°C, z odchyleniem do 10°C. Nie każdy układ
musi zawierać każdą strefę: pojedyncza planeta może krążyć daleko od gwiazdy.
Wielkość jest niezależna od typu. To uproszczony model gry, a wartości produkcji
stanowią początkowy balans, wymagający obserwacji w dłuższej rozgrywce.

Wykorzystano wszystkie 12 istniejących par grafik planety i kolonii.
Grafika jest teraz związana z rzeczywistym typem planety, także dla kolonii Roju.

## Obserwatorium i mgła wojny

Początkowo mapa pokazuje położenie nieznanych układów oraz własne kolonie.
Nie pokazuje ukrytych właścicieli, liczby planet, budynków ani podsumowań
pozwalających odtworzyć te dane. Własna kolonia nie odkrywa automatycznie
pozostałych planet swojego układu. Są one widoczne po zwiadzie lub budowie
obserwatorium. Ukryte dane są filtrowane przez serwer.

Obserwatorium jest wspólnym budynkiem każdej rasy, wymaga laboratorium
na poziomie 2 i ma maksymalnie 12 poziomów. Bazowy koszt pierwszego poziomu:
800 metalu, 1200 kryształu, 300 paliwa; czas przed modyfikatorami: 10 minut.
Wymagania i koszty są widoczne w szczegółach budynku. Rasowe nazwy laboratoriów
pozostają, np. laboratorium Zetan nazywa się „Obserwatorium psioniczne”.
Osobny budynek Obserwatorium odpowiada za widoczność mapy. Dotychczasowe
rasowe efekty zwiadowcze nie zastępują jego zasięgu.

| Poziom | Właściciele i typy — układy w każdą stronę | Budynki — układy w każdą stronę |
|---:|---:|---|
| 0 | Brak obserwacji | Brak |
| 1–2 | 1 | Brak |
| 3–4 | 2 | Brak |
| 5 | 3 | Brak |
| 6 | 3 | Tylko własny układ |
| 7 | 4 | Tylko własny układ |
| 8 | 4 | 1 |
| 9 | 5 | 1 |
| 10 | 5 | 2 |
| 11 | 6 | 2 |
| 12 | 6 | 3 |

Zasięg liczy sąsiednie układy wzdłuż pierścienia mapy, w obie strony,
z połączeniem ostatniego układu z pierwszym. Zawsze obejmuje też własny układ.
Na przykład poziom 1 pokazuje trzy układy, a poziom 12 trzynaście.
Obserwacja budynków ma osobny, krótszy zasięg. Informacje odświeżają się przy
kolejnych aktualizacjach stanu gry, także gdy szczegóły planety są otwarte.

Zasięgi wszystkich własnych obserwatoriów sumują się jako wspólny obszar
widoczności. Każde działa **wyłącznie w galaktyce swojej kolonii**. Nie obserwuje
sąsiedniej ani wybranej na ekranie obcej galaktyki. Kolonia w nowej galaktyce
może zbudować własne obserwatorium i zapewniać lokalne dane, zgodnie z wybranym
wariantem mechaniki. Samo przełączenie galaktyki w interfejsie niczego nie odkrywa.

Podstawowa obserwacja pokazuje właściciela i typ z grafiką. Pełne warunki
fizyczne, pojemność i mnożniki poznajesz po zwiadzie układu albo w zasięgu
zaawansowanej obserwacji. Obserwacja budynków podaje ich aktualne poziomy,
ale nie ujawnia aktualnych zapasów, floty ani obrony.

## Zwiad

Nieznany układ ma przycisk „Zbadaj układ”, prowadzący do istniejącego formularza
misji zwiadowczej. Nadal obowiązują koszty, czas podróży i ograniczenia lotów
między galaktykami. Inne misje wymagają najpierw poznania planety.

Przylot zwiadu zapisuje jednorazowy obraz właścicieli i typów całego układu
oraz szczegółowy raport o wskazanej planecie: budynkach, zasobach, flocie
i obronie. Raport zawiera czas obserwacji. Poza zasięgiem obserwatorium
pozostaje historyczny i nie aktualizuje się sam. Zmiany właściciela, budynków
lub zasobów nie nadpisują starego raportu. W aktywnym zasięgu właściciel i typ
są aktualne; budynki są aktualne tylko w krótszym zasięgu. Zasoby i siły wroga
nadal wymagają zwiadu. Po utracie obserwatorium obowiązuje zachowany zwiad,
a bez niego obcy układ ponownie jest nieznany.

## Migracja istniejącego świata

Przed pierwszą migracją wykonywana jest kopia zgodnie z istniejącym systemem
kopii bazy. Aktualizacja z 0.8.0 nie wywołuje resetu świata. Zachowuje konta,
kolonie, poziomy, zasoby, czat, flotę, terminy rozpoczętych kolejek oraz
megastruktury. Nowe mnożniki obowiązują od migracji; nie zmieniają wstecz
produkcji naliczonej za wcześniejszy czas offline.

Zmniejszanie liczby planet dotyczy wyłącznie całkowicie pustych światów,
bez zasobów, statków, obrony, poziomów i kolejek. Zajęte planety, punkty
startowe, cele i początki trwających lotów oraz zapisane cele zwiadu są chronione.
To może pozostawić w starym układzie więcej planet niż przewiduje generator
dla nowego świata; nadal najwyżej pięć. Dodawane planety uzupełniają większe układy.
Istniejąca kolonia otrzymuje co najmniej tyle slotów, ile zajmują jej poziomy,
rezerwacje i 8 dodatkowych, gdy naturalna pojemność jest zbyt mała.
Ten wyjątek może podnieść pojemność ponad 120; nie przerabia ukończonych budynków.

Warunki planet i zapisany zwiad przetrwają restart. Obserwatoria rozpoczynają
na poziomie 0. Dawna publiczna mapa nie jest zamieniana na fikcyjne raporty.
Rzeczywiście zapisane wcześniejsze zwiady Roju pozostają dostępne.

Instrukcja instalacji: `../START_TUTAJ.txt`. Weryfikacja: `../VERIFICATION_090.json`.
