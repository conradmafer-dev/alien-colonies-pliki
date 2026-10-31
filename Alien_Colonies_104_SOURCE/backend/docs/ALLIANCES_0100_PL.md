# Sojusze — Alien Colonies 0.10.0

Sojusz pozwala koordynować walkę z Rojem i innymi graczami, wysyłać wspólne ataki oraz bronić kolonii swoich członków. Gracze zachowują własne imperia, zasoby, badania i floty. Każdy sam decyduje, które statki przeznacza do operacji.

Wydanie: **0.10.0**, kod Android **45**, pełny projekt oparty na 0.9.5.

## Otwieranie panelu

Wybierz **ikonę wiadomości u góry ekranu → Sojusz**. Po dołączeniu dostępne są zakładki:

| Zakładka | Zawartość |
|---|---|
| Sojusz | Opis, liczba członków, rekrutacja i zarządzanie |
| Członkowie | Lista imperiów, rasy, role oraz decyzje dotyczące podań i zaproszeń |
| Operacje | Plany wspólnych uderzeń, uczestnicy i wsparcie obrony |
| Czat sojuszu | Wiadomości widoczne członkom sojuszu |

Przycisk **Operacje sojuszu** jest też dostępny w szczegółach rozpoznanej, zajętej planety, jeżeli należysz do sojuszu.

## Zakładanie i rekrutacja

Sojusz mieści **20 imperiów**. Jedno imperium należy do najwyżej jednego sojuszu. Założenie sojuszu nie pobiera zasobów.

Nazwa musi mieć 3–32 znaki, a tag 3–5 liter A–Z lub cyfr. Nazwa i tag muszą być unikalne. Opis mieści 500 znaków. Publiczny katalog pokazuje nazwę, tag, opis, lidera i liczebność.

Możesz wysłać podanie do wybranego sojuszu albo przyjąć zaproszenie. Samo wysłanie zaproszenia nie dopisuje gracza do członków. Podania zatwierdza lider lub oficer. Zaproszenia i podania wygasają po **7 dniach**; gracz może mieć do 5 oczekujących podań. Po przyjęciu do sojuszu jego pozostałe podania i zaproszenia są usuwane.

| Uprawnienie | Lider | Oficer | Członek |
|---|---|---|---|
| Czytanie i pisanie na czacie | Tak | Tak | Tak |
| Dołączanie własną flotą do operacji | Tak | Tak | Tak |
| Wysyłanie i odwoływanie własnej obrony | Tak | Tak | Tak |
| Planowanie wspólnego ataku | Tak | Tak | Nie |
| Zapraszanie i rozpatrywanie podań | Tak | Tak | Nie |
| Usuwanie zwykłych członków | Tak | Tak | Nie |
| Usuwanie oficerów | Tak | Nie | Nie |
| Zmiana nazwy, tagu, opisu i ról | Tak | Nie | Nie |
| Przekazanie przywództwa i rozwiązanie sojuszu | Tak | Nie | Nie |

Oficer nie może usunąć lidera ani innego oficera. Lider przed odejściem z sojuszu mającego innych członków przekazuje przywództwo. Rozwiązanie sojuszu wymaga wpisania jego dokładnego tagu.

Usunięcie konta lidera nie pozostawia sojuszu bez właściciela: przywództwo przejmuje oficer, a gdy go nie ma — najdłużej należący członek. Przy jednakowej dacie dołączenia rozstrzyga stały identyfikator imperium.

## Odejście, wyrzucenie i rozejm

Po odejściu, wyrzuceniu lub rozwiązaniu sojuszu obowiązują przez **24 godziny**:

- blokada dołączenia do kolejnego sojuszu i założenia własnego;
- wzajemny zakaz atakowania dotychczasowych sojuszników.

Rozejm działa w obie strony, także po wyrzuceniu przez lidera. Nie daje ogólnej ochrony przed resztą galaktyki. Po zmianie członkostwa serwer ponownie sprawdza dostęp do prywatnych operacji i czatu.

Wysłane własne wsparcie oraz wsparcie broniące kolonii odchodzącego gracza zawraca. Udział odchodzącego w niezakończonym ataku jest usuwany; odejście organizatora anuluje jego aktywną operację. Jeżeli do sojuszu dołączy gracz, przeciw któremu jego członkowie mają już wysłane ataki, te ataki zawracają.

## Wspólny atak krok po kroku

