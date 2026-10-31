# Sprawdzenia wersji 84 / 0.12.17

- 349 asercji mapowania grafiki na rzeczywistych katalogach trzech ras: PASS.
- 112 asercji ładowania 18 rzeczywistych tekstur w Godot 4.5.1: PASS. Obserwatoria, laboratoria i Obserwatorium Echa mają odrębne zasoby.
- 15 nowych ilustracji, wszystkie 1536 × 1024: 13 budynków Symbiontów oraz obserwatoria Zetan i Automatonów.
- Sprawdzono wszystkie 238 metadanych importu klienta: brak niepoprawnych importów i brakujących plików.
- Ostateczny AAB: 61/61 skryptów zgodnych ze źródłami i 53/53 obrazów zgodnych piksel w piksel (nowe budynki, statki z83 oraz logowanie).
- Android: bundletool validate i CRC poprawne, kod84/nazwa0.12.17, pakiet com.conradmafer.aliencolonies, SDK24–36, ARM32/64, wyrównanie bibliotek ARM64 do16KB.
- Dodatki logowania Google i Google Play Billing obecne w AAB.
- Podpisywacz84: kontrola dokładnego AAB, pakietu, numeru84 i istniejącego certyfikatu82; kompilacja oraz uruchomienie kodu Java pod JDK17: PASS.

Nie wykonano logowania Google ani zakupów na telefonie, ani graficznego podpisywania Windows z prywatnym kluczem właściciela. Te działania należy sprawdzić lokalnie i w teście wewnętrznym Google Play.

Pełne prompty generowania obrazów, ścieżki plików oraz sumy SHA256 zapisano w manifestach art_*_manifest.json. Użyto wbudowanego image_gen; finalne zasoby projektu to pliki WebP w client/assets/art/races.
