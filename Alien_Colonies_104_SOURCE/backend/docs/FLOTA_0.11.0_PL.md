# Flota i późna progresja — 0.11.0

Dane bazowe przed badaniami, umiejętnościami, premiami rasowymi i budynkami. Czas bazowy w sekundach przy tempie 1; rzeczywisty katalog pokazuje czas po wszystkich modyfikatorach. Paliwo to współczynnik jednostki, nie cena całej wyprawy.

| Rasa | Klasa / jednostka | Metal | Kryształy | Paliwo (budowa) | Czas bazowy, s | Atak | Kadłub | Ładownia | Wsp. paliwa | Prędkość |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| zetans | Pancernik — Strażnik Horyzontu | 14000 | 11500 | 3800 | 3300 | 850 | 2450 | 600 | 55 | 0.8 |
| zetans | Drednot — Kataklizm | 70000 | 82000 | 22000 | 18000 | 3800 | 10000 | 1800 | 210 | 0.48 |
| zetans | Okręt specjalny rasy — Pryzmat Osobliwości | 180000 | 280000 | 85000 | 54000 | 9500 | 22000 | 3500 | 420 | 0.65 |
| zetans | Tytan — Arka Zenitu | 1200000 | 1600000 | 550000 | 259200 | 48000 | 140000 | 15000 | 2300 | 0.3 |
| symbionts | Pancernik — Behemot | 14000 | 7800 | 6500 | 4290 | 700 | 4100 | 850 | 44 | 0.55 |
| symbionts | Drednot — Trawiciel Gwiazd | 74000 | 50000 | 45000 | 23400 | 3200 | 18000 | 2600 | 160 | 0.34 |
| symbionts | Okręt specjalny rasy — Matriarcha | 190000 | 140000 | 160000 | 70200 | 7500 | 40000 | 5000 | 330 | 0.38 |
| symbionts | Tytan — Prarodzic | 1300000 | 900000 | 950000 | 336960 | 40000 | 230000 | 22000 | 1800 | 0.2 |
| automatons | Pancernik — Dominator | 20500 | 8500 | 4900 | 3000 | 880 | 4650 | 750 | 82 | 0.5 |
| automatons | Drednot — Egzekutor | 110000 | 50000 | 28000 | 16200 | 4000 | 20000 | 2200 | 320 | 0.3 |
| automatons | Okręt specjalny rasy — Bastion Omega | 300000 | 135000 | 100000 | 48600 | 9000 | 46000 | 4200 | 600 | 0.3 |
| automatons | Tytan — Kolos Wieczności | 1900000 | 850000 | 650000 | 233280 | 50000 | 270000 | 18000 | 3600 | 0.18 |

## Warunki produkcji

Każdy statek wymaga również zapasów, wolnej kolejki stoczni i wybranej rasy. Poziomy badań są wspólne dla imperium, budynki i lokalna Sfera dotyczą kolonii budowy.

| Klasa | Wymagania |
|---|---|
| Pancernik | Stocznia 7; Konstrukcja okrętów liniowych 2; broń rasy (weapons) 5; Fizyka nadprzestrzeni 3 |
| Drednot | Stocznia 9; Konstrukcja okrętów liniowych 5; Uzbrojenie okrętów liniowych 3; Fizyka nadprzestrzeni 5 |
| Specjalny | Stocznia 10; rasowy budynek produkcyjny 4; projekt specjalny rasy 1; Fizyka nadprzestrzeni 6 |
| Tytan | Stocznia 12; Rdzeń tytana 1; Konstrukcja okrętów liniowych 8; Uzbrojenie okrętów liniowych 6; ukończona Sfera Dysona w tej kolonii |

Skrótowa ścieżka nie zastępuje pełnych zależności. W drzewku i szczegółach widoczne są wszystkie wcześniejsze badania oraz ich wymagane poziomy.

## Projekty i cechy rasowe

### Dowodzenie psioniczne — Pryzmat Osobliwości
Tylko Zetanie. Własna pierwsza salwa ×1,6, dodatkowo do premii rasy. Nie wzmacnia innych okrętów.
Projekt `psionic_command`: laboratorium 9, Konstrukcja okrętów liniowych 5, Uzbrojenie okrętów liniowych 3, `coherent_plasma` 3. Budynek rasowy potrzebny do produkcji statku: `quantum_foundry` 4.
Badanie ma tylko jeden poziom. Odblokowany projekt nie ogranicza produkcji do jednej sztuki.

### Suwerenność roju — Matriarcha
Tylko Symbionci. Po rundzie leczy 60% ran własnego ocalałego kadłuba. Nie wskrzesza strat ani nie leczy innych okrętów.
Projekt `brood_sovereignty`: laboratorium 9, Konstrukcja okrętów liniowych 5, Uzbrojenie okrętów liniowych 3, `corrosive_spores` 3. Budynek rasowy potrzebny do produkcji statku: `brood_chamber` 4.
Badanie ma tylko jeden poziom. Odblokowany projekt nie ogranicza produkcji do jednej sztuki.

### Autonomia oblężnicza — Bastion Omega
Tylko Automatony. Własny pancerz redukuje pozostałe obrażenia o 20% po premii rasy. Nie chroni innych okrętów.
Projekt `siege_autonomy`: laboratorium 9, Konstrukcja okrętów liniowych 5, Uzbrojenie okrętów liniowych 3, `siege_algorithms` 3. Budynek rasowy potrzebny do produkcji statku: `assembly_hub` 4.
Badanie ma tylko jeden poziom. Odblokowany projekt nie ogranicza produkcji do jednej sztuki.

## Badania wspólne

Konstrukcja okrętów liniowych: szybkość produkcji statków i obrony +3% na poziom (maks. 12).
Uzbrojenie okrętów liniowych: atak czterech nowych ciężkich klas +4% na poziom (maks. 12). Nie wzmacnia początkowych ośmiu klas.
Rdzeń tytana: jeden poziom; odblokowuje tytany i mnoży pojemność kondensatora Sfery x8. Nie tworzy energii. Wymagania: Projekt Sfery Dysona 1, Uzbrojenie okrętów liniowych 5, Kontrola grawitacji 6, Megastruktury 8, laboratorium 10.

## Cel końcowy

Rozwiń przemysł i badania gwiezdne, zaprojektuj i ukończ cztery etapy Sfery Dysona. Następnie wykorzystaj ją do produkcji tytanów oraz — po odpowiednich badaniach i budowie — podróży przez tunel. Są to powiązane, ale osobne odblokowania. Sam Rdzeń nie wymaga ukończenia fizycznej Sfery, jej ukończenie jest warunkiem produkcji tytana.
Tunel: stabilizacja 60 s, okno 300 s, transfer 120 s w jedną stronę. Otwarcie, utrzymanie, transfer i rezerwa powrotu zużywają energię. Zwykłe loty nadal kosztują paliwo; operacje sojuszu nadal korzystają wyłącznie ze zwykłego lotu.
Nowe mechaniki nie obniżają starych cen ani istniejących wymagań. Balans kosztów i skuteczności nowych hullów nie był jeszcze oceniony w wielodniowej rozgrywce PvP.

## Ilustracje

Pancerniki korzystają z istniejącej ilustracji krążownika danej rasy, a drednoty, jednostki specjalne i tytany z ilustracji jednostki oblężniczej. Te same prawidłowe klucze grafik otrzymują raporty bitew. To nie jest zestaw nowych obrazów.
