# Sprawdzenia wersji 83 / 0.12.16

- Testy kosztów megastruktur i układu logowania: 352 sprawdzenia, bez błędów.
- Nowe statki: 36 różnych obrazów, po 12 dla każdej rasy, wszystkie zmienione względem 82.
- Ostateczny AAB: 61/61 skryptów zgodnych ze źródłami oraz 38/38 zmienionych obrazów zgodnych piksel w piksel.
- Wszystkie importy grafik poprawne; frachtowiec Zetan znajduje się w końcowym AAB.
- Klient uruchamia się w Godot 4.5.1 w trybie headless bez błędów parsowania.
- Android: bundletool validate i CRC poprawne, kod wersji 83, nazwa 0.12.16, pakiet com.conradmafer.aliencolonies, SDK 24–36, ARM 32/64, wyrównanie bibliotek ARM64 do 16 KB.
- Dodatki logowania Google i Google Play Billing obecne w AAB.
- Podpisywacz sprawdza sumę konkretnego AAB, pakiet, wersję oraz dotychczasowy certyfikat wydania 82. Jego kod Java sprawdzony pod JDK 17.

Nie wykonano logowania Google ani zakupów na fizycznym urządzeniu. Nie uruchomiono okienkowego podpisywania w Windows z prywatnym kluczem właściciela. Te działania należy sprawdzić lokalnie i w teście wewnętrznym Google Play przed publikacją dla graczy.

Szczegóły i sumy znajdują się w raportach JSON w tym katalogu.
