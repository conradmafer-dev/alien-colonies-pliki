# Technologie i okresowy tunel — zasady 0.8.0

## Widok telefonu i drzewko

Logiczna szerokość pozostaje oparta na 720 px. Ekran wyższy niż 16:9 rozszerza
obszar gry w pionie zamiast ucinać dolną część. Wielkość przycisków nie rośnie
z samą wysokością ekranu. Nawigacja pozostaje przy dolnej krawędzi; zawartość
zakładek i szczegóły są przewijane, z uwzględnieniem bezpiecznych marginesów.

Drzewko ma trzy kolumny, osiem rzędów i 21 węzłów dla każdej rasy: 15 wspólnych,
dwa dotychczasowe podstawowe i cztery dotychczasowe rasowe. Linie odpowiadają
rzeczywistym zależnościom badań. Zaznaczenie podświetla drogę do wybranego węzła.
Dotknięcie węzła pokazuje pełne wymagania, koszt, czas i efekt. Wszystkie
wymagania muszą być ukończone równocześnie; badanie w toku jeszcze nie wystarcza.
Budynki wymagane przez badanie muszą istnieć na wybranej kolonii. Badania są
wspólne dla imperium; nadal może trwać tylko jedno badanie w całym imperium.

## Nowe badania

Zwykłe nowe technologie mają 12 poziomów. Projekt Sfery i Teoria tuneli mają
po jednym poziomie. Koszty w tabeli dotyczą pierwszego poziomu (metal / kryształ /
paliwo); kolejne poziomy stosują dotychczasowy wzrost kosztów gry. Czas i koszty
w interfejsie zawsze pochodzą z serwera. Cztery badania rasowe zachowują swoje
identyfikatory, efekty i limit pięciu poziomów.

| Badanie | Ukończone wymagania | Koszt poziomu 1, M / K / P | Efekt |
|---|---|---|---|
| Energetyka | Laboratorium 1 | 360 / 500 / 150 | Zwiększa moc elektrowni o 6% na poziom. |
| Informatyka | Laboratorium 1 | 400 / 600 / 200 | Zwiększa szybkość badań o 5% na poziom. |
| Synteza jądrowa | Energetyka 3, Laboratorium 3 | 850 / 900 / 400 | Zwiększa moc elektrowni o 4% na poziom. |
| Robotyka | Informatyka 3, Laboratorium 3 | 1 000 / 750 / 300 | Zwiększa szybkość budowy budynków o 4% na poziom. |
| Nadprzewodniki | Synteza jądrowa 3, Informatyka 4, Laboratorium 4 | 1 400 / 2 100 / 700 | Zmniejsza zużycie energii przez kopalnie o 2% na poziom. |
| Nanotechnologia | Robotyka 5, Laboratorium 5 | 2 300 / 1 900 / 900 | Zwiększa wydobycie wszystkich zwykłych surowców o 3% na poziom. |
| Fizyka nadprzestrzeni | Napęd 5, Informatyka 4, Laboratorium 5 | 1 600 / 2 500 / 1 300 | Zwiększa szybkość zwykłych lotów o 4% na poziom. |
| Kolektory gwiezdne | Nadprzewodniki 6, Laboratorium 6 | 3 500 / 4 200 / 1 600 | Zwiększa moc elektrowni o 4% na poziom i prowadzi do inżynierii gwiezdnej. |
| Inżynieria orbitalna | Nanotechnologia 4, Napęd 6, Laboratorium 6 | 5 000 / 3 500 / 1 800 | Zwiększa szybkość budowy statków i obrony o 4% na poziom. |
| Kontrola grawitacji | Fizyka nadprzestrzeni 5, Energetyka 6, Laboratorium 7 | 4 000 / 6 500 / 2 400 | Zmniejsza zmienną część kosztu paliwa o 2% na poziom. Stała opłata międzygalaktyczna pozostaje. |
| Inżynieria gwiezdna | Kolektory gwiezdne 8, Synteza jądrowa 8, Laboratorium 8 | 8 500 / 11 000 / 4 000 | Zwiększa ładowanie i moc Sfery Dysona o 4% na poziom. |
| Megastruktury | Inżynieria orbitalna 6, Nanotechnologia 6, Laboratorium 8 | 13 000 / 10 000 / 5 000 | Każdy poziom zwiększa szybkość budowy megastruktur o 5% i pojemność ich magazynu energii o 8%. |
| Stabilizacja czasoprzestrzeni | Kontrola grawitacji 6, Informatyka 8, Laboratorium 8 | 10 000 / 16 000 / 7 000 | Zmniejsza koszt otwarcia, podtrzymania i transferu przez tunel o 3% na poziom. |
| Projekt Sfery Dysona | Inżynieria gwiezdna 8, Megastruktury 8, Laboratorium 10 | 120 000 / 250 000 / 80 000 | Odblokowuje cztery etapy budowy Sfery Dysona wokół gwiazdy kolonii. |
| Teoria tuneli | Megastruktury 10, Stabilizacja czasoprzestrzeni 8, Projekt Sfery Dysona 1, Laboratorium 12 | 200 000 / 400 000 / 160 000 | Odblokowuje budowę Tunelu czasoprzestrzennego przy ukończonej Sferze Dysona. |

