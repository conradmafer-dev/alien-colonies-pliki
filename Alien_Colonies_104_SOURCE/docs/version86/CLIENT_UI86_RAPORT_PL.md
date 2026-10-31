# Klient 86 — osobny etap nazwy imperium

Status: **CLIENT FREEZE**, wersja **86 / 0.12.19**.

Po odpowiedzi `needs_name` Google i e-mail korzystają z jednego przejścia do osobnego `EmpireNamePanel`. Nazwa, „Stwórz imperium” i „Anuluj” są na górze. Stary panel logowania, przyciski Google/e-mail/utworzenia konta, grafika tła, ogłoszenie i stopka są schowane; nowy etap ma własne ciemne tło. Ogłoszenie oraz odświeżenia konfiguracji nie mogą odsłonić starego ekranu.

Błąd nazwy 400/409 zachowuje nazwę oraz potwierdzenie konta. Anulowanie i wygaśnięcie wracają do wyboru logowania. Sukces istniejącego konta prowadzi do gry; nowe imperium trafia do wyboru rasy. Odroczone sprawdzenie martwego flow respektuje kolejność `cancel → changed → completed` stosowaną przez kontrolery. Nie zmieniono protokołu, kontrolerów Google/e-mail ani walidacji.

Godot 4.5.1 headless: **1796 sprawdzeń, 0 błędów**. Testy obejmują rzeczywiste UI i maszyny stanów obu kontrolerów ze sztucznymi odpowiedziami HTTP/native: needs_name, kompletowanie, błąd lokalny i 400/409, ponowne konfiguracje, spóźnione ogłoszenie, cancel, deadline, ciche unieważnienie flow, istniejące konto, wybór rasy, logout, sesja401 i reauth. Widoczność i prostokąty nazwy/przycisków sprawdzono w PL/EN dla 720×960, 720×1280, 800×480, 640×360 i 960×640, w tym stabilność progu kompaktowego układu. Test zachowania marginesów klawiatury/safe area nie zastępuje testu na telefonie.

Raport: `auth_ui86_report.json`; log: `auth_ui86_runtime.log`; zmiany: `client_ui86.diff`; sumy plików zamrożenia: `client_freeze86.json`. Harness: `ui_project/test_auth86.gd`, rzeczywiste moduły skopiowane z finalnego źródła86. Przechowywanie sesji i renderowanie pełnego ekranu gry są stubowane; routing auth i widoczność ekranów są rzeczywiste.

Nie wykonano prawdziwego logowania Google/e-mail, zakupów ani testu urządzenia. Brak desktopowego display/compositora: headless korzysta z dummy rendering, dlatego nie przygotowano pozornych zrzutów telefonu i nie używano Xvfb. Bez sieci, push i wdrożenia.
