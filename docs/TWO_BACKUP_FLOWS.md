# Dane — dwa przepływy kopii i poprawka B3

Baza: `main` `fb6c975` po PR #107. Zakres: interfejs istniejących kopii oraz anulowanie odczytu/podglądu. Nie powstał nowy backend kopii. Plan nadrzędny i AGENTS.md pozostają obowiązujące. Ten etap zastępuje historyczne cztery przyciski opisane w [etapie G](SIMPLE_DATA_STAGE_G.md).

## Interfejs

Główne działania to **Zapisz kopię** i **Przywróć kopię**. Można rozwinąć tylko jedno; zamknięcie lub przełączenie przerywa oczekiwanie na podgląd. Stan rozwinięcia jest wyłącznie w pamięci UI, nie w ustawieniach ani danych. Otwarcie tych sekcji nie odczytuje pełnej historii lub archiwów.

- Zapis: Telefon / dysk (dotychczasowy eksport) lub ręczny Google Drive (dotychczasowy upload oraz weryfikacja POST/GET, SHA-256).
- Przywracanie: Z pliku lub Google Drive. Lista, weryfikacja, porównanie, potwierdzenie i wynik pozostają w tej samej sekcji. Wybór nie zapisuje danych. Gotowy podgląd otrzymuje fokus i jest przewijany na ekran.
- Drive używa istniejącego `download(..., {forRestore:true})`. Po świadomym potwierdzeniu zweryfikowany tekst trafia bezpośrednio do istniejącego importera; nie trzeba najpierw pobierać pliku na telefon.
- Pomocnicze pobranie oryginalnego JSON z Drive jest nadal dostępne w rozwijanej opcji przywracania, bez trzeciego przycisku głównego i bez importu.
- Po udanym przywróceniu aplikacja pozostaje w Dane, z wynikiem bezpośrednio w sekcji przywracania. Trening jest dostępny przez dotychczasową nawigację.
- Status, szczegóły błędów Drive, przycisk połączenia Google oraz komunikat audytu dla zapisu są bezpośrednio przy wybranej operacji. Zaawansowana konfiguracja, diagnostyka, zachowane kopie i eksperymentalne podglądy pozostają dostępne.

Dodatkowy CSS wyłącznie zapewnia ukrycie nieaktywnej sekcji: istniejąca `.stack { display: grid }` inaczej przysłania przeglądarkowe `hidden`. Nie zmieniono stylu kart treningu/Matrix, ikon ani pozostałego układu.

## B3 — przyczyna i naprawa

Przed zmianą `change` pliku oczekiwał na `file.text()` i `prepareRestore()` we wspólnej kolejce `actions`. Kolejny klik nawigacji trafiał za to oczekiwanie. Sam worker nie wystarczał: jego wynik również blokował zakończenie handlera. Pełny audyt przed obsługą pliku zajmował tę samą kolejkę.

Test najpierw zatrzymał rzeczywisty `File.text()` na jawnej bramce. Przed poprawką klik Trening nie był obsługiwany przed zwolnieniem odczytu (RED). Po poprawce ten sam test przechodzi bez zwalniania bramki przed nawigacją (GREEN).

Odczyt pliku, niezbędny audyt lokalny i podgląd są teraz zadaniem poza kolejką zdarzeń UI. Numer operacji i odczyt pliku są rezerwowane synchronicznie w `change`, zanim inne kliknięcie może trafić do kolejki. Osobny test wyboru i nawigacji w tej samej turze był RED przed tą ochroną, następnie GREEN. Anulowanie/opuszczenie ekranu podczas podglądu natychmiast unieważnia numer operacji. AbortController kończy worker lokalnego porównania; spóźniony odczyt, komunikat workera lub błąd nie publikuje podglądu ani statusu. Nowy wybór unieważnia poprzedni. Zmiana bazy podczas odczytu również unieważnia operację. Błędy pliku są wyświetlane w sekcji przywracania.

Kontrola rewizji i oryginalnego localStorage pozostaje przed/po podglądzie oraz przed zatwierdzeniem; nie usunięto audytu potrzebnego do pełnego porównania. Lista kopii Drive nie wymaga lokalnego `ensureFull()`; porównanie wybranego pliku nadal go wymaga. Nie przeniesiono audytu na zwykłą nawigację.

`File.text()`, rozpoczęty odczyt IndexedDB oraz istniejące HTTP Drive nie mają tutaj fizycznego przerwania. Mogą dokończyć odczyt w tle. Unieważnienie blokuje ich późniejszy efekt UI/import/pobranie. Nie deklarujemy, że anulowanie natychmiast odzyskuje całą pamięć lub zatrzymuje zdalne żądanie. Podczas rzeczywistej transakcji importu nie oferujemy anulowania commitu.