1. Lider lub oficer rozpoznaje cel zwiadem albo obserwatorium, otwiera **Operacje → Zaplanuj atak** i wybiera planetę.
2. Ustala termin uderzenia od **5 minut do 24 godzin** w przyszłości. Należy zostawić czas na dolot wszystkich uczestników.
3. Tworzy plan. Ten krok nie wysyła statków ani nie rezerwuje ich w kolonii.
4. Każdy uczestnik, również organizator, wybiera **Dołącz flotą**, własną kolonię i skład. Wymagany jest przynajmniej jeden okręt bojowy.
5. **Sprawdź trasę** pokazuje czas lotu, termin uderzenia i pełny koszt paliwa. Dopiero **Wyślij flotę** pobiera paliwo i statki z kolonii.
6. Wszystkie dołączone floty uderzają we wspólnym terminie. Wyniki trafiają do raportów uczestników.

Sojusz może prowadzić **3 aktywne plany**. W jednym ataku uczestniczy do **5 imperiów**, każde jedną flotą z jednej kolonii. Te misje wliczają się do istniejącego limitu 8 równoczesnych misji na imperium.

Termin nie przesuwa się po dołączeniu kolejnego gracza. Serwer odrzuci flotę, która nie zdąży dolecieć. **Dołączanie zamyka się 30 sekund przed uderzeniem.** Ten próg dotyczy dołączania: własną flotę można wycofać, a organizator lub lider może anulować operację, dopóki walka nie zostanie rozstrzygnięta. Odwołane statki muszą odbyć lot powrotny; nie pojawiają się natychmiast w kolonii.

Operacje korzystają ze zwykłego lotu. Podróże między galaktykami zachowują wysokie koszty i rzeczywisty czas dolotu. W tej wersji operacje sojuszu nie korzystają z tunelu czasoprzestrzennego.

Plan zawiera podstawowe dane celu z rozpoznania organizatora. Uczestnik może dołączyć do wskazanego celu bez odsłaniania całej galaktyki we własnej mapie. Organizator nie przekazuje w ten sposób bieżących wrogich zapasów, budynków ani floty. Przed rozpoczęciem walki serwer ponownie sprawdza właściciela celu, ochronę, sojusz i rozejm. Niedozwolony atak zawraca.

## Wsparcie obrony

Wybierz **Operacje → Wesprzyj obronę**, kolonię innego członka, własną kolonię startową i statki. Wybierz **1, 4 albo 8 godzin** dyżuru, sprawdź trasę i potwierdź start.

Jedną planetę może wspierać do **5 imperiów**, każde jedną flotą. Własna flota i obrona planetarna właściciela kolonii pozostają odrębną częścią obrony. Nie możesz tym poleceniem wysłać wsparcia do własnej kolonii.

Dyżur zaczyna się **po przylocie**. Dopiero wtedy flota bierze udział w atakach na tę planetę. Może przetrwać kilka bitew podczas jednego dyżuru. Po jego zakończeniu ocalałe jednostki wracają do swojej kolonii. Właściciel może wcześniej użyć **Odwołaj wsparcie**. Zmiana właściciela bronionej planety lub utrata wspólnego sojuszu również powoduje powrót.

Paliwo za podróż w obie strony i cały wybrany dyżur jest pobierane **raz przy starcie**. Wcześniejsze odwołanie nie zwraca paliwa. Obce statki nie są dopisywane do floty właściciela bronionej planety, nie można ich przejąć ani wydać im rozkazów jako własnym.

Wysłanie wsparcia obrony, podobnie jak wysłanie ataku na gracza, **wyłącza ochronę początkową wysyłającego**. Formularz ostrzega o tym przed potwierdzeniem misji. Samo członkostwo ani samo utworzenie planu nie wyłącza ochrony.

## Przebieg i rozliczenie wspólnej bitwy

Wspólny atak jest jedną bitwą, a nie serią oddzielnych pojedynków. Każda uczestnicząca flota ma własne statystyki wynikające z jej rasy, badań i bonusów. Wsparcie nie dziedziczy badań, rasowych premii ani Gaju Odnowy właściciela kolonii. Budynki gospodarza działają na jego własną obronę zgodnie z dotychczasowymi zasadami.

Bitwa trwa do 6 rund. W każdej rundzie:

1. Obie strony obliczają siłę salwy ze stanu na początku rundy. Statki zniszczone w tej rundzie zdążyły oddać swoją salwę.
2. Obrażenia są rozdzielane między floty proporcjonalnie do ich pozostałej efektywnej wytrzymałości. W każdej flocie najpierw trafiane są słabsze kadłuby.
3. Zapisywane są zniszczone jednostki i pozostałe uszkodzenia.
4. Ocalałe jednostki regenerują uszkodzenia zgodnie ze swoimi premiami. Regeneracja nie odtwarza zniszczonych statków.

