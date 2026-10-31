# Alien Colonies 100 / 0.12.33

Galaktyki wracaja do dawnych kompozycji i kolorow. Srednia jasnosc nowych grafik wynosi ok. 89% starej referencji. Kazda ma 3840 × 2560 pikseli, a drobne struktury pochodza z dziewieciu nakladajacych sie wygenerowanych kafelkow. Obszary czarnych dziur w Eclipse i Void sa mniejsze, z zachowaniem miejsca dla wewnetrznych ukladow. Szesc pierscieni / 155 ukladow na galaktyke pozostaje bez zmian.

Przewijanie zachowuje probkowanie czasu gestu, dominujaca os i blokowanie przypadkowych klikniec. Ped ustawiono pomiedzy wersjami 97 i 98: decay 4.2, limit 4 wysokosci widoku/s, maksymalny dobieg 4.5 dlugosci gestu, prog rozpedzenia 14 pikseli. Drobny gest nie powinien powodowac skoku o pol planszy. Warstwa ruchu flot jest osobna, a geometria szlakow buforowana — przesuwanie nie przelicza orbit przy kazdym ruchu palca.

Po potwierdzonym wyslaniu floty otwiera sie pelna mapa galaktyki. Widoczne sa wlasne wyslane floty, z polozeniem wynikajacym z started_at, arrives_at, czasu serwera oraz odleglosci kolejnych odcinkow zapisanej trasy. Powrot biegnie ta sama droga w odwrotnej kolejnosci, a wczesne odwolanie zaczyna sie w faktycznym punkcie zawrocenia. Flota obronna pozostaje przy celu w czasie postoju. Loty miedzy galaktykami i tunele maja oznaczone przejscia; starsze loty bez zapisanej trasy maja linie przerywana. Ruch animuje tylko nakladka do 30 Hz; nie odswieza calego katalogu gry ani nie zmienia logiki lotu.

Raporty otrzymuja 14 odrebnych ikon wedlug stabilnej kategorii z serwera. Kategoria starych raportow wynika z danych przed tlumaczeniem; ustawiony jezyk nie zmienia rozpoznania typu. Rozne ikony obejmuja zwiad, bitwe, ostrzezenie, transport, powrot, kolonizacje, badania, budowe, obrone, stocznie, umiejetnosc, ochrone, imperium i recykling.

## Sprawdzenie

VALIDATION100.json oraz android_*_report.json opisują testy gotowych zasobow Androida. Szesc skompilowanych tekstur jest pikselowo zgodnych z bezstratnymi masterami PNG. DEPLOYMENT100_RESULT.json zawiera odczyt kontrolny serwera i plikow web. Pomiary wydajnosci sa z komputera; pakiet wymaga jeszcze podpisu wlasciciela i sprawdzenia na rzeczywistym telefonie.

## Publikacja Androida

Rozpakuj MINI dla oryginalnego niepodpisanego AAB99 albo pelna paczke dla AAB91–98. Uruchom 01_AKTUALIZUJ_AAB_100.cmd i wskaz swoj oryginalny niepodpisany AAB. Nastepnie uruchom PODPISZ_AAB_100.cmd i wybierz dotychczasowy klucz. Haslo jest odczytywane tylko lokalnie; certyfikat jest porownywany z poprzednim wydaniem. Podpisany AAB100 przeslij do Google Play.

MINI jest paczka dla autora odtwarzajaca AAB100; nie jest plikiem instalowanym przez gracza. Rozmiar aktualizacji dla gracza ustala Google Play na podstawie jego urzadzenia i zainstalowanej wersji. Polityki minimalnej/najnowszej wersji aplikacji nie przestawiono na 100 przed publikacja podpisanego wydania.

## Zrodla i grafiki

Pelny projekt zachowuje wszystkie pliki z kompletnej wersji99 i dodaje zmiany100. docs/version100/galaxy_art_source zawiera gotowe PNG 3840 × 2560 i bazy. Surowe 54 kafelki, dawne referencje, prompty i skrypty odtworzenia sa w osobnym archiwum grafik. Generacja uzywala wbudowanego image_gen.imagegen; skladanie wykonywal ImageMagick. To zlozenie wygenerowanych detali z zachowaniem dawnej kompozycji, a nie pojedynczy render natywny 4K. Katalogi robocze i prywatne klucze nie sa potrzebne do uzycia projektu.

Nie wykonano czyszczenia kont ani resetu swiata. Anulowany launcher czyszczenia pozostaje wylaczony.
