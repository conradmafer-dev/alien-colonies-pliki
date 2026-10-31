# Opcjonalne odtwarzanie skryptów

Wymaga Python 3.10+ oraz pakietu `zstandard` (np. `python -m pip install zstandard`).
Narzędzie nie łączy się z serwerem gry, nie podpisuje i nie modyfikuje AAB.

`python recover_gdsc.py "Alien_Colonies_ANDROID_0.12.15_CODE_82.aab" "nowy_folder"`

Porównanie leksykalne nie jest kompilacją Godota. Zgodność wersji bufora:
GDSC 101, Godot 4.5.1. Format tokenów sprawdzono w źródłach Godot 4.5.1:
https://github.com/godotengine/godot/blob/4.5.1-stable/modules/gdscript/gdscript_tokenizer.h
https://github.com/godotengine/godot/blob/4.5.1-stable/modules/gdscript/gdscript_tokenizer_buffer.cpp
