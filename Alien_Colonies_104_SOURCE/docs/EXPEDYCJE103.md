# Alien Colonies 103 — 0.12.36

Baza ekspedycyjna jest wspólna dla wszystkich trzech ras. Koszt pierwszego poziomu: 4000 metalu, 6000 kryształów i 2000 paliwa; wymaga stoczni 3 i laboratorium 4. Zajmuje zwykłe pole budowlane. Kolejne poziomy korzystają ze standardowego skalowania kosztów i czasu budynków.

W zakładce Flota wybierz **Ekspedycja**, dodaj przynajmniej jednego zwiadowcę, transportowce dla ładowności i okręty bojowe dla ochrony. Wybierz 1, 3 lub 6 rzeczywistych godzin poszukiwań. Wycena pokazuje paliwo, czas dolotu i przewidywany powrót, uwzględniający poszukiwania i oba loty.

Limit jest wspólny dla imperium i zależy od najwyższego poziomu posiadanej bazy: poziomy 1–5 pozwalają na jedną ekspedycję, 6–10 na dwie, 11–15 na trzy, dalej analogicznie. Powracająca flota nadal zajmuje miejsce. Ekspedycje mają osobny limit od ośmiu zwykłych misji. Premia do znalezisk zależy od bazy w kolonii startowej: każdy poziom powyżej pierwszego daje +5%.

Losowanie przy starcie: surowce 50%, porzucone statki 10%, pusto 20%, patrol Roju 10%, opóźnienie 10%. Opóźnienie dodaje połowę wybranego czasu poszukiwań, po czym flota wraca bez znalezisk. Losowanie i parametry są przechowywane przez serwer i zachowują się po restarcie.

Udane znalezisko surowców to, dla każdego surowca osobno, `floor(0,5 × godzinowa produkcja kolonii × godziny poszukiwań × (1 + 0,05 × (poziom bazy − 1)))`. Produkcja i premia są zapamiętywane przy starcie. Przykład: 1000/600/300 na godzinę, 3 godziny i baza 5 dają 1800/1080/540. Ładunek jest proporcjonalnie ograniczony ładownością. Porzucone statki należą do rasy gracza i wyłącznie do odblokowanych typów; ich łączna wartość nie przekracza budżetu znaleziska, maksymalnie 10 jednostek. Przy zbyt małym budżecie odzyskiwane są surowce.

Patrol korzysta ze zwykłych sześciu jednoczesnych rund, technologii, cech ras i regeneracji. Jego siła rośnie co pięć poziomów bazy. Zwycięstwo daje **25% szansy na jeden Kryształ Roju** oraz drobny łup surowcowy. Kryształ zajmuje jednostkę ładowności. Utrata floty oznacza utratę łupu. Spotkanie z patrolem nie zmienia prawdziwych kolonii Roju ani nie przyznaje premii za zniszczenie gniazda.

Surowce, odzyskane statki i Kryształy Roju zostają dostarczone po lądowaniu. Można zawrócić flotę przed końcem poszukiwań: bez znalezisk i bez zwrotu paliwa. Polecenia oraz lądowanie są zabezpieczone przed podwójnym rozliczeniem.

Maksymalny poślizg przewijania zwiększono o 25%: limity prędkości z 4 do 5 wysokości/szerokości widoku na sekundę oraz długości poślizgu z 4,5 do 5,625 długości gestu. Hamowanie, progi krótkich gestów, blokada osi i zatrzymanie po nowym dotknięciu pozostają zachowane.

Zachowano poprawkę wysokości przycisków z wersji 102, kolory flot zgodne z legendą oraz łagodny kolor zwiadu. Ekspedycje mają dodatkowy fioletowy kolor strzałki i identyczny kolor w legendzie. Nowy interfejs, grafika i komunikaty są dostępne po angielsku, polsku, niemiecku, hiszpańsku i francusku.

Kontrola wydania obejmuje rzeczywisty silnik serwera, restart SQLite, rozliczanie nagród, przeglądarkę z lokalnym serwerem i rozpakowane zasoby faktycznego AAB. Nie jest to test instalacji na fizycznym telefonie ani publikacji w Google Play. AAB należy podpisać dotychczasowym kluczem przez PODPISZ_AAB_103.cmd. Wersja: kod 103, nazwa 0.12.36. Nie zmieniono minimum wersji w Google Play ani nie wykonano resetu świata.
