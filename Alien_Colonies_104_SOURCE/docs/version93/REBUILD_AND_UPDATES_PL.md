# Alien Colonies Android 93 / 0.12.26

Wersja odtworzona z pelnego projektu91 i zapisanej aktualizacji92. Android93 nie
byl opublikowany w Google Play przed odtworzeniem. Kod93 moze byc zbudowany ponownie
z kompletnego folderu projektu, lacznie z grafikami, dodatkami i kodem natywnym.
Gra zachowuje ten sam identyfikator pakietu i wymaga dotychczasowego klucza przesylania.

## Odtworzenie pelnych zrodel

Paczka aktualizacji zawiera `Alien_Colonies_93_SOURCE_PATCH.zip` oraz pelny manifest
SHA-256. `02_AKTUALIZUJ_ZRODLA_93.cmd` tworzy nowy kompletny folder projektu93 z
zachowanej bazy91 (ZIP, folder lub trzy pliki `AC_91_ZRODLA_*.bin`). Mozna tez
uzyc kompletnego folderu92. Kazdy odtworzony plik jest sprawdzany. Stara baza zostaje.

Zachowana baza91 na Dysku Google:
https://drive.google.com/drive/folders/1q8YV2KdaXFURkETbO4ibnnA0lGhPsA2X

## Budowanie Androida

- Godot4.5.1, Java JDK17+, oficjalne szablony eksportu4.5.1.
- Zainstaluj szablon Androida w projekcie i uruchom
  `python tools/configure_android_build.py`.
- Android SDK: platforma36, build-tools36.0.0, platform-tools; Gradle8.11.1,
  Android Gradle Plugin8.10.1. Godot moze pobrac potrzebny NDK28.1.13356709.
- Profil `Google Play AAB` tworzy unsigned AAB z kodem93 i nazwa0.12.26.
- Dodatki AAR sa dolaczone w `addons`; ich pelne zrodla i wrappery Gradle sa w
  `tools`. `android_updates_source` buduje most `AlienUpdates` przez
  `gradlew assembleDebug assembleRelease`. Zaleznosc: oficjalne
  `com.google.android.play:app-update:2.1.0`.

## Pasek aktualizacji

Przed logowaniem mala scena `boot.tscn` sprawdza pliki graficzne i Google Play.
Pliki wykonywalne aplikacji sa instalowane przez oficjalny mechanizm Play
wewnatrz gry, po zgodzie gracza. Pierwszy Android93 trzeba podpisac i opublikowac
dotychczasowa droga. Nie ma instalowania APK z serwera.

Publiczny manifest grafiki: `/play/content/manifest.json`, schema1, `min_client`,
`max_client`, `packs`. Kazda paczka ma `id`, `url` w obrebie `/play/content/`
tego samego serwera, `size`, `sha256`, `files` z polami `path`, `size`, `sha256`.
Na obecnym serwerze lista paczek jest pusta, wiec nie pobiera ponownie grafik.

`python tools/make_asset_update.py --id icons-1 --origin https://aliencolonies.com
--out backend/web/play/content/packs client/assets/example.png` przygotowuje
paczke po zaimportowaniu zmienionej tekstury w Godot. Dozwolone sa tylko obrazy,
ich mapowania `.import` i `.ctex`. Nie sa dozwolone skrypty, sceny ani biblioteki.
Suma i rozmiar sa sprawdzane dla ZIP oraz kazdego pliku; lista centralna ZIP jest
sprawdzana przed rozpakowaniem. Nieudany nowy zestaw nie zastapi poprzedniego.
Niezmienione, sprawdzone paczki pozostaja w pamieci podrecznej.

## Walidacja odtworzonej wersji

- 561 sprawdzen prawdziwego interfejsu Godot: 5 jezykow, 3 rozmiary okna,
  miejsca1/13/30/50/51/113, powtarzane skoki, kolory ras, bezwladne przewijanie.
- 139 testow regresji floty; 19 testow aktualizacji grafiki przez lokalny HTTP.
- 5 testow transakcji zmiany nazwy, 14 testow serwerowego rankingu, 3 testy
  znacznikow rankingu przegladarki.
- Porownanie30 prob tego samego stanu: mediana odswiezania65.46ms (92) i13.02ms
  (93) w desktopowym silniku headless. To pomiar pracy UI, nie liczba FPS telefonu.
- Fizyczny Android i rzeczywiste pobieranie kolejnej wersji z Play wymagaja
  sprawdzenia na urzadzeniu po publikacji93.

Serwer i przegladarka pozostaja na zapisanym wdrozeniu93. Nie wykonywano resetu
kont ani swiata. Polityka wymaganej wersji klienta nie jest podnoszona przed
opublikowaniem nowego wydania w Google Play.
