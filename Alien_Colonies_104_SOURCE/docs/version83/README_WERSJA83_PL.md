# Alien Colonies 0.12.16 — kod wersji 83

To kolejna wersja Androida oparta na odzyskanym projekcie 82. Numer Android versionCode to **83**, a versionName to **0.12.16**. Wersja 82 pozostaje zachowaną bazą historyczną.

## Zmiany w 83

- **36 nowych grafik statków:** każdy z 12 typów ma osobny projekt dla Zetan, Automatonów i Symbiontów. Sylwetki odzwierciedlają rolę: zwiad, transport, kolonizacja, eskorta, oblężenie i ciężkie jednostki.
- **Koszty megastruktur:** Sfera Dysona i tunel czasoprzestrzenny pokazują każdy brakujący surowiec na czerwono. Kolory aktualizują się wraz ze stanem zasobów; dokładnie wystarczająca ilość nie jest błędnie oznaczana jako niedobór.
- **Ekran przed logowaniem:** usunięto z grafiki napis o ludzkości, „Welcome Back” i narysowane obramowanie formularza. Zachowano logo oraz trzy rasy.
- **Logowanie:** obraz jest dopasowany w całości do ekranu. Rzeczywisty formularz ma czyste tło, bez wystających elementów drugiego panelu.
- **Podgląd floty:** miniatury w wyborze statków pokazują całe kadłuby.

Galeria wszystkich nowych grafik: [docs/STATKI_83.html](../STATKI_83.html). Otwórz ją po rozpakowaniu całego katalogu projektu.

## Dalsza edycja

1. Zainstaluj **Godot 4.5.1** i pasujące do niego szablony eksportu.
2. Zaimportuj znajdujący się tutaj `project.godot`.
3. Poczekaj na import grafik. Pierwsze otwarcie może potrwać kilka minut.
4. Uruchom projekt klawiszem **F5**.

Skrypty klienta: `client/scripts`. Grafiki: `client/assets`. Tłumaczenia: `localization`. Bieżące źródła serwera i WWW: `backend`. Źródła dodatków Androida: `tools`.

Ta aktualizacja nie wymaga resetu świata. Baza graczy pozostaje na serwerze; źródła w paczce nie są kopią danych produkcyjnych. Backend w paczce zachowuje wersję 0.12.13 z commitu `5ff017c36b503a512e7f483a774755e88e3e9f21`. Nowe grafiki i poprawki dotyczą klienta Android; witryna produkcyjna nie jest wdrażana przez uruchomienie podpisywacza.

## AAB i podpisywacz Windows

W części paczki z AAB znajduje się `Alien_Colonies_ANDROID_0.12.16_CODE_83_UNSIGNED.aab` oraz `PODPISZ83.bat`.

1. Rozpakuj cały katalog zawierający AAB i podpisywacz. Nie uruchamiaj skryptu bezpośrednio wewnątrz ZIP.
2. Uruchom **PODPISZ83.bat**.
3. Wskaż **ten sam istniejący klucz wysyłania Google Play**, którego używałeś dla wersji 82, i podaj jego alias oraz hasło zgodnie z instrukcją skryptu. Klucz pozostaje na Twoim komputerze.
4. Po pozytywnej weryfikacji powstanie `Alien_Colonies_ANDROID_0.12.16_CODE_83.aab`.
5. Do Play Console prześlij ten podpisany wynik, bez dopisku `UNSIGNED`.

Podpisywacz kontroluje zgodność certyfikatu z poprawnie podpisanym AAB 82. Nie tworzy nowego klucza zastępującego Twój dotychczasowy. Szczegóły wymagań i komunikatów są w `README_PODPISYWANIE_83.txt` obok skryptu.

## Ponowna kompilacja ze źródeł

Gotowe AAR logowania i płatności są dołączone w `addons`. Do budowania całego Androida potrzebne są Java 17, Android SDK 36, Build Tools 36.0.0 oraz szablony Godot 4.5.1.

W Godot wybierz **Project → Install Android Build Template**. Następnie w katalogu projektu uruchom:

```text
python tools/configure_android_build.py
```

Skrypt ustawia wersje narzędzi potrzebne do kompilacji aktualnych zależności Androida. W ustawieniach edytora Godot wskaż katalogi Java SDK i Android SDK. Potem użyj profilu **Google Play AAB**. Profil wydania tworzy plik niepodpisany — podpisz go swoim kluczem przed publikacją.

Katalogi `.godot` i `android/build` są generowane lokalnie i nie są częścią źródeł do przechowywania. Szablon Androida należy zainstalować ponownie przy świeżym rozpakowaniu projektu.

## Sprawdzenia i granice testów

Raporty aktualnej wersji znajdują się w `docs/version83`. Historyczne raporty odzyskania 82 znajdują się w `docs/recovery`.

Testy lokalne obejmują kolory kosztów, aktualizację zasobów, różne rozmiary ekranu i uruchamianie klienta. Kompilacja AAB i kontrola jego zawartości nie zastępują próby instalacji przez Google Play na Twoim urządzeniu. Przed udostępnieniem graczom sprawdź logowanie Google oraz zakupy/subskrypcje w ścieżce testowej aplikacji. Nie wykonywano zakupów ani logowania na Twoim koncie w trakcie przygotowania paczki.
