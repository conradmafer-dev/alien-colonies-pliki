# Sprawdzenie wersji 98

Silnik: Godot 4.5.1 stable f62fdbde1. Testy interfejsu są uruchamiane na komputerze
bez wyświetlacza, z zasobami wyjętymi z gotowego AAB i jego `assets.sparsepck`.
Nie ma tu testu wydajności GPU ani odczucia gestu na fizycznym telefonie.

## Wyniki

| Test | Sprawdzenia | Wynik |
| --- | ---: | --- |
| Pęd, małe ruchy, kierunki, hamowanie, zagnieżdżone osie, przyciski | 136 | PASS |
| Duży stan, worker JSON, odłożenie widoku, spóźnione odpowiedzi | 22 | PASS |
| Rzeczywisty lokalny HTTP GET i POST, bez powtórzenia polecenia | 12 | PASS |
| Ranking, trzy rasy, pięć języków, cztery rozmiary i My position | 1024 | PASS |
| Nawigacja floty, wyceny i wysyłanie | 139 | PASS |
| Okno oceny i bariera dotyku, pięć języków i trzy rozmiary | 270 | PASS |
| Start przez właściwy indeks Androida | 15 | PASS |
| Rekordy indeksu Androida, rozmiary i MD5 | 638 | PASS |
| 900 tekstów w pięciu językach i zgodne parametry tłumaczeń | 900 | PASS |

`bundletool validate` przyjął gotowy AAB. CRC archiwum zgodne.

## Porównanie

Zwykły kontroler Godot 4.5.1, dwa zdarzenia ruchu o łącznym przesunięciu 15:
około 109 dodatkowych jednostek przy 30 FPS, 412 przy 60 FPS i 1627 przy 120 FPS.
Nowy kontroler nie nadaje pędu po takim mikroruchu. Dla celowego ruchu 60
jednostek dalszy ruch wynosi 73,28–73,46 przy 30/60/90/120 FPS, w obu osiach
i trzech skalach ekranu. Jednostki te opisują logiczny widok, nie fizyczne mm.

Ten sam zestaw danych 701356 bajtów i ten sam komputer:

| Praca na głównym wątku | Wersja 97, mediana | Wersja 98, mediana |
| --- | ---: | ---: |
| Callback odpowiedzi stanu | 13,539 ms | 0,042 ms |
| Okresowy tick podczas dotyku | 0,6325 ms | 0,105 ms |

Dekodowanie nadal wymaga czasu CPU, ale wykonuje je worker. To pomiary pracy
callbacków na komputerze, a nie czas całego żądania ani FPS telefonu.
Surowe wartości są w `scroll_benchmark97_98.json`.

## Odtworzenie

1. Zweryfikuj AAB: `python tools/check_android_resource_index.py PLIK.aab`.
2. Wypakuj `assetPackInstallTime/assets/` do osobnego katalogu ASSETS, zachowując
   ścieżki. Umieść w nim także katalog `tests/` z tego projektu i
   `backend/tests/fixtures/android_0112.json`. Nie zastępuj `project.binary`
   ani `assets.sparsepck`.
3. Przykładowy test pędu:

```sh
godot --headless --emulate-touchscreen --path ASSETS --main-pack ASSETS/assets.sparsepck --script /pełna/ścieżka/tests/scroll98.gd
```

Testy `refresh98.tscn`, `ranking98.tscn`, `android_fleet87_regression.tscn` i
`review94.tscn` podaj zamiast argumentu `--script ...`, jako `res://tests/PLIK.tscn`.
Okno oceny testuj także z `--emulate-touchscreen`.
Test startu: `--script /pełna/ścieżka/tests/android_sparse_startup98.gd`.
Każdemu przebiegowi daj osobny katalog danych użytkownika, aby poprzednia
sesja lub ustawienia nie wpływały na wynik.

Rzeczywista komunikacja z lokalnym serwerem testowym:

```sh
python tools/check_scroll_network98.py --godot /pełna/ścieżka/godot --android-assets ASSETS
python tools/check_client_translations.py
```

Test rankingu czeka na zastosowanie odpowiedzi po barierze gestu. Test z 97
zakładał natychmiastową odpowiedź; jego sprawdzenia układu zostały zachowane.

## Ręczna kontrola na telefonie

Sprawdź powolne przesunięcie, krótki ruch, mocniejszy gest, zatrzymanie palca
przed puszczeniem, zmianę kierunku i zatrzymanie drugim dotknięciem. Powtórz na
kartach budynków, flocie, rankingu i raportach. Przy aktywnym odświeżaniu serwera
zwróć uwagę na płynność obrazu oraz poprawność liczników. To ostatni etap,
którego nie dało się zweryfikować w dostępnym środowisku.