## Sfera Dysona

Jedna Sfera i jedna brama przypadają na imperium. Rozpoczęcie pierwszego etapu
wiąże projekt z gwiazdą wybranej kolonii. Operacje budowy i tunelu wykonuje się
z tej kolonii. Etapy powstają kolejno w osobnej kolejce megastruktur, niezależnej
od zwykłej kolejki kolonii. Każdy etap zamawia się osobno. Anulowanie aktywnego
etapu zwraca faktycznie zapłacone surowce; ukończone etapy pozostają.

Wymagania budowy każdego etapu: Projekt Sfery Dysona 1, stocznia 8 i elektrownia 8.
Wymagania bramy: ukończony etap 4 Sfery, Teoria tuneli 1, stocznia 10 i laboratorium 12.

| Etap | Metal | Kryształ | Paliwo | Bazowy czas |
|---|---:|---:|---:|---:|
| Fundament orbitalny | 125 000 | 80 000 | 25 000 | 6 h |
| Pierścień kolektorów | 500 000 | 300 000 | 100 000 | 18 h |
| Sieć kolektorów | 1 500 000 | 900 000 | 250 000 | 48 h |
| Ukończona Sfera Dysona | 4 000 000 | 2 500 000 | 750 000 | 120 h |
| Tunel czasoprzestrzenny | 2 500 000 | 4 000 000 | 1 200 000 | 72 h |

Budowa Sfery i bramy łącznie: **8 625 000 metalu, 7 780 000 kryształu i
2 325 000 paliwa**, bez badań i budynków wymaganych do odblokowania.
Czas budowy = czas bazowy / PGR_SPEED / (1 + 0,05 × poziom Megastruktur),
zaokrąglony w górę do pełnych sekund. Czas jest ustalany przy zleceniu;
zwiększenie premii nie przelicza trwającej budowy.

| Ukończony etap Sfery | Dodatkowa moc kolonii | Ładowanie energii / s | Magazyn energii |
|---|---:|---:|---:|
| 1 | 2 000 | 400 | 25 000 000 |
| 2 | 10 000 | 1 500 | 100 000 000 |
| 3 | 40 000 | 6 000 | 350 000 000 |
| 4 | 120 000 | 20 000 | 1 200 000 000 |

Inżynieria gwiezdna zwiększa moc i ładowanie o 4% na poziom. Megastruktury
zwiększają pojemność magazynu o 8% na poziom. Magazyn energii tunelu jest
oddzielny od bieżącego bilansu mocy kopalń. Pełna Sfera dostarcza moc centrum
projektu i ładuje magazyn. Ładowanie używa rzeczywistego czasu, także offline.

## Okresowy Tunel czasoprzestrzenny

