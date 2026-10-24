# Issue #44 — informacja o wersji i gotowej aktualizacji

Baza po synchronizacji: `main` po scaleniu PR #46 (`23e1cab`). Zachowano trzyetapowe przywracanie z Issue #45; wygenerowany worker obejmuje teraz również komunikat aktualizacji, identyfikator wydania i ręczne sprawdzanie z Issue #44. Logika Drive/JSON, IndexedDB oraz dane treningowe pozostają bez zmian.

## Obsługa

- Gdy kompletne, sprawdzone wydanie workera jest zainstalowane i **czeka**, pojawia się dyskretny komunikat: „Dostępna nowa wersja PushPull. Zapisz bieżące wyniki i zamknij wszystkie okna aplikacji, następnie uruchom ją ponownie.” Sam komunikat niczego nie aktywuje ani nie zamyka.
- W **Dane** jest krótki identyfikator używanego wydania i przycisk **Sprawdź aktualizację**. Identyfikator pochodzi od workera kontrolującego tę stronę, nie z aktualnego pliku na serwerze ani z oczekującej wersji. Telefon i PC można porównać bez mylenia wersji kodu z planem treningowym.
- Błąd pobierania/integralności pokazuje komunikat niepowodzenia i zachowuje poprzednie wydanie. Ręczne sprawdzenie można ponowić. Zwykłe otwarcie z istniejącym workerem offline odczytuje stan lokalny, bez fałszywego ogłaszania nowego pakietu.
- Offline bez pobranego pakietu nie oznacza gotowej aktualizacji. Wcześniej w pełni zainstalowana, oczekująca kopia może być gotowa również offline. Po zamknięciu wszystkich starych klientów i przejściu do nowego wydania powiadomienie znika, a identyfikator pokazuje nową wersję.

## Zachowane zabezpieczenia

Nie dodano `skipWaiting`, wymuszonego reloadu, przejmowania aktywnej sesji ani importu danych. Dotychczasowa instalacja nadal weryfikuje SHA-256 kompletu zasobów i czeka na zamknięcie starych klientów. Szablon otrzymał wyłącznie odpowiedź na zapytanie o publiczny identyfikator wydania; inne komunikaty, w tym żądania wymuszenia aktywacji, nie są obsługiwane.

Stan powiadomienia jest ulotny. Nie czyta ani nie zapisuje IndexedDB, localStorage, szkiców lub konfiguracji Drive. Aktualizacja komunikatu zmienia tylko jego element DOM i etykietę wersji, bez przebudowy aktywnego formularza, utraty fokusu lub ponownego uruchomienia dziennika. Nie zmieniono CSS, ikon, Matrix, planów, historii, snapshotów, statystyk ani kopii Drive/JSON. Dane każdego urządzenia pozostają niezależne.

## Testy i ograniczenia

Istniejące Node/Chromium oraz nowe testy: protokół identyfikatora bez mutacji/aktywacji; rzeczywiste przejście main → wersja z powiadomieniami → kolejne wydanie; dwie karty; duża syntetyczna historia i lokalny edytor L/P z zachowanym fokusem/DOM; błąd odczytu identyfikatora; offline, uszkodzony pakiet i ponowienie; niezależny profil drugiego urządzenia; zgodność całego eksportu bazy, rewizji, szkiców, Google metadata i oryginalnego localStorage. Dokładne wyniki w PR.

Starsza aplikacja bez tej funkcji nie może pokazać nowego komunikatu retroaktywnie. Przy pierwszym przejściu na tę wersję należy raz zapisać pracę, zamknąć wszystkie okna i uruchomić ponownie; komunikaty będą dostępne przy kolejnych aktualizacjach. Starszy worker bez protokołu identyfikatora lub niedostępna komunikacja oznaczają „identyfikator niedostępny”, bez blokowania treningu. Aktualizację wykrywa przeglądarka lub ręczne sprawdzenie; bez sieci nie da się sprawdzić zawartości serwera.

Nie wykonano nowego testu fizycznego Androida ani prawdziwego połączenia Google. Przeglądarka zarządza aktywacją; pozostawiona karta/okno może nadal opóźniać zmianę wersji. Sam zapis szkicu/aktualizacja kodu nie jest kopią zapasową poza urządzeniem. Nie czyścić pamięci aplikacji w celu aktualizacji.