## Zachowane zabezpieczenia

Nie zmieniono modułów backendu, formatów v1–v6, IndexedDB v2, schematu, CAS, walidacji, readback ani `strict complete`. Import nadal wymaga osobnego potwierdzenia systemowego. Atomowy preimage oraz ochrona szkiców/historii/archiwów pozostają w istniejącym importerze. Nie dodano synchronizacji, retencji ani automatycznego usuwania danych.

B1 nadal przekazuje `isCurrent` i chroni pobranie oraz status przed spóźnioną odpowiedzią. Przywracanie Drive korzysta teraz z tego samego istniejącego argumentu. B2 nadal rezerwuje upload synchronicznie przed pierwszym `await`/audytem. Nowe operacje są dostępne po zakończeniu lub błędzie poprzedniej; podwójne kliknięcia nie są kolejką kolejnych kopii.

## Weryfikacja

Wyniki końcowej regresji i CI są uzupełnione w PR. Testy korzystają z izolowanych syntetycznych danych i prawdziwego Chromium/IndexedDB; OAuth i Google HTTP są symulowane.

- Node: **260/260 PASS**. Końcowy ukierunkowany przebieg Chromium nowych przepływów i B1/B2: **14/14 PASS** (8 nowych scenariuszy i 6 istniejących regresji). Składnia, hashe SW, build produkcyjny i `git diff --check`: PASS. Release `ab3303c619bac60baa83f50a`.
- PWA po dostosowaniu testów do dwóch przepływów: **33/33 PASS**, w tym rzeczywiste service workery, aktualizacje historycznych wydań i duża kopia offline.
- Pełny lokalny przebieg wykonał 261 scenariuszy: 249 PASS, 12 początkowo nieudanych. Przyczyną były stare oczekiwania ekranu Trening po imporcie, brak otwierania nowych sekcji w osobnej klasie PWA oraz odczyt geometrii i klasy ResizeObserver w dwóch różnych turach JS. Po korektach sprawdzono ponownie wszystkie te przypadki: PWA 33/33, trzy scenariusze importu/odzyskiwania 3/3 oraz atomowy pomiar układu 1/1 PASS. Zachowano porównania wszystkich danych i dotychczasową asercję liczby linii; nie zmieniono formattera wyników ani nie dodano tolerancji/sleep. Nie powtarzano niezmienionej reszty pełnego przebiegu. Końcowy pełny CI zamrożonego commitu (264 scenariusze, w tym trzy dodatkowe testy) jest podany w PR.
- Nowe scenariusze: nawigacja przy zatrzymanym odczycie pliku oraz wybór/nawigacja w jednej turze, anulowanie workera i spóźniony komunikat po nowym wyborze, błędny JSON/odczyt, konflikt podczas podglądu, dwa przepływy przy 360/390/412 px, fokus i przewinięcie, brak zapisu przy wyborze/odmowie potwierdzenia, eksport offline, bezpośrednie przywrócenie Drive, podwójny klik potwierdzenia, preimage i restart; anulowany podgląd Drive ze spóźnionym błędem HTTP.
- Dotychczasowe testy rozszerzono jedynie o jawne otwieranie nowych sekcji. Asercje danych, CAS, backupów i historii pozostają. Oczekiwanie alertu błędnego pliku zastąpiono sprawdzeniem konkretnego błędu w sekcji operacji. Sukces przywrócenia jest sprawdzany w Dane, zgodnie z nowym wymaganiem.
- Zachowane regresje B1/B2: spóźnione powodzenie i HTTP 500 po anulowaniu, podwójny upload przed audytem, anulowany audyt, błędy offline/POST/readback/integralności i późniejsza świadoma próba.
- Pełna regresja obejmuje stare kopie, trening, szkice, historię, plany, offline, aktualizacje PWA, restart, CAS oraz błędy zapisu. Szczegółowe wyniki są w PR.

## Ograniczenia

Brak testu fizycznego Pixela 9 i rzeczywistego OAuth/Drive. Nie zmieniono kosztu ani zapotrzebowania pamięci dotychczasowej pełnej walidacji/importu lub listowania wielu dużych plików Drive. Oddzielenie kolejki nie jest dowodem braku wszystkich długich zadań na każdym urządzeniu. Kopie >200 MB i zagnieżdżone archiwa nie są naprawiane tym etapem. Dotychczasowy fallback podglądu bez obsługi Worker pozostaje bez zmian; na wspieranym Chromium podgląd odbywa się w workerze.

Eksport na telefon potwierdza tylko zlecenie pobrania, nie fizyczny zapis przez menedżer Androida. Eksperymentalne formaty z zaawansowanych nadal mają poprzednie ograniczenia przywracania. Nie scalono PR ani nie wykonano ręcznego wdrożenia.