1. W centrum projektu wybierz w zakładce Flota jedną planetę docelową.
2. Otwórz tunel: 60 s stabilizacji, następnie 300 s na wysyłanie flot.
3. Włącz Podróż przez tunel, wybierz misję i statki, sprawdź trasę i wyślij.
4. Możesz wysłać kilka flot w tym samym oknie, jeśli wystarcza energii.
5. Zamknięcie okna kończy możliwość nowych wysyłek. Opłacone powroty pozostają.

Cel może być dowolną istniejącą planetą w dowolnej galaktyce, poza własnym
centrum projektu. Cel nie wymaga bramy. Zmiana celu wymaga zamknięcia bieżącego
okna i opłacenia nowego otwarcia. Początkowo jest jeden projekt końcowy; dane
badań i osobna kolejka pozwalają rozwijać system w kolejnych wydaniach.

Przelot w jedną stronę trwa **120 sekund rzeczywistych**, niezależnie od
odległości i prędkości serwera. Obrońca otrzymuje dotychczasowe ostrzeżenie
nadchodzącego ataku. Ochrona początkujących i wymagania misji nadal obowiązują.
Tunel zastępuje koszt paliwa kosztem energii. Nie zmienia wyniku walki.

Bazowe parametry przed premią Stabilizacji czasoprzestrzeni:

| Operacja | Energia |
|---|---:|
| Otwarcie | 50 000 000 |
| Podtrzymanie, także podczas stabilizacji | 1 000 000 / s |
| Transfer w jedną stronę | 250 000 × masa floty |
| Dodatkowy impuls umożliwiający powrót | 85 000 000 |

Masa = suma bazowej wytrzymałości kadłubów danej rasy / 10 + suma ładunku / 1000.
Premie do kadłuba nie zwiększają masy. Stabilizacja czasoprzestrzeni obniża
wszystkie te koszty o 3% na poziom (24% przy wymaganym poziomie 8, do 36% na 12).

Przy otwarciu serwer wymaga energii na opłatę otwarcia i całe 360 s podtrzymania,
uwzględniając ładowanie Sfery. Opłatę otwarcia pobiera od razu, podtrzymanie
rozlicza wraz z upływem czasu. Przed wysłaniem floty zachowuje zapas na resztę
okna, a następnie pobiera transfer w obie strony oraz impuls powrotny.
Rezerwa powrotu jest przypisana do floty i przetrwa zamknięcie okna oraz restart.
Nie trzeba pozostawać zalogowanym. Ręczne zamknięcie zatrzymuje dalszy pobór
podtrzymania; ponowne otwarcie wymaga nowej opłaty i stabilizacji.

Przykład przy minimalnych badaniach końcowych: Inżynieria gwiezdna 8,
Megastruktury 10 i Stabilizacja czasoprzestrzeni 8 dają pojemność 2,16 mld,
ładowanie 26 400/s, otwarcie 38 mln i podtrzymanie 760 000/s. Samo otwarcie
pełnego okna wymaga **302 096 000 energii**, a wysyłanie flot dodatkowej energii.
To parametry pierwszego wdrożenia; testy nie stanowią pomiaru tempa całego sezonu
ani bilansu PvP na długo działającym serwerze.

## Aktualizacja i sprawdzenie

Migracja z 0.7.8 dopisuje nowe badania od poziomu 0 i stan projektu. Zachowuje
zdobyte wcześniej poziomy. Zdobyte poziomy nie są odbierane, nawet jeśli nowa
zależność nie jest jeszcze spełniona; dalsza rozbudowa wymaga nowych warunków.
Zwykłe, już rozpoczęte kolejki i loty zachowują dotychczasowe terminy.

Pełna instrukcja: `START_TUTAJ.txt`. Wyniki testów: `VERIFICATION_080.json`.
Zrzuty w `docs/verification_080/` pochodzą z Godota i danych testowych, a nie
z działającego konta gracza. Nie wykonano APK/AAB ani testu fizycznego Androida.