Atak jest zwycięski, gdy cała obrona zostanie zniszczona i ocaleje przynajmniej jedna jednostka atakujących. Budynki i własność planety nie przechodzą automatycznie na zwycięzców. Nierozstrzygnięta walka kończy się odwrotem.

Każdy uczestnik otrzymuje raport z własnymi stratami, ocalałymi jednostkami i własną zdobyczą. Po otwarciu raportu uruchamia się animacja rzeczywistych rund; jednostki zachowują oznaczenie uczestnika. Dotychczasowe raporty pozostają historycznymi zapisami.

**Łup nie trafia do wspólnego skarbca.** Surowce są dzielone między ocalałe floty w granicach wolnych ładowni. Odzysk metalu z wraków uwzględnia odpowiedni bonus uczestnika i jego udział w sile bojowej. Każdy gracz otrzymuje przewożony łup dopiero po powrocie własnej floty.

**Kryształy Roju mają jeden limit na całą bitwę.** Liczba uczestników nie mnoży nagrody. Premie do zdobywania kryształów są uwzględniane według udziału flot w sile bojowej; podział bierze pod uwagę ten udział i dostępną pojemność ocalałych jednostek. Obowiązują dotychczasowe warunki zasobów i odbudowy Roju.

Dotychczasowe pojedyncze starcia bez sojuszniczego wsparcia korzystają z poprzedniego sposobu rozstrzygania. Pojedynczy atak na planetę z aktywnym wsparciem rozstrzyga się wspólnie z flotami obrońców.

## Transport, mapa i prywatność

Zwykła misja transportowa pozwala dostarczać surowce do własnych oraz rozpoznanych kolonii sojuszników. To transport ładunku: statki pozostają własnością wysyłającego i wracają. Jeżeli przed dostawą zmieni się odbiorca lub ustanie sojusz, transport wraca z ładunkiem.

Sojusz nie łączy automatycznie obserwatoriów i archiwów zwiadu. Panel obrony udostępnia nazwy i położenie kolonii sojuszników potrzebne do wysłania pomocy; nie odsłania przez to pozostałych układów ani zasobów, budynków i badań członków. Informacje o wrogach nadal pochodzą z własnego rozpoznania i zapisów konkretnych operacji. Rzadkie cechy planet nadal odkrywa się zwiadem lub obserwatorium.

Czat przechowuje ostatnie 100 wiadomości i jest dostępny aktualnym członkom. Jedna wiadomość mieści 500 znaków. Podania i oczekujące zaproszenia do zarządzania widzą tylko lider i oficerowie; kandydat widzi swoje. Osoba spoza sojuszu nie otrzymuje jego prywatnych operacji ani czatu. Usunięcie konta usuwa jego wiadomości sojuszu. Wyciszenie nałożone przez operatora obejmuje również wysyłanie wiadomości w sojuszu.

## Aktualizacja istniejącego świata

Zaktualizuj klienta oraz **całą zawartość `railway/`**, w tym `alliances.py`, `alliance_operations.py`, `app.py`, `Dockerfile` i pięć plików tłumaczeń. Zachowaj istniejący Volume, bazę i jedną replikę. Aktualizacja dopisuje schemat sojuszy; nie wymaga resetu świata ani nowych zmiennych środowiskowych.

Dane sojuszy, floty, terminy, raporty i rozliczenia są zapisywane trwale. Restart nie rozpoczyna ponownie misji. Serwer chroni przed podwójnym wykonaniem ponowionego żądania i dwukrotnym rozładunkiem tej samej floty. Awaria zapisu cofa daną transakcję, także gdy obejmuje rozstrzygnięcie wspólnej bitwy.

`PGR_MIN_VERSION_CODE` nie jest automatycznie podnoszone do 45. Minimum można zmienić po udostępnieniu odpowiedniego klienta graczom. Instrukcje zmiennych zawiera `railway/VARIABLES_0100.txt`.

Przy wycofaniu aktualizacji przywróć starszy kod **wraz z odpowiadającą mu kopią bazy**. Starszy serwer nie rozpoznaje nowych misji. Wyniki testów są w `VERIFICATION_0100.json` i `docs/verification_0100/`.

To pełna paczka źródłowa. Nie wykonano eksportu APK/AAB, wdrożenia produkcyjnego ani resetu świata podczas jej przygotowania.
